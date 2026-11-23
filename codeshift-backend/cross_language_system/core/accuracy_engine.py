import os

import joblib

from cross_language_system.core.model_features import FEATURES, to_frame


class AccuracyEngine:
    """Predicts behaviour_score: the percentage of inputs a migration reproduces.

    Trained on measured migrations — see ml/build_dataset.py.
    """

    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "ml", "accuracy_model.pkl"
        )
        self.model = joblib.load(model_path) if os.path.exists(model_path) else None

    def predict(self, features, source=None, target=None):
        # A model fitted on another feature set would be scoring nonsense.
        if self.model is None or list(getattr(self.model, "feature_names_in_", [])) != FEATURES:
            return None
        frame = to_frame(features)
        if hasattr(self.model, "predict_proba"):
            # The expected score from P(every input reproduced), which beat
            # every direct regressor in cross-validation (ml/model_card.json).
            score = 100.0 * float(self.model.predict_proba(frame)[0][1])
        else:
            score = float(self.model.predict(frame)[0])
        return round(max(0.0, min(100.0, score)), 2)
