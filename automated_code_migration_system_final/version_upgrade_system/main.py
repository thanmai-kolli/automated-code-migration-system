# import sys
# import os
# import json

# from core.upgrade_engine import UpgradeEngine
# from core.language_detector import LanguageDetector


# def read_code_from_file(file_path):
#     try:
#         with open(file_path, "r", encoding="utf-8") as f:
#             return f.read()
#     except Exception as e:
#         print(f"❌ Error reading file: {e}")
#         sys.exit(1)


# def read_code_from_input():
#     print("Paste your code below (finish with CTRL+D on Linux/Mac or CTRL+Z on Windows):\n")
#     return sys.stdin.read()


# def print_result(result):

#     if "error" in result:
#         print("\n❌ ERROR:")
#         print(result["error"])
#         return

#     print("\n" + "=" * 60)
#     print("UPGRADED CODE")
#     print("=" * 60)
#     print(result["upgraded_code"])

#     print("\n" + "=" * 60)
#     print("UPGRADE REPORT")
#     print("=" * 60)

#     report = result["report"]

#     print(f"Language            : {report['language']}")
#     print(f"Detected Version    : {report['detected_version']}")
#     print(f"Target Version      : {report['target_version']}")
#     print(f"Changes Applied     : {report['changes']}")
#     print(f"Compile Success     : {report['compile_success']}")
#     print(f"Compile Errors      : {report['compile_errors']}")
#     print(f"Risk Score          : {report['risk_score']}")
#     print(f"Risk Level          : {report['risk_level']}")
#     print(f"Validation Status   : {report['validation_status']}")
#     print("=" * 60)


# def main():

#     print("==============================================")
#     print("      VERSION UPGRADE ENGINE (CLI MODE)")
#     print("==============================================")

#     engine = UpgradeEngine()
#     detector = LanguageDetector()

#     choice = input("\nChoose input method:\n1. File\n2. Manual Paste\nEnter choice (1/2): ").strip()

#     if choice == "1":
#         file_path = input("Enter file path: ").strip()

#         if not os.path.exists(file_path):
#             print("❌ File does not exist.")
#             return

#         code = read_code_from_file(file_path)

#         # Auto detect from file extension
#         extension = os.path.splitext(file_path)[1]

#         if extension == ".py":
#             language = "python"
#         elif extension == ".java":
#             language = "java"
#         elif extension == ".c":
#             language = "c"
#         elif extension in [".cpp", ".cc", ".cxx"]:
#             language = "cpp"
#         else:
#             language = detector.detect(code)

#     elif choice == "2":
#         code = read_code_from_input()
#         language = input("Enter language (python/java/c/cpp) or leave blank for auto-detect: ").strip()

#         if not language:
#             language = detector.detect(code)

#     else:
#         print("❌ Invalid choice.")
#         return

#     if language == "unknown":
#         print("❌ Could not detect language.")
#         return

#     print(f"\n🔍 Detected Language: {language}")

#     result = engine.upgrade(code, language)

#     print_result(result)


# if __name__ == "__main__":
#     main()
import sys
import traceback
from core.upgrade_engine import UpgradeEngine


# ------------------------------------------------------------
# Read multi-line input
# ------------------------------------------------------------
def read_code():
    # print("\nPaste your code below.")
    # print("Finish with CTRL+Z then ENTER (Windows)")
    # print("or CTRL+D (Linux/Mac)\n")
    # return sys.stdin.read()
    print("\nEnter your code (type END on a new line to finish):\n")

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    return "\n".join(lines)


# ------------------------------------------------------------
# Structured Report Printer (Unified)
# ------------------------------------------------------------
def print_report(result):

    print("\n============================================================")
    print("                 MIGRATION REPORT")
    print("============================================================\n")

    # ---------------- ENGINE INFO ----------------
    print("ENGINE INFO")
    print("-----------")

    print(f"Engine Used        : {result.get('engine', 'N/A')}")
    print(f"Detected Version   : {result.get('detected_version', 'Unknown')}")

    compile_status = "SUCCESS" if result.get("compile_success") else "FAILED"
    print(f"Compile Status     : {compile_status}")

    if result.get("compile_errors"):
        print(f"Compile Errors     : {result.get('compile_errors')}")

    if "validation_status" in result:
        print(f"Validation Status  : {result.get('validation_status')}")

    if "test_success" in result:
        test_status = "PASSED" if result.get("test_success") else "FAILED"
        print(f"Test Execution     : {test_status}")

    # if "confidence_score" in result:
    #     print(f"Confidence Score   : {result.get('confidence_score')}%")
    confidence = result.get("confidence_score")
    if confidence is not None:
        print(f"Confidence Score   : {confidence}%")
    else:
        print("Confidence Score   : Not Available")

    print()

    # ---------------- CHANGE SUMMARY ----------------
    print("CHANGE SUMMARY")
    print("--------------")

    print(f"Risk Score         : {result.get('risk_score', 0)}")
    print(f"Risk Level         : {result.get('risk_level', 'N/A')}")

    triggers = result.get("risk_triggers", [])
    if triggers:
        print("Risk Triggers      :")
        for t in triggers:
            print(f"                     - {t}")
    else:
        print("Risk Triggers      : None")

    print()

    # ---------------- SYMBOL ANALYSIS ----------------
    print("SYMBOL ANALYSIS")
    print("---------------")

    symbols = result.get("symbols", {})
    if symbols:
        for key, values in symbols.items():
            if values:
                print(f"{key.capitalize():<20}: {', '.join(values)}")
            else:
                print(f"{key.capitalize():<20}: None")
    else:
        print("No symbol data available")

    print()

    # ---------------- DIFF SUMMARY ----------------
    print("DIFF SUMMARY")
    print("------------")

    print(f"Total Diff Entries : {result.get('total_diff_changes', 0)}")

    print("\n============================================================")


# ------------------------------------------------------------
# MAIN ENTRY
# ------------------------------------------------------------
def main():

    print("============================================================")
    print("        VERSION UPGRADE ENTERPRISE ENGINE")
    print("============================================================")

    engine = UpgradeEngine()

    code = read_code()

    if not code.strip():
        print("❌ No code provided.")
        return

    language = input("\nEnter language (python/java/cpp/c): ").strip().lower()

    try:

        # ---------------- PYTHON ----------------
        if language == "python":

            result = engine.upgrade(code, language)

        # ---------------- JAVA ----------------
        elif language == "java":
            result = engine.upgrade(code, language)

        # ---------------- C++ ----------------
        elif language == "cpp":
            result = engine.upgrade(code, language)
        elif language == "c":
            result = engine.upgrade(code,language)
        else:
            print("Unsupported language.")
            return

    except Exception as e:
        print("\n❌ Engine execution failed:")
        traceback.print_exc()
        return

    # ---------------- ERROR HANDLING ----------------
    if "error" in result:
        print("\nError:", result["error"])
        return

    # ---------------- SHOW UPGRADED CODE ----------------
    print("\n================ UPGRADED CODE ================\n")
    print(result.get("code", ""))

    # ---------------- PRINT REPORT ----------------
    print_report(result)

    # ---------------- OPTIONAL DIFF ----------------
    show_diff = input("\nShow full diff? (y/n): ").strip().lower()
    if show_diff == "y":
        print("\n================ DIFF OUTPUT =================\n")
        print(result.get("diff_text", ""))
        print("\n============================================================")


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
