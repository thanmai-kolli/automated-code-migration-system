"""Detects the programming language of a source file.

Used when a request does not name its source language. The model is a linear
classifier over character n-grams and code tokens, trained on whole programs
(ml/corpus.py plus corpus_extra.json, all four languages, including legacy
styles) rather than one-line snippets:

    python -m cross_language_system.ml.language_detector

trains it and prints grouped cross-validation accuracy.
"""

import os
import re
import sys

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "language_model.pkl")

LABELS = {"python": "python", "java": "java", "c": "c", "c++": "cpp", "cpp": "cpp"}

# Identifiers, numbers, and the punctuation clusters that distinguish the
# languages: '#include', '::', '->', '<<', '):', '{', ';'.
TOKEN_PATTERN = r"#\w+|[A-Za-z_]\w*|\d+|::|->|<<|>>|\):|[{};:]"


def _strip_literals(code):
    """String contents and comments say little about the language."""
    code = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', code)
    code = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", code)
    return code


def build_model():
    features = make_union(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True,
                        preprocessor=_strip_literals, min_df=2),
        TfidfVectorizer(analyzer="word", token_pattern=TOKEN_PATTERN, lowercase=False,
                        ngram_range=(1, 2), sublinear_tf=True, preprocessor=_strip_literals),
    )
    return make_pipeline(features, LogisticRegression(max_iter=5000, C=10.0))


def training_samples():
    from cross_language_system.ml.corpus import iter_training_programs
    return [(program["code"], LABELS[language], program["name"])
            for language, program in iter_training_programs()]


class MLLanguageDetector:

    def __init__(self):
        if os.path.exists(MODEL_PATH):
            self.model = joblib.load(MODEL_PATH)
            # Older pickles held a (vectorizer, model) tuple fitted on 12 snippets.
            if isinstance(self.model, tuple):
                self.model = self._train()
        else:
            self.model = self._train()

    def _train(self):
        codes, labels, _ = zip(*training_samples())
        model = build_model().fit(codes, labels)
        joblib.dump(model, MODEL_PATH, compress=3)
        return model

    def predict(self, code):
        return self.model.predict([code])[0]

    def predict_proba(self, code):
        probabilities = self.model.predict_proba([code])[0]
        return dict(zip(self.model.classes_, (round(float(p), 3) for p in probabilities)))


def main():
    from sklearn.model_selection import GroupKFold, cross_val_predict

    # Run as a script this file is __main__, and a model built here would be pickled
    # with a reference to __main__._strip_literals that no other process can load.
    # Build and save it through the importable module instead.
    sys.path.insert(0, os.path.dirname(os.path.dirname(BASE_DIR)))
    from cross_language_system.ml import language_detector as module

    codes, labels, names = zip(*module.training_samples())
    # A task written in several languages is one group: test on unseen tasks.
    groups = [name for name in names]
    predicted = cross_val_predict(module.build_model(), list(codes), list(labels),
                                  cv=GroupKFold(n_splits=5), groups=groups)
    correct = sum(p == t for p, t in zip(predicted, labels))
    print(f"grouped 5-fold CV accuracy: {correct}/{len(labels)} = {correct / len(labels):.3f}")

    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
    module.MLLanguageDetector()
    print("saved", MODEL_PATH)


if __name__ == "__main__":
    main()
