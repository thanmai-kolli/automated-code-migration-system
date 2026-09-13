from core.ir_nodes import *
from core.symbol_table import SymbolTable


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
        code = ""

        class_name = None

        for node in program.body:
            if isinstance(node, Class):
                class_name = node.name
                code += self._generate_node(node)

        if class_name:
            code += "\nif __name__ == '__main__':\n"
            code += f"    {class_name}.main([])\n"

        return code

    def _generate_node(self, node):

        if isinstance(node, Class):
            return self._generate_class(node)

        if isinstance(node, Function):
            return self._generate_function(node)

        return ""

    def _generate_class(self, cls):

        code = f"class {cls.name}:\n"

        if not cls.methods:
            code += "    pass\n"
            return code

        for method in cls.methods:
            code += self._generate_function(method, indent=1)

        return code + "\n"

    def _generate_function(self, func, indent=0):

        tab = "    " * indent
        params = ", ".join(func.params)

        if func.name == "main":
            code = f"{tab}@staticmethod\n"
            code += f"{tab}def {func.name}({params}):\n"
        else:
            code = f"{tab}def {func.name}({params}):\n"

        if not func.body:
            return code + f"{tab}    pass\n"

        for stmt in func.body:
            code += self._generate_statement(stmt, indent + 1)

        return code + "\n"

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent

        if isinstance(stmt, Variable):

            # Skip Scanner object creation
            if isinstance(stmt.value, ObjectCreation) and stmt.value.class_name == "Scanner":
                return ""

            return f"{tab}{stmt.name} = {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, Return):
            return f"{tab}return {self._generate_expr(stmt.value)}\n"

        if isinstance(stmt, IfStatement):
            code = f"{tab}if {self._generate_expr(stmt.condition)}:\n"
            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)
            if stmt.else_body:
                code += f"{tab}else:\n"
                for s in stmt.else_body:
                    code += self._generate_statement(s, indent + 1)
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

            exception = self.exception_map.get(
                stmt.exception_type, "Exception"
            )
            code = f"{tab}try:\n"
            if not stmt.try_body:
                code += f"{tab}    pass\n"
            else:
                for s in stmt.try_body:
                    code += self._generate_statement(s, indent + 1)

            code += f"{tab}except Exception as {stmt.catch_var}:\n"
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

        if isinstance(expr, Constant):
            return repr(expr.value)

        if isinstance(expr, Identifier):
            return expr.name


        if isinstance(expr, BinaryOp):
            op_map = {
                "&&": "and",
                "||": "or",
                "==": "==",
                "!=": "!=",
                ">": ">",
                "<": "<",
                ">=": ">=",
                "<=": "<=",
                "+": "+",
                "-": "-",
                "*": "*",
                "/": "/",
                "%": "%"
            }

            op = op_map.get(expr.operator, expr.operator)

            left = self._generate_expr(expr.left)
            right = self._generate_expr(expr.right)

            # If + operator and one side is string, convert to safe Python
            if expr.operator == "+":
                if isinstance(expr.left, Constant) and isinstance(expr.left.value, str):
                    return f"{left}, {right}"
                if isinstance(expr.right, Constant) and isinstance(expr.right.value, str):
                    return f"{left}, {right}"

            return f"{left} {op} {right}"
        

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

            # Array creation
            if isinstance(expr, FunctionCall) and expr.name == "range_array":
                size = self._generate_expr(expr.args[0])
                return f"[0]*{size}"

            object_name = expr.obj
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