"""Validation-gated rule application shared by every version-upgrade engine.

Each rule is applied on its own and kept only if the program does not get worse:
compile status first, then the number of test cases reproduced. A rule that breaks a
working program is rejected and reported instead of being shipped to the user.
"""

import difflib
from dataclasses import dataclass, field
from typing import Callable

from version_upgrade_system.config import TARGET_VERSIONS
from version_upgrade_system.core import toolchain


@dataclass
class Rule:
    name: str
    apply: Callable[[str], str]
    # Kept rewrites whose behaviour can still differ without tests (reported as a risk).
    caution: str = ""


@dataclass
class Validation:
    compiled: object  # True / False / None when the toolchain is missing
    passed: int = 0
    errors: list = field(default_factory=list)
    warnings: int = 0

    def key(self):
        return (1 if self.compiled else 0, self.passed)


def diff(original, upgraded, language):
    lines = list(difflib.unified_diff(original.splitlines(), upgraded.splitlines(),
                                      fromfile=f"original.{language}", tofile=f"upgraded.{language}",
                                      lineterm=""))
    changes = sum(1 for line in lines if line[:1] in "+-" and not line.startswith(("+++", "---")))
    return "\n".join(lines), changes


def risk_level(compiled, tests_failed, triggers):
    if compiled is False or tests_failed:
        return "HIGH"
    return "MEDIUM" if triggers else "LOW"


class GatedUpgrader:
    """Subclasses define `language`, `engine`, `detector`, `rules()` and `findings()`."""

    language = ""
    engine = ""
    detector = None

    def rules(self, code):
        raise NotImplementedError

    def findings(self, original, upgraded):
        """Risks that remain in the upgraded code."""
        return []

    def _validate(self, code, references):
        with toolchain.Build(self.language, code, toolchain.TARGET_STD.get(self.language)) as build:
            result = Validation(build.compiled, errors=build.errors, warnings=build.warnings)
            if build.compiled and references:
                for stdin_text, reference, _, reference_error in references:
                    output, error = build.run(stdin_text)
                    if error is None and reference_error is None and \
                            toolchain._normalize(output) == toolchain._normalize(reference):
                        result.passed += 1
            return result

    def upgrade(self, code, test_cases=None):
        original = code
        cases, references = toolchain.reference_outputs(self.language, original, test_cases)

        current = original
        state = self._validate(current, references)
        applied, rejected, cautions = [], [], []

        for rule in self.rules(original):
            try:
                candidate = rule.apply(current)
            except Exception as exc:
                rejected.append(f"{rule.name} (rule failed: {exc})")
                continue
            if candidate == current:
                continue
            outcome = self._validate(candidate, references)
            if outcome.compiled is None or state.compiled is None or outcome.key() >= state.key():
                current, state = candidate, outcome
                applied.append(rule.name)
                if rule.caution:
                    cautions.append(rule.caution)
            elif outcome.compiled is False:
                rejected.append(f"{rule.name} (would not compile)")
            else:
                rejected.append(f"{rule.name} (changed program output)")

        test_results = toolchain.check_behaviour(self.language, current, cases, references)
        tests_failed = bool(test_results and test_results.get("enabled") and test_results["failed"])

        triggers = list(cautions)
        triggers += self.findings(original, current)
        if state.compiled is False:
            triggers.insert(0, "Upgraded code does not compile")
        if state.compiled is None:
            triggers.append("Compiler not available: rules were not validated")
        if rejected:
            triggers.append(f"{len(rejected)} rule(s) rejected by validation")
        if tests_failed:
            triggers.append(f"{test_results['failed']} of {test_results['total']} test cases failed")

        diff_text, changes = diff(original, current, self.language)
        result = {
            "code": current,
            "engine": self.engine,
            "detected_version": self.detector.detect(original),
            "target_version": TARGET_VERSIONS.get(self.language),
            "compile_success": state.compiled,
            "compile_errors": state.errors,
            "validation_status": {True: "PASS", False: "FAIL", None: "SKIPPED"}[state.compiled],
            "compiler_warnings": state.warnings,
            "applied_rules": applied,
            "rejected_rules": rejected,
            "risk_triggers": triggers,
            "risk_score": len(triggers),
            "risk_level": risk_level(state.compiled, tests_failed, triggers),
            "total_diff_changes": changes,
            "diff_text": diff_text,
        }
        if test_results is not None:
            result["test_results"] = test_results
            if test_results.get("enabled"):
                result["test_success"] = not tests_failed
        return result
