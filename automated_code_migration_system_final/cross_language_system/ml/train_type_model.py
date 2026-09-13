from sklearn.ensemble import RandomForestClassifier
import joblib
import numpy as np

# Example feature vectors:
# [num_append_int, num_append_str, used_in_arithmetic, used_in_loop]
X = np.array([
    [2, 0, 0, 1],  # List<Integer>
    [0, 3, 0, 1],  # List<String>
    [0, 0, 1, 0],  # int
])

y = [
    "List<Integer>",
    "List<String>",
    "int"
]

model = RandomForestClassifier()
model.fit(X, y)

joblib.dump(model, "type_model.pkl")

print("Type model trained and saved.")