import difflib


class DiffGenerator:

    def generate(self, original, upgraded):

        diff = list(difflib.unified_diff(
            original.splitlines(),
            upgraded.splitlines(),
            fromfile="original.cpp",
            tofile="upgraded.cpp",
            lineterm=""
        ))

        return {
            "diff_text": "\n".join(diff),
            "total_changes": len(diff)
        }
