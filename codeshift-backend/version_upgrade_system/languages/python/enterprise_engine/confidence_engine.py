# class ConfidenceEngine:
#
#     def calculate(self, compile_success, risk_score, change_count):
#
#         if not compile_success:
#             return 0.0
#
#         base = 100
#
#         # Risk penalty
#         base -= (risk_score * 5)
#
#         # Large changes penalty
#         if change_count > 50:
#             base -= 15
#         elif change_count > 20:
#             base -= 8
#
#         if base < 0:
#             base = 0
#
#         return round(base, 2)

from version_upgrade_system.core.base_confidence_engine import BaseVersionConfidenceEngine


class PythonVersionConfidence:

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