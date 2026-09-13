# import re


# class JavaTransformer:

#     def transform(self, code):

#         # Replace legacy collections
#         code = re.sub(r"\bVector\b", "ArrayList", code)
#         code = re.sub(r"\bHashtable\b", "HashMap", code)

#         # Replace boxing
#         code = re.sub(r"new\s+Integer\((.*?)\)", r"Integer.valueOf(\1)", code)
#         code = re.sub(r"new\s+Double\((.*?)\)", r"Double.valueOf(\1)", code)

#         # Apply diamond operator
#         code = re.sub(r"new\s+ArrayList<[^>]+>\(\)", "new ArrayList<>()", code)
#         code = re.sub(r"new\s+HashMap<[^>]+>\(\)", "new HashMap<>()", code)

#         return code
# import re


# class JavaTransformer:

#     def transform(self, code):

#         # ---------------------------------------------
#         # 1️⃣ Legacy Collection Replacement
#         # ---------------------------------------------
#         code = re.sub(r"\bVector\b", "ArrayList", code)
#         code = re.sub(r"\bHashtable\b", "HashMap", code)

#         # ---------------------------------------------
#         # 2️⃣ Boxing Replacement
#         # ---------------------------------------------
#         code = re.sub(r"new\s+Integer\((.*?)\)", r"Integer.valueOf(\1)", code)
#         code = re.sub(r"new\s+Double\((.*?)\)", r"Double.valueOf(\1)", code)

#         # ---------------------------------------------
#         # 3️⃣ Diamond Operator
#         # ---------------------------------------------
#         code = re.sub(r"new\s+ArrayList<[^>]+>\(\)", "new ArrayList<>()", code)
#         code = re.sub(r"new\s+HashMap<[^>]+>\(\)", "new HashMap<>()", code)

#         # ---------------------------------------------
#         # 4️⃣ Anonymous Runnable → Lambda
#         # ---------------------------------------------
#         code = re.sub(
#             r"new\s+Runnable\s*\(\)\s*\{\s*public\s+void\s+run\s*\(\)\s*\{\s*(.*?)\s*\}\s*\}",
#             r"() -> { \1 }",
#             code,
#             flags=re.DOTALL
#         )

#         # ---------------------------------------------
#         # 5️⃣ Anonymous Comparator → Lambda
#         # ---------------------------------------------
#         code = re.sub(
#             r"new\s+Comparator<[^>]+>\s*\(\)\s*\{\s*public\s+int\s+compare\s*\(\s*(.*?)\s*,\s*(.*?)\s*\)\s*\{\s*(.*?)\s*\}\s*\}",
#             r"(\1, \2) -> { \3 }",
#             code,
#             flags=re.DOTALL
#         )

#         # ---------------------------------------------
#         # 6️⃣ Simple for-loop → Stream forEach
#         # Pattern:
#         # for (Type var : collection) {
#         #     System.out.println(var);
#         # }
#         # ---------------------------------------------
#         code = re.sub(
#             r"for\s*\(\s*\w+\s+(\w+)\s*:\s*(\w+)\s*\)\s*\{\s*System\.out\.println\(\1\);\s*\}",
#             r"\2.stream().forEach(\1 -> System.out.println(\1));",
#             code
#         )

#         # ---------------------------------------------
#         # 7️⃣ Classic index loop → Stream
#         # Pattern:
#         # for (int i = 0; i < list.size(); i++)
#         # ---------------------------------------------
#         code = re.sub(
#             r"for\s*\(\s*int\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\w+)\.size\(\)\s*;\s*\w+\+\+\s*\)",
#             r"\1.stream().forEach",
#             code
#         )

#         return code
import javalang


