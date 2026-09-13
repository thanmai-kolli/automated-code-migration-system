import difflib


class DiffGenerator:

    def generate(self, original_code, generated_code):

        original_lines = original_code.splitlines(keepends=True)
        generated_lines = generated_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            generated_lines,
            fromfile="source",
            tofile="target",
            lineterm=""
        )

        diff_text = "".join(diff)

        total_changes = self._count_changes(diff_text)

        return {
            "diff_text": diff_text,
            "total_changes": total_changes
        }

    def _count_changes(self, diff_text):

        additions = 0
        deletions = 0

        for line in diff_text.splitlines():

            # Skip metadata lines
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue

            if line.startswith("+"):
                additions += 1

            elif line.startswith("-"):
                deletions += 1

        return additions + deletions