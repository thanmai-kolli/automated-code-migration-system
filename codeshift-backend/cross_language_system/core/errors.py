"""Errors the translation pipeline raises on purpose."""


class UnsupportedConstruct(Exception):
    """The input uses something the engine cannot translate faithfully.

    Raised instead of emitting code that compiles but behaves differently: a
    translation that fails loudly costs the user a manual rewrite, one that
    silently changes behaviour costs them a bug they have to find first.
    """
