class JavaVersionDetector:

    def detect(self, code):

        if ".stream()" in code:
            return "Java 8+"

        if "<>" in code:
            return "Java 7+"

        if "enum " in code:
            return "Java 5+"

        if "Vector" in code or "Hashtable" in code:
            return "Pre-Java 5"

        return "Legacy"
