# SPDX-License-Identifier: MIT
"""C and C++ source metadata; build, formatter and analyser bindings are separate."""

from house.providers import Language

PROVIDER = Language(
    name="cxx",
    suffixes=(
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hh",
        ".hpp",
        ".hxx",
        ".ipp",
        ".tpp",
        ".inl",
    ),
    test_paths=("tests", "test"),
    comment_tokens=("//", "/*", "*/"),
    inline_suppressions=(r"NOLINT", r"IWYU pragma:"),
    scope_disables=(".clang-tidy",),
    spdx_line="// SPDX-License-Identifier: {licence}",
    version_sites=("CMakeLists.txt:project.VERSION",),
    format_cmd=("clang-format",),
    lint_cmd=("clang-tidy",),
    sync_defaults=(
        ".clang-format",
        ".clang-tidy",
        ".clangd",
        ".editorconfig",
    ),
)
