# from core.language_detector import LanguageDetector
# from core.risk_scorer import RiskScorer
# from core.semantic_validator import SemanticValidator
# from core.report import UpgradeReport
# from config import TARGET_VERSIONS

# # Language modules will be plugged in later
# # (placeholders for now)

# class UpgradeEngine:

#     def __init__(self):
#         self.detector = LanguageDetector()
#         self.risk_scorer = RiskScorer()
#         self.validator = SemanticValidator()

#     def upgrade(self, code, language=None):

#         report = UpgradeReport()

#         # 1️⃣ Detect language if not provided
#         if not language:
#             language = self.detector.detect(code)

#         if language == "unknown":
#             return {"error": "Unsupported or undetected language"}

#         report.language = language
#         report.target_version = TARGET_VERSIONS.get(language)

#         # 2️⃣ Version detection (placeholder ML)
#         detected_version, confidence = self._mock_version_detection(code)
#         report.detected_version = detected_version

#         # 3️⃣ Call language-specific upgrader
#         result = self._dispatch_to_language(code, language)

#         if "error" in result:
#             return result

#         upgraded_code = result["code"]
#         changes = result.get("changes", [])
#         compile_success = result.get("compile_success", True)
#         compile_errors = result.get("compile_errors")

#         report.changes = changes
#         report.compile_success = compile_success
#         report.compile_errors = compile_errors

#         # 4️⃣ Risk scoring
#         risk_score, risk_level = self.risk_scorer.compute(
#             len(changes),
#             confidence,
#             compile_success
#         )

#         report.risk_score = risk_score
#         report.risk_level = risk_level

#         # 5️⃣ Semantic validation
#         report.validation_status = self.validator.validate(
#             compile_success,
#             changes
#         )

#         return {
#             "upgraded_code": upgraded_code,
#             "report": report.generate()
#         }

#     # 🔹 Replace with real ML later
#     def _mock_version_detection(self, code):

#         if "raw_input" in code:
#             return "legacy_version", 0.85

#         if "NULL" in code:
#             return "legacy_version", 0.80

#         return "modern_version", 0.95

#     # 🔹 Dispatch layer (pluggable)
#     def _dispatch_to_language(self, code, language):

#         if language == "python":
#             from version_upgrade_system.languages.python.legacy_ast_engine.python_upgrader import PythonUpgrader
#             return PythonUpgrader().upgrade(code)

#         elif language == "java":
#             from languages.java.java_upgrader import JavaUpgrader
#             return JavaUpgrader().upgrade(code)

#         elif language == "c":
#             from languages.c.c_upgrader import CUpgrader
#             return CUpgrader().upgrade(code)

#         elif language == "cpp":
#             from languages.cpp.cpp_upgrader import CppUpgrader
#             return CppUpgrader().upgrade(code)

#         return {"error": "Language module not implemented"}
# class UpgradeEngine:

#     def upgrade(self, code, language, mode="enterprise"):

#         language = language.lower()

#         if language == "python":
#             return self._upgrade_python(code, mode)

#         if language == "java":
#             return self._upgrade_java(code)

#         return {
#             "error": f"Unsupported language: {language}"
#         }

#     # ---------------- Python ----------------
#     def _upgrade_python(self, code, mode):

#         if mode == "legacy":
#             from languages.python.legacy_ast_engine.python_upgrader import PythonUpgrader
#             upgrader = PythonUpgrader()

#         else:
#             from languages.python.enterprise_engine.python_upgrader import PythonEnterpriseUpgrader
#             upgrader = PythonEnterpriseUpgrader()

#         return upgrader.upgrade(code)

#     # ---------------- Java ----------------
#     def _upgrade_java(self, code):

#         from languages.java.enterprise_engine.java_upgrader import JavaEnterpriseUpgrader
#         upgrader = JavaEnterpriseUpgrader()

#         return upgrader.upgrade(code)
class UpgradeEngine:

    def upgrade(self, code, language, mode="enterprise"):

        language = language.lower()

        # ---------------- PYTHON ----------------
        if language == "python":
            from version_upgrade_system.languages.python.enterprise_engine.python_upgrader import PythonEnterpriseUpgrader
            engine = PythonEnterpriseUpgrader()
            return engine.upgrade(code)

            # if mode == "legacy":
            #     from languages.python.legacy_ast_engine.python_upgrader import PythonUpgrader
            #     engine = PythonUpgrader()
            # else:
            #     from languages.python.enterprise_engine.python_upgrader import PythonEnterpriseUpgrader
            #     engine = PythonEnterpriseUpgrader()
            #
            # return engine.upgrade(code)

        # ---------------- JAVA ----------------
        elif language == "java":

            from version_upgrade_system.languages.java.enterprise_engine.java_upgrader import JavaEnterpriseUpgrader
            engine = JavaEnterpriseUpgrader()
            return engine.upgrade(code)

        # ---------------- C++ ----------------
        elif language in ["cpp", "c++"]:

            from version_upgrade_system.languages.cpp.enterprise_engine.cpp_upgrader import CppEnterpriseUpgrader
            engine = CppEnterpriseUpgrader()
            return engine.upgrade(code)

        # ---------------- C ----------------
        elif language == "c":

            from version_upgrade_system.languages.c.enterprise_engine.c_upgrader import CEnterpriseUpgrader
            engine = CEnterpriseUpgrader()
            return engine.upgrade(code)

        else:
            return {
                "error": f"Unsupported language: {language}"
            }