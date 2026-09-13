# class ConfidenceEngine:

#     def calculate(self, semantic_issues, compile_success):

#         score = 100

#         # Penalize semantic issues
#         score -= len(semantic_issues) * 8

#         # Penalize compile failure heavily
#         if not compile_success:
#             score -= 40

#         # Clamp score
#         score = max(0, min(100, score))

#         return score


# features = {
#     "compile_success": 1 or 0,
#     "num_object_types": count_of_Object,
#     "num_generic_types": count_of_List_Set_Map,
#     "num_unresolved": unresolved_identifiers,
#     "num_method_mappings": mapped_methods_count,
#     "num_loops": loop_count,
#     "num_conditionals": if_count,
#     "num_fallback_mappings": fallback_count,
# }
import os
import joblib
import numpy as np

# class ConfidenceEngine:

#     def __init__(self):

#         BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#         model_path = os.path.join(BASE_DIR, "ml", "confidence_model.pkl")

#         self.model = joblib.load(model_path)

#     def predict(self, metrics):

#         features = np.array([[
#             metrics["compile_success"],
#             metrics["num_object_types"],
#             metrics["num_generic_types"],
#             metrics["num_loops"],
#             metrics["num_conditionals"],
#             metrics["diff_ratio"],
#             metrics["semantic_issues"]
#         ]])

#         score = self.model.predict(features)[0]

#         return round(float(score), 2)
import os
import joblib


class ConfidenceEngine:

    def __init__(self):

        model_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "ml",
            "confidence_model.pkl"
        )

        self.model = joblib.load(model_path)

    def predict(self, features):

        vector = [[
            features["diff_count"],
            features["semantic_issues"],
            features["compile_success"],
            features["risk_score"],
            features["token_similarity"],
            features["ast_similarity"],
            features["structure_similarity"]
        ]]

        score = self.model.predict(vector)[0]

        score = max(min(score, 1), 0)

        return round(float(score), 3)