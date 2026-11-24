"""Behaviour-preservation tests for cross-language translation.

Each test pins down a bug that once produced code which compiled and ran but
printed something different from the source program. Where a toolchain is
available the translation is executed and its output compared with what the
source prints; the generated-code assertions document the intended shape.
"""

import shutil

import pytest

from cross_language_system.core.dispatcher import CrossLanguageEngine
from cross_language_system.core.test_executor import ProgramRunner
from cross_language_system.core.type_annotator import TypeAnnotator

needs_javac = pytest.mark.skipif(not shutil.which("javac"), reason="javac not installed")
needs_gcc = pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")
needs_gpp = pytest.mark.skipif(not shutil.which("g++"), reason="g++ not installed")

TOOLCHAIN = {"java": [needs_javac], "c": [needs_gcc], "c++": [needs_gpp], "python": []}

ENGINE = CrossLanguageEngine()


def generate(code, source, target):
    """parse -> annotate -> generate, as the engine does, without compiling."""
    ir = ENGINE._get_parser(source, target).parse(code)
    TypeAnnotator(source).annotate(ir)
    return ENGINE._get_generator(source, target).generate(ir)


def run(language, code, stdin=""):
    with ProgramRunner(language, code) as runner:
        out, err = runner.run(stdin)
    assert err is None, f"{language} program failed: {err}\n{code}"
    return out.strip().replace("\r\n", "\n")


def behaves_the_same(code, source, target, *inputs):
    translated = generate(code, source, target)
    for stdin in inputs or ("",):
        assert run(target, translated, stdin) == run(source, code, stdin), translated


def directions(source, targets):
    return [pytest.param(t, marks=TOOLCHAIN[t]) for t in targets if t != source]


# ---------------------------------------------------------------------------
# Python sources
# ---------------------------------------------------------------------------

FIBONACCI = """n = int(input())
a, b = 0, 1
for _ in range(n):
    print(a)
    a, b = b, a + b
"""

SWAP = """data = [5, 3, 8, 1]
for i in range(len(data)):
    for j in range(len(data) - 1 - i):
        if data[j] > data[j + 1]:
            data[j], data[j + 1] = data[j + 1], data[j]
for x in data:
    print(x)
"""

FLOOR = """a = int(input())
b = int(input())
print(a // b)
print(a % b)
n = 1234
total = 0
while n > 0:
    total += n % 10
    n //= 10
print(total)
"""

GROUPING = """a = int(input())
b = int(input())
print((a + b) * 2)
print(a - (b - 1))
print(a & 1 == 0)
"""

PRINTING = """for i in range(4):
    print(i, end=" ")
print()
print("total:", 4 * 2)
print(2.5 * 2)
print(7 / 2)
print("a", "b", sep="-")
print(3 > 2)
"""


class TestPythonSource:

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_tuple_assignment_evaluates_right_side_first(self, target):
        behaves_the_same(FIBONACCI, "python", target, "6")

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_tuple_swap_of_list_elements(self, target):
        behaves_the_same(SWAP, "python", target)

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_floor_division_and_modulo(self, target):
        behaves_the_same(FLOOR, "python", target, "-7\n2", "7\n-2")

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_parentheses_survive(self, target):
        behaves_the_same(GROUPING, "python", target, "5\n3")

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_print_keeps_sep_end_and_value_spelling(self, target):
        behaves_the_same(PRINTING, "python", target)

    def test_augmented_floor_division_is_not_addition(self):
        java = generate(FLOOR, "python", "java")
        assert "Math.floorDiv(n, 10)" in java
        assert "+= 10" not in java

    def test_grouping_is_in_the_code(self):
        assert "(a + b) * 2" in generate(GROUPING, "python", "java")
        assert "(a + b) * 2" in generate(GROUPING, "python", "c")
        # Python ranks & above ==, Java below it.
        assert "(a & 1) == 0" in generate(GROUPING, "python", "java")

    def test_string_equality_uses_equals_in_java(self):
        java = generate('s = input()\nif s == "yes":\n    print(1)\n', "python", "java")
        assert "Objects.equals(s, \"yes\")" in java


# ---------------------------------------------------------------------------
# Java sources
# ---------------------------------------------------------------------------

