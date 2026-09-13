from cross_language_system.core.ir_nodes import *
import re


class CParser:
    """
    Advanced Lightweight C Parser
    - Preserves macros
    - Preserves includes
    - Extracts globals
    - Extracts full functions with brace matching
    """

    def parse(self, code):

        includes = []
        macros = []
        globals_code = []
        functions = []

        lines = code.splitlines()


        # -----------------------------
        # 1️⃣ Extract Includes & Macros
        # -----------------------------
        for line in lines:
            stripped = line.strip()

            if stripped.startswith("#include"):
                includes.append(line)

            elif stripped.startswith("#define"):
                macros.append(line)

        # Remove includes/macros for function scanning
        cleaned_code = "\n".join(
            line for line in lines
            if not line.strip().startswith("#")
        )

         # 3️⃣ NOW extract structs (after cleaned_code exists)
        struct_pattern = r'struct\s+[a-zA-Z_]\w*\s*\{'
        struct_matches = list(re.finditer(struct_pattern, cleaned_code))

        struct_ranges = []

        for match in struct_matches:
            start = match.start()
            brace_count = 0
            end = None

            for i in range(start, len(cleaned_code)):
                if cleaned_code[i] == "{":
                    brace_count += 1
                elif cleaned_code[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            if end:
                struct_text = cleaned_code[start:end]
                if not struct_text.endswith(";"):
                    struct_text += ";"

                functions.append(struct_text)
                struct_ranges.append((start, end))

        # remove struct blocks before function scanning
        for start, end in sorted(struct_ranges, reverse=True):
            cleaned_code = cleaned_code[:start] + cleaned_code[end:]
            
        # -----------------------------
        # 2️⃣ Extract Functions
        # -----------------------------
        function_pattern = r'([a-zA-Z_][\w\s\*]*?)\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{'
        matches = list(re.finditer(function_pattern, cleaned_code))

        used_ranges = []

        for match in matches:

            start = match.start()
            brace_count = 0
            end = None

            for i in range(start, len(cleaned_code)):
                if cleaned_code[i] == "{":
                    brace_count += 1
                elif cleaned_code[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        temp = end
                        while temp < len(cleaned_code) and cleaned_code[temp].isspace():
                            temp += 1

                        # If next non-space character is ';', include it
                        if temp < len(cleaned_code) and cleaned_code[temp] == ";":
                            end = temp + 1
                        break

            if end:
                function_text = cleaned_code[start:end]
                functions.append(function_text)
                used_ranges.append((start, end))

        # -----------------------------
        # 3️⃣ Extract Globals
        # -----------------------------
        remaining_code = cleaned_code

        for start, end in sorted(used_ranges, reverse=True):
            remaining_code = remaining_code[:start] + remaining_code[end:]

        for line in remaining_code.splitlines():
            stripped = line.strip()
            if stripped and stripped != ";" and ";" in stripped:
                globals_code.append(line)

        # -----------------------------
        # 4️⃣ Store Everything in IR
        # -----------------------------
        program_body = []

        # Store includes + macros as special raw block
        header_block = "\n".join(includes + macros)
        if header_block:
            program_body.append(Function("headers", [], header_block, "raw"))

        # Store globals
        if globals_code:
            global_block = "\n".join(globals_code)
            program_body.append(Function("globals", [], global_block, "raw"))

        # Store functions
        for func in functions:
            program_body.append(Function("function", [], func, "raw"))

        return Program(program_body)