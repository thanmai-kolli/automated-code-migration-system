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

    print(f"Confidence Score    : {result.get('confidence')* 100:.2f}%")

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