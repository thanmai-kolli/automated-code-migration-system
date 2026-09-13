class CVersionDetector:

    def detect(self, code):

        if "gets(" in code:
            return "C89/C90"

        if "void main(" in code:
            return "Pre-ANSI C"

        if "_Generic" in code:
            return "C11+"

        return "Legacy C"