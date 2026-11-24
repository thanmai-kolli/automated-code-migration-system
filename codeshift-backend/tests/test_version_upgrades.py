"""Version upgrades for Java, C and C++: every rewrite is validated by the real compiler.

The cases mirror the regressions found by the evaluation: each one used to compile or
behave differently after the old regex rules, and must now be preserved.
"""

import shutil

import pytest

from cross_language_system.core.test_executor import ENABLE_FLAG
from version_upgrade_system.core.gated import GatedUpgrader, Rule
from version_upgrade_system.core.textscan import mask
from version_upgrade_system.core.upgrade_engine import UpgradeEngine
from version_upgrade_system.languages.python.enterprise_engine.version_detector import PythonVersionDetector

needs_javac = pytest.mark.skipif(not shutil.which("javac"), reason="javac not installed")
needs_gcc = pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")
needs_gpp = pytest.mark.skipif(not shutil.which("g++"), reason="g++ not installed")


def upgrade(code, language, cases=None):
    return UpgradeEngine().upgrade(code, language, cases)


class TestMasking:

    def test_strings_and_comments_are_blanked_with_the_same_length(self):
        code = 'int x = 1; // NULL here\nchar *s = "NULL";\n'
        masked = mask(code, "cpp")
        assert len(masked) == len(code)
        assert "NULL" not in masked
        assert "int x = 1;" in masked


@needs_javac
class TestJavaUpgrade:

    VECTOR = (
        "import java.util.*;\n"
        "public class VectorSum {\n"
        "    public static void main(String[] args) {\n"
        "        Vector values = new Vector();\n"
        "        values.addElement(new Integer(4));\n"
        "        Enumeration e = values.elements();\n"
        "        System.out.println(values.size() + \" \" + e.hasMoreElements());\n"
        "    }\n"
        "}\n"
    )

    def test_local_vector_becomes_a_list_with_mapped_methods(self):
        result = upgrade(self.VECTOR, "java")
        code = result["code"]
        assert "List values = new ArrayList()" in code
        assert "values.add(Integer.valueOf(4))" in code
        assert "Collections.enumeration(values)" in code
        assert "public class VectorSum" in code  # the class name is not rewritten
        assert result["compile_success"] is True

    def test_validator_really_compiles(self):
        result = upgrade("public class Broken { void f() { int x = ; } }", "java")
        assert result["compile_success"] is False
        assert result["risk_level"] == "HIGH"

    def test_anonymous_runnable_becomes_a_lambda(self):
        code = (
            "public class T {\n"
            "    public static void main(String[] a) throws Exception {\n"
            "        Thread t = new Thread(new Runnable() {\n"
            "            public void run() { System.out.println(1); }\n"
            "        });\n"
            "        t.start(); t.join();\n"
            "    }\n"
            "}\n"
        )
        upgraded = upgrade(code, "java")["code"]
        assert "() -> {" in upgraded
        assert "new Runnable" not in upgraded

    def test_anonymous_class_using_this_is_kept(self):
        code = (
            "public class T {\n"
            "    public static void main(String[] a) {\n"
            "        Runnable r = new Runnable() {\n"
            "            public void run() { System.out.println(this.hashCode() > -1); }\n"
            "        };\n"
            "        r.run();\n"
            "    }\n"
            "}\n"
        )
        assert "new Runnable()" in upgrade(code, "java")["code"]

    def test_string_buffer_is_kept_when_threads_are_used(self):
        code = (
            "public class T {\n"
            "    public static void main(String[] a) {\n"
            "        StringBuffer b = new StringBuffer();\n"
            "        new Thread(() -> b.append(1)).start();\n"
            "    }\n"
            "}\n"
        )
        assert "StringBuffer" in upgrade(code, "java")["code"]


