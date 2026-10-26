# SPDX-License-Identifier: MIT
"""Install checkout-local shims and execute commit gates through the pinned runner."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from house.api import Result
from house.core import CannotRunError, read
from house.gates.commits import message_findings
from house.gates.common import verdict
from house.runner import execute

HOOKS = ("pre-commit", "commit-msg")


def setting(repo):
    done = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo.root,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if done.returncode not in {0, 1}:
        raise CannotRunError("cannot read core.hooksPath: " + done.stderr.strip())
    return done.stdout.strip()


def shim(root, name, interpreter):
    return (
        "#!/bin/sh\nexec "
        + shlex.quote(interpreter)
        + " "
        + shlex.quote((root / "dev.py").as_posix())
        + " hook "
        + name
        + ' "$@"\n'
    )


def install(repo):
    current = setting(repo)
    if current not in {"", ".house/hooks"}:
        raise CannotRunError(
            f"core.hooksPath already points to {current}; preserve the existing hooks",
        )
    if not current:
        default = Path(repo.git("rev-parse", "--git-path", "hooks").strip())
        default = repo.root / default
        if any((default / name).exists() for name in HOOKS):
            raise CannotRunError(
                "default Git hooks already exist; preserve them "
                "before changing core.hooksPath",
            )
    interpreter = Path(sys.executable).resolve().as_posix()
    destination = repo.root / ".house/hooks"
    output = {name: shim(repo.root, name, interpreter) for name in HOOKS}
    for name, text in output.items():
        path = destination / name
        if path.exists() and read(path) != text:
            raise CannotRunError(
                f"existing hook differs: {path}; preserve it before reinstalling",
            )
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in output.items():
        path = destination / name
        path.write_text(text, encoding="utf-8", newline="\n")
        path.chmod(path.stat().st_mode | 0o111)
    metadata = {"interpreter": interpreter, "root": repo.root.as_posix()}
    (destination / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    repo.git("config", "--local", "core.hooksPath", ".house/hooks")
    return Result.ok(
        "installed pre-commit and commit-msg through this checkout's pinned dev.py",
    )


def commit_message(_repo, filename):
    path = Path(filename).resolve()
    return verdict(
        "EN-07.2",
        message_findings(read(path), path),
        "commit message checked",
    )


def pre_commit(repo, runner):
    return tuple(
        execute(repo, gate)
        for gate in runner.select(("standards",))
        if gate.name != "commits"
    )


def doctor(repo):
    root = repo.root / ".house/hooks"
    metadata = json.loads(read(root / "metadata.json"))
    interpreter = Path(metadata["interpreter"])
    if not interpreter.is_file() or (
        os.name != "nt" and not os.access(interpreter, os.X_OK)
    ):
        return Result.cannot_run(f"hook interpreter is stale: {interpreter}")
    if metadata["root"] != repo.root.as_posix():
        return Result.cannot_run("hook checkout path is stale; reinstall hooks")
    for name in HOOKS:
        if read(root / name) != shim(repo.root, name, interpreter.as_posix()):
            return Result.cannot_run(
                f"hook {name} differs from the installed interpreter or checkout",
            )
    if setting(repo) != ".house/hooks":
        return Result.cannot_run("core.hooksPath does not select .house/hooks")
    return Result.ok("hook interpreter and checkout paths are current")
