import re
from cross_language_system.core.ir_nodes import *


class CppGenerator:

    def __init__(self, source=None, target=None):
        self.source = source
        self.target = target


    def generate(self, program):

        code = ""

        for node in program.body:
            code += self._convert_block(node.body)

        return code

    # -----------------------------------------
    # Convert C constructs to C++
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