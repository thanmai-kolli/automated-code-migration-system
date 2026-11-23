from cross_language_system.core import precedence as prec
from cross_language_system.core import printf_format
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.symbol_table import SymbolTable

LANG = "python"

OPERATORS = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
    "FloorDiv": "//", "FloorMod": "%", "Mod": "%", "Pow": "**",
    "BitAnd": "&", "BitOr": "|", "BitXor": "^",
    "LShift": "<<", "RShift": ">>",
}

COMPARISONS = {
    "And": "and", "Or": "or", "Eq": "==", "NotEq": "!=",
    "Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=",
    "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in",
}

# C and Java integer arithmetic, which Python's // and % do not reproduce for
# negative operands (-7 / 2 is -3 in C but -7 // 2 is -4 in Python).
HELPERS = {
    "_tdiv": (
        "def _tdiv(a, b):\n"
        "    # C/Java integer division truncates toward zero.\n"
        "    q = abs(a) // abs(b)\n"
        "    return q if (a < 0) == (b < 0) else -q\n"
    ),
    "_tmod": (
        "def _tmod(a, b):\n"
        "    # C/Java remainder takes the sign of the dividend.\n"
        "    return a - b * _tdiv(a, b)\n"
    ),
    "_char_at": (
        "def _char_at(text, index):\n"
        "    # A C string reads as '\\0' past its last character.\n"
        "    return text[index] if 0 <= index < len(text) else '\\0'\n"
    ),
}

ELEMENT_DEFAULTS = {"double": "0.0", "float": "0.0", "boolean": "False", "bool": "False",
                    "String": "None", "char": "'\\x00'"}

# scanf, cin and Scanner read words, single characters and rest-of-line from
# one shared position in stdin; input() alone cannot mix those faithfully.
STREAM_READER = (
    "_input = sys.stdin.read()\n"
    "_position = 0\n\n\n"
    "def _skip_space():\n"
    "    global _position\n"
    "    while _position < len(_input) and _input[_position].isspace():\n"
    "        _position += 1\n\n\n"
    "def _read_token():\n"
    "    global _position\n"
    "    _skip_space()\n"
    "    start = _position\n"
    "    while _position < len(_input) and not _input[_position].isspace():\n"
    "        _position += 1\n"
    "    if start == _position:\n"
    "        raise EOFError('no more input')\n"
    "    return _input[start:_position]\n\n\n"
    "def _read_char():\n"
    "    global _position\n"
    "    _skip_space()\n"
    "    if _position >= len(_input):\n"
    "        raise EOFError('no more input')\n"
    "    _position += 1\n"
    "    return _input[_position - 1]\n\n\n"
    "def _read_line():\n"
    "    global _position\n"
    "    if _position >= len(_input):\n"
    "        raise EOFError('no more input')\n"
    "    end = _input.find('\\n', _position)\n"
    "    end = len(_input) if end < 0 else end\n"
    "    line = _input[_position:end]\n"
    "    _position = end + 1\n"
    "    return line.rstrip('\\r')\n\n\n"
    "def _read_int():\n"
    "    return int(_read_token())\n\n\n"
    "def _read_float():\n"
    "    return float(_read_token())\n\n"
)

# C's <ctype.h> tests are string methods in Python.
CHARACTER_METHODS = {"isupper": "isupper", "islower": "islower", "isdigit": "isdigit",
                     "isalpha": "isalpha", "isspace": "isspace", "isalnum": "isalnum",
                     "toupper": "upper", "tolower": "lower"}


