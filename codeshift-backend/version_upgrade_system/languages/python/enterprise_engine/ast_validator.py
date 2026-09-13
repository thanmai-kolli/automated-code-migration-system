import ast


class ASTValidator:

    def validate(self, code):
        try:
            ast.parse(code)
            return True, None
        except Exception as e:
            return False, str(e)