JAVA_ARITHMETIC = """import java.util.Scanner;
public class Main {
    static int digitSum(int n) {
        int sum = 0;
        while (n > 0) {
            sum += n % 10;
            n = n / 10;
        }
        return sum;
    }
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        int steps = 0;
        int m = 6;
        while (m != 1) {
            if (m % 2 == 0) { m = m / 2; } else { m = 3 * m + 1; }
            steps++;
        }
        System.out.println(digitSum(n));
        System.out.println(steps);
        System.out.println(-7 / 2);
        System.out.println(-7 % 2);
        double half = n / 2;
        System.out.println(half);
    }
}
"""

JAVA_CONTROL = """public class Main {
    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1};
        for (int i = 0; i < arr.length; i++) {
            for (int j = 0; j < arr.length - 1 - i; j++) {
                if (arr[j] > arr[j + 1]) {
                    int t = arr[j];
                    arr[j] = arr[j + 1];
                    arr[j + 1] = t;
                }
            }
        }
        for (int i = 0; i < arr.length; i++) {
            System.out.print(arr[i] + " ");
        }
        System.out.println();
        int total = 0;
        for (int i = 10; i > 0; i -= 3) {
            total += i;
        }
        int n = 0;
        do {
            n++;
        } while (n < 5);
        switch (n) {
            case 1: System.out.println("one"); break;
            case 5: System.out.println("five"); break;
            default: System.out.println("other");
        }
        boolean flag = total % 2 == 1;
        String word = flag ? "odd" : "even";
        System.out.println(total + " " + word + " " + flag + " " + !(flag && n > 3));
        char c = 'x';
        System.out.println(c);
        long big = 10000000000L;
        System.out.println(big + 1);
    }
}
"""


class TestJavaSource:

    @pytest.mark.parametrize("target", directions("java", ["python", "c", "c++"]))
    def test_integer_arithmetic_and_increments(self, target):
        behaves_the_same(JAVA_ARITHMETIC, "java", target, "7", "1234")

    @pytest.mark.parametrize("target", directions("java", ["python", "c", "c++"]))
    def test_arrays_loops_switch_and_printing(self, target):
        behaves_the_same(JAVA_CONTROL, "java", target)

    def test_increment_statement_is_kept(self):
        assert "steps += 1" in generate(JAVA_ARITHMETIC, "java", "python")

    def test_counting_loop_keeps_its_step(self):
        assert "range(10, 0, -3)" in generate(JAVA_CONTROL, "java", "python")


# ---------------------------------------------------------------------------
# C and C++ sources
# ---------------------------------------------------------------------------

C_PROGRAM = """#include <stdio.h>
#define LIMIT 3
long power(int b, int e) {
    if (e == 0) return 1;
    return b * power(b, e - 1);
}
int is_prime(int n) {
    int i;
    if (n < 2) return 0;
    for (i = 2; i * i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}
int main(void) {
    int n, steps = 0, rev = 0, k;
    scanf("%d", &n);
    printf("%s\\n", is_prime(n) ? "prime" : "not prime");
    k = n;
    while (k > 0) {
        rev = rev * 10 + k % 10;
        k /= 10;
    }
    while (n != 1 && n > 0) {
        if (n % 2 == 0) n = n / 2; else n = 3 * n + 1;
        steps++;
    }
    printf("%d %d\\n", rev, steps);
    printf("%ld\\n", power(2, 10));
    printf("%.2f|%5d|%-4s|%x\\n", 0.0 * 9.0 / 5.0 + 32.0, LIMIT, "ab", 255);
    printf("100%%\\n");
    printf("%d\\n%d\\n", (12 & 10) | 1, 12 >> 2);
    return 0;
}
"""

CPP_PROGRAM = """#include <iostream>
using namespace std;
long long power(long long b, int e) {
    if (e == 0) return 1;
    return b * power(b, e - 1);
}
class Account {
private:
    int balance;
public:
    Account(int start) : balance(start) {}
    void deposit(int amount) { balance += amount; }
    int get() const { return balance; }
};
int main() {
    long long b;
    int e;
    cin >> b >> e;
    cout << power(b, e) << endl;
    int year = 1900;
    bool leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    cout << (leap ? "leap" : "not leap") << endl;
    Account account(100);
    account.deposit(50);
    cout << "balance " << account.get() << endl;
    return 0;
}
"""


