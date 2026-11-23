"""Operator precedence for printing IR expressions as infix text.

The IR is a tree, so grouping is implicit in its shape. Printing it back as
infix text loses that grouping unless the parentheses the tree implies are put
back: ``BinaryOp(BinaryOp(a, Add, b), Mult, 2)`` must print as ``(a + b) * 2``.
The two families differ in ways that matter — Python ranks bitwise operators
above comparisons and C ranks them below, and Python chains comparisons — so
each generator asks with its own language.
"""

from cross_language_system.core.ir_nodes import BinaryOp, BooleanOp, TernaryOp, UnaryOp

ATOM = 100
TERNARY = 1

_COMPARISONS = {"Eq", "NotEq", "Lt", "Gt", "LtE", "GtE", "In", "NotIn", "Is", "IsNot"}

# Higher binds tighter. Operators a generator prints as a call (Math.floorDiv,
# pow, a helper) are ranked as if they were infix, which can only add redundant
# parentheses, never drop needed ones.
_C_FAMILY = {
    "Or": 2, "And": 3, "BitOr": 4, "BitXor": 5, "BitAnd": 6,
    "Eq": 7, "NotEq": 7, "Is": 7, "IsNot": 7, "In": 7, "NotIn": 7,
    "Lt": 8, "Gt": 8, "LtE": 8, "GtE": 8,
    "LShift": 9, "RShift": 9,
    "Add": 10, "Sub": 10,
    "Mult": 11, "Div": 11, "FloorDiv": 11, "Mod": 11,
    "TruncDiv": 11, "TruncMod": 11, "FloorMod": 11,
    "Pow": 12, "Unary": 12,
}

_PYTHON = {
    "Or": 2, "And": 3, "Not": 4,
    "Eq": 5, "NotEq": 5, "Lt": 5, "Gt": 5, "LtE": 5, "GtE": 5,
    "In": 5, "NotIn": 5, "Is": 5, "IsNot": 5,
    "BitOr": 6, "BitXor": 7, "BitAnd": 8,
    "LShift": 9, "RShift": 9,
    "Add": 10, "Sub": 10,
    "Mult": 11, "Div": 11, "FloorDiv": 11, "Mod": 11,
    "TruncDiv": 11, "TruncMod": 11, "FloorMod": 11,
    "Unary": 12, "Pow": 13,
}


def _table(language):
    return _PYTHON if language == "python" else _C_FAMILY


def precedence(node, language):
    """How tightly the printed form of ``node`` binds."""

    table = _table(language)

    if isinstance(node, TernaryOp):
        return TERNARY
    if isinstance(node, (BinaryOp, BooleanOp)):
        # An operator this table does not know gets parenthesised everywhere.
        return table.get(node.operator, 0)
    if isinstance(node, UnaryOp):
        if node.operator == "Not" and language == "python":
            return table["Not"]
        return table["Unary"]
    return ATOM


def operand(text, node, parent_operator, language, right=False):
    """Parenthesise one operand of a binary operator when the tree demands it."""

    table = _table(language)
    parent = table.get(parent_operator, ATOM)
    child = precedence(node, language)

    if child < parent:
        return f"({text})"
    if child > parent:
        return text

    # Equal binding strength.
    if language == "python" and parent_operator in _COMPARISONS:
        # Python chains comparisons: a < b == c means a < b and b == c.
        return f"({text})"
    if parent_operator == "Pow" and language == "python":
        # ** is right-associative.
        return f"({text})" if not right else text
    # Everything else is left-associative, so only the right side needs
    # grouping: a - (b - c), and "x" + (1 + 2) for string concatenation.
    return f"({text})" if right else text


def unary_operand(text, node, language):
    """Operand of a prefix operator or a C-style cast."""

    if isinstance(node, UnaryOp):
        # -(-x) must not print as --x, which C and Java read as a decrement.
        return f"({text})"
    if precedence(node, language) < _table(language)["Unary"]:
        return f"({text})"
    return text


def postfix_operand(text, node, language):
    """Receiver of .attr, [index] or .method(): anything compound is grouped."""

    if precedence(node, language) < ATOM:
        return f"({text})"
    return text


def ternary_part(text, node):
    """Condition or branch of a conditional expression."""

    return f"({text})" if isinstance(node, TernaryOp) else text
