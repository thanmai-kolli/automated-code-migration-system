import os

import joblib

from cross_language_system.core.model_features import to_frame


class ConfidenceEngine:
    """Predicts P(the migration preserves behaviour).

    A classifier rather than a regressor, so the score is a calibrated
    probability instead of an arbitrary number clamped into [0, 1].
    """

    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "ml", "confidence_model.pkl"
        )
        self.model = joblib.load(model_path)

    def predict(self, features):
        probability = self.model.predict_proba(to_frame(features))[0][1]
        return round(float(probability), 3)
