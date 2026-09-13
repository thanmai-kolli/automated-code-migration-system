# # class ConfidenceEngine:
#
# #     def calculate(self, compile_success, risk_score, change_count):
#
# #         if not compile_success:
# #             return 0.0
#
# #         score = 100
#
# #         score -= risk_score * 5
#
# #         if change_count > 40:
# #             score -= 15
# #         elif change_count > 20:
# #             score -= 8
#
# #         return max(0, round(score, 2))
# class ConfidenceEngine:
#
#     def calculate(
#         self,
#         compile_success,
#         risk_score,
#         change_count,
#         test_success=True,
#         detected_version=None
#     ):
#
#         # Base score
#         score = 100
#
#         # -----------------------------------
#         # 1️⃣ Compile failure = critical
#         # -----------------------------------
#         if not compile_success:
#             return 0.0
#
#         # -----------------------------------
#         # 2️⃣ Risk impact
#         # -----------------------------------
#         score -= risk_score * 4   # slightly softer than before
#
#         # -----------------------------------
#         # 3️⃣ Change size impact
#         # -----------------------------------
#         if change_count > 60:
#             score -= 15
#         elif change_count > 30:
#             score -= 8
#         elif change_count > 10:
#             score -= 3
#
#         # -----------------------------------
#         # 4️⃣ Test result bonus
#         # -----------------------------------
#         if test_success:
#             score += 5
#         else:
#             score -= 10
#
#         # -----------------------------------
#         # 5️⃣ Version modernization bonus
#         # -----------------------------------
#         if detected_version == "Pre-Java 5":
#             score += 5   # successful modernization bonus
#
#         # Clamp between 0–100
#         score = max(0, min(100, score))
#
#         return round(score, 2)


from version_upgrade_system.core.base_confidence_engine import BaseVersionConfidenceEngine


class JavaVersionConfidence:

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