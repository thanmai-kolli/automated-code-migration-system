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
            _regex_rule("unicode() -> str()", r"\bunicode\(", "str("),
            _regex_rule("long() -> int()", r"\blong\(", "int("),
            _regex_rule("octal 0NNN -> 0oNNN", r"(?<![\w.])0([0-7]+)\b", r"0o\1"),
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
