import re

from version_upgrade_system.languages.python.enterprise_engine.confidence_engine import PythonVersionConfidence
from version_upgrade_system.languages.python.enterprise_engine.diff_generator import DiffGenerator
from version_upgrade_system.languages.python.enterprise_engine.risk_analyzer import PythonRiskAnalyzer
from version_upgrade_system.languages.python.enterprise_engine.validator import PythonValidator
from version_upgrade_system.languages.python.enterprise_engine.version_detector import PythonVersionDetector


class PythonEnterpriseUpgrader:

    def __init__(self):
        self.confidence = PythonVersionConfidence()
        self.risk = PythonRiskAnalyzer()
        self.validator = PythonValidator()
        self.detector = PythonVersionDetector()
        self.diff = DiffGenerator()

    # -----------------------------------
    # SAFE PRINT UPGRADE FUNCTION
    # -----------------------------------
    def safe_print_upgrade(self, code):

        pattern = r'^(\s*)print\s+(.*)$'
        lines = code.splitlines()
        new_lines = []

        for line in lines:
            match = re.match(pattern, line)
            if match:
                indent = match.group(1)
                content = match.group(2).rstrip()
                new_line = f'{indent}print({content})'
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        return "\n".join(new_lines)

    def upgrade(self, code):

        original = code

        # --------------------------
        # Safe upgrade logic
        # --------------------------
        upgraded = self.safe_print_upgrade(code)

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
        diff_data = self.diff.generate(original, upgraded)
        total_diff_changes = diff_data["total_changes"]

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
            "detected_version": self.detector.detect(original),
            "compile_success": validation["compile_success"],
            "compile_errors": validation["compile_errors"],
            "validation_status": validation["validation_status"],
            "risk_score": risk_data["risk_score"],
            "risk_level": risk_data["risk_level"],
            "risk_triggers": risk_data["risk_triggers"],
            "total_diff_changes": total_diff_changes,
            "confidence_score": confidence_score,
            "diff_text": diff_data["diff_text"],
            "test_success": validation["test_success"]
        }