import os
import shutil

import pytest

from cross_language_system.core import test_executor
from cross_language_system.core.test_executor import (
    ENABLE_FLAG, parse_cases, run_test_cases,
)


@pytest.fixture
def execution_enabled(monkeypatch):
    monkeypatch.setenv(ENABLE_FLAG, "1")


PY_ADD = "a, b = input().split()\nprint(int(a) + int(b))\n"
PY_ADD_BROKEN = "a, b = input().split()\nprint(int(a) * int(b))\n"


class TestCaseParsing:

    def test_empty_input_yields_nothing(self):
        assert parse_cases("") == []
        assert parse_cases("   \n  ") == []
        assert parse_cases(None) == []

    def test_single_case_with_expected(self):
        assert parse_cases("2 3\n===\n5") == [("2 3", "5")]

    def test_case_without_expected(self):
        assert parse_cases("2 3") == [("2 3", None)]

    def test_multiple_cases(self):
        cases = parse_cases("2 3\n===\n5\n---\n10 20\n===\n30")
        assert cases == [("2 3", "5"), ("10 20", "30")]

    def test_longer_separators_are_accepted(self):
        assert parse_cases("1\n=====\n1\n------\n2\n=====\n2") == [("1", "1"), ("2", "2")]

    def test_case_count_is_capped(self):
        blob = "\n---\n".join(f"{i}\n===\n{i}" for i in range(50))
        assert len(parse_cases(blob)) == test_executor.MAX_CASES


class TestDisabledByDefault:
    """Execution must never happen without the opt-in flag."""

    def test_returns_none_when_no_cases(self, monkeypatch):
        monkeypatch.delenv(ENABLE_FLAG, raising=False)
        assert run_test_cases("python", PY_ADD, "python", PY_ADD, "") is None

    def test_reports_disabled_instead_of_running(self, monkeypatch):
        monkeypatch.delenv(ENABLE_FLAG, raising=False)
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3\n===\n5")
        assert result["enabled"] is False
        assert result["total"] == 1
        assert result["cases"] == []
        assert ENABLE_FLAG in result["reason"]

    def test_flag_must_be_exactly_one(self, monkeypatch):
        monkeypatch.setenv(ENABLE_FLAG, "true")
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3")
        assert result["enabled"] is False


@pytest.mark.usefixtures("execution_enabled")
class TestPythonExecution:

    def test_expected_output_passes(self):
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3\n===\n5")
        assert result["enabled"] is True
        assert result["passed"] == 1
        assert result["failed"] == 0

    def test_wrong_output_fails(self):
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3\n===\n99")
        assert result["failed"] == 1
        assert result["cases"][0]["target_output"].strip() == "5"

    def test_differential_comparison_without_expected(self):
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3")
        assert result["passed"] == 1
        assert result["cases"][0]["compared_against"] == "original program"

    def test_differential_catches_behaviour_change(self):
        result = run_test_cases("python", PY_ADD, "python", PY_ADD_BROKEN, "2 3")
        assert result["failed"] == 1
        assert result["cases"][0]["source_output"].strip() == "5"
        assert result["cases"][0]["target_output"].strip() == "6"

    def test_multiple_cases_are_all_run(self):
        result = run_test_cases(
            "python", PY_ADD, "python", PY_ADD, "2 3\n===\n5\n---\n10 20\n===\n30"
        )
        assert result["total"] == 2
        assert result["passed"] == 2

    def test_runtime_error_is_reported_not_raised(self):
        result = run_test_cases("python", PY_ADD, "python", "raise SystemExit(3)\n", "2 3")
        assert result["failed"] == 1
        assert result["cases"][0]["error"]

    def test_infinite_loop_is_killed(self):
        result = run_test_cases("python", PY_ADD, "python", "while True:\n    pass\n", "2 3")
        assert result["failed"] == 1
        assert "timed out" in result["cases"][0]["error"]

    def test_trailing_whitespace_is_ignored(self):
        result = run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3\n===\n5   ")
        assert result["passed"] == 1


@pytest.mark.usefixtures("execution_enabled")
class TestCrossLanguageExecution:

    JAVA_ADD = (
        "import java.util.*;\n"
        "public class Converted {\n"
        "    public static void main(String[] args) {\n"
        "        Scanner sc = new Scanner(System.in);\n"
        "        System.out.println(sc.nextInt() + sc.nextInt());\n"
        "    }\n"
        "}\n"
    )

    C_ADD = (
        "#include <stdio.h>\n"
        "int main() {\n"
        "    int a, b;\n"
        "    scanf(\"%d %d\", &a, &b);\n"
        "    printf(\"%d\\n\", a + b);\n"
        "    return 0;\n"
        "}\n"
    )

    @pytest.mark.skipif(not shutil.which("javac"), reason="javac not installed")
    def test_python_against_java(self):
        result = run_test_cases("python", PY_ADD, "java", self.JAVA_ADD, "2 3")
        assert result["passed"] == 1, result["cases"]

    @pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")
    def test_python_against_c(self):
        result = run_test_cases("python", PY_ADD, "c", self.C_ADD, "2 3\n===\n5")
        assert result["passed"] == 1, result["cases"]

    @pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")
    def test_compile_failure_is_reported(self):
        result = run_test_cases("python", PY_ADD, "c", "int main( {\n", "2 3")
        assert result["failed"] == 1
        assert result["cases"][0]["error"]

    def test_unrunnable_language_is_reported(self):
        result = run_test_cases("python", PY_ADD, "rust", "fn main() {}", "2 3")
        assert result["failed"] == 1
        assert "rust" in result["cases"][0]["error"]


@pytest.mark.usefixtures("execution_enabled")
class TestCleanup:

    def test_temp_directories_are_removed(self):
        import tempfile

        before = set(os.listdir(tempfile.gettempdir()))
        run_test_cases("python", PY_ADD, "python", PY_ADD, "2 3")
        after = set(os.listdir(tempfile.gettempdir()))

        leaked = [d for d in after - before if d.startswith("codeshift_run_")]
        assert not leaked, f"leaked temp dirs: {leaked}"
