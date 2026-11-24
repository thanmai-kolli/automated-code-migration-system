import re

from cross_language_system.core import library
from cross_language_system.core import precedence as prec
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.printf_format import tokens as format_tokens
from cross_language_system.generators.c_family import CFamilyGenerator

LANG = "c"

FORMAT_HELPER = (
    "static string _format(const char *fmt, ...) {\n"
    "    char buffer[1024];\n"
    "    va_list args;\n"
    "    va_start(args, fmt);\n"
    "    vsnprintf(buffer, sizeof buffer, fmt, args);\n"
    "    va_end(args);\n"
    "    return string(buffer);\n"
    "}\n\n"
)

SPLIT_HELPER = (
    "vector<string> _split(const string& text) {\n"
    "    vector<string> parts;\n"
    "    istringstream stream(text);\n"
    "    string token;\n"
    "    while (stream >> token) parts.push_back(token);\n"
    "    return parts;\n"
    "}\n\n"
)

READ_LINE_HELPER = (
    "static string _read_line() {\n"
    "    string line;\n"
    "    getline(cin, line);\n"
    "    if (!line.empty() && line.back() == '\\r') line.pop_back();\n"
    "    return line;\n"
    "}\n\n"
)

INPUT_HELPER = (
    "static string _input(const string& prompt) {\n"
    "    cout << prompt;\n"
    "    return _read_line();\n"
    "}\n\n"
)

# Python string methods C++'s std::string lacks.
STRING_HELPERS = {
    "strip": (
        "static string _strip(const string& s) {\n"
        "    size_t start = s.find_first_not_of(\" \\t\\r\\n\");\n"
        "    if (start == string::npos) return \"\";\n"
        "    size_t end = s.find_last_not_of(\" \\t\\r\\n\");\n"
        "    return s.substr(start, end - start + 1);\n"
        "}\n\n"
    ),
    "lower": (
        "static string _lower(string s) {\n"
        "    for (char& c : s) c = (char) tolower((unsigned char) c);\n"
        "    return s;\n"
        "}\n\n"
    ),
    "upper": (
        "static string _upper(string s) {\n"
        "    for (char& c : s) c = (char) toupper((unsigned char) c);\n"
        "    return s;\n"
        "}\n\n"
    ),
}

# printf conversions that cout prints identically, so the call can become <<.
STREAMABLE = re.compile(r"%(l{0,2})([dis])")


