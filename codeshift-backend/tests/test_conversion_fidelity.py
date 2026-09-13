"""Conversion fidelity tests.

These assert on the *content* of generated code, not just that a conversion
returned something, because the engine's historical failure mode was silently
dropping statements while still reporting success.
"""

import itertools

import pytest

from cross_language_system.core.dispatcher import CrossLanguageEngine
from cross_language_system.core.type_annotator import TypeAnnotator
from cross_language_system.parsers.python_parser import PythonParser
from cross_language_system.core.ir_nodes import (
    Assignment, AttributeAccess, Class, Field, Return, UnaryOp, Variable,
)

PY_CLASS = """class BankAccount:
    def __init__(self, owner, balance):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        if amount > 0:
            self.balance = self.balance + amount
        return self.balance

    def withdraw(self, amount):
        if amount > self.balance:
            return -1
        self.balance = self.balance - amount
        return self.balance
"""

PY_FUNCS = """def average(scores):
    total = 0
    for s in scores:
        total += s
    return total / len(scores)


def classify(n):
    if n > 90:
        return "high"
    elif n > 50:
        return "mid"
    else:
        return "low"
"""

JAVA_CLASS = """public class Inventory {
    private int count;
    private String label;

    public Inventory(String label, int count) {
        this.label = label;
        this.count = count;
    }

    public int addStock(int amount) {
        if (amount > 0) {
            this.count = this.count + amount;
        }
        return this.count;
    }
}
"""

C_CODE = """#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int main() {
    int total = add(2, 3);
    printf("%d\\n", total);
    return 0;
}
"""

CPP_CODE = """#include <iostream>
using namespace std;

int square(int n) {
    return n * n;
}

int main() {
    int value = square(5);
    cout << value << endl;
    return 0;
}
"""

SAMPLES = {"python": PY_FUNCS, "java": JAVA_CLASS, "c": C_CODE, "c++": CPP_CODE}


@pytest.fixture(scope="module")
def engine():
    return CrossLanguageEngine()


class TestPythonParserCoverage:
    """The parser used to drop whole statement kinds, emitting silent nulls."""

    def _parse(self, code):
        program = PythonParser().parse(code)
        return TypeAnnotator().annotate(program)

    def test_attribute_assignment_is_not_dropped(self):
        program = self._parse("class A:\n    def __init__(self):\n        self.x = 1\n")
        constructor = program.body[0].methods[0]
        assert any(isinstance(s, Assignment) for s in constructor.body)

    def test_attribute_read_is_not_null(self):
        program = self._parse("class A:\n    def get(self):\n        return self.x\n")
        returned = program.body[0].methods[0].body[0]
        assert isinstance(returned, Return)
        assert isinstance(returned.value, AttributeAccess)

    def test_negative_literal_survives(self):
        program = self._parse("def f():\n    return -1\n")
        assert isinstance(program.body[0].body[0].value, UnaryOp)

    def test_class_fields_are_collected(self):
        program = self._parse(PY_CLASS)
        names = {f.name for f in program.body[0].fields}
        assert names == {"owner", "balance"}
        assert all(isinstance(f, Field) for f in program.body[0].fields)

    def test_init_is_marked_as_constructor(self):
        program = self._parse(PY_CLASS)
        assert program.body[0].methods[0].is_constructor

    def test_augmented_assignment_is_parsed(self):
        program = self._parse("def f():\n    x = 0\n    x += 1\n")
        assert len(program.body[0].body) == 2

    def test_class_node_is_produced(self):
        program = self._parse(PY_CLASS)
        assert isinstance(program.body[0], Class)


class TestTypeInference:

    def _annotate(self, code):
        return TypeAnnotator().annotate(PythonParser().parse(code))

    def test_parameter_type_from_arithmetic(self):
        program = self._annotate("def f(n):\n    return n - 1\n")
        assert program.body[0].param_types["n"] == "int"

    def test_field_type_from_constructor(self):
        program = self._annotate(PY_CLASS)
        fields = {f.name: f.field_type for f in program.body[0].fields}
        assert fields["balance"] == "int"

    def test_local_list_type(self):
        program = self._annotate("def f():\n    xs = [1, 2, 3]\n    return xs\n")
        assert program.body[0].body[0].var_type == "List<Integer>"

    def test_return_type_is_string(self):
        program = self._annotate('def f():\n    return "hi"\n')
        assert program.body[0].return_type == "String"

    def test_void_when_no_return(self):
        program = self._annotate("def f(a):\n    print(a)\n")
        assert program.body[0].return_type == "void"

    def test_call_site_refines_parameter(self):
        program = self._annotate(
            "def f(xs):\n    return xs\n\ndef g():\n    f([1, 2])\n"
        )
        assert program.body[0].param_types["xs"] == "List<Integer>"


