"""printf-style format strings: parsing and rewriting between dialects.

C's printf, Java's String.format and Python's % operator share most of one
syntax but differ at the edges (length modifiers, %i/%u, %n, %g). The IR keeps
formats in C syntax; these helpers translate them, and refuse the parts that
have no faithful equivalent instead of guessing.
"""

import re

from cross_language_system.core.errors import UnsupportedConstruct

SPEC = re.compile(
    r"%(?P<flags>[-+ #0]*)(?P<width>\*|\d+)?(?:\.(?P<precision>\*|\d*))?"
    r"(?P<length>hh|h|ll|l|L|z|j|t|q)?(?P<conv>[diouxXeEfFgGaAcspn%])"
)

INTEGER = set("diouxXc")
FLOATING = set("eEfFgGaA")


def tokens(fmt):
    """Split a format into literal strings and spec dicts, in order."""

    out = []
    position = 0
    while True:
        index = fmt.find("%", position)
        if index < 0:
            if position < len(fmt):
                out.append(fmt[position:])
            return out
        if index > position:
            out.append(fmt[position:index])
        match = SPEC.match(fmt, index)
        if not match:
            raise UnsupportedConstruct(f"format specifier {fmt[index:index + 4]!r} is not understood")
        spec = match.groupdict()
        spec["raw"] = match.group(0)
        out.append(spec)
        position = match.end()


def value_count(fmt):
    """How many arguments a format consumes (a * width or precision takes one)."""

    count = 0
    for token in tokens(fmt):
        if isinstance(token, dict) and token["conv"] != "%":
            count += 1 + (token["width"] == "*") + (token["precision"] == "*")
    return count


def _render(spec, conv=None):
    precision = spec["precision"]
    return (
        "%" + spec["flags"] + (spec["width"] or "")
        + ("." + precision if precision is not None else "")
        + (conv or spec["conv"])
    )


def to_python(fmt):
    """C format -> Python % format."""

    out = []
    for token in tokens(fmt):
        if isinstance(token, str):
            out.append(token)
            continue
        conv = token["conv"]
        if conv in "pnaA":
            raise UnsupportedConstruct(f"printf conversion %{conv} has no Python equivalent")
        # Python accepts every C conversion it knows minus the length modifiers.
        out.append(_render(token, {"u": "d", "i": "d", "F": "f"}.get(conv, conv)))
    return "".join(out)


def to_java(fmt):
    """C format -> java.util.Formatter format."""

    out = []
    for token in tokens(fmt):
        if isinstance(token, str):
            out.append(token)
            continue
        conv = token["conv"]
        if conv in "pngGaA":
            # Java's %g never trims trailing zeros, so it prints 32.0000 for
            # C's 32; the others have no counterpart at all.
            raise UnsupportedConstruct(f"printf conversion %{conv} has no exact Java equivalent")
        if token["width"] == "*" or token["precision"] == "*":
            raise UnsupportedConstruct("a * width or precision has no Java equivalent")
        if conv == "%":
            out.append("%%")
            continue
        out.append(_render(token, {"u": "d", "i": "d", "F": "f"}.get(conv, conv)))
    return "".join(out)


PYTHON_SPEC = re.compile(
    r"^(?:(?P<fill>.)?(?P<align>[<>=^]))?(?P<sign>[-+ ])?(?P<alt>#)?(?P<zero>0)?"
    r"(?P<width>\d+)?(?P<grouping>[,_])?(?:\.(?P<precision>\d+))?(?P<type>[bcdeEfFgGnosxX%])?$"
)


def python_spec_to_c(spec, value_is_text=False):
    """A Python format-spec (the part after : in an f-string) -> one C spec.

    Only specs whose meaning is the same in printf are accepted.
    """

    match = PYTHON_SPEC.match(spec)
    if not match:
        raise UnsupportedConstruct(f"format spec {spec!r} is not understood")
    parts = match.groupdict()

    if parts["grouping"] or parts["type"] in ("b", "n", "%", "E", "G") or parts["align"] in ("^", "="):
        raise UnsupportedConstruct(f"format spec {spec!r} has no printf equivalent")
    if parts["fill"] not in (None, " "):
        raise UnsupportedConstruct(f"fill character in {spec!r} has no printf equivalent")

    conv = parts["type"]
    if conv is None:
        if parts["width"] or parts["precision"]:
            # Python's default presentation depends on the value's type (and
            # aligns text left but numbers right), which printf cannot see.
            raise UnsupportedConstruct(f"format spec {spec!r} needs an explicit type")
        conv = "s"
    if conv == "F":
        conv = "f"

    flags = ""
    if parts["align"] == "<":
        flags += "-"
    elif parts["align"] is None and (conv == "s" or value_is_text) and parts["width"]:
        flags += "-"  # Python left-aligns text by default
    if parts["sign"] in ("+", " "):
        flags += parts["sign"]
    if parts["alt"]:
        flags += "#"
    if parts["zero"]:
        flags += "0"

    return (
        "%" + flags + (parts["width"] or "")
        + ("." + parts["precision"] if parts["precision"] is not None else "")
        + conv
    )
