from cross_language_system.core.ir_nodes import *
from cross_language_system.core.symbol_table import SymbolTable
from cross_language_system.core.type_mapper import TypeMapper


class JavaGenerator:

    def __init__(self, source_lang, target_lang):
        self.source_lang = source_lang.lower()
        self.target_lang = target_lang.lower()
        self.mapper = TypeMapper()
        self.symbol_table = SymbolTable()
        
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

    @staticmethod
    def _escape(text):
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )

    # -------------------------------------------------
    # ENTRY POINT
    # -------------------------------------------------

    def generate(self, program):

        uses_input = self._program_uses_input(program)
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
            # Only a zero-argument function can be invoked without inventing values.
            first_function = None

            for node in program.body:
                if isinstance(node, Function) and len(node.params) == 0:
                    first_function = node.name
                    break

            if first_function:
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

        previous_class = getattr(self, "current_class", None)
        self.current_class = cls

        extends = f" extends {cls.base}" if cls.base else ""
        code = f"    public static class {cls.name}{extends} {{\n"

        for field in cls.fields:
            code += f"        private {self._java_type(field.field_type)} {field.name};\n"

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
            params.append(f"{param_type} {p}")
            self.symbol_table.register_variable(p, param_type)

        if owner:
            for field in owner.fields:
                self.symbol_table.register_variable(field.name, self._java_type(field.field_type))

        signature = ", ".join(params)

        if func.is_constructor and owner:
            code = f"{tab}public {owner.name}({signature}) {{\n"
        else:
            return_type = self._java_type(func.return_type)
            self.function_returns[func.name] = return_type
            modifier = "public" if owner else "public static"
            code = f"{tab}{modifier} {return_type} {func.name}({signature}) {{\n"

        for stmt in func.body:
            code += self._generate_statement(stmt, indent + 1)

        code += f"{tab}}}\n\n"

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
            "float": "double",
            "double": "double",
            "bool": "boolean",
            "boolean": "boolean",
            "str": "String",
            "String": "String",
        }

        if type_name in direct:
            return direct[type_name]

        if type_name.startswith(("List<", "Map<", "Set<")):
            return type_name

        mapped = self.mapper.map(type_name, self.source_lang, self.target_lang)
        return mapped or "Object"

    # -------------------------------------------------
    # STATEMENTS
    # -------------------------------------------------

    def _generate_statement(self, stmt, indent):

        tab = "    " * indent

        if isinstance(stmt, Pass):
            return ""

        if isinstance(stmt, Break):
            return f"{tab}break;\n"

        if isinstance(stmt, Continue):
            return f"{tab}continue;\n"

        if isinstance(stmt, Assignment):
            return f"{tab}{self._generate_expr(stmt.target)} = {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, AugAssign):
            op_map = {"Add": "+=", "Sub": "-=", "Mult": "*=", "Div": "/=", "Mod": "%="}
            op = op_map.get(stmt.operator, "+=")
            return f"{tab}{self._generate_expr(stmt.target)} {op} {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, TryCatch):
            exception = stmt.exception_type or "Exception"
            code = f"{tab}try {{\n"
            for s in stmt.try_body:
                code += self._generate_statement(s, indent + 1)
            code += f"{tab}}} catch ({exception} {stmt.catch_var or 'e'}) {{\n"
            for s in stmt.catch_body:
                code += self._generate_statement(s, indent + 1)
            code += f"{tab}}}\n"
            return code

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

            # The annotator already resolved this declaration's type.
            java_type = self._fix_java_generics(self._java_type(stmt.var_type))

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
            if stmt.value is None:
                return f"{tab}return;\n"
            return f"{tab}return {self._generate_expr(stmt.value)};\n"

        if isinstance(stmt, IfStatement):

            code = f"{tab}if ({self._generate_expr(stmt.condition)}) {{\n"

            for s in stmt.body:
                code += self._generate_statement(s, indent + 1)

            if stmt.else_body:
                # A lone nested if is an elif in the source; keep it as else-if.
                if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
                    nested = self._generate_statement(stmt.else_body[0], indent).lstrip()
                    return code + f"{tab}}} else {nested}"

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
                # Python's print separates its arguments with a space.
                final_expr = ' + " " + '.join(parts)

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

        if expr is None:
            return "null"

        if isinstance(expr, SelfRef):
            return "this"

        if isinstance(expr, AttributeAccess):
            return f"{self._generate_expr(expr.obj)}.{expr.attribute}"

        if isinstance(expr, UnaryOp):
            op_map = {"USub": "-", "UAdd": "+", "Not": "!", "Invert": "~"}
            operand = self._generate_expr(expr.operand)
            if isinstance(expr.operand, (BinaryOp, BooleanOp, TernaryOp)):
                operand = f"({operand})"
            return f"{op_map.get(expr.operator, '-')}{operand}"

        if isinstance(expr, TernaryOp):
            return (
                f"{self._generate_expr(expr.condition)} ? "
                f"{self._generate_expr(expr.if_true)} : "
                f"{self._generate_expr(expr.if_false)}"
            )

        if isinstance(expr, StringInterpolation):
            parts = []
            for part in expr.parts:
                if isinstance(part, Constant) and isinstance(part.value, str):
                    if part.value:
                        parts.append(f'"{self._escape(part.value)}"')
                else:
                    parts.append(self._generate_expr(part))
            return " + ".join(parts) if parts else '""'

        if isinstance(expr, IndexAccess):
            container = self._generate_expr(expr.obj)
            index = self._generate_expr(expr.index)
            container_type = self.symbol_table.lookup(container) or ""
            if container_type.startswith("Map<"):
                return f"{container}.get({index})"
            return f"{container}.get({index})"

        if isinstance(expr, TypeCast):

            inner = self._generate_expr(expr.value)

            if expr.target_type == "int":
                return f"Integer.parseInt({inner})"

            if expr.target_type == "float":
                return f"Double.parseDouble({inner})"

            return inner

        if isinstance(expr, Constant):

            if expr.value is None:
                return "null"

            if isinstance(expr.value, bool):
                return str(expr.value).lower()

            if isinstance(expr.value, str):
                return f'"{self._escape(expr.value)}"'

            return str(expr.value)

        if isinstance(expr, Identifier):
            return expr.name

        if isinstance(expr, BinaryOp):

            op_map = {
                "Add": "+",
                "Sub": "-",
                "Mult": "*",
                "Div": "/",
                "FloorDiv": "/",
                "Mod": "%",
                "Pow": "^"
            }

            operator = op_map.get(expr.operator, "+")
            left = self._generate_expr(expr.left)
            right = self._generate_expr(expr.right)

            # Python's / is always float division; Java's / on two ints is not.
            if (
                expr.operator == "Div"
                and self.source_lang == "python"
                and self._infer_type(expr.left) in ("int", "Integer")
                and self._infer_type(expr.right) in ("int", "Integer")
            ):
                left = f"(double) {left}"

            return f"{left} {operator} {right}"

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
            args = ", ".join(self._generate_expr(a) for a in expr.args)
            return f"{expr.name}({args})"

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
                "discard": "remove"
            }

            java_method = method_map.get(expr.method, expr.method)

            args = ", ".join(self._generate_expr(a) for a in expr.args)

            # Python's bare split() tokenises on any whitespace; wrapping the
            # resulting String[] keeps it indexable like every other list.
            if expr.method == "split" and not expr.args:
                return (
                    f'Arrays.asList({self._generate_expr(expr.obj)}'
                    f'.trim().split("\\\\s+"))'
                )

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

        if isinstance(value, MethodCall):
            return "int" if value.method == "size" else "Object"

        if isinstance(value, UnaryOp):
            return "boolean" if value.operator == "Not" else self._infer_type(value.operand)

        if isinstance(value, AttributeAccess):
            current = getattr(self, "current_class", None)
            if current:
                for field in current.fields:
                    if field.name == value.attribute:
                        return self._java_type(field.field_type)
            return "Object"

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