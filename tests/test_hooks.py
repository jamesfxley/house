# SPDX-License-Identifier: MIT
"""Exercise installed Git hooks through real commits and two platform pins."""

import json
import shutil
import subprocess

import pytest

from house.core import CannotRunError
from house.hooks import install
from house.initialize import render
from tests.conftest import ROOT, commit, git, init
from tests.test_launcher import launch


@pytest.fixture
def hooked_families(tmp_path):
    source = init(tmp_path / "platform source")
    shutil.copytree(
        ROOT / "house",
        source / "house",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for directory in ("agents", "guides", "cxx"):
        shutil.copytree(ROOT / directory, source / directory)
    shutil.copyfile(ROOT / "house.toml", source / "house.toml")
    shutil.copyfile(ROOT / ".gitattributes", source / ".gitattributes")
    git(
        source,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(ROOT / "standard"),
        "standard",
    )
    hook = source / "house/hooks.py"
    hook.write_text(
        hook.read_text().replace(
            "commit message checked",
            "first pinned implementation",
        ),
    )
    first = commit(source)
    hook.write_text(
        hook.read_text().replace(
            "first pinned implementation",
            "second pinned implementation",
        ),
    )
    version = source / "house/__init__.py"
    version.write_text(
        version.read_text().replace('VERSION = "0.1.0"', 'VERSION = "0.1.1"'),
    )
    second = commit(source)
    families = []
    for name, sha, marker in [
        ("first family 'quoted'", first, "first pinned"),
        ("second family", second, "second pinned"),
    ]:
        root = init(tmp_path / name)
        for path in ["docs/README.md", "LICENSE"]:
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("# Ready\n")
        shutil.copyfile(ROOT / ".gitattributes", root / ".gitattributes")
        template = (ROOT / "templates/family/AGENTS.md").read_text()
        (root / "AGENTS.md").write_text(render(template, "platform", "AGENTS.md"))
        shutil.copyfile(ROOT / ".gitignore", root / ".gitignore")
        shutil.copyfile(ROOT / "house/launcher/dev.py", root / "dev.py")
        (root / "README.md").write_text("python3 dev.py check\n")
        (root / "house.toml").write_text(
            '[house]\nlanguages=["python"]\n[sync]\n'
            'files=["dev.py", ".github/workflows/ci.yml"]\n',
        )
        git(
            root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(source),
            "platform",
        )
        git(root / "platform", "checkout", "--quiet", "--detach", sha)
        git(root, "add", "platform")
        git(
            root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--init",
            "--recursive",
        )
        result = launch(root, "sync")
        assert result.returncode == 0, result.stdout + result.stderr
        commit(root)
        result = launch(root, "hook", "install")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "installed pre-commit and commit-msg" in result.stdout + result.stderr
        families.append((root, sha, marker))
    return families


def attempt(root, message, *, bypass=False):
    command = ["git", "commit", "--allow-empty", "-m", message]
    if bypass:
        command.append("--no-verify")
    return subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def test_two_pins_install_and_run_their_own_commit_hooks(hooked_families):
    for root, sha, marker in hooked_families:
        assert git(root / "platform", "rev-parse", "HEAD").strip() == sha
        assert git(root, "config", "--get", "core.hooksPath").strip() == ".house/hooks"
        assert launch(root, "doctor", "--hooks").returncode == 0
        result = attempt(root, "tests: accept the pinned hook")
        assert result.returncode == 0, result.stdout + result.stderr
        assert marker in result.stdout + result.stderr
        for message, expected in [
            ("Bad subject", "EN-07.2"),
            ("tests: add metadata\n\nAudit-Token: value", "EN-07.4"),
        ]:
            result = attempt(root, message)
            assert result.returncode == 1, result.stdout + result.stderr
            assert expected in result.stdout + result.stderr
            assert marker in result.stdout + result.stderr


def test_bypass_is_caught_but_pre_commit_does_not_check_old_commits(hooked_families):
    root, _sha, _marker = hooked_families[0]
    result = attempt(root, "tests: Bypass the hook", bypass=True)
    assert result.returncode == 0, result.stdout + result.stderr
    result = launch(root, "commits", "--root")
    assert result.returncode == 1
    assert "opening lowercase" in result.stdout + result.stderr
    result = attempt(root, "tests: accept a valid next message")
    assert result.returncode == 0, result.stdout + result.stderr
    result = launch(root, "commits", "--root")
    assert result.returncode == 1
    assert "opening lowercase" in result.stdout + result.stderr


def test_pre_commit_runs_standards_and_refuses_sync_drift(hooked_families):
    root, _sha, _marker = hooked_families[0]
    with (root / "dev.py").open("a") as stream:
        stream.write("\n# An edited synced launcher.\n")
    git(root, "add", "dev.py")
    result = attempt(root, "tests: try an edited launcher")
    assert result.returncode == 1
    assert "synced copy differs" in result.stdout + result.stderr


def test_doctor_reports_stale_interpreter(hooked_families):
    root, _sha, _marker = hooked_families[0]
    metadata = root / ".house/hooks/metadata.json"
    value = json.loads(metadata.read_text())
    value["interpreter"] = str(root / "missing-python")
    metadata.write_text(json.dumps(value))
    result = launch(root, "doctor", "--hooks")
    assert result.returncode == 2
    assert "hook interpreter is stale" in result.stdout + result.stderr


def test_install_preserves_existing_hook_configuration(repo):
    git(repo.root, "config", "core.hooksPath", "custom-hooks")
    with pytest.raises(CannotRunError, match=r"core\.hooksPath already points"):
        install(repo)
    assert git(repo.root, "config", "--get", "core.hooksPath").strip() == "custom-hooks"
    git(repo.root, "config", "--unset", "core.hooksPath")
    path = repo.root / ".git/hooks/pre-commit"
    path.write_text("# User hook\n")
    with pytest.raises(CannotRunError, match=r"default Git hooks already exist"):
        install(repo)
    assert path.read_text() == "# User hook\n"


def test_install_preserves_an_edited_generated_hook(repo):
    path = repo.root / ".house/hooks/pre-commit"
    path.parent.mkdir(parents=True)
    path.write_text("# User edit\n")
    with pytest.raises(CannotRunError, match="existing hook differs"):
        install(repo)
    assert path.read_text() == "# User edit\n"


def test_first_commit_and_nested_invocation_use_pinned_hooks(hooked_families):
    root, _sha, marker = hooked_families[0]
    git(root, "checkout", "--orphan", "fresh")
    result = attempt(root / "docs", "tests: create the first commit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker in result.stdout + result.stderr
    assert git(root, "rev-list", "--count", "HEAD").strip() == "1"


def test_empty_explicit_cli_range_is_unavailable(hooked_families):
    root, _sha, _marker = hooked_families[0]
    result = launch(root, "commits", "--range", "")
    assert result.returncode == 2
    assert "expected a two-endpoint" in result.stdout + result.stderr
