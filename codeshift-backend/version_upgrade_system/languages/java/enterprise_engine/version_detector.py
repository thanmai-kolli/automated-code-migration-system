import re

from version_upgrade_system.core.textscan import mask


class JavaVersionDetector:
    """Reports the newest language feature the code relies on."""

    # Ordered newest first so the first hit wins.
    MARKERS = [
        (r"\brecord\s+\w+\s*\(", "Java 16+"),
        (r"\bswitch\b[^{]*\{[^}]*->", "Java 14+"),
        (r"\bvar\s+\w+\s*=", "Java 10+"),
        (r"->|::|\.stream\(\)", "Java 8+"),
        (r"<>|\btry\s*\(", "Java 7+"),
        (r"\benum\b|@Override|\bfor\s*\([^;()]*(?<!:):(?!:)|<\s*[A-Z]\w*\s*>", "Java 5+"),
    ]

    def detect(self, code):
        masked = mask(code, "java")
        for pattern, version in self.MARKERS:
            if re.search(pattern, masked):
                return version
        return "Pre-Java 5 (raw collections, no generics)"
