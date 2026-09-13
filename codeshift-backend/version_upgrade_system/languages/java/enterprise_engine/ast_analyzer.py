import javalang


class JavaASTAnalyzer:

    def analyze(self, code):

        try:
            tree = javalang.parse.parse(code)
        except Exception:
            return {}

        result = {
            "classes": [],
            "methods": [],
            "fields": [],
            "imports": []
        }

        for path, node in tree:

            if isinstance(node, javalang.tree.ClassDeclaration):
                result["classes"].append(node.name)

            if isinstance(node, javalang.tree.MethodDeclaration):
                result["methods"].append(node.name)

            if isinstance(node, javalang.tree.FieldDeclaration):
                for decl in node.declarators:
                    result["fields"].append(decl.name)

            if isinstance(node, javalang.tree.Import):
                result["imports"].append(node.path)

        return result
