"""Python 2 -> 3 upgrader: textual syntax rules, then AST-based semantic rules.

Syntax rules run on a masked copy of the source, so string literals and comments are
never rewritten. Once the code parses as Python 3, the integer-division rule uses the
AST to find `/` whose operands are provably integers and keeps Python 2's floor
semantics with `//`.
"""

import ast
import re

from version_upgrade_system.core.gated import GatedUpgrader, Rule
from version_upgrade_system.core.textscan import group, mask, matching, splice, sub
from version_upgrade_system.languages.python.enterprise_engine.version_detector import PythonVersionDetector

LANG = "python"


def _regex_rule(name, pattern, replacement):
    def apply(code):
        return sub(pattern, lambda m, src: m.expand(replacement), code, LANG)
    return Rule(name, apply)


def _print_statements(code):
    masked = mask(code, LANG)
    edits = []
    # A statement start: line start, or after the colon of a one-line compound statement.
    for match in re.finditer(r"(^[ \t]*|:[ \t]*)print\b(?![ \t]*\()([^\n]*)$", masked, re.MULTILINE):
        start, end = match.start(2), match.end(2)
        masked_content = masked[start:end].strip()
        if masked_content.startswith("="):
            continue  # an assignment to a variable named print
        content = code[start:end].strip()
        stream = ""
        if masked_content.startswith(">>"):
            target, _, rest = content[2:].partition(",")
            stream, content = f"file={target.strip()}", rest.strip()
        ending = ""
        if content.endswith(","):
            content, ending = content[:-1].rstrip(), 'end=" "'
        arguments = ", ".join(part for part in (content, ending, stream) if part)
        edits.append((match.start(0) + len(match.group(1)), end, f"print({arguments})"))
    return splice(code, edits)


def _has_key(code):
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"([A-Za-z_][\w.]*)\.has_key\(", masked):
        close = matching(masked, match.end() - 1)
        if close == -1:
            continue
        key = code[match.end():close].strip()
        # Parenthesised so `d.has_key(k) == x` does not become a chained comparison.
        edits.append((match.start(), close + 1, f"({key} in {match.group(1)})"))
    return splice(code, edits)


def _raise_comma(code):
    def replace(match, src):
        return f"raise {group(match, src, 1)}({group(match, src, 2).strip()})"
    return sub(r"\braise[ \t]+([A-Za-z_][\w.]*)[ \t]*,[ \t]*([^\n]+?)[ \t]*$", replace, code, LANG)


