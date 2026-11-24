import ast
import math
import string

from cross_language_system.core import library
from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *
from cross_language_system.core.printf_format import python_spec_to_c
from cross_language_system.parsers.python_hoist import hoist_comprehensions


# math.<name>(...) calls every target can express.
MATH_FUNCTIONS = set(library.MATH_NAMES)
MATH_CONSTANTS = {"pi": math.pi, "e": math.e}


def _refuse(node, what):
    line = getattr(node, "lineno", None)
    where = f" (line {line})" if line else ""
    raise UnsupportedConstruct(f"{what}{where}")


class PythonParser:

    def __init__(self):
        self._temp_index = 0

    def parse(self, code):
        tree = hoist_comprehensions(ast.parse(code))
        tree.body = self._without_main_guard(tree.body)
        # A module-level function shadows the builtin of the same name.
        self._defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        return self._build_ir(tree)

    @staticmethod
    def _without_main_guard(statements):
        """if __name__ == "__main__": body  runs body when the program runs, as top-level code does."""

        out = []
        for node in statements:
            test = getattr(node, "test", None)
            if (isinstance(node, ast.If) and not node.orelse and isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name) and test.left.id == "__name__"
                    and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
                    and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__"):
                out.extend(node.body)
            else:
                out.append(node)
        return out

    def _build_ir(self, tree):

        body = []

        for node in tree.body:

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body.append(self._handle_function(node))

            elif isinstance(node, ast.ClassDef):
                body.append(self._handle_class(node))

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            else:
                # Tuple unpacking expands into several statements.
                body.extend(self._handle_body([node]))

        return Program(body)

    # ------------------------------------------------------------
    # FUNCTION
    # ------------------------------------------------------------

    def _handle_function(self, node, owner=None):

        params = [arg.arg for arg in node.args.args]

        is_method = bool(params) and params[0] in ("self", "cls")
        if is_method:
            params = params[1:]

        # Annotations are authoritative when the author supplied them.
        param_types = {}
        for arg in node.args.args:
            if arg.arg in params and arg.annotation is not None:
                param_types[arg.arg] = self._annotation_name(arg.annotation)

        body = self._handle_body(node.body)

        # Defaults bind to the trailing parameters.
        defaults = {}
        if node.args.defaults:
            tail = [a.arg for a in node.args.args][-len(node.args.defaults):]
            for param, default in zip(tail, node.args.defaults):
                if param in params:
                    defaults[param] = self._handle_expr(default)

        func = Function(
            node.name,
            params,
            body,
            is_constructor=(node.name == "__init__"),
            is_static=not is_method,
            param_types=param_types,
            owner=owner,
            defaults=defaults,
        )

        if node.returns is not None:
            func.return_type = self._annotation_name(node.returns)

        return func

    def _annotation_name(self, annotation):

        if isinstance(annotation, ast.Name):
            return annotation.id

        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value

        if isinstance(annotation, ast.Subscript):
            base = self._annotation_name(annotation.value)
            inner = self._annotation_name(annotation.slice)
            return f"{base}[{inner}]"

        return "object"

    # ------------------------------------------------------------
    # CLASS
    # ------------------------------------------------------------

    def _handle_class(self, node):

        methods = []
        fields = []
        seen_fields = set()

        base = None
        for b in node.bases:
            if isinstance(b, ast.Name) and b.id != "object":
                base = b.id
                break

        for item in node.body:

            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._handle_function(item, owner=node.name))

            # Class-level attribute: x = 0
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id not in seen_fields:
                        seen_fields.add(target.id)
                        fields.append(Field(target.id, value=self._handle_expr(item.value)))

            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.target.id not in seen_fields:
                    seen_fields.add(item.target.id)
                    fields.append(Field(
                        item.target.id,
                        self._annotation_name(item.annotation),
                        self._handle_expr(item.value) if item.value else None,
                    ))

        # Instance attributes assigned anywhere via self.<name> = ...
        for name in self._collect_self_attributes(node):
            if name not in seen_fields:
                seen_fields.add(name)
                fields.append(Field(name))

        return Class(node.name, methods, fields, base)

    def _collect_self_attributes(self, class_node):
        """Ordered list of every attribute assigned through self."""

        names = []

        for node in ast.walk(class_node):

            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]

            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr not in names
                ):
                    names.append(target.attr)

        return names

    # ------------------------------------------------------------
    # STATEMENT LISTS
    # ------------------------------------------------------------

    def _handle_body(self, statements):

        body = []

        for stmt in statements:
            parsed = self._handle_statement(stmt)

            # A tuple-unpacking assignment expands into several statements.
            if isinstance(parsed, list):
                body.extend(p for p in parsed if p is not None)
            elif parsed is not None:
                body.append(parsed)

        return body

    def _handle_statement(self, node):

        if isinstance(node, ast.Return):
            return Return(self._handle_expr(node.value))

        if isinstance(node, ast.Assign):
            return self._handle_assign(node)

        if isinstance(node, ast.AnnAssign):
            if node.value is None:
                return None
            value = self._handle_expr(node.value)
            declared = self._annotation_name(node.annotation)
            if isinstance(node.target, ast.Name):
                return Variable(node.target.id, declared, value)
            return Assignment(self._handle_expr(node.target), value)

        if isinstance(node, ast.AugAssign):
            return AugAssign(
                self._handle_expr(node.target),
                type(node.op).__name__,
                self._handle_expr(node.value),
            )

        if isinstance(node, ast.If):
            condition = self._handle_expr(node.test)
            body = self._handle_body(node.body)
            else_body = self._handle_body(node.orelse) if node.orelse else None
            return IfStatement(condition, body, else_body)

        if isinstance(node, ast.For):

            if node.orelse:
                _refuse(node, "for ... else")

            if isinstance(node.target, ast.Tuple):
                return self._tuple_for(node)
            if not isinstance(node.target, ast.Name):
                _refuse(node, "a for loop over this kind of target")

            return ForLoop(node.target.id, self._handle_expr(node.iter), self._handle_body(node.body))

        if isinstance(node, ast.While):
            if node.orelse:
                _refuse(node, "while ... else")
            return WhileLoop(self._handle_expr(node.test), self._handle_body(node.body))

        if isinstance(node, ast.Try):
            if len(node.handlers) > 1 or node.orelse or node.finalbody:
                _refuse(node, "try with several except clauses, else or finally")

            catch_var = None
            exception_type = None
            catch_body = []

            if node.handlers:
                handler = node.handlers[0]
                catch_var = handler.name
                if handler.type is not None:
                    exception_type = self._annotation_name(handler.type)
                catch_body = self._handle_body(handler.body)

            return TryCatch(
                self._handle_body(node.body),
                catch_var,
                catch_body,
                exception_type,
            )

        if isinstance(node, ast.Break):
            return Break()

        if isinstance(node, ast.Continue):
            return Continue()

        if isinstance(node, ast.Pass):
            return Pass()

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._handle_function(node)

        if isinstance(node, ast.ClassDef):
            return self._handle_class(node)

        if isinstance(node, ast.Expr):

            if isinstance(node.value, ast.Call):

                if isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                    return self._handle_print(node.value)

                # sys.stdout.write(s) prints s with nothing after it.
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == "write" and isinstance(func.value, ast.Attribute) \
                        and func.value.attr == "stdout" and isinstance(func.value.value, ast.Name) \
                        and func.value.value.id == "sys" and len(node.value.args) == 1 and not node.value.keywords:
                    return PrintStatement([self._handle_expr(node.value.args[0])], end="", sep="")

                if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "append":
                    return ListAppend(
                        self._handle_expr(node.value.func.value),
                        self._handle_expr(node.value.args[0]),
                    )

            # A bare docstring carries no executable meaning.
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return None

            return self._handle_expr(node.value)

        # These have no runtime effect on a program that runs correctly.
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assert)):
            return None

        _refuse(node, f"the '{type(node).__name__}' statement is not supported")

    def _handle_print(self, call):

        args = [self._handle_expr(a) for a in call.args]
        options = {"sep": " ", "end": "\n"}

        for keyword in call.keywords:
            if keyword.arg in options:
                if not (isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)):
                    _refuse(call, f"print({keyword.arg}=...) with a computed value")
                options[keyword.arg] = keyword.value.value
            elif keyword.arg == "flush":
                continue
            else:
                _refuse(call, f"print({keyword.arg}=...)")

        return PrintStatement(args, end=options["end"], sep=options["sep"])

    def _divmod_assign(self, node):
        """q, r = divmod(a, b)  ->  both results from a and b as they were, then the assignments."""

        value = node.value
        if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) and len(node.targets[0].elts) == 2
                and isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "divmod"
                and len(value.args) == 2 and not value.keywords and "divmod" not in getattr(self, "_defined", ())):
            return None
        statements, operands = [], []
        for argument in value.args:
            operand = self._handle_expr(argument)
            if not isinstance(argument, (ast.Name, ast.Constant)):
                self._temp_index += 1
                temp = f"_arg{self._temp_index}"
                statements.append(Variable(temp, value=operand))
                operand = Identifier(temp)
            operands.append(operand)
        self._temp_index += 1
        quotient, remainder = f"_q{self._temp_index}", f"_r{self._temp_index}"
        statements.append(Variable(quotient, value=BinaryOp(operands[0], "FloorDiv", operands[1])))
        statements.append(Variable(remainder, value=BinaryOp(operands[0], "Mod", operands[1])))
        for target, temp in zip(node.targets[0].elts, (quotient, remainder)):
            assignment = self._assign_to(target, Identifier(temp))
            if assignment is None:
                _refuse(node, "this divmod assignment target")
            statements.append(assignment)
        return statements

    def _handle_assign(self, node):

        divided = self._divmod_assign(node)
        if divided is not None:
            return divided

        # xs = list(map(int, input().split())) abbreviates a comprehension.
        comprehension = self._map_as_comprehension(node.value)
        if comprehension is not None and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            desugared = self._desugar_comprehension(node.targets[0].id, comprehension)
            if desugared is not None:
                return desugared

        # A comprehension has no equivalent in any target, but the loop it
        # stands for does, so desugar it before anything else sees it.
        if isinstance(node.value, (ast.ListComp, ast.SetComp)) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                desugared = self._desugar_comprehension(node.targets[0].id, node.value)
                if desugared is not None:
                    return desugared

        value = self._handle_expr(node.value)
        statements = []

        for target_node in node.targets:

            # a, b = 1, 2
            if isinstance(target_node, (ast.Tuple, ast.List)):

                # a, b = input().split() is N whitespace-delimited reads, which
                # every target language expresses directly.
                read_type = self._split_read_type(value)
                if read_type is not None:
                    for element in target_node.elts:
                        read = Input(None, "token")
                        if read_type != "token":
                            read = TypeCast(read_type, read)
                        statements.append(self._assign_to(element, read))
                    # input() consumed the whole line; so must the translation.
                    statements.append(Input(None, "eol"))
                    continue

                literal = (
                    node.value.elts
                    if isinstance(node.value, (ast.Tuple, ast.List))
                    and len(node.value.elts) == len(target_node.elts)
                    else None
                )

                if literal:
                    statements.extend(self._parallel_assign(target_node.elts, literal))
                    continue

                # Anything else must be evaluated once, or side effects such as
                # input() would run per unpacked name.
                self._temp_index += 1
                temp = f"_unpacked{self._temp_index}"
                statements.append(Variable(temp, value=value))

                for index, element in enumerate(target_node.elts):
                    statements.append(self._assign_to(
                        element,
                        IndexAccess(Identifier(temp), Constant(index)),
                    ))
                continue

            statements.append(self._assign_to(target_node, value))

        statements = [s for s in statements if s is not None]

        if not statements:
            return None

        return statements[0] if len(statements) == 1 else statements

    @staticmethod
    def _is_split_of_input(value):
        return (
            isinstance(value, MethodCall)
            and value.method == "split"
            and not value.args
            and isinstance(value.obj, Input)
        )

    def _split_read_type(self, value):
        """Read type of input().split() or map(int, input().split()), else None."""

        if self._is_split_of_input(value):
            return "token"
        if (isinstance(value, FunctionCall) and value.name == "map" and len(value.args) == 2
                and isinstance(value.args[0], Identifier) and self._is_split_of_input(value.args[1])):
            return {"int": "int", "float": "float", "str": "token"}.get(value.args[0].name)
        return None

    @classmethod
    def _map_as_comprehension(cls, node):
        """list(map(int, xs)) as the AST of [int(_v) for _v in xs], else None."""

        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list"
                and len(node.args) == 1 and not node.keywords):
            return None
        inner = node.args[0]
        if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "map"
                and len(inner.args) == 2 and not inner.keywords
                and isinstance(inner.args[0], ast.Name) and inner.args[0].id in cls.BUILTIN_CASTS):
            return None
        item = ast.Name(id="_v", ctx=ast.Load())
        return ast.ListComp(
            elt=ast.Call(func=inner.args[0], args=[item], keywords=[]),
            generators=[ast.comprehension(target=ast.Name(id="_v", ctx=ast.Store()),
                                          iter=inner.args[1], ifs=[], is_async=0)],
        )

    def _tuple_for(self, node):
        """for i, x in enumerate(xs) / for k, v in d.items() / for a, b in zip(xs, ys).

        Each becomes a loop over a hidden index or key, and the names are assigned
        at the top of the body, so a body that reassigns them cannot change the
        iteration (as in Python).
        """

        names = [e.id if isinstance(e, ast.Name) else None for e in node.target.elts]
        call = node.iter
        if None in names or not isinstance(call, ast.Call) or call.keywords:
            _refuse(node, "a for loop that unpacks this kind of value")

        self._temp_index += 1
        index = f"_i{self._temp_index}"
        func = call.func
        prologue = []

        def once(expression_node, label):
            if isinstance(expression_node, ast.Name):
                return Identifier(expression_node.id)
            temp = f"_{label}{self._temp_index}"
            prologue.append(Variable(temp, value=self._handle_expr(expression_node)))
            return Identifier(temp)

        if isinstance(func, ast.Name) and func.id == "enumerate" and len(names) == 2 and len(call.args) in (1, 2):
            sequence = once(call.args[0], "seq")
            position = Identifier(index)
            if len(call.args) == 2:
                position = BinaryOp(position, "Add", self._handle_expr(call.args[1]))
            header = [Variable(names[0], value=position),
                      Variable(names[1], value=IndexAccess(sequence, Identifier(index)))]
            loop = ForLoop(index, RangeCall([MethodCall(sequence, "size", [])]), header + self._handle_body(node.body))
            return prologue + [loop]

        if isinstance(func, ast.Name) and func.id == "zip" and len(call.args) == len(names) >= 2:
            sequences = [once(argument, f"seq{n}_") for n, argument in enumerate(call.args)]
            length = MethodCall(sequences[0], "size", [])
            for sequence in sequences[1:]:
                length = FunctionCall("min", [length, MethodCall(sequence, "size", [])])
            header = [Variable(name, value=IndexAccess(sequence, Identifier(index)))
                      for name, sequence in zip(names, sequences)]
            loop = ForLoop(index, RangeCall([length]), header + self._handle_body(node.body))
            return prologue + [loop]

        if (isinstance(func, ast.Attribute) and func.attr == "items" and not call.args and len(names) == 2):
            mapping = once(func.value, "map")
            header = [Variable(names[0], value=Identifier(index)),
                      Variable(names[1], value=IndexAccess(mapping, Identifier(index)))]
            return prologue + [ForLoop(index, mapping, header + self._handle_body(node.body))]

        _refuse(node, "a for loop that unpacks this kind of value")

    def _parallel_assign(self, targets, values):
        """a, b = b, a + b evaluates every right-hand side before assigning.

        Assigning element by element is only equivalent when no value reads a
        name an earlier element has already overwritten; any value that does
        is computed into a temporary first.
        """

        written = set()
        early = []
        late = []

        for target, value in zip(targets, values):
            read = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
            expression = self._handle_expr(value)
            if read & written:
                self._temp_index += 1
                temp = f"_next{self._temp_index}"
                early.append(Variable(temp, value=expression))
                expression = Identifier(temp)
            late.append(self._assign_to(target, expression))
            written |= self._names_written(target)

        return early + late

    @staticmethod
    def _names_written(target):
        """The variable an assignment target mutates: x, x[i] and x.f all write x."""

        node = target
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        names = {node.id} if isinstance(node, ast.Name) else set()
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                names |= PythonParser._names_written(element)
        return names

    def _repetition(self, node):
        """[x] * n with a constant x: n copies of an immutable value, which every target can build."""

        if not isinstance(node.op, ast.Mult):
            return None
        for sequence, count in ((node.left, node.right), (node.right, node.left)):
            if isinstance(sequence, ast.List) and len(sequence.elts) == 1 \
                    and isinstance(sequence.elts[0], ast.Constant) and not isinstance(sequence.elts[0].value, bytes):
                value = sequence.elts[0].value
                filled = FunctionCall("range_array", [self._handle_expr(count)])
                filled.element_type = {bool: "boolean", int: "int", float: "double", str: "String"}.get(
                    type(value), "Object")
                if value is not None and (isinstance(value, str) or value != 0 or isinstance(value, bool) and value):
                    filled.fill = Constant(value)
                return filled
        return None

    def _desugar_comprehension(self, name, node):
        """[f(i) for i in xs if c]  ->  name = []; for i in xs: if c: name.append(f(i))"""

        if len(node.generators) != 1:
            return None

        generator = node.generators[0]

        if generator.is_async or not isinstance(generator.target, ast.Name):
            return None

        body = [ListAppend(Identifier(name), self._handle_expr(node.elt))]

        for condition in reversed(generator.ifs):
            body = [IfStatement(self._handle_expr(condition), body)]

        empty = SetLiteral() if isinstance(node, ast.SetComp) else ArrayLiteral()

        return [
            Variable(name, value=empty),
            ForLoop(generator.target.id, self._handle_expr(generator.iter), body),
        ]

    def _assign_to(self, target_node, value):

        # d["b"] = 20
        if isinstance(target_node, ast.Subscript):
            return DictPut(
                self._handle_expr(target_node.value),
                self._handle_expr(target_node.slice),
                value,
            )

        # self.balance = 0   /   obj.field = 0
        if isinstance(target_node, ast.Attribute):
            return Assignment(self._handle_expr(target_node), value)

        if isinstance(target_node, ast.Name):
            return Variable(target_node.id, value=value)

        return None

    def _handle_expr(self, node):

        if node is None:
            return None

        if isinstance(node, ast.Call):
            return self._handle_call(node)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bytes):
                _refuse(node, "bytes literals")
            return Constant(node.value)

        if isinstance(node, ast.Name):
            if node.id == "self":
                return SelfRef()
            return Identifier(node.id)

        if isinstance(node, ast.Attribute):
            if (isinstance(node.value, ast.Name) and node.value.id == "math"
                    and node.attr in MATH_CONSTANTS):
                return Constant(MATH_CONSTANTS[node.attr])
            return AttributeAccess(self._handle_expr(node.value), node.attr)

        if isinstance(node, ast.BinOp):
            # "%d items" % n is printf-style formatting, not a remainder.
            if (
                isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)
            ):
                values = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
                return FormatString(node.left.value, [self._handle_expr(v) for v in values])

            repeated = self._repetition(node)
            if repeated is not None:
                return repeated

            return BinaryOp(
                self._handle_expr(node.left),
                type(node.op).__name__,
                self._handle_expr(node.right),
            )

        if isinstance(node, ast.UnaryOp):
            return UnaryOp(
                type(node.op).__name__,
                self._handle_expr(node.operand),
            )

        if isinstance(node, ast.BoolOp):
            # An and/or chain longer than two operands folds left to right.
            result = self._handle_expr(node.values[0])
            operator = type(node.op).__name__
            for value in node.values[1:]:
                result = BooleanOp(result, operator, self._handle_expr(value))
            return result

        if isinstance(node, ast.Compare):
            left = self._handle_expr(node.left)
            result = None
            for op, comparator in zip(node.ops, node.comparators):
                right = self._handle_expr(comparator)
                comparison = BooleanOp(left, type(op).__name__, right)
                result = comparison if result is None else BooleanOp(result, "And", comparison)
                left = right
            return result

        if isinstance(node, ast.IfExp):
            return TernaryOp(
                self._handle_expr(node.test),
                self._handle_expr(node.body),
                self._handle_expr(node.orelse),
            )

        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(Constant(value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append(self._formatted_value(value))
            return StringInterpolation(parts)

        if isinstance(node, (ast.List, ast.Tuple)):
            return ArrayLiteral([self._handle_expr(e) for e in node.elts])

        if isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                _refuse(node, "dictionary unpacking (**)")
            return DictLiteral(
                [self._handle_expr(k) for k in node.keys],
                [self._handle_expr(v) for v in node.values],
            )

        if isinstance(node, ast.Set):
            return SetLiteral([self._handle_expr(e) for e in node.elts])

        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                return self._slice(node)
            container = self._handle_expr(node.value)
            index = node.slice
            # xs[-1] counts from the end, which no target's indexing does.
            if (
                isinstance(index, ast.UnaryOp)
                and isinstance(index.op, ast.USub)
                and isinstance(index.operand, ast.Constant)
                and isinstance(index.operand.value, int)
            ):
                return IndexAccess(
                    container,
                    BinaryOp(MethodCall(self._handle_expr(node.value), "size", []),
                             "Sub", Constant(index.operand.value)),
                )
            return IndexAccess(container, self._handle_expr(index))

        _refuse(node, f"the '{type(node).__name__}' expression is not supported")

    def _slice(self, node):
        """s[a:b] and s[::-1]; any other step is refused."""

        bounds = node.slice
        container = self._handle_expr(node.value)
        step = bounds.step
        if step is not None:
            reverse = (isinstance(step, ast.UnaryOp) and isinstance(step.op, ast.USub)
                       and isinstance(step.operand, ast.Constant) and step.operand.value == 1)
            if reverse and bounds.lower is None and bounds.upper is None:
                return FunctionCall("reversed_copy", [container])
            _refuse(node, "slicing with a step")
        lower = self._handle_expr(bounds.lower) if bounds.lower is not None else Constant(None)
        upper = self._handle_expr(bounds.upper) if bounds.upper is not None else Constant(None)
        return FunctionCall("slice", [container, lower, upper])

    def _formatted_value(self, node):
        """One {value:spec} hole of an f-string."""

        if node.conversion not in (-1, ord("s")):
            _refuse(node, "f-string conversions !r and !a")

        value = self._handle_expr(node.value)

        if node.format_spec is None:
            return value

        pieces = node.format_spec.values
        if not all(isinstance(p, ast.Constant) for p in pieces):
            _refuse(node, "a computed f-string format spec")
        spec = "".join(p.value for p in pieces)
        return FormatString(python_spec_to_c(spec), [value])

    # ------------------------------------------------------------
    # CALLS
    # ------------------------------------------------------------

    BUILTIN_CASTS = {"int": "int", "float": "float", "str": "str", "bool": "bool"}

    def _handle_call(self, node):

        if node.keywords:
            _refuse(node, "keyword arguments")
        if any(isinstance(a, ast.Starred) for a in node.args):
            _refuse(node, "argument unpacking (*)")

        args = [self._handle_expr(a) for a in node.args]

        if isinstance(node.func, ast.Name):

            name = node.func.id

            if name in getattr(self, "_defined", ()):
                return FunctionCall(name, args)

            if name == "print":
                _refuse(node, "print() used as a value")

            if name == "len" and args:
                return MethodCall(args[0], "size", [])

            if name == "pow" and len(args) == 2:
                # The builtin keeps ints integral, unlike math.pow.
                return BinaryOp(args[0], "Pow", args[1])

            if name == "round" and len(args) in (1, 2):
                return FunctionCall("round_even" if len(args) == 1 else "round_digits", args)

            if name == "sorted" and len(args) == 1:
                return FunctionCall("sorted_copy", args)

            if name == "reversed" and len(args) == 1:
                return FunctionCall("reversed_copy", args)

            if name == "input":
                return Input(args[0] if args else None)

            if name in self.BUILTIN_CASTS and args:
                # int(input()) is a typed token read, not a cast over a line.
                if isinstance(args[0], Input) and args[0].reads_line:
                    return Input(args[0].prompt, {"int": "int", "float": "double"}.get(name, "String"))
                return TypeCast(self.BUILTIN_CASTS[name], args[0])

            if name == "range":
                return RangeCall(args)

            if name == "list" and not args:
                return ArrayLiteral()

            if name == "set" and not args:
                return SetLiteral()

            if name == "dict" and not args:
                return DictLiteral([], [])

            # A capitalised callee is conventionally a constructor.
            if name[:1].isupper():
                return ObjectCreation(name, args)

            return FunctionCall(name, args)

        if isinstance(node.func, ast.Attribute):

            method = node.func.attr

            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and method in MATH_FUNCTIONS
            ):
                # Python's math.floor and math.ceil return an int, C's and Java's a double.
                call = FunctionCall(method, args)
                call.library = True
                if method in ("floor", "ceil"):
                    return TypeCast("int", call)
                return call

            # "{} and {}".format(a, b) is an f-string written the old way.
            if (
                method == "format"
                and isinstance(node.func.value, ast.Constant)
                and isinstance(node.func.value.value, str)
            ):
                return self._str_format(node, node.func.value.value, args)

            obj = self._handle_expr(node.func.value)

            if method == "append" and args:
                return ListAppend(obj, args[0])

            if method in library.CHAR_TESTS and not args:
                return FunctionCall(method, [obj])

            if method == "join" and len(args) == 1:
                return FunctionCall("str_join", [obj, args[0]])

            return MethodCall(obj, method, args)

        _refuse(node, "calling the result of an expression")

    def _str_format(self, node, template, args):

        parts = []
        position = 0
        for literal, field, spec, conversion in string.Formatter().parse(template):
            if literal:
                parts.append(Constant(literal))
            if field is None:
                continue
            if field not in ("", str(position)) or conversion:
                _refuse(node, "str.format with named, reordered or converted fields")
            if position >= len(args):
                _refuse(node, "str.format with too few arguments")
            value = args[position]
            parts.append(FormatString(python_spec_to_c(spec), [value]) if spec else value)
            position += 1
        return StringInterpolation(parts)