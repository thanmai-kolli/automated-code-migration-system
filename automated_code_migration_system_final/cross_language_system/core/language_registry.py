class LanguageRegistry:

    SUPPORTED = ["python", "java", "cpp", "c"]

    @staticmethod
    def is_supported(language):
        if not language:
            return False
        return language.lower() in LanguageRegistry.SUPPORTED

    @staticmethod
    def list_supported():
        return LanguageRegistry.SUPPORTED