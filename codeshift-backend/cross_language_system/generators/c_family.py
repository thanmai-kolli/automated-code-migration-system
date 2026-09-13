"""Shared IR-to-C-family code generation.

The C and C++ generators historically worked only on raw text, because the C
parser emits source chunks rather than a structured IR. That is fine for C<->C++
but leaves Python->C/C++ unimplemented. This module renders a real IR into either
language so every source/target pair is covered.
"""

from cross_language_system.core.ir_nodes import *


ARITHMETIC = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "/",
    "Mod": "%", "BitAnd": "&", "BitOr": "|", "BitXor": "^",
    "LShift": "<<", "RShift": ">>",
}

COMPARISON = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=",
    "And": "&&", "Or": "||",
}

UNARY = {"USub": "-", "UAdd": "+", "Not": "!", "Invert": "~"}


class CFamilyGenerator:
    """Base emitter. Subclasses set `cpp` and provide the type table."""

    cpp = True

    def __init__(self, source=None, target=None):
        self.source = source
        self.target = target
        self.scope = {}
        self.current_class = None

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
            "float": "double",
            "double": "double",
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
        return {"Integer": "int", "Double": "double", "Boolean": "bool",
                "String": "String", "Object": "Object"}.get(name, name)

    def default_value(self, type_name):
        rendered = self.type_of(type_name)
        if rendered in ("int", "long"):
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

    # ------------------------------------------------------------
    # PROGRAM
    # ------------------------------------------------------------

    def generate_from_ir(self, program):

        classes = [n for n in program.body if isinstance(n, Class)]
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
        return self.headers(program, body) + body

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

    def expr(self, node):

        if node is None:
            return "NULL" if not self.cpp else "nullptr"

        if isinstance(node, Constant):
            return self.constant(node.value)

        if isinstance(node, Identifier):
            return node.name

        if isinstance(node, SelfRef):
            return "this" if self.cpp else "self"

        if isinstance(node, AttributeAccess):
            arrow = "->" if (not self.cpp or isinstance(node.obj, SelfRef)) else "."
            return f"{self.expr(node.obj)}{arrow}{node.attribute}"

        if isinstance(node, UnaryOp):
            operand = self.expr(node.operand)
            if isinstance(node.operand, (BinaryOp, BooleanOp, TernaryOp)):
                operand = f"({operand})"
            return f"{UNARY.get(node.operator, '-')}{operand}"

        if isinstance(node, BinaryOp):
            left = self.expr(node.left)
            right = self.expr(node.right)

            # There is no exponentiation operator in C or C++.
            if node.operator == "Pow":
                call = f"pow({left}, {right})"
                integral = (
                    self._expr_type(node.left) in (None, "int")
                    and self._expr_type(node.right) in (None, "int")
                )
                return f"(int) {call}" if integral else call

            if node.operator == "Div" and self.source == "python":
                left = f"(double) {left}"
            return f"{left} {ARITHMETIC.get(node.operator, '+')} {right}"

        if isinstance(node, BooleanOp):
            return f"{self.expr(node.left)} {COMPARISON.get(node.operator, '==')} {self.expr(node.right)}"

        if isinstance(node, TernaryOp):
            return f"{self.expr(node.condition)} ? {self.expr(node.if_true)} : {self.expr(node.if_false)}"

        if isinstance(node, IndexAccess):
            return f"{self.expr(node.obj)}[{self.expr(node.index)}]"

        if isinstance(node, TypeCast):
            inner = self.expr(node.value)

            # Parsing a string needs a conversion function, not a cast.
            if self._expr_type(node.value) in ("string", "char*"):
                if node.target_type == "int":
                    return f"stoi({inner})" if self.cpp else f"atoi({inner})"
                if node.target_type == "float":
                    return f"stod({inner})" if self.cpp else f"atof({inner})"

            target = {"int": "int", "float": "double", "bool": "bool"}.get(node.target_type)
            return f"({target}) {inner}" if target else inner

        if isinstance(node, ObjectCreation):
            # Java's collection classes become plain initialisers.
            if node.class_name in ("ArrayList", "LinkedList", "Vector",
                                   "HashMap", "TreeMap", "HashSet", "TreeSet"):
                return "{}"
            args = ", ".join(self.expr(a) for a in (node.arguments or []))
            return f"{node.class_name}({args})" if self.cpp else f"{node.class_name}_new({args})"

        if isinstance(node, FunctionCall):
            args = ", ".join(self.expr(a) for a in node.args)
            return f"{node.name}({args})"

        if isinstance(node, MethodCall):
            return self.method_call(node)

        if isinstance(node, Input):
            if self.cpp:
                # An immediately-invoked lambda lets a read work as an expression.
                return "[]{ string _line; getline(cin, _line); return _line; }()"
            return "NULL"

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

        if isinstance(node, RangeCall):
            return self.expr(node.args[-1]) if node.args else "0"

        return "0"

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

    def constant(self, value):
        if value is None:
            return "nullptr" if self.cpp else "NULL"
        if isinstance(value, bool):
            return ("true" if value else "false") if self.cpp else ("1" if value else "0")
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'
        return str(value)

    def method_call(self, node):
        obj = self.expr(node.obj)
        args = ", ".join(self.expr(a) for a in node.args)

        if node.method == "size":
            return f"{obj}.size()" if self.cpp else f"{obj}_length"

        if self.cpp:
            # Java collection calls have operator or member equivalents in C++.
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

        return f"{obj}.{node.method}({args})" if self.cpp else f"{node.method}({obj}{', ' + args if args else ''})"

    def interpolation(self, node):
        raise NotImplementedError

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def statement(self, stmt, indent):

        tab = "    " * indent

        if stmt is None or isinstance(stmt, Pass):
            return ""

        # Reading stdin is a statement in C and C++, not an expression.
        if isinstance(stmt, Variable) and isinstance(stmt.value, Input):
            declared = stmt.var_type if stmt.var_type not in (None, "auto") else stmt.value.value_type
            rendered = self.type_of(declared)
            already = self.scope.get(stmt.name)
            self.scope[stmt.name] = rendered
            prefix = "" if already else f"{tab}{rendered} {stmt.name};\n"
            return prefix + self.read_into(stmt.name, rendered, indent, stmt.value.value_type)

        if isinstance(stmt, Assignment) and isinstance(stmt.value, Input):
            target = self.expr(stmt.target)
            rendered = self.scope.get(target) or self.type_of(stmt.value.value_type)
            return self.read_into(target, rendered, indent, stmt.value.value_type)

        if isinstance(stmt, Break):
            return f"{tab}break;\n"

        if isinstance(stmt, Continue):
            return f"{tab}continue;\n"

        if isinstance(stmt, Return):
            if stmt.value is None:
                return f"{tab}return;\n"
            return f"{tab}return {self.expr(stmt.value)};\n"

        if isinstance(stmt, Variable):
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

        if isinstance(stmt, Assignment):
            return f"{tab}{self.expr(stmt.target)} = {self.expr(stmt.value)};\n"

        if isinstance(stmt, AugAssign):
            op = ARITHMETIC.get(stmt.operator, "+")
            return f"{tab}{self.expr(stmt.target)} {op}= {self.expr(stmt.value)};\n"

        if isinstance(stmt, IfStatement):
            code = f"{tab}if ({self.expr(stmt.condition)}) {{\n"
            for s in stmt.body:
                code += self.statement(s, indent + 1)
            if stmt.else_body:
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self.statement(stmt.else_body[0], indent).lstrip()
                    return code + f"{tab}}} else {nested}"
                code += f"{tab}}} else {{\n"
                for s in stmt.else_body:
                    code += self.statement(s, indent + 1)
            return code + f"{tab}}}\n"

        if isinstance(stmt, WhileLoop):
            code = f"{tab}while ({self.expr(stmt.condition)}) {{\n"
            for s in stmt.body:
                code += self.statement(s, indent + 1)
            return code + f"{tab}}}\n"

        if isinstance(stmt, ForLoop):
            return self.for_loop(stmt, indent)

        if isinstance(stmt, PrintStatement):
            return self.print_statement(stmt, indent)

        if isinstance(stmt, ListAppend):
            target = self.expr(stmt.list_obj)
            if self.cpp:
                return f"{tab}{target}.push_back({self.expr(stmt.value)});\n"
            return f"{tab}/* append to {target} requires manual sizing */\n"

        if isinstance(stmt, DictPut):
            return (
                f"{tab}{self.expr(stmt.dictionary)}[{self.expr(stmt.key)}]"
                f" = {self.expr(stmt.value)};\n"
            )

        if isinstance(stmt, (FunctionCall, MethodCall)):
            return f"{tab}{self.expr(stmt)};\n"

        if isinstance(stmt, TryCatch):
            return self.try_catch(stmt, indent)

        return ""

    def for_loop(self, stmt, indent):

        tab = "    " * indent

        if isinstance(stmt.iterable, RangeCall):
            args = stmt.iterable.args
            start = self.expr(args[0]) if len(args) > 1 else "0"
            end = self.expr(args[1]) if len(args) > 1 else (self.expr(args[0]) if args else "0")
            self.scope[stmt.iterator] = "int"
            code = f"{tab}for (int {stmt.iterator} = {start}; {stmt.iterator} < {end}; {stmt.iterator}++) {{\n"
        elif self.cpp:
            code = f"{tab}for (auto {stmt.iterator} : {self.expr(stmt.iterable)}) {{\n"
        else:
            name = self.expr(stmt.iterable)
            code = (
                f"{tab}for (int i = 0; i < {name}_length; i++) {{\n"
                f"{tab}    int {stmt.iterator} = {name}[i];\n"
            )

        for s in stmt.body:
            code += self.statement(s, indent + 1)

        return code + f"{tab}}}\n"

    def print_statement(self, stmt, indent):
        raise NotImplementedError

    def read_into(self, target, rendered_type, indent, value_type):
        raise NotImplementedError

    def try_catch(self, stmt, indent):

        tab = "    " * indent

        if not self.cpp:
            # C has no exceptions; keep the happy path and flag the loss.
            code = f"{tab}/* try/catch has no C equivalent; body inlined */\n"
            for s in stmt.try_body:
                code += self.statement(s, indent)
            return code

        code = f"{tab}try {{\n"
        for s in stmt.try_body:
            code += self.statement(s, indent + 1)
        code += f"{tab}}} catch (const exception& {stmt.catch_var or 'e'}) {{\n"
        for s in stmt.catch_body:
            code += self.statement(s, indent + 1)
        return code + f"{tab}}}\n"

    # ------------------------------------------------------------
    # DECLARATIONS
    # ------------------------------------------------------------

    def render_class(self, cls):
        raise NotImplementedError

    def render_function(self, func, indent=0, owner=None):
        raise NotImplementedError
