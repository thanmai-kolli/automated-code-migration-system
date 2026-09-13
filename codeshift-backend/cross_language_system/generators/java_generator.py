from cross_language_system.core.ir_nodes import *
from cross_language_system.core.symbol_table import SymbolTable
from cross_language_system.core.type_mapper import TypeMapper
from cross_language_system.core.type_inference import TypeInferenceEngine


class JavaGenerator:

    def __init__(self, source_lang, target_lang):
        self.source_lang = source_lang.lower()
        self.target_lang = target_lang.lower()
        self.mapper = TypeMapper()
        self.symbol_table = SymbolTable()
        self.inference_engine = TypeInferenceEngine()
        self.function_param_types = {}
        
    def _to_wrapper(self, primitive):

        wrapper_map = {
            "int": "Integer",
            "double": "Double",
            "float": "Double",
            "boolean": "Boolean",
            "bool": "Boolean",
            "char": "Character"
        }

        return wrapper_map.get(primitive, primitive)

    # -------------------------------------------------
    # ENTRY POINT
    # -------------------------------------------------

    # def generate(self, program):

    #     code = "import java.util.*;\n\n"
    #     code += "public class Converted {\n"
    #     code += "    static Scanner sc = new Scanner(System.in);\n\n"

    #     function_names = []
    #     self.function_returns = {}

    #     for node in program.body:
    #         code += self._generate_node(node)

    #         if isinstance(node, Function):
    #             function_names.append(node.name)

    #     # # Add main method automatically
    #     # if function_names:
    #     #     # Prefer calling function without parameters
    #     #     for node in program.body:
    #     #         if isinstance(node, Function) and len(node.params) == 0:
    #     #             first_function = node.name
    #     #             break
    #     #     else:
    #     #         first_function = function_names[-1]

    #     # code += f"""
    #     #     public static void main(String[] args) {{
    #     #         {first_function}();
    #     #     }}
    #     # """
    #     # Add main method automatically
    #     if function_names:
    #         for node in program.body:
    #             if isinstance(node, Function) and len(node.params) == 0:
    #                 first_function = node.name
    #                 break
    #         else:
    #             first_function = function_names[-1]

    #         main_call = f"{first_function}();"
    #     else:
    #         # No functions defined — no automatic call
    #         main_call = "// No functions to call"

    #     code += f"""
    #         public static void main(String[] args) {{
    #             {main_call}
    #         }}
    #     """
    #     code += "}\n"

    #     return code
    # -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------

    def generate(self, program):

        uses_input = self._program_uses_input(program)
        self._collect_function_calls(program)
        code = "import java.util.*;\n\n"
        code += "public class Converted {\n"

        if uses_input:
            code += "    static Scanner sc = new Scanner(System.in);\n\n"

        function_names = []
        main_statements = []
        self.function_returns = {}

        # ---------------------------------------------
        # Separate functions and top-level statements
        # ---------------------------------------------
        for node in program.body:

            if isinstance(node, Function):
                code += self._generate_node(node)
                function_names.append(node.name)

            elif isinstance(node, Class):
                code += self._generate_node(node)

            else:
                # Collect top-level statements to inject into main()
                main_statements.append(node)

        # ---------------------------------------------
        # Generate main method
        # ---------------------------------------------
        code += "    public static void main(String[] args) {\n"

        if not main_statements and function_names:
            # Prefer calling a no-parameter function
            first_function = None

            for node in program.body:
                if isinstance(node, Function) and len(node.params) == 0:
                    first_function = node.name
                    break

            if not first_function:
                first_function = function_names[-1]

            code += f"        {first_function}();\n"

        # Inject top-level statements (like print, variable, loops, etc.)
        for stmt in main_statements:
            code += self._generate_statement(stmt, indent=2)

        code += "    }\n"
        code += "}\n"

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

        code = f"    public static class {cls.name} {{\n"

        for method in cls.methods:
            code += self._generate_function(method, indent=2)

        code += "    }\n"
        return code

    # -------------------------------------------------
    # FUNCTION
    # -------------------------------------------------

    def _generate_function(self, func, indent=1):

        tab = "    " * indent
        params = []
        self.symbol_table = SymbolTable()

        # -------- PARAMETER TYPE INFERENCE --------
        for p in func.params:

            inferred_type = "List<Object>"

            # Check if function was called
            if func.name in self.function_param_types:
                inferred_type = self.function_param_types[func.name][func.params.index(p)]

            # Detect if used in loop
            for stmt in func.body:
                if isinstance(stmt, ForLoop):

                    if isinstance(stmt.iterable, Identifier) and stmt.iterable.name == p:

                        element_type = self._infer_list_element_type(func, p)

                        inferred_type = f"List<{element_type}>"

            param_type = self.mapper.map(
                inferred_type,
                self.source_lang,
                self.target_lang
            )

            params.append(f"{param_type} {p}")
            self.symbol_table.register_variable(p, param_type)

        # -------- RETURN TYPE INFERENCE --------

        has_return = False
        inferred = "void"

        for stmt in func.body:
            if isinstance(stmt, Return):
                has_return = True
                inferred = self.inference_engine.infer(stmt.value)
                if isinstance(stmt.value, Identifier):
                    var_type = self.symbol_table.lookup(stmt.value.name)
                    if var_type:
                        inferred = var_type
                break

        # If no return statement → void
        if not has_return:
            return_type = "void"

        elif isinstance(inferred, str) and inferred.startswith("List<"):
            return_type = inferred

        else:
            return_type = self.mapper.map(
                inferred,
                self.source_lang,
                self.target_lang
            )
        code = f"{tab}public static {return_type} {func.name}({', '.join(params)}) {{\n"

        self.function_returns[func.name] = return_type

        for stmt in func.body:
            code += self._generate_statement(stmt, indent + 1)

        code += f"{tab}}}\n"

        return code

    # -------------------------------------------------
    # STATEMENTS
    # -------------------------------------------------

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent
        if isinstance(stmt, FunctionCall):
            args = ", ".join(self._generate_expr(a) for a in stmt.args)
            return f"{tab}{stmt.name}({args});\n"
        if isinstance(stmt, MethodCall):
            return f"{tab}{self._generate_expr(stmt)};\n"

        if isinstance(stmt, Variable):

            # -------- DICTIONARY HANDLING --------
            if isinstance(stmt.value, DictLiteral):

                key_type = self._infer_type(stmt.value.keys[0])
                val_type = self._infer_type(stmt.value.values[0])

                # First map Python → Java
                mapped_key = self.mapper.map(
                    key_type,
                    self.source_lang,
                    self.target_lang
                )

                mapped_val = self.mapper.map(
                    val_type,
                    self.source_lang,
                    self.target_lang
                )

                # Then convert primitives to wrapper
                key_wrapper = self._to_wrapper(mapped_key)
                val_wrapper = self._to_wrapper(mapped_val)

                self.symbol_table.register_variable(
                    stmt.name,
                    f"Map<{key_wrapper}, {val_wrapper}>"
                )

                code = f"{tab}Map<{key_wrapper}, {val_wrapper}> {stmt.name} = new HashMap<>();\n"

                for k, v in zip(stmt.value.keys, stmt.value.values):
                    code += f"{tab}{stmt.name}.put({self._generate_expr(k)}, {self._generate_expr(v)});\n"

                return code

            # -------- int(input()) HANDLING --------
            if isinstance(stmt.value, TypeCast):

                if isinstance(stmt.value.value, Input):

                    prompt_code = ""

                    if stmt.value.value.prompt:
                        prompt_text = self._generate_expr(stmt.value.value.prompt)
                        prompt_code = f"{tab}System.out.print({prompt_text});\n"

                    target = stmt.value.target_type

                    if target == "int":
                        self.symbol_table.register_variable(stmt.name, "int")
                        return prompt_code + f"{tab}int {stmt.name} = Integer.parseInt(sc.nextLine());\n"

                    if target == "float":
                        self.symbol_table.register_variable(stmt.name, "double")
                        return prompt_code + f"{tab}double {stmt.name} = Double.parseDouble(sc.nextLine());\n"

            # -------- INPUT HANDLING --------
            if isinstance(stmt.value, Input):

                prompt_code = ""

                if stmt.value.prompt:
                    prompt_text = self._generate_expr(stmt.value.prompt)
                    prompt_code = f"{tab}System.out.print({prompt_text});\n"

                self.symbol_table.register_variable(stmt.name, "String")

                return prompt_code + f"{tab}String {stmt.name} = sc.nextLine();\n"

            inferred_type = self.inference_engine.infer(stmt.value, stmt.name)

            if (
                inferred_type in ["Integer", "Double", "Boolean", "String"]
                or inferred_type.startswith("List<")
                or inferred_type.startswith("Set<")
                or inferred_type.startswith("Map<")
            ):
                java_type = java_type = self._fix_java_generics(inferred_type)
            else:
                java_type = self._fix_java_generics(
                    self.mapper.map(
                        inferred_type,
                        self.source_lang,
                        self.target_lang
                    )
                )

            # Check if variable already declared
            existing_type = self.symbol_table.lookup(stmt.name)

            if existing_type:
                # Reassignment
                return f"{tab}{stmt.name} = {self._generate_expr(stmt.value)};\n"
            else:
                # First declaration
                self.symbol_table.register_variable(stmt.name, java_type)
                return f"{tab}{java_type} {stmt.name} = {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, Return):
            return f"{tab}return {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, IfStatement):

            code = f"{tab}if ({self._generate_expr(stmt.condition)}) {{\n"

            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)

            if stmt.else_body:
                code += f"{tab}}} else {{\n"
                for s in stmt.else_body:
                    code += self._generate_statement(s, indent + 1)

            code += f"{tab}}}\n"
            return code

        if isinstance(stmt, ForLoop):


            if isinstance(stmt.iterable, RangeCall):

                args = stmt.iterable.args

                if len(args) == 1:
                    start = "0"
                    end = self._generate_expr(args[0])
                elif len(args) == 2:
                    start = self._generate_expr(args[0])
                    end = self._generate_expr(args[1])
                else:
                    start = self._generate_expr(args[0])
                    end = self._generate_expr(args[1])

                self.symbol_table.register_variable(stmt.iterator, "int")

                return f"{tab}for (int {stmt.iterator} = {start}; {stmt.iterator} < {end}; {stmt.iterator}++) {{\n" + \
                    "".join(self._generate_statement(s, indent + 1) for s in stmt.body) + \
                    f"{tab}}}\n"

            iterable_expr = self._generate_expr(stmt.iterable)

            iterable_type = self._infer_type(stmt.iterable)

            if iterable_type.startswith("List<"):
                element_type = iterable_type.split("<")[1].replace(">", "")
            else:
                element_type = "Object"

            self.symbol_table.register_variable(stmt.iterator, element_type)

            code = f"{tab}for ({element_type} {stmt.iterator} : {iterable_expr}) {{\n"

            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)

            code += f"{tab}}}\n"
            return code
        
        if isinstance(stmt, DictPut):
            return f"{tab}{self._generate_expr(stmt.dictionary)}.put({self._generate_expr(stmt.key)}, {self._generate_expr(stmt.value)});\n"
        
        if isinstance(stmt, PrintStatement):

            parts = []

            for arg in stmt.args:
                if isinstance(arg, BinaryOp):
                    parts.append(f"({self._generate_expr(arg)})")
                else:
                    parts.append(self._generate_expr(arg))

            if len(parts) == 1:
                final_expr = parts[0]
            else:
                # final_expr = " + \" \" + ".join(parts)
                final_expr = " + ".join(parts)

            return f"{tab}System.out.println({final_expr});\n"
        
        

        if isinstance(stmt, WhileLoop):

            code = f"{tab}while ({self._generate_expr(stmt.condition)}) {{\n"

            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)

            code += f"{tab}}}\n"
            return code
        
        
        
        if isinstance(stmt, ListAppend):

            element_type = self._infer_type(stmt.value)

            wrapper = self._to_wrapper(element_type)

            list_name = self._generate_expr(stmt.list_obj)

            existing_type = self.symbol_table.lookup(list_name)

            if existing_type == "List<Object>":
                new_type = f"List<{wrapper}>"

                self.symbol_table.register_variable(list_name, new_type)

            return f"{tab}{list_name}.add({self._generate_expr(stmt.value)});\n"

        return ""

    # -------------------------------------------------
    # EXPRESSIONS
    # -------------------------------------------------

    def _generate_expr(self, expr):

        if isinstance(expr, TypeCast):

            inner = self._generate_expr(expr.value)

            if expr.target_type == "int":
                return f"Integer.parseInt({inner})"

            if expr.target_type == "float":
                return f"Double.parseDouble({inner})"

            return inner

        if isinstance(expr, Constant):

            if isinstance(expr.value, str):
                return f"\"{expr.value}\""

            if isinstance(expr.value, bool):
                return str(expr.value).lower()

            return str(expr.value)

        if isinstance(expr, Identifier):
            return expr.name

        if isinstance(expr, BinaryOp):

            op_map = {
                "Add": "+",
                "Sub": "-",
                "Mult": "*",
                "Div": "/",
                "Mod": "%",
                "Pow": "^"
            }

            operator = op_map.get(expr.operator, "+")

            return f"{self._generate_expr(expr.left)} {operator} {self._generate_expr(expr.right)}"

        if isinstance(expr, BooleanOp):

            op_map = {
                "And": "&&",
                "Or": "||",
                "Eq": "==",
                "NotEq": "!=",
                "Lt": "<",
                "Gt": ">",
                "LtE": "<=",
                "GtE": ">="
            }

            op = op_map.get(expr.operator, "==")

            return f"{self._generate_expr(expr.left)} {op} {self._generate_expr(expr.right)}"

        if isinstance(expr, ArrayLiteral):

            elements = ", ".join(self._generate_expr(e) for e in expr.elements)

            if not expr.elements:
                return "new ArrayList<>()"

            element_type = self._infer_type(expr.elements[0])

            wrapper_map = {
                "int": "Integer",
                "float": "Double",
                "bool": "Boolean",
                "str": "String"
            }

            element_type = wrapper_map.get(element_type, element_type)

            return f"new ArrayList<{element_type}>(Arrays.asList({elements}))"
                
        if isinstance(expr, Input):
            return "sc.nextLine()"
        
        if isinstance(expr, FunctionCall):

            arg_types = []

            for arg in expr.args:
                arg_types.append(self._infer_type(arg))

            # store argument types
            if expr.name not in self.function_param_types:
                self.function_param_types[expr.name] = arg_types

            args = ", ".join(self._generate_expr(a) for a in expr.args)

            return f"{expr.name}({args})"
        
        if isinstance(expr, DictAccess):
            return f"{self._generate_expr(expr.dictionary)}.get({self._generate_expr(expr.key)})"

        if isinstance(expr, ObjectCreation):
            return f"new {expr.class_name}()"

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
                "discard": "remove"
            }

            java_method = method_map.get(expr.method, expr.method)

            args = ", ".join(self._generate_expr(a) for a in expr.args)

            if expr.method == "remove":

                arg = self._generate_expr(expr.args[0])

                # Force wrapper for list removal
                return f"{self._generate_expr(expr.obj)}.remove(Integer.valueOf({arg}))"
            return f"{self._generate_expr(expr.obj)}.{java_method}({args})"

        return "null"

    # -------------------------------------------------
    # SIMPLE TYPE INFERENCE
    # -------------------------------------------------

    def _infer_type(self, value):

        if isinstance(value, FunctionCall):
            return self.function_returns.get(value.name, "Object")
        # -------- CONSTANT --------
        if isinstance(value, Constant):

            if isinstance(value.value, int):
                return "int"

            if isinstance(value.value, float):
                return "float"

            if isinstance(value.value, bool):
                return "bool"

            if isinstance(value.value, str):
                return "str"

        # -------- ARRAY LITERAL --------
        if isinstance(value, ArrayLiteral):

            if not value.elements:
                return "List<Object>"

            first_type = self._infer_type(value.elements[0])

            primitive_map = {
                    "int": "Integer",
                    "float": "Double",
                    "bool": "Boolean",
                    "str": "String"
            }

            wrapper = primitive_map.get(first_type, "Object")

            return f"List<{wrapper}>"

        # -------- IDENTIFIER --------
        if isinstance(value, Identifier):
            var_type = self.symbol_table.lookup(value.name)
            if var_type:
                return var_type

        # -------- BINARY OP --------
        if isinstance(value, BinaryOp):
            left_type = self._infer_type(value.left)
            right_type = self._infer_type(value.right)

            if left_type == "double" or right_type == "double":
                return "float"

            return "int"
        
        if isinstance(value, SetLiteral):

            if not value.elements:
                return "Set<Object>"

            element_type = self._infer_type(value.elements[0])

            mapped_type = self.mapper.map(
                element_type,
                self.source_lang,
                self.target_lang
            )

            wrapper = self._to_wrapper(mapped_type)

            return f"Set<{wrapper}>"

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
    def _collect_function_calls(self, program):

        def scan(node):

            if isinstance(node, FunctionCall):

                arg_types = []

                for arg in node.args:
                    arg_types.append(self._infer_type(arg))

                if node.name not in self.function_param_types:
                    self.function_param_types[node.name] = arg_types

            if hasattr(node, "__dict__"):
                for value in node.__dict__.values():

                    if isinstance(value, list):
                        for item in value:
                            scan(item)

                    else:
                        scan(value)

        for node in program.body:
            scan(node)
    def _fix_java_generics(self, type_str):

        replacements = {
            "List<int>": "List<Integer>",
            "List<float>": "List<Double>",
            "List<bool>": "List<Boolean>",
            "List<char>": "List<Character>",

            "Set<int>": "Set<Integer>",
            "Set<float>": "Set<Double>",
            "Set<bool>": "Set<Boolean>",

            "Map<int,": "Map<Integer,",
            "Map<float,": "Map<Double,",
            "Map<bool,": "Map<Boolean,"
        }

        for k, v in replacements.items():
            type_str = type_str.replace(k, v)

        return type_str
    def _infer_list_element_type(self, func, list_name):

        for stmt in func.body:

            # detect append usage
            if isinstance(stmt, ListAppend):

                if isinstance(stmt.list_obj, Identifier) and stmt.list_obj.name == list_name:

                    element_type = self._infer_type(stmt.value)

                    return self._to_wrapper(element_type)

            # detect for loop usage
            if isinstance(stmt, ForLoop):

                if isinstance(stmt.iterable, Identifier) and stmt.iterable.name == list_name:

                    # inspect loop body
                    for inner in stmt.body:

                        if isinstance(inner, ListAppend):

                            element_type = self._infer_type(inner.value)

                            return self._to_wrapper(element_type)

        return "Object"