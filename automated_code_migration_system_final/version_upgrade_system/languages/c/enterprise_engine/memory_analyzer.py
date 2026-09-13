class CMemoryAnalyzer:

    def analyze(self, original_code):

        allocations = original_code.count("malloc(")
        frees = original_code.count("free(")

        leaks = max(0, allocations - frees)

        return leaks

    def insert_leak_warning(self, upgraded_code, leak_count):

        if leak_count > 0:

            warning = (
                "\n/*\n"
                "⚠ MEMORY LEAK WARNING:\n"
                f"Detected {leak_count} allocation(s) without matching free().\n"
                "Review ownership and insert free() where necessary.\n"
                "*/\n"
            )

            return warning + upgraded_code

        return upgraded_code