class TypeMapper:

    # ------------------------
    # PYTHON → JAVA
    # ------------------------
    PYTHON_TO_JAVA = {
        "int": "int",
        "float": "double",
        "bool": "boolean",
        "str": "String",
        "object": "Object",
        "list": "List",
        "dict": "HashMap"
    }

    # ------------------------
    # JAVA → PYTHON
    # ------------------------
    JAVA_TO_PYTHON = {
        "int": "int",
        "Integer": "int",
        "double": "float",
        "Double": "float",
        "boolean": "bool",
        "Boolean": "bool",
        "String": "str",
        "Object": "object",

        "Vector": "list",
        "ArrayList": "list",
        "List": "list",
        "LinkedList": "list",

        "HashMap": "dict",
        "Hashtable": "dict",
        "Map": "dict",
    }

    # ------------------------
    # PYTHON → C++
    # ------------------------
    PYTHON_TO_CPP = {
        "int": "int",
        "float": "double",
        "bool": "bool",
        "str": "std::string",
        "object": "auto",
        "list": "std::vector",
        "dict": "std::map"
    }

    # ------------------------
    # PYTHON → C
    # ------------------------
    PYTHON_TO_C = {
        "int": "int",
        "float": "double",
        "bool": "int",
        "str": "char*",
        "object": "void*"
    }

    def map(self, source_type, source_lang, target_lang):

        source_type = source_type.strip()

        # Remove generics (List<Integer> → List)
        if "<" in source_type:
            source_type = source_type.split("<")[0]

        source_lang = source_lang.lower()
        target_lang = target_lang.lower()

        # ------------------------
        # JAVA → PYTHON
        # ------------------------
        if source_lang == "java" and target_lang == "python":
            return self.JAVA_TO_PYTHON.get(source_type, source_type)

        # ------------------------
        # PYTHON → JAVA
        # ------------------------
        if source_lang == "python" and target_lang == "java":
            return self.PYTHON_TO_JAVA.get(source_type, "Object")

        # ------------------------
        # PYTHON → CPP
        # ------------------------
        if source_lang == "python" and target_lang == "cpp":
            return self.PYTHON_TO_CPP.get(source_type, "auto")

        # ------------------------
        # PYTHON → C
        # ------------------------
        if source_lang == "python" and target_lang == "c":
            return self.PYTHON_TO_C.get(source_type, "void*")

        return source_type