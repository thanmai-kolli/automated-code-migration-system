from cross_language_system.core.ir_nodes import *
from cross_language_system.core.symbol_table import SymbolTable


class PythonGenerator:

    def __init__(self, source_lang, target_lang):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.exception_map = {
            "ArithmeticException": "ZeroDivisionError",
            "NullPointerException": "AttributeError",
            "IndexOutOfBoundsException": "IndexError"
        }
        

    def generate(self, program):

        self.symbol_table = SymbolTable()
        blocks = []
        main_statements = []
        entry_class = None

        for node in program.body:

            if isinstance(node, Class):
                blocks.append(self._generate_class(node))
                if any(m.name == "main" for m in node.methods):
                    entry_class = node.name

            elif isinstance(node, Function):
                blocks.append(self._generate_function(node))

            else:
                main_statements.append(node)

        code = "\n".join(b for b in blocks if b.strip())

        if main_statements:
            body = "".join(self._generate_statement(s, 1) for s in main_statements)
            code += "\n\nif __name__ == '__main__':\n" + (body or "    pass\n")

        elif entry_class:
            code += f"\n\nif __name__ == '__main__':\n    {entry_class}.main([])\n"

        return code or "pass\n"

    def _generate_class(self, cls):

        header = f"class {cls.name}({cls.base}):\n" if cls.base else f"class {cls.name}:\n"
        code = header

        if not cls.methods:
            # Fields alone still need a constructor to be meaningful.
            if cls.fields:
                code += "    def __init__(self):\n"
                for field in cls.fields:
                    default = self._generate_expr(field.value) if field.value else self._default_for(field.field_type)
                    code += f"        self.{field.name} = {default}\n"
                return code + "\n"
            return code + "    pass\n\n"

        for method in cls.methods:
            code += self._generate_function(method, indent=1, owner=cls)

        return code

    def _default_for(self, field_type):
        return {
            "int": "0",
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
        elif owner:
            params = ", ".join(func.params)
        else:
            params = ", ".join(func.params)

        code = ""
        if owner and func.is_static and not func.is_constructor:
            code += f"{tab}@staticmethod\n"

        code += f"{tab}def {name}({params}):\n"

        body = "".join(self._generate_statement(s, indent + 1) for s in func.body)

        if not body.strip():
            body = f"{tab}    pass\n"

        return code + body + "\n"

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent

        if isinstance(stmt, Pass):
            return f"{tab}pass\n"

        if isinstance(stmt, Assignment):
            return f"{tab}{self._generate_expr(stmt.target)} = {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, AugAssign):
            op_map = {"Add": "+=", "Sub": "-=", "Mult": "*=", "Div": "/=", "Mod": "%="}
            op = op_map.get(stmt.operator, "+=")
            return f"{tab}{self._generate_expr(stmt.target)} {op} {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, PrintStatement):
            args = ", ".join(self._generate_expr(a) for a in stmt.args)
            return f"{tab}print({args})\n"

        if isinstance(stmt, ListAppend):
            return f"{tab}{self._generate_expr(stmt.list_obj)}.append({self._generate_expr(stmt.value)})\n"

        if isinstance(stmt, DictPut):
            return (
                f"{tab}{self._generate_expr(stmt.dictionary)}"
                f"[{self._generate_expr(stmt.key)}] = {self._generate_expr(stmt.value)}\n"
            )

        if isinstance(stmt, Field):
            return ""

        if isinstance(stmt, Variable):

            # Skip Scanner object creation
            if isinstance(stmt.value, ObjectCreation) and stmt.value.class_name == "Scanner":
                return ""

            return f"{tab}{stmt.name} = {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, Return):
            if stmt.value is None:
                return f"{tab}return\n"
            return f"{tab}return {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, IfStatement):
            code = f"{tab}if {self._generate_expr(stmt.condition)}:\n"
            body = "".join(self._generate_statement(s, indent + 1) for s in stmt.body)
            code += body or f"{tab}    pass\n"
            if stmt.else_body:
                # A lone nested if came from an elif; keep it flat.
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self._generate_statement(stmt.else_body[0], indent)
                    return code + f"{tab}el" + nested.lstrip()
                code += f"{tab}else:\n"
                inner = "".join(self._generate_statement(s, indent + 1) for s in stmt.else_body)
                code += inner or f"{tab}    pass\n"
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
            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)
            return code
        
        if isinstance(stmt, TryCatch):

            exception = self.exception_map.get(stmt.exception_type, "Exception")
            code = f"{tab}try:\n"
            if not stmt.try_body:
                code += f"{tab}    pass\n"
            else:
                for s in stmt.try_body:
                    code += self._generate_statement(s, indent + 1)

            binding = f" as {stmt.catch_var}" if stmt.catch_var else ""
            code += f"{tab}except {exception}{binding}:\n"
            if not stmt.catch_body:
                code += f"{tab}    pass\n"
            else:
                for s in stmt.catch_body:
                    code += self._generate_statement(s, indent + 1)

            return code
        
        if isinstance(stmt, WhileLoop):

            code = f"{tab}while {self._generate_expr(stmt.condition)}:\n"

            if not stmt.body:
                code += f"{tab}    pass\n"
            else:
                for s in stmt.body:
                    code += self._generate_statement(s, indent + 1)

            return code

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

                    if i == 0:
                        code += f"{tab}if {condition}:\n"
                    else:
                        code += f"{tab}elif {condition}:\n"
                else:
                    code += f"{tab}else:\n"

                if not case.body:
                    code += f"{tab}    pass\n"
                else:
                    for s in case.body:
                        code += self._generate_statement(s, indent + 1)

            return code

        
        if isinstance(stmt, MethodCall):
            return f"{tab}{self._generate_expr(stmt)}\n"

        return ""
    
        

    def _generate_expr(self, expr):

        if expr is None:
            return "None"

        if isinstance(expr, SelfRef):
            return "self"

        if isinstance(expr, AttributeAccess):
            return f"{self._generate_expr(expr.obj)}.{expr.attribute}"

        if isinstance(expr, UnaryOp):
            op_map = {"USub": "-", "UAdd": "+", "Not": "not ", "Invert": "~"}
            operand = self._generate_expr(expr.operand)
            if isinstance(expr.operand, (BinaryOp, BooleanOp, TernaryOp)):
                operand = f"({operand})"
            return f"{op_map.get(expr.operator, '-')}{operand}"

        if isinstance(expr, TernaryOp):
            return (
                f"{self._generate_expr(expr.if_true)} if "
                f"{self._generate_expr(expr.condition)} else "
                f"{self._generate_expr(expr.if_false)}"
            )

        if isinstance(expr, StringInterpolation):
            parts = []
            for part in expr.parts:
                if isinstance(part, Constant) and isinstance(part.value, str):
                    parts.append(part.value)
                else:
                    parts.append("{" + self._generate_expr(part) + "}")
            return 'f"' + "".join(parts).replace('"', '\\"') + '"'

        if isinstance(expr, IndexAccess):
            return f"{self._generate_expr(expr.obj)}[{self._generate_expr(expr.index)}]"

        if isinstance(expr, BooleanOp):
            op_map = {
                "And": "and", "Or": "or", "Eq": "==", "NotEq": "!=",
                "Lt": "<", "Gt": ">", "LtE": "<=", "GtE": ">=",
                "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in",
            }
            op = op_map.get(expr.operator, expr.operator)
            return f"{self._generate_expr(expr.left)} {op} {self._generate_expr(expr.right)}"

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
            cast = {"int": "int", "float": "float", "str": "str", "bool": "bool"}
            return f"{cast.get(expr.target_type, 'str')}({self._generate_expr(expr.value)})"

        if isinstance(expr, Input):
            prompt = self._generate_expr(expr.prompt) if expr.prompt else ""
            return f"input({prompt})"

        if isinstance(expr, RangeCall):
            return "range(" + ", ".join(self._generate_expr(a) for a in expr.args) + ")"

        if isinstance(expr, Constant):
            return repr(expr.value)

        if isinstance(expr, Identifier):
            return expr.name

        if isinstance(expr, BinaryOp):
            op_map = {
                "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
                "FloorDiv": "//", "Mod": "%", "Pow": "**",
                "BitAnd": "&", "BitOr": "|", "BitXor": "^",
                "LShift": "<<", "RShift": ">>",
            }
            op = op_map.get(expr.operator, expr.operator)
            return f"{self._generate_expr(expr.left)} {op} {self._generate_expr(expr.right)}"
        

        if isinstance(expr, ArrayLiteral):
            elements = ", ".join(self._generate_expr(e) for e in expr.elements)
            return f"[{elements}]"
        
        if isinstance(expr, FunctionCall):

            if expr.name == "range_array":
                size = self._generate_expr(expr.args[0])
                return f"[0]*{size}"

            arg_list = expr.args
            args = ", ".join(self._generate_expr(a) for a in arg_list)

            if expr.name == "System.out.println" or expr.name == "System.out.print":
                return f"print({args})"

            if expr.name == "range":
                return f"range({args})"
            if "." in expr.name:
                return f"{expr.name}({args})"

            return f"{expr.name}({args})"
     
        if isinstance(expr, ObjectCreation):

            if expr.class_name == "ArrayList":
                return "[]"

            if expr.class_name == "HashMap":
                return "{}"

            if expr.class_name == "HashSet":
                return "set()"

            return f"{expr.class_name}()"
        
        if isinstance(expr, MethodCall):

            object_name = self._generate_expr(expr.obj)
            method_name = expr.method
            arg_list = expr.args

            args = ", ".join(self._generate_expr(a) for a in arg_list)

            if method_name == "set_index":
                index = self._generate_expr(arg_list[0])
                value = self._generate_expr(arg_list[1])
                return f"{object_name}[{index}] = {value}"

            # Handle System.out.println
            if object_name == "System.out" and (method_name == "println" or method_name == "print"):
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
                return f"len({object_name})"

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
            
            # arr[i] = value
            if method_name == "set_index":
                index = self._generate_expr(arg_list[0])
                value = self._generate_expr(arg_list[1])
                return f"{object_name}[{index}] = {value}"

            # arr[i]
            if method_name == "get_index":
                index = self._generate_expr(arg_list[0])
                return f"{object_name}[{index}]"

            # default case
            return f"{object_name}.{method_name}({args})"

        return "None"