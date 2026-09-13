import sys
import time
import traceback
from cross_language_system.core.dispatcher import CrossLanguageEngine
from cross_language_system.core.report_formatter import print_cross_report
from cross_language_system.core.language_registry import LanguageRegistry
from cross_language_system.ml.language_detector import MLLanguageDetector
from cross_language_system.core.token_similarity import compute_token_similarity
from cross_language_system.core.structure_similarity import compute_structure_similarity
from cross_language_system.core.ast_similarity import compute_ast_similarity
from cross_language_system.core.confidence_engine import ConfidenceEngine
from cross_language_system.core.accuracy_engine import AccuracyEngine
from cross_language_system.core.test_executor import run_test_cases
# ------------------------------------------------------------
# Read Multi-line Input
# ------------------------------------------------------------
def read_code():
    print("\nPaste your code below.")
    print("Finish with CTRL+Z then ENTER (Windows)")
    print("or CTRL+D (Linux/Mac)\n")
    return sys.stdin.read()


# ------------------------------------------------------------
# Main CLI
# ------------------------------------------------------------
def main():

    print("============================================================")
    print("      CROSS LANGUAGE ENTERPRISE ENGINE")
    print("============================================================")

    engine = CrossLanguageEngine()

    code = read_code()

    if not code.strip():
        print("❌ No code provided.")
        return

    source = input("\nEnter source language (or leave blank for auto-detect): ").strip().lower()

    if not source:
        detector = MLLanguageDetector()
        source = detector.predict(code)
        print(f"🔍 ML-detected source: {source}")

    if not LanguageRegistry.is_supported(source):
        print(f"❌ Unsupported source language: {source}")
        return

    target = input("Enter target language: ").strip().lower()

    if not LanguageRegistry.is_supported(target):
        print(f"❌ Unsupported target language: {target}")
        return

    try:
        result = engine.convert(code, source, target)
        
    except Exception:
        print("\n❌ Engine execution failed:")
        traceback.print_exc()
        return 

    if "error" in result:
        print("\nError:", result["error"])
        return

    print("\n================ GENERATED CODE ================\n")
    print(result.get("code", ""))

    print_cross_report(result)

    show_diff = input("\nShow full diff? (y/n): ").strip().lower()
    if show_diff == "y":
        print("\n================ DIFF OUTPUT =================\n")
        print(result.get("diff_text", ""))
        print("\n============================================================")


if __name__ == "__main__":
    main()
# ------------------------------------------------------------
# API ENTRY (For Flask)
# ------------------------------------------------------------
def run_cross_language_api(code, source=None, target=None, test_cases=None):

    engine = CrossLanguageEngine()

    if not code or not code.strip():
        return {"error": "No code provided."}

    if not source:
        detector = MLLanguageDetector()
        source = detector.predict(code)
    if not LanguageRegistry.is_supported(source):
        return {"error": f"Unsupported source language: {source}"}

    if not target:
        return {"error": "Target language is required."}

    if not LanguageRegistry.is_supported(target):
        return {"error": f"Unsupported target language: {target}"}

    try:
        start_time = time.perf_counter()

        result = engine.convert(code, source, target)
        result["token_similarity"] = compute_token_similarity(code, result["code"])

        result["structure_similarity"] = compute_structure_similarity(code, result["code"])

        result["ast_similarity"] = compute_ast_similarity(code, result["code"])
        token_similarity = compute_token_similarity(code, result["code"])
        ast_similarity = compute_ast_similarity(code, result["code"])
        structure_similarity = compute_structure_similarity(code, result["code"])
        confidence_engine = ConfidenceEngine()
        accuracy_engine = AccuracyEngine()
        features = {
            "diff_count": result.get("diff_count", 0),
            "semantic_issues": len(result.get("semantic_issues", [])),
            "compile_success": int(result.get("compile_success", False)),
            "risk_score": result.get("risk_score", 0),
            "token_similarity": token_similarity,
            "ast_similarity": ast_similarity,
            "structure_similarity": structure_similarity
        }

        result["confidence"] = confidence_engine.predict(features)
        result["accuracy"] = round(accuracy_engine.predict(features),2)

        test_results = run_test_cases(
            source, code, target, result.get("code", ""), test_cases
        )
        if test_results:
            result["test_results"] = test_results
            if test_results.get("enabled"):
                result["test_success"] = test_results["failed"] == 0

        end_time = time.perf_counter()

        time_taken_ms = round((end_time - start_time) * 1000)

        if not result:
            return {"error": "Conversion engine returned empty result."}

        result["timeTakenMs"] = time_taken_ms

        return result

    except Exception:
        traceback.print_exc()
        return {"error": "Engine execution failed."}