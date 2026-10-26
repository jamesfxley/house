# SPDX-License-Identifier: MIT
"""Suppression ceilings count languages and ratchet without a register (EN-00.6)."""

import pytest

from house.gates.deviations import Deviations
from house.runner import execute
from tests.test_standards import assert_fault, assert_pass


@pytest.mark.parametrize(
    "case",
    [
        ("x.py", "# ruff: noqa: F401\nimport os  # noqa: E501\n", "python", 2),
        ("x.cpp", "// NOLINTBEGIN(misc-x)\nint f(); // NOLINT(misc-x)\n", "cxx", 2),
        ("x.sh", "# shellcheck disable=SC2034\n", "shell", 1),
        ("x.md", "<!-- markdownlint-disable MD013 -->\n", "markdown", 1),
    ],
)
def test_language_count_and_ratchet(repo, write, case):
    name, text, language, count = case
    write(name, text)
    assert_fault(repo, Deviations(), f"{language}: {count} exceeds its ceiling of 0")
    path = write("docs/deviation-budget.txt", f"# Reason.\n{language} = 3\n")
    entry = execute(repo, Deviations())
    assert entry.result.status == 0
    assert f"lower {language} to {count}" in entry.result.message
    assert_pass(repo, Deviations(), ("--ratchet",))
    assert path.read_text() == f"# Reason.\n{language} = {count}\n"


def test_configuration_and_inline_share_one_ceiling(repo, write):
    write("ruff.toml", '[lint]\nignore=["F401"]\n')
    write("x.py", "import os  # noqa: E501\n")
    write("docs/deviation-budget.txt", "python = 1\n")
    assert_fault(repo, Deviations(), "python: 2 exceeds its ceiling of 1")
    write("docs/deviation-budget.txt", "python = 2\n")
    # Register contents and approval judgements are review, never row parsing.
    write("docs/deviations.md", "Prose register; no table.\n")
    assert_pass(repo, Deviations())


def test_strings_are_not_suppressions(repo, write):
    write("x.py", 'fixture = "# noqa"\n"""# noqa"""\n')
    write("x.cpp", 'const char* value = "NOLINT";\n')
    assert_pass(repo, Deviations())


@pytest.mark.parametrize(
    "budget", ["python.inline = 1", "python = -1", "python = 1\npython = 2"],
)
def test_old_or_invalid_budget_refuses(repo, write, budget):
    write("docs/deviation-budget.txt", budget)
    assert_fault(repo, Deviations(), "malformed or duplicate budget")


def test_ratchet_never_raises_and_is_atomic_across_packages(repo, write):
    repo.config["packages"] = {"alpha": {"path": "alpha"}, "beta": {"path": "beta"}}
    path = write("alpha/docs/deviation-budget.txt", "python = 3\n")
    write("beta/x.py", "import os  # noqa: F401\n")
    result = execute(repo, Deviations(), ("--ratchet",)).result
    assert result.status == 1
    assert "exceeds its ceiling of 0" in str(result)
    assert path.read_text() == "python = 3\n"


def test_cpp_and_shell_configuration_counts(repo, write):
    write("src/.clang-tidy", "InheritParentConfig: true\nChecks: '-misc-x,-misc-y'\n")
    write("scripts/.shellcheckrc", "disable=SC2034,SC2086\n")
    assert_fault(repo, Deviations(), "cxx: 2 exceeds")
    write("docs/deviation-budget.txt", "cxx = 2\nshell = 2\n")
    assert_pass(repo, Deviations())


def test_root_cpp_additions_count_beyond_the_pinned_configuration(repo, write):
    write("config/.clang-tidy", "Checks: '-*,misc-x,-misc-base'\n")
    write(
        ".clang-tidy",
        "# -comment-is-not-a-check\nChecks: '-*,misc-x,-misc-base,-misc-local'\n",
    )
    assert_fault(repo, Deviations(), "cxx: 1 exceeds")
    write("docs/deviation-budget.txt", "cxx = 1\n")
    assert_pass(repo, Deviations())


def test_cpp_region_endpoints_both_count(repo, write):
    write("x.cpp", "// NOLINTBEGIN(misc-x)\nint f();\n// NOLINTEND(misc-x)\n")
    assert_fault(repo, Deviations(), "cxx: 2 exceeds")
    write("docs/deviation-budget.txt", "cxx = 2\n")
    assert_pass(repo, Deviations())


@pytest.mark.parametrize(
    "pragma", ["keep", "export", "always_keep", "begin_keep", "begin_exports"],
)
def test_iwyu_pragmas_are_counted(repo, write, pragma):
    write("x.hpp", f'#include "a.h" // IWYU pragma: {pragma}\n')
    assert_fault(repo, Deviations(), "cxx: 1 exceeds")
    write("docs/deviation-budget.txt", "cxx = 1\n")
    assert_pass(repo, Deviations())


@pytest.mark.parametrize(
    "directive", ["# type: ignore[attr-defined]", "# pylint: disable=unused-import"],
)
def test_python_directives_are_counted(repo, write, directive):
    write("x.py", directive + "\n")
    assert_fault(repo, Deviations(), "python: 1 exceeds")
    write("docs/deviation-budget.txt", "python = 1\n")
    assert_pass(repo, Deviations())


def test_unused_ignore_patterns_do_not_consume_budget(repo, write):
    write("ruff.toml", '[lint.per-file-ignores]\n"**/absent.py"=["C901"]\n')
    write("sample.py", "value = 1\n")
    assert_pass(repo, Deviations())
