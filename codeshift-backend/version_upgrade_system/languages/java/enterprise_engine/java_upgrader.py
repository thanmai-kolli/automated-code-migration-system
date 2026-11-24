"""Legacy Java -> Java 17 upgrader.

Every rewrite is validated by javac (and by the user's test cases, if given) before it
is kept. Rules that would change behaviour in common cases are deliberately absent:
Hashtable -> HashMap and Stack -> ArrayDeque both change iteration order.
"""

import re

from version_upgrade_system.core.gated import GatedUpgrader, Rule
from version_upgrade_system.core.textscan import mask, matching, splice
from version_upgrade_system.languages.java.enterprise_engine.version_detector import JavaVersionDetector

LANG = "java"
BOXES = "Integer|Long|Short|Byte|Double|Float|Boolean|Character"
CONCURRENCY = r"\b(Thread|Runnable|synchronized|Executor\w*|Callable|volatile|Concurrent\w*)\b"
FUNCTIONAL = {"Runnable": "run", "Comparator": "compare", "Callable": "call"}

# Vector-only methods and their List equivalents; a callable gets (receiver, args).
VECTOR_METHODS = {
    "addElement": lambda v, a: f"{v}.add({a})",
    "elementAt": lambda v, a: f"{v}.get({a})",
    "firstElement": lambda v, a: f"{v}.get(0)",
    "lastElement": lambda v, a: f"{v}.get({v}.size() - 1)",
    "removeElementAt": lambda v, a: f"{v}.remove((int) ({a}))",
    "removeAllElements": lambda v, a: f"{v}.clear()",
    "elements": lambda v, a: f"Collections.enumeration({v})",
}
VECTOR_TWO_ARG = {
    "setElementAt": lambda v, x, i: f"{v}.set({i}, {x})",
    "insertElementAt": lambda v, x, i: f"{v}.add({i}, {x})",
}
LIST_METHODS = {"add", "get", "size", "isEmpty", "contains", "indexOf", "remove", "clear",
                "set", "iterator", "addAll", "toArray", "subList", "equals", "hashCode",
                "toString", "listIterator", "lastIndexOf", "containsAll", "removeAll",
                "retainAll", "forEach", "stream", "sort"}


def _boxing(code):
    masked = mask(code, LANG)
    edits = [(m.start(), m.end(), f"{m.group(1)}.valueOf(")
             for m in re.finditer(rf"\bnew\s+({BOXES})\s*\(", masked)]
    return splice(code, edits)


def _string_buffer(code):
    if re.search(CONCURRENCY, mask(code, LANG)):
        return code
    masked = mask(code, LANG)
    edits = [(m.start(), m.end(), "StringBuilder") for m in re.finditer(r"\bStringBuffer\b", masked)]
    return splice(code, edits)


def _split_arguments(text):
    parts, depth, start = [], 0, 0
    for index, ch in enumerate(text):
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _anonymous_to_lambda(code, occurrence):
    """Rewrite the n-th anonymous single-method functional class as a lambda."""
    masked = mask(code, LANG)
    pattern = rf"\bnew\s+({'|'.join(FUNCTIONAL)})\s*(<[^>(){{}}]*>)?\s*\(\s*\)\s*\{{"
    matches = list(re.finditer(pattern, masked))
    if occurrence >= len(matches):
        return code
    match = matches[occurrence]
    body_open = match.end() - 1
    body_close = matching(masked, body_open)
    if body_close == -1:
        return code
    inner = masked[body_open + 1:body_close]
    method = FUNCTIONAL[match.group(1)]
    header = re.match(rf"\s*(@Override\s*)?public\s+[\w<>\[\],\s]+?\s+{method}\s*\(([^)]*)\)\s*"
                      r"(throws\s+[\w.,\s]+)?\{", inner)
    if not header:
        return code
    method_open = body_open + 1 + header.end() - 1
    method_close = matching(masked, method_open)
    if method_close == -1 or masked[method_close + 1:body_close].strip():
        return code  # other members besides the single method
    body_masked = masked[method_open:method_close + 1]
    if re.search(r"\bthis\b|\bsuper\b", body_masked):
        return code  # `this` means the anonymous instance; a lambda would change it
    parameters = code[body_open + 1 + header.start(2):body_open + 1 + header.end(2)].strip()
    body = code[method_open:method_close + 1]
    return code[:match.start()] + f"({parameters}) -> {body}" + code[body_close + 1:]


def _enclosing_brace(masked, position):
    depth = 0
    for index in range(position - 1, -1, -1):
        if masked[index] == "}":
            depth += 1
        elif masked[index] == "{":
            if depth == 0:
                return index
            depth -= 1
    return -1


def _is_local(masked, position):
    """True when the declaration sits in a method or block, not in a class body."""
    brace = _enclosing_brace(masked, position)
    if brace == -1:
        return False
    start = max(masked.rfind(";", 0, brace), masked.rfind("}", 0, brace), masked.rfind("{", 0, brace))
    return not re.search(r"\b(class|interface|enum|record)\b", masked[start + 1:brace])


