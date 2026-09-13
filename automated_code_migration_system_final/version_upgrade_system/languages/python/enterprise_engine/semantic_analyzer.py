import ast


class SemanticAnalyzer:

    def analyze(self, code):

        tree = ast.parse(code)

        symbols = {
            "functions": [],
            "classes": [],
            "imports": []
        }

        for node in ast.walk(tree):

            if isinstance(node, ast.FunctionDef):
                symbols["functions"].append(node.name)

            elif isinstance(node, ast.ClassDef):
                symbols["classes"].append(node.name)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols["imports"].append(alias.name)

        return symbols
