"""Shared feature vector for the migration scoring models.

The models are fitted on a pandas DataFrame, so predictions must present the same
named columns in the same order — otherwise scikit-learn silently falls back to
positional matching and warns about missing feature names.
"""

import pandas as pd

FEATURES = [
    "diff_count",
    "semantic_issues",
    "compile_success",
    "risk_score",
    "token_similarity",
    "ast_similarity",
    "structure_similarity",
]


def to_frame(features):
    return pd.DataFrame([[features.get(name, 0) for name in FEATURES]], columns=FEATURES)
