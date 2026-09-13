from core.language_registry import LanguageRegistry
from core.semantic_analyzer import SemanticAnalyzer
from core.confidence_engine import ConfidenceEngine
from utils.diff_generator import DiffGenerator


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

        parser = self._get_parser(source)
        generator = self._get_generator(source, target)
        validator = self._get_validator(target)

        # Build IR
        ir = parser.parse(code)
        if ir is None:
            return {"error": "Parsing failed. IR is None."}

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

        # 🔹 Collect structural metrics
        num_object_types = generated_code.count("Object")

        num_generic_types = (
            generated_code.count("List<") +
            generated_code.count("Map<") +
            generated_code.count("Set<")
        )

        num_loops = generated_code.count("for (") + generated_code.count("while (")

        num_conditionals = generated_code.count("if (")
        # Generate diff
        diff_data = DiffGenerator().generate(code, generated_code)
        source_lines = len(code.splitlines())
        diff_ratio = diff_data["total_changes"] / max(source_lines, 1)
        
        metrics = {
            "compile_success": compile_flag,
            "num_object_types": num_object_types,
            "num_generic_types": num_generic_types,
            "num_loops": num_loops,
            "num_conditionals": num_conditionals,
            "diff_ratio": diff_ratio,
            "semantic_issues": len(semantic_issues)
        }
        

        # Confidence scoring
        confidence = ConfidenceEngine().predict(metrics)

        return {
            "source": source,
            "target": target,
            "code": generated_code,
            "compile_success": compile_success,
            "compile_errors": compile_errors,
            "semantic_issues": semantic_issues,
            "confidence": confidence,
            "diff_text": diff_data["diff_text"],
            "diff_count": diff_data["total_changes"]
        }

    # ---------------- Parser Loader ----------------

    def _get_parser(self, source):

        if source == "python":
            from parsers.python_parser import PythonParser
            return PythonParser()

        if source == "java":
            from parsers.java_parser import JavaParser
            return JavaParser()

        if source == "cpp":
            from parsers.cpp_parser import CppParser
            return CppParser()

        if source == "c":
            from parsers.c_parser import CParser
            return CParser()

    # ---------------- Generator Loader ----------------

    def _get_generator(self, source, target):

        if target == "java":
            from generators.java_generator import JavaGenerator
            return JavaGenerator(source, target)

        if target == "python":
            from generators.python_generator import PythonGenerator
            return PythonGenerator(source, target)

        if target == "cpp":
            from generators.cpp_generator import CppGenerator
            return CppGenerator(source, target)

        if target == "c":
            from generators.c_generator import CGenerator
            return CGenerator(source, target)

    # ---------------- Validator Loader ----------------

    def _get_validator(self, target):

        if target == "java":
            from validators.java_validator import JavaValidator
            return JavaValidator()

        if target == "python":
            from validators.python_validator import PythonValidator
            return PythonValidator()

        if target == "cpp":
            from validators.cpp_validator import CppValidator
            return CppValidator()

        if target == "c":
            from validators.c_validator import CValidator
            return CValidator()