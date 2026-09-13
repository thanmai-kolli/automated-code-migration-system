import ast
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.type_inference import TypeInferenceEngine


class PythonParser:

    def parse(self, code):
        tree = ast.parse(code)
        return self._build_ir(tree)

    def _build_ir(self, tree):

        body = []

        for node in tree.body:

            if isinstance(node, ast.FunctionDef):
                body.append(self._handle_function(node))

            elif isinstance(node, ast.ClassDef):
                body.append(self._handle_class(node))

            else:
                stmt = self._handle_statement(node)
                if stmt is not None:
                    body.append(stmt)

        return Program(body)

    def _handle_function(self, node):

        params = [arg.arg for arg in node.args.args]

        if params and params[0] == "self":
            params = params[1:]
        body = [self._handle_statement(stmt) for stmt in node.body]

        inference = TypeInferenceEngine()

        return_type = "void"
        for stmt in body:
            if isinstance(stmt, Return):
                return_type = inference.infer(stmt.value)

        return Function(node.name, params, body, return_type)

    def _handle_class(self, node):

        methods = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(self._handle_function(item))

        return Class(node.name, methods)

    def _handle_statement(self, node):

        if isinstance(node, ast.Return):
            return Return(self._handle_expr(node.value))

        if isinstance(node, ast.Assign):

            target_node = node.targets[0]

            # 🔹 Handle dict assignment: d["b"] = 20
            if isinstance(target_node, ast.Subscript):

                dictionary = self._handle_expr(target_node.value)
                key = self._handle_expr(target_node.slice)
                value = self._handle_expr(node.value)

                return DictPut(dictionary, key, value)

            # 🔹 Normal variable assignment
            if isinstance(target_node, ast.Name):
                target = target_node.id
                value = self._handle_expr(node.value)
                return Variable(target, value=value)

        if isinstance(node, ast.If):
            condition = self._handle_expr(node.test)
            body = [self._handle_statement(s) for s in node.body]
            else_body = [self._handle_statement(s) for s in node.orelse] if node.orelse else None
            return IfStatement(condition, body, else_body)

        if isinstance(node, ast.For):
            iterator = node.target.id
            iterable = self._handle_expr(node.iter)
            body = [self._handle_statement(s) for s in node.body]
            return ForLoop(iterator, iterable, body)

        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                    args = [self._handle_expr(arg) for arg in node.value.args]
                    return PrintStatement(args)
                

            

                if isinstance(node.value.func, ast.Attribute):
                    if node.value.func.attr == "append":
                        return ListAppend(
                            self._handle_expr(node.value.func.value),
                            self._handle_expr(node.value.args[0])
                )

            return self._handle_expr(node.value)

        if isinstance(node, ast.While):
            condition = self._handle_expr(node.test)
            body = [self._handle_statement(s) for s in node.body]
            return WhileLoop(condition, body)
        return None

    def _handle_expr(self, node):

        if isinstance(node, ast.Call):

            if isinstance(node.func, ast.Name) and node.func.id == "len":
                return MethodCall(
                    self._handle_expr(node.args[0]),
                    "size",
                    []
                )
            if isinstance(node.func, ast.Name):

                if node.func.id == "input":
                    prompt = None
                    if node.args:
                        prompt = self._handle_expr(node.args[0])
                    return Input(prompt)

                if node.func.id == "int":
                    return TypeCast("int", self._handle_expr(node.args[0]))
                
                if node.func.id == "float":
                    return TypeCast("float", self._handle_expr(node.args[0]))
                
                if node.func.id == "range":
                    args = [self._handle_expr(a) for a in node.args]
                    return RangeCall(args)

                return FunctionCall(node.func.id,
                            [self._handle_expr(a) for a in node.args])
            

            if isinstance(node.func, ast.Attribute):

                method = node.func.attr
                obj = self._handle_expr(node.func.value)
                args = [self._handle_expr(a) for a in node.args]

                # Keep append special if you want
                if method == "append":
                    return ListAppend(obj, args[0])

                # Generic method call
                return MethodCall(obj, method, args)

            # Normal function call
            if isinstance(node.func, ast.Name):
                return FunctionCall(
                    node.func.id,
                    [self._handle_expr(a) for a in node.args]
                )
           


        if isinstance(node, ast.Constant):
            return Constant(node.value)

        if isinstance(node, ast.Name):
            return Identifier(node.id)

        if isinstance(node, ast.BinOp):
            return BinaryOp(
                self._handle_expr(node.left),
                type(node.op).__name__,
                self._handle_expr(node.right)
            )

        if isinstance(node, ast.BoolOp):
            return BooleanOp(
                self._handle_expr(node.values[0]),
                type(node.op).__name__,
                self._handle_expr(node.values[1])
            )

        if isinstance(node, ast.Compare):
            return BooleanOp(
                self._handle_expr(node.left),
                type(node.ops[0]).__name__,
                self._handle_expr(node.comparators[0])
            )

        if isinstance(node, ast.List):
            elements = [self._handle_expr(e) for e in node.elts]
            return ArrayLiteral(elements)
        
        if isinstance(node, ast.Dict):

            keys = [self._handle_expr(k) for k in node.keys]
            values = [self._handle_expr(v) for v in node.values]

            return DictLiteral(keys, values)
        
        if isinstance(node, ast.Set):
            elements = [self._handle_expr(e) for e in node.elts]
            return SetLiteral(elements)


        if isinstance(node, ast.Tuple):
            elements = [self._handle_expr(e) for e in node.elts]
            return ArrayLiteral(elements)  # treat like list

        if isinstance(node, ast.Subscript):
            return DictAccess(
                self._handle_expr(node.value),
                self._handle_expr(node.slice)
            )

        return None