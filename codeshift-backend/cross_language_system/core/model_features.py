"""Shared feature vector for the migration scoring models.

The models are fitted on a pandas DataFrame, so predictions must present the same
named columns in the same order — otherwise scikit-learn silently falls back to
positional matching and warns about missing feature names.

Features come in three groups:

* the engine's own checks on the output (compiles? risk triggers? issues?)
* how far the text moved (diff size and three similarity measures)
* what the SOURCE program does: the constructs whose translation is least
  certain (library calls, collections, strings, floating point, classes,
  input) and the language pair, which no text similarity can see.
"""

import re

import pandas as pd

from cross_language_system.core.ir_nodes import *

FEATURES = [
    "compile_success",
    "risk_score",
    "semantic_issues",
    "diff_count",
    "token_similarity",
    "ast_similarity",
    "structure_similarity",
    "n_statements",
    "n_functions",
    "n_classes",
    "n_loops",
    "n_inputs",
    "n_library_calls",
    "n_collection_ops",
    "n_string_ops",
    "n_float_ops",
    "n_helpers",
    "source_python",
    "source_java",
    "source_c",
    "source_cpp",
    "target_python",
    "target_java",
    "target_c",
    "target_cpp",
]

# Helpers the generators emit to reproduce source semantics the target lacks.
HELPER_PATTERN = re.compile(
    r"\b(_tdiv|_tmod|_char_at|py_floordiv\w*|py_floormod\w*|Math\.floorDiv|Math\.floorMod"
    r"|_fmt_double|fmtG|_format|_read_\w+|_input|_skip_line|_strip|_lower|_upper|_split|charAt\()"
)

STATEMENTS = (Variable, Assignment, AugAssign, PrintStatement, IfStatement, ForLoop, WhileLoop,
              Return, Break, Continue, ListAppend, DictPut, TryCatch)


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(current)
        elif hasattr(current, "__dict__"):
            yield current
            stack.extend(v for v in vars(current).values() if isinstance(v, list) or hasattr(v, "__dict__"))


def construct_profile(program):
    """Counts of the source constructs, read from the annotated IR."""

    defined = set()
    for node in _walk(program):
        if isinstance(node, Function):
            defined.add(node.name)

    profile = {name: 0 for name in (
        "n_statements", "n_functions", "n_classes", "n_loops", "n_inputs",
        "n_library_calls", "n_collection_ops", "n_string_ops", "n_float_ops",
    )}

    for node in _walk(program):
        kind = getattr(node, "inferred_type", None)
        if isinstance(node, STATEMENTS):
            profile["n_statements"] += 1
        if isinstance(node, Function):
            profile["n_functions"] += 1
        elif isinstance(node, Class):
            profile["n_classes"] += 1
        elif isinstance(node, (ForLoop, WhileLoop)):
            profile["n_loops"] += 1
        elif isinstance(node, Input):
            profile["n_inputs"] += 1
        elif isinstance(node, FunctionCall) and node.name not in defined and node.name != "range_array":
            profile["n_library_calls"] += 1
        elif isinstance(node, MethodCall) and node.method != "size":
            profile["n_library_calls"] += 1
        if isinstance(node, (ArrayLiteral, ListAppend, DictPut, DictLiteral, SetLiteral, IndexAccess)) \
                or (isinstance(node, FunctionCall) and node.name == "range_array"):
            profile["n_collection_ops"] += 1
        if kind == "String" or isinstance(node, (StringInterpolation, FormatString)):
            profile["n_string_ops"] += 1
        if kind == "double":
            profile["n_float_ops"] += 1

    return profile


def direction(source, target):
    def key(language):
        return "cpp" if language in ("c++", "cpp") else language
    flags = {f"source_{lang}": 0 for lang in ("python", "java", "c", "cpp")}
    flags.update({f"target_{lang}": 0 for lang in ("python", "java", "c", "cpp")})
    flags[f"source_{key(source)}"] = 1
    flags[f"target_{key(target)}"] = 1
    return flags


def helper_count(code):
    return len(HELPER_PATTERN.findall(code or ""))


def to_frame(features):
    return pd.DataFrame([[features.get(name, 0) for name in FEATURES]], columns=FEATURES)
