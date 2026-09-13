"""Whole-program type inference over the IR.

The parsers emit an untyped IR because Python and C carry very little type
information at the syntax level. This pass walks the IR twice and records a
concrete type for every parameter, field, local and function return so that
statically typed generators do not have to fall back to `Object`.

Types are expressed in a neutral vocabulary — int, double, boolean, String,
List<T>, Map<K,V>, Set<T>, <ClassName>, Object — which TypeMapper then renders
per target language.
"""

from cross_language_system.core.ir_nodes import *

NUMERIC = ("int", "double")
UNKNOWN = "Object"

# Operators that force both operands to be numeric.
ARITHMETIC_OPS = {"Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow"}
ORDER_OPS = {"Lt", "Gt", "LtE", "GtE"}


def _unify_element(a, b):
    if a == b:
        return a
    if a in (None, "Object"):
        return b or "Object"
    if b in (None, "Object"):
        return a
    if {a, b} <= {"Integer", "Double"}:
        return "Double"
    return "Object"


def widen(a, b):
    """Least common type of two inferred types."""

    if a == b:
        return a
    if a in (None, UNKNOWN):
        return b or UNKNOWN
    if b in (None, UNKNOWN):
        return a
    if a in NUMERIC and b in NUMERIC:
        return "double"
    if {a, b} == {"int", "boolean"}:
        return "int"

    # Generic containers unify element-wise rather than collapsing to Object.
    for prefix in ("List<", "Set<"):
        if a.startswith(prefix) and b.startswith(prefix):
            return f"{prefix}{_unify_element(a[len(prefix):-1], b[len(prefix):-1])}>"

    if a.startswith("Map<") and b.startswith("Map<"):
        a_key, a_val = [p.strip() for p in a[4:-1].split(",", 1)]
        b_key, b_val = [p.strip() for p in b[4:-1].split(",", 1)]
        return f"Map<{_unify_element(a_key, b_key)}, {_unify_element(a_val, b_val)}>"

    return UNKNOWN


class Scope:

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        return self.parent.get(name) if self.parent else None

    def set(self, name, type_name):
        if type_name and type_name != UNKNOWN:
            self.vars[name] = type_name
        else:
            self.vars.setdefault(name, UNKNOWN)


