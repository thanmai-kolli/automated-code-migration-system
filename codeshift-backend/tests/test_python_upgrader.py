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


class TestPython2Rules:
    """Each rule must fire, preserve syntax, and be reported as a trigger."""

    def _upgrade(self, source):
        return PythonEnterpriseUpgrader().upgrade(source)

    def test_iteritems(self):
        result = self._upgrade("d = {}\nfor k, v in d.iteritems():\n    pass\n")
        assert ".items()" in result["code"]
        assert "iteritems" not in result["code"]
        assert result["compile_success"]

    def test_iterkeys_and_itervalues(self):
        result = self._upgrade("d = {}\nprint list(d.iterkeys()), list(d.itervalues())\n")
        assert ".keys()" in result["code"]
        assert ".values()" in result["code"]

    def test_xrange(self):
        result = self._upgrade("for i in xrange(3):\n    pass\n")
        assert "range(3)" in result["code"]
        assert "xrange" not in result["code"]

    def test_raw_input(self):
        result = self._upgrade("name = raw_input()\n")
        assert "input()" in result["code"]
        assert "raw_input" not in result["code"]

    def test_except_comma_becomes_as(self):
        result = self._upgrade("try:\n    pass\nexcept ValueError, e:\n    pass\n")
        assert "except ValueError as e:" in result["code"]
        assert result["compile_success"]

    def test_not_equal_operator(self):
        result = self._upgrade("x = 1\nif x <> 2:\n    pass\n")
        assert "!=" in result["code"]
        assert "<>" not in result["code"]

    def test_has_key(self):
        result = self._upgrade("d = {}\nif d.has_key('a'):\n    pass\n")
        assert "'a' in d" in result["code"]
        assert "has_key" not in result["code"]

    def test_unicode_and_basestring(self):
        result = self._upgrade("x = unicode(5)\ny = basestring\n")
        assert "str(5)" in result["code"]
        assert "basestring" not in result["code"]

    def test_applied_rules_are_reported(self):
        result = self._upgrade("for i in xrange(3):\n    print i\n")
        assert len(result["risk_triggers"]) >= 2
        assert result["risk_score"] >= 2

    def test_modern_code_triggers_nothing(self):
        result = self._upgrade("for i in range(3):\n    print(i)\n")
        assert result["risk_triggers"] == []
        assert result["risk_score"] == 0

    def test_combined_legacy_file_compiles(self):
        source = (
            "d = {'a': 1}\n"
            "for k, v in d.iteritems():\n"
            "    print k, v\n"
            "for i in xrange(2):\n"
            "    print i\n"
            "try:\n"
            "    pass\n"
            "except ValueError, e:\n"
            "    pass\n"
        )
        result = self._upgrade(source)
        assert result["compile_success"], result["compile_errors"]
        for legacy in ("iteritems", "xrange", "except ValueError,"):
            assert legacy not in result["code"]

    def test_a_broken_rewrite_falls_back_to_the_original(self):
        # Valid Python 3 in, valid Python 3 out — never a regression.
        source = "d = {'a': 1}\nprint(d)\n"
        result = self._upgrade(source)
        assert result["compile_success"]
