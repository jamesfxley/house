# SPDX-License-Identifier: MIT
"""Run provider linters only over this checkout's owned indexed sources."""

import os

from house.api import Finding, Result
from house.core import CannotRunError
from house.gates.clang_tidy import tidy
from house.gates.common import Always, no_args, verdict
from house.tools import diagnostic, owned, platform, ruff, run, warning
from house.trees import applicability, profile_names

# A matrix cell names the one lint gate it runs; `all` is the tree-less gate.
SELECTION = "HOUSE_MATRIX_LINT_TREE"


def selections(repo):
    """Return the values SELECTION may take: `all` and each C++ lint tree."""
    names = ["all"]
    if "cxx" in repo.config["house"]["languages"]:
        names.extend(profile_names(repo))
    return names


def python_lint(repo):
    paths = owned(repo, (".py",))
    if not paths:
        return Result.ok("0 owned Python files to lint")
    for path in paths:
        repo.read(path)
    config = repo.root / "ruff.toml"
    if not config.is_file():
        config = platform(repo) / "config/ruff.toml"
    done = run(
        [*ruff(repo), "check", "--config", str(config), *map(str, paths)],
        repo.root,
    )
    findings = (
        [Finding(".", 0, "EN-01.2", diagnostic(done))]
        if done.returncode or warning(diagnostic(done))
        else []
    )
    return verdict("EN-01.2", findings, f"{len(paths)} owned Python files linted")


class Lint(Always):
    name = "lint"
    group = "lint"
    rules = ("EN-01.2", "CXX-01.5")

    def __init__(self, tree=None):
        self.provider = "cxx" if tree else ("python", "cxx")
        self.tree = tree
        self.configuration = tree or "all"
        self.name = "lint:" + tree if tree else "lint"

    def deselected(self, repo):
        """Return why the matrix cell leaves this gate to another, or None (AR-23)."""
        value = os.environ.get(SELECTION, "")
        if not value:
            return None
        names = selections(repo)
        if value not in names:
            raise CannotRunError(
                f"{SELECTION}={value!r} names no lint gate; expected one of "
                + ", ".join(names),
            )
        if value == self.configuration:
            return None
        return f"{SELECTION} selects lint tree {value}"

    def applies(self, repo):
        if self.tree:
            return applicability(repo, self.tree)
        return (
            True
            if set(repo.config["house"]["languages"]) & {"cxx", "python"}
            else "no source linter applies"
        )

    def run(self, repo, argv):
        no_args(argv)
        results = []
        if self.tree is None and "python" in repo.config["house"]["languages"]:
            results.append(python_lint(repo))
        if "cxx" in repo.config["house"]["languages"]:
            results.append(tidy(repo, self.tree))
        findings = tuple(finding for result in results for finding in result.findings)
        return Result(
            1 if findings else 0,
            "\n".join(result.message for result in results),
            findings,
        )
