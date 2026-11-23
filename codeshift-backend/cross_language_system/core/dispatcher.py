import re

from cross_language_system.core.language_registry import LanguageRegistry
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.semantic_analyzer import SemanticAnalyzer
from cross_language_system.core.confidence_engine import ConfidenceEngine
from cross_language_system.core.type_annotator import TypeAnnotator
from cross_language_system.utils.diff_generator import DiffGenerator
from cross_language_system.core.accuracy_engine import AccuracyEngine
from cross_language_system.core.model_features import construct_profile, direction, helper_count
from cross_language_system.core.token_similarity import compute_token_similarity
from cross_language_system.core.ast_similarity import compute_ast_similarity
from cross_language_system.core.structure_similarity import compute_structure_similarity


def risk_level(compile_success, triggers, tests_failed=False):
    if not compile_success or tests_failed:
        return "HIGH"
    return "MEDIUM" if triggers else "LOW"


def _has_code(code, source):
    """Whether the input holds anything beyond comments and preprocessor lines."""

    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    comment = "#" if source == "python" else "//"
    lines = []
    for line in stripped.splitlines():
        line = line.split(comment, 1)[0].strip()
        if line and not (source != "python" and line.startswith("#")):
            lines.append(line)
    return bool(lines)


class CrossLanguageEngine:

    def convert(self, code, source, target):

        source = source.lower()
        target = target.lower()

        if not LanguageRegistry.is_supported(source):
            return {"error": f"Unsupported source language: {source}"}

        if not LanguageRegistry.is_supported(target):
            return {"error": f"Unsupported target language: {target}"}

        if source == target:
            return {"error": "Source and target language cannot be same."}

        parser = self._get_parser(source, target)
        generator = self._get_generator(source, target)
        validator = self._get_validator(target)

        # Parse, type and generate. A construct the engine cannot translate
        # faithfully is reported, never approximated.
        try:
            ir = parser.parse(code)
            if ir is None:
                return {"error": "Parsing failed. IR is None."}
            if not ir.body and _has_code(code, source):
                return {"error": f"Nothing in this {source} program could be translated."}

            # Resolve concrete types before generation so statically typed
            # targets do not have to fall back to Object.
            TypeAnnotator(source).annotate(ir)

            semantic_issues = SemanticAnalyzer().analyze(ir, source, target)
            generated_code = generator.generate(ir)
        except UnsupportedConstruct as exc:
            return {"error": f"Cannot translate this program faithfully: {exc}."}
        except SyntaxError as exc:
            return {"error": f"The {source} program could not be parsed: {exc.msg if hasattr(exc, 'msg') and exc.msg else exc}"}

        if not generated_code:
            return {"error": "Code generation failed."}

        # Validate compilation
        compile_success, compile_errors = validator.validate(generated_code)
        compile_flag = 1 if compile_success else 0

        risk_triggers = [] if compile_success else ["Generated code does not compile"]
        risk_triggers += [issue for issue in semantic_issues
                          if issue.startswith("Unsupported") or "not lowered" in issue]

        # Generate diff
        diff_data = DiffGenerator().generate(code, generated_code)
        token_similarity = compute_token_similarity(code, generated_code)
        ast_similarity = compute_ast_similarity(code, generated_code)
        structure_similarity = compute_structure_similarity(code, generated_code)

        # One feature vector, used both here and by ml/build_dataset.py, so
        # what the models are trained on is exactly what they are served.
        features = {
            "compile_success": compile_flag,
            "risk_score": len(risk_triggers),
            "semantic_issues": len(semantic_issues),
            "diff_count": diff_data["total_changes"],
            "token_similarity": token_similarity,
            "ast_similarity": ast_similarity,
            "structure_similarity": structure_similarity,
            **construct_profile(ir),
            "n_helpers": helper_count(generated_code),
            **direction(source, target),
        }

        confidence = ConfidenceEngine().predict(features)
        accuracy = AccuracyEngine().predict(features, source, target)

        return {
        "source": source,
        "target": target,
        "code": generated_code,
        "compile_success": compile_success,
        "compile_errors": compile_errors,
        "semantic_issues": semantic_issues,
        "confidence": confidence,
        "accuracy": accuracy,
        "risk_level": risk_level(compile_success, risk_triggers),
        "risk_score": len(risk_triggers),
        "risk_triggers": risk_triggers,
        "features": features,
        "token_similarity": token_similarity,
        "ast_similarity": ast_similarity,
        "structure_similarity": structure_similarity,
        "diff_text": diff_data["diff_text"],
        "diff_count": diff_data["total_changes"]
    }
    # ---------------- Parser Loader ----------------

    def _get_parser(self, source, target=None):

        if source == "python":
            from cross_language_system.parsers.python_parser import PythonParser
            return PythonParser()

        if source == "java":
            from cross_language_system.parsers.java_parser import JavaParser
            return JavaParser()

        if source in ["cpp","c++"]:
            from cross_language_system.parsers.cpp_parser import CppParser
            return CppParser(target)

        if source == "c":
            from cross_language_system.parsers.c_parser import CParser
            return CParser(target)

    # ---------------- Generator Loader ----------------

    def _get_generator(self, source, target):

        if target == "java":
            from cross_language_system.generators.java_generator import JavaGenerator
            return JavaGenerator(source, target)

        if target == "python":
            from cross_language_system.generators.python_generator import PythonGenerator
            return PythonGenerator(source, target)

        if target in ["c++", "cpp"]:
            from cross_language_system.generators.cpp_generator import CppGenerator
            return CppGenerator(source, target)

        if target == "c":
            from cross_language_system.generators.c_generator import CGenerator
            return CGenerator(source, target)

    # ---------------- Validator Loader ----------------

    def _get_validator(self, target):

        if target == "java":
            from cross_language_system.validators.java_validator import JavaValidator
            return JavaValidator()

        if target == "python":
            from cross_language_system.validators.python_validator import PythonValidator
            return PythonValidator()

        if target in ["cpp", "c++"]:
            from cross_language_system.validators.cpp_validator import CppValidator
            return CppValidator()

        if target == "c":
            from cross_language_system.validators.c_validator import CValidator
            return CValidator()