import csv
import random

CONF_ROWS = []
ACC_ROWS = []

for _ in range(1000):

    diff_count = random.randint(0, 25)
    semantic_issues = random.randint(0, 5)
    compile_success = random.choice([0, 1])
    risk_score = random.randint(0, 5)

    token_similarity = round(random.uniform(0.55, 0.98), 2)
    ast_similarity = round(random.uniform(0.60, 0.97), 2)
    structure_similarity = round(random.uniform(0.65, 0.98), 2)

    # ---------- CONFIDENCE ----------
    confidence = (
        token_similarity * 0.30 +
        ast_similarity * 0.30 +
        structure_similarity * 0.20 +
        (1 - diff_count / 30) * 0.10 +
        (1 - semantic_issues / 6) * 0.05 +
        (compile_success * 0.05)
    )

    confidence = max(min(confidence, 1), 0.25)

    # ---------- ACCURACY ----------
    accuracy = 100

    accuracy -= diff_count
    accuracy -= semantic_issues * 5
    accuracy -= risk_score * 3

    if compile_success == 0:
        accuracy -= random.randint(20, 35)

    accuracy += token_similarity * 5
    accuracy += ast_similarity * 8
    accuracy += structure_similarity * 6

    accuracy = max(min(round(accuracy), 100), 35)

    CONF_ROWS.append([
        diff_count,
        semantic_issues,
        compile_success,
        risk_score,
        token_similarity,
        ast_similarity,
        structure_similarity,
        round(confidence, 3)
    ])

    ACC_ROWS.append([
        diff_count,
        semantic_issues,
        compile_success,
        risk_score,
        token_similarity,
        ast_similarity,
        structure_similarity,
        accuracy
    ])

# ---------- WRITE CONFIDENCE DATA ----------

with open("confidence_training_data.csv", "w", newline="") as f:

    writer = csv.writer(f)

    writer.writerow([
        "diff_count",
        "semantic_issues",
        "compile_success",
        "risk_score",
        "token_similarity",
        "ast_similarity",
        "structure_similarity",
        "confidence"
    ])

    writer.writerows(CONF_ROWS)

# ---------- WRITE ACCURACY DATA ----------

with open("accuracy_training_data.csv", "w", newline="") as f:

    writer = csv.writer(f)

    writer.writerow([
        "diff_count",
        "semantic_issues",
        "compile_success",
        "risk_score",
        "token_similarity",
        "ast_similarity",
        "structure_similarity",
        "accuracy"
    ])

    writer.writerows(ACC_ROWS)

print("Datasets generated successfully.")