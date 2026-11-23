"""Text utilities for source rewriting that must not touch strings or comments."""

import re

FILL = "\x01"


def mask(code, language):
    """Same-length copy of `code` with string/char literal contents and comments blanked.

    Quotes and newlines are kept, so regex anchors and spans line up with the original.
    """
    out = list(code)
    i, n = 0, len(code)
    python = language == "python"

    def blank(start, end):
        for k in range(start, end):
            if out[k] != "\n":
                out[k] = FILL

    while i < n:
        ch = code[i]
        if python and ch == "#":
            end = code.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif not python and code.startswith("//", i):
            end = code.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif not python and code.startswith("/*", i):
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            blank(i, end)
            i = end
        elif ch in "\"'":
            triple = python and code.startswith(ch * 3, i)
            quote = ch * 3 if triple else ch
            j = i + len(quote)
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code.startswith(quote, j):
                    break
                if code[j] == "\n" and not triple:
                    break
                j += 1
            blank(i + len(quote), min(j, n))
            i = min(j + len(quote), n)
        else:
            i += 1
    return "".join(out)


def splice(code, edits):
    """Apply non-overlapping (start, end, replacement) edits."""
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        code = code[:start] + replacement + code[end:]
    return code


def matching(text, open_index):
    """Index of the bracket closing the one at `open_index` (on masked text)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    opener = text[open_index]
    closer = pairs[opener]
    depth = 0
    for k in range(open_index, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                return k
    return -1


def sub(pattern, replace, code, language, flags=re.MULTILINE):
    """re.sub over code-only regions. `replace(match, original)` returns the new text.

    The match runs on the masked text; slice `original` with the match spans to
    recover literal contents.
    """
    masked = mask(code, language)
    edits = []
    for match in re.finditer(pattern, masked, flags):
        replacement = replace(match, code)
        if replacement is not None:
            edits.append((match.start(), match.end(), replacement))
    return splice(code, edits)


def group(match, original, index):
    start, end = match.span(index)
    return original[start:end] if start >= 0 else None


def add_include(code, header):
    """Insert `#include <header>` after the last include, if missing."""
    if re.search(rf"#\s*include\s*<{re.escape(header)}>", code):
        return code
    includes = list(re.finditer(r"^\s*#\s*include[^\n]*\n", code, re.MULTILINE))
    position = includes[-1].end() if includes else 0
    return code[:position] + f"#include <{header}>\n" + code[position:]
