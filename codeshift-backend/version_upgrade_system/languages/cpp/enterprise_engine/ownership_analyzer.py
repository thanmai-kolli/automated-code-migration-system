from clang.cindex import CursorKind


class OwnershipAnalyzer:

    def analyze(self, translation_unit):

        raw_allocations = []

        for cursor in translation_unit.cursor.walk_preorder():

            if cursor.kind == CursorKind.CXX_NEW_EXPR:
                raw_allocations.append(cursor.location.line)

        return raw_allocations
