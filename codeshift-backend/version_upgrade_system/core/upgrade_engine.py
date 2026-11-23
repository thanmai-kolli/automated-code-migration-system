from version_upgrade_system.core.toolchain import normalize_language


def _engine(language):
    if language == "python":
        from version_upgrade_system.languages.python.enterprise_engine.python_upgrader import PythonEnterpriseUpgrader
        return PythonEnterpriseUpgrader()
    if language == "java":
        from version_upgrade_system.languages.java.enterprise_engine.java_upgrader import JavaEnterpriseUpgrader
        return JavaEnterpriseUpgrader()
    if language == "cpp":
        from version_upgrade_system.languages.cpp.enterprise_engine.cpp_upgrader import CppEnterpriseUpgrader
        return CppEnterpriseUpgrader()
    if language == "c":
        from version_upgrade_system.languages.c.enterprise_engine.c_upgrader import CEnterpriseUpgrader
        return CEnterpriseUpgrader()
    return None


class UpgradeEngine:

    def upgrade(self, code, language, test_cases=None):
        engine = _engine(normalize_language(language))
        if engine is None:
            return {"error": f"Unsupported language: {language}"}
        return engine.upgrade(code, test_cases)
