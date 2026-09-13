import re


class RAIITransformer:

    def transform(self, code, raw_lines):

        lines = code.split("\n")

        for line_no in raw_lines:
            line = lines[line_no - 1]

            # Simple replacement pattern
            match = re.search(r"(\w+)\s*\*\s*(\w+)\s*=\s*new\s+(\w+)\((.*?)\);", line)

            if match:
                var_type = match.group(3)
                var_name = match.group(2)
                constructor_args = match.group(4)

                lines[line_no - 1] = (
                    f"std::unique_ptr<{var_type}> {var_name} "
                    f"= std::make_unique<{var_type}>({constructor_args});"
                )

        return "\n".join(lines)
