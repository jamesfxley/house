# SPDX-License-Identifier: MIT
"""Pinned family defaults and modules compose without adapters (AR-18)."""

import sys

import pytest

from house.api import Repo
from house.cli import runner
from house.config import load
from house.core import CannotRunError
from house.sync import profile_overlays
from house.trees import profiles
from tests.conftest import commit, git, init

FAMILY = """[house]
languages = ["cxx"]
[context]
config_directories = ["sample"]
[[gates]]
name = "sample-check"
module = "sample_family.gate"
group = "standards"
[[trees]]
name = "sample-host"
profile = "sample_family.gate:host"
"""
MODULE = """from house.api import Result
class Sample:
    name = "sample-check"
    group = "standards"
    rules = ()
    def applies(self, repo):
        return True
    def run(self, repo, argv):
        return Result.ok("family gate ran")
GATE = Sample()
class Host:
    name = "sample-host"
    enabled = True
    cmake_args = ("-DSAMPLE=ON",)
    env = {}
    sync_overlay = {}
host = Host()
"""


@pytest.fixture
def family(repo, write):
    write("house.toml", 'family = "infra"\n[house]\nplatform="."\n')
    write("infra/family.toml", FAMILY)
    write("infra/sample_family/__init__.py", "")
    write("infra/sample_family/gate.py", MODULE)
    yield repo
    for name in list(sys.modules):
        if name == "sample_family" or name.startswith("sample_family."):
            del sys.modules[name]


def test_family_gate_tree_and_defaults_work_directly(family):
    repo = Repo(family.root, load(family.root))
    assert repo.config["context"]["config_directories"] == ["sample"]
    assert repo.config["house"]["languages"] == ["cxx"]
    engine = runner(repo)
    assert engine.named("sample-check").run(repo, ()).message == "family gate ran"
    assert profiles(repo)[0].args == ("-DSAMPLE=ON",)
    assert profile_overlays(repo) == [{}]


def test_repository_overrides_defaults_and_named_declarations(family, write):
    write(
        "house.toml",
        """family = "infra"
[house]
platform = "."
languages = ["python"]
[context]
config_directories = []
[[gates]]
name = "sample-check"
module = "local_gate"
group = "standards"
[[trees]]
name = "sample-host"
profile = "local_gate:host"
""",
    )
    write("local_gate.py", MODULE)
    repo = Repo(family.root, load(family.root))
    assert repo.config["house"]["languages"] == ["python"]
    assert repo.config["context"]["config_directories"] == []
    assert repo.config["gates"] == [
        {"name": "sample-check", "module": "local_gate", "group": "standards"},
    ]
    assert repo.config["trees"] == [
        {"name": "sample-host", "profile": "local_gate:host"},
    ]
    assert "local_gate" not in repo.config["_family_modules"]
    assert profiles(repo)[0].args == ("-DSAMPLE=ON",)
    assert runner(repo).named("sample-check").run(repo, ()).status == 0
    sys.modules.pop("local_gate", None)


@pytest.mark.parametrize("path", ["missing", "infra"])
def test_missing_family_path_or_file_names_the_input(repo, write, path):
    write("house.toml", f'family = "{path}"\n')
    with pytest.raises(CannotRunError, match=path + "/family.toml"):
        load(repo.root)


@pytest.mark.parametrize("path", ["../outside", "/outside", "C:/outside"])
def test_outside_family_paths_refuse(repo, write, path):
    write("house.toml", f'family = "{path}"\n')
    with pytest.raises(CannotRunError, match=r"family:.*(?:relative|inside)"):
        load(repo.root)


def test_symlink_cannot_escape_checkout(repo, write, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (repo.root / "infra").symlink_to(outside, target_is_directory=True)
    write("house.toml", 'family = "infra"\n')
    with pytest.raises(CannotRunError, match=r"family: path outside repository"):
        load(repo.root)


@pytest.mark.parametrize(
    "content",
    [
        'family="nested"',
        '[packages.x]\npath="."',
        '[house]\nplatform="house"',
        '[house]\ncontract="0.1"',
    ],
)
def test_family_forbidden_keys_name_the_file(family, write, content):
    write("infra/family.toml", content)
    with pytest.raises(CannotRunError, match=r"family.toml.*unknown keys"):
        load(family.root)


@pytest.mark.parametrize(
    "content",
    ["import absent_dependency\n", 'raise ImportError("broken")\n'],
)
def test_family_module_import_failure_names_module_and_source(family, write, content):
    write("infra/sample_family/gate.py", content)
    repo = Repo(family.root, load(family.root))
    with pytest.raises(
        CannotRunError,
        match=r"cannot import module sample_family.gate from .*infra",
    ):
        runner(repo)


def test_missing_family_tree_module_names_the_profile(family, write):
    write(
        "infra/family.toml",
        FAMILY.replace("sample_family.gate:host", "sample_family.absent:host"),
    )
    repo = Repo(family.root, load(family.root))
    with pytest.raises(
        CannotRunError,
        match=r"cannot import module sample_family.absent",
    ):
        profiles(repo)


def test_a_real_family_gitlink_loads_its_own_modules(repo, write, tmp_path):
    origin = init(tmp_path / "family origin")
    (origin / "sample_pinned").mkdir()
    (origin / "family.toml").write_text(
        FAMILY.replace("sample_family", "sample_pinned"),
    )
    (origin / "sample_pinned/__init__.py").write_text("")
    (origin / "sample_pinned/gate.py").write_text(MODULE)
    revision = commit(origin)
    git(
        repo.root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(origin),
        "pin",
    )
    write("house.toml", 'family = "pin"\n[house]\nplatform="."\n')
    configured = Repo(repo.root, load(repo.root))
    assert git(repo.root / "pin", "rev-parse", "HEAD").strip() == revision
    assert git(repo.root, "ls-files", "--stage", "pin").startswith("160000 ")
    assert (
        runner(configured).named("sample-check").run(configured, ()).message
        == "family gate ran"
    )
    assert profiles(configured)[0].args == ("-DSAMPLE=ON",)
