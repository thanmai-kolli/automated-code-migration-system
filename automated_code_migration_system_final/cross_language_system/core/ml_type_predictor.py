import joblib
import numpy as np

class MLTypePredictor:

    def __init__(self):
        try:
            self.model = joblib.load("type_model.pkl")
        except:
            self.model = None

    def predict(self, features):

        if self.model is None:
            return None

        X = np.array([[
            features["num_append_int"],
            features["num_append_str"],
            features["used_in_arithmetic"],
            features["used_in_loop"]
        ]])

        return self.model.predict(X)[0]