import re

from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.generators.c_family import CFamilyGenerator


# Headers whose facilities have no C counterpart at all.
CPP_ONLY_HEADERS = ("vector", "string", "map", "set", "iomanip", "algorithm", "sstream",
                    "fstream", "memory", "unordered_map", "list", "queue", "stack")

CPP_SCALARS = {
    "int": "%d", "short": "%d", "unsigned": "%u", "long": "%ld", "long long": "%lld",
    "double": "%g", "float": "%g", "char": "%c", "bool": "%d",
}

# Reads that can stand inside an expression, emitted only when used.
READ_HELPERS = {
    "read_line": (
        "static char *_read_line(void) {\n"
        "    /* One whole line without its newline, like Python's input(). */\n"
        "    char buffer[1024];\n"
        "    size_t length;\n"
        "    char *copy;\n"
        "    if (!fgets(buffer, sizeof buffer, stdin)) buffer[0] = '\\0';\n"
        "    length = strcspn(buffer, \"\\r\\n\");\n"
        "    buffer[length] = '\\0';\n"
        "    copy = malloc(length + 1);\n"
        "    memcpy(copy, buffer, length + 1);\n"
        "    return copy;\n"
        "}\n\n"
    ),
    "input": (
        "static char *_input(const char *prompt) {\n"
        "    fputs(prompt, stdout);\n"
        "    return _read_line();\n"
        "}\n\n"
    ),
    "skip_line": (
        "static void _skip_line(void) {\n"
        "    int c;\n"
        "    while ((c = getchar()) != '\\n' && c != EOF) {}\n"
        "}\n\n"
    ),
    "read_int": "static int _read_int(void) { int v = 0; scanf(\"%d\", &v); return v; }\n\n",
    "read_long": "static long long _read_long(void) { long long v = 0; scanf(\"%lld\", &v); return v; }\n\n",
    "read_double": "static double _read_double(void) { double v = 0; scanf(\"%lf\", &v); return v; }\n\n",
    "read_char": "static char _read_char(void) { char c = 0; scanf(\" %c\", &c); return c; }\n\n",
    "read_word": (
        "static char *_read_word(void) {\n"
        "    char buffer[1024];\n"
        "    char *copy;\n"
        "    if (scanf(\"%1023s\", buffer) != 1) buffer[0] = '\\0';\n"
        "    copy = malloc(strlen(buffer) + 1);\n"
        "    strcpy(copy, buffer);\n"
        "    return copy;\n"
        "}\n\n"
    ),
}


