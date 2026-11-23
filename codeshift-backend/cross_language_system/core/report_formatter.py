def print_cross_report(result):

    print("\n============================================================")
    print("           CROSS-LANGUAGE MIGRATION REPORT")
    print("============================================================\n")

    print("ENGINE INFO")
    print("-----------")
    print(f"Source Language     : {result.get('source')}")
    print(f"Target Language     : {result.get('target')}")
    print(f"Compile Status      : {'SUCCESS' if result.get('compile_success') else 'FAILED'}")

    if result.get("compile_errors"):
        print(f"Compile Details     : {result.get('compile_errors')}")

    confidence = result.get("confidence")
    shown = f"{confidence * 100:.2f}%" if confidence is not None else "unavailable"
    print(f"Confidence Score    : {shown}")
    print(f"Risk Level          : {result.get('risk_level')}")

    print("\nSEMANTIC ANALYSIS")
    print("-----------------")

    issues = result.get("semantic_issues", [])

    if issues:
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No semantic issues detected.")

    print("\nDIFF SUMMARY")
    print("------------")
    print(f"Total Diff Entries  : {result.get('diff_count')}")

    print("\n============================================================")