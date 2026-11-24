"""Library calls with one meaning, whatever language they came from.

Parsers lower library idioms (Python's round(x, 1) and s[::-1], Java's
Math.round and StringBuilder, C++'s to_string and setprecision) to the IR
call names below, and every generator renders each name with exactly the
semantics stated here. Reference semantics are Python's unless noted.
"""

# Python str tests; for a single character they are the <ctype.h> tests.
CHAR_TESTS = ("isupper", "islower", "isdigit", "isalpha", "isspace", "isalnum")

# Functions with the same meaning in Python's math, Java's Math and C's math.h.
MATH_NAMES = ("sqrt", "pow", "floor", "ceil", "log", "log10", "exp", "sin", "cos", "tan", "hypot")

# C and C++ library functions; one that no generator maps is refused rather than emitted.
C_LIBRARY_CALLS = {
    "malloc", "calloc", "realloc", "free", "memcpy", "memmove", "memset", "memcmp", "memchr",
    "strcpy", "strncpy", "strcat", "strncat", "strcmp", "strncmp", "strchr", "strrchr", "strstr",
    "strtok", "strspn", "strcspn", "strpbrk", "strdup", "strlen", "sprintf", "snprintf", "sscanf",
    "strtol", "strtoul", "strtoll", "strtod", "atoi", "atol", "atoll", "atof", "fopen", "fclose",
    "fprintf", "fscanf", "fgets", "fputs", "fputc", "fgetc", "fread", "fwrite", "fflush", "getc",
    "putc", "ungetc", "perror", "gets", "qsort", "bsearch", "rand", "srand", "system", "getenv",
    "atexit", "abort", "time", "clock", "difftime", "localtime", "strftime", "asin", "acos", "atan",
    "atan2", "log2", "cbrt", "trunc", "lround", "fmax", "fmin", "fmod", "setjmp", "longjmp", "signal",
    "labs", "llabs", "fabs",
}

ROUNDING = {
    "round_even": "int",       # Python round(x): ties to even, integral result
    "round_digits": "double",  # Python round(x, n): exact binary value rounded half-even
    "round_half_up": "long",   # Java Math.round(x): floor(x + 0.5)
    "round_away": "double",    # C round(x): ties away from zero
}

# Calls whose result has the type of their first argument (a string or a list).
SAME_TYPE = ("slice", "reversed_copy", "sorted_copy")

# Calls that need a growable string or list, which C output does not have.
NEEDS_CONTAINERS = ("slice", "reversed_copy", "sorted_copy", "str_join")


def result_type(name, arg_types):
    """Type of a library call, or None when name is not one."""

    if name in ROUNDING:
        return ROUNDING[name]
    if name in SAME_TYPE:
        return arg_types[0] if arg_types else None
    if name == "str_join":
        return "String"
    if name in CHAR_TESTS:
        return "boolean"
    if name in MATH_NAMES:
        return "double"
    return None


def user_functions(program):
    """Names of the functions and methods a program defines."""

    names = set()
    for node in program.body:
        if type(node).__name__ == "Function":
            names.add(node.name)
        elif type(node).__name__ == "Class":
            names.update(method.name for method in node.methods)
    return names


def module_globals(program):
    """Top-level variables of a Python module that its functions read, by name.

    Python functions see module variables; a Java static method or a C
    function sees only fields and globals, so these must be declared there.
    A function that assigns the name has a local of its own instead.
    """

    from cross_language_system.core.naming import walk

    top = {}
    for node in program.body:
        if type(node).__name__ == "Variable" and node.name not in top:
            top[node.name] = node
    functions = [n for n in program.body if type(n).__name__ == "Function"]
    functions += [m for n in program.body if type(n).__name__ == "Class" for m in n.methods]
    used = set()
    for function in functions:
        nodes = list(walk(function.body))
        local = {n.name for n in nodes if type(n).__name__ == "Variable"} | set(function.params)
        local |= {n.iterator for n in nodes if type(n).__name__ == "ForLoop" and isinstance(n.iterator, str)}
        used |= {n.name for n in nodes if type(n).__name__ == "Identifier" and n.name in top and n.name not in local}
    return {name: node for name, node in top.items() if name in used}


