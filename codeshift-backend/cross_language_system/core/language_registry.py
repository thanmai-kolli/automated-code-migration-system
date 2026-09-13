class LanguageRegistry:

    SUPPORTED_LANGUAGES = {
        "python",
        "java",
        "c",
        "c++",
        "cpp"
    }

    ALIASES = {
        "cpp": "c++"
    }

    @classmethod
    def normalize(cls, lang):
        if not lang:
            return None

        lang = lang.lower().strip()

        return cls.ALIASES.get(lang, lang)

    @classmethod
    def is_supported(cls, lang):
        lang = cls.normalize(lang)
        return lang in cls.SUPPORTED_LANGUAGES