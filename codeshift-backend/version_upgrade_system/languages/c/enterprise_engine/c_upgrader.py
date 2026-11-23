"""C89/K&R -> C17 upgrader.

Each rule is validated with `gcc -std=c17` (and the user's test cases, if given). The
bounded-copy rules only fire when the destination is an array declared in the same
function, because `sizeof` on a pointer gives the pointer's size, not the buffer's.
"""

import re

from version_upgrade_system.core.gated import GatedUpgrader, Rule
from version_upgrade_system.core.textscan import add_include, mask, matching, splice
from version_upgrade_system.languages.c.enterprise_engine.version_detector import CVersionDetector

LANG = "c"
TYPE = r"(?:(?:unsigned|signed|short|long|const|static|struct\s+\w+|enum\s+\w+|\w+)\s+)*?(?:\w+)(?:\s*\*+)?"
DEFINITION = re.compile(
    rf"^(?P<type>(?:{TYPE})[ \t\*]+)?(?P<name>[A-Za-z_]\w*)[ \t]*\((?P<params>[^;{{}}()]*)\)[ \t]*\n?[ \t]*\{{",
    re.MULTILINE)
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "do", "else"}


def _functions(masked):
    """Top-level function definitions: name -> (match, brace index)."""
    found = {}
    for match in DEFINITION.finditer(masked):
        name = match.group("name")
        if name in KEYWORDS or _depth(masked, match.start()) != 0:
            continue
        found[name] = match
    return found


def _depth(masked, position):
    return masked.count("{", 0, position) - masked.count("}", 0, position)


def _function_span(masked, position):
    """(start, end) of the top-level function body that contains `position`."""
    depth, start = 0, None
    for index, ch in enumerate(masked):
        if ch == "{":
            if depth == 0:
                start = index
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None and start <= position <= index:
                return start, index
    return 0, len(masked)


def _is_array(masked, name, position):
    start, end = _function_span(masked, position)
    scope = masked[start:end] + masked[:start]  # locals first, then file scope
    return re.search(rf"\b(char|unsigned\s+char)\s+(?:\w+\s*\[[^\]]*\]\s*,\s*)*{re.escape(name)}\s*\[\s*\w+\s*\]",
                     scope) is not None


def _array_destinations(function, replacement):
    """Rewrite `function(dest, ...)` when `dest` is a char array of known size."""
    def apply(code):
        masked = mask(code, LANG)
        edits = []
        for match in re.finditer(rf"\b{function}\s*\(\s*(\w+)\s*,", masked):
            if not _is_array(masked, match.group(1), match.start()):
                continue
            open_paren = match.start() + match.group(0).index("(")
            close = matching(masked, open_paren)
            if close == -1:
                continue
            # Split on the masked text so commas inside string literals are ignored.
            spans, depth, start = [], 0, open_paren + 1
            for index in range(open_paren + 1, close):
                ch = masked[index]
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    spans.append((start, index))
                    start = index + 1
            spans.append((start, close))
            arguments = [code[s:e].strip() for s, e in spans]
            edits.append((match.start(), close + 1, replacement(arguments[0], arguments[1:])))
        return splice(code, edits)
    return apply


def _gets(code):
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"\bgets\s*\(\s*(\w+)\s*\)\s*;", masked):
        buffer = match.group(1)
        if not _is_array(masked, buffer, match.start()):
            continue
        # fgets keeps the newline that gets discarded; strip it to preserve behaviour.
        edits.append((match.start(), match.end(),
                      f"if (fgets({buffer}, sizeof {buffer}, stdin)) "
                      f"{buffer}[strcspn({buffer}, \"\\n\")] = '\\0';"))
    upgraded = splice(code, edits)
    return add_include(upgraded, "string.h") if edits else upgraded


def _implicit_int(code):
    masked = mask(code, LANG)
    edits = []
    for name, match in _functions(masked).items():
        if not match.group("type") or not match.group("type").strip():
            edits.append((match.start("name"), match.start("name"), "int "))
    return splice(code, edits)


def _void_main(code):
    masked = mask(code, LANG)
    edits = [(m.start(), m.end(), "int main(") for m in re.finditer(r"\bvoid\s+main\s*\(", masked)]
    return splice(code, edits)


def _empty_params(code):
    masked = mask(code, LANG)
    edits = []
    for name, match in _functions(masked).items():
        if match.group("params").strip() == "":
            open_paren = masked.index("(", match.start("name"))
            edits.append((open_paren + 1, open_paren + 1, "void"))
    return splice(code, edits)


