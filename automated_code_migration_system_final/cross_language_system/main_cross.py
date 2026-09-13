import sys
import traceback
from core.dispatcher import CrossLanguageEngine
from core.report_formatter import print_cross_report
from core.language_registry import LanguageRegistry
from ml.language_detector import MLLanguageDetector


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