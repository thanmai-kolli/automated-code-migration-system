import ast


class PythonValidator:

    def validate(self, code):

        compile_errors = []

        try:
            ast.parse(code)
            compile_success = True
        except SyntaxError as exc:
            compile_success = False
            compile_errors.append(f"line {exc.lineno}: {exc.msg}")

        validation_status = "PASS" if compile_success else "FAIL"

        return {
            "compile_success": compile_success,
            "compile_errors": compile_errors,
            "validation_status": validation_status,
            "test_success": compile_success
        }
