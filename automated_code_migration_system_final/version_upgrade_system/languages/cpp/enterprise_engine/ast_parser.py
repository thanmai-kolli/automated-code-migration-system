from clang import cindex


class CppASTParser:

    def __init__(self):
        self.index = cindex.Index.create()

    def parse(self, code):

        with open("temp_input.cpp", "w") as f:
            f.write(code)

        translation_unit = self.index.parse(
            "temp_input.cpp",
            args=["-std=c++17"]
        )

        return translation_unit
