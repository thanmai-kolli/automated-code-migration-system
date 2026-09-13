import javalang
from core.ir_nodes import *


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

        methods = []

        for method in node.methods:
            methods.append(self._handle_method(method))

        return Class(node.name, methods)

    # ---------------- METHOD ----------------

    def _handle_method(self, node):

        params = [p.name for p in node.parameters]
        body = []

        if node.body:
            for stmt in node.body:
                parsed = self._handle_statement(stmt)
                if parsed:
                    body.append(parsed)

        return Function(
            node.name,
            params,
            body,
            node.return_type.name if node.return_type else "void"
        )

    # ---------------- STATEMENTS ----------------

    def _handle_statement(self, stmt):

        # RETURN
        if isinstance(stmt, javalang.tree.ReturnStatement):
            return Return(self._handle_expression(stmt.expression))

        # VARIABLE DECLARATION
        if isinstance(stmt, javalang.tree.LocalVariableDeclaration):
            decl = stmt.declarators[0]
            return Variable(
                decl.name,
                "auto",
                self._handle_expression(decl.initializer)
            )
        # TRY-CATCH
        # TRY-CATCH
        if isinstance(stmt, javalang.tree.TryStatement):

            try_body = []
            for inner_stmt in stmt.block:
                parsed = self._handle_statement(inner_stmt)
                if parsed:
                    try_body.append(parsed)

            catch = stmt.catches[0]
            catch_var = catch.parameter.name
            exception_type = catch.parameter.types[0]

            catch_body = []
            for inner_stmt in catch.block:
                parsed = self._handle_statement(inner_stmt)
                if parsed:
                    catch_body.append(parsed)

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
                        parsed = self._handle_statement(s)
                        if parsed:
                            body.append(parsed)
                else:
                    parsed = self._handle_statement(stmt.then_statement)
                    if parsed:
                        body.append(parsed)

            else_body = []
            if stmt.else_statement:

                if isinstance(stmt.else_statement, javalang.tree.BlockStatement):
                    for s in stmt.else_statement.statements:
                        parsed = self._handle_statement(s)
                        if parsed:
                            else_body.append(parsed)
                else:
                    parsed = self._handle_statement(stmt.else_statement)
                    if parsed:
                        else_body.append(parsed)

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
                        parsed = self._handle_statement(s)
                        if parsed:
                            body.append(parsed)
                else:
                    parsed = self._handle_statement(stmt.body)
                    if parsed:
                        body.append(parsed)

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
                        parsed = self._handle_statement(s)
                        if parsed:
                            body.append(parsed)
                else:
                    parsed = self._handle_statement(stmt.body)
                    if parsed:
                        body.append(parsed)

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
                right = expr.value

                # Handle array index assignment arr[i] = value
                if isinstance(left, javalang.tree.ArraySelector):
                    array_name = left.primary.member
                    index = self._handle_expression(left.index)

                    return MethodCall(
                        array_name,
                        "set_index",
                        [index, self._handle_expression(right)]
                    )

                # Normal variable assignment
                if hasattr(left, "member"):
                    var_name = left.member
                else:
                    var_name = left.name

                return Variable(
                    var_name,
                    "auto",
                    self._handle_expression(right)
                )

            # Method call: nums.add(5)
            if isinstance(expr, javalang.tree.MethodInvocation):

                if expr.qualifier:
                    return MethodCall(
                        expr.qualifier,
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

                    parsed = self._handle_statement(s)
                    if parsed:
                        body.append(parsed)

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
                    parsed = self._handle_statement(s)
                    if parsed:
                        body.append(parsed)
            else:
                parsed = self._handle_statement(stmt.body)
                if parsed:
                    body.append(parsed)

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

        # IDENTIFIER
        if isinstance(expr, javalang.tree.MemberReference):

            # If it has qualifier (like object.field)
            if expr.qualifier:
                return Identifier(f"{expr.qualifier}.{expr.member}")

            return Identifier(expr.member)

        # BINARY OP
        if isinstance(expr, javalang.tree.BinaryOperation):

            operator = expr.operator

            
            return BinaryOp(
                self._handle_expression(expr.operandl),
                operator,
                self._handle_expression(expr.operandr)
            )

        

        # METHOD CALL
        if isinstance(expr, javalang.tree.MethodInvocation):

            if expr.member == "equals" and expr.qualifier:
                return BinaryOp(
                    Identifier(expr.qualifier),
                    "==",
                    self._handle_expression(expr.arguments[0])
                )

            if expr.qualifier:
                return MethodCall(
                    expr.qualifier,
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
            return MethodCall(
                expr.member,
                "get_index",
                [self._handle_expression(expr.index)]
            )

        # OBJECT CREATION
        if isinstance(expr, javalang.tree.ClassCreator):
            return ObjectCreation(
                expr.type.name,
                [self._handle_expression(a) for a in expr.arguments]
            )

        return Constant(None)