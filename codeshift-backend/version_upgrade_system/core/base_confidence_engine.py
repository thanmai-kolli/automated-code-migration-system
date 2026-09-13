import os
import pickle
import numpy as np


class BaseVersionConfidenceEngine:

    def __init__(self, model_path=None):

        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__),
                "version_confidence_model.pkl"
            )

        self.model = self._load_model(model_path)

    def _load_model(self, path):

        if not os.path.exists(path):
            raise FileNotFoundError(
                "Version confidence model not found. Train it first."
            )

        with open(path, "rb") as f:
            return pickle.load(f)

    def predict(self, features_dict):

        feature_order = [
            "changes_count",
            "risky_changes",
            "syntax_valid",
            "semantic_valid",
            "test_passed",
            "diff_ratio"
        ]

        features = np.array([[features_dict[f] for f in feature_order]])

        probability = self.model.predict_proba(features)[0][1]

        return round(probability * 100, 2)