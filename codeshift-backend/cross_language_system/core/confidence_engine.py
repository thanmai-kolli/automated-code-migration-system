import os

import joblib

from cross_language_system.core.model_features import FEATURES, to_frame


class ConfidenceEngine:
    """Predicts P(the migration preserves behaviour).

    A calibrated classifier rather than a regressor, so the score is a
    probability that can be checked against observed outcomes.
    """

    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "ml", "confidence_model.pkl"
        )
        self.model = joblib.load(model_path) if os.path.exists(model_path) else None

    def predict(self, features):
        # A model fitted on another feature set would be scoring nonsense.
        if self.model is None or list(getattr(self.model, "feature_names_in_", [])) != FEATURES:
            return None
        probability = self.model.predict_proba(to_frame(features))[0][1]
        return round(float(probability), 3)