class CppGenerator(CFamilyGenerator):

    cpp = True

    def __init__(self, source=None, target=None):
        super().__init__(source, target)

    def generate(self, program):

        # The C parser emits raw source chunks; everything else emits a real IR.
        if any(isinstance(getattr(n, "body", None), str) for n in program.body):
            return self._convert_text(program)

        return self.generate_from_ir(program)

    # -----------------------------------------
    # IR PATH
    # -----------------------------------------

    def headers(self, program, body):

        helpers = self.helper_code()
        text = body + helpers
        code = "#include <iostream>\n#include <string>\n#include <vector>\n#include <map>\n"

        if re.search(r"\bset<", text):
            code += "#include <set>\n"
        if "_split(" in text:
            code += "#include <sstream>\n"
        if re.search(r"\b(printf|snprintf|vsnprintf)\(", text):
            code += "#include <cstdio>\n"
        if "va_list" in text:
            code += "#include <cstdarg>\n"
        if re.search(r"\b(strtod|atoi|atof|atoll)\(", text):
            code += "#include <cstdlib>\n"
        if re.search(r"\b(strchr|memcpy|strlen)\(", text):
            code += "#include <cstring>\n"
        if re.search(r"\b(pow|sqrt|floor|ceil|fmod|isnan|isinf|nearbyint|round|log|log10|exp|sin|cos|tan|hypot)\(", text):
            code += "#include <cmath>\n"
        if re.search(r"\b(max|min|find|sort|max_element|min_element|reverse|count)\(", text):
            code += "#include <algorithm>\n"
        if "accumulate(" in text:
            code += "#include <numeric>\n"
        if re.search(r"\b(isupper|islower|isdigit|isalpha|isspace|isalnum|toupper|tolower)\(", text):
            code += "#include <cctype>\n"

        return code + "using namespace std;\n\n"

    def helper_code(self):
        code = super().helper_code()
        if "format" in self.helpers:
            code += FORMAT_HELPER
        if "split" in self.helpers:
            code += SPLIT_HELPER
        if "input" in self.helpers:
            self.helpers.add("read_line")
        if "read_line" in self.helpers:
            code += READ_LINE_HELPER
        if "input" in self.helpers:
            code += INPUT_HELPER
        for name, helper in STRING_HELPERS.items():
            if f"string_{name}" in self.helpers:
                code += helper
        for name, helper in library.CPP_HELPERS.items():
            if f"lib_{name}" in self.helpers:
                code += helper
        return code

    def double_text_helper(self):
        return (
            "static string _fmt_double(double x) {\n"
            "    char out[40];\n"
            "    _format_double(x, out);\n"
            "    return string(out);\n"
            "}\n\n"
        )

    def double_text(self, code):
        return f"_fmt_double({code})"

    def c_string(self, code, node):
        # printf's %s needs a const char*, not a std::string.
        if isinstance(node, Constant):
            return code
        return f"{prec.postfix_operand(code, node, LANG)}.c_str()"

    def method_call(self, node):

        # C++ has no string::split, so the generator supplies one.
        if node.method == "split" and not node.args:
            self.helpers.add("split")
            return f"_split({self.expr(node.obj)})"

        if node.method == "split" and len(node.args) == 1:
            return self._split_on(node)

        if node.method in STRING_HELPERS and not node.args:
            self.helpers.add(f"string_{node.method}")
            return f"_{node.method}({self.expr(node.obj)})"

        receiver = prec.postfix_operand(self.expr(node.obj), node.obj, LANG)
        if isinstance(node.obj, Constant) and isinstance(node.obj.value, str):
            # A literal is a char array; only std::string has methods.
            receiver = f"string({receiver})"
        if node.method == "find" and len(node.args) == 1:
            # Java's indexOf and Python's find give -1, not npos, when absent.
            return f"(int) {receiver}.find({self.expr(node.args[0])})"
        if node.method == "sort" and not node.args:
            return f"sort({receiver}.begin(), {receiver}.end())"
        if node.method == "substring" and len(node.args) == 2:
            start = self.expr(node.args[0])
            end = prec.operand(self.expr(node.args[1]), node.args[1], "Sub", LANG)
            return f"{receiver}.substr({start}, {end} - {prec.operand(start, node.args[0], 'Sub', LANG, right=True)})"
        if node.method == "substring" and len(node.args) == 1:
            return f"{receiver}.substr({self.expr(node.args[0])})"
        if node.method == "startswith" and len(node.args) == 1:
            return f"({receiver}.rfind({self.expr(node.args[0])}, 0) == 0)"

        return super().method_call(node)

    def _split_on(self, node):
        """s.split(sep) with the source language's meaning."""

        text, separator = self.expr(node.obj), self.expr(node.args[0])
        self.helpers.add("lib_split_on")
        if self.source != "java":
            return f"_split_on({text}, {separator})"
        pattern = node.args[0].value if isinstance(node.args[0], Constant) else None
        if not isinstance(pattern, str):
            raise UnsupportedConstruct("String.split with a computed pattern")
        self.helpers.add("lib_java_split")
        if pattern == r"\s+":
            return f"_java_split_ws({text})"
        if re.search(r"[\\^$.|?*+()\[\]{}]", pattern):
            raise UnsupportedConstruct(f"String.split with the regular expression {pattern!r}")
        return f"_java_split({text}, {separator})"

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
            return {"int": f"stoi({line})", "long": f"stoll({line})",
                    "double": f"stod({line})"}.get(node.value_type, line)

        kind = {"int": "int", "long": "long long", "double": "double",
                "token": "string", "char": "char"}.get(node.value_type)
        if kind is None:
            return self._line(node)
        # An immediately-invoked lambda lets a read work as an expression.
        return f"[]{{ {kind} _v; cin >> _v; return _v; }}()"

    def read_statement(self, node, indent):
        tab = "    " * indent
        if node.value_type == "eol":
            return f"{tab}{{ string _rest; getline(cin, _rest); }}\n"
        return f"{tab}{self.read_expression(node)};\n"

    # ---- strings ----

    def to_text(self, node):
        """std::string spelling of a value, as the source would print it."""

        code = self.expr(node)
        kind = self._type(node)

        if kind == "String":
            return code
        if kind and kind.startswith("List<") and self.source == "python":
            self.helpers.update(("lib_repr", "fmt_double"))
            return f"_py_repr({code})"
        if kind and kind.startswith("List<") and self.source == "java":
            self.helpers.add("lib_java_text")
            return f"_java_text({code})"
        if kind == "char":
            return f"string(1, {code})"
        if kind == "boolean":
            words = ('"True"', '"False"') if self.source == "python" else ('"true"', '"false"')
            return f"string({prec.ternary_part(code, node)} ? {words[0]} : {words[1]})"
        if kind == "double":
            if self.source in ("python", "java"):
                self.helpers.add("fmt_double")
                return f"_fmt_double({code})"
            return f"_format(\"%g\", {code})"
        if kind in ("int", "long"):
            return f"to_string({code})"
        raise UnsupportedConstruct(f"converting '{code}' to a string: its type is unknown")

    def concatenate(self, node):

        parts = []

        def collect(item):
            if isinstance(item, BinaryOp) and item.operator == "Add" and self._type(item) == "String":
                collect(item.left)
                collect(item.right)
            else:
                parts.append(item)

        collect(node)

        rendered = []
        for index, part in enumerate(parts):
            if isinstance(part, Constant) and isinstance(part.value, str) and not getattr(part, "is_char", False):
                text = self.constant(part.value)
                # "a" + "b" would add two pointers.
                rendered.append(f"string({text})" if index == 0 else text)
            elif self._type(part) == "String":
                rendered.append(prec.operand(self.expr(part), part, "Add", LANG, right=index > 0))
            else:
                rendered.append(self.to_text(part))
        return " + ".join(rendered)

    def interpolation(self, node):

        pieces = []
        for part in node.parts:
            if isinstance(part, Constant) and isinstance(part.value, str):
                if part.value:
                    pieces.append(self.constant(part.value))
            elif isinstance(part, FormatString):
                pieces.append(self.format_string(part))
            else:
                pieces.append(self.to_text(part))

        if not pieces:
            return 'string("")'
        if pieces[0].startswith('"'):
            pieces[0] = f"string({pieces[0]})"
        return " + ".join(pieces)

    def format_string(self, node):
        fmt, values = self.c_format(node.fmt, node.args)
        self.helpers.add("format")
        return f"_format({self.string_literal(fmt)}{''.join(', ' + v for v in values)})"

    def membership(self, node):

        container = self.expr(node.right)
        needle = self.expr(node.left)
        kind = self._type(node.right) or ""

        if isinstance(node.right, Constant) and isinstance(node.right.value, str):
            container = f"string({container})"

        if kind == "String":
            test = f"{prec.postfix_operand(container, node.right, LANG)}.find({needle}) != string::npos"
        elif kind.startswith(("Set<", "Map<")):
            test = f"{prec.postfix_operand(container, node.right, LANG)}.count({needle}) > 0"
        elif kind.startswith("List<"):
            test = self._once(node.right, lambda c: f"find({c}.begin(), {c}.end(), {needle}) != {c}.end()")
        else:
            raise UnsupportedConstruct("the in operator on a value of unknown type")

        return test if node.operator == "In" else f"!({test})"

    def call(self, node):
        if node.name == "range_array":
            if len(node.args) != 1:
                raise UnsupportedConstruct("multi-dimensional arrays in C++ output")
            element = self.type_of(getattr(node, "element_type", None) or "int")
            if element == "auto":
                element = "int"
            fill = getattr(node, "fill", None)
            if fill is not None:
                return f"vector<{element}>({self.expr(node.args[0])}, {self.expr(fill)})"
            return f"vector<{element}>({self.expr(node.args[0])})"
        if node.name in ("min", "max", "sum") and len(node.args) == 1:
            if node.name == "sum":
                zero = {"double": "0.0", "long": "0LL"}.get(self._type(node), "0")
                return self._once(node.args[0], lambda c: f"accumulate({c}.begin(), {c}.end(), {zero})")
            return self._once(node.args[0], lambda c: f"*{node.name}_element({c}.begin(), {c}.end())")
        return super().call(node)

    def _once(self, container, body):
        """body(c) over a container expression that must be evaluated exactly once."""
        code = self.expr(container)
        if isinstance(container, (Identifier, AttributeAccess)):
            return body(prec.postfix_operand(code, container, LANG))
        return f"[&](const auto& _c) {{ return {body('_c')}; }}({code})"

    # ---- output ----

    def print_statement(self, stmt, indent):

        tab = "    " * indent
        args = list(stmt.args)

        # printf(...) alone keeps its exact formatting.
        if len(args) == 1 and isinstance(args[0], FormatString):
            fmt, values = self.c_format(args[0].fmt, args[0].args)
            fmt += stmt.end.replace("%", "%%")
            return f"{tab}printf({self.string_literal(fmt)}{''.join(', ' + v for v in values)});\n"

        end = stmt.end
        if end == "" and args and isinstance(args[-1], Constant) and args[-1].value == "\n":
            args = args[:-1]
            end = "\n"

        pieces = []
        for index, arg in enumerate(args):
            if index and stmt.sep:
                pieces.append(self.constant(stmt.sep))
            pieces.append(self._stream_piece(arg))

        if end == "\n":
            pieces.append("endl")
        elif end:
            pieces.append(self.constant(end))

        if not pieces:
            return ""
        return f"{tab}cout << {' << '.join(pieces)};\n"

    def _stream_piece(self, node):

        kind = self._type(node)

        # A concatenation or f-string streams piece by piece.
        if isinstance(node, BinaryOp) and node.operator == "Add" and kind == "String":
            return f"{self._stream_piece(node.left)} << {self._stream_piece(node.right)}"
        if isinstance(node, StringInterpolation):
            parts = [p for p in node.parts if not (isinstance(p, Constant) and p.value == "")]
            return " << ".join(self._stream_piece(p) for p in parts) if parts else '""'

        if isinstance(node, FormatString):
            return self.format_string(node)
        if kind and kind.startswith("List<") and self.source in ("python", "java"):
            return self.to_text(node)
        if kind == "boolean" and self.source in ("python", "java"):
            words = ('"True"', '"False"') if self.source == "python" else ('"true"', '"false"')
            return f"({prec.ternary_part(self.expr(node), node)} ? {words[0]} : {words[1]})"
        if kind == "double" and self.source in ("python", "java"):
            self.helpers.add("fmt_double")
            return f"_fmt_double({self.expr(node)})"
        if isinstance(node, Constant) and node.value is None:
            return self.constant("None" if self.source == "python" else "null")

        # << binds tighter than comparisons, logic and ?:, so those need grouping.
        return prec.operand(self.expr(node), node, "LShift", LANG, right=True)

    def read_into(self, target, rendered_type, indent, node):
        tab = "    " * indent
        if self.line_based(node):
            return f"{tab}{target} = {self.read_expression(node)};\n"
        # Only a whole-line read uses getline; a token read must stop at whitespace.
        if node.value_type == "String":
            return f"{tab}getline(cin, {target});\n"
        return f"{tab}cin >> {target};\n"

    def render_entry_call(self, cls, method):
        args = ", ".join("{}" for _ in method.params)
        return f"{cls.name}::{method.name}({args});"

    def render_class(self, cls):

        previous = self.current_class
        self.current_class = cls

        base = f" : public {cls.base}" if cls.base else ""
        code = f"class {cls.name}{base} {{\npublic:\n"

        for field in cls.fields:
            code += f"    {self.declared_type(field.field_type)} {field.name};\n"

        if cls.fields:
            code += "\n"

        for method in cls.methods:
            code += self.render_function(method, indent=1, owner=cls)

        code += "};\n\n"
        self.current_class = previous
        return code

    def render_function(self, func, indent=0, owner=None):

        tab = "    " * indent
        outer_scope = self.scope
        self.scope = dict(outer_scope)

        params = []
        for p in func.params:
            rendered = self.declared_type(func.param_types.get(p, "Object"))
            # C++ supports default arguments directly.
            default = func.defaults.get(p)
            suffix = f" = {self.expr(default)}" if default is not None else ""
            params.append(f"{rendered} {p}{suffix}")
            self.scope[p] = rendered

        if owner:
            for field in owner.fields:
                self.scope[field.name] = self.declared_type(field.field_type)

        signature = ", ".join(params)
        return_type = self.type_of(func.return_type)

        # C++ has no Object root type, so an unresolved element type becomes a
        # template parameter rather than an invalid vector<auto>.
        prefix = ""
        if "auto" in signature and "<auto>" in signature:
            signature = signature.replace("<auto>", "<T>")
            return_type = return_type.replace("<auto>", "<T>")
            prefix = f"{tab}template <typename T>\n"

        if func.is_constructor and owner:
            code = f"{prefix}{tab}{owner.name}({signature}) {{\n"
        else:
            modifier = "static " if owner and func.is_static else ""
            code = f"{prefix}{tab}{modifier}{return_type} {func.name}({signature}) {{\n"

        for stmt in func.body:
            code += self.statement(stmt, indent + 1)

        self.scope = outer_scope
        return code + f"{tab}}}\n\n"

    # -----------------------------------------
    # Convert C constructs to C++ (text path)
    # -----------------------------------------

    def _convert_text(self, program):

        self.converted_allocations = set()
        self.char_names = _char_names("\n".join(n.body for n in program.body))
        code = "".join(self._convert_block(n.body) for n in program.body)

        # Anything still calling the C stdio functions needs their header.
        if re.search(r"\b(printf|scanf|puts|putchar|getchar|fgets)\s*\(", code) and "<cstdio>" not in code:
            if "#include <iostream>" in code:
                code = code.replace("#include <iostream>", "#include <iostream>\n#include <cstdio>", 1)
            else:
                code = "#include <cstdio>\n" + code
        return code

    def _convert_block(self, text):

        code = text

        # ------------------------------
        # Headers conversion
        # ------------------------------
        code = re.sub(r"#[ \t]*include[ \t]*<", "#include <", code)
        code = code.replace("<stdio.h>", "<iostream>")
        code = code.replace("<stdlib.h>", "<cstdlib>")
        code = code.replace("<string.h>", "<cstring>")
        code = code.replace("<math.h>", "<cmath>")
        code = code.replace("<stdbool.h>", "<cstdbool>")

        if "#include <iostream>" in code and "using namespace std;" not in code:
            code = code.replace(
                "#include <iostream>",
                "#include <iostream>\nusing namespace std;"
            )

        code = _cast_allocations(code)

        # ------------------------------
        # printf → cout, only where cout prints exactly the same text
        # ------------------------------
        code = re.sub(
            r'\bprintf\s*\(\s*"((?:\\.|[^"\\])*)"\s*((?:,[^;]*)?)\)\s*;',
            self._convert_printf,
            code
        )

        # ------------------------------
        # scanf → cin, for plain numeric and word reads
        # ------------------------------
        code = re.sub(
            r'\bscanf\s*\(\s*"((?:\\.|[^"\\])*)"\s*((?:,[^;]*)?)\)\s*;',
            self._convert_scanf,
            code
        )

        # ------------------------------
        # malloc → new, and free → delete[] only for those allocations
        # ------------------------------
        def to_new(match):
            self.converted_allocations.add(match.group(1))
            return f"{match.group(1)} = new {match.group(2)}[{match.group(3)}];"

        code = re.sub(
            r'(\w+)\s*=\s*\((\w+)\*\)\s*malloc\(sizeof\(\w+\)\s*\*\s*(\w+)\);',
            to_new,
            code
        )

        def to_zeroed_new(match):
            self.converted_allocations.add(match.group(1))
            return f"{match.group(1)} = new {match.group(2)}[{match.group(3)}]();"

        code = re.sub(
            r'(\w+)\s*=\s*\((\w+)\*\)\s*calloc\((\w+),\s*sizeof\(\w+\)\);',
            to_zeroed_new,
            code
        )

        code = re.sub(
            r'\bfree\((\w+)\);',
            lambda m: f"delete[] {m.group(1)};" if m.group(1) in self.converted_allocations else m.group(0),
            code
        )

        # ------------------------------
        # NULL → nullptr (outside string literals)
        # ------------------------------
        code = _outside_strings(code, lambda chunk: re.sub(r"\bNULL\b", "nullptr", chunk))

        # ------------------------------
        # puts → cout
        # ------------------------------
        code = re.sub(
            r'\bputs\("((?:\\.|[^"\\])*)"\);',
            r'cout << "\1" << endl;',
            code
        )

        return code + "\n\n"

    # -----------------------------------------
    # printf conversion
    # -----------------------------------------
    def _convert_printf(self, match):

        if not _statement_start(match.string, match.start()):
            # printf inside an expression returns a count; cout << would not.
            return match.group(0)

        format_string = match.group(1)
        arguments = _split_arguments(match.group(2)[1:]) if match.group(2).strip() else []

        try:
            pieces = format_tokens(format_string)
        except UnsupportedConstruct:
            return match.group(0)

        specs = [p for p in pieces if isinstance(p, dict) and p["conv"] != "%"]
        simple = all(
            p["conv"] in "dis" and not p["flags"] and not p["width"] and p["precision"] is None
            and p["length"] in (None, "l", "ll")
            for p in specs
        )
        # %f, %.2f, widths, %c, %u ... print differently through cout.
        if not simple or len(specs) != len(arguments):
            return match.group(0)

        result = "cout"
        index = 0
        for piece in pieces:
            if isinstance(piece, str):
                result += f' << "{piece}"'
            elif piece["conv"] == "%":
                result += ' << "%"'
            else:
                argument = arguments[index]
                # A character constant is an int in C but a char in C++, and cout
                # prints a char as a character, so %d of a char needs a cast.
                base = re.match(r"\w+", argument)
                if piece["conv"] in "di" and (re.fullmatch(r"'(\\.|[^'\\])'", argument)
                                              or (base and base.group(0) in getattr(self, "char_names", ()))):
                    argument = f"int({argument})"
                # << binds tighter than &, |, ^, comparisons and ?:.
                if not re.fullmatch(r"[\w.]+(\[[^\]]*\])*(\([^()]*\))?", argument):
                    argument = f"({argument})"
                result += f" << {argument}"
                index += 1

        return (result if result != "cout" else 'cout << ""') + ";"

    # -----------------------------------------
    # scanf conversion
    # -----------------------------------------
    def _convert_scanf(self, match):

        arguments = _split_arguments(match.group(2)[1:]) if match.group(2).strip() else []
        try:
            pieces = format_tokens(match.group(1))
        except UnsupportedConstruct:
            return match.group(0)

        specs = [p for p in pieces if isinstance(p, dict)]
        literal = "".join(p for p in pieces if isinstance(p, str))
        if (literal.strip() or len(specs) != len(arguments)
                or any(p["conv"] not in "dfs" or p["width"] or p["flags"] for p in specs)
                or not all(a.startswith("&") or p["conv"] == "s" for a, p in zip(arguments, specs))):
            return match.group(0)

        targets = [a.lstrip("&").strip() for a in arguments]
        return "cin >> " + " >> ".join(targets) + ";"


