# SPDX-License-Identifier: MIT
"""Isolated Git repositories with no dependency on global author settings."""

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from house.api import Repo
from house.config import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def without_hosting_environment(monkeypatch):
    # Hosted CI sets GITHUB_*; fixture repositories must not see the outer run.
    for name in [name for name in os.environ if name.startswith("GITHUB_")]:
        monkeypatch.delenv(name)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        encoding="utf-8",
        stderr=subprocess.PIPE,
    )


def init(root):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    return root


def commit(root, summary="tests: create a synthetic repository"):
    git(root, "add", "--all")
    git(root, "commit", "--quiet", "-m", summary)
    return git(root, "rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path):
    init(tmp_path)
    return Repo(
        tmp_path,
        validate({"house": {"platform": ".", "languages": ["python"]}}),
    )


@pytest.fixture
def write(repo):
    def put(name, content):
        path = repo.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        git(repo.root, "add", "--", name)
        return path

    return put


REQUIRE = (
    "[[ci.require]]\ngroup='build'\n"
    "matrix={profile=['default','large'], other=['x']}\n"
)


def axes_config(extra, require=REQUIRE):
    """Return a validated configuration with a build matrix and `extra`."""
    return validate(tomllib.loads(require + extra))
