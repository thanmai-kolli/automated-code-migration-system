import re
from core.ir_nodes import *

class CGenerator:

    def __init__(self, source=None, target=None):
        self.source = source
        self.target = target

    def generate(self, program):

        code = ""

        for node in program.body:
            code += self._convert_block(node.body)

        return code

    # -----------------------------------------
    # Convert C++ constructs back to C
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
                if part.startswith('"') and part.endswith('"'):
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