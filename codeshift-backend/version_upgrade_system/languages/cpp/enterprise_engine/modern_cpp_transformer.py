import re


class CppModernizationTransformer:

    def transform(self, code):

        code = self._replace_nullptr(code)
        code = self._replace_auto_ptr(code)
        code = self._modernize_typedef(code)
        code = self._modernize_casts(code)

        code = self._convert_new_to_unique_ptr(code)
        code = self._remove_delete(code)

        # code = self._modernize_loops(code)
        code = self._modernize_iterators(code)

        code = self._modernize_push_back(code)
        code = self._modernize_insert(code)

        code = self._replace_make_pair(code)
        code = self._replace_endl(code)

        # code = self._replace_bind_with_lambda(code)

        code = self._replace_size_t_loops(code)

        # code = self._modernize_vector_initialization(code)

        # code = self._replace_raw_array(code)

        code = self._remove_register_keyword(code)

        code = self._modernize_auto_usage(code)

        # code = self._modernize_bool_comparisons(code)

        code = self._remove_unused_semicolons(code)

        return code


    # -------------------------------------------------
    # NULL → nullptr
    # -------------------------------------------------
    def _replace_nullptr(self, code):

        return re.sub(r"\bNULL\b", "nullptr", code)


    # -------------------------------------------------
    # auto_ptr → unique_ptr
    # -------------------------------------------------
    def _replace_auto_ptr(self, code):

        return re.sub(r"\bauto_ptr<", "unique_ptr<", code)


    # -------------------------------------------------
    # typedef → using
    # -------------------------------------------------
    def _modernize_typedef(self, code):

        return re.sub(
            r"typedef\s+(.+?)\s+(\w+);",
            r"using \2 = \1;",
            code
        )


    # -------------------------------------------------
    # C style cast → static_cast
    # -------------------------------------------------
    def _modernize_casts(self, code):

        return re.sub(
            r"\((int|double|float|long)\)\s*(\w+)",
            r"static_cast<\1>(\2)",
            code
        )


    # -------------------------------------------------
    # raw new → make_unique
    # -------------------------------------------------
    def _convert_new_to_unique_ptr(self, code):

        pattern = r"(\w+)\s*\*\s*(\w+)\s*=\s*new\s+(\w+)\((.*?)\);"

        return re.sub(
            pattern,
            r"auto \2 = std::make_unique<\3>(\4);",
            code
        )


    # -------------------------------------------------
    # remove delete
    # -------------------------------------------------
    def _remove_delete(self, code):

        return re.sub(r"\bdelete\s+\w+;", "// removed delete (RAII)", code)


    # -------------------------------------------------
    # iterator → auto
    # -------------------------------------------------
    def _modernize_iterators(self, code):

        return re.sub(
            r"std::vector<(.+?)>::iterator",
            "auto",
            code
        )


    # -------------------------------------------------
    # push_back → emplace_back
    # -------------------------------------------------
    def _modernize_push_back(self, code):

        return re.sub(
            r"\.push_back\(",
            ".emplace_back(",
            code
        )


    # -------------------------------------------------
    # insert → emplace
    # -------------------------------------------------
    def _modernize_insert(self, code):

        code = re.sub(
            r"\.insert\(\s*make_pair\((.+?),(.+?)\)\s*\)",
            r".emplace(\1,\2)",
            code
        )

        return code


    # -------------------------------------------------
    # make_pair → {}
    # -------------------------------------------------
    def _replace_make_pair(self, code):

        return re.sub(
            r"std::make_pair\((.+?),(.+?)\)",
            r"{\1,\2}",
            code
        )


    # -------------------------------------------------
    # endl → '\n'
    # -------------------------------------------------
    def _replace_endl(self, code):

        code = re.sub(r"<<\s*std::endl", "<< '\\\\n'", code)
        code = re.sub(r"<<\s*endl", "<< '\\\\n'", code)

        return code


    # -------------------------------------------------
    # bind → lambda
    # -------------------------------------------------
    def _replace_bind_with_lambda(self, code):

        return re.sub(
            r"std::bind\((.+?)\)",
            r"[&](auto&&... args){ return \1(args...); }",
            code
        )


    # -------------------------------------------------
    # size_t loop modernization
    # -------------------------------------------------
    def _replace_size_t_loops(self, code):

        pattern = r"for\s*\(\s*size_t\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\w+)\.size\(\)\s*;\s*\w+\+\+\s*\)"

        return re.sub(
            pattern,
            r"for (auto& item : \1)",
            code
        )


    # -------------------------------------------------
    # vector initialization modernization
    # -------------------------------------------------
    def _modernize_vector_initialization(self, code):

        return re.sub(
            r"std::vector<int>\s+(\w+);\s*\1\.push_back\((.+?)\);",
            r"std::vector<int> \1 = {\2};",
            code
        )


    # -------------------------------------------------
    # raw array → vector
    # -------------------------------------------------
    def _replace_raw_array(self, code):

        return re.sub(
            r"int\s+(\w+)\[(\d+)\];",
            r"std::vector<int> \1(\2);",
            code
        )


    # -------------------------------------------------
    # remove deprecated register keyword
    # -------------------------------------------------
    def _remove_register_keyword(self, code):

        return re.sub(r"\bregister\s+", "", code)


    # -------------------------------------------------
    # modernize auto usage
    # -------------------------------------------------
    def _modernize_auto_usage(self, code):

        return re.sub(
            r"std::vector<(.+?)>::iterator\s+(\w+)",
            r"auto \2",
            code
        )


    # -------------------------------------------------
    # simplify bool comparisons
    # -------------------------------------------------
    def _modernize_bool_comparisons(self, code):

        code = re.sub(r"==\s*true", "", code)
        code = re.sub(r"==\s*false", "!", code)

        return code


    # -------------------------------------------------
    # remove stray semicolons
    # -------------------------------------------------
    def _remove_unused_semicolons(self, code):

        return re.sub(r";\s*;", ";", code)