import re


def extract_ast_features(code):

    return {
        "loops": len(re.findall(r'\bfor\b|\bwhile\b', code)),
        "conditionals": len(re.findall(r'\bif\b|\belse\b|\bswitch\b', code)),
        "functions": len(re.findall(r'\bdef\b|\bvoid\b|\bint\b|\bfunction\b', code)),
        "returns": len(re.findall(r'\breturn\b', code))
    }


def compute_ast_similarity(src, tgt):

    s = extract_ast_features(src)
    t = extract_ast_features(tgt)

    score = 0

    for key in s:

        if max(s[key], t[key]) == 0:
            score += 1
        else:
            score += min(s[key], t[key]) / max(s[key], t[key])

    return round(score / len(s), 3)