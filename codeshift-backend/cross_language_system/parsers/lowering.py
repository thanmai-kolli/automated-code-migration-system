"""Lowering of C-style control flow, shared by the Java and C/C++ parsers.

The IR has Python-shaped loops (for x in range(...), while) and no switch, so
C-style for, do-while and switch are rewritten here. Each rewrite is either
provably equivalent or refused with UnsupportedConstruct; nothing is
approximated.
"""

import copy

from cross_language_system.core.errors import UnsupportedConstruct
from cross_language_system.core.ir_nodes import *

JUMPS = (Break, Continue, Return)


# ------------------------------------------------------------
# for (init; condition; update) body
# ------------------------------------------------------------

def counting_loop(init, condition, update, body, declared):
    """Lower a C-style for loop.

    init and update are lists of IR statements. ``declared`` says the init
    declares its variable (for (int i = 0; ...)), which scopes it to the loop:
    only then may the loop become a range loop, because a range loop leaves the
    variable at its last value while C leaves it one step past the bound.
    """

    as_range = _as_range(init, condition, update, body, declared)
    if as_range is not None:
        return as_range

    # A while loop with the update at the end of the body and before every
    # continue that belongs to this loop is exactly what for means.
    body = _update_before_continue(body, update)
    if _completes(body):
        body = body + copy.deepcopy(update)
    loop = WhileLoop(condition if condition is not None else Constant(True), body)
    return Block(list(init) + [loop]) if init else loop


def _as_range(init, condition, update, body, declared):

    if not declared or len(init) != 1 or len(update) != 1:
        return None

    start = init[0]
    if not isinstance(start, Variable) or start.value is None:
        return None
    if str(start.var_type) not in ("int", "long", "short", "auto"):
        return None
    name = start.name

    if not isinstance(condition, BooleanOp) or condition.operator not in ("Lt", "LtE", "Gt", "GtE"):
        return None

    operator = condition.operator
    if _is_name(condition.left, name):
        bound = condition.right
    elif _is_name(condition.right, name):
        bound = condition.left
        operator = {"Lt": "Gt", "LtE": "GtE", "Gt": "Lt", "GtE": "LtE"}[operator]
    else:
        return None

    step = update[0]
    if not (
        isinstance(step, AugAssign)
        and _is_name(step.target, name)
        and step.operator in ("Add", "Sub")
        and isinstance(step.value, Constant)
        and isinstance(step.value.value, int)
        and not isinstance(step.value.value, bool)
        and step.value.value > 0
    ):
        return None

    ascending = step.operator == "Add"
    if ascending != (operator in ("Lt", "LtE")):
        return None

    # range() fixes its bound once; the loop re-reads it every iteration.
    written = _written_names(body)
    if name in written or name in _read_names(bound) or _read_names(bound) & written:
        return None
    if _mutates_containers(body, _read_names(bound)):
        return None

    if operator == "LtE":
        end = _offset(bound, 1)
    elif operator == "GtE":
        end = _offset(bound, -1)
    else:
        end = bound

    amount = step.value.value if ascending else -step.value.value
    args = [start.value, end] if amount == 1 else [start.value, end, Constant(amount)]
    return ForLoop(name, RangeCall(args), body)


def _offset(expr, amount):
    if isinstance(expr, Constant) and isinstance(expr.value, int) and not isinstance(expr.value, bool):
        return Constant(expr.value + amount)
    return BinaryOp(expr, "Add" if amount > 0 else "Sub", Constant(abs(amount)))


def _update_before_continue(body, update):

    lowered = []
    for stmt in body:
        if isinstance(stmt, Continue):
            lowered.extend(copy.deepcopy(update))
            lowered.append(stmt)
        elif isinstance(stmt, IfStatement):
            lowered.append(IfStatement(
                stmt.condition,
                _update_before_continue(stmt.body, update),
                _update_before_continue(stmt.else_body or [], update),
            ))
        elif isinstance(stmt, Block):
            lowered.append(Block(_update_before_continue(stmt.body, update)))
        elif isinstance(stmt, TryCatch):
            lowered.append(TryCatch(
                _update_before_continue(stmt.try_body, update),
                stmt.catch_var,
                _update_before_continue(stmt.catch_body, update),
                stmt.exception_type,
            ))
        else:
            # A continue inside a nested loop belongs to that loop.
            lowered.append(stmt)
    return lowered


def _completes(body):
    """Whether control can fall off the end of a statement list."""

    if not body:
        return True
    last = body[-1]
    if isinstance(last, JUMPS):
        return False
    if isinstance(last, IfStatement) and last.else_body:
        return _completes(last.body) or _completes(last.else_body)
    if isinstance(last, Block):
        return _completes(last.body)
    return True


# ------------------------------------------------------------
# do { body } while (condition);
# ------------------------------------------------------------

def do_while(body, condition):

    if _loop_level(body, Continue):
        # continue in a do-while jumps to the condition test, which the
        # while (true) form would skip.
        raise UnsupportedConstruct("continue inside a do-while loop")

    if not _completes(body):
        return WhileLoop(Constant(True), body)
    return WhileLoop(Constant(True), body + [IfStatement(UnaryOp("Not", condition), [Break()])])


