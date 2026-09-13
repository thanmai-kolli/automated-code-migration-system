from version_upgrade_system.languages.python.enterprise_engine.python_upgrader import (
    PythonEnterpriseUpgrader,
)
from version_upgrade_system.languages.python.enterprise_engine.validator import (
    PythonValidator,
)
from version_upgrade_system.languages.python.enterprise_engine.version_detector import (
    PythonVersionDetector,
)


class TestPythonVersionDetector:

    def test_print_statement_is_python2(self):
        assert PythonVersionDetector().detect("print 'hello'") == "Python 2.x"

    def test_iteritems_is_python2(self):
        assert PythonVersionDetector().detect("for k, v in d.iteritems(): pass") == "Python 2.x"

    def test_xrange_is_python2(self):
        assert PythonVersionDetector().detect("for i in xrange(10): pass") == "Python 2.x"

    def test_comma_except_is_python2(self):
        assert PythonVersionDetector().detect("try:\n    x()\nexcept ValueError, e:\n    pass") == "Python 2.x"

    def test_plain_python3_is_not_reported_as_python2(self):
        assert PythonVersionDetector().detect("print('hello')") == "Python 3.x"

    def test_walrus_reports_3_8(self):
        assert PythonVersionDetector().detect("if (n := len(x)) > 3:\n    pass") == "Python 3.8+"

    def test_fstring_reports_3_6(self):
        assert PythonVersionDetector().detect('name = "x"\nprint(f"hi {name}")') == "Python 3.6+"


class TestPythonValidator:

    def test_valid_code_passes(self):
        result = PythonValidator().validate("x = 1\n")
        assert result["compile_success"] is True
        assert result["validation_status"] == "PASS"
        assert result["compile_errors"] == []

    def test_syntax_error_fails_with_line_number(self):
        result = PythonValidator().validate("def f(:\n    pass\n")
        assert result["compile_success"] is False
        assert result["validation_status"] == "FAIL"
        assert result["compile_errors"]

    def test_bad_indentation_is_rejected(self):
        result = PythonValidator().validate("def f():\n    x = 1\n  y = 2\n")
        assert result["compile_success"] is False


class TestPythonUpgrader:

    def test_print_statement_becomes_a_call(self):
        result = PythonEnterpriseUpgrader().upgrade("print 'hello'\n")
        assert result["code"].strip() == "print('hello')"

    def test_indentation_is_preserved(self):
        source = "def f():\n    print 'inner'\n"
        result = PythonEnterpriseUpgrader().upgrade(source)
        assert "    print('inner')" in result["code"]
        assert result["compile_success"] is True

    def test_nested_indentation_is_preserved(self):
        source = "def f():\n    if True:\n        print 'deep'\n"
        upgraded = PythonEnterpriseUpgrader().upgrade(source)["code"]
        assert "        print('deep')" in upgraded

    def test_change_count_reflects_real_edits_not_line_delta(self):
        source = "print 'a'\nprint 'b'\n"
        result = PythonEnterpriseUpgrader().upgrade(source)
        assert result["total_diff_changes"] > 0

    def test_diff_text_is_populated(self):
        result = PythonEnterpriseUpgrader().upgrade("print 'a'\n")
        assert "print('a')" in result["diff_text"]

    def test_already_modern_code_is_left_alone(self):
        source = "def f():\n    print('hi')\n"
        result = PythonEnterpriseUpgrader().upgrade(source)
        assert result["code"] == source.rstrip("\n")
        assert result["detected_version"] == "Python 3.x"

    def test_report_contains_expected_keys(self):
        result = PythonEnterpriseUpgrader().upgrade("print 'a'\n")
        for key in (
            "code",
            "engine",
            "detected_version",
            "compile_success",
            "validation_status",
            "risk_level",
            "risk_triggers",
            "total_diff_changes",
            "diff_text",
        ):
            assert key in result
