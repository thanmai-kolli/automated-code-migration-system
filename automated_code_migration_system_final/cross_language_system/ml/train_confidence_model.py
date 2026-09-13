import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(BASE_DIR, "confidence_training_data.csv")

df = pd.read_csv(csv_path)

X = df.drop("confidence_score", axis=1)
y = df["confidence_score"]

model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X, y)

model_path = os.path.join(BASE_DIR, "confidence_model.pkl")
joblib.dump(model, model_path)

print("✅ Model retrained successfully with 30 real samples.")