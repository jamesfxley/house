# SPDX-License-Identifier: MIT
"""Configure C++ trees and retain complete build evidence."""

import os

from house.api import Finding, Result
from house.core import CannotRunError
from house.gates.compile_db import merge
from house.tools import diagnostic, run, warning
from house.trees import configure_args, trees

COMPLETE = "# dev.py: every source compiled in a clean build"


def configure_tree(repo, tree):
    """Configure `tree`, leaving build.log marked incomplete (AR-24).

    Return the tree's environment and a failed result for configure warnings,
    or None in its place when the configure is clean.
    """
    directory = tree.directory(repo)
    if not directory.resolve().is_relative_to(repo.root.resolve()):
        raise CannotRunError("build tree must remain in the checkout")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "build.log").write_text(
        "# incomplete: configure/build has not finished\n",
        encoding="utf-8",
    )
    env = {**os.environ, **(tree.env or {})}
    configured = run(
        [
            "cmake",
            "-S",
            str(repo.root),
            "-B",
            str(directory),
            "-G",
            "Ninja",
            *configure_args(repo, tree),
        ],
        repo.root,
        env,
    )
    if configured.returncode:
        raise CannotRunError(
            "cmake could not configure " + tree.name + ":\n" + diagnostic(configured),
        )
    if warning(diagnostic(configured)):
        return env, Result.fail(
            Finding(directory, 0, "EN-01.3", diagnostic(configured)),
        )
    return env, None


def configure_only(repo, tree):
    _, failure = configure_tree(repo, tree)
    return failure or Result.ok(tree.name + " configured")


def build_tree(repo, tree):
    env, failure = configure_tree(repo, tree)
    if failure:
        return failure
    directory = tree.directory(repo)
    built = run(["cmake", "--build", str(directory), "--clean-first"], repo.root, env)
    text = diagnostic(built)
    clean = built.returncode == 0
    (directory / "build.log").write_text(
        (COMPLETE + "\n" if clean else "") + text + "\n",
        encoding="utf-8",
    )
    if not clean or warning(text):
        return Result.fail(Finding(directory / "build.log", 0, "EN-01.3", text))
    required_tests = any(
        "test" in package.get("modes", {}).get(tree.name, "build-test")
        for package in repo.packages.values()
    )
    if required_tests:
        tested = run(
            [
                "ctest",
                "--test-dir",
                str(directory),
                "--output-on-failure",
                "--no-tests=error",
            ],
            repo.root,
            env,
        )
        if tested.returncode or warning(diagnostic(tested)):
            return Result.fail(Finding(directory, 0, "EN-04.2", diagnostic(tested)))
    return Result.ok(tree.name + " configured, clean-built and tested")


def build(repo, name=None, *, configure=False):
    """Build and test the selected trees, or with `configure` only configure them.

    Configuring alone writes compile databases but no build evidence.
    """
    selected = [tree for tree in trees(repo) if name is None or tree.name == name]
    if not selected:
        raise CannotRunError(f"unknown build tree: {name}")
    step = configure_only if configure else build_tree
    results = [step(repo, tree) for tree in selected]
    # Merge only after every requested tree completed its step cleanly.
    if all(result.status == 0 for result in results):
        merge(repo)
    failures = tuple(item for result in results for item in result.findings)
    return Result(
        1 if failures else 0,
        "\n".join(result.message for result in results),
        failures,
    )
