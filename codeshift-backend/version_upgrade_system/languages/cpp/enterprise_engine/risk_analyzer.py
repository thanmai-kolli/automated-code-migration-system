class CppRiskAnalyzer:

    def compute(self, original, upgraded):

        risk = 0
        triggers = []

        # Feature-based risk
        if "auto_ptr" in original:
            risk += 3
            triggers.append("smart_pointer_modernization")

        if "NULL" in original and "nullptr" in upgraded:
            risk += 1
            triggers.append("null_pointer_conversion")

        if "typedef" in original and "using" in upgraded:
            risk += 1
            triggers.append("type_alias_modernization")

        if "(int)" in original or "(double)" in original:
            risk += 2
            triggers.append("cast_modification")

        # Diff ratio calculation
        original_lines = len(original.splitlines())
        upgraded_lines = len(upgraded.splitlines())

        diff_ratio = abs(original_lines - upgraded_lines) / max(original_lines, 1)

        if diff_ratio > 0.5:
            risk += 3
            triggers.append("large_structural_change")

        # Risk level mapping
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