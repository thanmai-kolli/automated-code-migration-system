"""Behavioural test execution for migrations.

Compiles and runs the original and migrated programs against the same stdin and
compares their stdout. This is what turns "it compiles" into "it behaves the
same", but it means executing user-submitted source, so it is disabled unless
CODESHIFT_ENABLE_TEST_EXECUTION=1 is set. Intended for local use only.

Test case format — cases separated by `---`, input and expected output by `===`:

    2 3
    ===
    5
    ---
    10 20
    ===
    30

The `===` section is optional. Without it a case still runs both programs and
compares them against each other, which needs no expected output at all.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ENABLE_FLAG = "CODESHIFT_ENABLE_TEST_EXECUTION"

# Deliberately tight: these bound a process running code we did not write.
TIMEOUT_SECONDS = int(os.getenv("CODESHIFT_TEST_TIMEOUT", "5"))
MAX_CASES = 20
MAX_INPUT_CHARS = 10_000
MAX_OUTPUT_CHARS = 10_000

CASE_SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
IO_SEPARATOR = re.compile(r"^\s*={3,}\s*$", re.MULTILINE)
JAVA_CLASS = re.compile(r"public\s+class\s+(\w+)")


def execution_enabled():
    return os.getenv(ENABLE_FLAG, "0") == "1"


def parse_cases(text):
    """Split the raw panel text into (stdin, expected-or-None) pairs."""

    if not text or not text.strip():
        return []

    cases = []

    for block in CASE_SEPARATOR.split(text):

        if not block.strip():
            continue

        parts = IO_SEPARATOR.split(block, maxsplit=1)
        stdin = parts[0].strip("\n")
        expected = parts[1].strip() if len(parts) > 1 else None

        if len(stdin) > MAX_INPUT_CHARS:
            stdin = stdin[:MAX_INPUT_CHARS]

        cases.append((stdin, expected))

        if len(cases) >= MAX_CASES:
            break

    return cases


def _normalize(output):
    """Compare on content, not incidental whitespace."""
    return "\n".join(line.rstrip() for line in (output or "").strip().splitlines())


def _minimal_env():
    # Windows needs SYSTEMROOT for sockets/CRT init; PATH is needed to find toolchains.
    keys = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT")
    return {k: os.environ[k] for k in keys if k in os.environ}


class ProgramRunner:
    """Compiles once, then runs the program per test case."""

    def __init__(self, language, code):
        self.language = (language or "").lower()
        if self.language == "cpp":
            self.language = "c++"
        self.code = code
        self.directory = None
        self.command = None
        self.error = None

    def __enter__(self):
        self.directory = tempfile.mkdtemp(prefix="codeshift_run_")
        try:
            self.command = self._prepare()
        except Exception as exc:
            self.error = str(exc)
        return self

    def __exit__(self, *_):
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
        return False

    # ------------------------------------------------------------
    # SETUP
    # ------------------------------------------------------------

    def _write(self, filename):
        path = os.path.join(self.directory, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.code)
        return path

    def _compile(self, command):
        result = subprocess.run(
            command,
            cwd=self.directory,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS * 4,
            env=_minimal_env(),
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[:MAX_OUTPUT_CHARS] or "compilation failed")

    def _prepare(self):

        if self.language == "python":
            self._write("program.py")
            return [sys.executable, "program.py"]

        if self.language == "java":
            if not shutil.which("javac") or not shutil.which("java"):
                raise RuntimeError("javac/java not found on PATH")
            match = JAVA_CLASS.search(self.code)
            class_name = match.group(1) if match else "Converted"
            self._write(f"{class_name}.java")
            self._compile(["javac", f"{class_name}.java"])
            return ["java", "-cp", ".", class_name]

        if self.language in ("c", "c++"):
            compiler = "gcc" if self.language == "c" else "g++"
            if not shutil.which(compiler):
                raise RuntimeError(f"{compiler} not found on PATH")
            source = "program.c" if self.language == "c" else "program.cpp"
            self._write(source)
            binary = "program.exe" if os.name == "nt" else "program"
            self._compile([compiler, source, "-o", binary])
            return [os.path.join(self.directory, binary)]

        raise RuntimeError(f"cannot execute language: {self.language}")

    # ------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------

    def run(self, stdin_text):

        if self.error:
            return None, self.error

        try:
            result = subprocess.run(
                self.command,
                cwd=self.directory,
                input=(stdin_text or "") + "\n",
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                env=_minimal_env(),
            )
        except subprocess.TimeoutExpired:
            return None, f"timed out after {TIMEOUT_SECONDS}s"
        except Exception as exc:
            return None, str(exc)

        if result.returncode != 0:
            return None, (result.stderr.strip()[:MAX_OUTPUT_CHARS] or f"exit code {result.returncode}")

        return result.stdout[:MAX_OUTPUT_CHARS], None


def run_test_cases(source_language, source_code, target_language, target_code, raw_cases):
    """Execute both programs against each case and compare their output.

    Returns None when execution is disabled or there is nothing to run, so the
    report simply omits the section rather than showing a misleading zero.
    """

    cases = parse_cases(raw_cases)

    if not cases:
        return None

    if not execution_enabled():
        return {
            "enabled": False,
            "reason": f"Set {ENABLE_FLAG}=1 to run test cases (executes submitted code locally).",
            "total": len(cases),
            "passed": 0,
            "failed": 0,
            "cases": [],
        }

    results = []
    passed = 0

    with ProgramRunner(source_language, source_code) as original, \
            ProgramRunner(target_language, target_code) as migrated:

        for index, (stdin_text, expected) in enumerate(cases, start=1):

            source_output, source_error = original.run(stdin_text)
            target_output, target_error = migrated.run(stdin_text)

            if expected is not None:
                ok = target_error is None and _normalize(target_output) == _normalize(expected)
                basis = "expected output"
            else:
                # Differential: the migration must behave like the original.
                ok = (
                    target_error is None
                    and source_error is None
                    and _normalize(target_output) == _normalize(source_output)
                )
                basis = "original program"

            passed += 1 if ok else 0

            results.append({
                "index": index,
                "input": stdin_text,
                "expected": expected,
                "source_output": source_output,
                "target_output": target_output,
                "error": target_error or source_error,
                "compared_against": basis,
                "passed": ok,
            })

    return {
        "enabled": True,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
    }