def is_user_call(call, names):
    """True when call reaches a function of the program, not a library function.

    A function the program defines shadows a library function of the same
    name (C's max, a Java method pow), unless the parser marked the call as a
    qualified library call (Java's Math.pow, Python's math.pow).
    """

    return call.name in names and not getattr(call, "library", False)


JAVA_HELPERS = {
    "pySum": (
        "    static double pySum(List<Double> xs) {\n"
        "        // Left to right, as Python adds; DoubleStream.sum compensates rounding.\n"
        "        double total = 0.0;\n"
        "        for (double x : xs) total += x;\n"
        "        return total;\n"
        "    }\n"
    ),
    "pyFloat": (
        "    static String pyFloat(double x) {\n"
        "        // Python's repr: the shortest digits that read back as x.\n"
        "        if (Double.isNaN(x)) return \"nan\";\n"
        "        if (Double.isInfinite(x)) return x > 0 ? \"inf\" : \"-inf\";\n"
        "        if (x == 0) return 1 / x < 0 ? \"-0.0\" : \"0.0\";\n"
        "        String digits = \"\";\n"
        "        for (int p = 1; p <= 17; p++) {\n"
        "            digits = String.format(Locale.ROOT, \"%.\" + (p - 1) + \"e\", x);\n"
        "            if (Double.parseDouble(digits) == x) break;\n"
        "        }\n"
        "        int mark = digits.indexOf('e');\n"
        "        int exp = Integer.parseInt(digits.substring(mark + 1));\n"
        "        String bare = digits.substring(0, mark).replace(\"-\", \"\").replace(\".\", \"\").replaceAll(\"0+$\", \"\");\n"
        "        if (bare.isEmpty()) bare = \"0\";\n"
        "        StringBuilder out = new StringBuilder(x < 0 ? \"-\" : \"\");\n"
        "        if (exp < -4 || exp >= 16) {\n"
        "            out.append(bare.charAt(0));\n"
        "            if (bare.length() > 1) out.append('.').append(bare.substring(1));\n"
        "            out.append(exp < 0 ? \"e-\" : \"e+\").append(Math.abs(exp) < 10 ? \"0\" : \"\").append(Math.abs(exp));\n"
        "        } else if (exp < 0) {\n"
        "            out.append(\"0.\");\n"
        "            for (int i = -1; i > exp; i--) out.append('0');\n"
        "            out.append(bare);\n"
        "        } else {\n"
        "            for (int i = 0; i <= exp; i++) out.append(i < bare.length() ? bare.charAt(i) : '0');\n"
        "            out.append('.').append(bare.length() > exp + 1 ? bare.substring(exp + 1) : \"0\");\n"
        "        }\n"
        "        return out.toString();\n"
        "    }\n\n"
    ),
    "pyStr": (
        "    static String pyStr(Object o) {\n"
        "        // Python's str(): a container shows the repr of its elements.\n"
        "        return o instanceof String ? (String) o : pyRepr(o);\n"
        "    }\n\n"
        "    static String pyRepr(Object o) {\n"
        "        if (o == null) return \"None\";\n"
        "        if (o instanceof Boolean) return (Boolean) o ? \"True\" : \"False\";\n"
        "        if (o instanceof Double) return pyFloat((Double) o);\n"
        "        if (o instanceof Character) o = String.valueOf(o);\n"
        "        if (o instanceof String) {\n"
        "            String s = (String) o;\n"
        "            char quote = s.contains(\"'\") && !s.contains(\"\\\"\") ? '\"' : '\\'';\n"
        "            StringBuilder out = new StringBuilder().append(quote);\n"
        "            for (char c : s.toCharArray()) {\n"
        "                if (c == '\\\\' || c == quote) out.append('\\\\').append(c);\n"
        "                else if (c == '\\n') out.append(\"\\\\n\");\n"
        "                else if (c == '\\t') out.append(\"\\\\t\");\n"
        "                else if (c == '\\r') out.append(\"\\\\r\");\n"
        "                else out.append(c);\n"
        "            }\n"
        "            return out.append(quote).toString();\n"
        "        }\n"
        "        if (o instanceof Map) {\n"
        "            StringJoiner out = new StringJoiner(\", \", \"{\", \"}\");\n"
        "            for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) out.add(pyRepr(e.getKey()) + \": \" + pyRepr(e.getValue()));\n"
        "            return out.toString();\n"
        "        }\n"
        "        if (o instanceof Collection) {\n"
        "            boolean set = o instanceof Set;\n"
        "            if (set && ((Set<?>) o).isEmpty()) return \"set()\";\n"
        "            StringJoiner out = new StringJoiner(\", \", set ? \"{\" : \"[\", set ? \"}\" : \"]\");\n"
        "            for (Object e : (Collection<?>) o) out.add(pyRepr(e));\n"
        "            return out.toString();\n"
        "        }\n"
        "        return String.valueOf(o);\n"
        "    }\n\n"
    ),
    "pyChars": (
        "    static List<String> pyChars(String s) {\n"
        "        // A Python string iterates as one-character strings.\n"
        "        List<String> out = new ArrayList<>();\n"
        "        for (char c : s.toCharArray()) out.add(String.valueOf(c));\n"
        "        return out;\n"
        "    }\n\n"
    ),
    "cRound": (
        "    static double cRound(double x) {\n"
        "        // C's round(): nearest integer as a double, ties away from zero.\n"
        "        double a = Math.abs(x), n = Math.floor(a);\n"
        "        return Math.copySign(a - n >= 0.5 ? n + 1 : n, x);\n"
        "    }\n\n"
    ),
    "pyRound": (
        "    static double pyRound(double x, int digits) {\n"
        "        // Python rounds the exact binary value, ties to even.\n"
        "        return new java.math.BigDecimal(x).setScale(digits, java.math.RoundingMode.HALF_EVEN).doubleValue();\n"
        "    }\n\n"
    ),
    "pySlice": (
        "    static String pySlice(String s, int a, int b) {\n"
        "        int n = s.length();\n"
        "        a = a < 0 ? Math.max(0, a + n) : Math.min(a, n);\n"
        "        b = b < 0 ? Math.max(0, b + n) : Math.min(b, n);\n"
        "        return a < b ? s.substring(a, b) : \"\";\n"
        "    }\n\n"
        "    static <T> List<T> pySlice(List<T> s, int a, int b) {\n"
        "        int n = s.size();\n"
        "        a = a < 0 ? Math.max(0, a + n) : Math.min(a, n);\n"
        "        b = b < 0 ? Math.max(0, b + n) : Math.min(b, n);\n"
        "        return a < b ? new ArrayList<>(s.subList(a, b)) : new ArrayList<>();\n"
        "    }\n\n"
    ),
    "pyReversed": (
        "    static <T> List<T> pyReversed(List<T> s) {\n"
        "        List<T> copy = new ArrayList<>(s);\n"
        "        Collections.reverse(copy);\n"
        "        return copy;\n"
        "    }\n\n"
    ),
    "pySorted": (
        "    static <T extends Comparable<? super T>> List<T> pySorted(List<T> s) {\n"
        "        List<T> copy = new ArrayList<>(s);\n"
        "        Collections.sort(copy);\n"
        "        return copy;\n"
        "    }\n\n"
    ),
    "pyCount": (
        "    static int pyCount(String s, String sub) {\n"
        "        if (sub.isEmpty()) return s.length() + 1;\n"
        "        int count = 0;\n"
        "        for (int i = s.indexOf(sub); i >= 0; i = s.indexOf(sub, i + sub.length())) count++;\n"
        "        return count;\n"
        "    }\n\n"
    ),
    "pyTests": (
        "    static boolean pyIsUpper(char c) { return Character.isUpperCase(c); }\n"
        "    static boolean pyIsLower(char c) { return Character.isLowerCase(c); }\n"
        "    static boolean pyIsDigit(char c) { return Character.isDigit(c); }\n"
        "    static boolean pyIsAlpha(char c) { return Character.isLetter(c); }\n"
        "    static boolean pyIsSpace(char c) { return Character.isWhitespace(c); }\n"
        "    static boolean pyIsAlnum(char c) { return Character.isLetterOrDigit(c); }\n\n"
        "    static boolean pyIsUpper(String s) {\n"
        "        boolean cased = false;\n"
        "        for (char c : s.toCharArray()) {\n"
        "            if (Character.isLowerCase(c)) return false;\n"
        "            if (Character.isUpperCase(c)) cased = true;\n"
        "        }\n"
        "        return cased;\n"
        "    }\n\n"
        "    static boolean pyIsLower(String s) {\n"
        "        boolean cased = false;\n"
        "        for (char c : s.toCharArray()) {\n"
        "            if (Character.isUpperCase(c)) return false;\n"
        "            if (Character.isLowerCase(c)) cased = true;\n"
        "        }\n"
        "        return cased;\n"
        "    }\n\n"
        "    static boolean pyIsDigit(String s) { return !s.isEmpty() && s.chars().allMatch(Character::isDigit); }\n"
        "    static boolean pyIsAlpha(String s) { return !s.isEmpty() && s.chars().allMatch(Character::isLetter); }\n"
        "    static boolean pyIsSpace(String s) { return !s.isEmpty() && s.chars().allMatch(Character::isWhitespace); }\n"
        "    static boolean pyIsAlnum(String s) { return !s.isEmpty() && s.chars().allMatch(Character::isLetterOrDigit); }\n\n"
    ),
}

