import re


class CTransformer:

    def transform(self, code):

        # malloc → calloc
        # malloc(sizeof(type)) → calloc(1, sizeof(type))
        code = re.sub(
            r"(\w+)\s*=\s*malloc\(\s*sizeof\(([^)]+)\)\s*\);",
            r"\1 = calloc(1, sizeof(\2));",
            code
        )

        # malloc(n * sizeof(type)) → calloc(n, sizeof(type))
        code = re.sub(
            r"(\w+)\s*=\s*malloc\(\s*(\d+)\s*\*\s*sizeof\(([^)]+)\)\s*\);",
            r"\1 = calloc(\2, sizeof(\3));",
            code
        )

        # gets → fgets
        code = re.sub(
            r"gets\((\w+)\);",
            r"fgets(\1, sizeof(\1), stdin);",
            code
        )

        # strcpy → strncpy
        code = re.sub(
            r"strcpy\((\w+),\s*(\w+)\);",
            r"strncpy(\1, \2, sizeof(\1));",
            code
        )

        # sprintf → snprintf
        code = re.sub(
            r"sprintf\((\w+),",
            r"snprintf(\1, sizeof(\1),",
            code
        )

        # void main → int main
        code = re.sub(
            r"\bvoid\s+main\s*\(",
            r"int main(",
            code
        )

        return code