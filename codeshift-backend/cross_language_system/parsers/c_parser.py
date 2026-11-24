from cross_language_system.core.ir_nodes import Function, Program
from cross_language_system.parsers.c_like_parser import CLikeParser


C_FAMILY = {"c", "cpp", "c++"}


class CParser:
    """C source: a real IR from CLikeParser, or the raw text for a C-family target.

    Converting to C++ is a text rewrite, so the source is kept whole and in its
    order; macros, comments and declarations stay where they were.
    """

    def __init__(self, target=None):
        self.target = (target or "").lower()

    def parse(self, code):

        if self.target and self.target not in C_FAMILY:
            return CLikeParser().parse(code)

        return Program([Function("source", [], code, "raw")])
