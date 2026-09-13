import os

import joblib

from cross_language_system.core.model_features import to_frame


class AccuracyEngine:
    """Predicts behaviour_score: the percentage of inputs a migration reproduces.

    Trained on measured migrations — see ml/build_dataset.py.
    """

    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "ml", "accuracy_model.pkl"
        )
        self.model = joblib.load(model_path)

    def predict(self, features, source=None, target=None):
        score = float(self.model.predict(to_frame(features))[0])
        return round(max(0.0, min(100.0, score)), 2)
