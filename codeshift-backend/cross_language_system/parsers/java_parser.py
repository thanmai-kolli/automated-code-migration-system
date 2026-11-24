import javalang

from cross_language_system.core import library
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.parsers import lowering


# javalang reports operators as Java symbols; the IR uses neutral names so that
# every generator can share one operator table regardless of source language.
ARITHMETIC_OPS = {
    "+": "Add", "-": "Sub", "*": "Mult", "/": "Div", "%": "Mod",
    "&": "BitAnd", "|": "BitOr", "^": "BitXor", "<<": "LShift", ">>": "RShift",
}

COMPARISON_OPS = {
    "==": "Eq", "!=": "NotEq", "<": "Lt", ">": "Gt",
    "<=": "LtE", ">=": "GtE", "&&": "And", "||": "Or",
}

COMPOUND_OPS = {
    "+=": "Add", "-=": "Sub", "*=": "Mult", "/=": "Div", "%=": "Mod",
    "&=": "BitAnd", "|=": "BitOr", "^=": "BitXor", "<<=": "LShift", ">>=": "RShift",
}

PREFIX_OPS = {"-": "USub", "+": "UAdd", "!": "Not", "~": "Invert"}

# Scanner reads map onto the IR's stdin node rather than a generic method call.
SCANNER_READS = {
    "nextInt": "int",
    "nextLong": "long",
    "nextDouble": "double",
    "nextFloat": "double",
    "next": "token",
    "nextLine": "String",
}

# Math.<name> calls every target can express under the same name.
MATH_FUNCTIONS = {"abs", "max", "min"} | set(library.MATH_NAMES)

# Classes that build a string in place; the IR models them as an immutable
# string that each update reassigns.
STRING_BUILDERS = ("StringBuilder", "StringBuffer")

# Character.<name> tests, under their C names.
CHARACTER_FUNCTIONS = {
    "isUpperCase": "isupper", "isLowerCase": "islower", "isDigit": "isdigit",
    "isLetter": "isalpha", "isWhitespace": "isspace", "isLetterOrDigit": "isalnum",
    "toUpperCase": "toupper", "toLowerCase": "tolower",
}

CONSTANTS = {
    ("Integer", "MAX_VALUE"): 2**31 - 1, ("Integer", "MIN_VALUE"): -2**31,
    ("Long", "MAX_VALUE"): 2**63 - 1, ("Long", "MIN_VALUE"): -2**63,
    ("Math", "PI"): 3.141592653589793,
}

# Java String methods under the (Python) names the generators expect.
STRING_METHODS = {
    "toLowerCase": "lower", "toUpperCase": "upper", "trim": "strip",
    "startsWith": "startswith", "endsWith": "endswith", "indexOf": "find",
}

PARSE_CALLS = {
    ("Integer", "parseInt"): "int",
    ("Integer", "valueOf"): "int",
    ("Long", "parseLong"): "long",
    ("Double", "parseDouble"): "float",
    ("Double", "valueOf"): "float",
    ("String", "valueOf"): "str",
    ("Integer", "toString"): "str",
    ("Double", "toString"): "str",
    ("Long", "toString"): "str",
}

ELEMENT_TYPES = {"int": "int", "long": "long", "short": "int", "byte": "int",
                 "double": "double", "float": "double", "boolean": "boolean",
                 "char": "char", "String": "String"}


def _refuse(node, what):
    position = getattr(node, "position", None)
    where = f" (line {position.line})" if position else ""
    raise UnsupportedConstruct(f"{what}{where}")


