class SymbolTable:

    def __init__(self):
        self.variables = {}
        self.functions = {}

    def register_variable(self, name, var_type):
        self.variables[name] = var_type

    def lookup(self, name):
        return self.variables.get(name)

    def get_variable(self, name):
        return self.variables.get(name, "Object")

    def register_function(self, name, return_type):
        self.functions[name] = return_type

    def get_function(self, name):
        return self.functions.get(name, "void")