"""Recursive-descent parser for the C/C++ subset this system targets.

The existing regex parsers slice source into raw text chunks, which is enough
for C<->C++ text rewriting but produces no usable IR for C -> Python/Java. This
module builds a real IR so those directions generate meaningful code.

It deliberately covers the common procedural subset — functions, structs and
simple classes, declarations, control flow, calls and expressions — rather than
the whole language.
"""

import re

from cross_language_system.core.ir_nodes import *


TYPE_KEYWORDS = {
    "void", "int", "long", "short", "char", "float", "double", "bool",
    "unsigned", "signed", "string", "auto", "size_t", "const", "static",
}

CONTROL_KEYWORDS = {
    "if", "else", "for", "while", "do", "return", "break", "continue",
    "switch", "case", "default", "struct", "class", "public", "private",
    "protected", "new", "delete", "try", "catch", "throw",
}

TOKEN_RE = re.compile(r"""
      (?P<comment>//[^\n]*|/\*.*?\*/)
    | (?P<preproc>\#[^\n]*)
    | (?P<string>"(?:\\.|[^"\\])*")
    | (?P<char>'(?:\\.|[^'\\])')
    | (?P<number>\d+\.\d+|\.\d+|\d+)
    | (?P<name>[A-Za-z_]\w*)
    | (?P<op><<=|>>=|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|::)
    | (?P<punct>[{}()\[\];,.<>+\-*/%=!&|^~?:])
    | (?P<ws>\s+)
""", re.VERBOSE | re.DOTALL)


BINARY_PRECEDENCE = [
    (["||"], "Or"),
    (["&&"], "And"),
    (["==", "!="], None),
    (["<", ">", "<=", ">="], None),
    (["+", "-"], None),
    (["*", "/", "%"], None),
]

COMPARISON_NAMES = {
    "==": "Eq", "!=": "NotEq", "<": "Lt", ">": "Gt", "<=": "LtE", ">=": "GtE",
}

ARITHMETIC_NAMES = {
    "+": "Add", "-": "Sub", "*": "Mult", "/": "Div", "%": "Mod",
    "&": "BitAnd", "|": "BitOr", "^": "BitXor", "<<": "LShift", ">>": "RShift",
}

TYPE_TO_IR = {
    "int": "int", "long": "int", "short": "int", "size_t": "int",
    "float": "double", "double": "double",
    "bool": "boolean",
    "char*": "String", "string": "String", "std::string": "String",
    "void": "void",
}


def tokenize(code):

    tokens = []
    position = 0

    while position < len(code):
        match = TOKEN_RE.match(code, position)
        if not match:
            position += 1
            continue
        position = match.end()
        kind = match.lastgroup
        if kind in ("ws", "comment", "preproc"):
            continue
        tokens.append((kind, match.group()))

    tokens.append(("eof", ""))
    return tokens


