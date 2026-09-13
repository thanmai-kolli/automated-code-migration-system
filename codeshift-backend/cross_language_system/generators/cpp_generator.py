import re
from cross_language_system.core.ir_nodes import *
from cross_language_system.generators.c_family import CFamilyGenerator


class CppGenerator(CFamilyGenerator):

    cpp = True

    def __init__(self, source=None, target=None):
        super().__init__(source, target)

    def generate(self, program):

        # The C parser emits raw source chunks; everything else emits a real IR.
        if any(isinstance(getattr(n, "body", None), str) for n in program.body):
            return "".join(self._convert_block(n.body) for n in program.body)

        return self.generate_from_ir(program)

    # -----------------------------------------
    # IR PATH
    # -----------------------------------------

    def headers(self, program, body):

        code = "#include <iostream>\n#include <string>\n#include <vector>\n#include <map>\n"

        if "_split(" in body:
            code += "#include <sstream>\n"

        code += "using namespace std;\n\n"

        if "_split(" in body:
            code += (
                "vector<string> _split(const string& text) {\n"
                "    vector<string> parts;\n"
                "    istringstream stream(text);\n"
                "    string token;\n"
                "    while (stream >> token) parts.push_back(token);\n"
                "    return parts;\n"
                "}\n\n"
            )

        return code

    def method_call(self, node):

        # C++ has no string::split, so the generator supplies one.
        if node.method == "split" and not node.args:
            return f"_split({self.expr(node.obj)})"

        return super().method_call(node)

    def interpolation(self, node):

        parts = []
        for part in node.parts:
            if isinstance(part, Constant) and isinstance(part.value, str):
                if part.value:
                    parts.append(self.constant(part.value))
            else:
                parts.append(f"to_string({self.expr(part)})")

        return " + ".join(parts) if parts else '""'

    def print_statement(self, stmt, indent):

        tab = "    " * indent
        if not stmt.args:
            return f"{tab}cout << endl;\n"

        pieces = ' << " " << '.join(self.expr(a) for a in stmt.args)
        return f"{tab}cout << {pieces} << endl;\n"

    def render_class(self, cls):

        previous = self.current_class
        self.current_class = cls

        base = f" : public {cls.base}" if cls.base else ""
        code = f"class {cls.name}{base} {{\npublic:\n"

        for field in cls.fields:
            code += f"    {self.type_of(field.field_type)} {field.name};\n"

        if cls.fields:
            code += "\n"

        for method in cls.methods:
            code += self.render_function(method, indent=1, owner=cls)

        code += "};\n\n"
        self.current_class = previous
        return code

    def render_function(self, func, indent=0, owner=None):

        tab = "    " * indent
        outer_scope = self.scope
        self.scope = dict(outer_scope)

        params = []
        for p in func.params:
            rendered = self.type_of(func.param_types.get(p, "Object"))
            params.append(f"{rendered} {p}")
            self.scope[p] = rendered

        if owner:
            for field in owner.fields:
                self.scope[field.name] = self.type_of(field.field_type)

        signature = ", ".join(params)
        return_type = self.type_of(func.return_type)

        # C++ has no Object root type, so an unresolved element type becomes a
        # template parameter rather than an invalid vector<auto>.
        prefix = ""
        if "auto" in signature and "<auto>" in signature:
            signature = signature.replace("<auto>", "<T>")
            return_type = return_type.replace("<auto>", "<T>")
            prefix = f"{tab}template <typename T>\n"

        if func.is_constructor and owner:
            code = f"{prefix}{tab}{owner.name}({signature}) {{\n"
        else:
            code = f"{prefix}{tab}{return_type} {func.name}({signature}) {{\n"

        for stmt in func.body:
            code += self.statement(stmt, indent + 1)

        self.scope = outer_scope
        return code + f"{tab}}}\n\n"
    # -----------------------------------------
    # Convert C constructs to C++ (text path)
    # -----------------------------------------
    def _convert_block(self, text):

        code = text

        # ------------------------------
        # Headers conversion
        # ------------------------------
        code = code.replace("<stdio.h>", "<iostream>")
        code = code.replace("<stdlib.h>", "<cstdlib>")
        code = code.replace("<string.h>", "<cstring>")

        if "#include <iostream>" in code and "using namespace std;" not in code:
            code = code.replace(
                "#include <iostream>",
                "#include <iostream>\nusing namespace std;"
            )

        # ------------------------------
        # printf → cout
        # ------------------------------
        code = re.sub(
            r'printf\("([^"]*)"(?:,\s*(.*?))?\);',
            self._convert_printf,
            code
        )

        # ------------------------------
        # scanf → cin
        # ------------------------------
        code = re.sub(
            r'scanf\("([^"]*)",\s*(.*?)\);',
            self._convert_scanf,
            code
        )

        # ------------------------------
        # malloc → new
        # ------------------------------
        code = re.sub(
            r'(\w+)\s*=\s*\((\w+)\*\)\s*malloc\(sizeof\(\w+\)\s*\*\s*(\w+)\);',
            r'\1 = new \2[\3];',
            code
        )

        code = re.sub(
            r'(\w+)\s*=\s*\((\w+)\*\)\s*calloc\((\w+),\s*sizeof\(\w+\)\);',
            r'\1 = new \2[\3]();',
            code
        )

        # ------------------------------
        # free → delete[]
        # ------------------------------
        code = re.sub(
            r'free\((\w+)\);',
            r'delete[] \1;',
            code
        )

        # ------------------------------
        # NULL → nullptr
        # ------------------------------
        code = code.replace("NULL", "nullptr")

        # ------------------------------
        # gets → getline
        # ------------------------------
        code = re.sub(
            r'gets\((\w+)\);',
            r'getline(cin, \1);',
            code
        )

        # ------------------------------
        # puts → cout
        # ------------------------------
        code = re.sub(
            r'puts\("([^"]*)"\);',
            r'cout << "\1" << endl;',
            code
        )

        

        return code + "\n\n"

    # -----------------------------------------
    # printf conversion
    # -----------------------------------------
    def _convert_printf(self, match):

        format_string = match.group(1)
        variables = match.group(2)

        parts = re.split(r'(%[dfs])', format_string)
        result = "cout"

        var_list = []
        if variables:
            var_list = [v.strip() for v in variables.split(",")]

        var_index = 0

        for part in parts:
            if part in ("%d", "%f", "%s"):
                if var_index < len(var_list):
                    result += f" << {var_list[var_index]}"
                    var_index += 1
            else:
                if part:
                    result += f' << "{part}"'

        result += ";"
        return result

    # -----------------------------------------
    # scanf conversion
    # -----------------------------------------
    def _convert_scanf(self, match):

        variables = match.group(2)
        var_list = [v.strip().replace("&", "") for v in variables.split(",")]

        result = "cin"
        for var in var_list:
            result += f" >> {var}"

        result += ";"
        return result