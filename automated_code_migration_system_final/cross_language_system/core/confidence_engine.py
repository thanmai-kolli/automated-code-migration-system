import os
import joblib
import numpy as np

class ConfidenceEngine:

    def __init__(self):

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(BASE_DIR, "ml", "confidence_model.pkl")

        self.model = joblib.load(model_path)

    def predict(self, metrics):

        features = np.array([[
            metrics["compile_success"],
            metrics["num_object_types"],
            metrics["num_generic_types"],
            metrics["num_loops"],
            metrics["num_conditionals"],
            metrics["diff_ratio"],
            metrics["semantic_issues"]
        ]])

        score = self.model.predict(features)[0]

        return round(float(score), 2)