def _ensure_imports(code, names):
    masked = mask(code, LANG)
    if re.search(r"^\s*import\s+java\.util\.\*\s*;", masked, re.MULTILINE):
        return code
    missing = [n for n in names
               if not re.search(rf"^\s*import\s+java\.util\.{n}\s*;", masked, re.MULTILINE)]
    if not missing:
        return code
    anchors = list(re.finditer(r"^\s*(import|package)\s[^;]*;[ \t]*\n", masked, re.MULTILINE))
    position = anchors[-1].end() if anchors else 0
    lines = "".join(f"import java.util.{n};\n" for n in missing)
    return code[:position] + lines + code[position:]


def _vector_locals(code):
    masked = mask(code, LANG)
    return [m.group(2) for m in re.finditer(
        r"(?<![.\w])Vector\s*(<[^>;=]*>)?\s+(\w+)\s*=\s*new\s+Vector\b", masked)
        if _is_local(masked, m.start())]


def _vector_to_list(code, name):
    masked = mask(code, LANG)
    if re.search(CONCURRENCY, masked):
        return code  # Vector's synchronization may be relied on
    declaration = re.search(
        rf"(?<![.\w])Vector(\s*<[^>;=]*>)?(\s+{name}\s*=\s*new\s+)Vector\b", masked)
    if not declaration:
        return code

    edits = []
    needs_collections = False
    for use in re.finditer(rf"(?<![.\w]){name}\b", masked):
        if declaration.start() <= use.start() < declaration.end():
            continue
        call = re.match(r"\s*\.\s*(\w+)\s*\(", masked[use.end():])
        if not call:
            continue  # passed on or returned: javac rejects the rule if a Vector is required
        method = call.group(1)
        open_paren = use.end() + call.end() - 1
        close_paren = matching(masked, open_paren)
        if close_paren == -1:
            return code
        arguments = code[open_paren + 1:close_paren]
        if method in VECTOR_METHODS:
            needs_collections |= method == "elements"
            edits.append((use.start(), close_paren + 1, VECTOR_METHODS[method](name, arguments.strip())))
        elif method in VECTOR_TWO_ARG:
            parts = _split_arguments(arguments)
            if len(parts) != 2:
                return code
            edits.append((use.start(), close_paren + 1, VECTOR_TWO_ARG[method](name, *parts)))
        elif method not in LIST_METHODS:
            return code  # an API ArrayList does not provide (copyInto, capacity, ...)

    generic = declaration.group(1) or ""
    edits.append((declaration.start(), declaration.end(),
                  f"List{generic}{code[declaration.start(2):declaration.end(2)]}ArrayList"))
    upgraded = splice(code, edits)
    return _ensure_imports(upgraded, ["List", "ArrayList"] + (["Collections"] if needs_collections else []))