JAVA_TESTS = {"isupper": "pyIsUpper", "islower": "pyIsLower", "isdigit": "pyIsDigit",
              "isalpha": "pyIsAlpha", "isspace": "pyIsSpace", "isalnum": "pyIsAlnum"}

CPP_HELPERS = {
    "repeat": (
        "static string _repeat(const string& text, long long times) {\n"
        "    // Python's str * int; no copies for a count below one.\n"
        "    string out;\n"
        "    for (long long i = 0; i < times; i++) out += text;\n"
        "    return out;\n"
        "}\n\n"
    ),
    "split_on": (
        "static vector<string> _split_on(const string& s, const string& sep) {\n"
        "    // Python's str.split(sep): every field, empty ones included.\n"
        "    vector<string> parts;\n"
        "    size_t start = 0, found;\n"
        "    while ((found = s.find(sep, start)) != string::npos) {\n"
        "        parts.push_back(s.substr(start, found - start));\n"
        "        start = found + sep.size();\n"
        "    }\n"
        "    parts.push_back(s.substr(start));\n"
        "    return parts;\n"
        "}\n\n"
    ),
    "java_split": (
        "static vector<string> _java_split(const string& s, const string& sep) {\n"
        "    // Java's String.split on literal text: trailing empty fields dropped.\n"
        "    if (s.empty()) return {\"\"};\n"
        "    vector<string> parts = _split_on(s, sep);\n"
        "    while (!parts.empty() && parts.back().empty()) parts.pop_back();\n"
        "    return parts;\n"
        "}\n\n"
        "static vector<string> _java_split_ws(const string& s) {\n"
        "    // Java's split(\"\\\\s+\"): leading whitespace gives an empty first field.\n"
        "    if (s.empty()) return {\"\"};\n"
        "    vector<string> parts(1);\n"
        "    for (size_t i = 0; i < s.size(); i++) {\n"
        "        if (!isspace((unsigned char) s[i])) parts.back() += s[i];\n"
        "        else if (i == 0 || !isspace((unsigned char) s[i - 1])) parts.push_back(\"\");\n"
        "    }\n"
        "    while (!parts.empty() && parts.back().empty()) parts.pop_back();\n"
        "    return parts;\n"
        "}\n\n"
    ),
    "java_text": (
        "static string _java_text(long long x) { return to_string(x); }\n"
        "static string _java_text(int x) { return to_string(x); }\n"
        "static string _java_text(bool x) { return x ? \"true\" : \"false\"; }\n"
        "static string _java_text(char x) { return string(1, x); }\n"
        "static string _java_text(const string& x) { return x; }\n\n"
        "template <class T> string _java_text(const vector<T>& v) {\n"
        "    // Java's List.toString: [a, b, c] with each element's own text.\n"
        "    string out = \"[\";\n"
        "    for (size_t i = 0; i < v.size(); i++) {\n"
        "        if (i) out += \", \";\n"
        "        out += _java_text((T) v[i]);\n"
        "    }\n"
        "    return out + \"]\";\n"
        "}\n\n"
    ),
    "repr": (
        "static string _py_repr(long long x) { return to_string(x); }\n"
        "static string _py_repr(int x) { return to_string(x); }\n"
        "static string _py_repr(bool x) { return x ? \"True\" : \"False\"; }\n"
        "static string _py_repr(double x) { return _fmt_double(x); }\n\n"
        "static string _py_repr(const string& s) {\n"
        "    // Python's repr of a string: quoted, with escapes.\n"
        "    char quote = s.find('\\'') != string::npos && s.find('\"') == string::npos ? '\"' : '\\'';\n"
        "    string out(1, quote);\n"
        "    for (char c : s) {\n"
        "        if (c == '\\\\' || c == quote) { out += '\\\\'; out += c; }\n"
        "        else if (c == '\\n') out += \"\\\\n\";\n"
        "        else if (c == '\\t') out += \"\\\\t\";\n"
        "        else if (c == '\\r') out += \"\\\\r\";\n"
        "        else out += c;\n"
        "    }\n"
        "    return out + quote;\n"
        "}\n\n"
        "static string _py_repr(char c) { return _py_repr(string(1, c)); }\n\n"
        "template <class T> string _py_repr(const vector<T>& v) {\n"
        "    // Python's str() of a list shows the repr of its elements.\n"
        "    string out = \"[\";\n"
        "    for (size_t i = 0; i < v.size(); i++) {\n"
        "        if (i) out += \", \";\n"
        "        out += _py_repr((T) v[i]);\n"
        "    }\n"
        "    return out + \"]\";\n"
        "}\n\n"
    ),
    "round_half_up": (
        "static long long _round_half_up(double x) {\n"
        "    // Java's Math.round: nearest integer, ties toward positive infinity.\n"
        "    double n = floor(x);\n"
        "    return (long long) (x - n >= 0.5 ? n + 1 : n);\n"
        "}\n\n"
    ),
    "py_round": (
        "static double _py_round(double x, int digits) {\n"
        "    // Python rounds the exact binary value, ties to even, as printf does.\n"
        "    char text[512];\n"
        "    snprintf(text, sizeof text, \"%.*f\", digits, x);\n"
        "    return strtod(text, nullptr);\n"
        "}\n\n"
    ),
    "slice": (
        "static const long long _END = 1LL << 62;\n\n"
        "static string _slice(const string& s, long long a, long long b) {\n"
        "    long long n = s.size();\n"
        "    a = a < 0 ? max(0LL, a + n) : min(a, n);\n"
        "    b = b < 0 ? max(0LL, b + n) : min(b, n);\n"
        "    return a < b ? s.substr(a, b - a) : string();\n"
        "}\n\n"
        "template <class T> vector<T> _slice(const vector<T>& v, long long a, long long b) {\n"
        "    long long n = v.size();\n"
        "    a = a < 0 ? max(0LL, a + n) : min(a, n);\n"
        "    b = b < 0 ? max(0LL, b + n) : min(b, n);\n"
        "    return a < b ? vector<T>(v.begin() + a, v.begin() + b) : vector<T>();\n"
        "}\n\n"
    ),
    "reversed": (
        "template <class C> C _reversed(C c) {\n"
        "    reverse(c.begin(), c.end());\n"
        "    return c;\n"
        "}\n\n"
    ),
    "sorted": (
        "template <class C> C _sorted(C c) {\n"
        "    sort(c.begin(), c.end());\n"
        "    return c;\n"
        "}\n\n"
    ),
    "join": (
        "static string _join(const string& sep, const vector<string>& parts) {\n"
        "    string out;\n"
        "    for (size_t i = 0; i < parts.size(); i++) {\n"
        "        if (i) out += sep;\n"
        "        out += parts[i];\n"
        "    }\n"
        "    return out;\n"
        "}\n\n"
    ),
    "replace": (
        "static string _replace_all(const string& s, const string& from, const string& to) {\n"
        "    if (from.empty()) {\n"
        "        string out = to;\n"
        "        for (char c : s) { out += c; out += to; }\n"
        "        return out;\n"
        "    }\n"
        "    string out;\n"
        "    size_t start = 0, found;\n"
        "    while ((found = s.find(from, start)) != string::npos) {\n"
        "        out += s.substr(start, found - start) + to;\n"
        "        start = found + from.size();\n"
        "    }\n"
        "    return out + s.substr(start);\n"
        "}\n\n"
    ),
    "count": (
        "static int _count(const string& s, const string& sub) {\n"
        "    if (sub.empty()) return (int) s.size() + 1;\n"
        "    int count = 0;\n"
        "    for (size_t i = s.find(sub); i != string::npos; i = s.find(sub, i + sub.size())) count++;\n"
        "    return count;\n"
        "}\n\n"
        "static int _count(const string& s, char c) { return (int) count(s.begin(), s.end(), c); }\n\n"
        "template <class T, class U> int _count(const vector<T>& v, const U& x) {\n"
        "    return (int) count(v.begin(), v.end(), x);\n"
        "}\n\n"
    ),
    "pop": (
        "template <class T> T _pop(vector<T>& v) {\n"
        "    T last = v.back();\n"
        "    v.pop_back();\n"
        "    return last;\n"
        "}\n\n"
        "template <class T> T _pop(vector<T>& v, long long i) {\n"
        "    if (i < 0) i += v.size();\n"
        "    T item = v[i];\n"
        "    v.erase(v.begin() + i);\n"
        "    return item;\n"
        "}\n\n"
    ),
    "tests": "".join(
        f"static bool _py_{name}(char c) {{ return {name}((unsigned char) c); }}\n"
        for name in CHAR_TESTS
    ) + "\n" + (
        "static bool _py_isupper(const string& s) {\n"
        "    bool cased = false;\n"
        "    for (unsigned char c : s) {\n"
        "        if (islower(c)) return false;\n"
        "        if (isupper(c)) cased = true;\n"
        "    }\n"
        "    return cased;\n"
        "}\n\n"
        "static bool _py_islower(const string& s) {\n"
        "    bool cased = false;\n"
        "    for (unsigned char c : s) {\n"
        "        if (isupper(c)) return false;\n"
        "        if (islower(c)) cased = true;\n"
        "    }\n"
        "    return cased;\n"
        "}\n\n"
    ) + "".join(
        f"static bool _py_{name}(const string& s) {{\n"
        f"    if (s.empty()) return false;\n"
        f"    for (unsigned char c : s) if (!{name}(c)) return false;\n"
        f"    return true;\n"
        f"}}\n\n"
        for name in ("isdigit", "isalpha", "isspace", "isalnum")
    ),
}

