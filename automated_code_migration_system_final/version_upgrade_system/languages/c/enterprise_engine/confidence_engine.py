# class ConfidenceEngine:
#
#     def calculate(self, compile_success, risk_score, change_count):
#
#         if not compile_success:
#             return 0.0
#
#         score = 100
#         score -= risk_score * 5
#
#         if change_count > 40:
#             score -= 10
#
#         return max(0, round(score, 2))


from core.base_confidence_engine import BaseVersionConfidenceEngine


class CVersionConfidence:

    def __init__(self):
        self.engine = BaseVersionConfidenceEngine()

    def calculate_confidence(self,
                             changes_count,
                             risky_changes,
                             syntax_valid,
                             semantic_valid,
                             test_passed,
                             diff_ratio):

        features = {
            "changes_count": changes_count,
            "risky_changes": risky_changes,
            "syntax_valid": int(syntax_valid),
            "semantic_valid": int(semantic_valid),
            "test_passed": int(test_passed),
            "diff_ratio": diff_ratio
        }

        return self.engine.predict(features)