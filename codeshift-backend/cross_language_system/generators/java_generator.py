from cross_language_system.core import library
from cross_language_system.core import naming
from cross_language_system.core import precedence as prec
from cross_language_system.core import printf_format
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.symbol_table import SymbolTable
from cross_language_system.core.type_mapper import TypeMapper

LANG = "java"

# Names a source may use freely that javac reserves.
RESERVED = {
    "_", "abstract", "assert", "boolean", "byte", "case", "catch", "char", "class",
    "const", "default", "do", "double", "enum", "extends", "final", "finally", "float",
    "goto", "implements", "import", "instanceof", "int", "interface", "long", "native",
    "new", "package", "private", "protected", "public", "short", "static", "strictfp",
    "super", "switch", "synchronized", "this", "throw", "throws", "transient", "void",
    "volatile", "var", "record", "yield", "null", "true", "false", "sc",
}


def java_name(name):
    return f"{name}_" if name in RESERVED else name

OPERATORS = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "TruncDiv": "/",
    "TruncMod": "%", "Mod": "%",
    "BitAnd": "&", "BitOr": "|", "BitXor": "^", "LShift": "<<", "RShift": ">>",
}

COMPARISONS = {
    "And": "&&", "Or": "||", "Eq": "==", "NotEq": "!=",
    "Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=",
    "Is": "==", "IsNot": "!=",
}

# cout prints a double the way printf's %g does; Java has no such conversion.
FMT_G = (
    "    static String fmtG(double x) {\n"
    "        // C++ stream output: %g with 6 significant digits.\n"
    "        if (Double.isNaN(x)) return \"nan\";\n"
    "        if (Double.isInfinite(x)) return x > 0 ? \"inf\" : \"-inf\";\n"
    "        if (x == 0) return (1 / x < 0) ? \"-0\" : \"0\";\n"
    "        String e = String.format(Locale.ROOT, \"%.5e\", x);\n"
    "        int exp = Integer.parseInt(e.substring(e.indexOf('e') + 1));\n"
    "        String text;\n"
    "        if (exp < -4 || exp >= 6) {\n"
    "            String mantissa = e.substring(0, e.indexOf('e'));\n"
    "            if (mantissa.contains(\".\")) mantissa = mantissa.replaceAll(\"0+$\", \"\").replaceAll(\"\\\\.$\", \"\");\n"
    "            text = mantissa + \"e\" + (exp < 0 ? \"-\" : \"+\") + (Math.abs(exp) < 10 ? \"0\" : \"\") + Math.abs(exp);\n"
    "        } else {\n"
    "            text = String.format(Locale.ROOT, \"%.\" + (5 - exp) + \"f\", x);\n"
    "            if (text.contains(\".\")) text = text.replaceAll(\"0+$\", \"\").replaceAll(\"\\\\.$\", \"\");\n"
    "        }\n"
    "        return text;\n"
    "    }\n\n"
)


