# SPDX-License-Identifier: MIT
"""The generic sanitizer tree preserves declared profile behavior (AR-22)."""

import pytest

from house.core import CannotRunError
from house.registry import builtin
from house.trees import applicability, configure_args, profile_names, trees


@pytest.mark.parametrize("value", [None, "", "OFF", "on", "1", "TRUE"])
def test_sanitize_is_declared_but_disabled_without_the_axis(
    repo, write, monkeypatch, value,
):
    write("CMakeLists.txt", "house_cxx_enable_sanitizers(SAMPLE)\n")
    if value is None:
        monkeypatch.delenv("HOUSE_MATRIX_SANITIZE", raising=False)
    else:
        monkeypatch.setenv("HOUSE_MATRIX_SANITIZE", value)
    assert profile_names(repo) == ["sanitize"]
    assert [tree.name for tree in trees(repo)] == ["host"]
    repo.config["house"]["languages"] = ["cxx"]
    assert applicability(repo, "sanitize") == "tree sanitize disabled"
    assert {gate.name for gate in builtin(repo)} >= {"build:sanitize", "lint:sanitize"}


def test_sanitize_uses_the_macro_prefix_and_debug_wins(repo, write, monkeypatch):
    write("CMakeLists.txt", "house_cxx_enable_sanitizers(SAMPLE_LIBRARY)\n")
    monkeypatch.setenv("HOUSE_MATRIX_SANITIZE", "ON")
    monkeypatch.setenv("BUILD_TYPE", "Release")
    repo.config["house"]["languages"] = ["cxx"]
    host, tree = trees(repo)
    assert host.name == "host"
    assert tree.name == "sanitize"
    assert tree.args == ("-DCMAKE_BUILD_TYPE=Debug", "-DSAMPLE_LIBRARY_SANITIZE=ON")
    assert tree.env == {"ASAN_OPTIONS": "detect_leaks=1"}
    assert applicability(repo, "sanitize") is True
    kinds = [
        arg
        for arg in configure_args(repo, tree)
        if arg.startswith("-DCMAKE_BUILD_TYPE=")
    ]
    assert kinds == ["-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_BUILD_TYPE=Debug"]


def test_axis_without_a_declaration_adds_no_tree(repo, monkeypatch):
    monkeypatch.setenv("HOUSE_MATRIX_SANITIZE", "ON")
    assert profile_names(repo) == []
    assert [tree.name for tree in trees(repo)] == ["host"]


@pytest.mark.parametrize("axis", ["", "ON"])
def test_macro_and_explicit_sanitize_name_are_duplicates(
    repo, write, monkeypatch, axis,
):
    write("CMakeLists.txt", "house_cxx_enable_sanitizers(SAMPLE)\n")
    write(
        "synthetic_sanitize.py",
        "from types import SimpleNamespace\n"
        "profile=SimpleNamespace(name='sanitize',enabled=False)\n",
    )
    repo.config["trees"] = [
        {"name": "sanitize", "profile": "synthetic_sanitize:profile"},
    ]
    monkeypatch.setenv("HOUSE_MATRIX_SANITIZE", axis)
    with pytest.raises(
        CannotRunError, match="duplicate host, fuzz or declared tree name",
    ):
        trees(repo)
