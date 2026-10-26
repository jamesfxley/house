# SPDX-License-Identifier: MIT
"""Markdown prose metadata; tool commands need an explicit toolchain binding."""

from house.providers import Language

PROVIDER = Language(
    name="markdown",
    suffixes=(".md",),
    test_paths=(),
    comment_tokens=("<!--", "-->"),
    inline_suppressions=(r"<!--\s*markdownlint-disable-(?:line|next-line)\b",),
    scope_disables=(r"<!--\s*markdownlint-disable\b",),
    spdx_line=None,
    version_sites=(),
    format_cmd=(),
    lint_cmd=(),
    sync_defaults=(".editorconfig",),
)
