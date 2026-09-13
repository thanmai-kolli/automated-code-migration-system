class CppVersionDetector:

    def detect(self, code):

        if "nullptr" in code or "auto " in code:
            return "C++11+"

        if "auto_ptr" in code:
            return "C++98/03"

        if "typedef struct" in code:
            return "C-style"

        return "Legacy"
