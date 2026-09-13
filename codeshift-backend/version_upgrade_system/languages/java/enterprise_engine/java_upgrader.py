from version_upgrade_system.languages.java.enterprise_engine.confidence_engine import JavaVersionConfidence
from version_upgrade_system.languages.java.enterprise_engine.risk_analyzer import JavaRiskAnalyzer
from version_upgrade_system.languages.java.enterprise_engine.validator import JavaValidator


class JavaEnterpriseUpgrader:

    def __init__(self):
        self.confidence = JavaVersionConfidence()
        self.risk = JavaRiskAnalyzer()
        self.validator = JavaValidator()

    def upgrade(self, code):

        original = code

        # --- Dummy upgrade logic (replace with real transformer) ---
        upgraded = code.replace("Vector", "ArrayList")

        # --- Validation ---
        validation = self.validator.validate(upgraded)

        # --- Risk ---
        risk_data = self.risk.compute(original, upgraded)

        # --- Diff Count ---
        total_diff_changes = abs(
            len(original.splitlines()) - len(upgraded.splitlines())
        )

        # --- Confidence ---
        confidence_score = self.confidence.calculate_confidence(
            changes_count=total_diff_changes,
            risky_changes=risk_data["risk_score"],
            syntax_valid=validation["compile_success"],
            semantic_valid=validation["validation_status"] == "PASS",
            test_passed=validation["test_success"],
            diff_ratio=risk_data["diff_ratio"]
        )

        return {
            "code": upgraded,
            "engine": "Java Enterprise Engine",
            "detected_version": "Java 8",
            "compile_success": validation["compile_success"],
            "compile_errors": validation["compile_errors"],
            "validation_status": validation["validation_status"],
            "risk_score": risk_data["risk_score"],
            "risk_level": risk_data["risk_level"],
            "risk_triggers": risk_data["risk_triggers"],
            "total_diff_changes": total_diff_changes,
            "confidence_score": confidence_score,
            "diff_text": "",
            "test_success": validation["test_success"]
        }