@needs_gcc
class TestCUpgrade:

    def test_gets_keeps_its_newline_behaviour(self):
        code = ("#include <stdio.h>\nvoid main()\n{\n    char name[50];\n"
                "    gets(name);\n    printf(\"Hello, %s!\\n\", name);\n}\n")
        upgraded = upgrade(code, "c")["code"]
        assert "fgets(name, sizeof name, stdin)" in upgraded
        assert "strcspn(name" in upgraded
        assert "int main(void)" in upgraded

    def test_strcpy_into_a_pointer_parameter_is_not_truncated(self):
        code = ("#include <string.h>\nvoid copy(char *dest, const char *src)\n{\n"
                "    strcpy(dest, src);\n}\nint main(void) { return 0; }\n")
        result = upgrade(code, "c")
        assert "strcpy(dest, src);" in result["code"]
        assert any("strcpy kept" in t for t in result["risk_triggers"])

    def test_strcpy_into_an_array_becomes_bounded(self):
        code = ("#include <stdio.h>\n#include <string.h>\nint main(void)\n{\n"
                "    char buf[8];\n    strcpy(buf, \"hi\");\n    puts(buf);\n    return 0;\n}\n")
        assert 'snprintf(buf, sizeof buf, "%s", "hi")' in upgrade(code, "c")["code"]

    def test_implicit_int_and_declarations_are_fixed(self):
        code = ("#include <stdio.h>\nmain()\n{\n    printf(\"%d\\n\", add(2, 3));\n    return 0;\n}\n"
                "int add(int a, int b)\n{\n    return a + b;\n}\n")
        result = upgrade(code, "c")
        assert result["compile_success"] is True
        assert "int add(int a, int b);" in result["code"]

    def test_knr_definition_becomes_a_prototype(self):
        code = ("#include <stdio.h>\nint twice(n)\nint n;\n{\n    return 2 * n;\n}\n"
                "int main(void) { printf(\"%d\\n\", twice(4)); return 0; }\n")
        assert "int twice(int n)" in upgrade(code, "c")["code"]


class TestGating:
    """The gate itself: a rule that changes behaviour must be rejected."""

    class OffByOne(GatedUpgrader):
        language = "python"
        engine = "test"
        detector = PythonVersionDetector()

        def rules(self, code):
            return [Rule("harmless rename", lambda c: c.replace("total", "result")),
                    Rule("changes output", lambda c: c.replace("+ 1", "+ 2"))]

    SOURCE = "total = int(input()) + 1\nprint(total)\n"

    def test_rule_that_changes_output_is_rejected(self, monkeypatch):
        monkeypatch.setenv(ENABLE_FLAG, "1")
        result = self.OffByOne().upgrade(self.SOURCE, "4\n===\n5")
        assert result["applied_rules"] == ["harmless rename"]
        assert result["rejected_rules"] == ["changes output (changed program output)"]
        assert "+ 1" in result["code"]
        assert result["test_results"]["passed"] == 1

    def test_without_test_cases_only_compilation_gates(self):
        result = self.OffByOne().upgrade(self.SOURCE)
        assert result["applied_rules"] == ["harmless rename", "changes output"]