class TestPythonToJava:

    @pytest.fixture(scope="class")
    def java(self, engine):
        return engine.convert(PY_CLASS, "python", "java")

    def test_it_compiles(self, java):
        assert java["compile_success"], java["compile_errors"]

    def test_fields_are_declared(self, java):
        assert "private int balance;" in java["code"]

    def test_constructor_is_generated(self, java):
        assert "public BankAccount(" in java["code"]

    def test_methods_are_instance_methods(self, java):
        assert "public int deposit(" in java["code"]
        assert "public static int deposit(" not in java["code"]

    def test_field_assignment_is_preserved(self, java):
        assert "this.balance = this.balance + amount;" in java["code"]

    def test_negative_return_is_preserved(self, java):
        assert "return -1;" in java["code"]

    def test_no_statement_became_null(self, java):
        assert "> null" not in java["code"]
        assert "return null;" not in java["code"]

    def test_parameters_are_typed(self, java):
        assert "int amount" in java["code"]

    def test_accuracy_is_high(self, java):
        assert java["accuracy"] > 85

    def test_float_division_semantics(self, engine):
        result = engine.convert(PY_FUNCS, "python", "java")
        assert "(double) total / scores.size()" in result["code"]

    def test_elif_becomes_else_if(self, engine):
        result = engine.convert(PY_FUNCS, "python", "java")
        assert "} else if (" in result["code"]


class TestJavaToPython:

    @pytest.fixture(scope="class")
    def python(self, engine):
        return engine.convert(JAVA_CLASS, "java", "python")

    def test_it_compiles(self, python):
        assert python["compile_success"], python["compile_errors"]

    def test_constructor_becomes_init(self, python):
        assert "def __init__(self, label, count):" in python["code"]

    def test_this_becomes_self(self, python):
        assert "self.count = self.count + amount" in python["code"]

    def test_methods_take_self(self, python):
        assert "def addStock(self, amount):" in python["code"]


class TestCFamily:

    def test_c_to_cpp_uses_iostream(self, engine):
        result = engine.convert(C_CODE, "c", "c++")
        assert "iostream" in result["code"]
        assert result["compile_success"], result["compile_errors"]

    def test_cpp_to_c_drops_endl(self, engine):
        result = engine.convert(CPP_CODE, "c++", "c")
        assert "endl" not in result["code"]
        assert result["compile_success"], result["compile_errors"]

    def test_c_to_python_keeps_the_function(self, engine):
        result = engine.convert(C_CODE, "c", "python")
        assert "def add(a, b):" in result["code"]
        assert "return a + b" in result["code"]

    def test_c_to_java_keeps_the_function(self, engine):
        result = engine.convert(C_CODE, "c", "java")
        assert "int add(int a, int b)" in result["code"]
        assert result["compile_success"], result["compile_errors"]

    def test_python_to_c_emits_array_length(self, engine):
        result = engine.convert(PY_FUNCS, "python", "c")
        assert "scores_length" in result["code"]
        assert result["compile_success"], result["compile_errors"]

    def test_python_to_cpp_uses_vector(self, engine):
        result = engine.convert(PY_FUNCS, "python", "c++")
        assert "vector<int>" in result["code"]
        assert result["compile_success"], result["compile_errors"]


class TestEveryDirection:
    """Every ordered language pair must produce compiling, non-empty output."""

    @pytest.mark.parametrize(
        "source,target",
        [p for p in itertools.permutations(SAMPLES, 2)],
    )
    def test_pair(self, engine, source, target):
        result = engine.convert(SAMPLES[source], source, target)
        assert "error" not in result, result.get("error")
        assert result["code"].strip(), f"{source}->{target} produced nothing"
        assert result["compile_success"], (
            f"{source}->{target} failed to compile: {result['compile_errors']}"
        )
