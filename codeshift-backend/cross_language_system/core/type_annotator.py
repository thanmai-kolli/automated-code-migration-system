"""Whole-program type inference over the IR.

The parsers emit an untyped IR because Python and C carry very little type
information at the syntax level. This pass walks the IR twice and records a
concrete type for every parameter, field, local and function return so that
statically typed generators do not have to fall back to `Object`.

Types are expressed in a neutral vocabulary — int, long, double, char,
boolean, String, List<T>, Map<K,V>, Set<T>, <ClassName>, Object — which the
generators then render per target language.

Every expression it visits also gets an ``inferred_type`` attribute, and the
final pass rewrites the arithmetic operators whose meaning depends on the
source language: ``/`` on two ints truncates in C and Java but not in Python,
and ``%`` takes the sign of the dividend in C and Java but of the divisor in
Python. After annotation the IR spells those out as TruncDiv/TruncMod (C
semantics) or FloorDiv/FloorMod (Python semantics), so generators never have
to guess.
"""

from cross_language_system.core import library
from cross_language_system.core.ir_nodes import *

NUMERIC = ("int", "long", "double")
INTEGRAL = ("int", "long", "char", "boolean")
UNKNOWN = "Object"
C_SEMANTICS = ("java", "c", "c++", "cpp")

# Library calls every parser normalises to the same name.
MATH_RETURNS = {"sqrt": "double", "pow": "double", "floor": "double", "ceil": "double"}

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
        return "double" if "double" in (a, b) else "long"
    if {a, b} in ({"int", "boolean"}, {"int", "char"}):
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

    def __init__(self, source="python"):
        self.functions = {}      # name -> return type
        self.classes = {}        # class name -> {field: type}
        self.function_defs = {}  # name -> Function node
        self.method_defs = {}    # (class, method) -> Function node; constructors as (class, None)
        self.method_returns = {}  # (class, method) -> return type
        self.call_sites = {}     # name or (class, method) -> list of argument-type tuples
        self.current_class = None
        # Whether / and % follow C (truncating) or Python (flooring) rules.
        self.c_semantics = (source or "python").lower() in C_SEMANTICS

    # ------------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------------

    def annotate(self, program):

        # In C and Java every parameter and return type is written down, and
        # the program's meaning depends on it (int division, truncation on
        # assignment), so declarations are authoritative there and inference
        # only fills what is missing.
        self.declared_params = {}
        self.declared_returns = {}

        for node in program.body:
            if isinstance(node, Class):
                self.classes.setdefault(
                    node.name, {f.name: f.field_type for f in node.fields}
                )
                for method in node.methods:
                    key = (node.name, None if method.is_constructor else method.name)
                    self.method_defs[key] = method
            elif isinstance(node, Function):
                self.function_defs[node.name] = node

        if self.c_semantics:
            for func in self._functions_of(program):
                self.declared_params[id(func)] = {
                    p: t for p, t in func.param_types.items() if self._is_declared(t)
                }
                if self._is_declared(func.return_type) or func.return_type == "void":
                    self.declared_returns[id(func)] = self._normalize(func.return_type)

        # Three passes: discover signatures, feed call-site argument types back
        # into the definitions, then resolve everything with full information.
        for _ in range(3):
            self.call_sites = {}
            global_scope = Scope()

            # Two sweeps: `xs = []` is only typed once a later append is seen.
            for _ in range(2):
                for node in program.body:
                    self._annotate_node(node, global_scope)

            self._apply_call_sites()

        self._lower_arithmetic(program)
        return program

    # ------------------------------------------------------------
    # SOURCE-LANGUAGE ARITHMETIC
    # ------------------------------------------------------------

    def _lower_arithmetic(self, program):
        """Name the division and remainder semantics the source actually has."""

        for node in self._walk_all(program):
            if isinstance(node, BinaryOp):
                node.operator = self._precise_operator(
                    node.operator, self._type_of(node.left), self._type_of(node.right)
                )
            elif isinstance(node, AugAssign):
                node.operator = self._precise_operator(
                    node.operator, self._type_of(node.target), self._type_of(node.value)
                )

    def _precise_operator(self, operator, left, right):

        if self.c_semantics:
            integral = self._integral(left) and self._integral(right)
            if operator == "Div" and integral:
                return "TruncDiv"
            if operator == "Mod" and integral:
                return "TruncMod"
            return operator

        # Python: % on a string is formatting, not arithmetic.
        if operator == "Mod" and left != "String":
            return "FloorMod"
        return operator

    @staticmethod
    def _integral(type_name):
        # An unresolved operand in a C-family source is almost always an int,
        # and every declared floating type resolves to double.
        return type_name in INTEGRAL or type_name in (None, UNKNOWN)

    @staticmethod
    def _type_of(expr):
        return getattr(expr, "inferred_type", None)

    def _walk_all(self, node):
        """Every IR object reachable from node, depth first."""

        stack = [node]
        seen = set()
        while stack:
            current = stack.pop()
            if current is None or isinstance(current, (str, int, float, bool)):
                continue
            if id(current) in seen:
                continue
            seen.add(id(current))
            yield current
            for value in vars(current).values() if hasattr(current, "__dict__") else ():
                if isinstance(value, list):
                    stack.extend(value)
                elif isinstance(value, dict):
                    stack.extend(value.values())
                elif hasattr(value, "__dict__"):
                    stack.append(value)

    def _apply_call_sites(self):

        for name, argument_lists in self.call_sites.items():

            func = self.method_defs.get(name) if isinstance(name, tuple) else self.function_defs.get(name)
            if not func:
                continue

            declared = self.declared_params.get(id(func), {})
            for arg_types in argument_lists:
                for param, arg_type in zip(func.params, arg_types):
                    if param in declared:
                        continue
                    func.param_types[param] = widen(func.param_types.get(param), arg_type)

    @staticmethod
    def _is_declared(type_name):
        return type_name not in (None, "", "auto", "void", UNKNOWN, "object")

    @staticmethod
    def _functions_of(program):
        for node in program.body:
            if isinstance(node, Function):
                yield node
            elif isinstance(node, Class):
                yield from node.methods

    def _converted(self, value, target_type):
        """value as C/Java would store it in a target_type slot.

        Both languages convert between int and double implicitly on
        assignment and return (C in both directions, Java when widening);
        Python does not, so the conversion has to become explicit.
        """

        if not self.c_semantics or value is None:
            return value
        value_type = getattr(value, "inferred_type", None)
        if target_type in ("int", "long") and value_type == "double":
            converted = TypeCast("int", value)
            converted.inferred_type = target_type
            return converted
        if target_type == "double" and value_type in ("int", "long"):
            if isinstance(value, Constant) and not isinstance(value.value, bool):
                converted = Constant(float(value.value))
            else:
                converted = TypeCast("float", value)
            converted.inferred_type = "double"
            return converted
        return value

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

        # A default value is direct evidence of the parameter's type.
        for param, default in (func.defaults or {}).items():
            scope.set(param, widen(scope.get(param), self.infer(default, scope)))

        # Locals must be resolved first: a parameter's type is often revealed by
        # what it is combined with (`total += s` only constrains s once total is
        # known), so visit the body, infer parameters, then re-visit.
        for stmt in func.body:
            self._visit_statement(stmt, scope)

        for param in func.params:
            if param in self.declared_params.get(id(func), {}):
                continue
            from_usage = self._infer_param_from_usage(param, func.body, scope)
            scope.set(param, widen(scope.get(param), from_usage))

        for stmt in func.body:
            self._visit_statement(stmt, scope)

        # A parameter stored straight into a field shares that field's type.
        self._unify_params_with_fields(func, scope)

        func.param_types = {p: scope.get(p) or UNKNOWN for p in func.params}

        if func.is_constructor:
            func.return_type = "void"
        elif id(func) in self.declared_returns:
            func.return_type = self.declared_returns[id(func)]
            self.functions[func.name] = func.return_type
            for stmt in self._walk(func.body):
                if isinstance(stmt, Return) and stmt.value is not None:
                    self.infer(stmt.value, scope)
                    stmt.value = self._converted(stmt.value, func.return_type)
        else:
            func.return_type = self._infer_return_type(func.body, scope)
            self.functions[func.name] = func.return_type

        if func.owner and not func.is_constructor:
            self.method_returns[(func.owner, func.name)] = func.return_type

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
            inferred = self._widened(stmt.value, self.infer(stmt.value, scope))
            declared = stmt.var_type and stmt.var_type not in ("auto", UNKNOWN)
            existing = scope.get(stmt.name)
            if self.c_semantics and declared:
                # int x = 2.5 is still an int in C.
                scope.vars[stmt.name] = self._normalize(stmt.var_type)
            elif self.c_semantics and existing not in (None, UNKNOWN):
                pass  # plain assignment to a variable declared earlier
            else:
                if declared:
                    inferred = widen(self._normalize(stmt.var_type), inferred)
                scope.set(stmt.name, widen(existing, inferred) if existing else inferred)
            stmt.var_type = scope.get(stmt.name) or UNKNOWN
            stmt.value = self._converted(stmt.value, stmt.var_type)

        elif isinstance(stmt, Assignment):
            # cin >> x carries no type; take it from what is being written to.
            if isinstance(stmt.value, Input) and stmt.value.value_type is None:
                stmt.value.value_type = self.infer(stmt.target, scope)

            value_type = self.infer(stmt.value, scope)
            target_type = self.infer(stmt.target, scope)

            if isinstance(stmt.target, Identifier):
                if self.c_semantics and target_type not in (None, UNKNOWN):
                    stmt.value = self._converted(stmt.value, target_type)
                else:
                    scope.set(stmt.target.name, widen(scope.get(stmt.target.name), value_type))

            if isinstance(stmt.target, AttributeAccess) and isinstance(stmt.target.obj, SelfRef):
                if self.current_class:
                    fields = self.classes.setdefault(self.current_class, {})
                    fields[stmt.target.attribute] = widen(
                        fields.get(stmt.target.attribute), value_type
                    )

        elif isinstance(stmt, AugAssign):
            self.infer(stmt.value, scope)
            # x op= v has the type of x op v (Python's x /= 2 makes x a float).
            value_type = self._widened(BinaryOp(stmt.target, stmt.operator, stmt.value),
                                       self._infer(BinaryOp(stmt.target, stmt.operator, stmt.value), scope))
            if isinstance(stmt.target, Identifier):
                current = scope.get(stmt.target.name)
                # x /= 2 on an int stays an int in C and Java.
                if not (self.c_semantics and current in INTEGRAL):
                    scope.set(stmt.target.name, widen(current, value_type))
            self.infer(stmt.target, scope)

        elif isinstance(stmt, PrintStatement):
            for arg in stmt.args:
                self.infer(arg, scope)

        elif isinstance(stmt, Block):
            for s in stmt.body:
                self._visit_statement(s, scope)

        elif isinstance(stmt, Return):
            self.infer(stmt.value, scope)

        elif isinstance(stmt, (IfStatement,)):
            self.infer(stmt.condition, scope)
            for s in list(stmt.body) + list(stmt.else_body or []):
                self._visit_statement(s, scope)

        elif isinstance(stmt, ForLoop):
            iterable_type = self.infer(stmt.iterable, scope)
            if isinstance(stmt.iterable, RangeCall):
                scope.set(stmt.iterator, "int")
            elif isinstance(iterable_type, str) and iterable_type.startswith("Map<"):
                # Iterating a dictionary visits its keys.
                key = iterable_type[4:-1].split(",")[0].strip()
                scope.set(stmt.iterator, self._element_type(f"List<{key}>"))
            else:
                scope.set(stmt.iterator, self._element_type(iterable_type))
            for s in stmt.body:
                self._visit_statement(s, scope)

        elif isinstance(stmt, WhileLoop):
            self.infer(stmt.condition, scope)
            for s in stmt.body:
                self._visit_statement(s, scope)

        elif isinstance(stmt, TryCatch):
            for s in list(stmt.try_body) + list(stmt.catch_body):
                self._visit_statement(s, scope)

        elif isinstance(stmt, ListAppend):
            self.infer(stmt.list_obj, scope)
            if isinstance(stmt.list_obj, Identifier):
                element = self._boxed(self.infer(stmt.value, scope))
                current = scope.get(stmt.list_obj.name)
                if not current or current in (UNKNOWN, "List<Object>"):
                    scope.set(stmt.list_obj.name, f"List<{element}>")
                elif current == "Set<Object>":
                    scope.set(stmt.list_obj.name, f"Set<{element}>")
            else:
                self.infer(stmt.value, scope)

        elif isinstance(stmt, DictPut):
            key = self._boxed(self.infer(stmt.key, scope))
            value = self._boxed(self.infer(stmt.value, scope))
            if isinstance(stmt.dictionary, Identifier):
                current = scope.get(stmt.dictionary.name)
                if not current or current in (UNKNOWN, "Map<Object, Object>"):
                    scope.set(stmt.dictionary.name, f"Map<{key}, {value}>")
            self.infer(stmt.dictionary, scope)

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
        """Type of expr; also recorded on the node for the generators."""

        result = self._infer(expr, scope)
        if expr is not None and hasattr(expr, "__dict__"):
            expr.inferred_type = result
        return result

    def _infer(self, expr, scope):

        if expr is None:
            return UNKNOWN

        if isinstance(expr, Constant):
            if getattr(expr, "is_char", False):
                return "char"
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
            operator = expr.operator
            if operator in ("Add", "Mult") and "String" in (left, right):
                return "String"
            if operator in ("Mod", "FloorMod") and left == "String":
                return "String"
            integral = "long" if "long" in (left, right) else "int"
            if operator in ("TruncDiv", "TruncMod"):
                return integral
            if operator == "Div":
                if self.c_semantics and self._integral(left) and self._integral(right):
                    return integral
                return "double"
            if operator == "Pow":
                # int ** int stays integral in Python, and unbounded.
                if "double" in (left, right):
                    return "double"
                return "long" if not self.c_semantics else integral
            if operator in ("BitAnd", "BitOr", "BitXor", "LShift", "RShift"):
                if operator == "LShift" and not self.c_semantics:
                    return "long"
                return integral
            if "double" in (left, right):
                return "double"
            if "long" in (left, right):
                return "long"
            if "int" in (left, right) or "char" in (left, right):
                return "int"
            return widen(left, right)

        if isinstance(expr, BooleanOp):
            self.infer(expr.left, scope)
            self.infer(expr.right, scope)
            return "boolean"

        if isinstance(expr, TernaryOp):
            self.infer(expr.condition, scope)
            return widen(self.infer(expr.if_true, scope), self.infer(expr.if_false, scope))

        if isinstance(expr, StringInterpolation):
            for part in expr.parts:
                self.infer(part, scope)
            return "String"

        if isinstance(expr, FormatString):
            for arg in expr.args:
                self.infer(arg, scope)
            if getattr(expr, "stream", None) is not None or getattr(expr, "to_string", False):
                expr.fmt = self._deferred_format(expr)
            return "String"

        if isinstance(expr, TypeCast):
            self.infer(expr.value, scope)
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
            arg_types = [self.infer(a, scope) for a in (expr.arguments or [])]
            if expr.class_name in self.classes:
                self._record_call((expr.class_name, None), arg_types)
            # A collection constructor describes a container, not a user class.
            return {
                "ArrayList": "List<Object>",
                "LinkedList": "List<Object>",
                "Vector": "List<Object>",
                "HashMap": "Map<Object, Object>",
                "TreeMap": "Map<Object, Object>",
                "HashSet": "Set<Object>",
                "TreeSet": "Set<Object>",
            }.get(expr.class_name, expr.class_name)

        if isinstance(expr, FunctionCall):
            arg_types = [self.infer(a, scope) for a in expr.args]
            library_call = getattr(expr, "library", False)
            if not library_call:
                self._record_call(expr.name, arg_types)
            if expr.name in self.functions and not library_call:
                return self.functions[expr.name]
            library_type = library.result_type(expr.name, arg_types)
            if library_type is not None:
                return library_type
            if expr.name in MATH_RETURNS:
                return MATH_RETURNS[expr.name]
            if expr.name in ("isupper", "islower", "isdigit", "isalpha", "isspace", "isalnum"):
                return "boolean"
            if expr.name in ("toupper", "tolower"):
                return "char"
            if expr.name in ("max", "min", "sum") and len(arg_types) == 1:
                # max(values) over a container yields an element.
                return self._element_type(arg_types[0])
            if expr.name in ("abs", "max", "min") and arg_types:
                result = None
                for arg_type in arg_types:
                    result = widen(result, arg_type)
                return result
            return UNKNOWN

        if isinstance(expr, MethodCall):
            obj_type = self.infer(expr.obj, scope)
            arg_types = [self.infer(arg, scope) for arg in expr.args]
            if obj_type in self.classes:
                # A call on a user object: its arguments type the method's
                # parameters, and its result is the method's return type.
                self._record_call((obj_type, expr.method), arg_types)
                return self.method_returns.get((obj_type, expr.method), UNKNOWN)
            if expr.method == "size":
                return "int"
            if expr.method == "split":
                return "List<String>"
            if expr.method in ("keys", "values"):
                return "List<Object>"
            if expr.method in ("upper", "lower", "strip", "toUpperCase", "toLowerCase", "trim", "replace"):
                return "String" if obj_type == "String" else UNKNOWN
            if expr.method in ("count", "find", "index"):
                return "int"
            if expr.method == "pop":
                return self._element_type(obj_type)
            if (expr.method == "add" and obj_type == "Set<Object>" and len(arg_types) == 1
                    and isinstance(expr.obj, Identifier) and arg_types[0] != UNKNOWN):
                # s = set(); s.add(3) makes s a set of integers.
                scope.set(expr.obj.name, f"Set<{self._boxed(arg_types[0])}>")
            return UNKNOWN

        if isinstance(expr, IndexAccess):
            self.infer(expr.index, scope)
            return self._element_type(self.infer(expr.obj, scope))

        if isinstance(expr, RangeCall):
            for arg in expr.args:
                self.infer(arg, scope)
            return "List<Integer>"

        return UNKNOWN

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _widened(self, value, inferred):
        """A Python int that can grow past 32 bits needs a 64-bit slot.

        Python integers never overflow; products, powers and shifts are where
        a translated int overflows in practice (factorials, 10 ** 12).
        """
        if self.c_semantics or inferred != "int":
            return inferred
        if isinstance(value, BinaryOp) and value.operator in ("Mult", "Pow", "LShift"):
            return "long"
        if isinstance(value, Constant) and isinstance(value.value, int) and not -2**31 <= value.value < 2**31:
            return "long"
        return inferred

    def _deferred_format(self, expr):
        """printf format for C++'s to_string(x) or a manipulated cout item."""

        kind = self._type_of(expr.args[0]) if expr.args else None
        if getattr(expr, "to_string", False):
            # to_string prints a double as %f and a char or bool as a number.
            return {"double": "%f", "long": "%lld", "String": "%s"}.get(kind, "%d")
        fixed, precision, width, left = expr.stream
        flags = ("-" if left else "") + (str(width) if width else "")
        if kind == "double":
            if fixed:
                return f"%{flags}.{6 if precision is None else precision}f"
            return f"%{flags}.{precision}g" if precision is not None else f"%{flags}g"
        conversion = {"int": "d", "boolean": "d", "long": "lld", "char": "c", "String": "s"}.get(kind)
        if conversion is None:
            # Unresolved yet; a later pass sees the full type information.
            return "%s"
        return f"%{flags}{conversion}"

    @staticmethod
    def _constant_type(value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "int" if -2**31 <= value < 2**31 else "long"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "String"
        return UNKNOWN

    @staticmethod
    def _normalize(name):
        return {
            "int": "int",
            "integer": "int",
            "short": "int",
            "byte": "int",
            "long": "long",
            "float": "double",
            "double": "double",
            "char": "char",
            "character": "char",
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
            "long": "Long",
            "double": "Double",
            "char": "Character",
            "boolean": "Boolean",
            None: "Object",
            UNKNOWN: "Object",
        }.get(type_name, type_name or "Object")

    @staticmethod
    def _element_type(container):
        if isinstance(container, str) and container.startswith(("List<", "Set<")):
            inner = container[container.index("<") + 1:-1]
            return {"Integer": "int", "Long": "long", "Double": "double",
                    "Character": "char", "Boolean": "boolean"}.get(inner, inner)
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
            elif isinstance(stmt, (ForLoop, WhileLoop, Block)):
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