@needs_gpp
class TestCppUpgrade:

    def test_cast_wraps_the_whole_operand(self):
        code = ("#include <vector>\nint n(const std::vector<int>& v)\n{\n"
                "    return (int) v.size();\n}\nint main() { return n({}); }\n")
        upgraded = upgrade(code, "cpp")["code"]
        assert "static_cast<int>(v.size())" in upgraded

    def test_index_loop_used_for_arithmetic_is_kept(self):
        code = ("#include <vector>\n#include <cstdio>\nint main()\n{\n    std::vector<int> v(3);\n"
                "    for (size_t i = 0; i < v.size(); i++) {\n        v[i] = i * 2;\n    }\n"
                "    printf(\"%d\\n\", v[2]);\n    return 0;\n}\n")
        assert "for (size_t i = 0" in upgrade(code, "cpp")["code"]

    def test_index_loop_used_only_for_access_becomes_range_for(self):
        code = ("#include <vector>\n#include <cstdio>\nint main()\n{\n    std::vector<int> v(3, 1);\n"
                "    int t = 0;\n    for (size_t i = 0; i < v.size(); i++) {\n        t += v[i];\n    }\n"
                "    printf(\"%d\\n\", t);\n    return 0;\n}\n")
        upgraded = upgrade(code, "cpp")["code"]
        assert "for (auto& element : v)" in upgraded
        assert "t += element;" in upgraded

    def test_pointer_passed_to_a_function_keeps_raw_ownership(self):
        code = ("#include <cstdio>\nstruct C { int v; C(int x) : v(x) {} };\n"
                "void show(C* c) { printf(\"%d\\n\", c->v); }\n"
                "int main()\n{\n    C* c = new C(5);\n    show(c);\n    delete c;\n    return 0;\n}\n")
        result = upgrade(code, "cpp")
        assert "C* c = new C(5);" in result["code"]
        assert result["compile_success"] is True

    def test_local_pointer_becomes_unique_ptr(self):
        code = ("#include <cstdio>\nstruct C { int v; C(int x) : v(x) {} };\n"
                "int main()\n{\n    C* c = new C(5);\n    printf(\"%d\\n\", c->v);\n    delete c;\n    return 0;\n}\n")
        result = upgrade(code, "cpp")
        assert "auto c = std::make_unique<C>(5);" in result["code"]
        assert "#include <memory>" in result["code"]
        assert result["compile_success"] is True

    def test_infinite_for_loop_is_not_damaged(self):
        code = ("int main()\n{\n    int i = 0;\n    for (;;) { if (++i > 3) break; }\n"
                "    return i == 4 ? 0 : 1;\n}\n")
        assert "for (;;)" in upgrade(code, "cpp")["code"]

    def test_features_removed_in_cpp17(self):
        code = (
            "#include <iostream>\n#include <vector>\n#include <algorithm>\n#include <functional>\n"
            "using namespace std;\n"
            "struct IsBig : public std::unary_function<int, bool> {\n"
            "    bool operator()(int x) const { return x > 10; }\n};\n"
            "int check(int v) throw(std::bad_alloc) {\n"
            "    if (v < 0) throw (std::bad_alloc());\n    return v * 2;\n}\n"
            "int main() {\n    std::vector<int> v;\n    v.push_back(5); v.push_back(20); v.push_back(30);\n"
            "    int big = std::count_if(v.begin(), v.end(), std::bind2nd(std::greater<int>(), 10));\n"
            "    int small = std::count_if(v.begin(), v.end(), std::not1(std::bind1st(std::less<int>(), 10)));\n"
            "    cout << big << ' ' << small << ' ' << std::count_if(v.begin(), v.end(), IsBig()) << ' ' << check(4);\n"
            "    return 0;\n}\n"
        )
        result = upgrade(code, "cpp")
        upgraded = result["code"]
        assert result["compile_success"] is True and result["rejected_rules"] == []
        assert "std::bind(std::greater<int>(), std::placeholders::_1, 10)" in upgraded
        assert "std::not_fn(std::bind(std::less<int>(), 10, std::placeholders::_1))" in upgraded
        assert "struct IsBig {" in upgraded
        assert "int check(int v) {" in upgraded
        assert "throw (std::bad_alloc());" in upgraded  # a throw statement, not a specification

    def test_pre_standard_headers_and_void_main(self):
        code = "#include <iostream.h>\nvoid main()\n{\n    cout << 42 << endl;\n}\n"
        result = upgrade(code, "cpp")
        assert result["compile_success"] is True
        assert "#include <iostream>\nusing namespace std;" in result["code"]
        assert "int main()" in result["code"]


