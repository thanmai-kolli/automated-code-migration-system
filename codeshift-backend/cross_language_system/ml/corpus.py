"""Sample programs used to measure migration quality.

Every program reads from stdin and prints to stdout so a migration can be judged
behaviourally: run the original and the migration on the same inputs and compare.
Programs are deliberately varied — arithmetic, loops, strings, collections,
classes — so the measured dataset covers easy and hard constructs alike.
"""

CORPUS = {

    # ------------------------------------------------------------------
    "python": [
        {
            "name": "sum_two",
            "code": "a, b = input().split()\nprint(int(a) + int(b))\n",
            "inputs": ["2 3", "10 20", "-4 9"],
        },
        {
            "name": "max_of_three",
            "code": (
                "a, b, c = input().split()\n"
                "x = int(a)\n"
                "y = int(b)\n"
                "z = int(c)\n"
                "best = x\n"
                "if y > best:\n"
                "    best = y\n"
                "if z > best:\n"
                "    best = z\n"
                "print(best)\n"
            ),
            "inputs": ["1 2 3", "9 4 2", "5 5 5"],
        },
        {
            "name": "factorial",
            "code": (
                "n = int(input())\n"
                "total = 1\n"
                "for i in range(1, n + 1):\n"
                "    total = total * i\n"
                "print(total)\n"
            ),
            "inputs": ["5", "1", "8"],
        },
        {
            "name": "classify_grade",
            "code": (
                "score = int(input())\n"
                "if score > 89:\n"
                "    print(\"A\")\n"
                "elif score > 79:\n"
                "    print(\"B\")\n"
                "elif score > 69:\n"
                "    print(\"C\")\n"
                "else:\n"
                "    print(\"F\")\n"
            ),
            "inputs": ["95", "82", "71", "40"],
        },
        {
            "name": "count_down",
            "code": (
                "n = int(input())\n"
                "while n > 0:\n"
                "    print(n)\n"
                "    n = n - 1\n"
                "print(0)\n"
            ),
            "inputs": ["4", "1", "7"],
        },
        {
            "name": "sum_list",
            "code": (
                "n = int(input())\n"
                "total = 0\n"
                "for i in range(0, n):\n"
                "    total += i\n"
                "print(total)\n"
            ),
            "inputs": ["5", "10", "1"],
        },
        {
            "name": "gcd",
            "code": (
                "a, b = input().split()\n"
                "x = int(a)\n"
                "y = int(b)\n"
                "while y != 0:\n"
                "    t = y\n"
                "    y = x % y\n"
                "    x = t\n"
                "print(x)\n"
            ),
            "inputs": ["12 18", "7 13", "100 75"],
        },
        {
            "name": "average_function",
            "code": (
                "def average(values):\n"
                "    total = 0\n"
                "    for v in values:\n"
                "        total += v\n"
                "    return total / len(values)\n"
                "\n"
                "n = int(input())\n"
                "nums = []\n"
                "for i in range(0, n):\n"
                "    nums.append(i * 2)\n"
                "print(average(nums))\n"
            ),
            "inputs": ["4", "2", "6"],
        },
        {
            "name": "power_function",
            "code": (
                "def power(base, exponent):\n"
                "    result = 1\n"
                "    for i in range(0, exponent):\n"
                "        result = result * base\n"
                "    return result\n"
                "\n"
                "a, b = input().split()\n"
                "print(power(int(a), int(b)))\n"
            ),
            "inputs": ["2 5", "3 3", "7 0"],
        },
        {
            "name": "counter_class",
            "code": (
                "class Counter:\n"
                "    def __init__(self, start):\n"
                "        self.value = start\n"
                "\n"
                "    def bump(self, amount):\n"
                "        self.value = self.value + amount\n"
                "        return self.value\n"
                "\n"
                "n = int(input())\n"
                "c = Counter(n)\n"
                "print(c.bump(5))\n"
                "print(c.bump(10))\n"
            ),
            "inputs": ["1", "100", "-3"],
        },
    ],

    # ------------------------------------------------------------------
    "java": [
        {
            "name": "sum_two",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int a = sc.nextInt();\n"
                "        int b = sc.nextInt();\n"
                "        System.out.println(a + b);\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["2 3", "10 20", "-4 9"],
        },
        {
            "name": "square_function",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static int square(int n) {\n"
                "        return n * n;\n"
                "    }\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        System.out.println(square(sc.nextInt()));\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["5", "12", "0"],
        },
        {
            "name": "factorial",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int n = sc.nextInt();\n"
                "        int total = 1;\n"
                "        for (int i = 1; i < n + 1; i++) {\n"
                "            total = total * i;\n"
                "        }\n"
                "        System.out.println(total);\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["5", "1", "8"],
        },
        {
            "name": "grade_branches",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int score = sc.nextInt();\n"
                "        if (score > 89) {\n"
                "            System.out.println(\"A\");\n"
                "        } else if (score > 79) {\n"
                "            System.out.println(\"B\");\n"
                "        } else {\n"
                "            System.out.println(\"F\");\n"
                "        }\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["95", "82", "40"],
        },
        {
            "name": "while_countdown",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int n = sc.nextInt();\n"
                "        while (n > 0) {\n"
                "            System.out.println(n);\n"
                "            n = n - 1;\n"
                "        }\n"
                "        System.out.println(0);\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["4", "1", "7"],
        },
        {
            "name": "gcd",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static int gcd(int x, int y) {\n"
                "        while (y != 0) {\n"
                "            int t = y;\n"
                "            y = x % y;\n"
                "            x = t;\n"
                "        }\n"
                "        return x;\n"
                "    }\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        System.out.println(gcd(sc.nextInt(), sc.nextInt()));\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["12 18", "7 13", "100 75"],
        },
        {
            "name": "accumulator_class",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static class Counter {\n"
                "        private int value;\n"
                "        public Counter(int start) {\n"
                "            this.value = start;\n"
                "        }\n"
                "        public int bump(int amount) {\n"
                "            this.value = this.value + amount;\n"
                "            return this.value;\n"
                "        }\n"
                "    }\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        Counter c = new Counter(sc.nextInt());\n"
                "        System.out.println(c.bump(5));\n"
                "        System.out.println(c.bump(10));\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["1", "100", "-3"],
        },
        {
            "name": "nested_loop",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int n = sc.nextInt();\n"
                "        int total = 0;\n"
                "        for (int i = 0; i < n; i++) {\n"
                "            for (int j = 0; j < n; j++) {\n"
                "                total = total + 1;\n"
                "            }\n"
                "        }\n"
                "        System.out.println(total);\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["3", "1", "5"],
        },
        {
            "name": "absolute_value",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static int abs(int n) {\n"
                "        if (n < 0) {\n"
                "            return -n;\n"
                "        }\n"
                "        return n;\n"
                "    }\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        System.out.println(abs(sc.nextInt()));\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["-5", "5", "0"],
        },
        {
            "name": "sum_to_n",
            "code": (
                "import java.util.*;\n"
                "public class Converted {\n"
                "    public static void main(String[] args) {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        int n = sc.nextInt();\n"
                "        int total = 0;\n"
                "        for (int i = 0; i < n; i++) {\n"
                "            total += i;\n"
                "        }\n"
                "        System.out.println(total);\n"
                "    }\n"
                "}\n"
            ),
            "inputs": ["5", "10", "1"],
        },
    ],

    # ------------------------------------------------------------------
    "c": [
        {
            "name": "sum_two",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int a, b;\n"
                "    scanf(\"%d %d\", &a, &b);\n"
                "    printf(\"%d\\n\", a + b);\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["2 3", "10 20", "-4 9"],
        },
        {
            "name": "square_function",
            "code": (
                "#include <stdio.h>\n"
                "int square(int n) {\n"
                "    return n * n;\n"
                "}\n"
                "int main() {\n"
                "    int n;\n"
                "    scanf(\"%d\", &n);\n"
                "    printf(\"%d\\n\", square(n));\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "12", "0"],
        },
        {
            "name": "factorial",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int n, i, total;\n"
                "    scanf(\"%d\", &n);\n"
                "    total = 1;\n"
                "    for (i = 1; i < n + 1; i++) {\n"
                "        total = total * i;\n"
                "    }\n"
                "    printf(\"%d\\n\", total);\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "1", "8"],
        },
        {
            "name": "grade_branches",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int score;\n"
                "    scanf(\"%d\", &score);\n"
                "    if (score > 89) {\n"
                "        printf(\"A\\n\");\n"
                "    } else if (score > 79) {\n"
                "        printf(\"B\\n\");\n"
                "    } else {\n"
                "        printf(\"F\\n\");\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["95", "82", "40"],
        },
        {
            "name": "while_countdown",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int n;\n"
                "    scanf(\"%d\", &n);\n"
                "    while (n > 0) {\n"
                "        printf(\"%d\\n\", n);\n"
                "        n = n - 1;\n"
                "    }\n"
                "    printf(\"%d\\n\", 0);\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["4", "1", "7"],
        },
        {
            "name": "gcd",
            "code": (
                "#include <stdio.h>\n"
                "int gcd(int x, int y) {\n"
                "    int t;\n"
                "    while (y != 0) {\n"
                "        t = y;\n"
                "        y = x % y;\n"
                "        x = t;\n"
                "    }\n"
                "    return x;\n"
                "}\n"
                "int main() {\n"
                "    int a, b;\n"
                "    scanf(\"%d %d\", &a, &b);\n"
                "    printf(\"%d\\n\", gcd(a, b));\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["12 18", "7 13", "100 75"],
        },
        {
            "name": "nested_loop",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int n, i, j, total;\n"
                "    scanf(\"%d\", &n);\n"
                "    total = 0;\n"
                "    for (i = 0; i < n; i++) {\n"
                "        for (j = 0; j < n; j++) {\n"
                "            total = total + 1;\n"
                "        }\n"
                "    }\n"
                "    printf(\"%d\\n\", total);\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["3", "1", "5"],
        },
        {
            "name": "absolute_value",
            "code": (
                "#include <stdio.h>\n"
                "int absolute(int n) {\n"
                "    if (n < 0) {\n"
                "        return -n;\n"
                "    }\n"
                "    return n;\n"
                "}\n"
                "int main() {\n"
                "    int n;\n"
                "    scanf(\"%d\", &n);\n"
                "    printf(\"%d\\n\", absolute(n));\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["-5", "5", "0"],
        },
        {
            "name": "power_function",
            "code": (
                "#include <stdio.h>\n"
                "int power(int base, int exponent) {\n"
                "    int result = 1;\n"
                "    int i;\n"
                "    for (i = 0; i < exponent; i++) {\n"
                "        result = result * base;\n"
                "    }\n"
                "    return result;\n"
                "}\n"
                "int main() {\n"
                "    int a, b;\n"
                "    scanf(\"%d %d\", &a, &b);\n"
                "    printf(\"%d\\n\", power(a, b));\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["2 5", "3 3", "7 0"],
        },
        {
            "name": "sum_to_n",
            "code": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "    int n, i, total;\n"
                "    scanf(\"%d\", &n);\n"
                "    total = 0;\n"
                "    for (i = 0; i < n; i++) {\n"
                "        total += i;\n"
                "    }\n"
                "    printf(\"%d\\n\", total);\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "10", "1"],
        },
    ],

    # ------------------------------------------------------------------
    "c++": [
        {
            "name": "sum_two",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int a, b;\n"
                "    cin >> a;\n"
                "    cin >> b;\n"
                "    cout << a + b << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["2 3", "10 20", "-4 9"],
        },
        {
            "name": "square_function",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int square(int n) {\n"
                "    return n * n;\n"
                "}\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    cout << square(n) << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "12", "0"],
        },
        {
            "name": "factorial",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    int total = 1;\n"
                "    for (int i = 1; i < n + 1; i++) {\n"
                "        total = total * i;\n"
                "    }\n"
                "    cout << total << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "1", "8"],
        },
        {
            "name": "grade_branches",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int score;\n"
                "    cin >> score;\n"
                "    if (score > 89) {\n"
                "        cout << \"A\" << endl;\n"
                "    } else if (score > 79) {\n"
                "        cout << \"B\" << endl;\n"
                "    } else {\n"
                "        cout << \"F\" << endl;\n"
                "    }\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["95", "82", "40"],
        },
        {
            "name": "while_countdown",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    while (n > 0) {\n"
                "        cout << n << endl;\n"
                "        n = n - 1;\n"
                "    }\n"
                "    cout << 0 << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["4", "1", "7"],
        },
        {
            "name": "gcd",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int gcd(int x, int y) {\n"
                "    while (y != 0) {\n"
                "        int t = y;\n"
                "        y = x % y;\n"
                "        x = t;\n"
                "    }\n"
                "    return x;\n"
                "}\n"
                "int main() {\n"
                "    int a, b;\n"
                "    cin >> a;\n"
                "    cin >> b;\n"
                "    cout << gcd(a, b) << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["12 18", "7 13", "100 75"],
        },
        {
            "name": "nested_loop",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    int total = 0;\n"
                "    for (int i = 0; i < n; i++) {\n"
                "        for (int j = 0; j < n; j++) {\n"
                "            total = total + 1;\n"
                "        }\n"
                "    }\n"
                "    cout << total << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["3", "1", "5"],
        },
        {
            "name": "absolute_value",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int absolute(int n) {\n"
                "    if (n < 0) {\n"
                "        return -n;\n"
                "    }\n"
                "    return n;\n"
                "}\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    cout << absolute(n) << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["-5", "5", "0"],
        },
        {
            "name": "power_function",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int power(int base, int exponent) {\n"
                "    int result = 1;\n"
                "    for (int i = 0; i < exponent; i++) {\n"
                "        result = result * base;\n"
                "    }\n"
                "    return result;\n"
                "}\n"
                "int main() {\n"
                "    int a, b;\n"
                "    cin >> a;\n"
                "    cin >> b;\n"
                "    cout << power(a, b) << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["2 5", "3 3", "7 0"],
        },
        {
            "name": "sum_to_n",
            "code": (
                "#include <iostream>\n"
                "using namespace std;\n"
                "int main() {\n"
                "    int n;\n"
                "    cin >> n;\n"
                "    int total = 0;\n"
                "    for (int i = 0; i < n; i++) {\n"
                "        total += i;\n"
                "    }\n"
                "    cout << total << endl;\n"
                "    return 0;\n"
                "}\n"
            ),
            "inputs": ["5", "10", "1"],
        },
    ],
}


def iter_programs():
    for language, programs in CORPUS.items():
        for program in programs:
            yield language, program


def program_count():
    return sum(len(v) for v in CORPUS.values())
