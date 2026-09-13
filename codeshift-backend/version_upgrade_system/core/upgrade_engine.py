class UpgradeEngine:

    def upgrade(self, code, language, mode="enterprise"):

        language = language.lower()

        # ---------------- PYTHON ----------------
        if language == "python":
            from version_upgrade_system.languages.python.enterprise_engine.python_upgrader import PythonEnterpriseUpgrader
            engine = PythonEnterpriseUpgrader()
            return engine.upgrade(code)

        # ---------------- JAVA ----------------
        elif language == "java":

            from version_upgrade_system.languages.java.enterprise_engine.java_upgrader import JavaEnterpriseUpgrader
            engine = JavaEnterpriseUpgrader()
            return engine.upgrade(code)

        # ---------------- C++ ----------------
        elif language in ["cpp", "c++"]:

            from version_upgrade_system.languages.cpp.enterprise_engine.cpp_upgrader import CppEnterpriseUpgrader
            engine = CppEnterpriseUpgrader()
            return engine.upgrade(code)

        # ---------------- C ----------------
        elif language == "c":

            from version_upgrade_system.languages.c.enterprise_engine.c_upgrader import CEnterpriseUpgrader
            engine = CEnterpriseUpgrader()
            return engine.upgrade(code)

        else:
            return {
                "error": f"Unsupported language: {language}"
            }