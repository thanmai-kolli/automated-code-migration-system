# ------------------------------------------------------------
# Base Node
# ------------------------------------------------------------

class IRNode:
    pass


# ------------------------------------------------------------
# Try-Catch
# ------------------------------------------------------------

class TryCatch(IRNode):
    def __init__(self, try_body=None, catch_var=None, catch_body=None, exception_type=None):
        self.try_body = try_body or []
        self.catch_var = catch_var
        self.catch_body = catch_body or []
        self.exception_type = exception_type
    
class PrintStatement:
    def __init__(self, args):
        self.args = args

class Input:
    """A read from stdin.

    value_type distinguishes the two shapes every language has: reading a whole
    line as text (Python's input(), Scanner.nextLine) versus reading one
    whitespace-delimited token of a given type (scanf, cin >>, Scanner.nextInt).
    None means the type is not known syntactically and the annotator resolves it
    from the assignment target.
    """

    def __init__(self, prompt=None, value_type="String"):
        self.prompt = prompt
        self.value_type = value_type

    @property
    def reads_line(self):
        return self.value_type == "String"

class TypeCast:
    def __init__(self, target_type, value):
        self.target_type = target_type
        self.value = value


class DictLiteral:
    def __init__(self, keys, values):
        self.keys = keys
        self.values = values

class ListAppend:
    def __init__(self, list_obj, value):
        self.list_obj = list_obj
        self.value = value

class SetLiteral:
    def __init__(self, elements):
        self.elements = elements

class DictPut:
    def __init__(self, dictionary, key, value):
        self.dictionary = dictionary
        self.key = key
        self.value = value

class RangeCall:
    def __init__(self, args):
        self.args = args



# ------------------------------------------------------------
# Program Root
# ------------------------------------------------------------

class Program(IRNode):

    def __init__(self, body=None):
        self.body = body or []


# ------------------------------------------------------------
# Class
# ------------------------------------------------------------

class Class(IRNode):

    def __init__(self, name, methods=None, fields=None, base=None):
        self.name = name
        self.methods = methods or []
        self.fields = fields or []
        self.base = base


# ------------------------------------------------------------
# Function / Method
# ------------------------------------------------------------

class Function(IRNode):

    def __init__(self, name, params=None, body=None, return_type="void",
                 is_constructor=False, is_static=True, param_types=None,
                 owner=None, defaults=None):
        self.name = name
        self.params = params or []
        self.body = body or []
        self.return_type = return_type
        self.is_constructor = is_constructor
        # Top-level functions stay static; methods bound to an instance do not.
        self.is_static = is_static
        self.param_types = param_types or {}
        self.owner = owner
        self.defaults = defaults or {}


# ------------------------------------------------------------
# Variable Declaration / Assignment
# ------------------------------------------------------------

class Variable(IRNode):

    def __init__(self, name, var_type="auto", value=None):
        self.name = name
        self.var_type = var_type
        self.value = value


# ------------------------------------------------------------
# Return Statement
# ------------------------------------------------------------

class Return(IRNode):

    def __init__(self, value=None):
        self.value = value


# ------------------------------------------------------------
# If Statement
# ------------------------------------------------------------

class IfStatement(IRNode):

    def __init__(self, condition, body=None, else_body=None):
        self.condition = condition
        self.body = body or []
        self.else_body = else_body or []


# ------------------------------------------------------------
# For Loop
# ------------------------------------------------------------

class ForLoop(IRNode):

    def __init__(self, iterator, iterable, body=None):
        self.iterator = iterator
        self.iterable = iterable
        self.body = body or []


# ------------------------------------------------------------
# Expressions
# ------------------------------------------------------------

class Expression(IRNode):
    pass


# ------------------------------------------------------------
# Constant
# ------------------------------------------------------------

class Constant(Expression):

    def __init__(self, value):
        self.value = value


# ------------------------------------------------------------
# Identifier
# ------------------------------------------------------------

