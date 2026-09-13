from .confidence_engine import PythonVersionConfidence
from .risk_analyzer import PythonRiskAnalyzer
from .validator import PythonValidator


class PythonEnterpriseUpgrader:

    def __init__(self):
        self.confidence = PythonVersionConfidence()
        self.risk = PythonRiskAnalyzer()
        self.validator = PythonValidator()

    def upgrade(self, code):

        original = code

        # --------------------------
        # Dummy upgrade logic
        # Replace Python2 print
        # --------------------------
        upgraded = code.replace("print ", "print(")

        # --------------------------
        # Validation
        # --------------------------
        validation = self.validator.validate(upgraded)

        # --------------------------
        # Risk Analysis
        # --------------------------
        risk_data = self.risk.compute(original, upgraded)

        # --------------------------
        # Diff Calculation
        # --------------------------
        total_diff_changes = abs(
            len(original.splitlines()) - len(upgraded.splitlines())
        )

        # --------------------------
        # ML Confidence
        # --------------------------
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
            "engine": "Python Enterprise Engine",
            "detected_version": "Python 2.x",
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