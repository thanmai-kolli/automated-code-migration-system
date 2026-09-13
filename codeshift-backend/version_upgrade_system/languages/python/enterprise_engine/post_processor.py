class PostProcessor:

    def apply(self, code):

        lines = code.split("\n")
        new_lines = []

        for line in lines:

            # Remove redundant object inheritance
            if "(object)" in line:
                line = line.replace("(object)", "")

            new_lines.append(line)

        return "\n".join(new_lines)