@needs_javac
class TestModernJava:

    LEGACY = (
        "import java.util.*;\nimport java.io.*;\n\n"
        "public class Legacy {\n"
        "    static String describe(Object o) {\n"
        "        if (o instanceof String) {\n"
        "            String s = (String) o;\n"
        "            return \"text:\" + s.length();\n"
        "        }\n"
        "        return \"other\";\n"
        "    }\n\n"
        "    public static void main(String[] args) throws IOException {\n"
        "        List<String> names = new ArrayList<String>();\n"
        "        names.add(\"ada\");\n"
        "        List raw = new ArrayList();\n"
        "        raw.add(\"linus\");\n"
        "        Iterator it = names.iterator();\n"
        "        while (it.hasNext()) {\n"
        "            String name = (String) it.next();\n"
        "            System.out.println(name.length());\n"
        "        }\n"
        "        Iterator r = raw.iterator();\n"
        "        while (r.hasNext()) {\n"
        "            String name = (String) r.next();\n"
        "            System.out.println(name);\n"
        "        }\n"
        "        StringWriter sink = new StringWriter();\n"
        "        PrintWriter out = new PrintWriter(sink);\n"
        "        try {\n"
        "            out.print(describe(\"hey\"));\n"
        "        } finally {\n"
        "            out.close();\n"
        "        }\n"
        "        System.out.println(sink + \" \" + describe(3));\n"
        "    }\n"
        "}\n"
    )

    def test_java_7_to_16_idioms(self):
        result = upgrade(self.LEGACY, "java")
        code = result["code"]
        assert result["compile_success"] is True and result["rejected_rules"] == []
        assert "new ArrayList<>()" in code
        assert "if (o instanceof String s) {" in code and "(String) o" not in code
        assert "for (String name : names) {" in code
        assert "for (Object _element : raw) {" in code  # a raw list still needs its cast
        assert "try (PrintWriter out = new PrintWriter(sink)) {" in code and "finally" not in code

    def test_finally_with_more_than_close_is_kept(self):
        code = self.LEGACY.replace("out.close();", "out.close();\n            System.out.println(1);")
        assert "finally" in upgrade(code, "java")["code"]


@needs_gcc
class TestBsdStrings:

    def test_bzero_bcopy_and_index(self):
        code = ("#include <stdio.h>\n#include <strings.h>\nint main(void) {\n"
                "    char buf[16]; char out[16];\n    bzero(buf, sizeof buf);\n"
                "    buf[0] = 'h'; buf[1] = 'i';\n    bcopy(buf, out, sizeof buf);\n"
                "    printf(\"%s %s\\n\", out, index(out, 'i'));\n    return 0;\n}\n")
        upgraded = upgrade(code, "c")["code"]
        assert "memset(buf, 0, sizeof buf)" in upgraded
        assert "memmove(out, buf, sizeof buf)" in upgraded
        assert "strchr(out, 'i')" in upgraded
        assert "#include <string.h>" in upgraded

    def test_variable_named_index_is_not_touched(self):
        code = ("#include <stdio.h>\nint index(int x) { return x; }\nint main(void) {\n"
                "    int index = 3;\n    printf(\"%d\\n\", index);\n    return 0;\n}\n")
        assert "strchr" not in upgrade(code, "c")["code"]


@needs_gcc
class TestCharacterizationTests:
    """Without user tests the original's own outputs on generated inputs gate every rule."""

    class Harmful(GatedUpgrader):
        language = "c"
        engine = "test"
        detector = PythonVersionDetector()

        def rules(self, code):
            return [Rule("changes output", lambda c: c.replace("n * 2", "n * 3"))]

    SOURCE = ("#include <stdio.h>\nint main(void) {\n    int n;\n"
              "    if (scanf(\"%d\", &n) != 1) return 0;\n    printf(\"%d\\n\", n * 2);\n    return 0;\n}\n")

    def test_generated_tests_reject_a_rule_that_changes_output(self, monkeypatch):
        monkeypatch.setenv(ENABLE_FLAG, "1")
        result = self.Harmful().upgrade(self.SOURCE)
        assert result["rejected_rules"] == ["changes output (changed program output)"]
        assert result["test_results"]["generated"] is True
        assert result["test_results"]["passed"] == result["test_results"]["total"] > 1
        assert "generated characterization" in result["validation_basis"]

    def test_disabled_execution_falls_back_to_compilation(self, monkeypatch):
        monkeypatch.delenv(ENABLE_FLAG, raising=False)
        result = self.Harmful().upgrade(self.SOURCE)
        assert result["applied_rules"] == ["changes output"]
        assert result["validation_basis"] == "compilation only"