class JavaParser:

    def __init__(self):
        self._temp_index = 0
        # True only while the outermost call chain of an expression statement is
        # parsed: a StringBuilder update is only meaningful there.
        self._statement_level = False
        self._builders = set()  # names declared as StringBuilder or StringBuffer

    def parse(self, code):

        try:
            tree = javalang.parse.parse(code)
        except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError) as exc:
            raise SyntaxError(f"Java source does not parse: {exc}") from None

        body = []

        for _, node in tree:
            if isinstance(node, javalang.tree.ClassDeclaration):
                body.append(self._handle_class(node))
            elif isinstance(node, (javalang.tree.EnumDeclaration, javalang.tree.InterfaceDeclaration)):
                _refuse(node, f"{type(node).__name__[:-11].lower()} declarations")

        return Program(body)

    # ---------------- CLASS ----------------

    def _handle_class(self, node):

        fields = []
        for member in node.fields:
            declared = self._type_name(member.type)
            if declared == "Scanner":
                continue  # stdin plumbing; reads become Input nodes
            if getattr(member.type, "name", None) in STRING_BUILDERS:
                self._builders.update(d.name for d in member.declarators)
            for declarator in member.declarators:
                declared_here = self._with_dimensions(declared, declarator)
                fields.append(Field(
                    declarator.name,
                    declared_here,
                    self._initializer(declarator.initializer, declared_here)
                    if declarator.initializer else None,
                ))

        methods = []

        for constructor in getattr(node, "constructors", None) or []:
            methods.append(self._handle_method(constructor, node.name, is_constructor=True))

        for method in node.methods:
            methods.append(self._handle_method(method, node.name))

        base = node.extends.name if node.extends else None

        record = Class(node.name, methods, fields, base)
        lowering.bind_members(record)
        return record

    # ---------------- METHOD ----------------

    def _handle_method(self, node, owner=None, is_constructor=False):

        params = [p.name for p in node.parameters]
        param_types = {p.name: self._type_name(p.type) for p in node.parameters}

        body = self._block(node.body or [])

        modifiers = getattr(node, "modifiers", None) or set()

        return Function(
            owner if is_constructor else node.name,
            params,
            body,
            self._type_name(getattr(node, "return_type", None)) or "void",
            is_constructor=is_constructor,
            is_static="static" in modifiers or owner is None,
            param_types=param_types,
            owner=owner,
        )

    def _type_name(self, type_node):

        if type_node is None:
            return "void"

        name = getattr(type_node, "name", None)
        if not name:
            return "Object"
        if name in STRING_BUILDERS:
            return "String"

        arguments = getattr(type_node, "arguments", None)
        if arguments:
            inner = ", ".join(
                self._type_name(a.type) if getattr(a, "type", None) else "Object"
                for a in arguments
            )
            name = f"{name}<{inner}>"

        for _ in getattr(type_node, "dimensions", None) or []:
            name = f"List<{self._boxed(name)}>"

        return name

    @staticmethod
    def _boxed(name):
        return {"int": "Integer", "long": "Long", "double": "Double", "float": "Double",
                "boolean": "Boolean", "char": "Character", "short": "Integer",
                "byte": "Integer"}.get(name, name)

    def _with_dimensions(self, declared, declarator):
        for _ in getattr(declarator, "dimensions", None) or []:
            declared = f"List<{self._boxed(declared)}>"
        return declared

    # ---------------- STATEMENTS ----------------

    @staticmethod
    def _collect(target, parsed):
        """_handle_statement may return several nodes for one declaration."""
        if isinstance(parsed, list):
            target.extend(p for p in parsed if p is not None)
        elif parsed is not None:
            target.append(parsed)

    def _block(self, statements):
        body = []
        for s in statements:
            self._collect(body, self._handle_statement(s))
        return body

    def _body_of(self, stmt):
        """Statements of a loop or branch body, braced or not."""
        if stmt is None:
            return []
        if isinstance(stmt, javalang.tree.BlockStatement):
            return self._block(stmt.statements or [])
        body = []
        self._collect(body, self._handle_statement(stmt))
        return body

    def _handle_statement(self, stmt):

        if getattr(stmt, "label", None):
            _refuse(stmt, "labelled statements")

        if isinstance(stmt, javalang.tree.ReturnStatement):
            return Return(self._handle_expression(stmt.expression) if stmt.expression else None)

        if isinstance(stmt, javalang.tree.LocalVariableDeclaration):

            declared = self._type_name(stmt.type)

            # A Scanner is Java plumbing for stdin; the IR models reads directly.
            if declared == "Scanner":
                return None
            if getattr(stmt.type, "name", None) in STRING_BUILDERS:
                self._builders.update(d.name for d in stmt.declarators)

            declarations = []
            for d in stmt.declarators:
                declared_here = self._with_dimensions(declared, d)
                declarations.append(Variable(
                    d.name,
                    declared_here,
                    self._initializer(d.initializer, declared_here) if d.initializer else None,
                ))

            return declarations[0] if len(declarations) == 1 else declarations

        if isinstance(stmt, javalang.tree.TryStatement):

            if stmt.resources or stmt.finally_block or len(stmt.catches or []) != 1:
                _refuse(stmt, "try with resources, finally or several catch clauses")

            catch = stmt.catches[0]
            return TryCatch(
                self._block(stmt.block or []),
                catch.parameter.name,
                self._block(catch.block or []),
                catch.parameter.types[0],
            )

        if isinstance(stmt, javalang.tree.IfStatement):
            return IfStatement(
                self._handle_expression(stmt.condition),
                self._body_of(stmt.then_statement),
                self._body_of(stmt.else_statement),
            )

        if isinstance(stmt, javalang.tree.ForStatement):
            return self._handle_for(stmt)

        if isinstance(stmt, javalang.tree.WhileStatement):
            return WhileLoop(self._handle_expression(stmt.condition), self._body_of(stmt.body))

        if isinstance(stmt, javalang.tree.DoStatement):
            return lowering.do_while(self._body_of(stmt.body), self._handle_expression(stmt.condition))

        if isinstance(stmt, javalang.tree.BlockStatement):
            return Block(self._block(stmt.statements or []))

        if isinstance(stmt, javalang.tree.BreakStatement):
            if stmt.goto:
                _refuse(stmt, "labelled break")
            return Break()

        if isinstance(stmt, javalang.tree.ContinueStatement):
            if stmt.goto:
                _refuse(stmt, "labelled continue")
            return Continue()

        if isinstance(stmt, javalang.tree.SwitchStatement):
            self._temp_index += 1
            cases = []
            for case in stmt.cases:
                statements = self._block(case.statements or [])
                labels = case.case or [None]
                # case 1: case 2: arrive here as one SwitchStatementCase.
                for label in labels[:-1]:
                    cases.append((None if label == "default" else self._handle_expression(label), []))
                last = labels[-1]
                cases.append((None if last in (None, "default") else self._handle_expression(last), statements))
            return lowering.switch(
                self._handle_expression(stmt.expression), cases, f"_switch{self._temp_index}"
            )

        if isinstance(stmt, javalang.tree.StatementExpression):
            return self._handle_statement_expression(stmt.expression)

        if isinstance(stmt, javalang.tree.ClassDeclaration):
            return None  # local classes are collected with the top-level ones

        if type(stmt) is javalang.tree.Statement:
            return None  # the empty statement ;

        if isinstance(stmt, javalang.tree.AssertStatement):
            return None

        _refuse(stmt, f"the Java statement '{type(stmt).__name__}' is not supported")

    def _handle_for(self, stmt):

        control = stmt.control

        if isinstance(control, javalang.tree.EnhancedForControl):
            return ForLoop(
                control.var.declarators[0].name,
                self._handle_expression(control.iterable),
                self._body_of(stmt.body),
            )

        init = []
        declared = False
        if control.init is not None:
            if isinstance(control.init, javalang.tree.VariableDeclaration):
                declared = True
                self._collect(init, self._handle_statement(
                    javalang.tree.LocalVariableDeclaration(
                        type=control.init.type, declarators=control.init.declarators,
                        modifiers=set(), annotations=[],
                    )
                ))
            else:
                for expression in control.init if isinstance(control.init, list) else [control.init]:
                    self._collect(init, self._handle_statement_expression(expression))

        update = []
        for expression in control.update or []:
            self._collect(update, self._handle_statement_expression(expression))

        condition = self._handle_expression(control.condition) if control.condition is not None else None

        return lowering.counting_loop(init, condition, update, self._body_of(stmt.body), declared)

    def _handle_statement_expression(self, expr):

        # i++, ++i, i--, --i as a statement are all just i += 1 / i -= 1.
        step = self._increment(expr)
        if step is not None:
            return step

        if isinstance(expr, javalang.tree.Assignment):

            target = self._handle_expression(expr.expressionl)
            right = self._handle_expression(expr.value)
            operator = expr.type

            if operator in COMPOUND_OPS:
                return AugAssign(target, COMPOUND_OPS[operator], right)
            if operator != "=":
                _refuse(expr, f"the {operator} operator")

            if isinstance(target, Identifier):
                return Variable(target.name, "auto", right)

            return Assignment(target, right)

        if isinstance(expr, javalang.tree.MethodInvocation):

            if expr.qualifier in ("System.out", "System.err") and not expr.selectors:
                if expr.qualifier == "System.err":
                    _refuse(expr, "writing to System.err")
                return self._print(expr)

            self._statement_level = True
            try:
                node = self._handle_expression(expr)
            finally:
                self._statement_level = False
            target = getattr(node, "assign_to", None)
            if target is not None:
                # sb.append(x); is sb = sb + x;
                return Variable(target.name, "auto", node) if isinstance(target, Identifier) \
                    else Assignment(target, node)
            return node

        if isinstance(expr, (javalang.tree.ClassCreator, javalang.tree.This)):
            return self._handle_expression(expr)

        _refuse(expr, "this expression statement")

    def _increment(self, expr):

        prefix = [op for op in (getattr(expr, "prefix_operators", None) or []) if op in ("++", "--")]
        postfix = [op for op in (getattr(expr, "postfix_operators", None) or []) if op in ("++", "--")]
        operators = prefix + postfix

        if not operators:
            return None
        if len(operators) > 1 or len(prefix + postfix) != len(
            (getattr(expr, "prefix_operators", None) or []) + (getattr(expr, "postfix_operators", None) or [])
        ):
            _refuse(expr, "combined increment operators")

        target = self._primary(expr, strip_increments=True)
        return AugAssign(target, "Add" if operators[0] == "++" else "Sub", Constant(1))

    def _print(self, expr):

        args = [self._handle_expression(a) for a in expr.arguments]

        if expr.member == "println":
            return PrintStatement(args[:1], end="\n")
        if expr.member == "print":
            return PrintStatement(args[:1], end="")
        if expr.member in ("printf", "format"):
            if not args or not isinstance(args[0], Constant) or not isinstance(args[0].value, str):
                _refuse(expr, "printf with a computed format string")
            fmt = args[0].value.replace("%n", "\n")
            return PrintStatement([FormatString(fmt, args[1:])], end="")

        _refuse(expr, f"System.out.{expr.member}")

    # ---------------- EXPRESSIONS ----------------

    def _initializer(self, initializer, declared):
        if isinstance(initializer, javalang.tree.ArrayInitializer):
            return ArrayLiteral([self._initializer(i, declared) for i in initializer.initializers or []])
        return self._handle_expression(initializer)

    def _handle_expression(self, expr):

        if expr is None:
            return Constant(None)

        if isinstance(expr, javalang.tree.BinaryOperation):
            node = self._binary(expr)
        elif isinstance(expr, javalang.tree.TernaryExpression):
            node = TernaryOp(
                self._handle_expression(expr.condition),
                self._handle_expression(expr.if_true),
                self._handle_expression(expr.if_false),
            )
        elif isinstance(expr, javalang.tree.Cast):
            node = self._cast(expr)
        elif isinstance(expr, javalang.tree.ArrayInitializer):
            node = ArrayLiteral([self._handle_expression(i) for i in expr.initializers or []])
        elif isinstance(expr, javalang.tree.Assignment):
            _refuse(expr, "assignment inside an expression")
        elif isinstance(expr, (javalang.tree.LambdaExpression, javalang.tree.MethodReference)):
            _refuse(expr, "lambdas and method references")
        elif isinstance(expr, javalang.tree.Primary):
            if self._increment_in(expr):
                _refuse(expr, "++ or -- inside an expression")
            top, self._statement_level = self._statement_level, False
            try:
                node = self._primary(expr)
            finally:
                self._statement_level = top
            if getattr(node, "assign_to", None) is not None and not top:
                _refuse(expr, "using the result of a StringBuilder update inside an expression")
            return self._apply_prefix(expr, node)
        else:
            _refuse(expr, f"the Java expression '{type(expr).__name__}' is not supported")

        return self._apply_prefix(expr, node)

    @staticmethod
    def _increment_in(expr):
        operators = (getattr(expr, "prefix_operators", None) or []) + (getattr(expr, "postfix_operators", None) or [])
        return any(op in ("++", "--") for op in operators)

    def _binary(self, expr):

        operator = expr.operator
        left = self._handle_expression(expr.operandl)
        right = self._handle_expression(expr.operandr)

        if operator in COMPARISON_OPS:
            return BooleanOp(left, COMPARISON_OPS[operator], right)
        if operator in ARITHMETIC_OPS:
            return BinaryOp(left, ARITHMETIC_OPS[operator], right)
        if operator == "instanceof":
            _refuse(expr, "instanceof")
        _refuse(expr, f"the {operator} operator")

    def _cast(self, expr):
        target = self._type_name(expr.type)
        inner = self._handle_expression(expr.expression)
        mapped = {"int": "int", "long": "long", "short": "int", "byte": "int",
                  "double": "float", "float": "float", "char": "char", "String": "str"}.get(target)
        if mapped is None:
            _refuse(expr, f"cast to {target}")
        return TypeCast(mapped, inner)

    def _primary(self, expr, strip_increments=False):
        """Literal, name, call, this or creation, with its selector chain."""

        if isinstance(expr, javalang.tree.Literal):
            node = self._literal(expr)

        elif isinstance(expr, javalang.tree.This):
            node = SelfRef()

        elif isinstance(expr, javalang.tree.MemberReference):
            node = self._member(expr)

        elif isinstance(expr, javalang.tree.MethodInvocation):
            node = self._invocation(expr)

        elif isinstance(expr, javalang.tree.ArrayCreator):
            if expr.initializer is not None:
                node = self._initializer(expr.initializer, None)
            else:
                if any(d is None for d in expr.dimensions):
                    _refuse(expr, "jagged array creation")
                node = FunctionCall("range_array", [self._handle_expression(d) for d in expr.dimensions])
                node.element_type = ELEMENT_TYPES.get(getattr(expr.type, "name", "int"), "Object")

        elif isinstance(expr, javalang.tree.ClassCreator):
            if expr.body:
                _refuse(expr, "anonymous classes")
            arguments = [self._handle_expression(a) for a in expr.arguments or []]
            if expr.type.name in STRING_BUILDERS:
                # new StringBuilder(16) only reserves capacity.
                if not arguments or (isinstance(arguments[0], Constant) and isinstance(arguments[0].value, int)
                                     and not isinstance(arguments[0].value, bool)):
                    node = Constant("")
                else:
                    node = TypeCast("str", arguments[0])
                node.builder = True
            elif expr.type.name in ("ArrayList", "LinkedList", "Vector") and len(arguments) == 1:
                # new ArrayList<>(xs) copies xs; new ArrayList<>(10) only reserves capacity.
                if isinstance(arguments[0], ArrayLiteral):
                    node = arguments[0]
                elif isinstance(arguments[0], Constant) and isinstance(arguments[0].value, int):
                    node = ObjectCreation(expr.type.name, [])
                else:
                    node = FunctionCall("slice", [arguments[0], Constant(None), Constant(None)])
            else:
                node = ObjectCreation(expr.type.name, arguments)

        else:
            _refuse(expr, f"the Java expression '{type(expr).__name__}' is not supported")

        for selector in expr.selectors or []:
            node = self._select(node, selector)

        return node

    def _select(self, node, selector):

        if isinstance(selector, javalang.tree.ArraySelector):
            return IndexAccess(node, self._handle_expression(selector.index))

        if isinstance(selector, javalang.tree.MemberReference):
            if selector.member == "length":
                return MethodCall(node, "size", [])
            return AttributeAccess(node, selector.member)

        if isinstance(selector, javalang.tree.MethodInvocation):
            return self._method(node, selector.member, [self._handle_expression(a) for a in selector.arguments or []])

        _refuse(selector, f"the selector '{type(selector).__name__}'")

    @staticmethod
    def _qualified(qualifier):
        node = None
        for part in qualifier.split("."):
            node = Identifier(part) if node is None else AttributeAccess(node, part)
        return node

    def _member(self, expr):

        if not expr.qualifier:
            return Identifier(expr.member)

        # Array length is a field in Java and a size everywhere else.
        if expr.member == "length":
            return MethodCall(self._qualified(expr.qualifier), "size", [])

        if (expr.qualifier, expr.member) in CONSTANTS:
            return Constant(CONSTANTS[(expr.qualifier, expr.member)])

        return AttributeAccess(self._qualified(expr.qualifier), expr.member)

    def _invocation(self, expr):

        args = [self._handle_expression(a) for a in expr.arguments or []]
        qualifier = expr.qualifier

        if qualifier and expr.member in SCANNER_READS:
            return Input(None, SCANNER_READS[expr.member])

        if qualifier == "Math" and expr.member in MATH_FUNCTIONS:
            return FunctionCall(expr.member, args)

        if qualifier == "Math" and expr.member == "round" and len(args) == 1:
            return FunctionCall("round_half_up", args)

        if qualifier == "Math" and expr.member in ("floorDiv", "floorMod") and len(args) == 2:
            return BinaryOp(args[0], "FloorDiv" if expr.member == "floorDiv" else "FloorMod", args[1])

        if qualifier == "Arrays" and expr.member == "sort" and len(args) == 1:
            return MethodCall(args[0], "sort", [])

        if (qualifier, expr.member) in (("Arrays", "asList"), ("List", "of")):
            return ArrayLiteral(args)

        if qualifier == "Collections" and expr.member == "reverse" and len(args) == 1:
            return self._updated(args[0], FunctionCall("reversed_copy", [args[0]]))

        if qualifier == "Character" and expr.member in CHARACTER_FUNCTIONS and len(args) == 1:
            return FunctionCall(CHARACTER_FUNCTIONS[expr.member], args)

        if qualifier == "Collections" and expr.member in ("min", "max") and len(args) == 1:
            return FunctionCall(expr.member, args)

        if qualifier == "Collections" and expr.member == "sort" and len(args) == 1:
            return MethodCall(args[0], "sort", [])

        if (qualifier, expr.member) in PARSE_CALLS and len(args) == 1:
            return TypeCast(PARSE_CALLS[(qualifier, expr.member)], args[0])

        if qualifier == "String" and expr.member == "format":
            if not args or not isinstance(args[0], Constant) or not isinstance(args[0].value, str):
                _refuse(expr, "String.format with a computed format string")
            return FormatString(args[0].value.replace("%n", "\n"), args[1:])

        if qualifier in ("System.out", "System.err"):
            _refuse(expr, "printing inside an expression")

        if qualifier:
            return self._method(self._qualified(qualifier), expr.member, args)

        return FunctionCall(expr.member, args)

    def _method(self, obj, member, args):

        # Java string and list idioms that have a neutral IR form.
        if member == "equals" and len(args) == 1:
            return BooleanOp(obj, "Eq", args[0])
        if member == "length" and not args:
            return MethodCall(obj, "size", [])
        if member == "charAt" and len(args) == 1:
            return IndexAccess(obj, args[0])
        if member == "contains" and len(args) == 1:
            return BooleanOp(args[0], "In", obj)
        if member == "isEmpty" and not args:
            return BooleanOp(MethodCall(obj, "size", []), "Eq", Constant(0))
        if member == "toCharArray" and not args:
            return obj
        if member == "toString" and not args:
            node = TypeCast("str", obj)
            node.assign_to = getattr(obj, "assign_to", None)
            return node

        builder = self._builder_update(obj, member, args)
        if builder is not None:
            return builder

        if member in STRING_METHODS:
            return MethodCall(obj, STRING_METHODS[member], args)

        return MethodCall(obj, member, args)

    @staticmethod
    def _updated(target, value):
        """value, marked as the new content of target (a name updated in place)."""
        value.assign_to = target if isinstance(target, (Identifier, AttributeAccess)) else None
        return value

    def _builder_update(self, obj, member, args):
        """StringBuilder updates as a new string value; None for other calls."""

        root = obj.attribute if isinstance(obj, AttributeAccess) else getattr(obj, "name", None)
        if not (getattr(obj, "builder", False) or getattr(obj, "assign_to", None) is not None
                or (isinstance(obj, (Identifier, AttributeAccess)) and root in self._builders)):
            return None
        target = getattr(obj, "assign_to", None) or obj

        def slice_of(start, end=None):
            return FunctionCall("slice", [obj, start, end if end is not None else Constant(None)])

        if member == "append" and len(args) == 1:
            value = BinaryOp(obj, "Add", args[0])
        elif member == "reverse" and not args:
            value = FunctionCall("reversed_copy", [obj])
        elif member == "insert" and len(args) == 2:
            if isinstance(args[0], Constant) and args[0].value == 0:
                value = BinaryOp(TypeCast("str", args[1]), "Add", obj)
            else:
                value = BinaryOp(BinaryOp(slice_of(Constant(0), args[0]), "Add", args[1]), "Add",
                                 slice_of(args[0]))
        elif member == "setLength" and len(args) == 1:
            value = Constant("") if isinstance(args[0], Constant) and args[0].value == 0 \
                else slice_of(Constant(0), args[0])
        elif member == "deleteCharAt" and len(args) == 1:
            value = BinaryOp(slice_of(Constant(0), args[0]), "Add", slice_of(BinaryOp(args[0], "Add", Constant(1))))
        elif member == "setCharAt" and len(args) == 2:
            value = BinaryOp(BinaryOp(slice_of(Constant(0), args[0]), "Add", args[1]), "Add",
                             slice_of(BinaryOp(args[0], "Add", Constant(1))))
        else:
            return None
        value.builder = True
        return self._updated(target, value)

    def _literal(self, expr):

        value = expr.value

        if value == "true":
            return Constant(True)
        if value == "false":
            return Constant(False)
        if value == "null":
            return Constant(None)
        if value.startswith('"'):
            return Constant(self._unescape(value[1:-1]))
        if value.startswith("'"):
            node = Constant(self._unescape(value[1:-1]))
            node.is_char = True
            return node

        text = value.replace("_", "")
        lowered = text.lower()
        try:
            if lowered.startswith(("0x", "0b")):
                return Constant(int(lowered.rstrip("l"), 0))
            if any(c in lowered for c in ".e") and not lowered.startswith("0x") or lowered.endswith(("f", "d")):
                return Constant(float(lowered.rstrip("fd")))
            digits = lowered.rstrip("l")
            if len(digits) > 1 and digits.startswith("0"):
                return Constant(int(digits, 8))
            return Constant(int(digits))
        except ValueError:
            _refuse(expr, f"the literal {value}")

    @staticmethod
    def _unescape(text):
        out = []
        index = 0
        escapes = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
                   "0": "\0", "\\": "\\", "'": "'", '"': '"'}
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                following = text[index + 1]
                if following == "u" and index + 5 < len(text):
                    out.append(chr(int(text[index + 2:index + 6], 16)))
                    index += 6
                    continue
                out.append(escapes.get(following, following))
                index += 2
                continue
            out.append(char)
            index += 1
        return "".join(out)

    @staticmethod
    def _apply_prefix(expr, node):
        """Wrap a node in whatever prefix operators javalang attached to it."""

        for operator in reversed(getattr(expr, "prefix_operators", None) or []):
            if operator in ("++", "--"):
                continue  # handled (or refused) by the caller
            node = UnaryOp(PREFIX_OPS[operator], node)

        return node
