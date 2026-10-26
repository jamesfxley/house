# SPDX-License-Identifier: MIT
"""Shared input handling; an unreadable input never becomes a passing check."""

import os
import subprocess
from pathlib import Path


class CannotRunError(Exception):
    """An input or tool could not establish a verdict."""


def read(path: Path) -> str:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return stream.read()
    except (OSError, UnicodeError) as error:
        raise CannotRunError(f"cannot read {path}: {error}") from error


def git(root: Path, *args: str, env=None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            encoding="utf-8",
            check=False,
            env=env,
        )
    except (OSError, UnicodeError) as error:
        raise CannotRunError(f"cannot run git: {error}") from error
    if result.returncode:
        raise CannotRunError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def foreign_git_environment():
    """Clear repository-local hook variables when inspecting another checkout."""
    names = git(Path.cwd(), "rev-parse", "--local-env-vars").splitlines()
    return {key: value for key, value in os.environ.items() if key not in names}


def tracked(root: Path, platform: str, *patterns: str) -> tuple[Path, ...]:
    rows = git(root, "ls-files", "--stage", "-z", "--", *patterns)
    found = []
    for row in rows.split("\0"):
        if not row:
            continue
        metadata, name = row.split("\t", 1)
        if metadata.split()[0] == "160000":
            continue
        path = Path(name)
        if platform != "." and path.is_relative_to(Path(platform)):
            continue
        found.append(path)
    return tuple(sorted(set(found)))