C_HELPERS = {
    "round_half_up": (
        "static long long _round_half_up(double x) {\n"
        "    /* Java's Math.round: nearest integer, ties toward positive infinity. */\n"
        "    double n = floor(x);\n"
        "    return (long long) (x - n >= 0.5 ? n + 1 : n);\n"
        "}\n\n"
    ),
    "py_round": (
        "static double _py_round(double x, int digits) {\n"
        "    /* Python rounds the exact binary value, ties to even, as printf does. */\n"
        "    char text[512];\n"
        "    snprintf(text, sizeof text, \"%.*f\", digits, x);\n"
        "    return strtod(text, NULL);\n"
        "}\n\n"
    ),
    "tests": "".join(
        f"static int _py_{name}_c(int c) {{ return {name}((unsigned char) c) != 0; }}\n"
        for name in CHAR_TESTS
    ) + "\n" + (
        "static int _py_isupper_s(const char *s) {\n"
        "    int cased = 0;\n"
        "    for (; *s; s++) {\n"
        "        if (islower((unsigned char) *s)) return 0;\n"
        "        if (isupper((unsigned char) *s)) cased = 1;\n"
        "    }\n"
        "    return cased;\n"
        "}\n\n"
        "static int _py_islower_s(const char *s) {\n"
        "    int cased = 0;\n"
        "    for (; *s; s++) {\n"
        "        if (isupper((unsigned char) *s)) return 0;\n"
        "        if (islower((unsigned char) *s)) cased = 1;\n"
        "    }\n"
        "    return cased;\n"
        "}\n\n"
    ) + "".join(
        f"static int _py_{name}_s(const char *s) {{\n"
        f"    if (!*s) return 0;\n"
        f"    for (; *s; s++) if (!{name}((unsigned char) *s)) return 0;\n"
        f"    return 1;\n"
        f"}}\n\n"
        for name in ("isdigit", "isalpha", "isspace", "isalnum")
    ) + "".join(
        # A char and a string argument need different tests; _Generic picks one.
        f"#define _py_{name}(x) _Generic((x), char *: _py_{name}_s, const char *: _py_{name}_s, "
        f"default: _py_{name}_c)(x)\n"
        for name in CHAR_TESTS
    ) + "\n",
}
