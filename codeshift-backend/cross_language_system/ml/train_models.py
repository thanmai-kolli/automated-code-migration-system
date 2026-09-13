"""Trains the accuracy and confidence models on measured migrations.

    python -m cross_language_system.ml.train_models

Reads migration_dataset.csv (produced by build_dataset.py) and fits:

  accuracy_model.pkl    regressor  -> behaviour_score, the percentage of inputs
                                      the migration reproduced exactly
  confidence_model.pkl  classifier -> P(correct), used as the confidence score

Both are evaluated with grouped cross-validation: all rows for one corpus program
stay in the same fold, so a model cannot score well by memorising a program it has
already seen in another target language. Every metric is compared against a
baseline that ignores the features entirely.
"""

import os
import sys

import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

FEATURES = [
    "diff_count",
    "semantic_issues",
    "compile_success",
    "risk_score",
    "token_similarity",
    "ast_similarity",
    "structure_similarity",
]

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "migration_dataset.csv")

# Small, shallow forests: the dataset has ~120 rows, so deep unpruned trees would
# memorise it and the pickles would dwarf the data they were fitted on.
FOREST = dict(n_estimators=60, max_depth=6, min_samples_leaf=3, random_state=42)


def load():
    if not os.path.exists(DATASET):
        raise SystemExit(f"{DATASET} not found — run build_dataset.py first.")
    return pd.read_csv(DATASET)


def report(title, lines):
    print()
    print(title)
    print("-" * len(title))
    for line in lines:
        print(line)


def main():

    data = load()
    X = data[FEATURES]
    groups = data["program"]
    folds = GroupKFold(n_splits=5)

    report("dataset", [
        f"rows                  {len(data)}",
        f"distinct programs     {data['program'].nunique()}",
        f"language pairs        {data.groupby(['source', 'target']).ngroups}",
        f"compiled              {int(data['compile_success'].sum())} / {len(data)}",
        f"behaviour-preserving  {int(data['correct'].sum())} / {len(data)}",
    ])

    # ---------------- accuracy (regression) ----------------
    y = data["behaviour_score"]

    predicted = cross_val_predict(
        RandomForestRegressor(**FOREST), X, y, cv=folds, groups=groups
    )
    baseline = cross_val_predict(
        DummyRegressor(strategy="mean"), X, y, cv=folds, groups=groups
    )

    report("accuracy model (predicts behaviour_score 0-100)", [
        f"MAE    {mean_absolute_error(y, predicted):6.2f}   baseline {mean_absolute_error(y, baseline):6.2f}",
        f"R2     {r2_score(y, predicted):6.3f}   baseline {r2_score(y, baseline):6.3f}",
    ])

    accuracy_model = RandomForestRegressor(**FOREST).fit(X, y)
    joblib.dump(accuracy_model, os.path.join(HERE, "accuracy_model.pkl"), compress=3)

    # ---------------- confidence (classification) ----------------
    y = data["correct"]

    predicted = cross_val_predict(
        RandomForestClassifier(**FOREST), X, y, cv=folds, groups=groups
    )
    probabilities = cross_val_predict(
        RandomForestClassifier(**FOREST), X, y, cv=folds, groups=groups,
        method="predict_proba",
    )[:, 1]
    baseline = cross_val_predict(
        DummyClassifier(strategy="most_frequent"), X, y, cv=folds, groups=groups
    )

    report("confidence model (predicts P(behaviour preserved))", [
        f"accuracy {accuracy_score(y, predicted):6.3f}   baseline {accuracy_score(y, baseline):6.3f}",
        f"ROC AUC  {roc_auc_score(y, probabilities):6.3f}   baseline  0.500",
    ])

    confidence_model = RandomForestClassifier(**FOREST).fit(X, y)
    joblib.dump(confidence_model, os.path.join(HERE, "confidence_model.pkl"), compress=3)

    importance = sorted(
        zip(FEATURES, accuracy_model.feature_importances_),
        key=lambda pair: pair[1],
        reverse=True,
    )
    report("feature importance (accuracy model)", [
        f"{name:<22} {value:.3f}" for name, value in importance
    ])

    sizes = [
        (name, os.path.getsize(os.path.join(HERE, name)) / 1024)
        for name in ("accuracy_model.pkl", "confidence_model.pkl")
    ]
    report("saved models", [f"{name:<22} {size:8.1f} KB" for name, size in sizes])


if __name__ == "__main__":
    main()
