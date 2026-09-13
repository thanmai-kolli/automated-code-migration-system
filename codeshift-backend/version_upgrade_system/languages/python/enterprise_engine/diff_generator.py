import difflib


class DiffGenerator:

    def generate(self, original_code, upgraded_code):

        original_lines = original_code.splitlines()
        upgraded_lines = upgraded_code.splitlines()

        diff = list(difflib.unified_diff(
            original_lines,
            upgraded_lines,
            fromfile="original.py",
            tofile="upgraded.py",
            lineterm=""
        ))

        changed_lines = []

        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                changed_lines.append({
                    "type": "added",
                    "content": line[1:]
                })
            elif line.startswith("-") and not line.startswith("---"):
                changed_lines.append({
                    "type": "removed",
                    "content": line[1:]
                })

        return {
            "diff_text": "\n".join(diff),
            "changed_lines": changed_lines,
            "total_changes": len(changed_lines)
        }
