import os
import joblib


class AccuracyEngine:

    def __init__(self):

        model_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "ml",
            "accuracy_model.pkl"
        )

        self.model = joblib.load(model_path)

    def predict(self, features, source=None, target=None):

        X = [[
            features["diff_count"],
            features["semantic_issues"],
            features["compile_success"],
            features["risk_score"],
            features["token_similarity"],
            features["ast_similarity"],
            features["structure_similarity"]
        ]]

        score = self.model.predict(X)[0]

        # language pair adjustment
        if source == "python" and target == "java":
            score += 12

        elif source == "java" and target == "python":
            score += 10

        elif source == "c" and target == "c++":
            score += 5

        elif source == "c++" and target == "c":
            score += 5

        return min(100, max(0, round(float(score), 2)))