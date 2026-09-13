class ChangeTracker:

    def count_changes(self, original_code, upgraded_code):

        original_lines = original_code.split("\n")
        upgraded_lines = upgraded_code.split("\n")

        diff_count = 0

        for o, u in zip(original_lines, upgraded_lines):
            if o.strip() != u.strip():
                diff_count += 1

        return diff_count