class CGenerator(CFamilyGenerator):

    cpp = False

    def __init__(self, source=None, target=None):
        super().__init__(source, target)
        self.array_lengths = set()

    def generate(self, program):

        # The C++ parser emits raw source chunks; everything else emits a real IR.
        if any(isinstance(getattr(n, "body", None), str) for n in program.body):
            return self._convert_text(program)

        return self.generate_from_ir(program)

    # -----------------------------------------
    # C ARRAYS
    # -----------------------------------------

    def statement(self, stmt, indent):

        tab = "    " * indent

        # A list literal becomes a fixed array plus its length.
        if (
            isinstance(stmt, Variable)
            and isinstance(stmt.value, ArrayLiteral)
            and stmt.name not in self.scope
        ):
            element = self.type_of(self._element_of(stmt.var_type))
            elements = ", ".join(self.expr(e) for e in stmt.value.elements)
            self.scope[stmt.name] = f"{element}*"
            self.array_lengths.add(stmt.name)
            return (
                f"{tab}{element} {stmt.name}[] = {{{elements}}};\n"
                f"{tab}int {stmt.name}_length = {len(stmt.value.elements)};\n"
            )

        # new int[n] / int a[n]: a zero-filled array of a runtime size.
        if (
            isinstance(stmt, Variable)
            and isinstance(stmt.value, FunctionCall)
            and stmt.value.name == "range_array"
        ):
            if stmt.name in self.scope:
                raise UnsupportedConstruct("re-allocating an array in C")
            if len(stmt.value.args) != 1:
                raise UnsupportedConstruct("multi-dimensional arrays in C output")
            element = self.type_of(getattr(stmt.value, "element_type", None) or self._element_of(stmt.var_type))
            size = self.expr(stmt.value.args[0])
            self.scope[stmt.name] = f"{element}*"
            self.array_lengths.add(stmt.name)
            return (
                f"{tab}int {stmt.name}_length = {size};\n"
                f"{tab}{element} {stmt.name}[{stmt.name}_length];\n"
                f"{tab}memset({stmt.name}, 0, sizeof {stmt.name});\n"
            )

        return super().statement(stmt, indent)

    @staticmethod
    def _element_of(type_name):
        if isinstance(type_name, str) and type_name.startswith(("List<", "Set<")):
            return CGenerator._unbox(type_name[type_name.index("<") + 1:-1])
        return "int"

    def expr(self, node):

        # Every array argument is followed by its length.
        if isinstance(node, FunctionCall) and node.name not in ("range_array",):
            args = []
            for arg in node.args:
                args.append(super().expr(arg))
                if isinstance(arg, Identifier) and arg.name in self.array_lengths:
                    args.append(f"{arg.name}_length")
            if node.name in ("max", "min", "abs", "sqrt", "pow", "floor", "ceil"):
                return super().call(node)
            # A method called from inside its own class became Class_method.
            if self.current_class is not None:
                for method in self.current_class.methods:
                    if method.name == node.name and not method.is_constructor:
                        if not method.is_static:
                            args.insert(0, "self")
                        return f"{self.current_class.name}_{node.name}({', '.join(args)})"
            return f"{node.name}({', '.join(args)})"

        if isinstance(node, MethodCall) and node.method == "size":
            if isinstance(node.obj, Identifier) and node.obj.name in self.array_lengths:
                return f"{node.obj.name}_length"

        return super().expr(node)

    # -----------------------------------------
    # IR PATH
    # -----------------------------------------

    def headers(self, program, body):
        code = "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
        if re.search(r"\b(pow|sqrt|floor|ceil|fmod|fabs|isnan|isinf)\(", body + self.helper_code()):
            code += "#include <math.h>\n"
        if re.search(r"\b(isupper|islower|isdigit|isalpha|isspace|isalnum|toupper|tolower)\(", body):
            code += "#include <ctype.h>\n"
        return code + "\n"

    def double_text_helper(self):
        return (
            "static const char *_fmt_double(double x) {\n"
            "    /* Rotating buffers: several may appear in one printf call. */\n"
            "    static char buffers[8][40];\n"
            "    static int next = 0;\n"
            "    char *out = buffers[next++ % 8];\n"
            "    _format_double(x, out);\n"
            "    return out;\n"
            "}\n\n"
        )

    def double_text(self, code):
        return f"_fmt_double({code})"

    def helper_code(self):
        code = super().helper_code()
        if "input" in self.helpers:
            self.helpers.add("read_line")
        for name in ("read_line", "input", "skip_line", "read_int", "read_long",
                     "read_double", "read_char", "read_word"):
            if name in self.helpers:
                code += READ_HELPERS[name]
        return code

    # ---- input ----

    def _line(self, node):
        if node.prompt is not None:
            self.helpers.add("input")
            return f"_input({self.expr(node.prompt)})"
        self.helpers.add("read_line")
        return "_read_line()"

    def read_expression(self, node):

        if self.line_based(node):
            line = self._line(node)
            return {"int": f"atoi({line})", "long": f"atoll({line})",
                    "double": f"atof({line})"}.get(node.value_type, line)

        helper = {"int": "read_int", "long": "read_long", "double": "read_double",
                  "char": "read_char", "token": "read_word"}.get(node.value_type)
        if helper is None:
            return self._line(node)
        self.helpers.add(helper)
        return f"_{helper}()"

    def read_statement(self, node, indent):
        tab = "    " * indent
        if node.value_type == "eol":
            self.helpers.add("skip_line")
            return f"{tab}_skip_line();\n"
        return f"{tab}{self.read_expression(node)};\n"

    def interpolation(self, node):
        raise UnsupportedConstruct("building a formatted string in C (only printing one)")

    def print_statement(self, stmt, indent):

        tab = "    " * indent
        parts = []
        values = []

        for index, arg in enumerate(stmt.args):
            if index and stmt.sep:
                parts.append(stmt.sep.replace("%", "%%"))
            for kind, piece in self.text_pieces(arg):
                if kind == "text":
                    parts.append(piece.replace("%", "%%"))
                else:
                    parts.append(piece[0])
                    values.extend(piece[1])

        parts.append(stmt.end.replace("%", "%%"))
        fmt = self.string_literal("".join(parts))

        if values:
            return f"{tab}printf({fmt}, {', '.join(values)});\n"
        return f"{tab}printf({fmt});\n"

    SCANF_FORMATS = {"int": "%d", "long long": "%lld", "double": "%lf", "char*": "%s", "char": " %c"}

    def render_entry_call(self, cls, method):
        args = ", ".join("NULL, 0" if str(t).startswith("List<") else "0"
                         for t in (method.param_types.get(p) for p in method.params))
        return f"{cls.name}_{method.name}({args});"

    def read_into(self, target, rendered_type, indent, node):
        tab = "    " * indent

        if self.line_based(node):
            return f"{tab}{target} = {self.read_expression(node)};\n"

        if rendered_type == "char*":
            # A char* has no storage yet, so read into a fixed buffer.
            buffer = "_buf_" + re.sub(r"\W", "_", target)
            return (
                f"{tab}static char {buffer}[256];\n"
                f'{tab}scanf("%255s", {buffer});\n'
                f"{tab}{target} = {buffer};\n"
            )
        fmt = self.SCANF_FORMATS.get(rendered_type)
        if fmt is None:
            raise UnsupportedConstruct(f"reading a value of type {rendered_type} in C")
        return f'{tab}scanf("{fmt}", &{target});\n'

    def render_class(self, cls):
        """C has no classes: emit a struct plus self-taking functions."""

        previous = self.current_class
        self.current_class = cls

        code = "typedef struct {\n"
        for field in cls.fields:
            code += f"    {self.type_of(field.field_type)} {field.name};\n"
        if not cls.fields:
            code += "    char _unused;\n"
        code += f"}} {cls.name};\n\n"

        for method in cls.methods:
            code += self.render_function(method, owner=cls)

        # Name_new(...) builds a value the way `new Name(...)` builds an object.
        constructor = next((m for m in cls.methods if m.is_constructor), None)
        params = []
        if constructor is not None:
            params = [f"{self.type_of(constructor.param_types.get(p, 'Object'))} {p}" for p in constructor.params]
        code += f"{cls.name} {cls.name}_new({', '.join(params) or 'void'}) {{\n"
        code += f"    {cls.name} self;\n    memset(&self, 0, sizeof self);\n"
        for field in cls.fields:
            if field.value is not None:
                code += f"    self.{field.name} = {self.expr(field.value)};\n"
        if constructor is not None:
            args = "".join(", " + p for p in constructor.params)
            code += f"    {cls.name}_init(&self{args});\n"
        code += "    return self;\n}\n\n"

        self.current_class = previous
        return code

    def method_call(self, node):
        owner = self._type(node.obj)
        if owner in getattr(self, "class_names", ()):
            args = "".join(", " + self.expr(a) for a in node.args)
            if isinstance(node.obj, SelfRef):
                receiver = "self"
            elif isinstance(node.obj, (Identifier, AttributeAccess, IndexAccess)):
                receiver = f"&{self.expr(node.obj)}"
            else:
                raise UnsupportedConstruct("calling a method on a temporary object in C")
            return f"{owner}_{node.method}({receiver}{args})"
        return super().method_call(node)

    def generate_from_ir(self, program):
        self.class_names = {n.name for n in program.body if isinstance(n, Class)}
        return super().generate_from_ir(program)

    def render_function(self, func, indent=0, owner=None):

        tab = "    " * indent
        outer_scope = self.scope
        self.scope = dict(outer_scope)

        params = []

        if owner and not func.is_static:
            params.append(f"{owner.name}* self")
            self.scope["self"] = f"{owner.name}*"

        for p in func.params:
            declared = func.param_types.get(p, "Object")
            rendered = self.type_of(declared)
            params.append(f"{rendered} {p}")
            self.scope[p] = rendered

            # C arrays decay to pointers, so the length has to travel with them.
            if str(declared).startswith(("List<", "Set<")):
                params.append(f"int {p}_length")
                self.array_lengths.add(p)

        signature = ", ".join(params) or "void"

        if func.is_constructor and owner:
            name = f"{owner.name}_init"
            return_type = "void"
        else:
            name = f"{owner.name}_{func.name}" if owner else func.name
            return_type = self.type_of(func.return_type)

        code = f"{tab}{return_type} {name}({signature}) {{\n"

        for stmt in func.body:
            code += self.statement(stmt, indent + 1)

        self.scope = outer_scope
        return code + f"{tab}}}\n\n"

    # -----------------------------------------
    # Convert C++ constructs back to C (text path)
    # -----------------------------------------

    def _convert_text(self, program):

        source = "\n".join(n.body for n in program.body)
        # Words inside literals and comments are not code.
        scanned = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', '""', source, flags=re.DOTALL)

        for header in CPP_ONLY_HEADERS:
            if re.search(rf"#\s*include\s*<{header}>", source):
                raise UnsupportedConstruct(f"the C++ library <{header}> has no C equivalent")
        for keyword, what in ((r"\bclass\b", "classes"), (r"\btemplate\b", "templates"),
                              (r"\bnew\b", "new"), (r"\bnamespace\s+\w+\s*\{", "namespaces"),
                              (r"\bstd::(?!cout|cin|endl)", "the std library"),
                              (r"\b(?:int|long|short|unsigned|double|float|char|bool|string)\s*&\s*\w+\s*[,)=]",
                               "reference parameters")):
            if re.search(keyword, scanned):
                raise UnsupportedConstruct(f"C++ {what} have no C equivalent")

        self.declared_types = self._declared_types(source)
        code = "".join(self._convert_block(n.body) for n in program.body)

        if re.search(r"\bbool\b", code) and "<stdbool.h>" not in code:
            code = "#include <stdbool.h>\n" + code
        return code

    @staticmethod
    def _declared_types(source):
        """name -> C++ scalar type, from declarations and function signatures."""

        types = {}
        pattern = re.compile(
            r"\b(unsigned\s+long\s+long|long\s+long|unsigned|long|short|int|double|float|char|bool)"
            r"\s+(\w+)\s*(?=[=;,)\[(])"
        )
        for match in pattern.finditer(source):
            types[match.group(2)] = re.sub(r"\s+", " ", match.group(1)).replace("unsigned long long", "long long")
        # A declaration list "int a, b, c;" names every variable after the first too.
        for match in re.finditer(r"\b(int|double|float|char|bool|long long|long)\s+([^;(){}]+);", source):
            for name in re.findall(r"(?:^|,)\s*(\w+)", match.group(2)):
                types.setdefault(name, match.group(1))
        return types

    def _convert_block(self, text):

        code = text

        # ------------------------------
        # Header conversion
        # ------------------------------
        code = code.replace("<iostream>", "<stdio.h>")
        code = code.replace("<cstdlib>", "<stdlib.h>")
        code = code.replace("<cstring>", "<string.h>")
        code = code.replace("<cmath>", "<math.h>")
        code = code.replace("<cstdio>", "<stdio.h>")

        code = code.replace("using namespace std;", "")
        code = re.sub(r"\bstd::", "", code)

        # ------------------------------
        # cin >> a >> b;  ->  scanf
        # ------------------------------
        code = re.sub(r"\bcin\s*((?:>>\s*\w+\s*)+);", self._replace_cin, code)
        if re.search(r"\bcin\b", code):
            raise UnsupportedConstruct("this use of cin has no direct C equivalent")

        # ------------------------------
        # cout << ... ;  ->  printf
        # ------------------------------
        code = re.sub(r"\bcout\s*<<\s*((?:[^;\"']|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])')*);",
                      self._replace_cout, code)
        if re.search(r"\bcout\b", code):
            raise UnsupportedConstruct("this use of cout has no direct C equivalent")

        # ------------------------------
        # nullptr → NULL
        # ------------------------------
        code = re.sub(r"\bnullptr\b", "NULL", code)

        return code + "\n\n"

    def _scalar_format(self, name):
        kind = self.declared_types.get(name)
        if kind is None:
            raise UnsupportedConstruct(f"the type of '{name}' could not be determined for scanf/printf")
        return CPP_SCALARS[kind]

    def _replace_cin(self, match):
        names = re.findall(r">>\s*(\w+)", match.group(1))
        formats = []
        for name in names:
            spec = self._scalar_format(name)
            formats.append({"%g": "%lf", "%c": " %c"}.get(spec, spec).replace("%u", "%u"))
        return f'scanf("{" ".join(formats)}", {", ".join("&" + n for n in names)});'

    def _replace_cout(self, match):

        parts = _split_stream(match.group(1))
        fmt = ""
        values = []

        for part in parts:
            if part in ("endl", "'\\n'"):
                fmt += "\\n"
            elif part.startswith('"') and part.endswith('"'):
                fmt += part[1:-1].replace("%", "%%")
            elif re.fullmatch(r"'(\\.|[^'\\])'", part):
                fmt += part[1:-1].replace("%", "%%")
            elif re.fullmatch(r"-?\d+", part):
                fmt += part
            elif re.fullmatch(r"\w+", part):
                fmt += self._scalar_format(part)
                values.append(part)
            else:
                # An expression: its type follows from the names inside it.
                bare = re.sub(r'"(?:\\.|[^"\\])*"', '""', part)
                if '"' in bare:
                    spec = "%s"  # e.g. (leap ? "leap" : "not leap")
                    fmt += spec
                    values.append(part)
                    continue
                names = [n for n in re.findall(r"[A-Za-z_]\w*", bare) if n not in ("true", "false")]
                kinds = {self.declared_types.get(n) for n in names}
                if None in kinds or not kinds:
                    raise UnsupportedConstruct(f"the type of '{part}' could not be determined for printf")
                if kinds & {"double", "float"}:
                    spec = "%g"
                elif "long long" in kinds:
                    spec = "%lld"
                else:
                    spec = "%d"
                fmt += spec
                values.append(part)

        if values:
            return f'printf("{fmt}", {", ".join(values)});'
        return f'printf("{fmt}");'


def _split_stream(text):
    """Split a << chain at top level (not inside strings or parentheses)."""

    parts = []
    depth = 0
    current = ""
    index = 0
    while index < len(text):
        char = text[index]
        if char in "\"'":
            end = index + 1
            while end < len(text) and text[end] != char:
                end += 2 if text[end] == "\\" else 1
            current += text[index:end + 1]
            index = end + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0 and text.startswith("<<", index):
            parts.append(current.strip())
            current = ""
            index += 2
            continue
        current += char
        index += 1
    parts.append(current.strip())
    return [p for p in parts if p]
