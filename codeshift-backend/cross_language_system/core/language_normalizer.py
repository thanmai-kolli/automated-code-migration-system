class LanguageNormalizer:

    ALIASES = {
        "cpp": "c++",
        "c++": "c++",
        "cplusplus": "c++",

        "c": "c",

        "python": "python",
        "py": "python",

        "java": "java"
    }

    @classmethod
    def normalize(cls, lang: str):
        if not lang:
            return None

        lang = lang.strip().lower()

        return cls.ALIASES.get(lang, lang)