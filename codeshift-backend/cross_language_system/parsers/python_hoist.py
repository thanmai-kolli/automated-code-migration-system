"""Comprehensions and generator expressions inside expressions, rewritten as loops.

No target language has comprehensions, but each has the loop a comprehension
stands for. A comprehension in a statement is computed into a fresh list (or
set) by loops placed just before the statement, and the statement uses that
list. A generator consumed by sum, max, min, sorted, list, set, tuple or
str.join is materialised the same way; any() and all() become loops that stop
at the first decisive element, as Python's do.

Only places Python evaluates unconditionally, once, before the statement's
effect are rewritten: the value of an expression statement, assignment or
return, an if test and a for iterable. A comprehension in a while test, in a
branch of a conditional expression, after the first operand of and/or, or in
a lambda stays where it is and is refused later.

Comprehension variables do not leak in Python 3, so they get fresh names.
"""

import ast

CONSUMERS = {"sum", "max", "min", "sorted", "list", "set", "tuple"}


def hoist_comprehensions(tree):
    tree.body = _Hoister().body(tree.body)
    return ast.fix_missing_locations(tree)


class _Renamer(ast.NodeTransformer):

    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        if node.id in self.mapping:
            return ast.copy_location(ast.Name(id=self.mapping[node.id], ctx=node.ctx), node)
        return node