def _knr_definitions(code):
    """int f(a, b) int a; char *b; {  ->  int f(int a, char *b) {"""
    masked = mask(code, LANG)
    pattern = re.compile(
        r"^(?P<head>[ \t]*(?:[\w\*]+[ \t\*]+)*?(?P<name>\w+)[ \t]*)\((?P<names>[\w\s,]+)\)[ \t]*\n"
        r"(?P<decls>(?:[ \t]*[\w][\w \t\*,\[\]]*;[ \t]*\n)+)(?P<brace>[ \t]*\{)", re.MULTILINE)
    edits = []
    for match in pattern.finditer(masked):
        names = [n.strip() for n in match.group("names").split(",") if n.strip()]
        types = {}
        for declaration in match.group("decls").split(";"):
            declarators = [d.strip() for d in declaration.split(",") if d.strip()]
            if not declarators:
                continue
            first = re.match(r"^(?P<base>.*\b\w+)\s+(?P<decl>[\*\s]*\w+(?:\s*\[[^\]]*\])*)$", declarators[0])
            if not first:
                break
            base = first.group("base")
            for declarator in [first.group("decl")] + declarators[1:]:
                bare = re.search(r"\w+", declarator).group(0)
                types[bare] = f"{base} {declarator}"
        if set(types) != set(names):
            continue
        parameters = ", ".join(types[n] for n in names)
        edits.append((match.start(), match.start("brace"),
                      f"{code[match.start('head'):match.end('head')]}({parameters})\n"))
    return splice(code, edits)


def _prototypes(code):
    """Declare functions used before their definition (implicit declarations are errors in C99+)."""
    masked = mask(code, LANG)
    functions = _functions(masked)
    declared = set()
    for match in re.finditer(r"^[ \t]*[\w \t\*]+?\b(\w+)[ \t]*\([^;{]*\)[ \t]*;", masked, re.MULTILINE):
        if _depth(masked, match.start()) == 0:
            declared.add(match.group(1))

    replacements, inserts = [], []
    for name, match in functions.items():
        if name == "main":
            continue
        first_use = re.search(rf"\b{name}\s*\(", masked)
        if not first_use or first_use.start() >= match.start("name"):
            continue
        prototype_type = (match.group("type") or "int ").strip()
        parameters = code[match.start("params"):match.end("params")].strip() or "void"
        prototype = f"{prototype_type} {name}({parameters});"
        old = re.search(rf"^[ \t]*[\w \t\*]+?\b{name}[ \t]*\([ \t]*\)[ \t]*;[ \t]*$", masked, re.MULTILINE)
        if old and _depth(masked, old.start()) == 0:
            replacements.append((old.start(), old.end(), prototype))
        elif name not in declared:
            inserts.append(prototype)

    code = splice(code, replacements)
    if inserts:
        directives = list(re.finditer(r"^[ \t]*#[^\n]*\n", code, re.MULTILINE))
        position = directives[-1].end() if directives else 0
        code = code[:position] + "\n" + "\n".join(inserts) + "\n" + code[position:]
    return code


def _calloc(code):
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"\bmalloc\s*\(\s*(?:(\w+)\s*\*\s*)?sizeof\s*\(?([^()]+?)\)?\s*(?:\*\s*(\w+)\s*)?\)", masked):
        count = match.group(1) or match.group(3) or "1"
        edits.append((match.start(), match.end(), f"calloc({count}, sizeof({match.group(2).strip()}))"))
    return splice(code, edits)


class CEnterpriseUpgrader(GatedUpgrader):

    language = LANG
    engine = "C89 to C17 engine (gcc-gated)"
    detector = CVersionDetector()

    def rules(self, code):
        return [
            Rule("K&R definition -> ANSI prototype", _knr_definitions),
            Rule("implicit int -> explicit int", _implicit_int),
            Rule("void main -> int main", _void_main),
            Rule("prototype for functions used before definition", _prototypes),
            Rule("f() definition -> f(void)", _empty_params),
            Rule("gets -> fgets with newline stripped (array buffers)", _gets),
            Rule("strcpy -> snprintf bounded copy (array destinations)", _array_destinations(
                "strcpy", lambda dest, rest: f"snprintf({dest}, sizeof {dest}, \"%s\", {rest[0]})"),
                 caution="strcpy -> snprintf now truncates input that would have overflowed"),
            Rule("strcat -> strncat bounded append (array destinations)", _array_destinations(
                "strcat", lambda dest, rest: f"strncat({dest}, {rest[0]}, sizeof {dest} - strlen({dest}) - 1)")),
            Rule("sprintf -> snprintf (array destinations)", _array_destinations(
                "sprintf", lambda dest, rest: f"snprintf({dest}, sizeof {dest}, {', '.join(rest)})")),
            Rule("malloc(sizeof) -> calloc (zero-initialised)", _calloc),
        ]

    def findings(self, original, upgraded):
        masked = mask(upgraded, LANG)
        notes = []
        for name in ("gets", "strcpy", "strcat", "sprintf"):
            if re.search(rf"\b{name}\s*\(", masked):
                notes.append(f"{name} kept: destination is not an array of known size")
        allocations = len(re.findall(r"\b(malloc|calloc|realloc)\s*\(", masked))
        frees = len(re.findall(r"\bfree\s*\(", masked))
        if allocations > frees:
            notes.append(f"{allocations - frees} allocation(s) without a matching free()")
        return notes
