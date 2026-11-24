"""Shared IR-to-C-family code generation.

The C and C++ generators historically worked only on raw text, because the C
parser emits source chunks rather than a structured IR. That is fine for C<->C++
but leaves Python->C/C++ unimplemented. This module renders a real IR into either
language so every source/target pair is covered.
"""

from cross_language_system.core import library
from cross_language_system.core import precedence as prec
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *

LANG = "c"

ARITHMETIC = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "TruncDiv": "/", "TruncMod": "%",
    "BitAnd": "&", "BitOr": "|", "BitXor": "^", "LShift": "<<", "RShift": ">>",
}

COMPARISON = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=",
    "And": "&&", "Or": "||", "Is": "==", "IsNot": "!=",
}

UNARY = {"USub": "-", "UAdd": "+", "Not": "!", "Invert": "~"}

# Python's // and % round toward negative infinity; C's / and % toward zero.
FLOOR_HELPERS = {
    "int": (
        "static int py_floordiv(int a, int b) {\n"
        "    int q = a / b;\n"
        "    return (q * b != a && ((a < 0) != (b < 0))) ? q - 1 : q;\n"
        "}\n\n"
        "static int py_floormod(int a, int b) {\n"
        "    int r = a % b;\n"
        "    return (r != 0 && ((r < 0) != (b < 0))) ? r + b : r;\n"
        "}\n\n"
    ),
    "long": (
        "static long long py_floordiv_ll(long long a, long long b) {\n"
        "    long long q = a / b;\n"
        "    return (q * b != a && ((a < 0) != (b < 0))) ? q - 1 : q;\n"
        "}\n\n"
        "static long long py_floormod_ll(long long a, long long b) {\n"
        "    long long r = a % b;\n"
        "    return (r != 0 && ((r < 0) != (b < 0))) ? r + b : r;\n"
        "}\n\n"
    ),
}

# The shortest text that reads back as the same double, laid out the way
# Python's repr (or Java's Double.toString) lays it out.
FORMAT_DOUBLE_BODY = (
    "static void _format_double(double x, char *out) {{\n"
    "    char digits[32];\n"
    "    int precision, exponent, length, i;\n"
    "    char *mark;\n"
    "    if (isnan(x)) {{ snprintf(out, 40, \"nan\"); return; }}\n"
    "    if (isinf(x)) {{ snprintf(out, 40, x > 0 ? \"{inf}\" : \"-{inf}\"); return; }}\n"
    "    for (precision = 1; precision <= 17; precision++) {{\n"
    "        snprintf(digits, sizeof digits, \"%.*e\", precision - 1, x);\n"
    "        if (strtod(digits, NULL) == x) break;\n"
    "    }}\n"
    "    mark = strchr(digits, 'e');\n"
    "    exponent = atoi(mark + 1);\n"
    "    *mark = '\\0';\n"
    "    /* digits is now [-]d[.ddd]; drop the point and trailing zeros. */\n"
    "    {{\n"
    "        char bare[32];\n"
    "        int n = 0, negative = digits[0] == '-';\n"
    "        for (i = negative; digits[i]; i++) if (digits[i] != '.') bare[n++] = digits[i];\n"
    "        while (n > 1 && bare[n - 1] == '0') n--;\n"
    "        bare[n] = '\\0';\n"
    "        length = 0;\n"
    "        if (negative) out[length++] = '-';\n"
    "        if (exponent < {low} || exponent >= {high}) {{\n"
    "            out[length++] = bare[0];\n"
    "            out[length++] = '.';\n"
    "            if (n > 1) {{ memcpy(out + length, bare + 1, n - 1); length += n - 1; }}\n"
    "            else out[length++] = '0';\n"
    "            {exponent_format}\n"
    "        }} else if (exponent < 0) {{\n"
    "            out[length++] = '0';\n"
    "            out[length++] = '.';\n"
    "            for (i = -1; i > exponent; i--) out[length++] = '0';\n"
    "            memcpy(out + length, bare, n); length += n;\n"
    "            out[length] = '\\0';\n"
    "        }} else {{\n"
    "            for (i = 0; i <= exponent; i++) out[length++] = i < n ? bare[i] : '0';\n"
    "            out[length++] = '.';\n"
    "            if (n > exponent + 1) {{ memcpy(out + length, bare + exponent + 1, n - exponent - 1); length += n - exponent - 1; }}\n"
    "            else out[length++] = '0';\n"
    "            out[length] = '\\0';\n"
    "        }}\n"
    "    }}\n"
    "}}\n\n"
)

PYTHON_DOUBLE = dict(
    inf="inf", low=-4, high=16,
    exponent_format=(
        "if (n == 1) length -= 2; /* 1e+16, not 1.0e+16 */\n"
        "            snprintf(out + length, 16, \"e%c%02d\", exponent < 0 ? '-' : '+', exponent < 0 ? -exponent : exponent);"
    ),
)

