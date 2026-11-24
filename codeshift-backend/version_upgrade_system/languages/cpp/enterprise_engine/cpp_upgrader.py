"""C++98/03 -> C++20 upgrader.

Every rewrite is validated with `g++ -std=c++20` (and the user's test cases, if given).
Rewrites whose safety depends on how a variable is used check those uses first:
an index loop only becomes a range-for when the index is used solely to subscript the
container, and a raw `new` only becomes `make_unique` when ownership is local.
"""

import re

from version_upgrade_system.core.gated import GatedUpgrader, Rule
from version_upgrade_system.core.textscan import add_include, mask, matching, splice
from version_upgrade_system.languages.cpp.enterprise_engine.version_detector import CppVersionDetector

LANG = "cpp"
CONTAINERS = r"(?:std::)?(?:vector|map|set|list|deque|multimap|multiset|unordered_map|unordered_set|basic_string|string)"
MUTATORS = r"push_back|emplace_back|pop_back|insert|emplace|erase|clear|resize|assign|swap|reserve"
CAST_CONTEXT_KEYWORDS = {"return", "case", "throw", "else", "do", "co_return", "co_yield"}


def _replace(pattern, replacement):
    def apply(code):
        masked = mask(code, LANG)
        edits = [(m.start(), m.end(), m.expand(replacement)) for m in re.finditer(pattern, masked)]
        return splice(code, edits)
    return apply


def _operand_end(masked, start):
    """End of the postfix expression starting at `start` (identifiers, calls, members, subscripts)."""
    index = start
    match = re.match(r"\s*(::)?[A-Za-z_]\w*(::\w+)*|\s*\d[\w.]*", masked[index:])
    if not match:
        if index < len(masked) and masked[index] == "(":
            close = matching(masked, index)
            return close + 1 if close != -1 else -1
        return -1
    index += match.end()
    while index < len(masked):
        rest = masked[index:]
        member = re.match(r"\s*(\.|->)\s*[A-Za-z_]\w*", rest)
        if member:
            index += member.end()
            continue
        opener = re.match(r"\s*([(\[])", rest)
        if opener:
            open_index = index + opener.end() - 1
            close = matching(masked, open_index)
            if close == -1:
                return -1
            index = close + 1
            continue
        break
    return index


def _casts(code):
    masked = mask(code, LANG)
    edits = []
    pattern = r"\((?P<type>(?:unsigned\s+|signed\s+)?(?:int|double|float|long(?:\s+long)?|short|char|bool|size_t))\)\s*"
    for match in re.finditer(pattern, masked):
        before = masked[:match.start()].rstrip()
        previous = re.search(r"(\w+)$", before)
        if previous and previous.group(1) not in CAST_CONTEXT_KEYWORDS:
            continue  # a function call or declaration, not a cast
        end = _operand_end(masked, match.end())
        if end == -1 or end <= match.end():
            continue
        operand = code[match.end():end].strip()
        edits.append((match.start(), end, f"static_cast<{match.group('type')}>({operand})"))
    return splice(code, edits)


def _typedefs(code):
    return _replace(r"\btypedef\s+((?:const\s+)?[\w:]+(?:\s*<[^;(){}]*>)?(?:\s*[\*&]+)?(?:\s+[\w:]+)*?)\s+(\w+)\s*;",
                    r"using \2 = \1;")(code)


def _iterators(code):
    return _replace(rf"\b{CONTAINERS}\s*<[^;(){{}}]*>\s*::\s*(?:const_)?iterator\s+(\w+)\s*=", r"auto \1 =")(code)


def _range_for(code):
    """for (size_t i = 0; i < v.size(); i++) { ...v[i]... }  ->  for (auto& item : v) { ...item... }"""
    masked = mask(code, LANG)
    header = re.compile(
        r"\bfor\s*\(\s*(?:std::)?(?:size_t|unsigned(?:\s+int)?|int|long)\s+(\w+)\s*=\s*0\s*;"
        r"\s*\1\s*<\s*(\w+)\s*\.\s*size\s*\(\s*\)\s*;\s*(?:\+\+\s*\1|\1\s*\+\+|\1\s*\+=\s*1)\s*\)")
    for match in header.finditer(masked):
        index, container = match.group(1), match.group(2)
        cursor = match.end()
        while cursor < len(masked) and masked[cursor].isspace():
            cursor += 1
        if cursor < len(masked) and masked[cursor] == "{":
            body_end = matching(masked, cursor) + 1
            if body_end == 0:
                continue
        else:
            body_end = masked.find(";", cursor) + 1
            if body_end == 0:
                continue
        body = masked[cursor:body_end]
        subscript = rf"\b{container}\s*\[\s*{index}\s*\]"
        if re.search(rf"\b{index}\b", re.sub(subscript, "", body)):
            continue  # the index is used for something other than subscripting
        if re.search(rf"\b{container}\s*\.\s*({MUTATORS})\b", body):
            continue  # modifying the container invalidates range-for iterators
        name = "element"
        while re.search(rf"\b{name}\b", body):
            name += "_"
        new_body = re.sub(subscript, name, code[cursor:body_end])
        return code[:match.start()] + f"for (auto& {name} : {container})" + code[match.end():cursor] + \
            new_body + code[body_end:]
    return code


