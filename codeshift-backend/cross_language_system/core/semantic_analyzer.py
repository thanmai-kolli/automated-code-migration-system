class SemanticAnalyzer:

    # Everything the generators can place inside the target's entry point.
    SUPPORTED_TOP_LEVEL = {
        "Function", "Class", "Variable", "Assignment", "AugAssign",
        "PrintStatement", "IfStatement", "ForLoop", "WhileLoop", "TryCatch",
        "Break", "Continue", "Pass", "Return",
        "FunctionCall", "MethodCall", "ListAppend", "DictPut",
    }

    # Nodes no generator lowers into C-family targets yet.
    UNSUPPORTED_IN_C_FAMILY = {"SwitchStatement"}

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

        for node in getattr(program, "body", []):

            name = node.__class__.__name__

            if name not in self.SUPPORTED_TOP_LEVEL:
                issues.append(f"Unsupported top-level construct: {name}")

            elif name in self.UNSUPPORTED_IN_C_FAMILY and target in ("c", "cpp", "c++"):
                issues.append(f"{name} is not lowered into {target} yet")

        return issues