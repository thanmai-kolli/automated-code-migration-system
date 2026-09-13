import re


class MoveSemanticsOptimizer:

    def optimize(self, code):

        # Detect return by value of large objects
        code = re.sub(
            r"return\s+(\w+);",
            r"return std::move(\1);",
            code
        )

        return code