def _unique_ptrs(code):
    """T* p = new T(args); ... delete p;  ->  auto p = std::make_unique<T>(args); when ownership is local."""
    masked = mask(code, LANG)
    pattern = re.compile(r"\b([A-Za-z_][\w:]*)\s*\*\s*(\w+)\s*=\s*new\s+\1\s*(\(([^;]*)\))?\s*;")
    for match in pattern.finditer(masked):
        name = match.group(2)
        deletes = list(re.finditer(rf"\bdelete\s+{name}\s*;", masked))
        if len(deletes) != 1:
            continue
        others = [m for m in re.finditer(rf"\b{name}\b", masked)
                  if not (match.start() <= m.start() < match.end())
                  and not (deletes[0].start() <= m.start() < deletes[0].end())]
        if not all(re.match(r"\s*->", masked[m.end():]) or masked[:m.start()].rstrip().endswith("*")
                   and not masked[:m.start()].rstrip().endswith("**") for m in others):
            continue  # passed, copied or reassigned: ownership is not local
        arguments = code[match.start(4):match.end(4)] if match.group(4) is not None else ""
        replacement = f"auto {name} = std::make_unique<{code[match.start(1):match.end(1)]}>({arguments});"
        # reset() keeps the destructor at the point where delete ran.
        upgraded = splice(code, [(match.start(), match.end(), replacement),
                                 (deletes[0].start(), deletes[0].end(), f"{name}.reset();")])
        return add_include(upgraded, "memory")
    return code


PRE_STANDARD_HEADERS = ("iostream", "fstream", "iomanip", "strstream")


def _standard_headers(code):
    """<iostream.h> (pre-1998) -> <iostream> plus using namespace std."""
    pattern = rf"#\s*include\s*<({'|'.join(PRE_STANDARD_HEADERS)})\.h>"
    if not re.search(pattern, code):
        return code
    code = re.sub(pattern, r"#include <\1>", code)
    if re.search(r"\busing\s+namespace\s+std\s*;", mask(code, LANG)):
        return code
    includes = list(re.finditer(r"^\s*#\s*include[^\n]*\n", code, re.MULTILINE))
    position = includes[-1].end() if includes else 0
    return code[:position] + "using namespace std;\n" + code[position:]


