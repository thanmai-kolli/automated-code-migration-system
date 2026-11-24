"""Recursive-descent parser for the C/C++ subset this system targets.

The existing regex parsers slice source into raw text chunks, which is enough
for C<->C++ text rewriting but produces no usable IR for C -> Python/Java. This
module builds a real IR so those directions generate meaningful code.

It deliberately covers the common procedural subset — functions, structs and
simple classes, declarations, control flow, calls and expressions — rather than
the whole language. Anything outside that subset raises UnsupportedConstruct:
a construct that is skipped instead would vanish from the translation without
a trace.
"""

import re

from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.printf_format import tokens as format_tokens, value_count
from cross_language_system.parsers import lowering


QUALIFIERS = {"const", "static", "inline", "extern", "register", "volatile", "constexpr", "mutable"}

PRIMITIVE_WORDS = {"void", "int", "long", "short", "char", "float", "double", "bool",
                   "unsigned", "signed"}

TYPE_KEYWORDS = PRIMITIVE_WORDS | QUALIFIERS | {"string", "auto", "size_t"}

CONTROL_KEYWORDS = {
    "if", "else", "for", "while", "do", "return", "break", "continue",
    "switch", "case", "default", "struct", "class", "public", "private",
    "protected", "new", "delete", "try", "catch", "throw", "goto", "sizeof",
    "template", "typename", "enum", "union", "operator", "friend", "virtual",
}

TOKEN_RE = re.compile(r"""
      (?P<comment>//[^\n]*|/\*.*?\*/)
    | (?P<preproc>\#[^\n]*(?:\\\n[^\n]*)*)
    | (?P<string>"(?:\\.|[^"\\])*")
    | (?P<char>'(?:\\.|[^'\\])')
    | (?P<number>0[xX][0-9a-fA-F]+[uUlL]*
                |(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?[fFlL]?
                |\d+[eE][+-]?\d+[fFlL]?
                |\d+[uUlL]*)
    | (?P<name>[A-Za-z_]\w*)
    | (?P<op><<=|>>=|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|::)
    | (?P<punct>[{}()\[\];,.<>+\-*/%=!&|^~?:])
    | (?P<ws>\s+)
""", re.VERBOSE | re.DOTALL)


BINARY_PRECEDENCE = [
    (["||"], "Or"),
    (["&&"], "And"),
    (["|"], None),
    (["^"], None),
    (["&"], None),
    (["==", "!="], None),
    (["<", ">", "<=", ">="], None),
    (["<<", ">>"], None),
    (["+", "-"], None),
    (["*", "/", "%"], None),
]

# A cout operand binds tighter than <<, so it is parsed from the additive level.
ABOVE_SHIFT = 8

COMPARISON_NAMES = {
    "==": "Eq", "!=": "NotEq", "<": "Lt", ">": "Gt", "<=": "LtE", ">=": "GtE",
}

ARITHMETIC_NAMES = {
    "+": "Add", "-": "Sub", "*": "Mult", "/": "Div", "%": "Mod",
    "&": "BitAnd", "|": "BitOr", "^": "BitXor", "<<": "LShift", ">>": "RShift",
}

COMPOUND_NAMES = {
    "+=": "Add", "-=": "Sub", "*=": "Mult", "/=": "Div", "%=": "Mod",
    "&=": "BitAnd", "|=": "BitOr", "^=": "BitXor", "<<=": "LShift", ">>=": "RShift",
}

TYPE_TO_IR = {
    "int": "int", "short": "int", "size_t": "long", "unsigned": "int", "signed": "int",
    "long": "long", "long long": "long", "long int": "long", "long long int": "long",
    "short int": "int", "unsigned int": "int", "signed int": "int",
    "unsigned long": "long", "unsigned long long": "long", "unsigned short": "int",
    "float": "double", "double": "double", "long double": "double",
    "char": "char", "signed char": "char", "unsigned char": "char",
    "bool": "boolean",
    "char*": "String", "string": "String", "std::string": "String",
    "void": "void",
}

CASTS = {"int": "int", "long": "long", "short": "int", "char": "char",
         "float": "float", "double": "float", "boolean": "bool", "String": "str"}

SCANF_TYPES = {"d": "int", "i": "int", "u": "int", "f": "double", "e": "double",
               "g": "double", "s": "token", "c": "char"}

STREAM_MANIPULATORS = {"fixed", "setprecision", "setw", "scientific", "boolalpha", "left",
                       "right", "setfill", "showpoint", "hex", "dec", "oct", "noboolalpha"}

# Manipulators whose effect lasts until changed (setw affects one item only).
STICKY_MANIPULATORS = {"fixed", "setprecision", "left", "right"}

# C and C++ conversions that are casts in the IR.
CONVERSIONS = {"stoi": "int", "atoi": "int", "stol": "long", "stoll": "long", "atol": "long",
               "atoll": "long", "stod": "float", "stof": "float", "atof": "float"}

SCALARS = {"int", "long", "double", "char", "boolean", "String"}

# <limits.h> / <climits> constants, as plain values.
LIMITS = {"INT_MAX": 2**31 - 1, "INT_MIN": -2**31, "LLONG_MAX": 2**63 - 1,
          "LLONG_MIN": -2**63, "LONG_MAX": 2**31 - 1, "LONG_MIN": -2**31}


class _Step:
    """x++ / ++x / x-- / --x, held apart until it is known to stand alone.

    As a statement (or a for-loop update) it is just x += 1. Inside a larger
    expression its side effect would need statement hoisting, so any _Step
    that survives parsing is refused.
    """

    def __init__(self, target, operator):
        self.target = target
        self.operator = operator