class _Hoister:

    def __init__(self):
        self.counter = 0

    def fresh(self, base):
        self.counter += 1
        return f"_{base}{self.counter}"

    # ---- statements ----
    def body(self, statements):
        out = []
        for statement in statements:
            out.extend(self.statement(statement))
        return out

    def statement(self, stmt):
        for field in ("body", "orelse", "finalbody"):
            if isinstance(getattr(stmt, field, None), list):
                setattr(stmt, field, self.body(getattr(stmt, field)))
        if isinstance(stmt, ast.Try):
            for handler in stmt.handlers:
                handler.body = self.body(handler.body)

        before = []
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            self.unpacked_print(stmt.value)
        if isinstance(stmt, (ast.Expr, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign)) and stmt.value is not None:
            stmt.value = self.expr(stmt.value, before)
        elif isinstance(stmt, ast.If):
            stmt.test = self.expr(stmt.test, before)
        elif isinstance(stmt, ast.For):
            stmt.iter = self.expr(stmt.iter, before)
        for node in before:
            ast.copy_location(node, stmt)
        return before + [stmt]

    # ---- expressions ----
    def expr(self, node, before):
        if isinstance(node, (ast.Lambda, ast.GeneratorExp, ast.DictComp)):
            return node
        if isinstance(node, ast.IfExp):
            node.test = self.expr(node.test, before)
            return node
        if isinstance(node, ast.BoolOp):
            node.values[0] = self.expr(node.values[0], before)
            return node
        if isinstance(node, (ast.ListComp, ast.SetComp)):
            return self.materialise(node, before, as_set=isinstance(node, ast.SetComp))
        if isinstance(node, ast.Call):
            return self.call(node, before)
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.expr(value, before))
            elif isinstance(value, list):
                setattr(node, field, [self.expr(v, before) if isinstance(v, ast.expr) else v for v in value])
        return node

    def call(self, node, before):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        join = isinstance(node.func, ast.Attribute) and node.func.attr == "join"
        single = len(node.args) == 1 and not node.keywords
        argument = node.args[0] if node.args else None
        if single and name in CONSUMERS and isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name) \
                and argument.func.id == "range":
            # list(range(n)) and sum(range(a, b)) consume the numbers one by one.
            element = self.fresh("n")
            argument = node.args[0] = ast.GeneratorExp(
                elt=ast.Name(id=element, ctx=ast.Load()),
                generators=[ast.comprehension(target=ast.Name(id=element, ctx=ast.Store()), iter=argument,
                                              ifs=[], is_async=0)])

        if single and name in ("any", "all") and isinstance(argument, (ast.GeneratorExp, ast.ListComp)) \
                and len(argument.generators) == 1 and self.plain(argument):
            return self.any_all(name, argument, before)
        if single and isinstance(argument, ast.GeneratorExp) and (name in CONSUMERS or join) and self.plain(argument):
            if name in ("list", "tuple"):
                return self.materialise(argument, before)
            if name == "set":
                return self.materialise(argument, before, as_set=True)
            node.args[0] = self.materialise(argument, before)

        node.func = self.expr(node.func, before)
        node.args = [self.expr(a, before) for a in node.args]
        for keyword in node.keywords:
            keyword.value = self.expr(keyword.value, before)
        return node

    @staticmethod
    def plain(comprehension):
        return not any(g.is_async for g in comprehension.generators)

    # ---- rewriting ----
    def unpacked_print(self, call):
        """print(*xs, sep=s) prints the same text as print(s.join(str(x) for x in xs))."""

        if not (isinstance(call.func, ast.Name) and call.func.id == "print" and len(call.args) == 1
                and isinstance(call.args[0], ast.Starred)):
            return
        separator = " "
        keywords = []
        for keyword in call.keywords:
            if keyword.arg == "sep":
                if not (isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)):
                    return
                separator = keyword.value.value
            else:
                keywords.append(keyword)
        element = self.fresh("e")
        text = ast.GeneratorExp(
            elt=ast.Call(func=ast.Name(id="str", ctx=ast.Load()), args=[ast.Name(id=element, ctx=ast.Load())],
                         keywords=[]),
            generators=[ast.comprehension(target=ast.Name(id=element, ctx=ast.Store()), iter=call.args[0].value,
                                          ifs=[], is_async=0)])
        call.args = [ast.Call(func=ast.Attribute(value=ast.Constant(separator), attr="join", ctx=ast.Load()),
                              args=[text], keywords=[])]
        call.keywords = keywords

    def renamed(self, comprehension):
        """The comprehension with its loop variables given fresh names."""

        mapping = {}
        for generator in comprehension.generators:
            for node in ast.walk(generator.target):
                if isinstance(node, ast.Name):
                    mapping[node.id] = self.fresh(node.id.strip("_") or "v")
        renamer = _Renamer(mapping)
        for index, generator in enumerate(comprehension.generators):
            generator.target = renamer.visit(generator.target)
            if index:
                # Only the first iterable is evaluated outside the comprehension.
                generator.iter = renamer.visit(generator.iter)
            generator.ifs = [renamer.visit(condition) for condition in generator.ifs]
        comprehension.elt = renamer.visit(comprehension.elt)
        return comprehension

    @staticmethod
    def loops(generators, inner):
        body = inner
        for generator in reversed(generators):
            for condition in reversed(generator.ifs):
                body = [ast.If(test=condition, body=body, orelse=[])]
            body = [ast.For(target=generator.target, iter=generator.iter, body=body, orelse=[])]
        return body

    def materialise(self, comprehension, before, as_set=False):
        if not self.plain(comprehension):
            return comprehension
        temp = self.fresh("set" if as_set else "list")
        comprehension = self.renamed(comprehension)
        empty = ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[]) if as_set \
            else ast.List(elts=[], ctx=ast.Load())
        before.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())], value=empty))
        add = ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id=temp, ctx=ast.Load()), attr="add" if as_set else "append",
                               ctx=ast.Load()),
            args=[comprehension.elt], keywords=[]))
        before.extend(self.body(self.loops(comprehension.generators, [add])))
        return ast.Name(id=temp, ctx=ast.Load())

    def any_all(self, name, comprehension, before):
        temp = self.fresh(name)
        comprehension = self.renamed(comprehension)
        decisive = name == "any"
        before.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())], value=ast.Constant(not decisive)))
        test = comprehension.elt if decisive else ast.UnaryOp(op=ast.Not(), operand=comprehension.elt)
        found = [ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())], value=ast.Constant(decisive)),
                 ast.Break()]
        before.extend(self.body(self.loops(comprehension.generators, [ast.If(test=test, body=found, orelse=[])])))
        return ast.Name(id=temp, ctx=ast.Load())
