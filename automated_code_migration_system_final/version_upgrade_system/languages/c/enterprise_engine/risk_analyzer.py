class CRiskAnalyzer:

    def compute(self, original, upgraded, leak_count=0):

        risk = 0
        triggers = []

        if "gets(" in original:
            risk += 3
            triggers.append("unsafe_input_function")

        if "strcpy(" in original:
            risk += 2
            triggers.append("unsafe_string_copy")

        if "sprintf(" in original:
            risk += 2
            triggers.append("unsafe_formatting")

        if leak_count > 0:
            risk += leak_count * 2
            triggers.append("potential_memory_leak")

        # Diff ratio calculation
        original_lines = len(original.splitlines())
        upgraded_lines = len(upgraded.splitlines())

        diff_ratio = abs(original_lines - upgraded_lines) / max(original_lines, 1)

        if diff_ratio > 0.5:
            risk += 3
            triggers.append("large_structural_change")

        if risk <= 2:
            level = "LOW"
        elif risk <= 5:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return {
            "risk_score": risk,
            "risk_level": level,
            "risk_triggers": triggers,
            "diff_ratio": diff_ratio
        }