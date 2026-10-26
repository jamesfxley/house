# SPDX-License-Identifier: MIT
"""Run provider linters only over this checkout's owned indexed sources."""

from house.api import Finding, Result
from house.gates.clang_tidy import tidy
from house.gates.common import Always, no_args, verdict
from house.tools import diagnostic, owned, platform, ruff, run, warning
from house.trees import applicability


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