JAVA_DOUBLE = dict(
    inf="Infinity", low=-3, high=7,
    exponent_format="snprintf(out + length, 16, \"E%d\", exponent);",
)


class CFamilyGenerator:
    """Base emitter. Subclasses set `cpp` and provide the type table."""

    cpp = True

    def __init__(self, source=None, target=None):
        self.source = (source or "").lower()
        self.target = target
        self.scope = {}
        self.current_class = None
        self.helpers = set()

    # ------------------------------------------------------------
    # TYPES
    # ------------------------------------------------------------

    def type_of(self, name):

        if not name or name in ("Object", "object", "auto"):
            return "auto" if self.cpp else "void*"

        if name == "void":
            return "void"

        simple = {
            "int": "int",
            "long": "long long",
            "float": "double",
            "double": "double",
            "char": "char",
            "bool": "bool" if self.cpp else "int",
            "boolean": "bool" if self.cpp else "int",
            "str": "string" if self.cpp else "char*",
            "token": "string" if self.cpp else "char*",
            "String": "string" if self.cpp else "char*",
        }

        if name in simple:
            return simple[name]

        if name.startswith(("List<", "Set<")):
            element = self._unbox(name[name.index("<") + 1:-1])
            if self.cpp:
                container = "vector" if name.startswith("List<") else "set"
                return f"{container}<{self.type_of(element)}>"
            # C has no generics; an unresolved element defaults to int.
            inner = self.type_of(element)
            return f"{'int' if inner == 'void*' else inner}*"

        if name.startswith("Map<"):
            key, value = [p.strip() for p in name[4:-1].split(",", 1)]
            if self.cpp:
                return f"map<{self.type_of(self._unbox(key))}, {self.type_of(self._unbox(value))}>"
            return "void*"

        # A class name passes through; C uses the struct typedef.
        return name

    def declared_type(self, name):
        """Type for a slot that has no initializer to deduce from.

        ``auto`` is only legal where the compiler can see an initializer, so a
        data member or a parameter must fall back to the untyped pointer that
        both languages already use for unresolved values.
        """
        rendered = self.type_of(name)
        return "void*" if rendered == "auto" else rendered

    @staticmethod
    def _unbox(name):
        return {"Integer": "int", "Long": "long", "Double": "double", "Boolean": "bool",
                "Character": "char", "String": "String", "Object": "Object"}.get(name, name)

    def default_value(self, type_name):
        rendered = self.type_of(type_name)
        if rendered in ("int", "long long", "char"):
            return "0"
        if rendered == "double":
            return "0.0"
        if rendered == "bool":
            return "false"
        if rendered == "string":
            return '""'
        if rendered == "char*":
            return "NULL"
        return "{}" if self.cpp else "0"

    @staticmethod
    def _type(expr):
        return getattr(expr, "inferred_type", None)

    # ------------------------------------------------------------
    # PROGRAM
    # ------------------------------------------------------------

    def generate_from_ir(self, program):

        self.helpers = set()
        self.class_names = {n.name for n in program.body if isinstance(n, Class)}
        self.user_functions = library.user_functions(program)

        # A class must be declared before code that uses it, and only the class
        # holding the entry point uses the others.
        classes = sorted(
            (n for n in program.body if isinstance(n, Class)),
            key=lambda cls: any(m.name == "main" for m in cls.methods),
        )
        functions = [n for n in program.body if isinstance(n, Function)]
        top_level = [
            n for n in program.body
            if not isinstance(n, (Class, Function))
        ]

        body = ""

        for cls in classes:
            body += self.render_class(cls)

        for func in functions:
            if func.name == "main":
                continue
            body += self.render_function(func)

        user_main = next((f for f in functions if f.name == "main"), None)

        body += "int main() {\n"
        if user_main:
            for stmt in user_main.body:
                body += self.statement(stmt, 1)
        else:
            # A class-based source keeps its entry point as a static method.
            entry = self.entry_call(classes)
            if entry:
                body += f"    {entry}\n"
        for stmt in top_level:
            body += self.statement(stmt, 1)
        body += "    return 0;\n}\n"

        # Headers come last so they can react to what the body actually needs.
        return self.headers(program, body) + self.helper_code() + body

    def helper_code(self):

        code = ""
        for kind in ("int", "long"):
            if f"floor_{kind}" in self.helpers:
                code += FLOOR_HELPERS[kind]
        if "fmt_double" in self.helpers:
            style = JAVA_DOUBLE if self.source == "java" else PYTHON_DOUBLE
            code += FORMAT_DOUBLE_BODY.format(**style)
            code += self.double_text_helper()
        return code

    def double_text_helper(self):
        raise NotImplementedError

    # ------------------------------------------------------------
    # VALUE FORMATTING (shared by printf in C and _format in C++)
    # ------------------------------------------------------------

    def value_spec(self, node):
        """(printf spec, C expression) that prints node as the source did."""

        code = self.expr(node)
        kind = self._type(node)

        if isinstance(node, Constant) and node.value is None:
            return "%s", self.string_literal("None" if self.source == "python" else "null")

        if kind is None or kind == "Object":
            rendered = self._expr_type(node) or ""
            kind = {"int": "int", "long long": "long", "double": "double", "char": "char",
                    "char*": "String", "string": "String", "bool": "boolean"}.get(rendered)
            if kind is None:
                raise UnsupportedConstruct(
                    f"printing '{code}', whose type could not be determined"
                )

        if kind == "boolean":
            if self.source == "python":
                return "%s", f'{prec.ternary_part(code, node)} ? "True" : "False"'
            if self.source == "java":
                return "%s", f'{prec.ternary_part(code, node)} ? "true" : "false"'
            return "%d", code
        if kind == "double":
            if self.source in ("python", "java"):
                self.helpers.add("fmt_double")
                return "%s", self.double_text(code)
            return "%g", code
        if kind == "long":
            return "%lld", code
        if kind == "char":
            return "%c", code
        if kind == "String":
            return "%s", self.c_string(code, node)
        if kind == "int":
            return "%d", code
        raise UnsupportedConstruct(f"printing a value of type {kind}")

    def double_text(self, code):
        raise NotImplementedError

    def c_string(self, code, node):
        return code

    def c_format(self, fmt, args):
        """A source format (C, Java or Python dialect) -> (C format, C values)."""

        from cross_language_system.core.printf_format import tokens

        parts = []
        values = []
        remaining = list(args)

        for token in tokens(fmt):
            if isinstance(token, str):
                parts.append(token.replace("%", "%%"))
                continue
            conv = token["conv"]
            if conv == "%":
                parts.append("%%")
                continue
            if conv in "pn" or token["width"] == "*" or token["precision"] == "*":
                raise UnsupportedConstruct(f"the format conversion {token['raw']}")
            if not remaining:
                raise UnsupportedConstruct("a format with more conversions than values")
            node = remaining.pop(0)
            kind = self._type(node)
            code = self.expr(node)
            spec = "%" + token["flags"] + (token["width"] or "") + (
                "." + token["precision"] if token["precision"] is not None else "")

            if conv in "di" or conv == "u":
                if kind == "double":
                    code = f"(int) {prec.unary_operand(code, node, LANG)}"
                    kind = "int"
                conv = ("ll" if kind == "long" else "") + "d"
            elif conv in "oxX":
                conv = ("ll" if kind == "long" else "") + conv
            elif conv in "eEfFgG":
                if kind in ("int", "long", "char"):
                    code = f"(double) {prec.unary_operand(code, node, LANG)}"
            elif conv == "s":
                if kind != "String":
                    # Python's %s and Java's %s print any value.
                    nested, code = self.value_spec(node)
                    if nested != "%s":
                        conv = nested[1:]
                else:
                    code = self.c_string(code, node)
            parts.append(spec + conv)
            values.append(code)

        if remaining:
            raise UnsupportedConstruct("a format with fewer conversions than values")
        return "".join(parts), values

    def text_pieces(self, node):
        """Flatten printed text: literals, formats, concatenations, values.

        Returns a list of ("text", str) and ("format", (fmt, values)) items.
        """

        if isinstance(node, Constant) and isinstance(node.value, str):
            return [("text", node.value)]

        if isinstance(node, FormatString):
            return [("format", self.c_format(node.fmt, node.args))]

        if isinstance(node, StringInterpolation):
            pieces = []
            for part in node.parts:
                pieces.extend(self.text_pieces(part))
            return pieces

        if isinstance(node, BinaryOp) and node.operator == "Add" and self._type(node) == "String":
            return self.text_pieces(node.left) + self.text_pieces(node.right)

        spec, code = self.value_spec(node)
        return [("format", (spec, [code]))]

    def headers(self, program, body):
        raise NotImplementedError

    def entry_call(self, classes):
        """Statement that invokes a class-based entry point, if there is one."""

        for cls in classes:
            for method in cls.methods:
                if method.name == "main":
                    return self.render_entry_call(cls, method)
        return None

    def render_entry_call(self, cls, method):
        raise NotImplementedError

    # ------------------------------------------------------------
    # EXPRESSIONS
    # ------------------------------------------------------------

    def receiver(self, node):
        return prec.postfix_operand(self.expr(node), node, LANG)

    def condition(self, node):
        """A C test for a value the source tests for truth.

        Ints already mean what they mean in Python and C; a Python container
        or string is true when non-empty, which a pointer test would not check.
        """

        code = self.expr(node)
        kind = self._type(node) or ""
        if self.source != "python":
            return code
        if kind.startswith(("List<", "Set<", "Map<")):
            if self.cpp:
                return f"!{self.receiver(node)}.empty()"
            if isinstance(node, Identifier):
                return f"{node.name}_length != 0"
            raise UnsupportedConstruct("testing a list expression for emptiness in C")
        if kind == "String":
            return f"!{self.receiver(node)}.empty()" if self.cpp else f"{self.receiver(node)}[0] != '\\0'"
        return code

    def condition_operand(self, node, parent, right=False):
        plain = self.expr(node)
        test = self.condition(node)
        if test != plain:
            return f"({test})"
        if parent == "Not":
            return prec.unary_operand(test, node, LANG)
        return prec.operand(test, node, parent, LANG, right=right)

    def expr(self, node):

        if node is None:
            return "NULL" if not self.cpp else "nullptr"

        if isinstance(node, Constant):
            if getattr(node, "is_char", False) and isinstance(node.value, str) and len(node.value) == 1:
                return self.char_literal(node.value)
            return self.constant(node.value)

        if isinstance(node, Identifier):
            return node.name

        if isinstance(node, SelfRef):
            return "this" if self.cpp else "self"

        if isinstance(node, AttributeAccess):
            # C++ objects are values (.) except this (->); C methods take self
            # by pointer (->) and every other struct is a value (.).
            arrow = "->" if isinstance(node.obj, SelfRef) else "."
            return f"{self.receiver(node.obj)}{arrow}{node.attribute}"

        if isinstance(node, UnaryOp):
            if node.operator not in UNARY:
                raise UnsupportedConstruct(f"unary operator {node.operator}")
            if node.operator == "Not":
                return f"!{self.condition_operand(node.operand, 'Not')}"
            operand = prec.unary_operand(self.expr(node.operand), node.operand, LANG)
            return f"{UNARY[node.operator]}{operand}"

        if isinstance(node, BinaryOp):
            return self.binary(node)

        if isinstance(node, BooleanOp):
            return self.comparison(node)

        if isinstance(node, TernaryOp):
            condition = self.condition(node.condition)
            condition = f"({condition})" if condition != self.expr(node.condition) \
                else prec.ternary_part(condition, node.condition)
            return (
                f"{condition} ? "
                f"{prec.ternary_part(self.expr(node.if_true), node.if_true)} : "
                f"{self.expr(node.if_false)}"
            )

        if isinstance(node, IndexAccess):
            element = f"{self.receiver(node.obj)}[{self.expr(node.index)}]"
            if self.cpp and self.source == "python" and self._type(node.obj) == "String":
                # Indexing a Python string gives a one-character string.
                return f"string(1, {element})"
            return element

        if isinstance(node, TypeCast):
            return self.cast(node)

        if isinstance(node, ObjectCreation):
            # Java's collection classes become plain initialisers.
            if node.class_name in ("ArrayList", "LinkedList", "Vector",
                                   "HashMap", "TreeMap", "HashSet", "TreeSet"):
                return "{}"
            args = ", ".join(self.expr(a) for a in (node.arguments or []))
            return f"{node.class_name}({args})" if self.cpp else f"{node.class_name}_new({args})"

        if isinstance(node, FunctionCall):
            return self.call(node)

        if isinstance(node, MethodCall):
            return self.method_call(node)

        if isinstance(node, Input):
            return self.read_expression(node)

        if isinstance(node, ArrayLiteral):
            elements = ", ".join(self.expr(e) for e in node.elements)
            return "{" + elements + "}"

        if isinstance(node, SetLiteral):
            return "{" + ", ".join(self.expr(e) for e in node.elements) + "}"

        if isinstance(node, DictLiteral):
            pairs = ", ".join(
                "{" + f"{self.expr(k)}, {self.expr(v)}" + "}"
                for k, v in zip(node.keys, node.values)
            )
            return "{" + pairs + "}"

        if isinstance(node, StringInterpolation):
            return self.interpolation(node)

        if isinstance(node, FormatString):
            return self.format_string(node)

        if isinstance(node, RangeCall):
            raise UnsupportedConstruct("range() used as a value")

        raise UnsupportedConstruct(f"expression {type(node).__name__} cannot be written as C/C++")

    def binary(self, node, declared_type=None):

        op = node.operator
        left_type, right_type = self._type(node.left), self._type(node.right)

        def side(child, right=False, parent=op):
            return prec.operand(self.expr(child), child, parent, LANG, right=right)

        # There is no exponentiation operator in C or C++.
        if op == "Pow":
            call = f"pow({self.expr(node.left)}, {self.expr(node.right)})"
            result = declared_type or self._type(node)
            if result in ("int", "long") or (result is None and left_type in (None, "int") and right_type in (None, "int")):
                return f"({self.type_of(result or 'int')}) {call}"
            return call

        if op in ("FloorDiv", "FloorMod"):
            if "double" in (left_type, right_type):
                quotient = f"floor({side(node.left, parent='Div')} / {side(node.right, True, 'Div')})"
                if op == "FloorDiv":
                    return quotient
                return f"{side(node.left, parent='Sub')} - {side(node.right, parent='Mult')} * {quotient}"
            kind = "long" if "long" in (left_type, right_type) else "int"
            self.helpers.add(f"floor_{kind}")
            name = "py_floordiv" if op == "FloorDiv" else "py_floormod"
            return f"{name}{'_ll' if kind == 'long' else ''}({self.expr(node.left)}, {self.expr(node.right)})"

        if op == "Mod":
            # A floating-point remainder; % only accepts integers.
            return f"fmod({self.expr(node.left)}, {self.expr(node.right)})"

        if op == "Add" and self._type(node) == "String":
            return self.concatenate(node)

        if op not in ARITHMETIC:
            raise UnsupportedConstruct(f"operator {op} cannot be written as C/C++")

        left = side(node.left)
        right = side(node.right, right=True)

        if op == "Div" and self.source == "python" and left_type not in ("double",) \
                and right_type not in ("double",):
            left = f"(double) {prec.unary_operand(self.expr(node.left), node.left, LANG)}"

        return f"{left} {ARITHMETIC[op]} {right}"

    def concatenate(self, node):
        raise UnsupportedConstruct("string concatenation in C")

    def comparison(self, node):

        op = node.operator

        if op in ("In", "NotIn"):
            return self.membership(node)

        if op in ("Eq", "NotEq", "Lt", "Gt", "LtE", "GtE") and not self.cpp and (
            self._type(node.left) == "String" or self._type(node.right) == "String"
        ) and not (isinstance(node.left, Constant) and node.left.value is None
                   or isinstance(node.right, Constant) and node.right.value is None):
            # C compares char* by address; strcmp compares the text.
            return f"strcmp({self.expr(node.left)}, {self.expr(node.right)}) {COMPARISON[op]} 0"

        if op not in COMPARISON:
            raise UnsupportedConstruct(f"comparison {op} cannot be written as C/C++")

        if op in ("And", "Or"):
            left = self.condition_operand(node.left, op)
            right = self.condition_operand(node.right, op, True)
            return f"{left} {COMPARISON[op]} {right}"

        left = prec.operand(self.expr(node.left), node.left, op, LANG)
        right = prec.operand(self.expr(node.right), node.right, op, LANG, right=True)
        return f"{left} {COMPARISON[op]} {right}"

    def membership(self, node):
        raise UnsupportedConstruct("the in operator in C")

    def cast(self, node):

        inner = self.expr(node.value)
        source = self._type(node.value)

        # Parsing a string needs a conversion function, not a cast.
        if source == "String" or self._expr_type(node.value) in ("string", "char*"):
            if node.target_type in ("int", "long"):
                if self.cpp:
                    return f"stoi({inner})" if node.target_type == "int" else f"stoll({inner})"
                return f"atoi({inner})" if node.target_type == "int" else f"atoll({inner})"
            if node.target_type == "float":
                return f"stod({inner})" if self.cpp else f"atof({inner})"
            if node.target_type in ("str", "String"):
                return inner

        if node.target_type in ("str", "String"):
            return self.to_text(node.value)

        target = {"int": "int", "long": "long long", "float": "double", "double": "double",
                  "bool": "bool" if self.cpp else "int", "char": "char"}.get(node.target_type)
        if target is None:
            raise UnsupportedConstruct(f"cast to {node.target_type}")
        return f"({target}) {prec.unary_operand(inner, node.value, LANG)}"

    def to_text(self, node):
        raise UnsupportedConstruct("converting a value to a string in C")

    def call(self, node):

        user_functions = getattr(self, "user_functions", ())
        if library.is_user_call(node, user_functions):
            return f"{node.name}({', '.join(self.expr(a) for a in node.args)})"

        library_call = self.library_call(node)
        if library_call is not None:
            return library_call

        args = ", ".join(self.expr(a) for a in node.args)
        name = node.name

        if name in user_functions and self.cpp:
            # The program's own function of this name would hide the library's.
            return f"std::{name}({args})"

        if name == "range_array":
            raise UnsupportedConstruct("an array allocation outside a declaration")

        if name in ("max", "min") and len(node.args) == 2 and not self.cpp:
            # C has no generic max/min.
            left = prec.operand(self.expr(node.args[0]), node.args[0], "Gt", LANG)
            right = prec.operand(self.expr(node.args[1]), node.args[1], "Gt", LANG, right=True)
            symbol = ">" if name == "max" else "<"
            return f"({left} {symbol} {right} ? {left} : {right})"

        if name == "abs" and not self.cpp:
            kind = self._type(node.args[0]) if node.args else None
            name = {"double": "fabs", "long": "llabs"}.get(kind, "abs")

        return f"{name}({args})"

    def library_call(self, node):
        """The calls of core/library.py; None for any other name."""

        name = node.name
        args = [self.expr(a) for a in node.args]
        kind = self._type(node.args[0]) if node.args else None

        if name == "round_even":
            return f"(int) nearbyint({args[0]})"
        if name == "round_digits":
            self.helpers.add("lib_py_round")
            return f"_py_round({args[0]}, {args[1]})"
        if name == "round_half_up":
            self.helpers.add("lib_round_half_up")
            return f"_round_half_up({args[0]})"
        if name == "round_away":
            return f"round({args[0]})"
        if name in library.CHAR_TESTS and len(args) == 1 and kind != "char":
            # Python's str tests; the helper also accepts a single character.
            self.helpers.add("lib_tests")
            return f"_py_{name}({args[0]})"
        if name not in library.NEEDS_CONTAINERS:
            return None

        if not self.cpp:
            raise UnsupportedConstruct(f"{name.replace('_', ' ')} on a string or list in C")
        if isinstance(node.args[0], Constant) and isinstance(node.args[0].value, str):
            args[0] = f"string({args[0]})"
        if name == "slice":
            self.helpers.add("lib_slice")
            lower = "0" if isinstance(node.args[1], Constant) and node.args[1].value is None else args[1]
            upper = "_END" if isinstance(node.args[2], Constant) and node.args[2].value is None else args[2]
            return f"_slice({args[0]}, {lower}, {upper})"
        if name == "reversed_copy":
            self.helpers.add("lib_reversed")
            return f"_reversed({args[0]})"
        if name == "sorted_copy":
            if kind == "String":
                raise UnsupportedConstruct("sorted() over a string")
            self.helpers.add("lib_sorted")
            return f"_sorted({args[0]})"
        self.helpers.add("lib_join")
        return f"_join({args[0]}, {args[1]})"

    def _expr_type(self, node):
        """Best-effort static type, used only to pick a conversion form."""

        if isinstance(node, Identifier):
            return self.scope.get(node.name)
        if isinstance(node, Constant) and isinstance(node.value, str):
            return "string" if self.cpp else "char*"
        if isinstance(node, MethodCall) and node.method == "split":
            return "vector<string>"
        if isinstance(node, Input):
            return "string" if self.cpp else "char*"
        if isinstance(node, IndexAccess):
            container = self._expr_type(node.obj)
            if container and "string" in container:
                return "string" if self.cpp else "char*"
        return None

    def char_literal(self, value):
        escaped = {"'": "\\'", "\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\0"}.get(value, value)
        return f"'{escaped}'"

    def constant(self, value):
        if value is None:
            return "nullptr" if self.cpp else "NULL"
        if isinstance(value, bool):
            return ("true" if value else "false") if self.cpp else ("1" if value else "0")
        if isinstance(value, str):
            return self.string_literal(value)
        if isinstance(value, int) and not -2**31 <= value < 2**31:
            return f"{value}LL"
        return repr(value) if isinstance(value, float) else str(value)

    @staticmethod
    def string_literal(value):
        escaped = (value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                   .replace("\t", "\\t").replace("\r", "\\r"))
        return f'"{escaped}"'

    def method_call(self, node):
        obj = self.receiver(node.obj)
        args = ", ".join(self.expr(a) for a in node.args)

        if node.method == "size":
            if not self.cpp:
                if self._type(node.obj) == "String":
                    return f"(int) strlen({self.expr(node.obj)})"
                return f"{obj}_length"
            return f"(int) {obj}.size()"

        if self.cpp:
            # A user-defined object's methods mean what its class says.
            if self._type(node.obj) in self.class_names or isinstance(node.obj, SelfRef):
                return f"{obj}.{node.method}({args})" if not isinstance(node.obj, SelfRef) \
                    else f"this->{node.method}({args})"
            # Java collection calls have operator or member equivalents in C++.
            if node.method == "add" and (self._type(node.obj) or "").startswith("Set<"):
                return f"{obj}.insert({args})"
            if node.method in ("add", "append", "push_back"):
                return f"{obj}.push_back({args})"
            if node.method == "get" and len(node.args) == 1:
                return f"{obj}[{self.expr(node.args[0])}]"
            if node.method == "put" and len(node.args) == 2:
                return f"{obj}[{self.expr(node.args[0])}] = {self.expr(node.args[1])}"
            if node.method in ("containsKey", "contains"):
                return f"{obj}.count({args})"
            if node.method in ("isEmpty",):
                return f"{obj}.empty()"
            first = self.expr(node.args[0]) if node.args else ""
            if node.method == "replace" and len(node.args) == 2 and self._type(node.obj) == "String":
                self.helpers.add("lib_replace")
                return f"_replace_all({self.expr(node.obj)}, {first}, {self.expr(node.args[1])})"
            if node.method == "count" and len(node.args) == 1:
                self.helpers.add("lib_count")
                return f"_count({self.expr(node.obj)}, {first})"
            if node.method == "reverse" and not node.args:
                return f"reverse({obj}.begin(), {obj}.end())"
            if node.method == "pop" and len(node.args) <= 1:
                self.helpers.add("lib_pop")
                return f"_pop({self.expr(node.obj)}{', ' + first if node.args else ''})"
            if node.method == "insert" and len(node.args) == 2:
                return f"{obj}.insert({obj}.begin() + {first}, {self.expr(node.args[1])})"
            return f"{obj}.{node.method}({args})"

        raise UnsupportedConstruct(f"the method call .{node.method}() in C")

    def interpolation(self, node):
        raise NotImplementedError

    def format_string(self, node):
        raise UnsupportedConstruct("formatting a string outside a print statement")

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def block(self, statements, indent):
        """A nested scope: names declared inside are forgotten afterwards."""

        saved = dict(self.scope)
        try:
            return "".join(self.statement(s, indent) for s in statements)
        finally:
            self.scope = saved

    def statement(self, stmt, indent):

        tab = "    " * indent

        if stmt is None or isinstance(stmt, Pass):
            return ""

        if isinstance(stmt, Block):
            return f"{tab}{{\n{self.block(stmt.body, indent + 1)}{tab}}}\n"

        # Reading stdin is a statement in C and C++, not an expression.
        if isinstance(stmt, Variable) and isinstance(stmt.value, Input):
            declared = stmt.var_type if stmt.var_type not in (None, "auto") else stmt.value.value_type
            rendered = self.type_of(declared)
            already = self.scope.get(stmt.name)
            self.scope[stmt.name] = rendered
            prefix = "" if already else f"{tab}{rendered} {stmt.name};\n"
            return prefix + self.read_into(stmt.name, rendered, indent, stmt.value)

        if isinstance(stmt, Assignment) and isinstance(stmt.value, Input):
            target = self.expr(stmt.target)
            rendered = self.scope.get(target) or self.type_of(self._type(stmt.target) or stmt.value.value_type)
            return self.read_into(target, rendered, indent, stmt.value)

        if isinstance(stmt, Input):
            return self.read_statement(stmt, indent)

        if isinstance(stmt, Break):
            return f"{tab}break;\n"

        if isinstance(stmt, Continue):
            return f"{tab}continue;\n"

        if isinstance(stmt, Return):
            if stmt.value is None:
                return f"{tab}return;\n"
            return f"{tab}return {self.expr(stmt.value)};\n"

        if isinstance(stmt, Variable):
            return self.declaration(stmt, tab)

        if isinstance(stmt, Assignment):
            return f"{tab}{self.expr(stmt.target)} = {self.expr(stmt.value)};\n"

        if isinstance(stmt, AugAssign):
            return f"{tab}{self.aug_assign(stmt)};\n"

        if isinstance(stmt, IfStatement):
            code = f"{tab}if ({self.condition(stmt.condition)}) {{\n"
            code += self.block(stmt.body, indent + 1)
            if stmt.else_body:
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self.statement(stmt.else_body[0], indent).lstrip()
                    return code + f"{tab}}} else {nested}"
                code += f"{tab}}} else {{\n"
                code += self.block(stmt.else_body, indent + 1)
            return code + f"{tab}}}\n"

        if isinstance(stmt, WhileLoop):
            code = f"{tab}while ({self.condition(stmt.condition)}) {{\n"
            code += self.block(stmt.body, indent + 1)
            return code + f"{tab}}}\n"

        if isinstance(stmt, ForLoop):
            saved = dict(self.scope)
            try:
                return self.for_loop(stmt, indent)
            finally:
                self.scope = saved

        if isinstance(stmt, PrintStatement):
            return self.print_statement(stmt, indent)

        if isinstance(stmt, ListAppend):
            target = self.receiver(stmt.list_obj)
            if self.cpp:
                kind = self._type(stmt.list_obj) or ""
                if kind == "String":
                    return f"{tab}{target} += {self.expr(stmt.value)};\n"
                if kind.startswith("Set<"):
                    return f"{tab}{target}.insert({self.expr(stmt.value)});\n"
                return f"{tab}{target}.push_back({self.expr(stmt.value)});\n"
            raise UnsupportedConstruct("growing a list in C (arrays have a fixed size)")

        if isinstance(stmt, DictPut):
            return (
                f"{tab}{self.receiver(stmt.dictionary)}[{self.expr(stmt.key)}]"
                f" = {self.expr(stmt.value)};\n"
            )

        if isinstance(stmt, (FunctionCall, MethodCall, ObjectCreation)):
            return f"{tab}{self.expr(stmt)};\n"

        if isinstance(stmt, TryCatch):
            return self.try_catch(stmt, indent)

        raise UnsupportedConstruct(f"statement {type(stmt).__name__} cannot be written as C/C++")

    def declaration(self, stmt, tab):

        declared = self.scope.get(stmt.name)
        rendered = self.type_of(stmt.var_type)

        if stmt.value is None:
            if declared:
                return ""
            self.scope[stmt.name] = rendered
            return f"{tab}{rendered} {stmt.name};\n"

        value = self.expr(stmt.value)
        if declared:
            return f"{tab}{stmt.name} = {value};\n"
        self.scope[stmt.name] = rendered
        return f"{tab}{rendered} {stmt.name} = {value};\n"

    def aug_assign(self, stmt):

        op = stmt.operator
        target = self.expr(stmt.target)

        if op in ARITHMETIC and op != "Div":
            return f"{target} {ARITHMETIC[op]}= {self.expr(stmt.value)}"
        if op == "Div" and not (self.source == "python" and self._type(stmt.target) != "double"):
            return f"{target} /= {self.expr(stmt.value)}"

        # Helper-based operators have no compound form.
        combined = self.binary(BinaryOp(stmt.target, op, stmt.value), declared_type=self._type(stmt.target))
        return f"{target} = {combined}"

    def for_loop(self, stmt, indent):

        tab = "    " * indent

        if isinstance(stmt.iterable, RangeCall):
            args = stmt.iterable.args
            name = stmt.iterator
            start = self.expr(args[0]) if len(args) > 1 else "0"
            end = self.expr(args[1]) if len(args) > 1 else (self.expr(args[0]) if args else "0")
            self.scope[name] = "int"
            if len(args) < 3:
                header = f"int {name} = {start}; {name} < {end}; {name}++"
            else:
                step = args[2]
                if isinstance(step, Constant) and isinstance(step.value, int):
                    compare = "<" if step.value > 0 else ">"
                    update = f"{name} += {step.value}" if step.value > 0 else f"{name} -= {-step.value}"
                    header = f"int {name} = {start}; {name} {compare} {end}; {update}"
                else:
                    step_code = self.expr(step)
                    header = (f"int {name} = {start}; ({step_code}) > 0 ? {name} < {end} : "
                              f"{name} > {end}; {name} += {step_code}")
            code = f"{tab}for ({header}) {{\n"
        elif self.cpp:
            if (self._type(stmt.iterable) or "").startswith("Map<"):
                raise UnsupportedConstruct("iterating a map in C++ (std::map visits keys in sorted order)")
            if self.source == "python" and (self._type(stmt.iterable) or "").startswith("Set<"):
                raise UnsupportedConstruct("iterating a set in C++ (std::set visits elements in sorted order)")
            if self.source == "python" and self._type(stmt.iterable) == "String":
                # A Python string yields one-character strings, not chars.
                code = (f"{tab}for (char _c_{stmt.iterator} : {self.expr(stmt.iterable)}) {{\n"
                        f"{tab}    string {stmt.iterator}(1, _c_{stmt.iterator});\n")
            else:
                code = f"{tab}for (auto {stmt.iterator} : {self.expr(stmt.iterable)}) {{\n"
        else:
            if self._type(stmt.iterable) == "String":
                raise UnsupportedConstruct("iterating over the characters of a string in C")
            if not isinstance(stmt.iterable, Identifier):
                raise UnsupportedConstruct("iterating over an expression in C")
            name = self.expr(stmt.iterable)
            element = self.type_of(self._element_of_type(self._type(stmt.iterable)))
            index = f"_i_{stmt.iterator}"
            code = (
                f"{tab}for (int {index} = 0; {index} < {name}_length; {index}++) {{\n"
                f"{tab}    {element} {stmt.iterator} = {name}[{index}];\n"
            )

        for s in stmt.body:
            code += self.statement(s, indent + 1)

        return code + f"{tab}}}\n"

    @staticmethod
    def _element_of_type(type_name):
        if isinstance(type_name, str) and type_name.startswith(("List<", "Set<")):
            inner = type_name[type_name.index("<") + 1:-1]
            return {"Integer": "int", "Long": "long", "Double": "double", "Boolean": "boolean",
                    "Character": "char"}.get(inner, inner)
        return "int"

    def print_statement(self, stmt, indent):
        raise NotImplementedError

    def read_into(self, target, rendered_type, indent, node):
        raise NotImplementedError

    def read_expression(self, node):
        raise NotImplementedError

    def read_statement(self, node, indent):
        raise NotImplementedError

    def line_based(self, node):
        """Python's input() consumes a whole line, whatever is done with it."""
        return (self.source == "python" and node.value_type != "token") or node.prompt is not None

    def try_catch(self, stmt, indent):

        tab = "    " * indent

        if not self.cpp:
            # C has no exceptions; the handler could never run.
            raise UnsupportedConstruct("try/except in C")

        code = f"{tab}try {{\n"
        code += self.block(stmt.try_body, indent + 1)
        code += f"{tab}}} catch (const exception& {stmt.catch_var or 'e'}) {{\n"
        code += self.block(stmt.catch_body, indent + 1)
        return code + f"{tab}}}\n"

    # ------------------------------------------------------------
    # DECLARATIONS
    # ------------------------------------------------------------

    def render_class(self, cls):
        raise NotImplementedError

    def render_function(self, func, indent=0, owner=None):
        raise NotImplementedError
