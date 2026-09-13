def build_accuracy_features(report):

    return [

        report.get("diff_count", 0),

        len(report.get("semantic_issues", [])),

        1 if report.get("compile_success") else 0,

        report.get("risk_score", 0),

        report.get("token_similarity", 0),

        report.get("ast_similarity", 0),

        report.get("structure_similarity", 0)

    ]