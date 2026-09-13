"""Builds the training data by measuring real migrations.

For every corpus program and every target language, this runs the engine, records
the features the engine actually computed, then *measures* the outcome: does the
generated code compile, and does it behave like the original on real inputs?

    python -m cross_language_system.ml.build_dataset

Labels
------
behaviour_score  fraction of inputs where the migration printed exactly what the
                 original printed, times 100. Zero if it does not compile.
correct          1 when every input matched, else 0.

This replaces the previous synthetic generator, whose features were random and
whose labels came from a hand-written formula.
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cross_language_system.core.dispatcher import CrossLanguageEngine
from cross_language_system.core import test_executor
from cross_language_system.ml.corpus import iter_programs, program_count

LANGUAGES = ["python", "java", "c", "c++"]

FEATURES = [
    "diff_count",
    "semantic_issues",
    "compile_success",
    "risk_score",
    "token_similarity",
    "ast_similarity",
    "structure_similarity",
]

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(HERE, "migration_dataset.csv")


def measure(engine, source, target, program):

    result = engine.convert(program["code"], source, target)

    if "error" in result:
        return None

    compile_success = 1 if result.get("compile_success") else 0

    row = {
        "source": source,
        "target": target,
        "program": program["name"],
        "diff_count": result.get("diff_count", 0),
        "semantic_issues": len(result.get("semantic_issues", [])),
        "compile_success": compile_success,
        # Derived exactly as dispatcher.convert does, so training matches serving.
        "risk_score": 0 if compile_success else 1,
        "token_similarity": round(result.get("token_similarity", 0.0), 4),
        "ast_similarity": round(result.get("ast_similarity", 0.0), 4),
        "structure_similarity": round(result.get("structure_similarity", 0.0), 4),
    }

    if not compile_success:
        row["behaviour_score"] = 0.0
        row["correct"] = 0
        return row

    cases = "\n---\n".join(program["inputs"])
    executed = test_executor.run_test_cases(
        source, program["code"], target, result["code"], cases
    )

    if not executed or not executed.get("enabled"):
        raise SystemExit(
            f"Test execution is disabled. Set {test_executor.ENABLE_FLAG}=1 to build the dataset."
        )

    total = executed["total"] or 1
    row["behaviour_score"] = round(100.0 * executed["passed"] / total, 2)
    row["correct"] = 1 if executed["failed"] == 0 else 0

    return row


def build():

    engine = CrossLanguageEngine()
    rows = []
    skipped = 0

    total_runs = program_count() * (len(LANGUAGES) - 1)
    done = 0

    for source, program in iter_programs():
        for target in LANGUAGES:

            if target == source:
                continue

            done += 1
            row = measure(engine, source, target, program)

            if row is None:
                skipped += 1
                print(f"[{done}/{total_runs}] {source:>6} -> {target:<4} {program['name']:<18} SKIPPED")
                continue

            rows.append(row)
            print(
                f"[{done}/{total_runs}] {source:>6} -> {target:<4} {program['name']:<18}"
                f" compile={row['compile_success']} behaviour={row['behaviour_score']:.0f}"
            )

    columns = ["source", "target", "program"] + FEATURES + ["behaviour_score", "correct"]

    with open(DATASET_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"wrote {len(rows)} measured migrations to {DATASET_PATH}")
    if skipped:
        print(f"{skipped} runs skipped (engine returned an error)")

    compiled = sum(r["compile_success"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    print(f"compiled: {compiled}/{len(rows)}   behaviour-preserving: {correct}/{len(rows)}")

    return rows


if __name__ == "__main__":
    build()