def _diamond(code):
    """List<String> xs = new ArrayList<String>();  ->  new ArrayList<>()  (Java 7)."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"\b[\w.]+\s*<[^;=(){}]*>\s+\w+\s*=\s*new\s+[\w.]+\s*(<[^;=(){}]+>)\s*\(", masked):
        if match.group(1).replace(" ", "") != "<>":
            edits.append((match.start(1), match.end(1), "<>"))
    return splice(code, edits)


def _try_with_resources(code):
    """X r = new X(..); try { .. } finally { r.close(); }  ->  try (X r = new X(..)) { .. }  (Java 7).

    Only without catch clauses: there a catch would run before the resource is closed.
    """
    masked = mask(code, LANG)
    pattern = (r"(?m)^([ \t]*)((?:final\s+)?[\w.<>\[\], ]+?\s+(\w+)\s*=\s*new\s+[\w.<>]+\s*\()")
    for declaration in re.finditer(pattern, masked):
        name = declaration.group(3)
        open_paren = declaration.end() - 1
        close_paren = matching(masked, open_paren)
        if close_paren == -1:
            continue
        semicolon = re.match(r"\s*;", masked[close_paren + 1:])
        if not semicolon:
            continue
        after = close_paren + 1 + semicolon.end()
        try_match = re.match(r"\s*try\s*\{", masked[after:])
        if not try_match:
            continue
        body_open = after + try_match.end() - 1
        body_close = matching(masked, body_open)
        if body_close == -1:
            continue
        finally_match = re.match(r"\s*finally\s*\{", masked[body_close + 1:])
        if not finally_match:
            continue
        finally_open = body_close + 1 + finally_match.end() - 1
        finally_close = matching(masked, finally_open)
        if finally_close == -1:
            continue
        cleanup = masked[finally_open + 1:finally_close].strip()
        close_call = rf"{name}\s*\.\s*close\s*\(\s*\)\s*;"
        if not re.fullmatch(rf"(if\s*\(\s*{name}\s*!=\s*null\s*\)\s*)?(\{{\s*)?{close_call}(\s*\}})?", cleanup):
            continue
        resource = code[declaration.start(2):close_paren + 1].strip()
        indent = declaration.group(1)
        body = code[body_open:body_close + 1]
        return code[:declaration.start()] + f"{indent}try ({resource}) {body}" + code[finally_close + 1:]
    return code


def _iterator_loops(code):
    """Iterator it = xs.iterator(); while (it.hasNext()) { T x = (T) it.next(); .. }  ->  for-each (Java 5)."""
    masked = mask(code, LANG)
    pattern = (r"(?m)^([ \t]*)Iterator\s*(<[^;=]*>)?\s+(\w+)\s*=\s*(\w+(?:\.\w+)*)\s*\.\s*iterator\s*\(\s*\)\s*;"
               r"\s*while\s*\(\s*\3\s*\.\s*hasNext\s*\(\s*\)\s*\)\s*\{")
    for match in re.finditer(pattern, masked):
        iterator, collection = match.group(3), match.group(4)
        body_open = match.end() - 1
        body_close = matching(masked, body_open)
        if body_close == -1:
            continue
        first = re.match(rf"\s*([\w.<>\[\]]+)\s+(\w+)\s*=\s*(\(\s*([\w.<>\[\]]+)\s*\)\s*)?{iterator}\s*\.\s*next\s*\(\s*\)\s*;",
                         masked[body_open + 1:])
        if not first:
            continue
        rest = masked[body_open + 1 + first.end():]
        if re.search(rf"(?<![\w.]){iterator}\b", rest):
            continue  # it.remove() or later uses need the explicit iterator
        element_type, variable = first.group(1), first.group(2)
        statement_end = body_open + 1 + first.end()
        declared = re.search(rf"\b[\w.]+\s*<\s*([\w.]+)\s*>\s+{re.escape(collection)}\s*[=;,)]", masked)
        if first.group(3) and not (declared and declared.group(1) == first.group(4) == element_type):
            # A raw collection yields Objects: keep the cast the original applied.
            header = f"for (Object _element : {collection}) {{\n{match.group(1)}    {element_type} {variable} = ({first.group(4)}) _element;"
        else:
            header = f"for ({element_type} {variable} : {collection}) {{"
        return code[:match.start()] + match.group(1) + header + code[statement_end:]
    return code


def _instanceof_patterns(code):
    """if (o instanceof T) { T t = (T) o; ..  ->  if (o instanceof T t) { ..  (Java 16)."""
    masked = mask(code, LANG)
    edits = []
    pattern = (r"\(\s*(\w+)\s+instanceof\s+([\w.]+)\s*\)\s*\{(\s*)(?:final\s+)?\2\s+(\w+)\s*=\s*"
               r"\(\s*\2\s*\)\s*\1\s*;[ \t]*\n?")
    for match in re.finditer(pattern, masked):
        separator = "\n" if "\n" in match.group(3) else " "
        edits.append((match.start(), match.end(),
                      f"({match.group(1)} instanceof {match.group(2)} {match.group(4)}) {{{separator}"))
    return splice(code, edits)


def _until_stable(rewrite):
    """Apply a one-occurrence rewrite until nothing changes."""
    def apply(code):
        for _ in range(50):
            rewritten = rewrite(code)
            if rewritten == code:
                break
            code = rewritten
        return code
    return apply


class JavaEnterpriseUpgrader(GatedUpgrader):

    language = LANG
    engine = "Java legacy to Java 17 engine (javac-gated)"
    detector = JavaVersionDetector()

    def rules(self, code):
        masked = mask(code, LANG)
        rules = [Rule("new Integer(x) etc. -> Integer.valueOf(x) (deprecated for removal)", _boxing),
                 Rule("StringBuffer -> StringBuilder (no concurrency in file)", _string_buffer),
                 Rule("generic instantiation -> diamond <>", _diamond),
                 Rule("close() in finally -> try-with-resources", _until_stable(_try_with_resources)),
                 Rule("Iterator while-loop -> enhanced for", _until_stable(_iterator_loops)),
                 Rule("instanceof and cast -> pattern matching", _instanceof_patterns)]
        lambdas = len(re.findall(rf"\bnew\s+({'|'.join(FUNCTIONAL)})\s*(<[^>(){{}}]*>)?\s*\(\s*\)\s*\{{", masked))
        # Rewrite from the last occurrence back so earlier indices stay valid.
        for index in reversed(range(lambdas)):
            rules.append(Rule(f"anonymous class #{index + 1} -> lambda",
                              lambda c, i=index: _anonymous_to_lambda(c, i)))
        for name in _vector_locals(code):
            rules.append(Rule(f"local Vector '{name}' -> List/ArrayList",
                              lambda c, n=name: _vector_to_list(c, n),
                              caution=f"'{name}' is no longer synchronized (was Vector)"))
        return rules

    def findings(self, original, upgraded):
        masked = mask(upgraded, LANG)
        notes = []
        if re.search(r"\b(Hashtable|Stack)\b", masked):
            notes.append("Hashtable/Stack kept: replacements change iteration order")
        if re.search(r"\b(List|ArrayList|Map|HashMap|Vector|Hashtable|Iterator|Enumeration)\s+\w+\s*=", masked):
            notes.append("Raw collection types remain: add generics after review")
        return notes