class JavaTransformer:

    def transform(self, code):

        try:
            tree = javalang.parse.parse(code)
        except:
            return code

        return self._generate_compilation_unit(tree)

    # ------------------------------------------------------------
    # Compilation Unit
    # ------------------------------------------------------------

    def _generate_compilation_unit(self, tree):

        code = ""

        if tree.package:
            code += f"package {tree.package.name};\n\n"

        for imp in tree.imports:
            code += f"import {imp.path};\n"

        if tree.imports:
            code += "\n"

        for type_decl in tree.types:
            code += self._generate_type(type_decl)

        return code

    # ------------------------------------------------------------
    # Type Dispatcher
    # ------------------------------------------------------------

    def _generate_type(self, node):

        if isinstance(node, javalang.tree.ClassDeclaration):
            return self._generate_class(node)

        if isinstance(node, javalang.tree.InterfaceDeclaration):
            return self._generate_interface(node)

        if isinstance(node, javalang.tree.EnumDeclaration):
            return self._generate_enum(node)

        return ""

    # ------------------------------------------------------------
    # Class (Supports Nested)
    # ------------------------------------------------------------

    def _generate_class(self, node):

        generics = self._generate_generics(node.type_parameters)

        code = f"public class {node.name}{generics} {{\n"

        for member in node.body:
            code += self._generate_member(member)

        code += "}\n\n"
        return code

    # ------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------

    def _generate_interface(self, node):

        generics = self._generate_generics(node.type_parameters)

        code = f"public interface {node.name}{generics} {{\n"

        for member in node.body:
            code += self._generate_member(member)

        code += "}\n\n"
        return code

    # ------------------------------------------------------------
    # Enum
    # ------------------------------------------------------------

    def _generate_enum(self, node):

        constants = ", ".join(c.name for c in node.body.constants)

        code = f"public enum {node.name} {{ {constants} }}\n\n"
        return code

    # ------------------------------------------------------------
    # Members
    # ------------------------------------------------------------

    def _generate_member(self, node):

        if isinstance(node, javalang.tree.FieldDeclaration):
            return self._generate_field(node)

        if isinstance(node, javalang.tree.MethodDeclaration):
            return self._generate_method(node)

        if isinstance(node, javalang.tree.ConstructorDeclaration):
            return self._generate_constructor(node)

        if isinstance(node, javalang.tree.ClassDeclaration):
            return self._generate_class(node)  # Nested class

        return ""

    # ------------------------------------------------------------
    # Field
    # ------------------------------------------------------------

    def _generate_field(self, node):

        type_name = self._upgrade_type(node.type)

        code = ""
        for decl in node.declarators:
            code += f"    private {type_name} {decl.name};\n"

        return code

    # ------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------

    def _generate_constructor(self, node):

        params = []

        for p in node.parameters:
            param_type = self._upgrade_type(p.type)
            params.append(f"{param_type} {p.name}")

        code = f"    public {node.name}({', '.join(params)}) {{\n"

        if node.body:
            for stmt in node.body:
                code += self._generate_statement(stmt)

        code += "    }\n"
        return code

    # ------------------------------------------------------------
    # Method
    # ------------------------------------------------------------

    def _generate_method(self, node):

        return_type = self._upgrade_type(node.return_type) if node.return_type else "void"

        generics = self._generate_generics(node.type_parameters)

        params = []
        for p in node.parameters:
            param_type = self._upgrade_type(p.type)
            params.append(f"{param_type} {p.name}")

        code = f"    public {generics}{return_type} {node.name}({', '.join(params)}) {{\n"

        if node.body:
            for stmt in node.body:
                code += self._generate_statement(stmt)

        code += "    }\n"
        return code

    # ------------------------------------------------------------
    # Statements (Try/Catch + Lambda)
    # ------------------------------------------------------------

    def _generate_statement(self, stmt):

        if isinstance(stmt, javalang.tree.ReturnStatement):
            return f"        return {self._generate_expression(stmt.expression)};\n"

        if isinstance(stmt, javalang.tree.StatementExpression):
            return f"        {self._generate_expression(stmt.expression)};\n"

        if isinstance(stmt, javalang.tree.TryStatement):

            code = "        try {\n"

            for s in stmt.block:
                code += self._generate_statement(s)

            code += "        }"

            for catch in stmt.catches:
                param_type = self._upgrade_type(catch.parameter.type)
                param_name = catch.parameter.name

                code += f" catch ({param_type} {param_name}) {{\n"
                for s in catch.block:
                    code += self._generate_statement(s)
                code += "        }"

            code += "\n"
            return code

        return ""

    # ------------------------------------------------------------
    # Expressions (Includes Lambda)
    # ------------------------------------------------------------

    def _generate_expression(self, expr):

        if isinstance(expr, javalang.tree.Literal):
            return expr.value

        if isinstance(expr, javalang.tree.MemberReference):
            return expr.member

        if isinstance(expr, javalang.tree.BinaryOperation):
            return f"{self._generate_expression(expr.operandl)} {expr.operator} {self._generate_expression(expr.operandr)}"

        if isinstance(expr, javalang.tree.MethodInvocation):
            args = ", ".join(self._generate_expression(a) for a in expr.arguments)
            return f"{expr.member}({args})"

        if isinstance(expr, javalang.tree.LambdaExpression):
            params = ", ".join(p.name for p in expr.parameters)
            body = self._generate_expression(expr.body)
            return f"({params}) -> {body}"

        return ""

    # ------------------------------------------------------------
    # Generics
    # ------------------------------------------------------------

    def _generate_generics(self, type_params):

        if not type_params:
            return ""

        params = ", ".join(p.name for p in type_params)
        return f"<{params}>"

    # ------------------------------------------------------------
    # Type Upgrade Logic
    # ------------------------------------------------------------

    def _upgrade_type(self, type_node):

        if not type_node:
            return "void"

        name = type_node.name

        # Modernization rules
        if name == "Vector":
            return "ArrayList"
        if name == "Hashtable":
            return "HashMap"

        return name