class PythonRiskAnalyzer:

    def compute(self, original, upgraded, applied_rules=None):

        triggers = list(applied_rules or [])
        risk_score = len(triggers)

        original_lines = len(original.splitlines())
        upgraded_lines = len(upgraded.splitlines())

        diff_ratio = abs(original_lines - upgraded_lines) / max(original_lines, 1)

        if diff_ratio > 0.5:
            risk_score += 3
            triggers.append("Large structural modification")

        if risk_score <= 2:
            level = "LOW"
        elif risk_score <= 5:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return {
            "risk_score": risk_score,
            "risk_level": level,
            "risk_triggers": triggers,
            "diff_ratio": diff_ratio
        }