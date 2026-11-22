# SPDX-License-Identifier: MIT
"""A lint matrix cell runs the one lint gate HOUSE_MATRIX_LINT_TREE names (AR-23)."""

from types import SimpleNamespace

import pytest

from house.api import Result
from house.gates import lint
from house.gates.lint import SELECTION, Lint
from house.registry import builtin
from house.runner import Runner, execute


@pytest.fixture
def trees(repo, write, monkeypatch):
    repo.config["house"]["languages"] = ["cxx"]
    write(
        "CMakeLists.txt",
        "house_cxx_enable_sanitizers(SAMPLE)\nhouse_cxx_declare_fuzzers_option(SAMPLE)\n",
    )
    ran = []

    def tidy(_repo, tree):
        ran.append(tree)
        return Result.ok(f"tidy {tree}")

    monkeypatch.setattr(lint, "tidy", tidy)
    monkeypatch.delenv(SELECTION, raising=False)
    monkeypatch.setenv("HOUSE_MATRIX_SANITIZE", "address")
    return SimpleNamespace(repo=repo, ran=ran)


def lint_entries(repo):
    return Runner(repo, builtin(repo)).run(("lint",), ci=True)


def test_without_a_selection_every_lint_gate_runs(trees):
    entries = lint_entries(trees.repo)
    assert [entry.name for entry in entries] == ["lint", "lint:sanitize", "lint:fuzz"]
    assert [entry.verdict for entry in entries] == ["PASS"] * 3
    assert trees.ran == [None, "sanitize", "fuzz"]


@pytest.mark.parametrize(
    ("selected", "gate", "tree"),
    [("all", "lint", None), ("fuzz", "lint:fuzz", "fuzz"),
     ("sanitize", "lint:sanitize", "sanitize")],
)
def test_a_selection_runs_one_gate_and_the_rest_are_not_applicable(
    trees, monkeypatch, selected, gate, tree,
):
    monkeypatch.setenv(SELECTION, selected)
    entries = lint_entries(trees.repo)
    assert trees.ran == [tree]
    for entry in entries:
        if entry.name == gate:
            assert entry.verdict == "PASS"
        else:
            assert entry.verdict == "N/A"
            assert entry.result.status == 0
            assert entry.result.message == (
                f"HOUSE_MATRIX_LINT_TREE selects lint tree {selected}"
            )


def test_listing_shows_the_unselected_gates_as_not_applicable(trees, monkeypatch):
    monkeypatch.setenv(SELECTION, "fuzz")
    verdicts = {
        entry.name: entry.verdict
        for entry in Runner(trees.repo, builtin(trees.repo)).listed(("lint",))
    }
    assert verdicts == {
        "lint": "n/a: HOUSE_MATRIX_LINT_TREE selects lint tree fuzz",
        "lint:sanitize": "n/a: HOUSE_MATRIX_LINT_TREE selects lint tree fuzz",
        "lint:fuzz": "applicable",
    }


@pytest.mark.parametrize("selected", ["host", "firmware", "ALL"])
def test_an_unknown_selection_cannot_run(trees, monkeypatch, selected):
    monkeypatch.setenv(SELECTION, selected)
    entry = execute(trees.repo, Lint(), ci=True)
    assert entry.verdict == "CANNOT_RUN"
    assert entry.result.message == (
        f"HOUSE_MATRIX_LINT_TREE={selected!r} names no lint gate; "
        "expected one of all, sanitize, fuzz"
    )
    assert trees.ran == []


def test_python_only_accepts_only_all(repo, monkeypatch):
    monkeypatch.setenv(SELECTION, "all")
    assert Lint().deselected(repo) is None
    monkeypatch.setenv(SELECTION, "fuzz")
    assert execute(repo, Lint()).verdict == "CANNOT_RUN"


def test_the_runner_consults_selection_only_on_the_builtin_lint_gate(
    trees, monkeypatch,
):
    class Other:
        name = "other"
        group = "lint"

        def applies(self, _repo):
            return True

        def deselected(self, _repo):
            raise AssertionError("not part of the gate contract")

        def run(self, _repo, _argv):
            return Result.ok("ran")

    monkeypatch.setenv(SELECTION, "fuzz")
    entry = execute(trees.repo, Other(), ci=True)
    assert entry.verdict == "PASS"
    assert entry.result.message == "ran"