def _statement_start(code, index):
    """True when the text at index begins a statement rather than sits inside an expression."""

    before = code[:index].rstrip()
    if not before or before[-1] in ";{})":
        return True
    if re.search(r"\b(else|do)$", before):
        return True
    return before[-1] == ":" and bool(re.search(r"(\bcase\b[^;{}?]*|\bdefault\s*|^\s*\w+\s*):$", before, re.M))


_ALLOCATION = r"(malloc|calloc|realloc)\s*\("
_POINTER_TYPE = r"\b((?:(?:unsigned|signed|const|struct)\s+)*[A-Za-z_]\w*)\s*(\*+)\s*"


def _without_const(type_name):
    return re.sub(r"\bconst\s+", "", type_name)


def _cast_allocations(code):
    """C converts malloc's void* implicitly; C++ needs a cast: int *a = (int *) malloc(...)."""

    pointers = {m.group(3): (_without_const(m.group(1)), m.group(2))
                for m in re.finditer(_POINTER_TYPE + r"(\w+)\s*(?=[=;,)\[])", code)}
    code = re.sub(_POINTER_TYPE + r"(\w+)\s*=\s*" + _ALLOCATION,
                  lambda m: f"{m.group(1)} {m.group(2)}{m.group(3)} = "
                            f"({_without_const(m.group(1))} {m.group(2)}) {m.group(4)}(", code)

    def assignment(match):
        name = match.group(2)
        if name not in pointers:
            return match.group(0)
        base, stars = pointers[name]
        return f"{match.group(1)}{name} = ({base} {stars}) {match.group(3)}("

    return re.sub(r"(^|[;{}\s])(\w+)\s*=\s*" + _ALLOCATION, assignment, code)


def _char_names(code):
    """Names declared with a char type (scalars, arrays and pointers)."""

    names = set()
    for match in re.finditer(r"\b(?:(?:un)?signed\s+)?char\s+([^;(){}]+);", code):
        for declarator in _split_arguments(match.group(1)):
            name = re.match(r"[\s*]*(\w+)", declarator)
            if name:
                names.add(name.group(1))
    return names


def _split_arguments(text):
    """Split call arguments at top-level commas."""

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
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
        index += 1
    if current.strip():
        parts.append(current.strip())
    return parts


def _outside_strings(code, transform):
    """Apply transform to everything except string and char literals."""

    pieces = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\')', code)
    return "".join(piece if index % 2 else transform(piece) for index, piece in enumerate(pieces))
