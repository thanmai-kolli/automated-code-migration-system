from cross_language_system.core.language_registry import LanguageRegistry
from cross_language_system.core.semantic_analyzer import SemanticAnalyzer
from cross_language_system.core.confidence_engine import ConfidenceEngine
from cross_language_system.core.type_annotator import TypeAnnotator
from cross_language_system.utils.diff_generator import DiffGenerator
from cross_language_system.core.accuracy_engine import AccuracyEngine
from cross_language_system.core.token_similarity import compute_token_similarity
from cross_language_system.core.ast_similarity import compute_ast_similarity
from cross_language_system.core.structure_similarity import compute_structure_similarity

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

        # Build IR
        ir = parser.parse(code)
        if ir is None:
            return {"error": "Parsing failed. IR is None."}

        # Resolve concrete types before generation so statically typed targets
        # do not have to fall back to Object.
        TypeAnnotator().annotate(ir)

        # Semantic validation
        analyzer = SemanticAnalyzer()
        semantic_issues = analyzer.analyze(ir, source, target)

        # Generate target code
        generated_code = generator.generate(ir)
        if not generated_code:
            return {"error": "Code generation failed."}

        # Validate compilation
        compile_success, compile_errors = validator.validate(generated_code)
        compile_flag = 1 if compile_success else 0

        # Generate diff
        diff_data = DiffGenerator().generate(code, generated_code)
        token_similarity = compute_token_similarity(code, generated_code)
        ast_similarity = compute_ast_similarity(code, generated_code)
        structure_similarity = compute_structure_similarity(code, generated_code)
        metrics = {
            "diff_count": diff_data["total_changes"],
            "semantic_issues": len(semantic_issues),
            "compile_success": compile_flag,
            "risk_score": 1 if not compile_success else 0,
            "token_similarity": token_similarity,
            "ast_similarity": ast_similarity,
            "structure_similarity": structure_similarity
        }

        # Confidence scoring
        confidence_engine = ConfidenceEngine()
        accuracy_engine = AccuracyEngine()

        confidence = confidence_engine.predict(metrics)
        accuracy = round(accuracy_engine.predict(metrics,source,target),2)

        return {
        "source": source,
        "target": target,
        "code": generated_code,
        "compile_success": compile_success,
        "compile_errors": compile_errors,
        "semantic_issues": semantic_issues,
        "confidence": confidence,
        "accuracy": accuracy,
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