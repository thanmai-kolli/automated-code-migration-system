import re
from cross_language_system.core.ir_nodes import *
from cross_language_system.parsers.c_like_parser import CLikeParser


C_FAMILY = {"c", "cpp", "c++"}


class CppParser:
    """Converting to another C-family language is a text rewrite, so the raw
    source is preserved. Any other target needs a real IR from CLikeParser."""

    def __init__(self, target=None):
        self.target = (target or "").lower()

    def parse(self, code):

        if self.target and self.target not in C_FAMILY:
            return CLikeParser().parse(code)

        return self._parse_as_text(code)

    def _parse_as_text(self, code):

        includes = []
        globals_code = []
        blocks = []

        lines = code.splitlines()

        # -----------------------------
        # 1️⃣ Extract Includes
        # -----------------------------
        for line in lines:
            if line.strip().startswith("#include"):
                includes.append(line)

        # Remove includes
        cleaned_code = "\n".join(
            line for line in lines
            if not line.strip().startswith("#include")
        )

        # -----------------------------
        # 2️⃣ Extract Classes / Structs
        # -----------------------------
        class_pattern = r'(class|struct)\s+[a-zA-Z_]\w*\s*\{'
        matches = list(re.finditer(class_pattern, cleaned_code))

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
                        break

            if end:
                block_text = cleaned_code[start:end].rstrip()
                if not block_text.endswith(";"):
                    block_text += ";"

                blocks.append(block_text)
                used_ranges.append((start, end))

        # Remove class blocks
        for start, end in sorted(used_ranges, reverse=True):
            cleaned_code = cleaned_code[:start] + cleaned_code[end:]

        # -----------------------------
        # 3️⃣ Extract Functions
        # -----------------------------
        function_pattern = r'([a-zA-Z_][\w\s:<>\*&]*?)\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{'
        matches = list(re.finditer(function_pattern, cleaned_code))

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
                        break

            if end:
                func_text = cleaned_code[start:end]
                blocks.append(func_text)

        # -----------------------------
        # 4️⃣ Build IR
        # -----------------------------
        program_body = []

        header_block = "\n".join(includes)
        if header_block:
            program_body.append(Function("headers", [], header_block, "raw"))

        for block in blocks:
            program_body.append(Function("block", [], block, "raw"))

        return Program(program_body)