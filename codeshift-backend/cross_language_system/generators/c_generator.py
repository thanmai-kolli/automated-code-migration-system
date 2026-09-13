import re
from cross_language_system.core.ir_nodes import *
from cross_language_system.generators.c_family import CFamilyGenerator


class CGenerator(CFamilyGenerator):

    cpp = False

    def __init__(self, source=None, target=None):
        super().__init__(source, target)
        self.array_lengths = set()

    def generate(self, program):

        # The C++ parser emits raw source chunks; everything else emits a real IR.
        if any(isinstance(getattr(n, "body", None), str) for n in program.body):
            return "".join(self._convert_block(n.body) for n in program.body)

        return self.generate_from_ir(program)

    # -----------------------------------------
    # C ARRAYS
    # -----------------------------------------

    def statement(self, stmt, indent):

        tab = "    " * indent

        # A list literal becomes a fixed array plus its length.
        if (
            isinstance(stmt, Variable)
            and isinstance(stmt.value, ArrayLiteral)
            and stmt.name not in self.scope
        ):
            element = self.type_of(self._element_of(stmt.var_type))
            elements = ", ".join(self.expr(e) for e in stmt.value.elements)
            self.scope[stmt.name] = f"{element}*"
            self.array_lengths.add(stmt.name)
            return (
                f"{tab}{element} {stmt.name}[] = {{{elements}}};\n"
                f"{tab}int {stmt.name}_length = {len(stmt.value.elements)};\n"
            )

        return super().statement(stmt, indent)

    @staticmethod
    def _element_of(type_name):
        if isinstance(type_name, str) and type_name.startswith(("List<", "Set<")):
            return CGenerator._unbox(type_name[type_name.index("<") + 1:-1])
        return "int"

    def expr(self, node):

        # Every array argument is followed by its length.
        if isinstance(node, FunctionCall):
            args = []
            for arg in node.args:
                args.append(super().expr(arg))
                if isinstance(arg, Identifier) and arg.name in self.array_lengths:
                    args.append(f"{arg.name}_length")
            return f"{node.name}({', '.join(args)})"

        if isinstance(node, MethodCall) and node.method == "size":
            if isinstance(node.obj, Identifier) and node.obj.name in self.array_lengths:
                return f"{node.obj.name}_length"

        return super().expr(node)

    # -----------------------------------------
    # IR PATH
    # -----------------------------------------

    def headers(self, program):
        return "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n\n"

    def interpolation(self, node):
        # C has no string concatenation operator; fall back to the literal text.
        literal = "".join(
            part.value for part in node.parts
            if isinstance(part, Constant) and isinstance(part.value, str)
        )
        return self.constant(literal)

    FORMATS = {"int": "%d", "double": "%f", "char*": "%s", "string": "%s"}

    def print_statement(self, stmt, indent):

        tab = "    " * indent
        if not stmt.args:
            return f'{tab}printf("\\n");\n'

        specifiers = []
        values = []

        for arg in stmt.args:
            if isinstance(arg, Constant) and isinstance(arg.value, str):
                specifiers.append(arg.value.replace("%", "%%"))
                continue
            specifiers.append(self.FORMATS.get(self._static_type(arg), "%d"))
            values.append(self.expr(arg))

        fmt = " ".join(specifiers) + "\\n"
        if values:
            return f'{tab}printf("{fmt}", {", ".join(values)});\n'
        return f'{tab}printf("{fmt}");\n'

    def _static_type(self, expr):
        if isinstance(expr, Constant):
            if isinstance(expr.value, bool):
                return "int"
            if isinstance(expr.value, int):
                return "int"
            if isinstance(expr.value, float):
                return "double"
            if isinstance(expr.value, str):
                return "char*"
        if isinstance(expr, Identifier):
            return self.scope.get(expr.name, "int")
        return "int"

    def render_class(self, cls):
        """C has no classes: emit a struct plus self-taking functions."""

        previous = self.current_class
        self.current_class = cls

        code = "typedef struct {\n"
        for field in cls.fields:
            code += f"    {self.type_of(field.field_type)} {field.name};\n"
        if not cls.fields:
            code += "    char _unused;\n"
        code += f"}} {cls.name};\n\n"

        for method in cls.methods:
            code += self.render_function(method, owner=cls)

        self.current_class = previous
        return code

    def render_function(self, func, indent=0, owner=None):

        tab = "    " * indent
        outer_scope = self.scope
        self.scope = dict(outer_scope)

        params = []

        if owner and not func.is_static:
            params.append(f"{owner.name}* self")
            self.scope["self"] = f"{owner.name}*"

        for p in func.params:
            declared = func.param_types.get(p, "Object")
            rendered = self.type_of(declared)
            params.append(f"{rendered} {p}")
            self.scope[p] = rendered

            # C arrays decay to pointers, so the length has to travel with them.
            if str(declared).startswith(("List<", "Set<")):
                params.append(f"int {p}_length")
                self.array_lengths.add(p)

        signature = ", ".join(params) or "void"

        if func.is_constructor and owner:
            name = f"{owner.name}_init"
            return_type = "void"
        else:
            name = f"{owner.name}_{func.name}" if owner else func.name
            return_type = self.type_of(func.return_type)

        code = f"{tab}{return_type} {name}({signature}) {{\n"

        for stmt in func.body:
            code += self.statement(stmt, indent + 1)

        self.scope = outer_scope
        return code + f"{tab}}}\n\n"

    # -----------------------------------------
    # Convert C++ constructs back to C (text path)
    # -----------------------------------------
    def _convert_block(self, text):

        code = text

        # ------------------------------
        # Header conversion
        # ------------------------------
        code = code.replace("<iostream>", "<stdio.h>")
        code = code.replace("<cstdlib>", "<stdlib.h>")
        code = code.replace("<cstring>", "<string.h>")

        code = code.replace("using namespace std;", "")


        # ------------------------------
        # cin → scanf
        # ------------------------------
        code = re.sub(
            r'cin\s*>>\s*(\w+)\s*;',
            r'scanf("%d", &\1);',
            code
        )

        # ------------------------------
        # new → malloc
        # ------------------------------
        code = re.sub(
            r'(\w+)\s*=\s*new\s+(\w+)\[(\w+)\];',
            r'\1 = (\2*) malloc(sizeof(\2) * \3);',
            code
        )

        # ------------------------------
        # delete[] → free
        # ------------------------------
        code = re.sub(
            r'delete\[\]\s*(\w+);',
            r'free(\1);',
            code
        )

        # ------------------------------
        # nullptr → NULL
        # ------------------------------
        code = code.replace("nullptr", "NULL")

        

        # ------------------------------
        # General cout → printf (Improved)
        # ------------------------------
        def replace_cout(match):
            full = match.group(1).strip()

            # Split chained << parts
            parts = [p.strip() for p in full.split("<<")]

            format_string = ""
            variables = []

            for part in parts:
                if part in ("endl", "std::endl"):
                    format_string += "\\n"
                elif part.startswith('"') and part.endswith('"'):
                    # string literal
                    format_string += part.strip('"')
                else:
                    # assume integer variable/expression
                    format_string += "%d"
                    variables.append(part)

            if variables:
                vars_joined = ", ".join(variables)
                return f'printf("{format_string}", {vars_joined});'
            else:
                return f'printf("{format_string}");'

        code = re.sub(
            r'cout\s*<<\s*(.*?);',
            replace_cout,
            code
        )

        return code + "\n\n"