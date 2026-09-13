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