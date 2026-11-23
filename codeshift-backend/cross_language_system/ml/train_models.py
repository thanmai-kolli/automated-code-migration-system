"""Trains the accuracy and confidence models on measured migrations.

    python -m cross_language_system.ml.train_models

Reads migration_dataset.csv (produced by build_dataset.py) and fits:

  confidence_model.pkl  classifier -> P(correct): every input reproduced exactly
  accuracy_model.pkl    model      -> behaviour_score, the percentage of inputs
                                      reproduced exactly

Candidates (model family x feature set) are compared with grouped
cross-validation: all rows for one program stay in the same fold, so a model
cannot score well by memorising a program it has already seen in another target
language. The deployed classifier is the candidate with the lowest Brier score
(the proper scoring rule for probabilities, so calibration counts); the
deployed accuracy model is the candidate with the lowest MAE, where one
candidate is simply 100 x the classifier's probability. Baselines that ignore
the features, or look only at whether the code compiled, are reported next to
every candidate and are never deployed.
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, brier_score_loss, mean_absolute_error,
                             r2_score, roc_auc_score)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cross_language_system.core.model_features import FEATURES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "migration_dataset.csv")
CARD = os.path.join(HERE, "model_card.json")

# Small, shallow forests: a few hundred rows would let deep trees memorise them.
FOREST = dict(n_estimators=200, max_depth=4, min_samples_leaf=5, random_state=42)
FOLDS = 5

FEATURE_SETS = {
    "all": FEATURES,
    # The residual failures are unmapped library APIs, so the count of library
    # calls (with the structures they act on) carries most of the signal.
    "compile+library": ["compile_success", "n_library_calls", "n_classes", "n_collection_ops"],
}


class CompileOnly:
    """Baseline that sees only compile_success: the training mean per value."""

    def __init__(self, proba=False):
        self.proba = proba

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        flag = X["compile_success"].to_numpy()
        self.means = {v: (y[flag == v].mean() if (flag == v).any() else y.mean()) for v in (0, 1)}
        return self

    def _values(self, X):
        return np.array([self.means[int(v)] for v in X["compile_success"]])

    def predict(self, X):
        values = self._values(X)
        return (values >= 0.5).astype(int) if self.proba else values

    def predict_proba(self, X):
        p = self._values(X)
        return np.column_stack([1 - p, p])


def _on(columns, *steps):
    """A pipeline that takes the full feature frame and uses only `columns`."""
    return make_pipeline(ColumnTransformer([("keep", "passthrough", list(columns))]), *steps)


def classifiers():
    candidates = {}
    for set_name, columns in FEATURE_SETS.items():
        candidates[f"logistic_regression[{set_name}]"] = lambda c=columns: _on(
            c, StandardScaler(), LogisticRegression(max_iter=5000, C=0.5))
        candidates[f"random_forest[{set_name}]"] = lambda c=columns: _on(
            c, RandomForestClassifier(**FOREST))
        candidates[f"random_forest_sigmoid[{set_name}]"] = lambda c=columns: _on(
            c, CalibratedClassifierCV(RandomForestClassifier(**FOREST), method="sigmoid", cv=3))
    return candidates


def regressors():
    candidates = {}
    for set_name, columns in FEATURE_SETS.items():
        candidates[f"ridge[{set_name}]"] = lambda c=columns: _on(c, StandardScaler(), Ridge(alpha=10.0))
        candidates[f"random_forest[{set_name}]"] = lambda c=columns: _on(c, RandomForestRegressor(**FOREST))
    return candidates


BASELINE_CLASSIFIERS = {
    "compile_only (baseline)": lambda: CompileOnly(proba=True),
    "class_prior (baseline)": lambda: DummyClassifier(strategy="prior"),
}

BASELINE_REGRESSORS = {
    "compile_only (baseline)": lambda: CompileOnly(),
    "mean (baseline)": lambda: DummyRegressor(strategy="mean"),
}


def grouped_predictions(factory, X, y, groups, proba):
    predictions = np.zeros(len(y))
    for train, test in GroupKFold(n_splits=FOLDS).split(X, y, groups):
        model = factory().fit(X.iloc[train], y.iloc[train])
        predictions[test] = (model.predict_proba(X.iloc[test])[:, 1] if proba
                             else model.predict(X.iloc[test]))
    return predictions


def expected_calibration_error(y, p, bins=5):
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return total


def classification_report(y, p, compiled):
    report = {
        "Brier": round(brier_score_loss(y, p), 4),
        "ECE": round(expected_calibration_error(y, p), 4),
        "accuracy": round(accuracy_score(y, (p >= 0.5).astype(int)), 4),
        "ROC_AUC": round(roc_auc_score(y, p), 4) if len(set(y)) > 1 else None,
    }
    if len(set(y[compiled])) > 1:
        report["ROC_AUC_compiled_only"] = round(roc_auc_score(y[compiled], p[compiled]), 4)
    return report


def main():

    data = pd.read_csv(DATASET)
    X = data[FEATURES]
    groups = data["program"]
    compiled = data["compile_success"].to_numpy() == 1
    card = {
        "dataset": {
            "rows": len(data),
            "programs": int(data["program"].nunique()),
            "compiled": int(data["compile_success"].sum()),
            "correct": int(data["correct"].sum()),
            "features": FEATURES,
        },
        "cv": {"scheme": f"GroupKFold({FOLDS}) by program"},
    }

    # ---------------- confidence (classification) ----------------
    y = data["correct"]
    scores, probabilities = {}, {}
    for name, factory in {**classifiers(), **BASELINE_CLASSIFIERS}.items():
        probabilities[name] = grouped_predictions(factory, X, y, groups, proba=True)
        scores[name] = classification_report(y.to_numpy(), probabilities[name], compiled)
    chosen_classifier = min((n for n in classifiers()), key=lambda n: scores[n]["Brier"])
    card["confidence_model"] = {"chosen": chosen_classifier, "cv": scores}
    classifier = classifiers()[chosen_classifier]().fit(X, y)
    joblib.dump(classifier, os.path.join(HERE, "confidence_model.pkl"), compress=3)

    # ---------------- accuracy (behaviour score) ----------------
    y = data["behaviour_score"]
    scores = {}
    expectation = "100 x confidence model"
    for name, factory in {**regressors(), **BASELINE_REGRESSORS}.items():
        predicted = np.clip(grouped_predictions(factory, X, y, groups, proba=False), 0, 100)
        scores[name] = {"MAE": round(mean_absolute_error(y, predicted), 3),
                        "R2": round(r2_score(y, predicted), 3)}
    predicted = 100 * probabilities[chosen_classifier]
    scores[expectation] = {"MAE": round(mean_absolute_error(y, predicted), 3),
                           "R2": round(r2_score(y, predicted), 3)}
    chosen_regressor = min((n for n in list(regressors()) + [expectation]), key=lambda n: scores[n]["MAE"])
    card["accuracy_model"] = {"chosen": chosen_regressor, "cv": scores}
    if chosen_regressor == expectation:
        # AccuracyEngine reports 100 x P(correct) for a model with predict_proba.
        accuracy_model = classifier
    else:
        accuracy_model = regressors()[chosen_regressor]().fit(X, y)
    joblib.dump(accuracy_model, os.path.join(HERE, "accuracy_model.pkl"), compress=3)

    with open(CARD, "w", encoding="utf-8") as handle:
        json.dump(card, handle, indent=2)
        handle.write("\n")

    print(json.dumps(card, indent=2))


if __name__ == "__main__":
    main()