class TestCFamilySource:

    @pytest.mark.parametrize("target", directions("c", ["python", "java", "c++"]))
    def test_c_semantics_survive(self, target):
        behaves_the_same(C_PROGRAM, "c", target, "2", "9", "123")

    @pytest.mark.parametrize("target", directions("c++", ["python", "java"]))
    def test_cpp_long_long_ternary_and_classes(self, target):
        behaves_the_same(CPP_PROGRAM, "c++", target, "2\n40")

    def test_loop_with_computed_condition_is_not_a_range(self):
        python = generate(C_PROGRAM, "c", "python")
        assert "while i * i <= n:" in python
        assert "_tdiv" in python  # C's / truncates

    def test_cpp_long_long_is_not_dropped(self):
        python = generate(CPP_PROGRAM, "c++", "python")
        assert "def power(b, e):" in python


# ---------------------------------------------------------------------------
# Input, objects and strings
# ---------------------------------------------------------------------------

PY_MIXED_INPUT = """a = int(input())
op = input()
b = int(input())
if op == "+":
    print(a + b)
else:
    print("error")
name, age = input().split()
city = input()
print(name, int(age) + 1, city)
"""

PY_OBJECTS = """class Account:
    def __init__(self, balance):
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount

    def withdraw(self, amount):
        if amount > self.balance:
            return False
        self.balance -= amount
        return True


account = Account(int(input()))
account.deposit(int(input()))
print(account.balance)
if account.withdraw(int(input())):
    print(account.balance)
else:
    print("insufficient funds")
"""

JAVA_OBJECTS = """import java.util.*;
public class Bank {
    static class Account {
        private int balance;
        Account(int balance) { this.balance = balance; }
        void deposit(int amount) { balance += amount; }
        boolean withdraw(int amount) {
            if (amount > balance) return false;
            balance -= amount;
            return true;
        }
        int get() { return balance; }
    }
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        Account account = new Account(sc.nextInt());
        account.deposit(sc.nextInt());
        System.out.println(account.get());
        System.out.println(account.withdraw(sc.nextInt()) ? account.get() : -1);
        String word = sc.next().toLowerCase();
        List<Integer> values = new ArrayList<>();
        for (int i = 0; i < word.length(); i++) {
            if ("aeiou".indexOf(word.charAt(i)) >= 0) values.add(i);
        }
        System.out.println(values.size() + " " + (values.isEmpty() ? -1 : Collections.max(values)));
    }
}
"""

C_STRUCTS_AND_STRINGS = """#include <stdio.h>
#include <ctype.h>
struct Account { int balance; };
void deposit(struct Account *account, int amount) { account->balance += amount; }
int main(void) {
    struct Account account;
    char word[100];
    char op;
    int i, vowels = 0;
    scanf("%d", &account.balance);
    deposit(&account, 50);
    printf("%d\\n", account.balance);
    scanf("%99s", word);
    for (i = 0; word[i] != '\\0'; i++) {
        char ch = tolower(word[i]);
        if (ch == 'a' || ch == 'e' || ch == 'i' || ch == 'o' || ch == 'u') vowels++;
    }
    scanf(" %c", &op);
    printf("%d %c\\n", vowels, op);
    return 0;
}
"""


class TestInputObjectsAndStrings:

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_python_reads_whole_lines(self, target):
        behaves_the_same(PY_MIXED_INPUT, "python", target, "6\n+\n3\nAsha 20\nPune")

    @pytest.mark.parametrize("target", directions("python", ["java", "c", "c++"]))
    def test_python_objects(self, target):
        behaves_the_same(PY_OBJECTS, "python", target, "100\n50\n30", "10\n5\n100")

    @pytest.mark.parametrize("target", directions("java", ["python", "c++"]))
    def test_java_fields_and_string_methods(self, target):
        behaves_the_same(JAVA_OBJECTS, "java", target, "100\n50\n30\nProgramming", "1\n1\n9\nxyz")

    @pytest.mark.parametrize("target", directions("c", ["python", "java"]))
    def test_c_struct_pointers_and_strings(self, target):
        behaves_the_same(C_STRUCTS_AND_STRINGS, "c", target, "100\nEducation\n+")

    def test_unqualified_field_becomes_self_access(self):
        python = generate(JAVA_OBJECTS, "java", "python")
        assert "self.balance += amount" in python


# ---------------------------------------------------------------------------
# Library idioms with one defined meaning (core/library.py)
# ---------------------------------------------------------------------------

PY_LIBRARY = """text = input()
nums = list(map(int, input().split()))
upper = 0
for ch in text:
    if ch.isupper():
        upper += 1
print(upper, text.isdigit())
print(text[::-1], text[1:3], text[-2:])
print(round(2.5), round(3.5), round(84.666, 1))
print("-".join(text.split()))
for i, x in enumerate(nums):
    print(i, x)
print(sorted(nums), 2 ** 40)
"""

