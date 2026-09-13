class SemanticAnalyzer:

    def analyze(self, program, source, target):

        issues = []

        # Example rule: Python dynamic typing → static languages
        if source == "python" and target in ["java", "cpp", "c"]:
            issues.append("Dynamic typing converted to static types")

        # Memory model differences
        if source == "python" and target == "c":
            issues.append("Manual memory management required")

        if source == "python" and target == "cpp":
            issues.append("Smart pointer ownership required")

        # Unsupported feature detection placeholder
        for node in getattr(program, "body", []):
            if node.__class__.__name__ not in [
                "Function", "Class"
            ]:
                issues.append("Unsupported top-level construct detected")

        return issues