"""Identifiers that the target language reserves are renamed before generation.

A C variable called `pass` or a Python variable called `new` is legal in its
own language but a syntax error in another, and a user function called `gcd`
or `round` would clash with the library function the target already has.
"""

import keyword

from cross_language_system.core.ir_nodes import (AttributeAccess, Class, Field, ForLoop, Function, FunctionCall,
                                                 Identifier, TryCatch, Variable)

_C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern",
    "float", "for", "goto", "if", "inline", "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while",
    "bool", "true", "false", "NULL",
}
_C_LIBRARY = {
    "printf", "scanf", "puts", "putchar", "getchar", "fgets", "malloc", "calloc", "realloc", "free", "exit",
    "strlen", "strcmp", "strcpy", "strncpy", "strcat", "strchr", "strstr", "memcpy", "memset", "sprintf",
    "snprintf", "sqrt", "pow", "floor", "ceil", "fabs", "abs", "labs", "llabs", "round", "nearbyint", "log",
    "log10", "exp", "sin", "cos", "tan", "hypot", "fmod", "isupper", "islower", "isdigit", "isalpha", "isspace",
    "isalnum", "toupper", "tolower", "atoi", "atof", "strtod", "strtol", "stdin", "stdout", "stderr",
}
_CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "catch", "char8_t", "char16_t",
    "char32_t", "class", "compl", "concept", "const_cast", "consteval", "constexpr", "constinit", "co_await",
    "co_return", "co_yield", "decltype", "delete", "dynamic_cast", "explicit", "export", "friend", "mutable",
    "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private",
    "protected", "public", "reinterpret_cast", "requires", "static_assert", "static_cast", "template", "this",
    "thread_local", "throw", "try", "typeid", "typename", "using", "virtual", "wchar_t", "xor", "xor_eq",
}
# Functions of namespace std that a user function of the same name makes ambiguous
# under "using namespace std".
_STD_FUNCTIONS = {
    "max", "min", "swap", "count", "find", "sort", "reverse", "gcd", "lcm", "distance", "next", "prev",
    "begin", "end", "size", "data", "accumulate", "fill", "copy", "move", "remove", "replace", "unique",
    "transform", "merge", "search", "equal", "rotate", "partition", "to_string", "stoi", "getline",
}

RESERVED = {
    "python": set(keyword.kwlist) | {
        "print", "input", "len", "range", "int", "float", "str", "bool", "list", "dict", "set", "tuple",
        "round", "sorted", "reversed", "ord", "chr", "abs", "min", "max", "sum", "pow", "divmod", "map", "zip",
        "enumerate", "any", "all", "iter", "next", "math", "sys", "re", "type", "object", "format", "repr",
        "isinstance", "super", "open", "exit", "id", "hash", "filter", "self",
    },
    "java": {
        "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const", "continue",
        "default", "do", "double", "else", "enum", "extends", "final", "finally", "float", "for", "goto", "if",
        "implements", "import", "instanceof", "int", "interface", "long", "native", "new", "package", "private",
        "protected", "public", "return", "short", "static", "strictfp", "super", "switch", "synchronized",
        "this", "throw", "throws", "transient", "try", "void", "volatile", "while", "true", "false", "null",
        "yield", "Math", "String", "System", "Integer", "Long", "Double", "Character", "Arrays", "Collections",
        "Scanner", "Locale",
    },
    "c": _C_KEYWORDS | _C_LIBRARY,
    "c++": _C_KEYWORDS | _C_LIBRARY | _CPP_KEYWORDS,
}
RESERVED_FUNCTIONS = {"c++": _STD_FUNCTIONS}


def rename_reserved(program, target, extra=()):
    """Rename every identifier of program that target reserves; returns program.

    Methods keep their names: they are reached as attributes, where a library
    name does not clash. extra names more top-level functions to rename.
    """

    nodes = list(walk(program))
    top_level = {id(n) for n in program.body if isinstance(n, Function)}
    functions = {n.name for n in program.body if isinstance(n, Function)}
    fields = {n.name for n in nodes if isinstance(n, Field)}
    classes = {n.name for n in nodes if isinstance(n, Class)}
    names = _declared_names(nodes, top_level)
    reserved = RESERVED.get(target, set())
    clashes = {n for n in names if n in reserved}
    clashes |= {n for n in functions if n in RESERVED_FUNCTIONS.get(target, ()) or n in extra}
    if not clashes:
        return program

    taken = names | reserved | classes
    renamed = {}
    for name in sorted(clashes):
        candidate = name + "_"
        while candidate in taken:
            candidate += "_"
        renamed[name] = candidate
        taken.add(candidate)

    for node in nodes:
        if isinstance(node, (Identifier, Variable, Field)) and node.name in renamed:
            node.name = renamed[node.name]
        elif isinstance(node, Function):
            if id(node) in top_level:
                node.name = renamed.get(node.name, node.name)
            node.params = [renamed.get(p, p) if isinstance(p, str) else p for p in node.params]
            node.param_types = {renamed.get(k, k): v for k, v in node.param_types.items()}
            node.defaults = {renamed.get(k, k): v for k, v in node.defaults.items()}
        elif isinstance(node, ForLoop) and isinstance(node.iterator, str):
            node.iterator = renamed.get(node.iterator, node.iterator)
        elif isinstance(node, TryCatch) and isinstance(node.catch_var, str):
            node.catch_var = renamed.get(node.catch_var, node.catch_var)
        elif isinstance(node, FunctionCall) and node.name in functions and not getattr(node, "library", False):
            node.name = renamed.get(node.name, node.name)
        elif isinstance(node, AttributeAccess) and node.attribute in fields:
            node.attribute = renamed.get(node.attribute, node.attribute)
    return program


def _declared_names(nodes, top_level):
    names = set()
    for node in nodes:
        if isinstance(node, (Identifier, Variable, Field)):
            names.add(node.name)
        elif isinstance(node, Function):
            if id(node) in top_level:
                names.add(node.name)
            names.update(p for p in node.params if isinstance(p, str))
        elif isinstance(node, ForLoop) and isinstance(node.iterator, str):
            names.add(node.iterator)
        elif isinstance(node, TryCatch) and isinstance(node.catch_var, str):
            names.add(node.catch_var)
    return names


def walk(root):
    """Every IR object reachable from root, once."""

    seen = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, (list, tuple)):
            stack.extend(node)
            continue
        if isinstance(node, dict):
            stack.extend(node.values())
            continue
        if not hasattr(node, "__dict__") or id(node) in seen or isinstance(node, type):
            continue
        seen.add(id(node))
        yield node
        for key, value in vars(node).items():
            if key != "owner" and (isinstance(value, (list, tuple, dict)) or hasattr(value, "__dict__")):
                stack.append(value)
