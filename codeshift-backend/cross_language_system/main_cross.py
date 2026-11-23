import sys
import time
import traceback
from cross_language_system.core.dispatcher import CrossLanguageEngine, risk_level
from cross_language_system.core.report_formatter import print_cross_report
from cross_language_system.core.language_registry import LanguageRegistry
from cross_language_system.ml.language_detector import MLLanguageDetector
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

        # The engine is the single place scores are computed, from the same
        # features the models were trained on.
        result = engine.convert(code, source, target)
        if "error" in result:
            return result

        test_results = run_test_cases(
            source, code, target, result.get("code", ""), test_cases
        )
        if test_results:
            result["test_results"] = test_results
            if test_results.get("enabled"):
                result["test_success"] = test_results["failed"] == 0
                if test_results["failed"]:
                    result["risk_triggers"].append(
                        f"{test_results['failed']} of {test_results['total']} test cases failed"
                    )
                    result["risk_score"] = len(result["risk_triggers"])
                    result["risk_level"] = risk_level(
                        result["compile_success"], result["risk_triggers"], tests_failed=True
                    )

        result["timeTakenMs"] = round((time.perf_counter() - start_time) * 1000)

        return result

    except Exception:
        traceback.print_exc()
        return {"error": "Engine execution failed."}