class Identifier(Expression):

    def __init__(self, name):
        self.name = name


# ------------------------------------------------------------
# Binary Operation (+, -, *, /)
# ------------------------------------------------------------

class BinaryOp(Expression):

    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator  # Add, Sub, Mult, Div
        self.right = right


# ------------------------------------------------------------
# Boolean Operation (and, or, ==, <, >)
# ------------------------------------------------------------

class BooleanOp(Expression):

    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right


# ------------------------------------------------------------
# Array Literal
# ------------------------------------------------------------

class ArrayLiteral(Expression):

    def __init__(self, elements=None):
        self.elements = elements or []


# ------------------------------------------------------------
# Function Call
# ------------------------------------------------------------

class FunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


# ------------------------------------------------------------
# Object Creation
# ------------------------------------------------------------

class ObjectCreation(Expression):

    def __init__(self, class_name, arguments=None):
        self.class_name = class_name
        self.arguments = arguments or []


class MethodCall:
    def __init__(self, obj, method, args):
        self.obj = obj
        self.method = method
        self.args = args


class SwitchStatement(IRNode):

    def __init__(self, variable, cases=None):
        self.variable = variable
        self.cases = cases or []


class SwitchCase(IRNode):

    def __init__(self, value, body=None):
        self.value = value
        self.body = body or []

# ---------------- WHILE LOOP ----------------

class WhileLoop(IRNode):
    def __init__(self, condition, body=None):
        self.condition = condition
        self.body = body or []


# ---------------- BREAK ----------------

class Break(IRNode):
    pass


# ---------------- CONTINUE ----------------

class Continue(IRNode):
    pass


# ---------------- PASS / NO-OP ----------------

class Pass(IRNode):
    pass


# ------------------------------------------------------------
# Attribute Access  (self.balance, obj.field)
# ------------------------------------------------------------

class AttributeAccess(Expression):

    def __init__(self, obj, attribute):
        self.obj = obj
        self.attribute = attribute


# ------------------------------------------------------------
# Self / this reference
# ------------------------------------------------------------

class SelfRef(Expression):
    pass


# ------------------------------------------------------------
# Unary Operation  (-x, not x, ~x)
# ------------------------------------------------------------

class UnaryOp(Expression):

    def __init__(self, operator, operand):
        self.operator = operator  # USub, UAdd, Not, Invert
        self.operand = operand


# ------------------------------------------------------------
# Assignment to an existing target (attribute, index, name)
#
# Distinct from Variable, which declares a NEW local.
# ------------------------------------------------------------

class Assignment(IRNode):

    def __init__(self, target, value):
        self.target = target
        self.value = value


# ------------------------------------------------------------
# Augmented Assignment  (x += 1)
# ------------------------------------------------------------

class AugAssign(IRNode):

    def __init__(self, target, operator, value):
        self.target = target
        self.operator = operator
        self.value = value


# ------------------------------------------------------------
# Class Field / Member Variable
# ------------------------------------------------------------

class Field(IRNode):

    def __init__(self, name, field_type="Object", value=None):
        self.name = name
        self.field_type = field_type
        self.value = value


# ------------------------------------------------------------
# Index Access  (arr[i]) — distinct from DictAccess so generators
# can emit arr[i] instead of arr.get(i) when the target is a list.
# ------------------------------------------------------------

class IndexAccess(Expression):

    def __init__(self, obj, index):
        self.obj = obj
        self.index = index


# ------------------------------------------------------------
# String formatting (f-strings, % formatting, .format)
# ------------------------------------------------------------

class StringInterpolation(Expression):

    def __init__(self, parts=None):
        # parts: list of Constant (literal text) and Expression (holes)
        self.parts = parts or []


# ------------------------------------------------------------
# Ternary / conditional expression  (a if c else b)
# ------------------------------------------------------------

class TernaryOp(Expression):

    def __init__(self, condition, if_true, if_false):
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
