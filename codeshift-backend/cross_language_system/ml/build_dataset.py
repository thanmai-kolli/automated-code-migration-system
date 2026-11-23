"""Builds the training data by measuring real migrations.

For every training program and every target language, this runs the engine,
records the feature vector the engine itself computed (so training and serving
see identical features), then *measures* the outcome: does the generated code
compile, and does it behave like the original on real inputs?

    CODESHIFT_ENABLE_TEST_EXECUTION=1 python -m cross_language_system.ml.build_dataset

Training programs: ml/corpus.py (B1) plus corpus_extra.json (the evaluation's
B2 programs and the Java/C/C++ programs of B3). Migrations the engine refuses
are counted but not scored: no translation exists to put a score on.

Labels
------
behaviour_score  fraction of inputs where the migration printed exactly what the
                 original printed, times 100. Zero if it does not compile.
correct          1 when every input matched, else 0.
"""

import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cross_language_system.core import test_executor
from cross_language_system.core.dispatcher import CrossLanguageEngine
from cross_language_system.core.model_features import FEATURES
from cross_language_system.ml.corpus import iter_training_programs

LANGUAGES = ["python", "java", "c", "c++"]

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(HERE, "migration_dataset.csv")


def measure(job):

    source, target, program = job
    result = CrossLanguageEngine().convert(program["code"], source, target)

    if "error" in result:
        return job, None, result["error"]

    row = {"source": source, "target": target, "program": program["name"]}
    row.update({name: round(float(result["features"][name]), 4) for name in FEATURES})

    if not result["compile_success"]:
        row["behaviour_score"] = 0.0
        row["correct"] = 0
        return job, row, None

    cases = "\n---\n".join(program["inputs"])
    executed = test_executor.run_test_cases(
        source, program["code"], target, result["code"], cases
    )

    if not executed or not executed.get("enabled"):
        raise SystemExit(
            f"Test execution is disabled. Set {test_executor.ENABLE_FLAG}=1 to build the dataset."
        )

    if any(case["source_output"] is None for case in executed["cases"]):
        # The reference itself did not run, so there is nothing to compare with.
        return job, None, "source program does not run"

    total = executed["total"] or 1
    row["behaviour_score"] = round(100.0 * executed["passed"] / total, 2)
    row["correct"] = 1 if executed["failed"] == 0 else 0
    return job, row, None


def build():

    jobs = [(source, target, program)
            for source, program in iter_training_programs()
            for target in LANGUAGES if target != source]

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(measure, jobs))

    rows = []
    refused = 0
    skipped = 0
    for (source, target, program), row, error in outcomes:
        if row is None:
            if error == "source program does not run":
                skipped += 1
            else:
                refused += 1
            print(f"{source:>6} -> {target:<6} {program['name']:<22} SKIPPED  {error[:70]}")
            continue
        rows.append(row)
        print(f"{source:>6} -> {target:<6} {program['name']:<22} compile={row['compile_success']:.0f}"
              f" behaviour={row['behaviour_score']:.0f}")

    columns = ["source", "target", "program"] + FEATURES + ["behaviour_score", "correct"]

    with open(DATASET_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    compiled = sum(r["compile_success"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    print()
    print(f"wrote {len(rows)} measured migrations to {DATASET_PATH}")
    print(f"refused by the engine (not scored): {refused}")
    print(f"source program does not run here (not scored): {skipped}")
    print(f"compiled: {compiled:.0f}/{len(rows)}   behaviour-preserving: {correct}/{len(rows)}")

    return rows


if __name__ == "__main__":
    build()
