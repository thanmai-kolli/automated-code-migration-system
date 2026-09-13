import os
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


# Paths
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "version_training_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "version_confidence_model.pkl")


def train_model():

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            "Training data not found: version_training_data.csv"
        )

    print("Loading training data...")
    df = pd.read_csv(DATA_PATH)

    # Feature columns (MUST match base_confidence_engine.py order)
    feature_columns = [
        "changes_count",
        "risky_changes",
        "syntax_valid",
        "semantic_valid",
        "test_passed",
        "diff_ratio"
    ]

    X = df[feature_columns]
    y = df["successful_upgrade"]

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42
    )

    print("Training RandomForest model...")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"Model Accuracy: {round(accuracy * 100, 2)}%")

    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print("✅ version_confidence_model.pkl saved successfully!")


if __name__ == "__main__":
    train_model()