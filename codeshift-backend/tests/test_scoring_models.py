"""Guards on the scoring models and the dataset they were fitted on.

The previous models were fitted on synthetic rows: random features with labels
from a hand-written formula. These tests assert the replacement is grounded in
measured migrations and behaves like a real probability/score.
"""

import os

import pandas as pd
import pytest

from cross_language_system.core.accuracy_engine import AccuracyEngine
from cross_language_system.core.confidence_engine import ConfidenceEngine
from cross_language_system.core.model_features import FEATURES, to_frame
from cross_language_system.ml import corpus

DATASET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cross_language_system", "ml", "migration_dataset.csv",
)

_ROWS = pd.read_csv(DATASET)


def _sample(mask):
    """A real measured feature vector, so predictions stay in-distribution.

    Hand-written extremes sit outside the training range, where a random forest
    extrapolates badly and the assertion would be testing nothing useful.
    """
    row = _ROWS[mask].iloc[0]
    return {name: row[name] for name in FEATURES}


GOOD = _sample((_ROWS["correct"] == 1) & (_ROWS["behaviour_score"] == 100))
BAD = _sample(_ROWS["compile_success"] == 0)


class TestCorpus:

    def test_every_language_has_programs(self):
        assert set(corpus.CORPUS) == {"python", "java", "c", "c++"}
        for language, programs in corpus.CORPUS.items():
            assert len(programs) >= 8, language

    def test_programs_have_code_and_inputs(self):
        for language, program in corpus.iter_programs():
            assert program["code"].strip(), f"{language}/{program['name']}"
            assert program["inputs"], f"{language}/{program['name']}"

    def test_names_are_unique_per_language(self):
        for language, programs in corpus.CORPUS.items():
            names = [p["name"] for p in programs]
            assert len(names) == len(set(names)), language


class TestDataset:

    @pytest.fixture(scope="class")
    def data(self):
        assert os.path.exists(DATASET), "run build_dataset.py"
        return pd.read_csv(DATASET)

    def test_has_the_expected_columns(self, data):
        for column in FEATURES + ["source", "target", "program", "behaviour_score", "correct"]:
            assert column in data.columns

    def test_covers_every_language_pair(self, data):
        assert data.groupby(["source", "target"]).ngroups == 12

    def test_labels_are_in_range(self, data):
        assert data["behaviour_score"].between(0, 100).all()
        assert data["correct"].isin([0, 1]).all()

    def test_failed_compiles_score_zero(self, data):
        failed = data[data["compile_success"] == 0]
        assert (failed["behaviour_score"] == 0).all()
        assert (failed["correct"] == 0).all()

    def test_risk_score_matches_the_serving_formula(self, data):
        # dispatcher.convert sets risk_score = 1 if not compile_success else 0.
        # Training must agree, or the model sees a feature it never sees live.
        expected = 1 - data["compile_success"]
        assert (data["risk_score"] == expected).all()

    def test_labels_are_not_all_the_same(self, data):
        # A degenerate dataset would make the metrics meaningless.
        assert data["correct"].nunique() == 2
        assert data["behaviour_score"].nunique() > 2

    def test_features_vary(self, data):
        for column in ("diff_count", "token_similarity", "ast_similarity"):
            assert data[column].nunique() > 5, column


class TestFeatureFrame:

    def test_column_order_is_preserved(self):
        frame = to_frame(GOOD)
        assert list(frame.columns) == FEATURES

    def test_missing_keys_default_to_zero(self):
        frame = to_frame({})
        assert frame.iloc[0].tolist() == [0] * len(FEATURES)


class TestAccuracyEngine:

    @pytest.fixture(scope="class")
    def engine(self):
        return AccuracyEngine()

    def test_score_is_bounded(self, engine):
        for features in (GOOD, BAD):
            assert 0.0 <= engine.predict(features) <= 100.0

    def test_good_migration_outscores_broken_one(self, engine):
        assert engine.predict(GOOD) > engine.predict(BAD)

    def test_broken_migration_scores_low(self, engine):
        assert engine.predict(BAD) < 40

    def test_prediction_is_deterministic(self, engine):
        assert engine.predict(GOOD) == engine.predict(GOOD)


class TestConfidenceEngine:

    @pytest.fixture(scope="class")
    def engine(self):
        return ConfidenceEngine()

    def test_is_a_probability(self, engine):
        for features in (GOOD, BAD):
            assert 0.0 <= engine.predict(features) <= 1.0

    def test_good_migration_is_more_confident(self, engine):
        assert engine.predict(GOOD) > engine.predict(BAD)

    def test_broken_migration_has_low_confidence(self, engine):
        assert engine.predict(BAD) < 0.5


class TestModelSize:
    """The synthetic-era models were 21 MB each, fitted on 500 rows."""

    @pytest.mark.parametrize("name", ["accuracy_model.pkl", "confidence_model.pkl"])
    def test_model_is_small(self, name):
        path = os.path.join(os.path.dirname(DATASET), name)
        assert os.path.getsize(path) < 1_000_000, f"{name} is unexpectedly large"
