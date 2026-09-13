from difflib import SequenceMatcher


def compute_token_similarity(src_code, tgt_code):

    try:
        similarity = SequenceMatcher(None, src_code, tgt_code).ratio()
        return round(similarity, 3)

    except Exception:
        return 0.5