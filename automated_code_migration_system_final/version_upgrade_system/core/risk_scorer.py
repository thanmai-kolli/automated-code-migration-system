class RiskScorer:

    def compute(self, change_count, ml_confidence, compile_success):

        base_risk = change_count * 10

        confidence_penalty = (1 - ml_confidence) * 40

        compile_penalty = 30 if not compile_success else 0

        total = base_risk + confidence_penalty + compile_penalty

        if total < 20:
            level = "LOW"
        elif total < 50:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return round(total, 2), level
