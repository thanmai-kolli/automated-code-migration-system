"""Compiles and runs programs for the version-upgrade engines with explicit standards.

The original program is built with its legacy standard and the upgraded program with
the target standard, so a comparison measures what the upgrade changed.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

from cross_language_system.core.test_executor import (
    ENABLE_FLAG,
    TIMEOUT_SECONDS,
    _minimal_env,
    _normalize,
    execution_enabled,
    parse_cases,
)

TARGET_STD = {"c": "-std=c17", "cpp": "-std=c++20"}
LEGACY_STD = {"c": "-std=gnu89", "cpp": "-std=gnu++98"}
COMPILERS = {"c": "gcc", "cpp": "g++"}
COMPILE_TIMEOUT = 20
JAVA_CLASS = re.compile(r"public\s+(?:final\s+|abstract\s+)?class\s+(\w+)")

# Generic inputs for a golden-master run: small integers read as ints, floats and words alike.
CHARACTERIZATION_INPUTS = (
    "\n".join(["3"] * 40),
    "\n".join(["10"] * 40),
    "\n".join(["4", "1", "7", "2", "9", "5", "8", "3", "6", "12"] * 4),
    "\n".join(["1 2 3 4 5"] * 20),
)
READS_INPUT = {
    "python": r"\b(raw_)?input\s*\(|\bsys\.stdin\b",
    "java": r"\bScanner\b|\bSystem\.in\b|\bBufferedReader\b",
    "c": r"\b(scanf|getchar|fgets|gets|getline|fgetc|getc)\s*\(",
    "cpp": r"\bcin\b|\b(scanf|getchar|fgets|gets|getline)\s*\(",
}
_PYTHON2 = []


def python2():
    """Command that runs a Python 2 interpreter, or None; the original of a 2-to-3 upgrade needs one."""
    if not _PYTHON2:
        command = None
        for candidate in (["python2"], ["python2.7"], ["py", "-2"]):
            if shutil.which(candidate[0]):
                try:
                    probe = subprocess.run(candidate + ["-c", "import sys; print(sys.version_info[0])"],
                                           capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    continue
                if probe.stdout.strip() == "2":
                    command = candidate
                    break
        _PYTHON2.append(command)
    return _PYTHON2[0]


def normalize_language(language):
    language = (language or "").lower()
    return "cpp" if language in ("cpp", "c++") else language


class Build:
    """Compiles once on entry; `run` executes the binary per input."""

    def __init__(self, language, code, std=None):
        self.language = normalize_language(language)
        self.code = code
        self.std = std
        self.directory = None
        self.command = None
        self.compiled = None
        self.errors = []
        self.warnings = 0

    def __enter__(self):
        self.directory = tempfile.mkdtemp(prefix="codeshift_upgrade_")
        try:
            self.command = self._compile()
            self.compiled = self.command is not None
        except _ToolchainMissing as exc:
            self.compiled = None
            self.errors = [str(exc)]
        except Exception as exc:
            self.compiled = False
            self.errors = [str(exc)[:4000]]
        return self

    def __exit__(self, *_):
        shutil.rmtree(self.directory, ignore_errors=True)
        return False

    def _write(self, name):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.code)
        return path

    def _invoke(self, command):
        result = subprocess.run(command, cwd=self.directory, capture_output=True, text=True,
                                timeout=COMPILE_TIMEOUT)
        diagnostics = (result.stderr or "") + (result.stdout or "")
        self.warnings = len(re.findall(r"\bwarning:", diagnostics))
        if result.returncode != 0:
            raise RuntimeError(diagnostics.strip() or "compilation failed")

    def _compile(self):
        if self.language == "python" and self.std == "python2":
            self._write("program.py")
            return python2() + ["program.py"]

        if self.language == "python":
            try:
                compile(self.code, "program.py", "exec")
            except SyntaxError as exc:
                raise RuntimeError(f"line {exc.lineno}: {exc.msg}")
            self._write("program.py")
            return [sys.executable, "program.py"]

        if self.language == "java":
            if not shutil.which("javac"):
                raise _ToolchainMissing("javac not found - compile validation skipped")
            match = JAVA_CLASS.search(self.code)
            name = match.group(1) if match else "Main"
            self._write(f"{name}.java")
            self._invoke(["javac", "-encoding", "UTF-8", f"{name}.java"])
            return ["java", "-cp", ".", name]

        if self.language in COMPILERS:
            compiler = shutil.which(COMPILERS[self.language])
            if not compiler:
                raise _ToolchainMissing(f"{COMPILERS[self.language]} not found - compile validation skipped")
            source = self._write("program.c" if self.language == "c" else "program.cpp")
            binary = os.path.join(self.directory, "program.exe" if os.name == "nt" else "program")
            flags = [self.std] if self.std else []
            self._invoke([compiler, *flags, source, "-o", binary, "-lm"])
            return [binary]

        raise RuntimeError(f"unsupported language: {self.language}")

    def run(self, stdin_text):
        if not self.compiled:
            return None, "; ".join(self.errors) or "not compiled"
        try:
            result = subprocess.run(self.command, cwd=self.directory,
                                    input=(stdin_text or "") + "\n", capture_output=True,
                                    text=True, timeout=TIMEOUT_SECONDS, env=_minimal_env())
        except subprocess.TimeoutExpired:
            return None, f"timed out after {TIMEOUT_SECONDS}s"
        stderr = (result.stderr or "").strip()
        # A legacy `void main()` exits with an arbitrary status, which is not a failure.
        crashed = result.returncode < 0 or result.returncode >= 0xC0000000
        if crashed or (result.returncode != 0 and stderr):
            return None, stderr or f"exit code {result.returncode}"
        return result.stdout, None


class _ToolchainMissing(Exception):
    pass


def compile_check(language, code):
    """compile_success is None when the toolchain is unavailable, never a silent True."""
    language = normalize_language(language)
    with Build(language, code, TARGET_STD.get(language)) as build:
        status = {True: "PASS", False: "FAIL", None: "SKIPPED"}[build.compiled]
        return {
            "compile_success": build.compiled,
            "compile_errors": build.errors,
            "warnings": build.warnings,
            "validation_status": status,
        }


def _legacy_build(language, original):
    """Build the original under the oldest standard that accepts it."""
    if language == "python" and python2():
        return Build(language, original, "python2").__enter__()
    for std in (LEGACY_STD.get(language), TARGET_STD.get(language), None):
        build = Build(language, original, std).__enter__()
        if build.compiled or language not in COMPILERS or std is None:
            return build
        build.__exit__()


def characterization(language, original):
    """Golden-master cases for a program the user gave no tests for.

    The original runs on generic inputs; each input on which it terminates and
    prints the same output twice becomes a case whose reference is that output.
    A Python 2 original needs a Python 2 interpreter: Python 3 would record
    different semantics (true division) as the expected behaviour.
    """
    language = normalize_language(language)
    if not execution_enabled() or language not in READS_INPUT or (language == "python" and not python2()):
        return [], None
    from version_upgrade_system.core.textscan import mask
    inputs = CHARACTERIZATION_INPUTS if re.search(READS_INPUT[language], mask(original, language)) else ("",)
    cases, references = [], []
    legacy = _legacy_build(language, original)
    try:
        if not legacy.compiled:
            return [], None
        for stdin_text in inputs:
            first, error = legacy.run(stdin_text)
            if error is not None:
                continue
            second, error = legacy.run(stdin_text)
            if error is not None or _normalize(first) != _normalize(second):
                continue
            cases.append((stdin_text, None))
            references.append((stdin_text, first, "original program", None))
    finally:
        legacy.__exit__()
    return (cases, references) if cases else ([], None)


def reference_outputs(language, original, raw_cases):
    """Expected output per case: the user's, else the original under its legacy standard."""
    language = normalize_language(language)
    cases = parse_cases(raw_cases)
    if not cases or not execution_enabled():
        return cases, None

    references = []
    legacy = _legacy_build(language, original)
    try:
        for stdin_text, expected in cases:
            if expected is not None:
                references.append((stdin_text, expected, "expected output", None))
                continue
            output, error = legacy.run(stdin_text)
            if error and language == "python" and legacy.compiled is False:
                error = "the original is Python 2 and cannot run here; add an expected output (===)"
            references.append((stdin_text, output, "original program", error))
    finally:
        legacy.__exit__()
    return cases, references


def check_behaviour(language, upgraded, cases, references):
    """Runs the upgraded program against precomputed references (test_executor format)."""
    if not cases:
        return None
    if references is None:
        return {
            "enabled": False,
            "reason": f"Set {ENABLE_FLAG}=1 to run test cases (executes submitted code locally).",
            "total": len(cases), "passed": 0, "failed": 0, "cases": [],
        }

    language = normalize_language(language)
    results = []
    with Build(language, upgraded, TARGET_STD.get(language)) as build:
        for index, (stdin_text, reference, basis, reference_error) in enumerate(references, start=1):
            output, error = build.run(stdin_text)
            ok = (error is None and reference_error is None
                  and _normalize(output) == _normalize(reference))
            results.append({
                "index": index,
                "input": stdin_text,
                "expected": reference if basis == "expected output" else None,
                "source_output": reference if basis == "original program" else None,
                "target_output": output,
                "error": error or reference_error,
                "compared_against": basis,
                "passed": ok,
            })

    passed = sum(1 for case in results if case["passed"])
    return {"enabled": True, "total": len(results), "passed": passed,
            "failed": len(results) - passed, "cases": results}
