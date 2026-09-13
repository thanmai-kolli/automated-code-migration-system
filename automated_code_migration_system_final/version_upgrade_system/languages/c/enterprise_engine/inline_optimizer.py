import re


class InlineOptimizer:

    def optimize(self, code):

        def replace(match):
            func_name = match.group(1)

            if func_name == "main":
                return match.group(0)

            return f"\nstatic inline int {func_name}("

        return re.sub(
            r"\nint\s+(\w+)\(",
            replace,
            code
        )