# ------------------------------------------------------------
# switch
# ------------------------------------------------------------

def switch(subject, cases, temp_name):
    """Lower switch to an if / else-if chain.

    cases is a list of (label, statements) in source order, label None for
    default. Labels with no statements fall through into the next ones, which
    becomes an or-ed condition. Falling through after statements, or a break
    that is not the last statement of its case, has no if/else equivalent and
    is refused.
    """

    groups = []
    labels = []
    for label, statements in cases:
        labels.append(label)
        if statements:
            groups.append((labels, statements))
            labels = []
    if labels:
        groups.append((labels, []))

    prelude = []
    if not isinstance(subject, (Identifier, Constant)):
        # The subject is evaluated once in C and Java.
        prelude.append(Variable(temp_name, "auto", subject))
        subject = Identifier(temp_name)

    branches = []
    default = None

    for index, (group_labels, statements) in enumerate(groups):

        last = index == len(groups) - 1
        if statements and _completes(statements) and not last:
            raise UnsupportedConstruct("switch case that falls through into the next case")

        if statements and isinstance(statements[-1], Break):
            statements = statements[:-1]
        if _loop_level(statements, Break):
            raise UnsupportedConstruct("break in the middle of a switch case")

        if None in group_labels:
            default = statements
            continue

        condition = None
        for label in group_labels:
            test = BooleanOp(copy.deepcopy(subject), "Eq", label)
            condition = test if condition is None else BooleanOp(condition, "Or", test)
        branches.append((condition, statements))

    chain = default or []
    for condition, statements in reversed(branches):
        chain = [IfStatement(condition, statements or [Pass()], chain)]

    return prelude + chain


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def bind_members(record):
    """Inside a Java or C++ method a bare field name means this.field.

    Python (and C, which passes self explicitly) needs the receiver spelled
    out, so every unshadowed use of a field in an instance method becomes an
    explicit member access.
    """

    fields = {f.name for f in record.fields}
    if not fields:
        return

    for method in record.methods:
        if method.is_static and not method.is_constructor:
            # A static method sees no instance; its bare names are locals or statics.
            continue
        local = set(method.params)
        for node in _walk(method.body):
            if isinstance(node, Variable) and node.var_type != "auto":
                local.add(node.name)
            elif isinstance(node, ForLoop):
                local.add(node.iterator)
        members = fields - local
        if members:
            method.body = [_member_access(s, members) for s in method.body]


def _member_access(node, members):
    """Rewrite one statement or expression tree, returning the new node."""

    if isinstance(node, list):
        return [_member_access(n, members) for n in node]

    if isinstance(node, Identifier) and node.name in members:
        return AttributeAccess(SelfRef(), node.name)

    if isinstance(node, Variable) and node.var_type == "auto" and node.name in members:
        return Assignment(AttributeAccess(SelfRef(), node.name), _member_access(node.value, members))

    if hasattr(node, "__dict__") and not isinstance(node, (Function, Class)):
        for key, value in vars(node).items():
            if isinstance(value, list) or hasattr(value, "__dict__"):
                setattr(node, key, _member_access(value, members))

    return node

def _is_name(expr, name):
    return isinstance(expr, Identifier) and expr.name == name


def _loop_level(body, kind):
    """Whether a statement of `kind` occurs outside any nested loop."""

    for stmt in body:
        if isinstance(stmt, kind):
            return True
        if isinstance(stmt, IfStatement):
            if _loop_level(stmt.body, kind) or _loop_level(stmt.else_body or [], kind):
                return True
        elif isinstance(stmt, Block):
            if _loop_level(stmt.body, kind):
                return True
        elif isinstance(stmt, TryCatch):
            if _loop_level(stmt.try_body, kind) or _loop_level(stmt.catch_body, kind):
                return True
    return False


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(current)
            continue
        if current is None or isinstance(current, (str, int, float, bool)):
            continue
        yield current
        for value in vars(current).values() if hasattr(current, "__dict__") else ():
            if isinstance(value, (list, dict)) or hasattr(value, "__dict__"):
                stack.append(list(value.values()) if isinstance(value, dict) else value)


def _written_names(body):
    names = set()
    for node in _walk(body):
        if isinstance(node, Variable):
            names.add(node.name)
        elif isinstance(node, (Assignment, AugAssign)) and isinstance(node.target, Identifier):
            names.add(node.target.name)
        elif isinstance(node, Input):
            pass
    return names


def _read_names(expr):
    return {node.name for node in _walk(expr) if isinstance(node, Identifier)}


MUTATORS = {"add", "append", "remove", "pop", "clear", "insert", "push_back",
            "pop_back", "erase", "put", "set", "addAll", "removeAll"}


def _mutates_containers(body, names):
    for node in _walk(body):
        if isinstance(node, ListAppend) and isinstance(node.list_obj, Identifier) \
                and node.list_obj.name in names:
            return True
        if isinstance(node, MethodCall) and isinstance(node.obj, Identifier) \
                and node.obj.name in names and node.method in MUTATORS:
            return True
    return False