class TypeAnnotator:
    """Annotates a Program in place and exposes the resolved type tables."""

    def __init__(self):
        self.functions = {}      # name -> return type
        self.classes = {}        # class name -> {field: type}
        self.function_defs = {}  # name -> Function node
        self.call_sites = {}     # name -> list of argument-type tuples
        self.current_class = None

    # ------------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------------

    def annotate(self, program):

        for node in program.body:
            if isinstance(node, Class):
                self.classes.setdefault(
                    node.name, {f.name: f.field_type for f in node.fields}
                )
            elif isinstance(node, Function):
                self.function_defs[node.name] = node

        # Three passes: discover signatures, feed call-site argument types back
        # into the definitions, then resolve everything with full information.
        for _ in range(3):
            self.call_sites = {}
            global_scope = Scope()

            for node in program.body:
                self._annotate_node(node, global_scope)

            self._apply_call_sites()

        return program

    def _apply_call_sites(self):

        for name, argument_lists in self.call_sites.items():

            func = self.function_defs.get(name)
            if not func:
                continue

            for arg_types in argument_lists:
                for param, arg_type in zip(func.params, arg_types):
                    func.param_types[param] = widen(func.param_types.get(param), arg_type)

    def _record_call(self, name, arg_types):
        self.call_sites.setdefault(name, []).append(arg_types)

    def _annotate_node(self, node, scope):

        if isinstance(node, Class):
            self._annotate_class(node)
        elif isinstance(node, Function):
            self._annotate_function(node, Scope(scope))
        else:
            self._visit_statement(node, scope)

    # ------------------------------------------------------------
    # CLASSES
    # ------------------------------------------------------------

    def _annotate_class(self, cls):

        previous = self.current_class
        self.current_class = cls.name
        fields = self.classes.setdefault(cls.name, {})

        for field in cls.fields:
            if field.value is not None:
                fields[field.name] = widen(fields.get(field.name), self.infer(field.value, Scope()))

        for method in cls.methods:
            self._annotate_function(method, Scope())

        # Constructor assignments are the strongest signal for field types.
        for field in cls.fields:
            field.field_type = fields.get(field.name) or UNKNOWN

        self.current_class = previous

    # ------------------------------------------------------------
    # FUNCTIONS
    # ------------------------------------------------------------

    def _annotate_function(self, func, scope):

        if func.owner:
            self.current_class = func.owner

        usage = {p: func.param_types.get(p) for p in func.params}

        for param, declared in list(usage.items()):
            scope.set(param, self._normalize(declared) if declared else UNKNOWN)

        # Locals must be resolved first: a parameter's type is often revealed by
        # what it is combined with (`total += s` only constrains s once total is
        # known), so visit the body, infer parameters, then re-visit.
        for stmt in func.body:
            self._visit_statement(stmt, scope)

        for param in func.params:
            from_usage = self._infer_param_from_usage(param, func.body, scope)
            scope.set(param, widen(scope.get(param), from_usage))

        for stmt in func.body:
            self._visit_statement(stmt, scope)

        # A parameter stored straight into a field shares that field's type.
        self._unify_params_with_fields(func, scope)

        func.param_types = {p: scope.get(p) or UNKNOWN for p in func.params}

        if func.is_constructor:
            func.return_type = "void"
        else:
            func.return_type = self._infer_return_type(func.body, scope)
            self.functions[func.name] = func.return_type

        return func

    def _unify_params_with_fields(self, func, scope):

        if not self.current_class:
            return

        fields = self.classes.setdefault(self.current_class, {})

        for stmt in self._walk(func.body):

            if not isinstance(stmt, Assignment):
                continue
            if not isinstance(stmt.target, AttributeAccess):
                continue
            if not isinstance(stmt.target.obj, SelfRef):
                continue
            if not isinstance(stmt.value, Identifier) or stmt.value.name not in func.params:
                continue

            name = stmt.value.name
            unified = widen(scope.get(name), fields.get(stmt.target.attribute))
            scope.set(name, unified)
            fields[stmt.target.attribute] = unified

    def _infer_return_type(self, body, scope):

        result = None
        found = False

        for stmt in self._walk(body):
            if isinstance(stmt, Return):
                found = True
                if stmt.value is None:
                    continue
                result = widen(result, self.infer(stmt.value, scope))

        if not found:
            return "void"

        return result or UNKNOWN

    def _infer_param_from_usage(self, param, body, scope):
        """Derive a parameter's type from the operations applied to it."""

        inferred = None

        for node in self._walk_expressions(body):

            if isinstance(node, BinaryOp):
                if self._is_name(node.left, param):
                    other = self.infer(node.right, scope)
                    inferred = widen(inferred, other if other in NUMERIC else
                                     ("String" if other == "String" else
                                      ("int" if node.operator in ARITHMETIC_OPS else None)))
                if self._is_name(node.right, param):
                    other = self.infer(node.left, scope)
                    inferred = widen(inferred, other if other in NUMERIC else
                                     ("String" if other == "String" else
                                      ("int" if node.operator in ARITHMETIC_OPS else None)))

            elif isinstance(node, BooleanOp) and node.operator in ORDER_OPS:
                if self._is_name(node.left, param):
                    other = self.infer(node.right, scope)
                    inferred = widen(inferred, other if other in NUMERIC else "int")
                if self._is_name(node.right, param):
                    other = self.infer(node.left, scope)
                    inferred = widen(inferred, other if other in NUMERIC else "int")

            elif isinstance(node, MethodCall) and self._is_name(node.obj, param):
                if node.method in ("size", "add", "get", "remove"):
                    inferred = widen(inferred, "List<Object>")

            elif isinstance(node, IndexAccess) and self._is_name(node.obj, param):
                inferred = widen(inferred, "List<Object>")

        for stmt in self._walk(body):

            if isinstance(stmt, AugAssign):
                # total += s constrains s to whatever total already is.
                if self._is_name(stmt.value, param):
                    inferred = widen(inferred, self.infer(stmt.target, scope))
                if self._is_name(stmt.target, param):
                    inferred = widen(inferred, self.infer(stmt.value, scope))

            if isinstance(stmt, ForLoop) and self._is_name(stmt.iterable, param):
                # The loop variable's usage reveals the element type.
                element = self._infer_param_from_usage(stmt.iterator, stmt.body, scope)
                inferred = widen(inferred, f"List<{self._boxed(element)}>")

            if isinstance(stmt, ListAppend) and self._is_name(stmt.list_obj, param):
                element = self.infer(stmt.value, scope)
                inferred = widen(inferred, f"List<{self._boxed(element)}>")

        return inferred or UNKNOWN

    @staticmethod
    def _is_name(expr, name):
        return isinstance(expr, Identifier) and expr.name == name

    # ------------------------------------------------------------
    # STATEMENTS
    # ------------------------------------------------------------

    def _visit_statement(self, stmt, scope):

        if isinstance(stmt, Variable):
            inferred = self.infer(stmt.value, scope)
            if stmt.var_type and stmt.var_type not in ("auto", UNKNOWN):
                inferred = widen(self._normalize(stmt.var_type), inferred)
            existing = scope.get(stmt.name)
            scope.set(stmt.name, widen(existing, inferred) if existing else inferred)
            stmt.var_type = scope.get(stmt.name) or UNKNOWN

        elif isinstance(stmt, Assignment):
            # cin >> x carries no type; take it from what is being written to.
            if isinstance(stmt.value, Input) and stmt.value.value_type is None:
                stmt.value.value_type = self.infer(stmt.target, scope)

            value_type = self.infer(stmt.value, scope)

            if isinstance(stmt.target, Identifier):
                scope.set(stmt.target.name, widen(scope.get(stmt.target.name), value_type))

            if isinstance(stmt.target, AttributeAccess) and isinstance(stmt.target.obj, SelfRef):
                if self.current_class:
                    fields = self.classes.setdefault(self.current_class, {})
                    fields[stmt.target.attribute] = widen(
                        fields.get(stmt.target.attribute), value_type
                    )

        elif isinstance(stmt, AugAssign):
            if isinstance(stmt.target, Identifier):
                scope.set(stmt.target.name, widen(scope.get(stmt.target.name), self.infer(stmt.value, scope)))

        elif isinstance(stmt, (IfStatement,)):
            for s in list(stmt.body) + list(stmt.else_body or []):
                self._visit_statement(s, scope)

        elif isinstance(stmt, ForLoop):
            if isinstance(stmt.iterable, RangeCall):
                scope.set(stmt.iterator, "int")
            else:
                scope.set(stmt.iterator, self._element_type(self.infer(stmt.iterable, scope)))
            for s in stmt.body:
                self._visit_statement(s, scope)

        elif isinstance(stmt, WhileLoop):
            for s in stmt.body:
                self._visit_statement(s, scope)

        elif isinstance(stmt, TryCatch):
            for s in list(stmt.try_body) + list(stmt.catch_body):
                self._visit_statement(s, scope)

        elif isinstance(stmt, ListAppend):
            if isinstance(stmt.list_obj, Identifier):
                element = self._boxed(self.infer(stmt.value, scope))
                current = scope.get(stmt.list_obj.name)
                if not current or current in (UNKNOWN, "List<Object>"):
                    scope.set(stmt.list_obj.name, f"List<{element}>")

        elif isinstance(stmt, Function):
            self._annotate_function(stmt, Scope(scope))

        elif isinstance(stmt, Class):
            self._annotate_class(stmt)

        else:
            # A bare call statement still contributes call-site argument types.
            self.infer(stmt, scope)

    # ------------------------------------------------------------
    # EXPRESSIONS
    # ------------------------------------------------------------

    def infer(self, expr, scope):

        if expr is None:
            return UNKNOWN

        if isinstance(expr, Constant):
            return self._constant_type(expr.value)

        if isinstance(expr, Identifier):
            return scope.get(expr.name) or UNKNOWN

        if isinstance(expr, SelfRef):
            return self.current_class or UNKNOWN

        if isinstance(expr, AttributeAccess):
            if isinstance(expr.obj, SelfRef) and self.current_class:
                return self.classes.get(self.current_class, {}).get(expr.attribute, UNKNOWN)
            owner = self.infer(expr.obj, scope)
            return self.classes.get(owner, {}).get(expr.attribute, UNKNOWN)

        if isinstance(expr, UnaryOp):
            if expr.operator == "Not":
                return "boolean"
            return self.infer(expr.operand, scope)

        if isinstance(expr, BinaryOp):
            left = self.infer(expr.left, scope)
            right = self.infer(expr.right, scope)
            if "String" in (left, right):
                return "String"
            if expr.operator == "Div":
                return "double"
            if "double" in (left, right):
                return "double"
            if left == "int" or right == "int":
                return "int"
            return widen(left, right)

        if isinstance(expr, BooleanOp):
            return "boolean"

        if isinstance(expr, TernaryOp):
            return widen(self.infer(expr.if_true, scope), self.infer(expr.if_false, scope))

        if isinstance(expr, StringInterpolation):
            return "String"

        if isinstance(expr, TypeCast):
            return self._normalize(expr.target_type)

        if isinstance(expr, Input):
            return self._normalize(expr.value_type) if expr.value_type else UNKNOWN

        if isinstance(expr, ArrayLiteral):
            if not expr.elements:
                return "List<Object>"
            element = None
            for e in expr.elements:
                element = widen(element, self.infer(e, scope))
            return f"List<{self._boxed(element)}>"

        if isinstance(expr, SetLiteral):
            if not expr.elements:
                return "Set<Object>"
            element = None
            for e in expr.elements:
                element = widen(element, self.infer(e, scope))
            return f"Set<{self._boxed(element)}>"

        if isinstance(expr, DictLiteral):
            if not expr.keys:
                return "Map<Object, Object>"
            key = None
            value = None
            for k in expr.keys:
                key = widen(key, self.infer(k, scope))
            for v in expr.values:
                value = widen(value, self.infer(v, scope))
            return f"Map<{self._boxed(key)}, {self._boxed(value)}>"

        if isinstance(expr, ObjectCreation):
            return expr.class_name

        if isinstance(expr, FunctionCall):
            self._record_call(expr.name, [self.infer(a, scope) for a in expr.args])
            return self.functions.get(expr.name, UNKNOWN)

        if isinstance(expr, MethodCall):
            if expr.method == "size":
                return "int"
            if expr.method == "split":
                return "List<String>"
            if expr.method in ("keys", "values"):
                return "List<Object>"
            return UNKNOWN

        if isinstance(expr, IndexAccess):
            return self._element_type(self.infer(expr.obj, scope))

        if isinstance(expr, RangeCall):
            return "List<Integer>"

        return UNKNOWN

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    @staticmethod
    def _constant_type(value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "String"
        return UNKNOWN

    @staticmethod
    def _normalize(name):
        return {
            "int": "int",
            "float": "double",
            "double": "double",
            "bool": "boolean",
            "boolean": "boolean",
            "str": "String",
            "string": "String",
            "token": "String",
            "list": "List<Object>",
            "dict": "Map<Object, Object>",
            "set": "Set<Object>",
            "object": UNKNOWN,
        }.get(str(name).lower(), name)

    @staticmethod
    def _boxed(type_name):
        return {
            "int": "Integer",
            "double": "Double",
            "boolean": "Boolean",
            None: "Object",
            UNKNOWN: "Object",
        }.get(type_name, type_name or "Object")

    @staticmethod
    def _element_type(container):
        if isinstance(container, str) and container.startswith(("List<", "Set<")):
            inner = container[container.index("<") + 1:-1]
            return {"Integer": "int", "Double": "double", "Boolean": "boolean"}.get(inner, inner)
        if isinstance(container, str) and container.startswith("Map<"):
            inner = container[container.index("<") + 1:-1]
            return inner.split(",")[-1].strip()
        if container == "String":
            return "String"
        return UNKNOWN

    def _walk(self, body):
        for stmt in body:
            yield stmt
            if isinstance(stmt, IfStatement):
                yield from self._walk(stmt.body)
                yield from self._walk(stmt.else_body or [])
            elif isinstance(stmt, (ForLoop, WhileLoop)):
                yield from self._walk(stmt.body)
            elif isinstance(stmt, TryCatch):
                yield from self._walk(stmt.try_body)
                yield from self._walk(stmt.catch_body)

    def _walk_expressions(self, body):
        for stmt in self._walk(body):
            for expr in self._statement_expressions(stmt):
                yield from self._walk_expression(expr)

    @staticmethod
    def _statement_expressions(stmt):
        for attr in ("value", "condition", "iterable", "target", "list_obj", "key", "dictionary"):
            expr = getattr(stmt, attr, None)
            if expr is not None:
                yield expr
        for expr in getattr(stmt, "args", None) or []:
            yield expr

    def _walk_expression(self, expr):
        # Several IR classes predate IRNode and do not subclass it, so nodes are
        # recognised by exclusion rather than by isinstance.
        if expr is None or isinstance(expr, (str, int, float, bool)):
            return
        yield expr
        for attr in ("left", "right", "operand", "obj", "value", "index", "condition",
                     "if_true", "if_false", "dictionary", "key"):
            yield from self._walk_expression(getattr(expr, attr, None))
        for child in (getattr(expr, "args", None) or []):
            yield from self._walk_expression(child)
        for child in (getattr(expr, "elements", None) or []):
            yield from self._walk_expression(child)
