# SPDX-License-Identifier: MIT
"""The launcher always executes the platform commit owned by its checkout."""

import os
import shutil
import subprocess
import sys

import pytest

from house import VERSION
from tests.conftest import ROOT, commit, git, init

NEXT_VERSION = "99.0.0"


def set_next_version(platform):
    version = platform / "house/__init__.py"
    text = version.read_text()
    current = f'VERSION = "{VERSION}"'
    assert current in text
    version.write_text(text.replace(current, f'VERSION = "{NEXT_VERSION}"'))


def launch(root, *args, cwd=None, isolated=False):
    flags = ["-I"] if isolated else []
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(
        [sys.executable, *flags, str(root / "dev.py"), *args],
        cwd=cwd or root,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture
def pinned_families(tmp_path):
    platform = init(tmp_path / "platform source")
    shutil.copytree(
        ROOT / "house",
        platform / "house",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (platform / "house.toml").write_text('[house]\nplatform="."\n')
    first = commit(platform)
    set_next_version(platform)
    second = commit(platform, "tests: change the synthetic platform version")
    families = []
    for name, pin in [("first family", first), ("second family", second)]:
        root = init(tmp_path / name)
        shutil.copyfile(ROOT / "house/launcher/dev.py", root / "dev.py")
        (root / "house.toml").write_text('[house]\nlanguages=["python"]\n')
        git(
            root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(platform),
            "platform",
        )
        git(root / "platform", "checkout", "--quiet", "--detach", pin)
        commit(root)
        families.append((root, pin))
    return families


def test_two_real_pins_from_root_nested_and_isolated(pinned_families):
    versions = [VERSION, NEXT_VERSION]
    for (root, pin), expected in zip(pinned_families, versions, strict=True):
        assert git(root / "platform", "rev-parse", "HEAD").strip() == pin
        nested = root / "nested directory" / "deeper"
        nested.mkdir(parents=True)
        for cwd, isolated in [(root, False), (nested, False), (nested, True)]:
            result = launch(root, "--version", cwd=cwd, isolated=isolated)
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == expected


def test_missing_platform_names_the_repair(tmp_path):
    shutil.copyfile(ROOT / "house/launcher/dev.py", tmp_path / "dev.py")
    (tmp_path / "house.toml").write_text("[house]\n")
    result = launch(tmp_path, "check")
    assert result.returncode == 2
    assert result.stderr.strip() == (
        "platform submodule missing: run git submodule update --init --recursive"
    )


@pytest.mark.parametrize(
    "source",
    ["[broken", "house=1", "[house]\nplatform=1", "[house]\nplatform='../outside'"],
)
def test_launcher_invalid_inputs_are_exit_two(tmp_path, source):
    shutil.copyfile(ROOT / "house/launcher/dev.py", tmp_path / "dev.py")
    (tmp_path / "house.toml").write_text(source)
    result = launch(tmp_path, "check")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_old_interpreter_refused_before_toml_import(tmp_path):
    shutil.copyfile(ROOT / "house/launcher/dev.py", tmp_path / "dev.py")
    program = (
        "import runpy,sys;sys.version_info=(3,10,0);sys.modules['tomllib']=None;"
        f"runpy.run_path({str(tmp_path / 'dev.py')!r},run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert "Python 3.11 or later is required" in result.stderr


def test_root_launcher_is_the_canonical_asset():
    assert (ROOT / "dev.py").read_bytes() == (
        ROOT / "house/launcher/dev.py"
    ).read_bytes()
