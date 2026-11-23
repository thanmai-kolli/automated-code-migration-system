import re

from version_upgrade_system.core.textscan import mask


class CVersionDetector:
    """Reports the newest standard the code needs, or the legacy idiom it relies on."""

    MARKERS = [
        (r"\b_Generic\b|\b_Static_assert\b|\b_Alignas\b|\b_Noreturn\b", "C11+"),
        (r"\bfor\s*\(\s*(int|long|unsigned|size_t|char)\b|//|\b_Bool\b|\binline\b|<stdbool\.h>", "C99+"),
    ]
    LEGACY = [
        (r"^\s*(int\s+)?\w+\s*\([\w\s,]*\)\s*\n(\s*\w[\w\s\*]*;\s*\n)+\s*\{", "K&R C (pre-ANSI definitions)"),
        (r"^\s*main\s*\(|\bgets\s*\(|\bvoid\s+main\s*\(", "C89/C90"),
    ]

    def detect(self, code):
        masked = mask(code, "c")
        for pattern, version in self.LEGACY:
            if re.search(pattern, masked, re.MULTILINE):
                return version
        for pattern, version in self.MARKERS:
            if re.search(pattern, masked, re.MULTILINE):
                return version
        return "C89/C90"
