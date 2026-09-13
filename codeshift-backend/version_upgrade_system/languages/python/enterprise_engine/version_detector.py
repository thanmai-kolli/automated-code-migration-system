import re


class PythonVersionDetector:

    PY2_MARKERS = [
        r'^\s*print\s+[^(=]',
        r'\.iter(items|keys|values)\s*\(',
        r'\bxrange\s*\(',
        r'\braw_input\s*\(',
        r'^\s*except\s+\w+\s*,\s*\w+\s*:',
        r'\bbasestring\b',
        r'\bunicode\s*\(',
        r'^\s*exec\s+[^(]',
        r'<>',
    ]

    # Ordered newest first so the first hit wins.
    PY3_MARKERS = [
        (r'^\s*match\s+.+:\s*$', "Python 3.10+"),
        (r':=', "Python 3.8+"),
        (r'^\s*async\s+def\s', "Python 3.5+"),
        (r'\bf["\']', "Python 3.6+"),
    ]

    def detect(self, code):

        for marker in self.PY2_MARKERS:
            if re.search(marker, code, re.MULTILINE):
                return "Python 2.x"

        for marker, version in self.PY3_MARKERS:
            if re.search(marker, code, re.MULTILINE):
                return version

        return "Python 3.x"