def _list_views(code):
    """`x = d.keys()` returned a list in Python 2; keep it a list where it is stored."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"^[ \t]*[A-Za-z_]\w*[ \t]*=[ \t]*", masked, re.MULTILINE):
        start = match.end()
        line_end = masked.find("\n", start)
        line_end = len(masked) if line_end == -1 else line_end
        value = masked[start:line_end].rstrip()
        if re.fullmatch(r"[\w.]+\.(keys|values|items)\(\)", value):
            edits.append((start, start + len(value), f"list({code[start:start + len(value)]})"))
        elif re.match(r"(map|filter|zip)\(", value):
            close = matching(masked, start + value.index("("))
            if close == start + len(value) - 1:
                edits.append((start, close + 1, f"list({code[start:close + 1]})"))
    return splice(code, edits)


def _int_names(tree):
    """Names whose every binding is provably an int."""
    bindings = {}

    def bind(name, value):
        bindings.setdefault(name, []).append(value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bind(target.id, node.value)
                else:
                    for element in ast.walk(target):
                        if isinstance(element, ast.Name):
                            bind(element.id, None)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and isinstance(node.target, ast.Name):
            value = node.value
            if isinstance(node, ast.AugAssign):
                value = ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op, right=node.value)
            bind(node.target.id, value)
        elif isinstance(node, ast.For):
            iterator = node.iter
            is_range = (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name)
                        and iterator.func.id == "range" and isinstance(node.target, ast.Name))
            for element in ast.walk(node.target):
                if isinstance(element, ast.Name):
                    bind(element.id, iterator if is_range else None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            for argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
                bind(argument.arg, None)
            for argument in (arguments.vararg, arguments.kwarg):
                if argument:
                    bind(argument.arg, None)
        elif isinstance(node, (ast.With, ast.ExceptHandler, ast.comprehension, ast.NamedExpr,
                               ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
            for element in ast.walk(node):
                if isinstance(element, ast.Name) and isinstance(element.ctx, ast.Store):
                    bind(element.id, None)
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                for name in node.names:
                    bind(name, None)
            if isinstance(node, ast.ExceptHandler) and node.name:
                bind(node.name, None)

    known = set()

    def is_int(expr):
        if isinstance(expr, ast.Constant):
            return type(expr.value) is int
        if isinstance(expr, ast.Name):
            return expr.id in known
        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.USub, ast.UAdd, ast.Invert)):
            return is_int(expr.operand)
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Sub, ast.Mult,
                                                                 ast.FloorDiv, ast.Mod, ast.Div)):
            return is_int(expr.left) and is_int(expr.right)
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and len(expr.args) >= 1:
            if expr.func.id in ("int", "len", "ord"):
                return True
            if expr.func.id == "range":
                return all(is_int(a) for a in expr.args)
            if expr.func.id == "abs" and len(expr.args) == 1:
                return is_int(expr.args[0])
        return False

    changed = True
    while changed:
        changed = False
        for name, values in bindings.items():
            if name not in known and all(v is not None and is_int(v) for v in values):
                known.add(name)
                changed = True
    return is_int


def _int_division(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    is_int = _int_names(tree)

    lines = code.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    masked = mask(code, LANG)

    def position(line, column):
        text = lines[line - 1].encode("utf-8")[:column].decode("utf-8", "ignore")
        return offsets[line - 1] + len(text)

    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) \
                and is_int(node.left) and is_int(node.right):
            start = position(node.left.end_lineno, node.left.end_col_offset)
            end = position(node.right.lineno, node.right.col_offset)
            slash = masked.find("/", start, end)
            if slash != -1 and masked[slash + 1] != "/":
                edits.append((slash, slash + 1, "//"))
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Div) \
                and is_int(node.target) and is_int(node.value):
            start = position(node.target.end_lineno, node.target.end_col_offset)
            end = position(node.value.lineno, node.value.col_offset)
            slash = masked.find("/=", start, end)
            if slash != -1:
                edits.append((slash, slash + 2, "//="))
    return splice(code, edits)


def _true_divisions(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.Div))


# Python 2 modules renamed in Python 3 whose attributes kept their names (2to3's fix_imports).
RENAMED_MODULES = {
    "ConfigParser": "configparser", "Queue": "queue", "cPickle": "pickle", "StringIO": "io", "cStringIO": "io",
    "urllib2": "urllib.request", "urlparse": "urllib.parse", "httplib": "http.client", "HTMLParser": "html.parser",
    "Cookie": "http.cookies", "cookielib": "http.cookiejar", "BaseHTTPServer": "http.server",
    "SimpleHTTPServer": "http.server", "SocketServer": "socketserver", "Tkinter": "tkinter",
    "tkMessageBox": "tkinter.messagebox", "__builtin__": "builtins", "copy_reg": "copyreg", "thread": "_thread",
    "xmlrpclib": "xmlrpc.client", "anydbm": "dbm", "commands": "subprocess", "htmlentitydefs": "html.entities",
}
ITERTOOLS = {"izip": "zip", "imap": "map", "ifilter": "filter"}


def _imports(code):
    """import X / import X as Y / from X import ...  for the renamed modules."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"^([ \t]*)import[ \t]+([^\n#;]+)", masked, re.MULTILINE):
        parts = []
        changed = False
        for item in code[match.start(2):match.end(2)].split(","):
            name, _, alias = item.strip().partition(" as ")
            name, alias = name.strip(), alias.strip()
            if name in RENAMED_MODULES:
                parts.append(f"{RENAMED_MODULES[name]} as {alias or name}")
                changed = True
            else:
                parts.append(item.strip())
        if changed:
            edits.append((match.start(2), match.end(2), ", ".join(parts)))
    for match in re.finditer(r"^([ \t]*)from[ \t]+([\w.]+)[ \t]+import\b", masked, re.MULTILINE):
        if match.group(2) in RENAMED_MODULES:
            edits.append((match.start(2), match.end(2), RENAMED_MODULES[match.group(2)]))
    return splice(code, edits)


def _itertools(code):
    """izip/imap/ifilter became the builtins zip/map/filter."""
    code = sub(r"\bitertools\.(izip|imap|ifilter)\b", lambda m, src: ITERTOOLS[m.group(1)], code, LANG)
    code = sub(r"\bitertools\.izip_longest\b", lambda m, src: "itertools.zip_longest", code, LANG)
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"^([ \t]*)from[ \t]+itertools[ \t]+import[ \t]+([^\n#;()]+)$", masked, re.MULTILINE):
        names = [n.strip() for n in code[match.start(2):match.end(2)].split(",") if n.strip()]
        builtins = [n for n in names if n in ITERTOOLS]
        if not builtins:
            continue
        rest = [("zip_longest" if n == "izip_longest" else n) for n in names if n not in ITERTOOLS]
        indent = match.group(1)
        lines = [f"{indent}from itertools import {', '.join(rest)}"] if rest else []
        lines.append(f"{indent}{', '.join(builtins)} = {', '.join(ITERTOOLS[n] for n in builtins)}")
        edits.append((match.start(), match.end(), "\n".join(lines)))
    return splice(code, edits)


def _add_import(code, statement):
    """statement after the module docstring, __future__ imports and leading comments."""
    if re.search(rf"^{re.escape(statement)}\s*$", code, re.MULTILINE):
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    line = 0
    for node in tree.body:
        is_docstring = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
            and isinstance(node.value.value, str) and node is tree.body[0]
        is_future = isinstance(node, ast.ImportFrom) and node.module == "__future__"
        if is_docstring or is_future:
            line = node.end_lineno
        else:
            break
    lines = code.splitlines(keepends=True)
    return "".join(lines[:line]) + statement + "\n" + "".join(lines[line:])


def _cmp_arguments(code):
    """sort(cmp=f) / sorted(x, cmp=f) -> key=functools.cmp_to_key(f)."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"\b(sort|sorted)\(", masked):
        close = matching(masked, match.end() - 1)
        if close == -1:
            continue
        argument = re.search(r"(?<![\w.])cmp[ \t]*=[ \t]*", masked[match.end():close])
        if not argument:
            continue
        start = match.end() + argument.end()
        depth, end = 0, start
        # The value ends at the closing parenthesis or at a comma that starts another keyword
        # argument; a comma between lambda parameters does neither.
        while end < close:
            if masked[end] in "([{":
                depth += 1
            elif masked[end] in ")]}":
                depth -= 1
            elif masked[end] == "," and depth == 0 and re.match(r"\s*\w+\s*=(?!=)", masked[end + 1:close]):
                break
            end += 1
        value = code[start:end].strip()
        edits.append((match.end() + argument.start(), end, f"key=functools.cmp_to_key({value})"))
    if not edits:
        return code
    return _add_import(splice(code, edits), "import functools")


def _reduce(code):
    """reduce moved to functools."""
    masked = mask(code, LANG)
    if not re.search(r"(?<![\w.])reduce\s*\(", masked) or re.search(r"\bdef\s+reduce\b|\bimport\b[^\n]*\breduce\b", masked):
        return code
    return _add_import(code, "from functools import reduce")


def _next_methods(code):
    """def next(self) also serves Python 3's iterator protocol; it.next() becomes next(it)."""
    masked = mask(code, LANG)
    lines = code.splitlines(keepends=True)
    masked_lines = masked.splitlines(keepends=True)
    inserts = []
    for index, line in enumerate(masked_lines):
        found = re.match(r"^([ \t]+)def[ \t]+next[ \t]*\([ \t]*self[ \t]*\)[ \t]*:", line)
        if not found:
            continue
        indent = found.group(1)
        end = index + 1
        while end < len(masked_lines):
            text = masked_lines[end]
            if text.strip() and len(text) - len(text.lstrip()) <= len(indent):
                break
            end += 1
        if not any(re.match(rf"^{indent}__next__\b", l) for l in masked_lines):
            inserts.append((end, f"{indent}__next__ = next\n"))
    for position, text in sorted(inserts, reverse=True):
        if position > 0 and not lines[position - 1].endswith("\n"):
            lines[position - 1] += "\n"
        lines.insert(position, text)
    code = "".join(lines)
    return sub(r"(?<![\w.])([A-Za-z_][\w.]*)\.next\(\)", lambda m, src: f"next({group(m, src, 1)})", code, LANG)


def _apply_calls(code):
    """apply(f, args[, kwargs]) -> f(*args[, **kwargs])."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"(?<![\w.])apply\(", masked):
        close = matching(masked, match.end() - 1)
        if close == -1:
            continue
        arguments, depth, start = [], 0, match.end()
        for k in range(match.end(), close + 1):
            ch = masked[k]
            if ch in "([{":
                depth += 1
            elif ch in ")]}" and k != close:
                depth -= 1
            if (ch == "," and depth == 0) or k == close:
                arguments.append(code[start:k].strip())
                start = k + 1
        if len(arguments) not in (2, 3) or not all(arguments):
            continue
        call = f"{arguments[0]}(*{arguments[1]}" + (f", **{arguments[2]})" if len(arguments) == 3 else ")")
        edits.append((match.start(), close + 1, call))
    return splice(code, edits)


def _backticks(code):
    """`x` was repr(x)."""
    masked = mask(code, LANG)
    edits = [(m.start(), m.end(), f"repr({code[m.start() + 1:m.end() - 1]})")
             for m in re.finditer(r"`([^`\n]+)`", masked)]
    return splice(code, edits)


def _long_literals(code):
    return sub(r"(?<![\w.])(\d+|0[xX][0-9a-fA-F]+)[lL]\b", lambda m, src: group(m, src, 1), code, LANG)


def _execfile(code):
    """execfile(path) -> exec(open(path).read())."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"(?<![\w.])execfile\(", masked):
        close = matching(masked, match.end() - 1)
        if close != -1 and "," not in masked[match.end():close]:
            edits.append((match.start(), close + 1, f"exec(open({code[match.end():close].strip()}).read())"))
    return splice(code, edits)


def _builtin_call(old, new, extra_import=None):
    """A removed builtin call `old(` -> `new(` unless the program defines its own `old`."""
    def apply(code):
        masked = mask(code, LANG)
        if re.search(rf"\bdef\s+{old}\b|^\s*{old}\s*=", masked, re.MULTILINE):
            return code
        rewritten = sub(rf"(?<![\w.]){old}\(", lambda m, src: f"{new}(", code, LANG)
        if extra_import and rewritten != code:
            rewritten = _add_import(rewritten, extra_import)
        return rewritten
    return apply


class PythonEnterpriseUpgrader(GatedUpgrader):

    language = LANG
    engine = "Python 2 to 3 engine (validation-gated)"
    detector = PythonVersionDetector()

    def rules(self, code):
        return [
            Rule("print statement -> print()", _print_statements),
            Rule("except X, e -> except X as e", lambda c: sub(
                r"^([ \t]*except[ \t]+)([\w.]+|\([^)\n]*\))[ \t]*,[ \t]*(\w+)[ \t]*:",
                lambda m, src: f"{group(m, src, 1)}{group(m, src, 2)} as {group(m, src, 3)}:", c, LANG)),
            Rule("raise E, msg -> raise E(msg)", _raise_comma),
            Rule("exec statement -> exec()", lambda c: sub(
                r"^([ \t]*)exec[ \t]+(?!\()([^\n]+)$",
                lambda m, src: f"{group(m, src, 1)}exec({group(m, src, 2).strip()})", c, LANG)),
            _regex_rule("<> -> !=", r"<>", "!="),
            _regex_rule("xrange() -> range()", r"\bxrange\(", "range("),
            _regex_rule("raw_input() -> input()", r"\braw_input\(", "input("),
            _regex_rule("dict.iteritems() -> items()", r"\.iteritems\(\)", ".items()"),
            _regex_rule("dict.iterkeys() -> keys()", r"\.iterkeys\(\)", ".keys()"),
            _regex_rule("dict.itervalues() -> values()", r"\.itervalues\(\)", ".values()"),
            Rule("dict.has_key(k) -> k in dict", _has_key),
            _regex_rule("basestring -> str", r"\bbasestring\b", "str"),
            _regex_rule("unicode -> str", r"(?<![\w.])unicode\b", "str"),
            _regex_rule("long() -> int()", r"\blong\(", "int("),
            _regex_rule("octal 0NNN -> 0oNNN", r"(?<![\w.])0([0-7]+)\b", r"0o\1"),
            Rule("long literal 10L -> 10", _long_literals),
            Rule("renamed modules (ConfigParser, Queue, cPickle, urllib2, StringIO, ...)", _imports),
            Rule("itertools.izip/imap/ifilter -> zip/map/filter", _itertools),
            _regex_rule("sys.maxint -> sys.maxsize", r"\bsys\.maxint\b", "sys.maxsize"),
            _regex_rule("string.letters/lowercase/uppercase -> ascii_*",
                        r"\bstring\.(letters|lowercase|uppercase)\b", r"string.ascii_\1"),
            _regex_rule("dict.viewkeys()/viewvalues()/viewitems() -> keys()/values()/items()",
                        r"\.view(keys|values|items)\(\)", r".\1()"),
            _regex_rule("os.getcwdu() -> os.getcwd()", r"\bos\.getcwdu\(", "os.getcwd("),
            Rule("unichr() -> chr()", _builtin_call("unichr", "chr")),
            Rule("file() -> open()", _builtin_call("file", "open")),
            Rule("intern() -> sys.intern()", _builtin_call("intern", "sys.intern", "import sys")),
            Rule("execfile(f) -> exec(open(f).read())", _execfile),
            Rule("apply(f, args) -> f(*args)", _apply_calls),
            Rule("`x` -> repr(x)", _backticks),
            Rule("sort(cmp=f) -> sort(key=functools.cmp_to_key(f))", _cmp_arguments),
            Rule("reduce() -> functools.reduce()", _reduce),
            _regex_rule("__nonzero__ -> __bool__", r"\bdef[ \t]+__nonzero__\(", "def __bool__("),
            Rule("iterator next() -> __next__ / next(it)", _next_methods),
            Rule("stored keys()/values()/items()/map()/filter()/zip() -> list()", _list_views),
            Rule("integer / -> // (operands proven int)", _int_division),
        ]

    def findings(self, original, upgraded):
        if self.detector.detect(original) != "Python 2.x":
            return []
        remaining = _true_divisions(upgraded)
        if remaining:
            return [f"{remaining} '/' kept as true division: Python 2 floored it when both operands were ints"]
        return []
