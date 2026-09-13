from lib2to3.refactor import RefactoringTool, get_fixers_from_package


class Python2GrammarParser:

    def __init__(self):
        fixers = get_fixers_from_package("lib2to3.fixes")
        self.tool = RefactoringTool(fixers)

    def transform(self, code):
        tree = self.tool.refactor_string(code, name="input")
        return str(tree)
