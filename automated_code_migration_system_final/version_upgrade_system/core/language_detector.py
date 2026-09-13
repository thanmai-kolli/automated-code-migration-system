class LanguageDetector:

    def detect(self, code: str) -> str:

        if "public class" in code or "System.out.println" in code:
            return "java"

        if "#include" in code:
            if "std::" in code or "using namespace std" in code:
                return "cpp"
            return "c"

        if "def " in code or "import " in code:
            return "python"

        return "unknown"
