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
    # PYTHON 2 -> 3 RULES
    #
    # (pattern, replacement, description). Applied to whole lines, so the
    # indentation captured by each pattern is preserved.
    # -----------------------------------
    RULES = [
        (r'\.iteritems\(\)', '.items()', "dict.iteritems() -> items()"),
        (r'\.iterkeys\(\)', '.keys()', "dict.iterkeys() -> keys()"),
        (r'\.itervalues\(\)', '.values()', "dict.itervalues() -> values()"),
        (r'\bxrange\(', 'range(', "xrange() -> range()"),
        (r'\braw_input\(', 'input(', "raw_input() -> input()"),
        (r'\bbasestring\b', 'str', "basestring -> str"),
        (r'\bunicode\(', 'str(', "unicode() -> str()"),
        (r'\blong\(', 'int(', "long() -> int()"),
        (r'<>', '!=', "<> -> !="),
        (r'^(\s*)except\s+([\w.]+)\s*,\s*(\w+)\s*:', r'\1except \2 as \3:',
         "except X, e -> except X as e"),
        (r'(\w+)\.has_key\((.+?)\)', r'\2 in \1', "dict.has_key(k) -> k in dict"),
    ]

    def safe_print_upgrade(self, code):

        pattern = r'^(\s*)print\s+(.*)$'
        lines = code.splitlines()
        new_lines = []
        changed = False

        for line in lines:
            match = re.match(pattern, line)
            if match:
                indent = match.group(1)
                content = match.group(2).rstrip()
                new_lines.append(f'{indent}print({content})')
                changed = True
            else:
                new_lines.append(line)

        return "\n".join(new_lines), changed

    def _apply_rules(self, code):
        """Run every modernization rule, reporting which ones actually fired."""

        applied = []

        code, printed = self.safe_print_upgrade(code)
        if printed:
            applied.append("Python2 to Python3 print modernization")

        for pattern, replacement, description in self.RULES:
            updated, count = re.subn(pattern, replacement, code, flags=re.MULTILINE)
            if count:
                code = updated
                applied.append(description)

        return code, applied

    def upgrade(self, code):

        original = code

        # --------------------------
        # Safe upgrade logic
        # --------------------------
        upgraded, applied_rules = self._apply_rules(code)

        # --------------------------
        # Validation
        # --------------------------
        validation = self.validator.validate(upgraded)

        # A rule that breaks the file is worse than no upgrade at all.
        if not validation["compile_success"] and self.validator.validate(original)["compile_success"]:
            upgraded = original
            applied_rules = []
            validation = self.validator.validate(original)

        # --------------------------
        # Risk Analysis
        # --------------------------
        risk_data = self.risk.compute(original, upgraded, applied_rules)

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