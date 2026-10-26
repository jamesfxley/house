# SPDX-License-Identifier: MIT
"""Python's comment, suppression and tool conventions."""

from house.providers import Language

PROVIDER = Language(
    name="python",
    suffixes=(".py",),
    test_paths=("tests", "test"),
    comment_tokens=("#",),
    inline_suppressions=(
        r"#\s*noqa\b",
        r"#\s*type:\s*ignore\b",
        r"#\s*pylint:\s*disable\b",
    ),
    scope_disables=(
        "lint.ignore",
        "lint.extend-ignore",
        "lint.per-file-ignores",
        "lint.extend-per-file-ignores",
    ),
    spdx_line="# SPDX-License-Identifier: {licence}",
    version_sites=("pyproject.toml:project.version",),
    format_cmd=(),
    lint_cmd=("ruff", "check"),
    sync_defaults=(
        "ruff.toml",
        ".editorconfig",
    ),
)
