import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

data = pd.read_csv("accuracy_training_data.csv")

X = data.drop(columns=["accuracy"])
y = data["accuracy"]

model = RandomForestRegressor(
    n_estimators=300,
    random_state=42
)

model.fit(X, y)

joblib.dump(model, "accuracy_model.pkl")

print("Accuracy model trained.")