# SPDX-License-Identifier: MIT
"""Owned indexed paths and unreadable inputs behave the same for extensions."""

import tomllib
from pathlib import Path

import pytest

from house import VERSION
from house.core import CannotRunError
from house.providers import get
from tests.conftest import ROOT, commit, git


def test_repo_paths_and_unreadable_input(repo):
    (repo.root / "sample.py").write_text("value = 1\n")
    (repo.root / "untracked.py").write_text("value = 2\n")
    git(repo.root, "add", "sample.py")
    assert repo.tracked("*.py") == (Path("sample.py"),)
    assert repo.read("sample.py") == "value = 1\n"
    (repo.root / "sample.py").unlink()
    with pytest.raises(CannotRunError, match="cannot read"):
        repo.read("sample.py")
    assert repo.tracked() == (Path("sample.py"),)


def test_gitlinks_are_not_owned_source_paths(repo):
    (repo.root / "sample.py").write_text("value = 1\n")
    sha = commit(repo.root)
    git(repo.root, "update-index", "--add", "--cacheinfo", "160000", sha, "dependency")
    assert repo.tracked() == (Path("sample.py"),)


def test_providers_are_language_metadata():
    python = get("python")
    markdown = get("markdown")
    assert python.comment_tokens == ("#",)
    assert markdown.comment_tokens == ("<!--", "-->")
    assert set(python.sync_defaults).isdisjoint({"CMakeLists.txt", ".clang-tidy"})
    assert markdown.spdx_line is None
    assert get("cxx").spdx_line == "// SPDX-License-Identifier: {licence}"


def test_build_and_code_version_agree():
    assert (
        tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        == VERSION
    )
