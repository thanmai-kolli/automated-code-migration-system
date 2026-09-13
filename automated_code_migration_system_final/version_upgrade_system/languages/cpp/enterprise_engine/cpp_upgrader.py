# from .version_detector import CppVersionDetector
# from .risk_analyzer import CppRiskAnalyzer
# from .validator import CppValidator
# from .diff_generator import DiffGenerator
# from .confidence_engine import CppVersionConfidence
#
# # Fallback transformer (regex-based safe mode)
# from .fallback_transformer import CppFallbackTransformer
#
# try:
#     from .ast_parser import CppASTParser
#     from .ownership_analyzer import OwnershipAnalyzer
#     from .raii_transformer import RAIITransformer
#     from .move_semantics import MoveSemanticsOptimizer
#     LIBCLANG_AVAILABLE = True
# except Exception:
#     LIBCLANG_AVAILABLE = False
#
#
# class CppEnterpriseUpgrader:
#
#     def __init__(self):
#
#         self.detector = CppVersionDetector()
#         self.risk = CppRiskAnalyzer()
#         self.validator = CppValidator()
#         self.diff = DiffGenerator()
#         self.confidence = CppVersionConfidence()
#
#         self.libclang_enabled = False
#
#         if LIBCLANG_AVAILABLE:
#             try:
#                 self.parser = CppASTParser()
#                 self.ownership = OwnershipAnalyzer()
#                 self.raii = RAIITransformer()
#                 self.move_optimizer = MoveSemanticsOptimizer()
#                 self.libclang_enabled = True
#             except Exception:
#                 self.libclang_enabled = False
#
#         self.fallback = CppFallbackTransformer()
#
#     def upgrade(self, code):
#
#         original = code
#         detected_version = self.detector.detect(code)
#
#         # -------------------------------------------------
#         # Try AST Mode
#         # -------------------------------------------------
#         if self.libclang_enabled:
#
#             try:
#                 translation_unit = self.parser.parse(code)
#                 raw_alloc_lines = self.ownership.analyze(translation_unit)
#                 upgraded = self.raii.transform(code, raw_alloc_lines)
#                 upgraded = self.move_optimizer.optimize(upgraded)
#                 engine_used = "enterprise_cpp_ast"
#
#             except Exception:
#                 upgraded = self.fallback.transform(code)
#                 engine_used = "enterprise_cpp_fallback"
#
#         # -------------------------------------------------
#         # Fallback Mode
#         # -------------------------------------------------
#         else:
#             upgraded = self.fallback.transform(code)
#             engine_used = "enterprise_cpp_fallback"
#
#         compile_success, compile_errors = self.validator.validate(upgraded)
#
#         risk_data = self.risk.compute(original)
#         diff_data = self.diff.generate(original, upgraded)
#
#         confidence_score = self.confidence.calculate(
#             compile_success,
#             risk_data["risk_score"],
#             diff_data["total_changes"]
#         )
#
#         return {
#             "code": upgraded,
#             "engine": engine_used,
#             "detected_version": detected_version,
#             "compile_success": compile_success,
#             "compile_errors": compile_errors,
#             "confidence_score": confidence_score,
#             "diff_text": diff_data["diff_text"],
#             "total_diff_changes": diff_data["total_changes"],
#             **risk_data
#         }


from .version_detector import CppVersionDetector
from .risk_analyzer import CppRiskAnalyzer
from .validator import CppValidator
from .diff_generator import DiffGenerator
from .confidence_engine import CppVersionConfidence

from .fallback_transformer import CppFallbackTransformer

try:
    from .ast_parser import CppASTParser
    from .ownership_analyzer import OwnershipAnalyzer
    from .raii_transformer import RAIITransformer
    from .move_semantics import MoveSemanticsOptimizer
    LIBCLANG_AVAILABLE = True
except Exception:
    LIBCLANG_AVAILABLE = False


class CppEnterpriseUpgrader:

    def __init__(self):

        self.detector = CppVersionDetector()
        self.risk = CppRiskAnalyzer()
        self.validator = CppValidator()
        self.diff = DiffGenerator()
        self.confidence = CppVersionConfidence()

        self.libclang_enabled = False

        if LIBCLANG_AVAILABLE:
            try:
                self.parser = CppASTParser()
                self.ownership = OwnershipAnalyzer()
                self.raii = RAIITransformer()
                self.move_optimizer = MoveSemanticsOptimizer()
                self.libclang_enabled = True
            except Exception:
                self.libclang_enabled = False

        self.fallback = CppFallbackTransformer()

    def upgrade(self, code):

        original = code
        detected_version = self.detector.detect(code)

        # ---------------- AST Mode ----------------
        if self.libclang_enabled:
            try:
                translation_unit = self.parser.parse(code)
                raw_alloc_lines = self.ownership.analyze(translation_unit)
                upgraded = self.raii.transform(code, raw_alloc_lines)
                upgraded = self.move_optimizer.optimize(upgraded)
                engine_used = "enterprise_cpp_ast"
            except Exception:
                upgraded = self.fallback.transform(code)
                engine_used = "enterprise_cpp_fallback"
        else:
            upgraded = self.fallback.transform(code)
            engine_used = "enterprise_cpp_fallback"

        # ---------------- Validation ----------------
        validation = self.validator.validate(upgraded)

        # ---------------- Risk ----------------
        risk_data = self.risk.compute(original, upgraded)

        # ---------------- Diff ----------------
        diff_data = self.diff.generate(original, upgraded)

        total_changes = diff_data["total_changes"]

        # ---------------- ML Confidence ----------------
        confidence_score = self.confidence.calculate_confidence(
            changes_count=total_changes,
            risky_changes=risk_data["risk_score"],
            syntax_valid=validation["compile_success"],
            semantic_valid=validation["validation_status"] == "PASS",
            test_passed=validation["test_success"],
            diff_ratio=risk_data["diff_ratio"]
        )

        return {
            "code": upgraded,
            "engine": engine_used,
            "detected_version": detected_version,
            "compile_success": validation["compile_success"],
            "compile_errors": validation["compile_errors"],
            "validation_status": validation["validation_status"],
            "risk_score": risk_data["risk_score"],
            "risk_level": risk_data["risk_level"],
            "risk_triggers": risk_data["risk_triggers"],
            "total_diff_changes": total_changes,
            "confidence_score": confidence_score,
            "diff_text": diff_data["diff_text"],
            "test_success": validation["test_success"]
        }