import javalang
from cross_language_system.core.ir_nodes import *


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
}

# Scanner reads map onto the IR's stdin node rather than a generic method call.
SCANNER_READS = {
    "nextInt": "int",
    "nextLong": "int",
    "nextDouble": "double",
    "nextFloat": "double",
    "next": "token",
    "nextLine": "String",
}


class JavaParser:

    def parse(self, code):

        tree = javalang.parse.parse(code)
        body = []

        for _, node in tree:
            if isinstance(node, javalang.tree.ClassDeclaration):
                body.append(self._handle_class(node))

        return Program(body)

    # ---------------- CLASS ----------------

    def _handle_class(self, node):

        fields = []
        for member in node.fields:
            declared = self._type_name(member.type)
            for declarator in member.declarators:
                fields.append(Field(
                    declarator.name,
                    declared,
                    self._handle_expression(declarator.initializer)
                    if declarator.initializer else None,
                ))

        methods = []

        for constructor in getattr(node, "constructors", None) or []:
            methods.append(self._handle_method(constructor, node.name, is_constructor=True))

        for method in node.methods:
            methods.append(self._handle_method(method, node.name))

        base = node.extends.name if node.extends else None

        return Class(node.name, methods, fields, base)

    # ---------------- METHOD ----------------

    def _handle_method(self, node, owner=None, is_constructor=False):

        params = [p.name for p in node.parameters]
        param_types = {p.name: self._type_name(p.type) for p in node.parameters}

        body = []
        if node.body:
            for stmt in node.body:
                self._collect(body, self._handle_statement(stmt))

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

        arguments = getattr(type_node, "arguments", None)
        if arguments:
            inner = ", ".join(
                self._type_name(a.type) if getattr(a, "type", None) else "Object"
                for a in arguments
            )
            return f"{name}<{inner}>"

        if getattr(type_node, "dimensions", None):
            return f"List<{name}>"

        return name

    # ---------------- STATEMENTS ----------------

    @staticmethod
    def _collect(target, parsed):
        """_handle_statement may return several nodes for one declaration."""
        if isinstance(parsed, list):
            target.extend(p for p in parsed if p is not None)
        elif parsed is not None:
            target.append(parsed)

    def _handle_statement(self, stmt):

        # RETURN
        if isinstance(stmt, javalang.tree.ReturnStatement):
            return Return(self._handle_expression(stmt.expression))

        # VARIABLE DECLARATION
        if isinstance(stmt, javalang.tree.LocalVariableDeclaration):

            declared = self._type_name(stmt.type)

            # A Scanner is Java plumbing for stdin; the IR models reads directly.
            if declared == "Scanner":
                return None

            declarations = [
                Variable(
                    d.name,
                    declared,
                    self._handle_expression(d.initializer) if d.initializer else None,
                )
                for d in stmt.declarators
            ]

            return declarations[0] if len(declarations) == 1 else declarations
        # TRY-CATCH
        # TRY-CATCH
        if isinstance(stmt, javalang.tree.TryStatement):

            try_body = []
            for inner_stmt in stmt.block:
                self._collect(try_body, self._handle_statement(inner_stmt))

            catch = stmt.catches[0]
            catch_var = catch.parameter.name
            exception_type = catch.parameter.types[0]

            catch_body = []
            for inner_stmt in catch.block:
                self._collect(catch_body, self._handle_statement(inner_stmt))

            return TryCatch(
                try_body,
                catch_var,
                catch_body,
                exception_type
            )
        # IF
        if isinstance(stmt, javalang.tree.IfStatement):

            condition = self._handle_expression(stmt.condition)

            body = []
            if stmt.then_statement:

                if isinstance(stmt.then_statement, javalang.tree.BlockStatement):
                    for s in stmt.then_statement.statements:
                        self._collect(body, self._handle_statement(s))
                else:
                    self._collect(body, self._handle_statement(stmt.then_statement))

            else_body = []
            if stmt.else_statement:

                if isinstance(stmt.else_statement, javalang.tree.BlockStatement):
                    for s in stmt.else_statement.statements:
                        self._collect(else_body, self._handle_statement(s))
                else:
                    self._collect(else_body, self._handle_statement(stmt.else_statement))

            return IfStatement(condition, body, else_body)

        # FOR LOOP
        if isinstance(stmt, javalang.tree.ForStatement):

            control = stmt.control

            # ---------- Enhanced for ----------
            if isinstance(control, javalang.tree.EnhancedForControl):

                var_name = control.var.declarators[0].name
                iterable = self._handle_expression(control.iterable)

                body = []
                if isinstance(stmt.body, javalang.tree.BlockStatement):
                    for s in stmt.body.statements:
                        self._collect(body, self._handle_statement(s))
                else:
                    self._collect(body, self._handle_statement(stmt.body))

                return ForLoop(var_name, iterable, body)

            # ---------- Traditional for ----------
            if hasattr(control, "init") and control.init:

                init = control.init
                if isinstance(init, list):
                    init = init[0]

                var_decl = init.declarators[0]
                var_name = var_decl.name
                start_expr = self._handle_expression(var_decl.initializer)

                end_expr = self._handle_expression(control.condition.operandr)

                iterable = FunctionCall("range", [start_expr, end_expr])

                body = []
                if isinstance(stmt.body, javalang.tree.BlockStatement):
                    for s in stmt.body.statements:
                        self._collect(body, self._handle_statement(s))
                else:
                    self._collect(body, self._handle_statement(stmt.body))

                return ForLoop(var_name, iterable, body)
    

        if isinstance(stmt, javalang.tree.BreakStatement):
            return Break()

        if isinstance(stmt, javalang.tree.ContinueStatement):
            return Continue()
                    
        # METHOD CALL (like System.out.println)
                # Assignment
        # StatementExpression (assignment or method call)
        if isinstance(stmt, javalang.tree.StatementExpression):

            expr = stmt.expression

            # Assignment: sum = sum + nums.get(i)
            if isinstance(expr, javalang.tree.Assignment):

                left = expr.expressionl
                right = self._handle_expression(expr.value)
                operator = getattr(expr, "type", "=")

                # Handle array index assignment arr[i] = value
                if isinstance(left, javalang.tree.ArraySelector):
                    array_name = left.primary.member
                    index = self._handle_expression(left.index)

                    return MethodCall(
                        array_name,
                        "set_index",
                        [index, right]
                    )

                target = self._handle_expression(left)

                if operator in COMPOUND_OPS:
                    return AugAssign(target, COMPOUND_OPS[operator], right)

                # Writing through this/obj mutates existing state rather than
                # declaring a new local.
                if isinstance(target, AttributeAccess):
                    return Assignment(target, right)

                if isinstance(target, Identifier):
                    return Variable(target.name, "auto", right)

                return Assignment(target, right)

            # Method call: nums.add(5)
            if isinstance(expr, javalang.tree.MethodInvocation):

                if expr.member in ("println", "print") and expr.qualifier in ("System.out", "System.err"):
                    return PrintStatement(
                        [self._handle_expression(a) for a in expr.arguments]
                    )

                if expr.qualifier:
                    return MethodCall(
                        Identifier(expr.qualifier),
                        expr.member,
                        [self._handle_expression(a) for a in expr.arguments]
                    )

                return FunctionCall(
                    expr.member,
                    [self._handle_expression(a) for a in expr.arguments]
                )

            
        # SWITCH
        # SWITCH
        if isinstance(stmt, javalang.tree.SwitchStatement):

            cases = []

            for case in stmt.cases:

                # case value
                value = None
                if case.case:
                    value = self._handle_expression(case.case[0])

                body = []

                for s in case.statements:

                    # Ignore break statements
                    if isinstance(s, javalang.tree.BreakStatement):
                        continue

                    self._collect(body, self._handle_statement(s))

                cases.append(SwitchCase(value, body))

            return SwitchStatement(
                self._handle_expression(stmt.expression),
                cases
            )
        
        if isinstance(stmt, javalang.tree.WhileStatement):

            condition = self._handle_expression(stmt.condition)

            body = []
            if isinstance(stmt.body, javalang.tree.BlockStatement):
                for s in stmt.body.statements:
                    self._collect(body, self._handle_statement(s))
            else:
                self._collect(body, self._handle_statement(stmt.body))

            return WhileLoop(condition, body)

    # ---------------- EXPRESSIONS ----------------

    def _handle_expression(self, expr):

        if expr is None:
            return Constant(None)

        # LITERAL
        if isinstance(expr, javalang.tree.Literal):

            value = expr.value

            if value == "true":
                return Constant(True)

            if value == "false":
                return Constant(False)

            if value == "null":
                return Constant(None)

            if value.startswith('"'):
                return Constant(value.strip('"'))

            if "." in value:
                return Constant(float(value))

            return Constant(int(value))

        # THIS  (this / this.field / this.method())
        if isinstance(expr, javalang.tree.This):

            node = SelfRef()

            for selector in (expr.selectors or []):
                if isinstance(selector, javalang.tree.MemberReference):
                    node = AttributeAccess(node, selector.member)
                elif isinstance(selector, javalang.tree.MethodInvocation):
                    node = MethodCall(
                        node,
                        selector.member,
                        [self._handle_expression(a) for a in selector.arguments],
                    )

            return node

        # IDENTIFIER
        if isinstance(expr, javalang.tree.MemberReference):

            base = (
                AttributeAccess(Identifier(expr.qualifier), expr.member)
                if expr.qualifier
                else Identifier(expr.member)
            )

            return self._apply_prefix(expr, base)

        # BINARY OP
        if isinstance(expr, javalang.tree.BinaryOperation):

            operator = expr.operator
            left = self._handle_expression(expr.operandl)
            right = self._handle_expression(expr.operandr)

            if operator in COMPARISON_OPS:
                return BooleanOp(left, COMPARISON_OPS[operator], right)

            return BinaryOp(left, ARITHMETIC_OPS.get(operator, "Add"), right)

        

        # METHOD CALL
        if isinstance(expr, javalang.tree.MethodInvocation):

            if expr.member in SCANNER_READS:
                return Input(None, SCANNER_READS[expr.member])

            if expr.member == "equals" and expr.qualifier:
                return BooleanOp(
                    Identifier(expr.qualifier),
                    "Eq",
                    self._handle_expression(expr.arguments[0])
                )

            if expr.qualifier:
                return MethodCall(
                    Identifier(expr.qualifier),
                    expr.member,
                    [self._handle_expression(a) for a in expr.arguments]
                )

            return FunctionCall(
                expr.member,
                [self._handle_expression(a) for a in expr.arguments]
            )
        
        # ARRAY CREATION like new int[n]
        if isinstance(expr, javalang.tree.ArrayCreator):
            size = self._handle_expression(expr.dimensions[0])
            return FunctionCall("range_array", [size])


        # Array access arr[i]
        if isinstance(expr, javalang.tree.ArraySelector):
            return IndexAccess(
                Identifier(expr.member),
                self._handle_expression(expr.index)
            )

        # OBJECT CREATION
        if isinstance(expr, javalang.tree.ClassCreator):
            return ObjectCreation(
                expr.type.name,
                [self._handle_expression(a) for a in expr.arguments]
            )

        return Constant(None)

    @staticmethod
    def _apply_prefix(expr, node):
        """Wrap a node in whatever prefix operators javalang attached to it."""

        for operator in reversed(getattr(expr, "prefix_operators", None) or []):
            mapped = {"-": "USub", "+": "UAdd", "!": "Not", "~": "Invert"}.get(operator)
            if mapped:
                node = UnaryOp(mapped, node)

        return node