def _binders(code):
    """bind1st/bind2nd (removed in C++17) -> std::bind with a placeholder."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"(?<![\w:])(?:std::)?bind(1st|2nd)\s*\(", masked):
        close = matching(masked, match.end() - 1)
        if close == -1:
            continue
        depth, split = 0, -1
        for k in range(match.end(), close):
            depth += masked[k] in "(<[{"
            depth -= masked[k] in ")>]}"
            if masked[k] == "," and depth == 0:
                split = k
                break
        if split == -1:
            continue
        function, value = code[match.end():split].strip(), code[split + 1:close].strip()
        placeholder = "std::placeholders::_1"
        arguments = f"{value}, {placeholder}" if match.group(1) == "1st" else f"{placeholder}, {value}"
        edits.append((match.start(), close + 1, f"std::bind({function}, {arguments})"))
    return add_include(splice(code, edits), "functional") if edits else code


def _random_shuffle(code):
    """random_shuffle(first, last) (removed in C++17) -> shuffle with a seeded engine."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"(?<![\w:])(?:std::)?random_shuffle\s*\(", masked):
        close = matching(masked, match.end() - 1)
        if close == -1 or masked[match.end():close].count(",") != 1:
            continue  # a third argument is a custom generator
        edits.append((match.start(), close + 1,
                      f"std::shuffle({code[match.end():close].strip()}, std::mt19937{{std::random_device{{}}()}})"))
    return add_include(add_include(splice(code, edits), "random"), "algorithm") if edits else code


def _base_function_classes(code):
    """struct F : std::unary_function<A, R> (removed in C++17): the base only supplied typedefs."""
    return _replace(r"\s*:\s*(?:public\s+)?(?:std::)?(?:unary|binary)_function\s*<[^<>{;]*>(?=\s*\{)", "")(code)


def _dynamic_specs(code):
    """void f() throw(std::bad_alloc)  ->  void f()  (dynamic specifications are an error in C++17)."""
    masked = mask(code, LANG)
    edits = []
    for match in re.finditer(r"\)\s*throw\s*\(\s*[\w:<>, ]*\w[\w:<>, ]*\)(?=\s*(?:[{;=]|const\b|override\b))", masked):
        depth, open_index = 0, -1
        for k in range(match.start(), -1, -1):
            if masked[k] == ")":
                depth += 1
            elif masked[k] == "(":
                depth -= 1
                if depth == 0:
                    open_index = k
                    break
        before = re.search(r"([A-Za-z_]\w*)\s*$", masked[:open_index]) if open_index > 0 else None
        if not before or before.group(1) in ("if", "while", "for", "switch", "return", "catch", "sizeof"):
            continue  # `if (x) throw (e);` is a throw statement, not a specification
        edits.append((match.start() + 1, match.end(), ""))
    return splice(code, edits)


class CppEnterpriseUpgrader(GatedUpgrader):

    language = LANG
    engine = "C++98 to C++20 engine (g++-gated)"
    detector = CppVersionDetector()

    def rules(self, code):
        masked = mask(code, LANG)
        rules = [
            # Rewrites that make legacy code compile again come first, so later rules are
            # validated against a program that compiles.
            Rule("<iostream.h> -> <iostream> (pre-standard headers)", _standard_headers),
            Rule("void main -> int main", _replace(r"\bvoid\s+main\s*\(", "int main(")),
            Rule("dynamic exception specification throw(X) removed", _dynamic_specs),
            Rule("NULL -> nullptr", _replace(r"\bNULL\b", "nullptr")),
            Rule("std::auto_ptr -> std::unique_ptr", _replace(r"\b(std::)?auto_ptr\b", r"std::unique_ptr")),
            Rule("register storage class removed", _replace(r"\bregister\s+(?=\w)", "")),
            Rule("typedef -> using", _typedefs),
            Rule("C-style cast -> static_cast", _casts),
            Rule("container iterator declaration -> auto", _iterators),
            Rule("insert(make_pair(k, v)) -> emplace(k, v)",
                 _replace(r"\.insert\s*\(\s*(?:std::)?make_pair\s*\(([^()]*?),([^()]*?)\)\s*\)", r".emplace(\1,\2)")),
            Rule("throw() -> noexcept", _replace(r"\bthrow\s*\(\s*\)", "noexcept")),
            # not_fn accepts any callable, so the adaptors go before the binders they wrap.
            Rule("ptr_fun(f) -> f", _replace(r"(?<![\w:])(?:std::)?ptr_fun\s*\(\s*([\w:]+)\s*\)", r"\1")),
            Rule("not1/not2 -> std::not_fn", _replace(r"(?<![\w:])(?:std::)?not[12]\s*\(", "std::not_fn(")),
            Rule("mem_fun/mem_fun_ref -> std::mem_fn", _replace(r"(?<![\w:])(?:std::)?mem_fun(?:_ref)?\s*\(", "std::mem_fn(")),
            Rule("bind1st/bind2nd -> std::bind", _binders),
            Rule("unary_function/binary_function base removed", _base_function_classes),
            Rule("random_shuffle -> std::shuffle", _random_shuffle,
                 caution="random_shuffle -> shuffle: a different random sequence"),
        ]
        loops = len(re.findall(r"\bfor\s*\(\s*(?:std::)?(?:size_t|unsigned(?:\s+int)?|int|long)\s+\w+\s*=\s*0\s*;", masked))
        for index in range(loops):
            rules.append(Rule(f"index loop #{index + 1} -> range-based for", _range_for))
        news = len(re.findall(r"=\s*new\s+\w", masked))
        for index in range(news):
            rules.append(Rule(f"owning raw pointer #{index + 1} -> std::make_unique", _unique_ptrs))
        return rules

    def findings(self, original, upgraded):
        masked = mask(upgraded, LANG)
        notes = []
        if re.search(r"\b[\w:]+\s*\*\s*\w+\s*=\s*new\b", masked):
            notes.append("raw owning pointer kept: it is passed on or reassigned")
        if re.search(r"\(\s*(?:int|double|float|long|char)\s*\)", masked):
            notes.append("C-style cast kept where the operand could not be delimited")
        return notes
