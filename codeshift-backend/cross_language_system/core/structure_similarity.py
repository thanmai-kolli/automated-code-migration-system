import re


def extract_structure(code):

    return {
        "functions": len(re.findall(r'\bdef\b|\bvoid\b|\bint\b|\bfunction\b', code)),
        "loops": len(re.findall(r'\bfor\b|\bwhile\b', code)),
        "conditionals": len(re.findall(r'\bif\b|\belse\b|\bswitch\b', code)),
        "returns": len(re.findall(r'\breturn\b', code)),
        "assignments": len(re.findall(r'=', code))
    }


def compute_structure_similarity(src, tgt):

    s = extract_structure(src)
    t = extract_structure(tgt)

    score = 0

    for key in s:

        if max(s[key], t[key]) == 0:
            score += 1
        else:
            score += min(s[key], t[key]) / max(s[key], t[key])

    return round(score / len(s), 3)