class CLikeParser:

    def __init__(self):
        self.tokens = []
        self.index = 0

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
        if self.value() == text:
            self.index += 1
            return True
        return False

    def expect(self, text):
        if not self.accept(text):
            raise SyntaxError(f"expected {text!r}, found {self.value()!r}")

    def at_end(self):
        return self.peek()[0] == "eof"

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

            if self.value() in ("using", "namespace", "typedef"):
                self._skip_to_semicolon()
                continue

            if self.value() in ("struct", "class"):
                parsed = self._parse_record()
                if parsed:
                    body.append(parsed)
                continue

            declaration = self._parse_top_level_declaration()
            if declaration is not None:
                body.append(declaration)
            elif not self.at_end():
                self.index += 1

        return Program(body)

    def _skip_to_semicolon(self):
        depth = 0
        while not self.at_end():
            token = self.value()
            if token in "{([":
                depth += 1
            elif token in "})]":
                depth -= 1
            self.index += 1
            if token == ";" and depth <= 0:
                return

    # ------------------------------------------------------------
    # TYPES
    # ------------------------------------------------------------

    def _looks_like_type(self, offset=0):
        kind, text = self.peek(offset)
        if text in TYPE_KEYWORDS:
            return True
        # A user type is an identifier followed by another identifier or a star.
        return (
            kind == "name"
            and text not in CONTROL_KEYWORDS
            and (self.peek(offset + 1)[0] == "name" or self.value(offset + 1) in ("*", "<"))
        )

    def _parse_type(self):

        parts = []

        while self.value() in ("const", "static", "unsigned", "signed"):
            self.index += 1

        if self.peek()[0] != "name":
            return None

        parts.append(self.next()[1])

        while self.accept("::"):
            parts.append(self.next()[1])

        name = "::".join(parts)

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
                elif depth:
                    inner.append(token)
                self.index += 1
            element = self._to_ir_type("".join(inner) or "int")
            container = "Set" if name.endswith("set") else "List"
            return f"{container}<{self._box(element)}>"

        pointer = False
        while self.value() in ("*", "&"):
            pointer = pointer or self.value() == "*"
            self.index += 1

        if pointer and name == "char":
            return "String"
        if pointer:
            return f"List<{self._box(self._to_ir_type(name))}>"

        return self._to_ir_type(name)

    @staticmethod
    def _to_ir_type(name):
        return TYPE_TO_IR.get(name, name)

    @staticmethod
    def _box(name):
        return {"int": "Integer", "double": "Double", "boolean": "Boolean"}.get(name, name)

    # ------------------------------------------------------------
    # DECLARATIONS
    # ------------------------------------------------------------

    def _parse_top_level_declaration(self):

        start = self.index
        declared = self._parse_type()

        if declared is None or self.peek()[0] != "name":
            self.index = start
            return None

        name = self.next()[1]

        if self.value() == "(":
            return self._parse_function(declared, name)

        # Global variable
        if self.value() == "=":
            self.index += 1
            value = self._parse_expression()
            self.accept(";")
            return Variable(name, declared, value)

        self._skip_to_semicolon()
        return Variable(name, declared, None)

    def _parse_function(self, return_type, name, owner=None):

        params, param_types = self._parse_parameters()

        # Array parameters carry a companion length in C; drop it on the way in.
        if self.value() == ";":
            self.index += 1
            return None

        body = self._parse_block()

        return Function(
            name,
            params,
            body,
            return_type,
            is_constructor=(owner is not None and name == owner),
            is_static=owner is None,
            param_types=param_types,
            owner=owner,
        )

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

            if self.peek()[0] == "name":
                name = self.next()[1]
                while self.accept("["):
                    self.accept("]")
                    declared = f"List<{self._box(declared)}>"
                params.append(name)
                param_types[name] = declared
            else:
                self.index += 1

        self.accept(")")
        return params, param_types

    def _parse_record(self):
        """struct / class declaration."""

        self.index += 1  # struct | class

        name = self.next()[1] if self.peek()[0] == "name" else "Anonymous"

        base = None
        if self.accept(":"):
            while self.value() in ("public", "private", "protected"):
                self.index += 1
            if self.peek()[0] == "name":
                base = self.next()[1]

        if not self.accept("{"):
            self._skip_to_semicolon()
            return None

        fields = []
        methods = []

        while not self.at_end() and self.value() != "}":

            if self.value() in ("public", "private", "protected"):
                self.index += 1
                self.accept(":")
                continue

            if self.accept(";"):
                continue

            start = self.index

            # Constructor: Name(
            if self.value() == name and self.value(1) == "(":
                self.index += 1
                method = self._parse_function(name, name, owner=name)
                if method:
                    methods.append(method)
                continue

            declared = self._parse_type()

            if declared is None or self.peek()[0] != "name":
                self.index = start + 1
                continue

            member = self.next()[1]

            if self.value() == "(":
                method = self._parse_function(declared, member, owner=name)
                if method:
                    method.is_static = False
                    methods.append(method)
                continue

            value = None
            if self.accept("="):
                value = self._parse_expression()

            fields.append(Field(member, declared, value))
            self._skip_to_semicolon()

        self.accept("}")
        self.accept(";")

        return Class(name, methods, fields, base)

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def _parse_block(self):

        body = []

        if not self.accept("{"):
            statement = self._parse_statement()
            return [statement] if statement else []

        while not self.at_end() and self.value() != "}":
            statement = self._parse_statement()
            if statement is not None:
                body.append(statement)

        self.accept("}")
        return body

    def _parse_statement(self):

        token = self.value()

        if token == ";":
            self.index += 1
            return None

        if token == "{":
            return IfStatement(Constant(True), self._parse_block())

        if token == "return":
            self.index += 1
            if self.accept(";"):
                return Return(None)
            value = self._parse_expression()
            self.accept(";")
            return Return(value)

        if token == "break":
            self.index += 1
            self.accept(";")
            return Break()

        if token == "continue":
            self.index += 1
            self.accept(";")
            return Continue()

        if token == "if":
            return self._parse_if()

        if token == "while":
            self.index += 1
            self.expect("(")
            condition = self._parse_expression()
            self.expect(")")
            return WhileLoop(condition, self._parse_block())

        if token == "for":
            return self._parse_for()

        if token in ("cout", "std") and "cout" in (self.value(), self.value(2)):
            return self._parse_cout()

        if token == "printf":
            return self._parse_printf()

        # Declaration?
        if self._looks_like_type():
            start = self.index
            declaration = self._parse_declaration()
            if declaration is not None:
                return declaration
            self.index = start

        expression = self._parse_expression()
        self.accept(";")

        if isinstance(expression, tuple):
            return expression[0]

        return expression

    def _parse_declaration(self):

        declared = self._parse_type()

        if declared is None or self.peek()[0] != "name":
            return None

        name = self.next()[1]

        # Array declaration: int values[] = {1, 2, 3};
        if self.accept("["):
            while not self.at_end() and self.value() != "]":
                self.index += 1
            self.accept("]")
            declared = f"List<{self._box(declared)}>"

        value = None
        if self.accept("="):
            value = self._parse_initializer()

        self._skip_to_semicolon()
        return Variable(name, declared, value)

    def _parse_initializer(self):

        if self.accept("{"):
            elements = []
            while not self.at_end() and self.value() != "}":
                if self.accept(","):
                    continue
                elements.append(self._parse_expression())
            self.accept("}")
            return ArrayLiteral(elements)

        return self._parse_expression()

    def _parse_if(self):

        self.index += 1
        self.expect("(")
        condition = self._parse_expression()
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
                iterable = self._parse_expression()
                self.expect(")")
                return ForLoop(iterator, iterable, self._parse_block())
        self.index = start

        init = self._parse_statement()
        condition = None if self.value() == ";" else self._parse_expression()
        self.accept(";")
        step = None if self.value() == ")" else self._parse_expression()
        self.expect(")")
        body = self._parse_block()

        # for (int i = start; i < end; i++)  ->  a range loop
        if (
            isinstance(init, Variable)
            and isinstance(condition, BooleanOp)
            and condition.operator in ("Lt", "LtE")
        ):
            end = condition.right
            if condition.operator == "LtE":
                end = BinaryOp(end, "Add", Constant(1))
            return ForLoop(init.name, RangeCall([init.value or Constant(0), end]), body)

        if init is not None:
            body = body + [step] if step is not None else body
            return IfStatement(Constant(True), [init, WhileLoop(condition or Constant(True), body)])

        return WhileLoop(condition or Constant(True), body)

    def _parse_cout(self):

        while self.value() in ("std", "::"):
            self.index += 1
        self.index += 1  # cout

        args = []
        while self.accept("<<"):
            if self.value() in ("endl", "std"):
                while self.value() in ("std", "::"):
                    self.index += 1
                if self.value() == "endl":
                    self.index += 1
                continue
            args.append(self._parse_expression())

        self.accept(";")
        return PrintStatement(args)

    def _parse_printf(self):

        self.index += 1
        self.expect("(")

        args = []
        while not self.at_end() and self.value() != ")":
            if self.accept(","):
                continue
            args.append(self._parse_expression())

        self.accept(")")
        self.accept(";")

        # Drop the format string; keep the values being printed.
        if args and isinstance(args[0], Constant) and isinstance(args[0].value, str):
            literal = re.sub(r"%[-0-9.]*[a-zA-Z]", "", args[0].value).replace("\\n", "").strip()
            remaining = args[1:]
            if literal:
                remaining = [Constant(literal)] + remaining
            args = remaining

        return PrintStatement(args)

    # ------------------------------------------------------------
    # EXPRESSIONS
    # ------------------------------------------------------------

    def _parse_expression(self):
        return self._parse_assignment()

    def _parse_assignment(self):

        left = self._parse_binary(0)

        if self.value() == "=":
            self.index += 1
            right = self._parse_assignment()
            if isinstance(left, Identifier):
                return Variable(left.name, "auto", right)
            return Assignment(left, right)

        compound = {"+=": "Add", "-=": "Sub", "*=": "Mult", "/=": "Div", "%=": "Mod"}
        if self.value() in compound:
            operator = compound[self.next()[1]]
            return AugAssign(left, operator, self._parse_assignment())

        return left

    def _parse_binary(self, level):

        if level >= len(BINARY_PRECEDENCE):
            return self._parse_unary()

        left = self._parse_binary(level + 1)
        operators, logical = BINARY_PRECEDENCE[level]

        while self.value() in operators:
            symbol = self.next()[1]
            right = self._parse_binary(level + 1)

            if logical:
                left = BooleanOp(left, logical, right)
            elif symbol in COMPARISON_NAMES:
                left = BooleanOp(left, COMPARISON_NAMES[symbol], right)
            else:
                left = BinaryOp(left, ARITHMETIC_NAMES.get(symbol, "Add"), right)

        return left

    def _parse_unary(self):

        if self.value() in ("-", "!", "~", "+"):
            operator = {"-": "USub", "+": "UAdd", "!": "Not", "~": "Invert"}[self.next()[1]]
            return UnaryOp(operator, self._parse_unary())

        if self.value() in ("++", "--"):
            self.index += 1
            return self._parse_unary()

        if self.value() == "(" and self._looks_like_type(1):
            start = self.index
            self.index += 1
            cast = self._parse_type()
            if self.accept(")"):
                target = {"int": "int", "double": "float"}.get(cast)
                if target:
                    return TypeCast(target, self._parse_unary())
            self.index = start

        return self._parse_postfix()

    def _parse_postfix(self):

        node = self._parse_primary()

        while not self.at_end():

            if self.accept("("):
                args = []
                while not self.at_end() and self.value() != ")":
                    if self.accept(","):
                        continue
                    args.append(self._parse_expression())
                self.accept(")")
                if isinstance(node, Identifier):
                    node = FunctionCall(node.name, args)
                elif isinstance(node, AttributeAccess):
                    node = MethodCall(node.obj, node.attribute, args)
                continue

            if self.accept("["):
                index = self._parse_expression()
                self.accept("]")
                node = IndexAccess(node, index)
                continue

            if self.value() in (".", "->"):
                self.index += 1
                member = self.next()[1]
                node = AttributeAccess(node, member)
                continue

            if self.value() in ("++", "--"):
                self.index += 1
                continue

            break

        return node

    def _parse_primary(self):

        kind, text = self.peek()

        if text == "(":
            self.index += 1
            inner = self._parse_expression()
            self.accept(")")
            return inner

        if text == "new":
            self.index += 1
            class_name = self.next()[1]
            args = []
            if self.accept("("):
                while not self.at_end() and self.value() != ")":
                    if self.accept(","):
                        continue
                    args.append(self._parse_expression())
                self.accept(")")
            return ObjectCreation(class_name, args)

        if kind == "number":
            self.index += 1
            return Constant(float(text) if "." in text else int(text))

        if kind == "string":
            self.index += 1
            return Constant(self._unescape(text[1:-1]))

        if kind == "char":
            self.index += 1
            return Constant(self._unescape(text[1:-1]))

        if kind == "name":
            self.index += 1
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
            return Identifier(text)

        self.index += 1
        return Constant(None)

    @staticmethod
    def _unescape(text):
        return (
            text.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
