# SPDX-License-Identifier: MIT
"""Command-level verdicts and local extension loading in isolated processes."""

import shutil

import pytest

from tests.conftest import ROOT, commit, git, init
from tests.test_launcher import launch


def test_registered_check_list_and_unknowns():
    result = launch(ROOT, "check", "--list")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(
        "gate\tgroup\tpackage\tconfiguration\tapplicability\n",
    )
    assert (
        "synced-files\tstandards\trepository\tdefault\tapplicable" in result.stdout
    )
    result = launch(ROOT, "gate", "not-registered")
    assert result.returncode == 2
    assert "unknown gate" in result.stderr
    result = launch(ROOT, "check", "--group", "not-registered")
    assert result.returncode == 2
    assert "unknown groups" in result.stderr


def test_extension_uses_pinned_api_and_ci_skip(tmp_path):
    platform = init(tmp_path / "platform-source")
    shutil.copytree(
        ROOT / "house",
        platform / "house",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copyfile(ROOT / "house.toml", platform / "house.toml")
    git(
        platform,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(ROOT / "standard"),
        "standard",
    )
    commit(platform)
    root = init(tmp_path / "consumer")
    shutil.copyfile(ROOT / "house/launcher/dev.py", root / "dev.py")
    # Local path here is a scratch fixture, never a tracked distribution URL.
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(platform),
        "platform",
    )
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "--recursive",
    )
    (root / "sample_gate.py").write_text("""
from house.api import Result
class Sample:
    name = "sample"
    group = "audit"
    rules = ()
    def applies(self, repo):
        return "no matching source"
    def run(self, repo, argv):
        raise AssertionError("a skipped gate must not run")
GATE = Sample()
""")
    declaration = """
[house]
languages = ["python"]
[[gates]]
name = "sample"
module = "sample_gate"
group = "audit"
[groups]
audit = ["sample"]
"""
    (root / "house.toml").write_text(declaration)
    result = launch(root, "check", "--ci", "--group", "audit")
    assert result.returncode == 1
    assert "sample [audit/repository/default]: SKIP" in result.stdout
    assert "no matching source" in result.stdout
    with (root / "house.toml").open("a") as stream:
        stream.write('[ci.skip]\nsample="not applicable in this job"\n')
    result = launch(root, "check", "--ci", "--group", "audit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CI allowance: not applicable in this job" in result.stdout




@pytest.mark.parametrize("phase", ["applies", "run", "import"])
def test_crashing_extension_is_unavailable_and_preserves_other_verdicts(
    tmp_path,
    phase,
):
    root = init(tmp_path / "consumer")
    shutil.copyfile(ROOT / "house/launcher/dev.py", root / "dev.py")
    shutil.copytree(ROOT / "house", root / "platform/house")
    # The pinned contract belongs to the platform, not the synthetic consumer.
    shutil.copytree(ROOT / "standard", root / "platform/standard")
    shutil.copyfile(ROOT / "house.toml", root / "platform/house.toml")
    (root / "house.toml").write_text("""
[house]
languages = ["python"]
[[gates]]
name = "sample"
module = "sample_gate"
group = "audit"
[[gates]]
name = "survivor"
module = "survivor_gate"
group = "audit"
[groups]
audit = ["sample", "survivor"]
""")
    body = """
from house.api import Result
class Sample:
    name = "sample"
    group = "audit"
    rules = ()
    def applies(self, repo):
        return True
    def run(self, repo, argv):
        return Result.ok("still running")
GATE = Sample()
"""
    (root / "survivor_gate.py").write_text(body.replace('"sample"', '"survivor"'))
    if phase == "applies":
        body = body.replace("return True", '{}["missing"]')
    elif phase == "run":
        body = body.replace('return Result.ok("still running")', '{}["missing"]')
    else:
        body += '\n{}["missing"]\n'
    (root / "sample_gate.py").write_text(body)
    result = launch(root, "check", "--group", "audit")
    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "crashed: KeyError: 'missing'" in output
    assert "Traceback (most recent call last)" in output
    if phase != "import":
        assert "survivor [audit/repository/default]: PASS" in output
        assert "still running" in output
        assert "sample [audit/repository/default]: CANNOT_RUN" in output


def declared_gate_consumer(tmp_path, repair):
    root = init(tmp_path / "consumer")
    shutil.copyfile(ROOT / "house/launcher/dev.py", root / "dev.py")
    shutil.copytree(ROOT / "house", root / "platform/house")
    shutil.copytree(ROOT / "standard", root / "platform/standard")
    shutil.copyfile(ROOT / "house.toml", root / "platform/house.toml")
    extra = f'repair = "{repair}"\n' if repair else ""
    (root / "house.toml").write_text(f"""
[house]
languages = ["python"]
[[gates]]
name = "sample"
module = "sample_gate"
group = "audit"
{extra}[[gates]]
name = "survivor"
module = "survivor_gate"
group = "audit"
[groups]
audit = ["sample", "survivor"]
""")
    body = """
from house.api import Result
class Survivor:
    name = "survivor"
    group = "audit"
    rules = ()
    def applies(self, repo):
        return True
    def run(self, repo, argv):
        return Result.ok("still running")
GATE = Survivor()
"""
    (root / "survivor_gate.py").write_text(body)
    return root


def test_an_absent_gate_module_with_a_repair_fails_while_other_gates_run(tmp_path):
    root = declared_gate_consumer(tmp_path, "run regenerate-the-gate")
    result = launch(root, "check", "--group", "audit")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "sample [audit/repository/default]: FAIL" in output
    assert (
        "sample_gate.py:0: EN-01.8: declared gate module sample_gate is missing; "
        "run regenerate-the-gate" in output
    )
    assert "survivor [audit/repository/default]: PASS" in output


def test_an_absent_gate_module_without_a_repair_is_unavailable(tmp_path):
    root = declared_gate_consumer(tmp_path, None)
    result = launch(root, "check", "--group", "audit")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "cannot run: No module named 'sample_gate'" in result.stderr


def test_a_gate_module_missing_its_own_import_stays_unavailable(tmp_path):
    root = declared_gate_consumer(tmp_path, "run regenerate-the-gate")
    (root / "sample_gate.py").write_text("import module_that_does_not_exist\n")
    result = launch(root, "check", "--group", "audit")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "cannot run: No module named 'module_that_does_not_exist'" in (
        result.stderr
    )


@pytest.mark.parametrize(
    "event", ["schedule", "workflow_dispatch", "repository_dispatch"],
)
def test_no_commit_event_passes_standards_in_ci(monkeypatch, event):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    result = launch(ROOT, "check", "--ci", "--group", "standards")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "commits [standards/repository/default]: PASS" in result.stdout
    assert (
        event + " introduces no commits; ranges are checked on push and pull_request"
        in result.stdout
    )
    assert "CANNOT_RUN" not in result.stdout