class JavaGenerator:

    # Python exception names have no meaning to javac.
    EXCEPTIONS = {
        "ZeroDivisionError": "ArithmeticException",
        "ValueError": "IllegalArgumentException",
        "TypeError": "ClassCastException",
        "IndexError": "IndexOutOfBoundsException",
        "KeyError": "NoSuchElementException",
        "AttributeError": "NullPointerException",
        "IOError": "java.io.IOException",
        "OSError": "java.io.IOException",
        "Exception": "Exception",
    }

    def __init__(self, source_lang, target_lang):
        self.source_lang = source_lang.lower()
        self.target_lang = target_lang.lower()
        self.mapper = TypeMapper()
        self.symbol_table = SymbolTable()

    def _to_wrapper(self, primitive):

        wrapper_map = {
            "int": "Integer",
            "long": "Long",
            "double": "Double",
            "float": "Double",
            "boolean": "Boolean",
            "bool": "Boolean",
            "char": "Character"
        }

        return wrapper_map.get(primitive, primitive)

    @staticmethod
    def _escape(text):
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )

    def _literal(self, text):
        return f'"{self._escape(text)}"'

    # -------------------------------------------------
    # ENTRY POINT
    # -------------------------------------------------

    def generate(self, program):

        naming.rename_reserved(program, "java")
        uses_input = self._program_uses_input(program)
        self.helpers = set()
        self.function_returns = {}
        self.current_class = None
        self.class_names = {n.name for n in program.body if isinstance(n, Class)}
        self.user_functions = library.user_functions(program)

        members = ""
        function_names = []
        main_statements = []

        for node in program.body:

            if isinstance(node, Function):
                members += self._generate_node(node)
                function_names.append(node.name)

            elif isinstance(node, Class):
                members += self._generate_node(node)

            else:
                # Collect top-level statements to inject into main()
                main_statements.append(node)

        main = "    public static void main(String[] args) {\n"

        if not main_statements and function_names:
            # Only a zero-argument function can be invoked without inventing values.
            for node in program.body:
                if isinstance(node, Function) and len(node.params) == 0:
                    main += f"        {node.name}();\n"
                    break

        self.symbol_table = SymbolTable()
        fields = ""
        if self.source_lang == "python":
            for name, variable in library.module_globals(program).items():
                java_type = self._java_type(variable.var_type)
                fields += f"    static {java_type} {name};\n"
                self.symbol_table.register_variable(name, java_type)
        for stmt in main_statements:
            main += self._generate_statement(stmt, indent=2)

        main += "    }\n"

        code = "import java.util.*;\n\n"
        code += "public class Converted {\n"
        if uses_input:
            code += "    static Scanner sc = new Scanner(System.in);\n\n"
        if "fmtG" in self.helpers:
            code += FMT_G
        if "charAt" in self.helpers:
            code += (
                "    static char charAt(String text, int index) {\n"
                "        // A C string reads as '\\0' past its last character.\n"
                "        return index >= 0 && index < text.length() ? text.charAt(index) : '\\0';\n"
                "    }\n\n"
            )
        for name, helper in library.JAVA_HELPERS.items():
            if name in self.helpers:
                code += helper
        if fields:
            code += fields + "\n"
        code += members + main + "}\n"

        return code

    # -------------------------------------------------
    # NODE GENERATION
    # -------------------------------------------------

    def _generate_node(self, node):

        if isinstance(node, Class):
            return self._generate_class(node)

        if isinstance(node, Function):
            return self._generate_function(node)

        return ""

    # -------------------------------------------------
    # CLASS
    # -------------------------------------------------

    def _generate_class(self, cls):

        previous_class = self.current_class
        self.current_class = cls

        extends = f" extends {cls.base}" if cls.base else ""
        code = f"    public static class {cls.name}{extends} {{\n"

        for field in cls.fields:
            initializer = f" = {self._generate_expr(field.value)}" if field.value is not None else ""
            code += f"        private {self._java_type(field.field_type)} {field.name}{initializer};\n"

        if cls.fields:
            code += "\n"

        for method in cls.methods:
            code += self._generate_function(method, indent=2, owner=cls)

        code += "    }\n\n"
        self.current_class = previous_class
        return code

    # -------------------------------------------------
    # FUNCTION
    # -------------------------------------------------

    def _generate_function(self, func, indent=1, owner=None):

        tab = "    " * indent
        self.symbol_table = SymbolTable()

        params = []
        for p in func.params:
            param_type = self._java_type(func.param_types.get(p, "Object"))
            params.append(f"{param_type} {java_name(p)}")
            self.symbol_table.register_variable(java_name(p), param_type)

        if owner:
            for field in owner.fields:
                self.symbol_table.register_variable(field.name, self._java_type(field.field_type))

        signature = ", ".join(params)
        self.current_return_type = None if func.is_constructor else self._java_type(func.return_type)

        if func.is_constructor and owner:
            code = f"{tab}public {owner.name}({signature}) {{\n"
        else:
            return_type = self._java_type(func.return_type)
            self.function_returns[func.name] = return_type
            modifier = "public" if owner and not func.is_static else "public static"
            code = f"{tab}{modifier} {return_type} {func.name}({signature}) {{\n"

        for stmt in func.body:
            code += self._generate_statement(stmt, indent + 1)

        if func.name == "main" and self.source_lang in ("c", "c++") and self._java_type(func.return_type) == "int" \
                and not (func.body and isinstance(func.body[-1], Return)):
            # C's main returns 0 when it reaches its end; Java insists on a return.
            code += f"{tab}    return 0;\n"

        code += f"{tab}}}\n\n"

        # Java has no default arguments, so each one becomes an overload that
        # forwards to the full signature.
        if func.defaults and not func.is_constructor:
            required = [p for p in func.params if p not in func.defaults]
            optional = [p for p in func.params if p in func.defaults]

            for count in range(len(optional)):
                kept = required + optional[:count]
                signature = ", ".join(
                    f"{self._java_type(func.param_types.get(p, 'Object'))} {p}" for p in kept
                )
                forwarded = ", ".join(
                    kept + [self._generate_expr(func.defaults[p]) for p in optional[count:]]
                )
                modifier = "public" if owner else "public static"
                returns = "" if func.return_type == "void" else "return "
                code += (
                    f"{tab}{modifier} {self._java_type(func.return_type)} {func.name}({signature}) {{\n"
                    f"{tab}    {returns}{func.name}({forwarded});\n"
                    f"{tab}}}\n\n"
                )

        return code

    # -------------------------------------------------
    # TYPE RENDERING
    # -------------------------------------------------

    def _java_type(self, type_name):
        """Render a neutral IR type as Java."""

        if not type_name or type_name in ("auto", "Object", "object"):
            return "Object"

        if type_name == "void":
            return "void"

        direct = {
            "int": "int",
            "long": "long",
            "float": "double",
            "double": "double",
            "char": "char",
            "bool": "boolean",
            "boolean": "boolean",
            "str": "String",
            "String": "String",
        }

        if type_name in direct:
            return direct[type_name]

        if type_name.startswith(("List<", "Map<", "Set<")):
            return self._fix_java_generics(type_name)

        if type_name in getattr(self, "class_names", ()):
            return type_name

        mapped = self.mapper.map(type_name, self.source_lang, self.target_lang)
        return mapped or "Object"

    @staticmethod
    def _type(expr):
        return getattr(expr, "inferred_type", None)

    # -------------------------------------------------
    # STATEMENTS
    # -------------------------------------------------

    def _scoped(self, statements, indent):
        """A nested block: names declared inside go out of scope after it."""

        self.symbol_table.push()
        try:
            return "".join(self._generate_statement(s, indent) for s in statements)
        finally:
            self.symbol_table.pop()

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent

        if stmt is None or isinstance(stmt, Pass):
            return ""

        if isinstance(stmt, Block):
            return f"{tab}{{\n{self._scoped(stmt.body, indent + 1)}{tab}}}\n"

        if isinstance(stmt, Break):
            return f"{tab}break;\n"

        if isinstance(stmt, Continue):
            return f"{tab}continue;\n"

        if isinstance(stmt, Assignment):
            value = self._generate_expr(stmt.value)
            if self._c_truth_into_int(stmt.value, self._type(stmt.target)):
                value = f"({value} ? 1 : 0)"
            return f"{tab}{self._store(stmt.target, value)};\n"

        if isinstance(stmt, AugAssign):
            return f"{tab}{self._aug_assign(stmt)};\n"

        if isinstance(stmt, TryCatch):
            exception = self.EXCEPTIONS.get(stmt.exception_type, stmt.exception_type or "Exception")
            code = f"{tab}try {{\n"
            code += self._scoped(stmt.try_body, indent + 1)
            code += f"{tab}}} catch ({exception} {stmt.catch_var or 'e'}) {{\n"
            code += self._scoped(stmt.catch_body, indent + 1)
            code += f"{tab}}}\n"
            return code

        if isinstance(stmt, (FunctionCall, MethodCall, ObjectCreation)):
            return f"{tab}{self._generate_expr(stmt)};\n"

        if isinstance(stmt, Input):
            if stmt.value_type == "eol":
                return f"{tab}if (sc.hasNextLine()) sc.nextLine();\n"
            # A read whose value is discarded still consumes input.
            return f"{tab}{self._generate_expr(stmt)};\n"

        if isinstance(stmt, Variable):
            return self._declaration(stmt, tab)

        if isinstance(stmt, Return):
            if stmt.value is None:
                return f"{tab}return;\n"
            if self._c_truth_into_int(stmt.value, getattr(self, "current_return_type", None)):
                return f"{tab}return {self._generate_expr(stmt.value)} ? 1 : 0;\n"
            return f"{tab}return {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, IfStatement):

            code = f"{tab}if ({self._condition(stmt.condition)}) {{\n"
            code += self._scoped(stmt.body, indent + 1)

            if stmt.else_body:
                # A lone nested if is an elif in the source; keep it as else-if.
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self._generate_statement(stmt.else_body[0], indent).lstrip()
                    return code + f"{tab}}} else {nested}"

                code += f"{tab}}} else {{\n"
                code += self._scoped(stmt.else_body, indent + 1)

            code += f"{tab}}}\n"
            return code

        if isinstance(stmt, ForLoop):
            return self._for_loop(stmt, indent)

        if isinstance(stmt, DictPut):
            return f"{tab}{self._store(IndexAccess(stmt.dictionary, stmt.key), self._generate_expr(stmt.value))};\n"

        if isinstance(stmt, PrintStatement):
            return f"{tab}{self._print(stmt)}\n"

        if isinstance(stmt, WhileLoop):
            code = f"{tab}while ({self._condition(stmt.condition)}) {{\n"
            code += self._scoped(stmt.body, indent + 1)
            return code + f"{tab}}}\n"

        if isinstance(stmt, ListAppend):
            if self._type(stmt.list_obj) == "String":
                # C++'s s.push_back(c) on a string.
                return f"{tab}{self._generate_expr(stmt.list_obj)} += {self._generate_expr(stmt.value)};\n"
            return f"{tab}{self._receiver(stmt.list_obj)}.add({self._generate_expr(stmt.value)});\n"

        raise UnsupportedConstruct(f"statement {type(stmt).__name__} cannot be written as Java")

    def _declaration(self, stmt, tab):

        # -------- DICTIONARY HANDLING --------
        if isinstance(stmt.value, DictLiteral) and not self.symbol_table.lookup(stmt.name):

            declared = self._java_type(stmt.var_type)
            if not declared.startswith("Map<"):
                key_type = self._to_wrapper(self._java_type(self._type(stmt.value.keys[0]) or "Object")) \
                    if stmt.value.keys else "Object"
                val_type = self._to_wrapper(self._java_type(self._type(stmt.value.values[0]) or "Object")) \
                    if stmt.value.values else "Object"
                declared = f"Map<{key_type}, {val_type}>"

            self.symbol_table.register_variable(stmt.name, declared)
            # A Python dict iterates in insertion order, which LinkedHashMap keeps.
            kind = "LinkedHashMap" if self.source_lang == "python" else "HashMap"
            code = f"{tab}{declared} {stmt.name} = new {kind}<>();\n"
            for k, v in zip(stmt.value.keys, stmt.value.values):
                code += f"{tab}{stmt.name}.put({self._generate_expr(k)}, {self._generate_expr(v)});\n"
            return code

        java_type = self._java_type(stmt.var_type)
        name = java_name(stmt.name)
        existing_type = self.symbol_table.lookup(name)

        if stmt.value is None:
            if existing_type:
                return ""
            self.symbol_table.register_variable(name, java_type)
            return f"{tab}{java_type} {name};\n"

        value = self._value_for(stmt.value, java_type)

        if existing_type:
            return f"{tab}{name} = {value};\n"

        self.symbol_table.register_variable(name, java_type)
        return f"{tab}{java_type} {name} = {value};\n"

    def _value_for(self, value, java_type):
        """value rendered for a slot of java_type (char literals, list builders)."""

        if java_type == "char" and isinstance(value, Constant) and isinstance(value.value, str) \
                and len(value.value) == 1:
            return self._char(value.value)
        if self._c_truth_into_int(value, java_type):
            return f"({self._generate_expr(value)} ? 1 : 0)"
        return self._generate_expr(value)

    def _c_truth_into_int(self, value, slot_type):
        """A C comparison or ! yields the int 0 or 1, a Java one a boolean."""

        return self.source_lang in ("c", "c++") and self._type(value) == "boolean" \
            and slot_type in ("int", "long", "Integer", "Long")

    def _for_loop(self, stmt, indent):

        tab = "    " * indent
        self.symbol_table.push()

        try:
            if isinstance(stmt.iterable, RangeCall):

                args = stmt.iterable.args
                start = "0" if len(args) == 1 else self._generate_expr(args[0])
                end = self._generate_expr(args[0] if len(args) == 1 else args[1])
                name = java_name(stmt.iterator)
                self.symbol_table.register_variable(name, "int")

                if len(args) < 3:
                    header = f"int {name} = {start}; {name} < {end}; {name}++"
                else:
                    step = args[2]
                    if isinstance(step, Constant) and isinstance(step.value, int):
                        compare = "<" if step.value > 0 else ">"
                        update = f"{name} += {step.value}" if step.value > 0 else f"{name} -= {-step.value}"
                        header = f"int {name} = {start}; {name} {compare} {end}; {update}"
                    else:
                        step_code = self._generate_expr(step)
                        header = (f"int {name} = {start}; ({step_code}) > 0 ? {name} < {end} : "
                                  f"{name} > {end}; {name} += {step_code}")

                body = "".join(self._generate_statement(s, indent + 1) for s in stmt.body)
                return f"{tab}for ({header}) {{\n{body}{tab}}}\n"

            iterable_type = self._type(stmt.iterable) or self._infer_type(stmt.iterable)

            if iterable_type == "String":
                if self.source_lang == "python":
                    # Iterating a Python string yields one-character strings.
                    self.helpers.add("pyChars")
                    iterable = f"pyChars({self._generate_expr(stmt.iterable)})"
                    element_type = "String"
                else:
                    iterable = f"{self._receiver(stmt.iterable)}.toCharArray()"
                    element_type = "char"
            elif iterable_type.startswith("Map<"):
                iterable = f"{self._receiver(stmt.iterable)}.keySet()"
                element_type = self._fix_java_generics(iterable_type[4:-1].split(",")[0].strip())
            else:
                iterable = self._generate_expr(stmt.iterable)
                if iterable_type.startswith(("List<", "Set<")):
                    element_type = self._fix_java_generics(iterable_type[iterable_type.index("<") + 1:-1])
                else:
                    element_type = "Object"

            self.symbol_table.register_variable(java_name(stmt.iterator), element_type)
            body = "".join(self._generate_statement(s, indent + 1) for s in stmt.body)
            return f"{tab}for ({element_type} {java_name(stmt.iterator)} : {iterable}) {{\n{body}{tab}}}\n"
        finally:
            self.symbol_table.pop()

    def _store(self, target, value):
        """Assignment to a variable, field, list element or map entry."""

        if isinstance(target, IndexAccess):
            container = self._type(target.obj) or self.symbol_table.lookup(self._generate_expr(target.obj)) or ""
            method = "put" if container.startswith("Map<") else "set"
            index = self._generate_expr(target.index) if method == "put" else self._index(target.index)
            return f"{self._receiver(target.obj)}.{method}({index}, {value})"
        return f"{self._generate_expr(target)} = {value}"

    def _index(self, index):
        """A list or string position: Java requires an int there."""
        code = self._generate_expr(index)
        if self._type(index) == "long":
            return f"(int) {prec.unary_operand(code, index, LANG)}"
        return code

    def _aug_assign(self, stmt):

        op = stmt.operator
        combined = self._binary(BinaryOp(stmt.target, op, stmt.value), declared_type=self._type(stmt.target))

        if isinstance(stmt.target, IndexAccess) or op in ("FloorDiv", "FloorMod", "Pow"):
            return self._store(stmt.target, combined)

        if op not in OPERATORS:
            raise UnsupportedConstruct(f"augmented operator {op} cannot be written as Java")

        value = self._generate_expr(stmt.value)
        if op == "Div" and self._integral(self._type(stmt.target)):
            # Python's x /= y makes x a float; the annotator typed x double,
            # so reaching here means both really are integral in the source.
            pass
        return f"{self._generate_expr(stmt.target)} {OPERATORS[op]}= {value}"

    # -------------------------------------------------
    # OUTPUT
    # -------------------------------------------------

    def _print(self, stmt):

        args = list(stmt.args)
        end = stmt.end

        # printf / String.format with nothing else on the line.
        if len(args) == 1 and isinstance(args[0], FormatString):
            fmt = printf_format.to_java(args[0].fmt) + end.replace("%", "%%")
            values = "".join(", " + self._generate_expr(a) for a in args[0].args)
            return f"System.out.printf(Locale.ROOT, {self._literal(fmt)}{values});"

        # cout << ... << endl
        if end == "" and args and isinstance(args[-1], Constant) and args[-1].value == "\n":
            args = args[:-1]
            end = "\n"

        pieces = []
        for index, arg in enumerate(args):
            if index and stmt.sep:
                pieces.append((self._literal(stmt.sep), True, None))
            pieces.append((self._text(arg), self._is_text(arg), arg))

        if end not in ("", "\n"):
            pieces.append((self._literal(end), True, None))

        method = "println" if end == "\n" else "print"
        if not pieces:
            return f"System.out.{method}();" if method == "println" else 'System.out.print("");'
        return f"System.out.{method}({self._concat(pieces)});"

    def _concat(self, pieces):

        if len(pieces) == 1:
            return pieces[0][0]

        out = []
        for index, (code, is_text, node) in enumerate(pieces):
            if node is not None:
                code = prec.operand(code, node, "Add", LANG, right=index > 0)
            out.append(code)

        # Java's + only concatenates once a String is involved.
        prefix = "" if pieces[0][1] or pieces[1][1] else '"" + '
        return prefix + " + ".join(out)

    def _is_text(self, expr):
        return self._type(expr) in ("String", "char") or isinstance(expr, FormatString) or (
            isinstance(expr, Constant) and isinstance(expr.value, str)
        ) or self._shown_as_text(expr)

    def _shown_as_text(self, expr):
        kind = self._type(expr)
        if self.source_lang == "python" and (kind == "boolean" or (isinstance(expr, Constant) and expr.value is None)):
            return True
        return self.source_lang in ("c++", "cpp") and kind == "double"

    def _text(self, expr):
        """Java expression printing exactly what the source printed for expr."""

        code = self._generate_expr(expr)
        kind = self._type(expr)

        if self.source_lang == "python":
            if kind == "boolean":
                return f'({code} ? "True" : "False")'
            if isinstance(expr, Constant) and expr.value is None:
                return '"None"'
            if kind == "double":
                self.helpers.add("pyFloat")
                return f"pyFloat({code})"
            if kind and kind.startswith(("List<", "Set<", "Map<")):
                self.helpers.update(("pyStr", "pyFloat"))
                return f"pyStr({code})"

        if self.source_lang in ("c++", "cpp"):
            if kind == "boolean":
                return f"({code} ? 1 : 0)"
            if kind == "double":
                self.helpers.add("fmtG")
                return f"fmtG({code})"

        return code

    # -------------------------------------------------
    # EXPRESSIONS
    # -------------------------------------------------

    def _receiver(self, expr):
        return prec.postfix_operand(self._generate_expr(expr), expr, LANG)

    def _condition(self, expr):
        """A Java boolean for a value the source tests for truth.

        C tests ints against zero and Python tests any value for emptiness;
        Java accepts only booleans.
        """

        code = self._generate_expr(expr)
        kind = self._type(expr) or ""

        if kind in ("int", "long", "char", "double", "Integer", "Long", "Character", "Double"):
            return f"{prec.operand(code, expr, 'NotEq', LANG)} != 0"
        if self.source_lang == "python" and (kind == "String" or kind.startswith(("List<", "Set<", "Map<"))):
            return f"!{self._receiver(expr)}.isEmpty()"
        return code

    def _condition_operand(self, expr, parent, right=False):
        plain = self._generate_expr(expr)
        test = self._condition(expr)
        if test != plain:
            return f"({test})"  # a synthesized comparison is always grouped
        if parent == "Not":
            return prec.unary_operand(test, expr, LANG)
        return prec.operand(test, expr, parent, LANG, right=right)

    @staticmethod
    def _integral(kind):
        return kind in ("int", "long", "char", None, "Object")

    def _char(self, value):
        escaped = {"'": "\\'", "\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r", "\0": "\\0"}.get(value, value)
        return f"'{escaped}'"

    def _binary(self, expr, declared_type=None):

        op = expr.operator
        left_type, right_type = self._type(expr.left), self._type(expr.right)

        def side(node, right=False, parent=op):
            return prec.operand(self._generate_expr(node), node, parent, LANG, right=right)

        if op == "Pow":
            call = f"Math.pow({self._generate_expr(expr.left)}, {self._generate_expr(expr.right)})"
            result = declared_type or self._type(expr)
            if result in ("int", "long"):
                return f"({result}) {call}"
            return call

        if op in ("FloorDiv", "FloorMod"):
            left, right = self._generate_expr(expr.left), self._generate_expr(expr.right)
            if "double" in (left_type, right_type):
                quotient = f"Math.floor({side(expr.left, parent='Div')} / {side(expr.right, True, 'Div')})"
                if op == "FloorDiv":
                    return quotient
                return f"{side(expr.left, parent='Sub')} - {side(expr.right, parent='Mult')} * {quotient}"
            return f"Math.{'floorDiv' if op == 'FloorDiv' else 'floorMod'}({left}, {right})"

        if op not in OPERATORS:
            raise UnsupportedConstruct(f"operator {op} cannot be written as Java")

        if op == "Mult" and "String" in (left_type, right_type) and self.source_lang == "python":
            # Python's str * int; String.repeat gives "" for a count of zero.
            text, count = (expr.left, expr.right) if left_type == "String" else (expr.right, expr.left)
            return f"{self._receiver(text)}.repeat(Math.max(0, (int) ({self._generate_expr(count)})))"

        left = side(expr.left)
        right = side(expr.right, right=True)

        # Python's / is always float division; Java's / on two ints is not.
        if op == "Div" and self._integral(left_type) and self._integral(right_type) \
                and self.source_lang == "python":
            left = f"(double) {prec.unary_operand(self._generate_expr(expr.left), expr.left, LANG)}"

        if self.source_lang != "python" or op != "Add":
            pass

        return f"{left} {OPERATORS[op]} {right}"

    def _comparison(self, expr):

        op = expr.operator
        left_node, right_node = expr.left, expr.right
        left_type, right_type = self._type(left_node), self._type(right_node)

        if op in ("In", "NotIn"):
            container_type = right_type or ""
            method = "containsKey" if container_type.startswith("Map<") else "contains"
            needle = self._generate_expr(left_node)
            if container_type == "String" and left_type != "String":
                needle = f"String.valueOf({needle})"
            test = f"{self._receiver(right_node)}.{method}({needle})"
            return test if op == "In" else f"!{test}"

        if op in ("Eq", "NotEq"):
            # A char compared with a one-letter literal is a char comparison.
            for node, other_type in ((right_node, left_type), (left_node, right_type)):
                if other_type == "char" and isinstance(node, Constant) and isinstance(node.value, str) \
                        and len(node.value) == 1:
                    left = self._char(left_node.value) if node is left_node else self._comparison_side(left_node, op)
                    right = self._char(right_node.value) if node is right_node else self._comparison_side(right_node, op, True)
                    return f"{left} {COMPARISONS[op]} {right}"

            text_types = ("String",)
            if (left_type in text_types or right_type in text_types) and not (
                isinstance(left_node, Constant) and left_node.value is None
                or isinstance(right_node, Constant) and right_node.value is None
            ):
                # == on Strings compares references in Java.
                test = f"Objects.equals({self._generate_expr(left_node)}, {self._generate_expr(right_node)})"
                return test if op == "Eq" else f"!{test}"

        if op not in COMPARISONS:
            raise UnsupportedConstruct(f"comparison {op} cannot be written as Java")

        if op in ("And", "Or"):
            left = self._condition_operand(left_node, op)
            right = self._condition_operand(right_node, op, True)
            return f"{left} {COMPARISONS[op]} {right}"

        left = self._comparison_side(left_node, op)
        right = self._comparison_side(right_node, op, True)
        return f"{left} {COMPARISONS[op]} {right}"

    def _comparison_side(self, node, op, right=False):
        return prec.operand(self._generate_expr(node), node, op, LANG, right=right)

    def _cast(self, expr):

        target = expr.target_type
        source = self._type(expr.value)
        inner = self._generate_expr(expr.value)
        operand = prec.unary_operand(inner, expr.value, LANG)

        if target in ("int", "long"):
            if source == "String":
                parser = "Integer.parseInt" if target == "int" else "Long.parseLong"
                return f"{parser}({self._receiver(expr.value)}.trim())"
            return f"({target}) {operand}"

        if target in ("float", "double"):
            if source == "String":
                return f"Double.parseDouble({self._receiver(expr.value)}.trim())"
            return f"(double) {operand}"

        if target in ("str", "String"):
            if self.source_lang == "python" and source == "boolean":
                return f'({inner} ? "True" : "False")'
            if self.source_lang == "python" and (source == "double" or (source or "").startswith(("List<", "Set<", "Map<"))):
                return self._text(expr.value)
            return f"String.valueOf({inner})"

        if target == "char":
            return f"(char) {operand}"

        raise UnsupportedConstruct(f"cast to {target} cannot be written as Java")

    def _call(self, expr):

        args = ", ".join(self._generate_expr(a) for a in expr.args)

        if library.is_user_call(expr, getattr(self, "user_functions", ())):
            return f"{expr.name}({args})"

        if expr.name in ("min", "max") and len(expr.args) == 1:
            return f"Collections.{expr.name}({args})"

        if expr.name == "sum" and len(expr.args) == 1:
            element = self._type(expr) or "int"
            if element == "double":
                self.helpers.add("pySum")
                return f"pySum({args})"
            mapper = {"long": "mapToLong(Long::longValue)"}.get(element, "mapToInt(Integer::intValue)")
            return f"{self._receiver(expr.args[0])}.stream().{mapper}.sum()"

        if expr.name in ("sqrt", "pow", "abs", "max", "min") or expr.name in library.MATH_NAMES:
            return f"Math.{expr.name}({args})"

        library_call = self._library_call(expr)
        if library_call is not None:
            return library_call

        if expr.name in library.CHAR_TESTS and len(expr.args) == 1 and self._type(expr.args[0]) != "char":
            # Python's str tests, which also cover a one-character string.
            self.helpers.add("pyTests")
            return f"{library.JAVA_TESTS[expr.name]}({args})"

        character = {"isupper": "isUpperCase", "islower": "isLowerCase", "isdigit": "isDigit",
                     "isalpha": "isLetter", "isspace": "isWhitespace", "isalnum": "isLetterOrDigit",
                     "toupper": "toUpperCase", "tolower": "toLowerCase"}
        if expr.name in character and len(expr.args) == 1:
            return f"Character.{character[expr.name]}({args})"

        if expr.name == "range_array":
            if len(expr.args) != 1:
                raise UnsupportedConstruct("multi-dimensional arrays in Java output")
            default = {"double": "0.0", "boolean": "false", "char": "'\\0'", "long": "0L",
                       "String": "null"}.get(getattr(expr, "element_type", "int"), "0")
            if getattr(expr, "fill", None) is not None:
                default = self._generate_expr(expr.fill)
            return f"new ArrayList<>(Collections.nCopies({args}, {default}))"

        return f"{expr.name}({args})"

    def _library_call(self, expr):
        """The calls of core/library.py; None for any other name."""

        name = expr.name
        args = [self._generate_expr(a) for a in expr.args]
        kind = self._type(expr.args[0]) if expr.args else None

        if name == "round_even":
            return f"(int) Math.rint({args[0]})"
        if name == "round_digits":
            self.helpers.add("pyRound")
            return f"pyRound({args[0]}, {args[1]})"
        if name == "round_half_up":
            return f"Math.round({args[0]})"
        if name == "round_away":
            self.helpers.add("cRound")
            return f"cRound({args[0]})"
        if name == "slice":
            self.helpers.add("pySlice")
            lower = "0" if isinstance(expr.args[1], Constant) and expr.args[1].value is None else args[1]
            upper = "Integer.MAX_VALUE" if isinstance(expr.args[2], Constant) and expr.args[2].value is None \
                else args[2]
            return f"pySlice({args[0]}, {lower}, {upper})"
        if name == "reversed_copy":
            if kind == "String":
                return f"new StringBuilder({args[0]}).reverse().toString()"
            self.helpers.add("pyReversed")
            return f"pyReversed({args[0]})"
        if name == "sorted_copy":
            if kind == "String":
                raise UnsupportedConstruct("sorted() over a string")
            self.helpers.add("pySorted")
            return f"pySorted({args[0]})"
        if name == "str_join":
            return f"String.join({args[0]}, {args[1]})"
        return None

    def _generate_expr(self, expr):

        if expr is None:
            return "null"

        if isinstance(expr, SelfRef):
            return "this"

        if isinstance(expr, AttributeAccess):
            return f"{self._receiver(expr.obj)}.{expr.attribute}"

        if isinstance(expr, UnaryOp):
            op_map = {"USub": "-", "UAdd": "+", "Not": "!", "Invert": "~"}
            if expr.operator not in op_map:
                raise UnsupportedConstruct(f"unary operator {expr.operator}")
            if expr.operator == "Not":
                return f"!{self._condition_operand(expr.operand, 'Not')}"
            operand = prec.unary_operand(self._generate_expr(expr.operand), expr.operand, LANG)
            return f"{op_map[expr.operator]}{operand}"

        if isinstance(expr, TernaryOp):
            condition = self._condition(expr.condition)
            if condition != self._generate_expr(expr.condition):
                condition = f"({condition})"
            else:
                condition = prec.ternary_part(condition, expr.condition)
            return (
                f"{condition} ? "
                f"{prec.ternary_part(self._generate_expr(expr.if_true), expr.if_true)} : "
                f"{self._generate_expr(expr.if_false)}"
            )

        if isinstance(expr, StringInterpolation):
            parts = []
            for part in expr.parts:
                if isinstance(part, Constant) and isinstance(part.value, str):
                    if part.value:
                        parts.append(self._literal(part.value))
                else:
                    parts.append(prec.operand(self._text(part), part, "Add", LANG, right=True))
            if not parts:
                return '""'
            if not (expr.parts and isinstance(expr.parts[0], Constant) and isinstance(expr.parts[0].value, str)
                    and expr.parts[0].value):
                parts.insert(0, '""')
            return " + ".join(parts)

        if isinstance(expr, FormatString):
            fmt = printf_format.to_java(expr.fmt)
            values = "".join(", " + self._generate_expr(a) for a in expr.args)
            return f"String.format(Locale.ROOT, {self._literal(fmt)}{values})"

        if isinstance(expr, IndexAccess):
            if getattr(expr, "c_string", False):
                self.helpers.add("charAt")
                return f"charAt({self._generate_expr(expr.obj)}, {self._generate_expr(expr.index)})"
            container_type = self._type(expr.obj) or self.symbol_table.lookup(self._generate_expr(expr.obj)) or ""
            index = self._generate_expr(expr.index) if container_type.startswith("Map<") else self._index(expr.index)
            if container_type == "String":
                char = f"{self._receiver(expr.obj)}.charAt({index})"
                # Python has no char type: indexing a string gives a string.
                return f"String.valueOf({char})" if self.source_lang == "python" else char
            return f"{self._receiver(expr.obj)}.get({index})"

        if isinstance(expr, TypeCast):
            return self._cast(expr)

        if isinstance(expr, Constant):

            if expr.value is None:
                return "null"

            if isinstance(expr.value, bool):
                return str(expr.value).lower()

            if isinstance(expr.value, str):
                if getattr(expr, "is_char", False) and len(expr.value) == 1:
                    return self._char(expr.value)
                return self._literal(expr.value)

            if isinstance(expr.value, int) and not -2**31 <= expr.value < 2**31:
                return f"{expr.value}L"

            return repr(expr.value) if isinstance(expr.value, float) else str(expr.value)

        if isinstance(expr, Identifier):
            return java_name(expr.name)

        if isinstance(expr, BinaryOp):
            return self._binary(expr)

        if isinstance(expr, BooleanOp):
            return self._comparison(expr)

        if isinstance(expr, ArrayLiteral):

            if not expr.elements:
                return "new ArrayList<>()"

            kinds = {self._type(e) for e in expr.elements}
            widest = next((k for k in ("double", "long") if k in kinds and kinds <= {"int", "long", "double"}), None)
            if widest:
                # Arrays.asList(1, 2L) has no single element type; widen as Python's numbers would.
                cast = f"({widest}) "
                elements = ", ".join(cast + prec.unary_operand(self._generate_expr(e), e, LANG)
                                     if self._type(e) != widest else self._generate_expr(e) for e in expr.elements)
                element_type = self._to_wrapper(widest)
            else:
                elements = ", ".join(self._generate_expr(e) for e in expr.elements)
                element_type = self._to_wrapper(self._java_type(self._type(expr.elements[0]) or "Object"))
            return f"new ArrayList<{element_type}>(Arrays.asList({elements}))"

        if isinstance(expr, Input):
            if self.source_lang == "python" and expr.value_type in ("int", "long", "double"):
                # int(input()) parses a whole line, not the next word.
                parser = {"int": "Integer.parseInt", "long": "Long.parseLong",
                          "double": "Double.parseDouble"}[expr.value_type]
                return f"{parser}(sc.nextLine().trim())"
            return {
                "int": "sc.nextInt()",
                "long": "sc.nextLong()",
                "double": "sc.nextDouble()",
                "token": "sc.next()",
                "char": "sc.next().charAt(0)",
            }.get(expr.value_type, "sc.nextLine()")

        if isinstance(expr, FunctionCall):
            return self._call(expr)

        if isinstance(expr, ObjectCreation):
            args = ", ".join(self._generate_expr(a) for a in (expr.arguments or []))
            return f"new {expr.class_name}({args})"

        if isinstance(expr, SetLiteral):

            elements = ", ".join(self._generate_expr(e) for e in expr.elements)

            if not expr.elements:
                return "new HashSet<>()"

            return f"new HashSet<>(Arrays.asList({elements}))"

        if isinstance(expr, MethodCall):

            method_map = {
                # list methods
                "append": "add",
                "remove": "remove",
                "pop": "remove",
                "clear": "clear",
                "size": "size",

                # dict methods
                "keys": "keySet",
                "values": "values",
                "items": "entrySet",

                # set methods
                "add": "add",
                "discard": "remove",

                # string methods
                "upper": "toUpperCase",
                "lower": "toLowerCase",
                "strip": "trim",
                "startswith": "startsWith",
                "endswith": "endsWith",
                "find": "indexOf",
                "replace": "replace",
            }

            java_method = method_map.get(expr.method, expr.method)

            args = ", ".join(self._generate_expr(a) for a in expr.args)

            # A user-defined object's methods mean what its class says.
            if isinstance(expr.obj, SelfRef) or self._type(expr.obj) in self.class_names:
                return f"{self._receiver(expr.obj)}.{expr.method}({args})"

            # len() lowers to size(), but a Java String measures with length().
            if expr.method == "size" and (self._type(expr.obj) or self._infer_type(expr.obj)) == "String":
                return f"{self._receiver(expr.obj)}.length()"

            # Python's bare split() tokenises on any whitespace; wrapping the
            # resulting String[] keeps it indexable like every other list.
            if expr.method == "split" and not expr.args:
                return (
                    f'Arrays.asList({self._receiver(expr.obj)}'
                    f'.trim().split("\\\\s+"))'
                )

            if expr.method == "split" and len(expr.args) == 1 and self.source_lang == "python":
                # Python splits on the literal text and keeps trailing empty fields.
                return (f"new ArrayList<>(Arrays.asList({self._receiver(expr.obj)}.split("
                        f"java.util.regex.Pattern.quote({args}), -1)))")

            if expr.method == "remove" and expr.args:

                arg = self._generate_expr(expr.args[0])

                # Force wrapper for list removal
                return f"{self._receiver(expr.obj)}.remove(Integer.valueOf({arg}))"

            if expr.method == "sort" and not expr.args:
                return f"Collections.sort({self._generate_expr(expr.obj)})"

            receiver = self._receiver(expr.obj)
            obj_type = self._type(expr.obj) or ""
            if expr.method == "pop" and len(expr.args) <= 1:
                if not expr.args:
                    return f"{receiver}.remove({receiver}.size() - 1)"
                return f"{receiver}.remove((int) ({args}))"
            if expr.method == "count" and len(expr.args) == 1:
                if obj_type == "String":
                    self.helpers.add("pyCount")
                    return f"pyCount({self._generate_expr(expr.obj)}, String.valueOf({args}))"
                return f"Collections.frequency({self._generate_expr(expr.obj)}, {args})"
            if expr.method == "reverse" and not expr.args:
                return f"Collections.reverse({self._generate_expr(expr.obj)})"
            if expr.method == "insert" and len(expr.args) == 2:
                return f"{receiver}.add({self._generate_expr(expr.args[0])}, {self._generate_expr(expr.args[1])})"
            if expr.method == "index" and len(expr.args) == 1:
                return f"{receiver}.indexOf({args})"
            if expr.method == "clear" and not expr.args and obj_type == "String":
                # Java strings are immutable: C++'s s.clear() rebinds the name.
                return f'{self._generate_expr(expr.obj)} = ""'

            return f"{self._receiver(expr.obj)}.{java_method}({args})"

        raise UnsupportedConstruct(f"expression {type(expr).__name__} cannot be written as Java")

    # -------------------------------------------------
    # SIMPLE TYPE INFERENCE
    # -------------------------------------------------

    def _infer_type(self, value):

        if isinstance(value, FunctionCall):
            return self.function_returns.get(value.name, "Object")

        if isinstance(value, MethodCall):
            return "int" if value.method == "size" else "Object"

        if isinstance(value, UnaryOp):
            return "boolean" if value.operator == "Not" else self._infer_type(value.operand)

        if isinstance(value, AttributeAccess):
            current = self.current_class
            if current:
                for field in current.fields:
                    if field.name == value.attribute:
                        return self._java_type(field.field_type)
            return "Object"

        if isinstance(value, Constant):

            if isinstance(value.value, bool):
                return "boolean"

            if isinstance(value.value, int):
                return "int"

            if isinstance(value.value, float):
                return "double"

            if isinstance(value.value, str):
                return "String"

        if isinstance(value, ArrayLiteral):

            if not value.elements:
                return "List<Object>"

            return f"List<{self._to_wrapper(self._infer_type(value.elements[0]))}>"

        if isinstance(value, Identifier):
            var_type = self.symbol_table.lookup(value.name)
            if var_type:
                return var_type

        if isinstance(value, BinaryOp):
            left_type = self._infer_type(value.left)
            right_type = self._infer_type(value.right)

            if left_type == "double" or right_type == "double":
                return "double"

            return "int"

        return "Object"

    def _program_uses_input(self, program):

        def check_node(node):

            if isinstance(node, Input):
                return True

            if hasattr(node, "__dict__"):
                for value in node.__dict__.values():

                    if isinstance(value, list):
                        for item in value:
                            if check_node(item):
                                return True

                    else:
                        if check_node(value):
                            return True

            return False

        for node in program.body:
            if check_node(node):
                return True

        return False

    def _fix_java_generics(self, type_str):

        replacements = {
            "<int>": "<Integer>",
            "<long>": "<Long>",
            "<float>": "<Double>",
            "<double>": "<Double>",
            "<bool>": "<Boolean>",
            "<boolean>": "<Boolean>",
            "<char>": "<Character>",
            "<int,": "<Integer,",
            "<float,": "<Double,",
            "<bool,": "<Boolean,",
            ", int>": ", Integer>",
            ", double>": ", Double>",
        }

        for k, v in replacements.items():
            type_str = type_str.replace(k, v)

        return type_str
