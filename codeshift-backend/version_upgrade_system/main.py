import time
import traceback
from version_upgrade_system.core.upgrade_engine import UpgradeEngine
# ------------------------------------------------------------
# Read multi-line input
# ------------------------------------------------------------
def read_code():
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

    compile_status = {True: "SUCCESS", False: "FAILED", None: "NOT CHECKED"}[result.get("compile_success")]
    print(f"Compile Status     : {compile_status}")

    if result.get("compile_errors"):
        print(f"Compile Errors     : {result.get('compile_errors')}")

    if "validation_status" in result:
        print(f"Validation Status  : {result.get('validation_status')}")

    if "test_success" in result:
        test_status = "PASSED" if result.get("test_success") else "FAILED"
        print(f"Test Execution     : {test_status}")

    print()

    # ---------------- RULES ----------------
    print("RULES")
    print("-----")
    for title, key in (("Applied", "applied_rules"), ("Rejected", "rejected_rules")):
        rules = result.get(key, [])
        print(f"{title + ':':<19}{' None' if not rules else ''}")
        for rule in rules:
            print(f"                     - {rule}")

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
        result = engine.upgrade(code, language)
    except Exception:
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
# ------------------------------------------------------------
# API ENTRY (For Flask)
# ------------------------------------------------------------
def run_version_upgrade_api(code, language, test_cases=None):

    engine = UpgradeEngine()

    if not code or not code.strip():
        return {"error": "No code provided."}
    if language not in ["python", "java", "cpp", "c","c++"]:
        return {"error": "Unsupported language."}

    try:
        start_time = time.perf_counter()

        result = engine.upgrade(code, language, test_cases)

        # Only measured values are reported: the cross-language scoring models were
        # trained on translations, not on upgrades.
        tests = result.get("test_results")
        if tests and tests.get("enabled") and tests.get("total"):
            result["accuracy"] = round(100.0 * tests["passed"] / tests["total"], 2)

        result["timeTakenMs"] = round((time.perf_counter() - start_time) * 1000)

    except Exception:
        traceback.print_exc()
        return {"error": "Engine execution failed."}

    return result