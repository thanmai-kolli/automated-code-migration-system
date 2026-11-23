import re

from version_upgrade_system.core.textscan import mask


class CppVersionDetector:
    """Reports the newest standard the code needs, or that it is pre-C++11."""

    MARKERS = [
        (r"\bconcept\b|\brequires\b|<=>|\bco_await\b|std::span\b", "C++20"),
        (r"\bif\s+constexpr\b|std::optional\b|std::variant\b|\[\[nodiscard\]\]|auto\s*\[", "C++17"),
        (r"std::make_unique\b|\bdecltype\(auto\)", "C++14"),
        (r"\bnullptr\b|\bauto\s+\w+\s*=|\bconstexpr\b|\boverride\b|\busing\s+\w+\s*=|"
         r"std::unique_ptr\b|std::shared_ptr\b|\bfor\s*\([^;()]*(?<!:):(?!:)", "C++11"),
    ]

    def detect(self, code):
        masked = mask(code, "cpp")
        for pattern, version in self.MARKERS:
            if re.search(pattern, masked):
                return version
        return "C++98/03"