JAVA_LIBRARY = """import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.nextLine();
        StringBuilder sb = new StringBuilder();
        for (int i = s.length() - 1; i >= 0; i--) {
            sb.append(s.charAt(i));
        }
        System.out.println(sb.toString() + " " + new StringBuilder(s).reverse().toString().equals(sb.toString()));
        System.out.println(Math.round(2.5) + " " + Math.round(-2.5) + " " + Math.floorMod(-7, 3));
        List<Integer> xs = new ArrayList<>(Arrays.asList(3, 1, 2));
        Collections.reverse(xs);
        System.out.println(xs);
        String[] words = s.split(" ");
        System.out.println(words.length + " " + s.isEmpty());
    }
}
"""

CPP_LIBRARY = """#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <algorithm>
using namespace std;

int main() {
    string s;
    getline(cin, s);
    string r(s.rbegin(), s.rend());
    cout << r << " " << (s == r) << endl;
    cout << to_string(7) + "!" << " " << to_string(2.5) << endl;
    cout << s.substr(1, 2) << " " << s.back() << " " << s.empty() << endl;
    vector<int> v = {3, 1, 3};
    reverse(v.begin(), v.end());
    cout << v[0] << " " << count(v.begin(), v.end(), 3) << endl;
    cout << fixed << setprecision(2) << 84.666 << " " << setw(5) << 42 << "|" << endl;
    return 0;
}
"""

C_STRUCT_ARRAYS = """#include <stdio.h>

struct Student {
    char name[32];
    int marks[3];
};

int main(void) {
    struct Student s;
    int i, total = 0;
    scanf("%31s", s.name);
    for (i = 0; i < 3; i++) {
        scanf("%d", &s.marks[i]);
        total += s.marks[i];
    }
    printf("%s %d\\n", s.name, total);
    return 0;
}
"""


class TestLibraryIdioms:

    @pytest.mark.parametrize("target", directions("python", ["java", "c++"]))
    def test_python_library(self, target):
        behaves_the_same(PY_LIBRARY, "python", target, "Hello World 42\n3 1 2\n")

    @pytest.mark.parametrize("target", directions("java", ["python", "c++"]))
    def test_java_library(self, target):
        behaves_the_same(JAVA_LIBRARY, "java", target, "ab cd\n", "\n")

    @pytest.mark.parametrize("target", directions("c++", ["python", "java"]))
    def test_cpp_library(self, target):
        behaves_the_same(CPP_LIBRARY, "c++", target, "level\n")

    @pytest.mark.parametrize("target", directions("c", ["python", "java"]))
    def test_c_struct_with_array_members(self, target):
        behaves_the_same(C_STRUCT_ARRAYS, "c", target, "Asha 91 85 78\n")


# ---------------------------------------------------------------------------
# Refusals: what cannot be translated faithfully must say so
# ---------------------------------------------------------------------------

class TestFailsLoudly:

    @pytest.mark.parametrize("code,source,target", [
        ("xs = []\nxs.append(1)\nprint(xs[0])\n", "python", "c"),
        ("s = 'hello'\nprint(s[::2])\n", "python", "java"),
        ("d = {'b': 1, 'a': 2}\nfor k in d:\n    print(k)\n", "python", "c++"),
        ("print(sorted([3, 1], reverse=True))\n", "python", "java"),
        ("import sys\nprint('x', file=sys.stderr)\n", "python", "java"),
        ("for i in range(3):\n    pass\nelse:\n    print('done')\n", "python", "java"),
        ("int main() { int i = 0, j; j = i++; return 0; }", "c", "python"),
        ("int main() { goto end; end: return 0; }", "c", "python"),
        ("int main() { int x = 1; switch (x) { case 1: x++; case 2: x++; break; } return 0; }",
         "c", "python"),
        ("public class A { public static void main(String[] a) {"
         " Runnable r = () -> {}; } }", "java", "python"),
        ("void swap(int &a, int &b) { int t = a; a = b; b = t; }\nint main() { return 0; }",
         "c++", "python"),
    ])
    def test_refused_with_an_explanation(self, code, source, target):
        result = ENGINE.convert(code, source, target)
        assert "error" in result, result.get("code")
        assert result["error"].startswith("Cannot translate this program faithfully")