class PythonGenerator:

    def __init__(self, source_lang, target_lang):
        self.source_lang = (source_lang or "").lower()
        self.target_lang = target_lang
        self.exception_map = {
            "ArithmeticException": "ZeroDivisionError",
            "NullPointerException": "AttributeError",
            "IndexOutOfBoundsException": "IndexError"
        }

    def generate(self, program):

        self.symbol_table = SymbolTable()
        self.uses_tokens = False
        self.uses_math = False
        self.helpers = set()
        self.current_class = None
        self.in_static = True
        self.class_names = {n.name for n in program.body if isinstance(n, Class)}

        blocks = []
        main_statements = []
        entry_class = None
        entry_function = None

        for node in program.body:

            if isinstance(node, Class):
                blocks.append(self._generate_class(node))
                if any(m.name == "main" for m in node.methods):
                    entry_class = node.name

            elif isinstance(node, Function):
                blocks.append(self._generate_function(node))
                if node.name == "main":
                    entry_function = node

            else:
                main_statements.append(node)

        code = "\n".join(b for b in blocks if b.strip())

        if main_statements:
            body = "".join(self._generate_statement(s, 1) for s in main_statements)
            code += "\n\nif __name__ == '__main__':\n" + (body or "    pass\n")

        elif entry_function is not None:
            # A C-family source keeps its entry point as a plain main().
            args = ", ".join("None" for _ in entry_function.params)
            code += f"\n\nif __name__ == '__main__':\n    main({args})\n"

        elif entry_class:
            code += f"\n\nif __name__ == '__main__':\n    {entry_class}.main([])\n"

        code = code or "pass\n"

        # Prepended last: only now is it known what the body needed.
        prelude = ""
        if self.uses_math:
            prelude += "import math\n"
        if self.uses_tokens:
            prelude += "import sys\n"
        if prelude:
            prelude += "\n"
        if self.uses_tokens:
            prelude += STREAM_READER
        if "_tmod" in self.helpers:
            self.helpers.add("_tdiv")
        for name in ("_tdiv", "_tmod", "_char_at"):
            if name in self.helpers:
                prelude += HELPERS[name] + "\n"
        if prelude:
            code = prelude + "\n" + code

        return code

    # ------------------------------------------------------------
    # DECLARATIONS
    # ------------------------------------------------------------

    def _generate_class(self, cls):

        previous = self.current_class
        self.current_class = cls

        header = f"class {cls.name}({cls.base}):\n" if cls.base else f"class {cls.name}:\n"
        code = header

        if not cls.methods:
            # Fields alone still need a constructor to be meaningful.
            if cls.fields:
                code += "    def __init__(self):\n"
                for field in cls.fields:
                    default = self._generate_expr(field.value) if field.value else self._default_for(field.field_type)
                    code += f"        self.{field.name} = {default}\n"
                self.current_class = previous
                return code + "\n"
            self.current_class = previous
            return code + "    pass\n\n"

        for method in cls.methods:
            code += self._generate_function(method, indent=1, owner=cls)

        self.current_class = previous
        return code

    def _default_for(self, field_type):
        return {
            "int": "0",
            "long": "0",
            "double": "0.0",
            "float": "0.0",
            "boolean": "False",
            "bool": "False",
            "String": '""',
            "str": '""',
        }.get(field_type, "None")

    def _generate_function(self, func, indent=0, owner=None):

        tab = "    " * indent
        name = "__init__" if func.is_constructor else func.name

        if owner and not func.is_static:
            params = ", ".join(["self"] + list(func.params))
        else:
            params = ", ".join(func.params)

        code = ""
        if owner and func.is_static and not func.is_constructor:
            code += f"{tab}@staticmethod\n"

        code += f"{tab}def {name}({params}):\n"

        previous_static = self.in_static
        self.in_static = not owner or (func.is_static and not func.is_constructor)
        body = "".join(self._generate_statement(s, indent + 1) for s in func.body)
        self.in_static = previous_static

        if not body.strip():
            body = f"{tab}    pass\n"

        return code + body + "\n"

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def _body(self, statements, indent):
        code = "".join(self._generate_statement(s, indent) for s in statements)
        return code or f"{'    ' * indent}pass\n"

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent

        if stmt is None or isinstance(stmt, Pass):
            return f"{tab}pass\n"

        if isinstance(stmt, Block):
            # Python has no block scope; the statements simply run in place.
            return "".join(self._generate_statement(s, indent) for s in stmt.body)

        if isinstance(stmt, Assignment):
            return f"{tab}{self._generate_expr(stmt.target)} = {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, AugAssign):
            return tab + self._aug_assign(stmt) + "\n"

        if isinstance(stmt, PrintStatement):
            return f"{tab}{self._print(stmt)}\n"

        if isinstance(stmt, ListAppend):
            return f"{tab}{self._receiver(stmt.list_obj)}.append({self._generate_expr(stmt.value)})\n"

        if isinstance(stmt, DictPut):
            return (
                f"{tab}{self._receiver(stmt.dictionary)}"
                f"[{self._generate_expr(stmt.key)}] = {self._generate_expr(stmt.value)}\n"
            )

        if isinstance(stmt, Field):
            return ""

        if isinstance(stmt, Variable):

            # Skip Scanner object creation
            if isinstance(stmt.value, ObjectCreation) and stmt.value.class_name == "Scanner":
                return ""

            # A bare C-style declaration carries no value to assign.
            if stmt.value is None:
                return ""

            return f"{tab}{stmt.name} = {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, Return):
            if stmt.value is None:
                return f"{tab}return\n"
            return f"{tab}return {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, IfStatement):
            code = f"{tab}if {self._generate_expr(stmt.condition)}:\n"
            code += self._body(stmt.body, indent + 1)
            if stmt.else_body:
                # A lone nested if came from an elif; keep it flat.
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self._generate_statement(stmt.else_body[0], indent)
                    return code + f"{tab}el" + nested.lstrip()
                code += f"{tab}else:\n"
                code += self._body(stmt.else_body, indent + 1)
            return code

        if isinstance(stmt, ForLoop):

            # Detect pattern: array input loop
            if (
                isinstance(stmt.iterable, FunctionCall)
                and stmt.iterable.name == "range"
                and len(stmt.body) == 1
                and isinstance(stmt.body[0], MethodCall)
                and stmt.body[0].method == "set_index"
            ):
                array_name = stmt.body[0].obj
                return f"{tab}{array_name} = list(map(int, input().split()))\n"

            code = f"{tab}for {stmt.iterator} in {self._generate_expr(stmt.iterable)}:\n"
            return code + self._body(stmt.body, indent + 1)

        if isinstance(stmt, TryCatch):

            exception = self.exception_map.get(stmt.exception_type, "Exception")
            code = f"{tab}try:\n"
            code += self._body(stmt.try_body, indent + 1)
            binding = f" as {stmt.catch_var}" if stmt.catch_var else ""
            code += f"{tab}except {exception}{binding}:\n"
            code += self._body(stmt.catch_body, indent + 1)
            return code

        if isinstance(stmt, WhileLoop):
            code = f"{tab}while {self._generate_expr(stmt.condition)}:\n"
            return code + self._body(stmt.body, indent + 1)

        if isinstance(stmt, Break):
            return f"{tab}break\n"

        if isinstance(stmt, Continue):
            return f"{tab}continue\n"

        if isinstance(stmt, FunctionCall):
            return f"{tab}{self._generate_expr(stmt)}\n"

        if isinstance(stmt, SwitchStatement):

            code = ""

            for i, case in enumerate(stmt.cases):

                if case.value is not None:
                    condition = f"{self._generate_expr(stmt.variable)} == {self._generate_expr(case.value)}"
                    code += f"{tab}{'if' if i == 0 else 'elif'} {condition}:\n"
                else:
                    code += f"{tab}else:\n"

                code += self._body(case.body, indent + 1)

            return code

        if isinstance(stmt, MethodCall):
            return f"{tab}{self._generate_expr(stmt)}\n"

        if isinstance(stmt, (Input, Identifier, Constant, BinaryOp, BooleanOp, UnaryOp,
                             TernaryOp, IndexAccess, AttributeAccess, ObjectCreation, TypeCast)):
            # An expression evaluated for its side effects, e.g. a bare input().
            return f"{tab}{self._generate_expr(stmt)}\n"

        raise UnsupportedConstruct(f"statement {type(stmt).__name__} cannot be written as Python")

    def _aug_assign(self, stmt):

        target = self._generate_expr(stmt.target)
        value = self._generate_expr(stmt.value)
        op = stmt.operator

        if op in ("TruncDiv", "TruncMod") or (op == "Mod" and self.source_lang != "python"):
            # No augmented form exists for a helper call.
            call = self._binary(BinaryOp(stmt.target, op, stmt.value))
            return f"{target} = {call}"

        if op == "Add" and self._type(stmt.target) == "String" and self._type(stmt.value) != "String":
            value = self._as_text(stmt.value)

        if op not in OPERATORS:
            raise UnsupportedConstruct(f"augmented operator {op} cannot be written as Python")
        return f"{target} {OPERATORS[op]}= {value}"

    # ------------------------------------------------------------
    # OUTPUT
    # ------------------------------------------------------------

    def _print(self, stmt):

        args = list(stmt.args)
        end = stmt.end

        # printf("...\n") and cout << ... << endl both end in a newline that
        # Python's print supplies by itself.
        if end == "" and args:
            last = args[-1]
            if isinstance(last, FormatString) and last.fmt.endswith("\n"):
                args[-1] = FormatString(last.fmt[:-1], last.args)
                end = "\n"
            elif isinstance(last, Constant) and isinstance(last.value, str) and last.value.endswith("\n"):
                if last.value == "\n" and len(args) > 1:
                    args = args[:-1]
                else:
                    args[-1] = Constant(last.value[:-1])
                end = "\n"

        parts = [self._as_printed(a) for a in args]
        if len(parts) > 1 and stmt.sep != " ":
            parts.append(f"sep={stmt.sep!r}")
        if end != "\n":
            parts.append(f"end={end!r}")
        return f"print({', '.join(parts)})"

    def _as_printed(self, expr):
        """Python expression that prints exactly as the source printed expr."""

        code = self._generate_expr(expr)
        kind = self._type(expr)

        if self.source_lang == "java" and kind == "boolean":
            return f"str({code}).lower()"

        if self.source_lang in ("c++", "cpp"):
            # cout shows a bool as 1/0 and a double like printf's %g.
            if kind == "boolean":
                return f"int({code})"
            if kind == "double":
                return f"'%g' % {prec.operand(code, expr, 'Mod', LANG, right=True)}"

        return code

    def _as_text(self, expr):
        """str(expr) the way the source language would concatenate it."""

        code = self._generate_expr(expr)
        kind = self._type(expr)
        if kind in ("String", "char"):
            return prec.operand(code, expr, "Add", LANG, right=True)
        if self.source_lang == "java" and kind == "boolean":
            return f"str({code}).lower()"
        return f"str({code})"

    @staticmethod
    def _type(expr):
        return getattr(expr, "inferred_type", None)

    # ------------------------------------------------------------
    # EXPRESSIONS
    # ------------------------------------------------------------

    def _receiver(self, expr):
        return prec.postfix_operand(self._generate_expr(expr), expr, LANG)

    def _binary(self, expr):

        op = expr.operator

        if op in ("TruncDiv", "TruncMod"):
            helper = "_tdiv" if op == "TruncDiv" else "_tmod"
            self.helpers.add(helper)
            return f"{helper}({self._generate_expr(expr.left)}, {self._generate_expr(expr.right)})"

        if op == "Mod" and self.source_lang != "python":
            # A floating-point % in C or Java truncates, like fmod.
            self.uses_math = True
            return f"math.fmod({self._generate_expr(expr.left)}, {self._generate_expr(expr.right)})"

        if op == "Add" and self.source_lang != "python" and self._type(expr) == "String":
            # Java's + converts the non-string side; Python needs str().
            left = self._as_text(expr.left) if self._type(expr.left) != "String" else \
                prec.operand(self._generate_expr(expr.left), expr.left, "Add", LANG)
            right = self._as_text(expr.right)
            return f"{left} + {right}"

        if op not in OPERATORS:
            raise UnsupportedConstruct(f"operator {op} cannot be written as Python")

        left = prec.operand(self._generate_expr(expr.left), expr.left, op, LANG)
        right = prec.operand(self._generate_expr(expr.right), expr.right, op, LANG, right=True)
        return f"{left} {OPERATORS[op]} {right}"

    def _cast(self, expr):

        inner = self._generate_expr(expr.value)
        source = self._type(expr.value)
        target = expr.target_type

        if target in ("int", "long", "short", "byte"):
            return f"ord({inner})" if source == "char" else f"int({inner})"
        if target in ("float", "double"):
            return f"float(ord({inner}))" if source == "char" else f"float({inner})"
        if target in ("str", "String"):
            if source in ("String", "char"):
                return inner
            return self._as_text(expr.value)
        if target in ("bool", "boolean"):
            return f"bool({inner})"
        if target == "char":
            return f"chr({inner})" if source in ("int", "long") else inner
        raise UnsupportedConstruct(f"cast to {target} cannot be written as Python")

    def _call(self, expr):

        args = ", ".join(self._generate_expr(a) for a in expr.args)
        name = expr.name

        if name == "range_array":
            element = ELEMENT_DEFAULTS.get(getattr(expr, "element_type", "int"), "0")
            if len(expr.args) == 1:
                return f"[{element}] * {prec.operand(self._generate_expr(expr.args[0]), expr.args[0], 'Mult', LANG, right=True)}"
            if len(expr.args) == 2:
                rows = self._generate_expr(expr.args[0])
                columns = prec.operand(self._generate_expr(expr.args[1]), expr.args[1], "Mult", LANG, right=True)
                return f"[[{element}] * {columns} for _ in range({rows})]"
            raise UnsupportedConstruct("arrays with more than two dimensions")

        if name in ("sqrt", "pow"):
            self.uses_math = True
            return f"math.{name}({args})"

        if name in CHARACTER_METHODS and len(expr.args) == 1:
            receiver = prec.postfix_operand(self._generate_expr(expr.args[0]), expr.args[0], LANG)
            return f"{receiver}.{CHARACTER_METHODS[name]}()"

        if name in ("floor", "ceil"):
            # Java's Math.floor and C's floor return a double.
            self.uses_math = True
            return f"float(math.{name}({args}))"

        if name in ("System.out.println", "System.out.print"):
            return f"print({args})"

        # A sibling method called without a receiver, as Java allows.
        if self.current_class is not None and "." not in name:
            for method in self.current_class.methods:
                if method.name == name and not method.is_constructor:
                    if method.is_static or self.in_static:
                        return f"{self.current_class.name}.{name}({args})"
                    return f"self.{name}({args})"

        return f"{name}({args})"

    def _generate_expr(self, expr):

        if expr is None:
            return "None"

        if isinstance(expr, SelfRef):
            return "self"

        if isinstance(expr, AttributeAccess):
            return f"{self._receiver(expr.obj)}.{expr.attribute}"

        if isinstance(expr, UnaryOp):
            op_map = {"USub": "-", "UAdd": "+", "Not": "not ", "Invert": "~"}
            if expr.operator not in op_map:
                raise UnsupportedConstruct(f"unary operator {expr.operator}")
            operand = prec.unary_operand(self._generate_expr(expr.operand), expr.operand, LANG)
            return f"{op_map[expr.operator]}{operand}"

        if isinstance(expr, TernaryOp):
            return (
                f"{prec.ternary_part(self._generate_expr(expr.if_true), expr.if_true)} if "
                f"{prec.ternary_part(self._generate_expr(expr.condition), expr.condition)} else "
                f"{self._generate_expr(expr.if_false)}"
            )

        if isinstance(expr, StringInterpolation):
            parts = []
            for part in expr.parts:
                if isinstance(part, Constant) and isinstance(part.value, str):
                    parts.append(part.value.replace("{", "{{").replace("}", "}}"))
                elif isinstance(part, FormatString) and len(part.args) == 1:
                    parts.append("{" + self._generate_expr(FormatString(part.fmt, part.args)) + "}")
                else:
                    parts.append("{" + self._generate_expr(part) + "}")
            return 'f' + repr("".join(parts))

        if isinstance(expr, FormatString):
            fmt = printf_format.to_python(expr.fmt)
            args = [self._generate_expr(a) for a in expr.args]
            if len(args) == 1:
                return f"{fmt!r} % ({args[0]},)"
            return f"{fmt!r} % ({', '.join(args)})"

        if isinstance(expr, IndexAccess):
            if getattr(expr, "c_string", False):
                self.helpers.add("_char_at")
                return f"_char_at({self._generate_expr(expr.obj)}, {self._generate_expr(expr.index)})"
            return f"{self._receiver(expr.obj)}[{self._generate_expr(expr.index)}]"

        if isinstance(expr, BooleanOp):
            if expr.operator not in COMPARISONS:
                raise UnsupportedConstruct(f"comparison {expr.operator} cannot be written as Python")
            op = expr.operator
            left = prec.operand(self._generate_expr(expr.left), expr.left, op, LANG)
            right = prec.operand(self._generate_expr(expr.right), expr.right, op, LANG, right=True)
            return f"{left} {COMPARISONS[op]} {right}"

        if isinstance(expr, DictLiteral):
            pairs = ", ".join(
                f"{self._generate_expr(k)}: {self._generate_expr(v)}"
                for k, v in zip(expr.keys, expr.values)
            )
            return "{" + pairs + "}"

        if isinstance(expr, SetLiteral):
            if not expr.elements:
                return "set()"
            return "{" + ", ".join(self._generate_expr(e) for e in expr.elements) + "}"

        if isinstance(expr, TypeCast):
            return self._cast(expr)

        if isinstance(expr, Input):
            # A C, C++ or Java source reads through a stream whose position
            # every kind of read shares; Python's own input() is line-based.
            if self.source_lang != "python":
                self.uses_tokens = True
                return {
                    "int": "_read_int()",
                    "long": "_read_int()",
                    "double": "_read_float()",
                    "char": "_read_char()",
                    "token": "_read_token()",
                }.get(expr.value_type, "_read_line()")

            prompt = self._generate_expr(expr.prompt) if expr.prompt else ""
            return f"input({prompt})"

        if isinstance(expr, RangeCall):
            return "range(" + ", ".join(self._generate_expr(a) for a in expr.args) + ")"

        if isinstance(expr, Constant):
            return repr(expr.value)

        if isinstance(expr, Identifier):
            return expr.name

        if isinstance(expr, BinaryOp):
            return self._binary(expr)

        if isinstance(expr, ArrayLiteral):
            elements = ", ".join(self._generate_expr(e) for e in expr.elements)
            return f"[{elements}]"

        if isinstance(expr, FunctionCall):
            return self._call(expr)

        if isinstance(expr, ObjectCreation):

            if expr.class_name in ("ArrayList", "LinkedList", "Vector"):
                return "[]"

            if expr.class_name in ("HashMap", "TreeMap"):
                return "{}"

            if expr.class_name in ("HashSet", "TreeSet"):
                return "set()"

            args = ", ".join(self._generate_expr(a) for a in (expr.arguments or []))
            return f"{expr.class_name}({args})"

        if isinstance(expr, MethodCall):

            object_name = self._receiver(expr.obj)
            method_name = expr.method
            arg_list = expr.args

            args = ", ".join(self._generate_expr(a) for a in arg_list)

            # A user-defined object's methods mean what its class says.
            if isinstance(expr.obj, SelfRef) or self._type(expr.obj) in self.class_names:
                return f"{object_name}.{method_name}({args})"

            if method_name == "set_index":
                index = self._generate_expr(arg_list[0])
                value = self._generate_expr(arg_list[1])
                return f"{object_name}[{index}] = {value}"

            # Handle System.out.println
            if object_name == "System.out" and method_name in ("println", "print"):
                return f"print({args})"

            # list.add() → append()
            if method_name == "add":
                return f"{object_name}.append({args})"

            # map.put(key, value)
            if method_name == "put":
                key = self._generate_expr(arg_list[0])
                val = self._generate_expr(arg_list[1])
                return f"{object_name}[{key}] = {val}"

            # list.size()
            if method_name == "size":
                return f"len({self._generate_expr(expr.obj)})"

            if method_name == "isEmpty" and not arg_list:
                return f"len({self._generate_expr(expr.obj)}) == 0"

            # Java's substring(a, b) is a slice.
            if method_name == "substring" and len(arg_list) in (1, 2):
                bounds = ":".join(self._generate_expr(a) for a in arg_list)
                return f"{object_name}[{bounds}{':' if len(arg_list) == 1 else ''}]"

            # list.get(i)
            if method_name == "get":
                return f"{object_name}[{args}]"

            # thread.start()
            if method_name == "start":
                return f"{object_name}.start()"

            # scanner.nextInt()
            if method_name == "nextInt":
                return "int(input())"

            if method_name == "nextLine":
                return "input()"

            # arr[i]
            if method_name == "get_index":
                index = self._generate_expr(arg_list[0])
                return f"{object_name}[{index}]"

            # default case
            return f"{object_name}.{method_name}({args})"

        raise UnsupportedConstruct(f"expression {type(expr).__name__} cannot be written as Python")
