from cross_language_system.core.language_registry import LanguageRegistry
from cross_language_system.core.language_normalizer import LanguageNormalizer
from cross_language_system.core.token_similarity import compute_token_similarity
from cross_language_system.main_cross import run_cross_language_api


class TestLanguageRegistry:

    def test_known_languages_are_supported(self):
        for lang in ("python", "java", "c", "c++", "cpp"):
            assert LanguageRegistry.is_supported(lang)

    def test_cpp_alias_normalizes(self):
        assert LanguageRegistry.normalize("cpp") == "c++"

    def test_casing_and_whitespace_are_tolerated(self):
        assert LanguageRegistry.is_supported("  Python ")

    def test_unknown_language_is_rejected(self):
        assert not LanguageRegistry.is_supported("rust")

    def test_empty_language_is_rejected(self):
        assert not LanguageRegistry.is_supported("")
        assert not LanguageRegistry.is_supported(None)


class TestLanguageNormalizer:

    def test_normalizes_aliases(self):
        assert LanguageNormalizer.normalize("CPP") in ("c++", "cpp")


class TestTokenSimilarity:

    def test_identical_code_scores_high(self):
        code = "def add(a, b):\n    return a + b\n"
        assert compute_token_similarity(code, code) > 0.9

    def test_score_is_bounded(self):
        score = compute_token_similarity("int x = 1;", "def f(): pass")
        assert 0.0 <= score <= 1.0


class TestCrossLanguageApi:

    def test_empty_code_is_rejected(self):
        assert "error" in run_cross_language_api("   ", "python", "java")

    def test_unsupported_source_is_rejected(self):
        assert "error" in run_cross_language_api("x = 1", "rust", "java")

    def test_missing_target_is_rejected(self):
        assert "error" in run_cross_language_api("x = 1", "python", None)

    def test_unsupported_target_is_rejected(self):
        assert "error" in run_cross_language_api("x = 1", "python", "rust")

    def test_python_to_java_produces_a_report(self):
        result = run_cross_language_api(
            "class Counter:\n    def bump(self, n):\n        return n\n",
            "python",
            "java",
        )
        assert "error" not in result
        assert result["code"].strip()
        for key in ("confidence", "accuracy", "token_similarity", "timeTakenMs"):
            assert key in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert 0.0 <= result["accuracy"] <= 100.0

    def test_invalid_python_surfaces_an_error(self):
        assert "error" in run_cross_language_api("def broken(:\n", "python", "java")
