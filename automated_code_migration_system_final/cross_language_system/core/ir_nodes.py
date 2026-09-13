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
    def __init__(self, prompt=None):
        self.prompt = prompt

class TypeCast:
    def __init__(self, target_type, value):
        self.target_type = target_type
        self.value = value


class DictLiteral:
    def __init__(self, keys, values):
        self.keys = keys
        self.values = values

class DictAccess:
    def __init__(self, dictionary, key):
        self.dictionary = dictionary
        self.key = key

class ListAppend:
    def __init__(self, list_obj, value):
        self.list_obj = list_obj
        self.value = value

class SetLiteral:
    def __init__(self, elements):
        self.elements = elements

class ObjectCreation:
    def __init__(self, class_name):
        self.class_name = class_name
        
class DictPut:
    def __init__(self, dictionary, key, value):
        self.dictionary = dictionary
        self.key = key
        self.value = value

class WhileLoop:
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

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

    def __init__(self, name, methods=None, fields=None):
        self.name = name
        self.methods = methods or []
        self.fields = fields or []


# ------------------------------------------------------------
# Function / Method
# ------------------------------------------------------------

class Function(IRNode):

    def __init__(self, name, params=None, body=None, return_type="void"):
        self.name = name
        self.params = params or []
        self.body = body or []
        self.return_type = return_type


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

class CollectionCreation(Expression):
    def __init__(self, collection_type, elements=None):
        self.collection_type = collection_type
        self.elements = elements or []


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