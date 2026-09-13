# from .grammar_parser import Python2GrammarParser
# from .post_processor import PostProcessor
# from .semantic_analyzer import SemanticAnalyzer
# from .ast_validator import ASTValidator
# from .risk_analyzer import RiskAnalyzer
# from .change_tracker import ChangeTracker
# from .diff_generator import DiffGenerator
# from .confidence_engine import PythonVersionConfidence
# from .test_runner import TestRunner
#
#
# class PythonEnterpriseUpgrader:
#
#     def __init__(self):
#         self.parser = Python2GrammarParser()
#         self.post = PostProcessor()
#         self.semantic = SemanticAnalyzer()
#         self.validator = ASTValidator()
#         self.risk = RiskAnalyzer()
#         self.tracker = ChangeTracker()
#         self.diff = DiffGenerator()
#         self.confidence = ConfidenceEngine()
#         self.test_runner = TestRunner()
#
#     def upgrade(self, code):
#
#         original_code = code
#
#         # 1️⃣ Grammar conversion
#         try:
#             upgraded_code = self.parser.transform(code)
#         except Exception as e:
#             return self._error_report(code, str(e))
#
#         # 2️⃣ Post processing
#         upgraded_code = self.post.apply(upgraded_code)
#
#         # 3️⃣ Semantic analysis
#         try:
#             symbols = self.semantic.analyze(upgraded_code)
#         except Exception:
#             symbols = {}
#
#         # 4️⃣ AST Validation
#         valid, error = self.validator.validate(upgraded_code)
#         validation_status = "PASSED" if valid else "FAILED"
#
#         # 5️⃣ Risk Analysis
#         risk_data = self.risk.compute(original_code, upgraded_code)
#
#         # 6️⃣ Change tracking
#         change_count = self.tracker.count_changes(original_code, upgraded_code)
#
#         # 7️⃣ Diff generation
#         diff_data = self.diff.generate(original_code, upgraded_code)
#
#         # 8️⃣ Confidence score
#         confidence_score = self.confidence.calculate(
#             valid,
#             risk_data["risk_score"],
#             change_count
#         )
#
#         # 9️⃣ Test execution
#         test_result = self.test_runner.run(upgraded_code)
#
#         return {
#             "code": upgraded_code,
#             "compile_success": valid,
#             "compile_errors": error,
#             "validation_status": validation_status,
#             "engine": "enterprise",
#             "change_count": change_count,
#             "symbols": symbols,
#             "confidence_score": confidence_score,
#             "test_success": test_result["test_success"],
#             "test_error": test_result["test_error"],
#             "diff_text": diff_data["diff_text"],
#             "changed_lines": diff_data["changed_lines"],
#             "total_diff_changes": diff_data["total_changes"],
#             **risk_data
#         }
#
#     def _error_report(self, code, error_message):
#
#         return {
#             "code": code,
#             "compile_success": False,
#             "compile_errors": error_message,
#             "validation_status": "FAILED",
#             "engine": "enterprise",
#             "change_count": 0,
#             "symbols": {},
#             "confidence_score": 0.0,
#             "test_success": False,
#             "test_error": error_message,
#             "diff_text": "",
#             "changed_lines": [],
#             "total_diff_changes": 0,
#             "risk_score": 10,
#             "risk_level": "HIGH",
#             "risk_triggers": []
#         }


# from version_upgrade_system.languages.python.enterprise_engine.confidence_engine import PythonVersionConfidence
# from version_upgrade_system.languages.python.enterprise_engine.risk_analyzer import PythonRiskAnalyzer
# from version_upgrade_system.languages.python.enterprise_engine.validator import PythonValidator


# class PythonEnterpriseUpgrader:

#     def __init__(self):
#         self.confidence = PythonVersionConfidence()
#         self.risk = PythonRiskAnalyzer()
#         self.validator = PythonValidator()

#     def upgrade(self, code):

#         original = code

#         # --------------------------
#         # Dummy upgrade logic
#         # Replace Python2 print
#         # --------------------------
#         upgraded = code.replace("print ", "print(")

#         # --------------------------
#         # Validation
#         # --------------------------
#         validation = self.validator.validate(upgraded)

#         # --------------------------
#         # Risk Analysis
#         # --------------------------
#         risk_data = self.risk.compute(original, upgraded)

#         # --------------------------
#         # Diff Calculation
#         # --------------------------
#         total_diff_changes = abs(
#             len(original.splitlines()) - len(upgraded.splitlines())
#         )

#         # --------------------------
#         # ML Confidence
#         # --------------------------
#         confidence_score = self.confidence.calculate_confidence(
#             changes_count=total_diff_changes,
#             risky_changes=risk_data["risk_score"],
#             syntax_valid=validation["compile_success"],
#             semantic_valid=validation["validation_status"] == "PASS",
#             test_passed=validation["test_success"],
#             diff_ratio=risk_data["diff_ratio"]
#         )

#         return {
#             "code": upgraded,
#             "engine": "Python Enterprise Engine",
#             "detected_version": "Python 2.x",
#             "compile_success": validation["compile_success"],
#             "compile_errors": validation["compile_errors"],
#             "validation_status": validation["validation_status"],
#             "risk_score": risk_data["risk_score"],
#             "risk_level": risk_data["risk_level"],
#             "risk_triggers": risk_data["risk_triggers"],
#             "total_diff_changes": total_diff_changes,
#             "confidence_score": confidence_score,
#             "diff_text": "",
#             "test_success": validation["test_success"]
#         }
import re

from version_upgrade_system.languages.python.enterprise_engine.confidence_engine import PythonVersionConfidence
from version_upgrade_system.languages.python.enterprise_engine.risk_analyzer import PythonRiskAnalyzer
from version_upgrade_system.languages.python.enterprise_engine.validator import PythonValidator


class PythonEnterpriseUpgrader:

    def __init__(self):
        self.confidence = PythonVersionConfidence()
        self.risk = PythonRiskAnalyzer()
        self.validator = PythonValidator()

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