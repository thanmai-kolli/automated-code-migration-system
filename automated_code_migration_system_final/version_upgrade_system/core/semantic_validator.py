class SemanticValidator:

    def validate(self, compile_success, changes):

        if not compile_success:
            return "FAILED"

        if len(changes) == 0:
            return "NO_CHANGES"

        return "PASSED"
