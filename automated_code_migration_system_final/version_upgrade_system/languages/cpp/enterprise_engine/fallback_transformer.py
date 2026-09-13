import re


class CppFallbackTransformer:

    def transform(self, code):

        # auto_ptr → unique_ptr
        code = re.sub(r"\bauto_ptr\b", "unique_ptr", code)

        # NULL → nullptr
        code = re.sub(r"\bNULL\b", "nullptr", code)

        # typedef → using
        code = re.sub(
            r"typedef\s+(.+?)\s+(\w+);",
            r"using \2 = \1;",
            code
        )

        # C-style cast → static_cast
        code = re.sub(
            r"\((int|double|float)\)\s*(\w+)",
            r"static_cast<\1>(\2)",
            code
        )

        # Simple for loop → range-based
        code = re.sub(
            r"for\s*\(\s*int\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\w+)\.size\(\)\s*;\s*\w+\+\+\s*\)",
            r"for (auto& item : \1)",
            code
        )

        return code