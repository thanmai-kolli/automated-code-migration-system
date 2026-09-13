import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

# Load dataset
df = pd.read_csv("confidence_training_data.csv")

# Features and target
X = df.drop("confidence", axis=1)
y = df["confidence"]

# Train model
model = RandomForestRegressor(
    n_estimators=250,
    random_state=42
)

model.fit(X, y)

# Save model
joblib.dump(model, "confidence_model.pkl")

print("Confidence model trained successfully.")