def tokenize(code):

    tokens = []
    macros = {}
    position = 0

    while position < len(code):
        match = TOKEN_RE.match(code, position)
        if not match:
            raise UnsupportedConstruct(f"unexpected character {code[position]!r}")
        position = match.end()
        kind = match.lastgroup
        if kind == "preproc":
            _define(match.group(), macros)
            continue
        if kind in ("ws", "comment"):
            continue
        if kind == "name" and match.group() in macros:
            tokens.extend(macros[match.group()])
            continue
        tokens.append((kind, match.group()))

    tokens.append(("eof", ""))
    return tokens


def _define(line, macros):
    """#define NAME value becomes a token substitution; anything fancier is refused."""

    match = re.match(r"#\s*define\s+([A-Za-z_]\w*)(\(?)(.*)", line.replace("\\\n", " "))
    if not match:
        return
    name, function_like, body = match.groups()
    if function_like:
        raise UnsupportedConstruct(f"function-like macro {name}()")
    body_tokens = [t for t in tokenize(body.strip())[:-1]]
    if len(body_tokens) > 1:
        # Keep the macro's grouping wherever it is used.
        body_tokens = [("punct", "(")] + body_tokens + [("punct", ")")]
    macros[name] = body_tokens


class CLikeParser:

    def __init__(self):
        self.tokens = []
        self.index = 0
        self.records = set()
        self._temp_index = 0
        # Declared variable types (function-scoped is enough for the checks
        # below) and the char arrays that hold C strings.
        self.var_types = {}
        self.c_strings = set()
        # cout formatting state, tracked in program order within one function.
        self.stream = {"fixed": False, "precision": None, "left": False}
        self.block_depth = 0
        self.current_function = None
        self.sticky_in = set()      # functions that set fixed/setprecision/left
        self.cout_in = set()        # functions that print computed values

    # ------------------------------------------------------------
    # TOKEN HELPERS
    # ------------------------------------------------------------

    def peek(self, offset=0):
        position = min(self.index + offset, len(self.tokens) - 1)
        return self.tokens[position]

    def value(self, offset=0):
        return self.peek(offset)[1]

    def next(self):
        token = self.peek()
        self.index += 1
        return token

    def accept(self, text):
        if self.value() == text and self.peek()[0] != "string":
            self.index += 1
            return True
        return False

    def expect(self, text):
        if not self.accept(text):
            raise SyntaxError(f"expected {text!r}, found {self.value()!r}")

    def at_end(self):
        return self.peek()[0] == "eof"

    def _skip_namespace(self):
        while self.value() == "std" and self.value(1) == "::":
            self.index += 2

    # ------------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------------

    def parse(self, code):

        self.tokens = tokenize(code)
        self.index = 0

        body = []

        while not self.at_end():

            if self.accept(";"):
                continue

            if self.value() in ("using", "namespace"):
                self._skip_to_semicolon()
                continue

            if self.value() == "typedef":
                record = self._parse_typedef()
                if record is not None:
                    body.append(record)
                continue

            if self.value() in ("struct", "class") and self.value(2) in ("{", ":"):
                body.append(self._parse_record())
                continue

            if self.value() in ("template", "enum", "union"):
                raise UnsupportedConstruct(f"{self.value()} declarations")

            declaration = self._parse_top_level_declaration()
            if isinstance(declaration, list):
                body.extend(declaration)
            elif declaration is not None:
                body.append(declaration)

        program = Program(body)
        self._refuse_leftover_steps(program)
        if self.sticky_in and self.cout_in - self.sticky_in:
            # The stream state set in one function would also govern the others.
            raise UnsupportedConstruct("stream manipulators that would apply across functions")
        return program

    def _refuse_leftover_steps(self, program):
        stack = [program]
        while stack:
            node = stack.pop()
            if isinstance(node, _Step):
                raise UnsupportedConstruct("++ or -- inside a larger expression")
            if isinstance(node, list):
                stack.extend(node)
            elif hasattr(node, "__dict__"):
                stack.extend(v for v in vars(node).values() if isinstance(v, list) or hasattr(v, "__dict__"))

    def _skip_to_semicolon(self):
        depth = 0
        while not self.at_end():
            token = self.value()
            if token in ("{", "(", "["):
                depth += 1
            elif token in ("}", ")", "]"):
                depth -= 1
            self.index += 1
            if token == ";" and depth <= 0:
                return

    # ------------------------------------------------------------
    # TYPES
    # ------------------------------------------------------------

    def _looks_like_type(self, offset=0):
        kind, text = self.peek(offset)
        if kind != "name":
            return False
        if text in TYPE_KEYWORDS:
            return True
        if text == "struct":
            return self.peek(offset + 1)[0] == "name"
        if text == "std" and self.value(offset + 1) == "::":
            return self.value(offset + 2) in ("string", "vector", "set", "map")
        if text in self.records and self.peek(offset + 1)[0] == "name":
            return True
        # A user type is an identifier followed by another identifier or a star.
        return (
            text not in CONTROL_KEYWORDS
            and (self.peek(offset + 1)[0] == "name" or self.value(offset + 1) == "<")
        )

    def _parse_type(self):

        self.last_base_type = None
        constant = False
        while self.value() in QUALIFIERS:
            constant = constant or self.value() == "const"
            self.index += 1

        if self.accept("struct"):
            pass

        if self.peek()[0] != "name":
            return None

        self._skip_namespace()

        # unsigned long long int, long double, ...
        if self.value() in PRIMITIVE_WORDS:
            words = []
            while self.value() in PRIMITIVE_WORDS:
                words.append(self.next()[1])
            if words in (["unsigned"], ["signed"]):
                words.append("int")
            name = " ".join(words)
            if name not in TYPE_TO_IR:
                raise UnsupportedConstruct(f"the type '{name}'")
        else:
            parts = [self.next()[1]]
            while self.accept("::"):
                parts.append(self.next()[1])
            name = "::".join(parts)
        # Remembered so a declaration can tell std::string from char*.
        self.last_base_type = name.split("::")[-1]

        while self.value() in QUALIFIERS:
            constant = constant or self.value() == "const"
            self.index += 1

        # Template arguments: vector<int>
        if self.value() == "<":
            depth = 0
            inner = []
            while not self.at_end():
                token = self.value()
                if token == "<":
                    depth += 1
                elif token == ">":
                    depth -= 1
                    self.index += 1
                    if depth == 0:
                        break
                    inner.append(token)
                    continue
                elif token == ">>":
                    raise UnsupportedConstruct("nested template types")
                elif depth:
                    inner.append(token)
                self.index += 1
            base = name.split("::")[-1]
            if base not in ("vector", "set", "list"):
                raise UnsupportedConstruct(f"the template type {base}<...>")
            element = self._to_ir_type(" ".join(inner) or "int")
            container = "Set" if base == "set" else "List"
            name = f"{container}<{self._box(element)}>"
            return self._decorators(name, constant)

        return self._decorators(self._to_ir_type(name), constant)

    def _decorators(self, name, constant):
        """Pointer and reference markers after a type."""

        pointer = False
        while self.value() in ("*", "&", "const"):
            token = self.next()[1]
            if token == "*":
                pointer = True
            elif token == "&" and not constant and name in SCALARS:
                # Writing through a reference changes the caller's variable,
                # which Python and Java cannot do for a value type. Containers
                # and objects are references there already.
                raise UnsupportedConstruct("non-const references to a scalar")

        if pointer and name == "char":
            return "String"
        if pointer and name in self.records:
            # Every Python or Java object is already a reference, so a pointer
            # to a struct means the same thing as the struct itself there.
            return name
        if pointer:
            return f"List<{self._box(name)}>"
        return name

    @staticmethod
    def _to_ir_type(name):
        return TYPE_TO_IR.get(name, name)

    @staticmethod
    def _box(name):
        return {"int": "Integer", "long": "Long", "double": "Double", "boolean": "Boolean",
                "char": "Character"}.get(name, name)

    # ------------------------------------------------------------
    # DECLARATIONS
    # ------------------------------------------------------------

    def _parse_top_level_declaration(self):

        if not self._looks_like_type():
            raise UnsupportedConstruct(f"unexpected '{self.value()}' at the top level")

        declared = self._parse_type()

        if declared is None or self.peek()[0] != "name":
            raise UnsupportedConstruct(f"unexpected '{self.value()}' after a type")

        name = self.next()[1]

        if self.value() == "::":
            raise UnsupportedConstruct("member functions defined outside their class")

        if self.value() == "(":
            return self._parse_function(declared, name)

        # Global variable(s): rewind onto the name and reuse the local path.
        self.index -= 1
        return self._parse_declarators(declared)

    def _parse_function(self, return_type, name, owner=None):

        params, param_types = self._parse_parameters()

        while self.value() in ("const", "override", "noexcept", "final"):
            self.index += 1

        # A prototype declares nothing the IR needs.
        if self.accept(";"):
            return None

        prelude = []
        if self.accept(":"):
            if owner is None or name != owner:
                raise SyntaxError("only a constructor may have an initializer list")
            prelude = self._parse_member_initializers()

        self.current_function = f"{owner}::{name}" if owner else name
        self.stream = {"fixed": False, "precision": None, "left": False}
        body = self._parse_block()

        return Function(
            name,
            params,
            prelude + body,
            return_type,
            is_constructor=(owner is not None and name == owner),
            is_static=owner is None,
            param_types=param_types,
            owner=owner,
        )

    def _parse_member_initializers(self):
        """balance(b), owner(o)  ->  this->balance = b; this->owner = o;"""

        assignments = []
        while self.peek()[0] == "name":
            member = self.next()[1]
            self.expect("(")
            value = self._parse_value()
            self.expect(")")
            assignments.append(Assignment(AttributeAccess(SelfRef(), member), value))
            if not self.accept(","):
                break
        return assignments

    def _parse_parameters(self):

        self.expect("(")
        params = []
        param_types = {}

        while not self.at_end() and self.value() != ")":

            if self.accept(","):
                continue

            if self.value() == "void" and self.value(1) == ")":
                self.index += 1
                break

            declared = self._parse_type()

            if declared is None or self.peek()[0] != "name":
                raise UnsupportedConstruct("unnamed or unusual function parameters")

            name = self.next()[1]
            while self.accept("["):
                while not self.at_end() and self.value() != "]":
                    self.index += 1
                self.expect("]")
                declared = f"List<{self._box(declared)}>"
            if self.value() == "=":
                raise UnsupportedConstruct("default parameter values")
            params.append(name)
            param_types[name] = declared
            self.var_types[name] = declared

        self.expect(")")
        return params, param_types

    def _parse_typedef(self):
        """typedef struct { ... } Name;  is a record; other typedefs are refused."""

        self.index += 1  # typedef
        if self.value() != "struct":
            raise UnsupportedConstruct("typedef of a non-struct type")
        self.index += 1
        if self.peek()[0] == "name" and self.value(1) == "{":
            self.index += 1
        if self.value() != "{":
            raise UnsupportedConstruct("typedef of a struct declared elsewhere")
        record = self._parse_record_body("_anonymous")
        alias = self.next()[1]
        self.expect(";")
        record.name = alias
        for method in record.methods:
            method.owner = alias
        self.records.add(alias)
        return record

    def _parse_record(self):
        """struct / class declaration."""

        self.index += 1  # struct | class
        name = self.next()[1]

        base = None
        if self.accept(":"):
            while self.value() in ("public", "private", "protected", "virtual"):
                self.index += 1
            base = self.next()[1]

        self.records.add(name)
        record = self._parse_record_body(name, base)
        self.expect(";")
        return record

    def _parse_record_body(self, name, base=None):

        self.expect("{")
        fields = []
        methods = []

        while not self.at_end() and self.value() != "}":

            if self.value() in ("public", "private", "protected"):
                self.index += 1
                self.expect(":")
                continue

            if self.accept(";"):
                continue

            if self.value() in ("friend", "virtual", "operator", "template") or self.value() == "~":
                raise UnsupportedConstruct(f"'{self.value()}' members in a class")

            if self.value() == "static":
                raise UnsupportedConstruct("static class members")

            # Constructor: Name(
            if self.value() == name and self.value(1) == "(":
                self.index += 1
                method = self._parse_function(name, name, owner=name)
                if method:
                    methods.append(method)
                continue

            declared = self._parse_type()

            if declared is None or self.peek()[0] != "name":
                raise UnsupportedConstruct(f"unexpected '{self.value()}' in a class body")

            member = self.next()[1]

            if self.value() == "(":
                method = self._parse_function(declared, member, owner=name)
                if method:
                    method.is_static = False
                    methods.append(method)
                continue

            while True:
                field_type, value = declared, None
                dimensions = []
                while self.accept("["):
                    dimensions.append(self._parse_value())
                    self.expect("]")
                if dimensions:
                    if declared == "char" and len(dimensions) == 1:
                        # char name[32]; holds a C string.
                        field_type = "String"
                    else:
                        for _ in dimensions:
                            field_type = f"List<{self._box(field_type)}>"
                        value = FunctionCall("range_array", dimensions)
                        value.element_type = declared
                if self.accept("="):
                    value = self._parse_value()
                fields.append(Field(member, field_type, value))
                if not self.accept(","):
                    break
                member = self.next()[1]
            self.expect(";")

        self.expect("}")

        record = Class(name, methods, fields, base)
        lowering.bind_members(record)
        return record

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def _parse_block(self):

        self.block_depth += 1
        try:
            return self._parse_block_body()
        finally:
            self.block_depth -= 1

    def _parse_block_body(self):

        body = []

        if not self.accept("{"):
            statement = self._parse_statement()
            if isinstance(statement, list):
                return [s for s in statement if s is not None]
            return [statement] if statement is not None else []

        while not self.at_end() and self.value() != "}":
            statement = self._parse_statement()
            # One scanf or cin chain expands into several reads.
            if isinstance(statement, list):
                body.extend(s for s in statement if s is not None)
            elif statement is not None:
                body.append(statement)

        self.expect("}")
        return body

    def _parse_statement(self):

        token = self.value()

        if self.peek()[0] in ("string", "number", "char"):
            token = None

        if token == ";":
            self.index += 1
            return None

        if token == "{":
            return Block(self._parse_block())

        if token == "return":
            self.index += 1
            if self.accept(";"):
                return Return(None)
            value = self._parse_value()
            self.expect(";")
            return Return(value)

        if token == "break":
            self.index += 1
            self.expect(";")
            return Break()

        if token == "continue":
            self.index += 1
            self.expect(";")
            return Continue()

        if token == "if":
            return self._parse_if()

        if token == "while":
            self.index += 1
            self.expect("(")
            condition = self._parse_value()
            self.expect(")")
            return WhileLoop(condition, self._parse_block())

        if token == "do":
            self.index += 1
            body = self._parse_block()
            self.expect("while")
            self.expect("(")
            condition = self._parse_value()
            self.expect(")")
            self.expect(";")
            return lowering.do_while(body, condition)

        if token == "for":
            return self._parse_for()

        if token == "switch":
            return self._parse_switch()

        if token in ("delete",):
            # Freeing memory has no counterpart in a garbage-collected target.
            self._skip_to_semicolon()
            return None

        if token in ("goto", "throw", "try", "case", "default"):
            raise UnsupportedConstruct(f"'{token}' statements")

        if token in ("cout", "std") and "cout" in (self.value(), self.value(2)):
            return self._parse_cout()

        if token in ("cin", "std") and "cin" in (self.value(), self.value(2)):
            return self._parse_cin()

        if token == "getline" or (token == "std" and self.value(2) == "getline"):
            return self._parse_getline()

        if token == "printf":
            return self._parse_printf()

        if token == "puts":
            self.index += 1
            self.expect("(")
            value = self._parse_value()
            self.expect(")")
            self.expect(";")
            return PrintStatement([value], end="\n")

        if token == "putchar":
            self.index += 1
            self.expect("(")
            value = self._parse_value()
            self.expect(")")
            self.expect(";")
            if not (isinstance(value, Constant) and isinstance(value.value, str)):
                value = FormatString("%c", [value])
            return PrintStatement([value], end="")

        if token == "scanf":
            return self._parse_scanf()

        if token == "struct" and self.peek(1)[0] == "name" and self.peek(2)[0] == "name":
            self.index += 1

        # Declaration?
        if self._looks_like_type():
            return self._parse_declarators(self._parse_type())

        expression = self._parse_expression()
        self.expect(";")
        return self._as_statement(expression)

    def _as_statement(self, expression):

        if isinstance(expression, _Step):
            return AugAssign(expression.target, expression.operator, Constant(1))

        if isinstance(expression, MethodCall) and expression.method == "push_back" \
                and len(expression.args) == 1:
            return ListAppend(expression.obj, expression.args[0])

        target = getattr(expression, "assign_to", None)
        if target is not None:
            # s.pop_back() on a string is s = s[:-1].
            return self._assign(target, expression)

        # reverse(v.begin(), v.end()) reverses the whole container.
        container = self._whole_range(expression, "reverse")
        if container is not None:
            return self._assign(container, FunctionCall("reversed_copy", [container]))

        # std::swap(a, b) exchanges two variables or elements.
        if isinstance(expression, FunctionCall) and expression.name == "swap" and len(expression.args) == 2:
            first, second = expression.args
            self._temp_index += 1
            temp = f"_swap{self._temp_index}"
            return [Variable(temp, "auto", first), self._assign(first, second),
                    self._assign(second, Identifier(temp))]

        # sort(v.begin(), v.end()) sorts the whole container.
        if isinstance(expression, FunctionCall) and expression.name == "sort" and len(expression.args) == 2:
            begin, end = expression.args
            if (isinstance(begin, MethodCall) and begin.method == "begin"
                    and isinstance(end, MethodCall) and end.method == "end"
                    and isinstance(begin.obj, Identifier) and isinstance(end.obj, Identifier)
                    and begin.obj.name == end.obj.name):
                return MethodCall(begin.obj, "sort", [])

        if isinstance(expression, (Identifier, Constant, BinaryOp, BooleanOp)):
            raise UnsupportedConstruct("an expression statement with no effect")

        return expression

    @staticmethod
    def _whole_range(call, name, extra=0):
        """The container c of name(c.begin(), c.end()[, ...]), else None."""

        if not (isinstance(call, FunctionCall) and call.name == name and len(call.args) == 2 + extra):
            return None
        begin, end = call.args[:2]
        if (isinstance(begin, MethodCall) and isinstance(end, MethodCall)
                and (begin.method, end.method) in (("begin", "end"), ("rbegin", "rend"))
                and isinstance(begin.obj, Identifier) and isinstance(end.obj, Identifier)
                and begin.obj.name == end.obj.name):
            return begin.obj
        return None

    @staticmethod
    def _assign(target, value):
        if isinstance(target, Identifier):
            return Variable(target.name, "auto", value)
        return Assignment(target, value)

    def _parse_declarators(self, declared):
        """int n, i = 0, xs[10];  ->  one Variable per name."""

        if declared is None or self.peek()[0] != "name":
            raise UnsupportedConstruct(f"unexpected '{self.value()}' in a declaration")

        declarations = []

        while True:

            name = self.next()[1]
            element_type = declared
            dimensions = []

            while self.accept("["):
                dimensions.append(None if self.value() == "]" else self._parse_value())
                self.expect("]")
                element_type = f"List<{self._box(element_type)}>"

            value = None
            if self.accept("="):
                value = self._parse_initializer()
            elif self.value() == "(":
                value = self._constructor_arguments(declared)
            elif dimensions and all(d is not None for d in dimensions):
                value = FunctionCall("range_array", dimensions)
                value.element_type = declared
            elif declared in self.records:
                # A struct variable is a value that already exists in C.
                value = ObjectCreation(declared, [])
            elif not dimensions and getattr(self, "last_base_type", None) in ("string", "vector", "set") \
                    and declared == self._declared_container(declared):
                # std::string s; and std::vector<int> v; start out empty.
                value = Constant("") if declared == "String" else \
                    (SetLiteral() if declared.startswith("Set<") else ArrayLiteral())

            if dimensions and None in dimensions and not isinstance(value, ArrayLiteral):
                if not (declared == "char" and isinstance(value, Constant)):
                    raise UnsupportedConstruct("an array of unspecified size")

            if declared == "char" and len(dimensions) == 1 and not isinstance(value, ArrayLiteral):
                # A char buffer holds a C string: char word[100]; scanf("%s", word);
                element_type = "String"
                if isinstance(value, FunctionCall) and value.name == "range_array":
                    value = None
                self.c_strings.add(name)

            if declared in self.records and isinstance(value, Identifier):
                # C copies the struct; a Python or Java assignment would alias it.
                raise UnsupportedConstruct("copying a struct by assignment")

            self.var_types[name] = element_type
            declarations.append(Variable(name, element_type, value))

            if not self.accept(","):
                break

        self.expect(";")
        return declarations[0] if len(declarations) == 1 else declarations

    @staticmethod
    def _declared_container(declared):
        """declared itself when it is a std::string, vector or set type, else None."""
        if declared == "String" or declared.startswith(("List<", "Set<")):
            return declared
        return None

    def _constructor_arguments(self, declared):
        """vector<int> v(n);  Account a(100);"""

        self.expect("(")
        args = self._call_arguments()
        self.expect(")")
        if declared in ("String", ) or declared.startswith("List<"):
            # string r(s.rbegin(), s.rend()); is a reversed copy.
            reversed_copy = self._call("string", args)
            if isinstance(reversed_copy, FunctionCall) and reversed_copy.name == "reversed_copy":
                return reversed_copy
        if declared.startswith("List<"):
            if len(args) != 1:
                raise UnsupportedConstruct("vector constructors other than vector<T>(n)")
            value = FunctionCall("range_array", args)
            value.element_type = {"Integer": "int", "Long": "long", "Double": "double",
                                  "Boolean": "boolean"}.get(declared[5:-1], "Object")
            return value
        return ObjectCreation(declared, args)

    def _parse_initializer(self):

        if self.accept("{"):
            elements = []
            while not self.at_end() and self.value() != "}":
                if self.accept(","):
                    continue
                elements.append(self._parse_initializer())
            self.expect("}")
            return ArrayLiteral(elements)

        return self._parse_value()

    def _parse_if(self):

        self.index += 1
        self.expect("(")
        condition = self._parse_value()
        self.expect(")")

        body = self._parse_block()
        else_body = []

        if self.accept("else"):
            if self.value() == "if":
                else_body = [self._parse_if()]
            else:
                else_body = self._parse_block()

        return IfStatement(condition, body, else_body)

    def _parse_for(self):

        self.index += 1
        self.expect("(")

        # Range-for: for (auto x : items)
        start = self.index
        if self._looks_like_type():
            self._parse_type()
            if self.peek()[0] == "name" and self.value(1) == ":":
                iterator = self.next()[1]
                self.index += 1
                iterable = self._parse_value()
                self.expect(")")
                return ForLoop(iterator, iterable, self._parse_block())
        self.index = start

        init = []
        declared = False
        if not self.accept(";"):
            if self._looks_like_type():
                declared = True
                parsed = self._parse_declarators(self._parse_type())
                init = parsed if isinstance(parsed, list) else [parsed]
            else:
                init = self._comma_statements()
                self.expect(";")

        condition = None if self.value() == ";" else self._parse_value()
        self.expect(";")
        update = [] if self.value() == ")" else self._comma_statements()
        self.expect(")")
        body = self._parse_block()

        return lowering.counting_loop(init, condition, update, body, declared)

    def _comma_statements(self):
        """i = 0, j = n  or  i++, j--  in a for header."""

        statements = [self._as_statement(self._parse_expression())]
        while self.accept(","):
            statements.append(self._as_statement(self._parse_expression()))
        return statements

    def _parse_switch(self):

        self.index += 1
        self.expect("(")
        subject = self._parse_value()
        self.expect(")")
        self.expect("{")

        cases = []
        while not self.at_end() and self.value() != "}":
            if self.accept("case"):
                label = self._parse_value()
                self.expect(":")
            elif self.accept("default"):
                label = None
                self.expect(":")
            else:
                raise SyntaxError(f"expected case or default, found {self.value()!r}")

            statements = []
            while not self.at_end() and self.value() not in ("case", "default", "}"):
                statement = self._parse_statement()
                if isinstance(statement, list):
                    statements.extend(s for s in statement if s is not None)
                elif statement is not None:
                    statements.append(statement)
            cases.append((label, statements))

        self.expect("}")
        self._temp_index += 1
        return lowering.switch(subject, cases, f"_switch{self._temp_index}")

    def _parse_cout(self):

        self._skip_namespace()
        self.index += 1  # cout

        parts = []
        width = None
        while self.accept("<<"):
            self._skip_namespace()
            if self.value() == "endl":
                self.index += 1
                parts.append(Constant("\n"))
                continue
            if self.value() == "flush":
                self.index += 1
                continue
            if self.value() in STREAM_MANIPULATORS:
                width = self._manipulator(width)
                continue
            item = self._parse_binary(ABOVE_SHIFT)
            if not isinstance(item, Constant):
                self.cout_in.add(self.current_function)
            state = self.stream
            if width is not None or state["fixed"] or state["precision"] is not None or state["left"]:
                # The annotator picks the conversion once the item's type is known.
                formatted = FormatString("", [item])
                formatted.stream = (state["fixed"], state["precision"], width, state["left"])
                item, width = formatted, None
            parts.append(item)

        self.expect(";")
        return PrintStatement(parts, end="", sep="")

    def _manipulator(self, width):
        """Apply one stream manipulator; returns the width for the next item."""

        name = self.next()[1]
        if name not in STICKY_MANIPULATORS and name != "setw":
            raise UnsupportedConstruct(f"the stream manipulator {name}")
        argument = None
        if name in ("setw", "setprecision"):
            self.expect("(")
            value = self._parse_value()
            self.expect(")")
            if not (isinstance(value, Constant) and isinstance(value.value, int)):
                raise UnsupportedConstruct(f"{name} with a computed argument")
            argument = value.value
        if name == "setw":
            return argument
        if self.block_depth > 1:
            # Inside a branch or loop the state after it depends on the path taken.
            raise UnsupportedConstruct(f"the stream manipulator {name} inside a branch or loop")
        self.sticky_in.add(self.current_function)
        if name == "fixed":
            self.stream["fixed"] = True
        elif name == "setprecision":
            self.stream["precision"] = argument
        else:
            self.stream["left"] = name == "left"
        return width

    def _parse_cin(self):
        """cin >> a >> b  ->  one read per target."""

        self._skip_namespace()
        self.index += 1  # cin

        reads = []
        while self.accept(">>"):
            target = self._parse_postfix()
            # The type comes from the variable's declaration; the annotator fills it.
            reads.append(Assignment(target, Input(None, None)))

        self.expect(";")

        return reads or None

    def _parse_getline(self):
        """getline(cin, line)  ->  a whole-line read."""

        self._skip_namespace()
        self.index += 1
        self.expect("(")
        self._skip_namespace()
        if not self.accept("cin"):
            raise UnsupportedConstruct("getline from anything but cin")
        self.expect(",")
        target = self._parse_postfix()
        self.expect(")")
        self.expect(";")
        return Assignment(target, Input(None, "String"))

    def _parse_scanf(self):
        """scanf("%d %d", &a, &b)  ->  one typed read per target."""

        self.index += 1
        self.expect("(")

        arguments = []
        while not self.at_end() and self.value() != ")":
            if self.accept(","):
                continue
            self.accept("&")
            arguments.append(self._parse_value())

        self.expect(")")
        self.expect(";")

        if not arguments or not isinstance(arguments[0], Constant) or not isinstance(arguments[0].value, str):
            raise UnsupportedConstruct("scanf with a computed format string")

        specs = [t for t in format_tokens(arguments[0].value) if isinstance(t, dict) and t["conv"] != "%"]
        targets = arguments[1:]
        if len(specs) != len(targets):
            raise UnsupportedConstruct("scanf whose format does not match its arguments")

        reads = []
        for spec, target in zip(specs, targets):
            # %99s only bounds the buffer; the word read is the same.
            if (spec["width"] and spec["conv"] != "s") or spec["conv"] not in SCANF_TYPES:
                raise UnsupportedConstruct(f"scanf conversion {spec['raw']}")
            kind = SCANF_TYPES[spec["conv"]]
            if kind == "int" and spec["length"] in ("l", "ll"):
                kind = "long"
            reads.append(Assignment(target, Input(None, kind)))

        return reads

    def _parse_printf(self):

        self.index += 1
        self.expect("(")
        args = self._call_arguments()
        self.expect(")")
        self.expect(";")

        if not args or not isinstance(args[0], Constant) or not isinstance(args[0].value, str):
            raise UnsupportedConstruct("printf with a computed format string")
        if value_count(args[0].value) != len(args) - 1:
            raise UnsupportedConstruct("printf whose format does not match its arguments")

        return PrintStatement([FormatString(args[0].value, args[1:])], end="")

    # ------------------------------------------------------------
    # EXPRESSIONS
    # ------------------------------------------------------------

    def _parse_expression(self):
        """An expression that may assign (statement level only)."""

        left = self._parse_value()

        if (self.value() == "=" or self.value() in COMPOUND_NAMES) and getattr(left, "c_string", False):
            # Python and Java strings cannot be changed in place.
            raise UnsupportedConstruct("writing into a C string")

        if self.value() == "=":
            self.index += 1
            right = self._parse_value()
            if self.value() in ("=",) or self.value() in COMPOUND_NAMES:
                raise UnsupportedConstruct("chained assignment")
            if isinstance(left, Identifier):
                return Variable(left.name, "auto", right)
            return Assignment(left, right)

        if self.value() in COMPOUND_NAMES:
            operator = COMPOUND_NAMES[self.next()[1]]
            right = self._parse_value()
            return AugAssign(left, operator, right)

        return left

    def _parse_value(self):
        """An expression that only produces a value: ternaries and below."""

        condition = self._parse_binary(0)

        if self.accept("?"):
            if_true = self._parse_value()
            self.expect(":")
            if_false = self._parse_value()
            return TernaryOp(condition, if_true, if_false)

        return condition

    def _parse_binary(self, level):

        if level >= len(BINARY_PRECEDENCE):
            return self._parse_unary()

        left = self._parse_binary(level + 1)
        operators, logical = BINARY_PRECEDENCE[level]

        while self.value() in operators and self.peek()[0] in ("op", "punct"):
            symbol = self.next()[1]
            right = self._parse_binary(level + 1)

            if logical:
                left = BooleanOp(left, logical, right)
            elif symbol in COMPARISON_NAMES:
                left = BooleanOp(left, COMPARISON_NAMES[symbol], right)
            else:
                left = BinaryOp(left, ARITHMETIC_NAMES[symbol], right)

        return left

    def _parse_unary(self):

        if self.value() in ("-", "!", "~", "+") and self.peek()[0] == "punct":
            operator = {"-": "USub", "+": "UAdd", "!": "Not", "~": "Invert"}[self.next()[1]]
            return UnaryOp(operator, self._parse_unary())

        if self.value() in ("++", "--"):
            operator = "Add" if self.next()[1] == "++" else "Sub"
            return _Step(self._parse_unary(), operator)

        if self.value() == "&" and self.peek()[0] == "punct" and self.peek(1)[0] == "name" \
                and self.var_types.get(self.value(1)) in self.records:
            # &account passes the struct itself, which a reference already is.
            self.index += 1
            return self._parse_postfix()

        if self.value() == "*" and self.peek()[0] == "punct":
            # *max_element(v.begin(), v.end()) is the largest element of v.
            start = self.index
            self.index += 1
            self._skip_namespace()
            if self.value() in ("max_element", "min_element") and self.value(1) == "(":
                call = self._parse_postfix()
                if (isinstance(call, FunctionCall) and len(call.args) == 2
                        and all(isinstance(a, MethodCall) and isinstance(a.obj, Identifier) for a in call.args)
                        and [a.method for a in call.args] == ["begin", "end"]
                        and call.args[0].obj.name == call.args[1].obj.name):
                    return FunctionCall(call.name[:3], [call.args[0].obj])
            self.index = start

        if self.value() in ("*", "&") and self.peek()[0] == "punct":
            raise UnsupportedConstruct("pointer dereference and address-of")

        if self.value() == "sizeof":
            raise UnsupportedConstruct("sizeof")

        if self.value() == "(" and self._looks_like_cast():
            self.index += 1
            cast = self._parse_type()
            self.expect(")")
            target = CASTS.get(cast)
            if target is None:
                raise UnsupportedConstruct(f"cast to {cast}")
            return TypeCast(target, self._parse_unary())

        return self._parse_postfix()

    def _looks_like_cast(self):
        kind, text = self.peek(1)
        if kind != "name":
            return False
        if text in PRIMITIVE_WORDS or text in ("const", "string") or text in self.records:
            # (int) x, but not (n) * 2 for a variable n.
            position = 1
            while self.peek(position)[0] == "name" or self.value(position) in ("*", "&", "::"):
                position += 1
            return self.value(position) == ")"
        return False

    def _call_arguments(self):
        args = []
        while not self.at_end() and self.value() != ")":
            if self.accept(","):
                continue
            args.append(self._parse_value())
        return args

    def _parse_postfix(self):

        node = self._parse_primary()

        while not self.at_end():

            if self.accept("("):
                args = self._call_arguments()
                self.expect(")")
                if isinstance(node, Identifier):
                    node = self._call(node.name, args)
                elif isinstance(node, AttributeAccess):
                    node = self._method(node.obj, node.attribute, args)
                else:
                    raise UnsupportedConstruct("calling the result of an expression")
                continue

            if self.accept("["):
                index = self._parse_value()
                self.expect("]")
                node = IndexAccess(node, index)
                if isinstance(node.obj, Identifier) and node.obj.name in self.c_strings:
                    # Past the last character a C string reads as '\0'.
                    node.c_string = True
                continue

            if self.value() in (".", "->"):
                self.index += 1
                member = self.next()[1]
                node = AttributeAccess(node, member)
                continue

            if self.value() in ("++", "--"):
                operator = "Add" if self.next()[1] == "++" else "Sub"
                node = _Step(node, operator)
                continue

            break

        return node

    def _method(self, obj, member, args):
        if member in ("length", "size") and not args:
            return MethodCall(obj, "size", [])
        if member == "c_str" and not args:
            return obj
        if member == "empty" and not args:
            return BooleanOp(MethodCall(obj, "size", []), "Eq", Constant(0))
        if member == "at" and len(args) == 1:
            return IndexAccess(obj, args[0])
        if member == "substr" and len(args) in (1, 2):
            end = BinaryOp(args[0], "Add", args[1]) if len(args) == 2 else Constant(None)
            return FunctionCall("slice", [obj, args[0], end])
        if member == "back" and not args:
            return IndexAccess(obj, BinaryOp(MethodCall(obj, "size", []), "Sub", Constant(1)))
        if member == "front" and not args:
            return IndexAccess(obj, Constant(0))
        if member == "pop_back" and not args:
            if isinstance(obj, Identifier) and self.var_types.get(obj.name) == "String":
                shortened = FunctionCall("slice", [obj, Constant(0), Constant(-1)])
                shortened.assign_to = obj
                return shortened
            return MethodCall(obj, "pop", [])
        return MethodCall(obj, member, args)

    def _call(self, name, args):
        """A call by name, with C and C++ library idioms lowered."""

        if name in CONVERSIONS and len(args) == 1:
            return TypeCast(CONVERSIONS[name], args[0])
        if name == "to_string" and len(args) == 1:
            # to_string(2.5) is "2.500000": the conversion depends on the type.
            text = FormatString("", args)
            text.to_string = True
            return text
        if name == "fabs" and len(args) == 1:
            return FunctionCall("abs", args)
        if name == "round" and len(args) == 1:
            return FunctionCall("round_away", args)
        if name in ("lround", "llround") and len(args) == 1:
            return TypeCast("long", FunctionCall("round_away", args))
        call = FunctionCall(name, args)
        if name in ("string", "vector"):
            container = self._whole_range(call, name)
            if container is not None and args[0].method == "rbegin":
                return FunctionCall("reversed_copy", [container])
        container = self._whole_range(call, "count", extra=1)
        if container is not None:
            return MethodCall(container, "count", [args[2]])
        return call

    def _parse_primary(self):

        kind, text = self.peek()

        if text == "(" and kind == "punct":
            self.index += 1
            inner = self._parse_value()
            self.expect(")")
            return inner

        if text == "new" and kind == "name":
            self.index += 1
            class_name = self.next()[1]
            if self.value() == "[":
                raise UnsupportedConstruct("new[] arrays")
            args = []
            if self.accept("("):
                args = self._call_arguments()
                self.expect(")")
            return ObjectCreation(class_name, args)

        if kind == "number":
            self.index += 1
            return Constant(self._number(text))

        if kind == "string":
            self.index += 1
            value = self._unescape(text[1:-1])
            # "a" "b" is one literal in C.
            while self.peek()[0] == "string":
                value += self._unescape(self.next()[1][1:-1])
            return Constant(value)

        if kind == "char":
            self.index += 1
            node = Constant(self._unescape(text[1:-1]))
            node.is_char = True
            return node

        if kind == "name":
            if text in CONTROL_KEYWORDS and text not in ("new",):
                raise UnsupportedConstruct(f"'{text}' inside an expression")
            if text in ("reinterpret_cast", "const_cast", "dynamic_cast"):
                raise UnsupportedConstruct(text)
            if text == "static_cast" and self.value(1) == "<":
                self.index += 2
                cast = self._parse_type()
                self.expect(">")
                self.expect("(")
                value = self._parse_value()
                self.expect(")")
                if CASTS.get(cast) is None:
                    raise UnsupportedConstruct(f"static_cast to {cast}")
                return TypeCast(CASTS[cast], value)
            self.index += 1
            if text in LIMITS:
                return Constant(LIMITS[text])
            if text == "strlen" and self.value() == "(":
                self.index += 1
                value = self._parse_value()
                self.expect(")")
                return MethodCall(value, "size", [])
            if text == "true":
                return Constant(True)
            if text == "false":
                return Constant(False)
            if text in ("NULL", "nullptr"):
                return Constant(None)
            if text == "this":
                return SelfRef()
            while self.accept("::"):
                text = self.next()[1]
            if text == "npos":
                # find() reports absence as npos; the IR's find returns -1.
                return Constant(-1)
            return Identifier(text)

        raise UnsupportedConstruct(f"unexpected '{text}' in an expression")

    @staticmethod
    def _number(text):
        lowered = text.lower()
        if lowered.startswith("0x"):
            return int(lowered.rstrip("ul"), 16)
        if any(c in lowered for c in ".e"):
            return float(lowered.rstrip("fl"))
        digits = lowered.rstrip("ul")
        if len(digits) > 1 and digits.startswith("0"):
            return int(digits, 8)
        return int(digits)

    @staticmethod
    def _unescape(text):
        escapes = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\",
                   "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
        out = []
        index = 0
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                out.append(escapes.get(text[index + 1], text[index + 1]))
                index += 2
                continue
            out.append(char)
            index += 1
        return "".join(out)
