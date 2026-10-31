# SPDX-License-Identifier: MIT
"""Exercise scaffolding through real local pins and fresh checkouts (AR-13)."""

import json
import re
import shutil
import sys
import tomllib

import pytest

from house import core
from house.core import CannotRunError
from house.initialize import Source, initialize
from tests.conftest import ROOT, commit, git, init
from tests.test_launcher import launch


@pytest.fixture
def platform_source(tmp_path):
    source = init(tmp_path / "reviewed platform")
    paths = git(
        ROOT, "ls-files", "--cached", "--others", "--exclude-standard", "-z",
    ).split("\0")
    for name in paths:
        path = ROOT / name
        if not name or name == ".gitmodules" or not path.is_file():
            continue
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    git(
        source,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "--quiet",
        str(ROOT / "standard"),
        "standard",
    )
    git(
        source,
        "config",
        "-f",
        ".gitmodules",
        "submodule.standard.url",
        "https://github.com/jamesfxley/engineering-standard.git",
    )
    commit(source)
    return source


@pytest.fixture
def author(monkeypatch):
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Fixture")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "fixture@example.invalid")


@pytest.mark.usefixtures("author")
def test_python_family_passes_ci_without_cpp_copies_or_allowances(
    repo, platform_source, capsys,
):
    destination = repo.root / "new family"
    result = initialize(repo, destination, "family", ["python"], source=platform_source)
    assert result.status == 0
    checked = launch(destination, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "synced-files [standards/repository/default]: PASS" in checked.stdout
    data = launch(destination, "check", "--list")
    assert "n/a: cxx not declared" in data.stdout
    context = launch(destination, "context", "--json")
    assert context.returncode == 0, context.stderr
    assert "platform/guides/engineering-standard/SKILL.md" in context.stdout.replace(
        "\\\\", "/",
    )
    config = (destination / "house.toml").read_text()
    assert "skip = {}" in config
    assert "clang" not in config
    assert "CMake" not in config
    assert "ARM" not in config
    assert not (destination / ".vscode").exists()
    assert not (destination / ".devcontainer").exists()
    assert "| Work |" in (destination / "AGENTS.md").read_text()
    assert not list(destination.glob(".clang*"))
    assert not (destination / "CMakeLists.txt").exists()
    assert not (destination / "src/__init__.py").exists()
    assert (destination / "sample/__init__.py").is_file()
    imported = core.subprocess.run(
        [sys.executable, "-c", "from sample.value import value; assert value() == 1"],
        cwd=destination, capture_output=True, text=True, check=False,
    )
    assert imported.returncode == 0, imported.stdout + imported.stderr
    assert git(destination, "status", "--porcelain") == ""
    assert git(destination / "platform", "rev-parse", "HEAD") == git(
        platform_source, "rev-parse", "HEAD",
    )
    assert (
        "https://github.com/jamesfxley/house.git"
        in (destination / ".gitmodules").read_text()
    )
    assert not capsys.readouterr().err


@pytest.mark.usefixtures("author")
def test_fresh_generated_clone_preserves_both_pins(repo, platform_source):
    origin = repo.root / "family-origin"
    initialize(repo, origin, "family", ["python"], source=platform_source)
    clone = repo.root / "family-clone"
    git(repo.root, "clone", "--quiet", str(origin), str(clone))
    git(clone, "config", "submodule.platform.url", str(platform_source))
    git(
        clone,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "platform",
    )
    git(clone / "platform", "config", "submodule.standard.url", str(ROOT / "standard"))
    git(
        clone,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "--recursive",
    )
    checked = launch(clone, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "synced-files [standards/repository/default]: PASS" in checked.stdout
    assert git(clone, "status", "--porcelain") == ""


@pytest.mark.parametrize("kind", ["standard", "platform"])
def test_other_kinds_keep_their_dependency_direction(repo, platform_source, kind):
    destination = repo.root / kind
    result = initialize(repo, destination, kind, [], source=platform_source)
    assert result.status == 0
    assert git(destination, "remote") == ""
    assert not (destination / "platform").exists()
    if kind == "standard":
        assert (destination / "check.py").is_file()
        assert not (destination / ".gitmodules").exists()
        assert not (destination / "house.toml").exists()
    else:
        assert (destination / "standard/check.py").is_file()
        assert (destination / "house.toml").is_file()
    assert git(destination, "status", "--porcelain") == ""


def test_init_preserves_nonempty_destination_and_refuses_dirty_pin(
    repo, write, platform_source,
):
    write("keep.txt", "User content\n")
    with pytest.raises(
        CannotRunError, match="empty destination; existing files are preserved",
    ):
        initialize(repo, repo.root, "family", ["python"], source=platform_source)
    assert repo.read("keep.txt") == "User content\n"
    (platform_source / "user-edit.txt").write_text("Uncommitted\n")
    with pytest.raises(CannotRunError, match="clean, committed platform source"):
        initialize(
            repo, repo.root / "new", "family", ["python"], source=platform_source,
        )
    assert not (repo.root / "new").exists()


@pytest.mark.usefixtures("author")
def test_scaffold_under_autocrlf_true_has_lf_attributes(
    repo, platform_source, monkeypatch,
):
    errors = []
    original = core.subprocess.run
    def record(*args, **kwargs):
        done = original(*args, **kwargs)
        errors.append(done.stderr or "")
        return done
    monkeypatch.setattr(core.subprocess, "run", record)
    # Command-scope config also reaches every nested git invocation.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.autocrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    destination = repo.root / "lf-family"
    initialize(repo, destination, "family", ["python"], source=platform_source)
    assert not any("warning:" in error.lower() for error in errors), errors
    assert (destination / ".gitattributes").read_bytes() == b"* text=auto eol=lf\n"
    assert (
        git(destination, "check-attr", "eol", "--", "README.md").strip()
        == "README.md: eol: lf"
    )
    assert git(destination, "status", "--porcelain") == ""


@pytest.mark.usefixtures("author")
def test_cpp_scaffold_uses_shipped_helpers_and_relocated_consumer(
    repo, platform_source,
):
    destination = repo.root / "cpp-family"
    initialize(repo, destination, "family", ["cxx"], source=platform_source)
    formatted = launch(destination, "format", "--check")
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr
    checked = launch(destination, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "installed and relocated consumers built: root" in checked.stdout


@pytest.mark.parametrize("languages", [["markdown"], ["markdown", "python"]])
@pytest.mark.usefixtures("author")
def test_documentation_template_matches_declared_providers(
    repo, platform_source, languages,
):
    destination = repo.root / "documented-family"
    initialize(repo, destination, "family", languages, source=platform_source)
    checked = launch(destination, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    specification = (destination / "docs/technical-specification.md").read_text()
    if "python" in languages:
        assert "The sample returns one" in specification
        assert (destination / "tests/test_sample.py").is_file()
    else:
        assert "relative documentation link resolves" in specification
        assert not (destination / "tests").exists()
        document = destination / "docs/README.md"
        document.write_text(document.read_text() + "\n[Broken](absent.md)\n")
        refused = launch(destination, "check", "--ci")
        assert refused.returncode == 1
        assert "EN-03.8: broken link: absent.md" in refused.stdout


@pytest.fixture
def infrastructure_source(tmp_path, platform_source):
    # A family infrastructure repository that pins House one level down.
    source = init(tmp_path / "infrastructure source")
    (source / "README.md").write_text("# Synthetic family infrastructure\n")
    (source / "family.toml").write_text(
        '[context]\nconfig_directories=["sample"]\n',
    )
    git(
        source,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "--quiet",
        str(platform_source),
        "house",
    )
    git(source / "house", "config", "submodule.standard.url", str(ROOT / "standard"))
    git(
        source / "house",
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "standard",
    )
    commit(source)
    return source


def rendered(destination):
    # Owned, indexed outputs only; pinned checkouts and caches are not rendered.
    names = git(destination, "ls-files", "-z").split("\0")
    return {
        destination / name: (destination / name).read_text(encoding="utf-8")
        for name in names
        if name and (destination / name).is_file()
    }


@pytest.mark.usefixtures("author")
def test_nested_family_pins_infrastructure_that_contains_the_platform(
    repo, platform_source, infrastructure_source,
):
    destination = repo.root / "nested family"
    result = initialize(
        repo, destination, "family", ["python"],
        source=Source(infrastructure_source, "infra", "infra/house"),
    )
    assert result.status == 0
    checked = launch(destination, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    context = launch(destination, "context", "--json")
    assert "infra/house/guides/engineering-standard/SKILL.md" in (
        context.stdout.replace("\\\\", "/")
    )
    config = (destination / "house.toml").read_text()
    assert 'platform = "infra/house"' in config
    assert 'family = "infra"' in config
    texts = rendered(destination)
    assert "Before work, read `infra/agents/AGENTS.md`;" in (
        texts[destination / "AGENTS.md"]
    )
    assert "| Work |" not in texts[destination / "AGENTS.md"]
    assert texts[destination / "AGENTS.md"].endswith(
        "never create `CLAUDE.md` or `CLAUDE.local.md`\n",
    )
    assert '"infra/house/config/ruff.toml"' in texts[destination / "ruff.toml"]
    for path, text in texts.items():
        assert "@PLATFORM@" not in text, path
        assert "`platform/" not in text, path
        assert "(platform/" not in text, path
    assert not (destination / "platform").exists()
    assert git(destination / "infra", "rev-parse", "HEAD") == git(
        infrastructure_source, "rev-parse", "HEAD",
    )
    assert git(destination / "infra/house", "rev-parse", "HEAD") == git(
        platform_source, "rev-parse", "HEAD",
    )
    assert git(destination, "status", "--porcelain") == ""


@pytest.mark.usefixtures("author")
def test_default_paths_render_the_platform_directory(repo, platform_source):
    destination = repo.root / "default family"
    initialize(repo, destination, "family", ["python"], source=platform_source)
    texts = rendered(destination)
    assert "`platform/agents/AGENTS.md`" in texts[destination / "AGENTS.md"]
    assert "](platform/standard/README.md)" in texts[destination / "CONTRIBUTING.md"]
    assert 'extend = "platform/config/ruff.toml"' in texts[destination / "ruff.toml"]
    assert all("@PLATFORM@" not in text for text in texts.values())


@pytest.mark.usefixtures("author")
def test_the_default_scaffold_declares_no_gate_repair(repo, platform_source):
    destination = repo.root / "default family"
    initialize(repo, destination, "family", ["python"], source=platform_source)
    texts = rendered(destination)
    assert "repair" not in texts[destination / "house.toml"]


@pytest.mark.usefixtures("author")
def test_the_initial_commit_subject_names_the_tooling_area(repo, platform_source):
    destination = repo.root / "default family"
    initialize(repo, destination, "family", ["python"], source=platform_source)
    subject = git(destination, "log", "-1", "--format=%s").strip()
    assert subject == "tooling: scaffold the initial repository"


@pytest.mark.parametrize(
    "case",
    [
        ("infra", "other/house", "inside the pin path"),
        ("/infra", "/infra/house", "relative"),
        ("infra", "infra/../house", "relative"),
        ("infra", "infra\\house", "forward slashes"),
    ],
)
def test_invalid_path_options_are_refused(repo, infrastructure_source, case):
    pin_path, platform_path, expected = case
    with pytest.raises(CannotRunError, match=re.escape(expected)):
        initialize(
            repo, repo.root / "refused", "family", ["python"],
            source=Source(infrastructure_source, pin_path, platform_path),
        )
    assert not (repo.root / "refused").exists()


@pytest.mark.parametrize(
    ("languages", "pin_path"),
    [
        (["python"], "docs"),
        (["python"], "docs/infra"),
        (["python"], ".git"),
        (["python"], ".github"),
        (["python"], ".github/infra"),
        (["python"], "tests"),
        (["python"], "Tests"),
        (["python"], "sample"),
        (["python"], "house.toml"),
        (["python"], "dev.py"),
        (["python"], "LICENSE"),
        (["python"], ".gitmodules"),
        (["cxx"], "include"),
        (["cxx"], "src"),
        (["cxx"], "CMakeLists.txt"),
    ],
)
def test_a_pin_path_that_collides_with_scaffold_output_is_refused(
    repo, platform_source, languages, pin_path,
):
    destination = repo.root / "refused"
    with pytest.raises(CannotRunError, match="collides with the scaffold's own"):
        initialize(
            repo, destination, "family", languages,
            source=Source(platform_source, pin_path, pin_path),
        )
    assert not destination.exists()


@pytest.mark.parametrize("option", [(" ", None), ("", None), ("infra", "")])
def test_an_empty_path_option_is_refused_not_defaulted(
    repo, platform_source, option,
):
    destination = repo.root / "refused"
    pin_path, platform_path = option
    with pytest.raises(CannotRunError, match="must be a relative subdirectory"):
        initialize(
            repo, destination, "family", ["python"],
            source=Source(platform_source, pin_path, platform_path),
        )
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["standard", "platform"])
def test_path_options_apply_only_to_families(repo, platform_source, kind):
    with pytest.raises(CannotRunError, match="only for --kind family"):
        initialize(
            repo, repo.root / kind, kind, [], source=Source(platform_source, "infra"),
        )


@pytest.mark.usefixtures("author")
def test_nested_scaffold_refuses_a_template_that_hardcodes_the_platform(
    repo, infrastructure_source,
):
    agents = infrastructure_source / "house/templates/family/AGENTS.md"
    agents.write_text(agents.read_text() + "| Extra | `platform/extra.md` |\n")
    git(infrastructure_source / "house", "commit", "--quiet", "-am", "docs: extra")
    commit(infrastructure_source, "house: move the pin")
    expected = re.escape("AGENTS.md hardcodes platform/")
    with pytest.raises(CannotRunError, match=expected):
        initialize(
            repo, repo.root / "refused", "family", ["python"],
            source=Source(infrastructure_source, "infra", "infra/house"),
        )


@pytest.mark.parametrize("complete", [True, False])
@pytest.mark.usefixtures("author")
def test_family_sync_defaults_remain_referred_unless_languages_add_files(
    repo, infrastructure_source, complete,
):
    inherited = [
        ".editorconfig",
        ".github/ISSUE_TEMPLATE/defect.yml",
        ".github/pull_request_template.md",
        ".github/workflows/ci.yml",
    ]
    if complete:
        inherited.append("dev.py")
    family = infrastructure_source / "family.toml"
    family.write_text("[sync]\nfiles = " + json.dumps(inherited) + "\n")
    commit(infrastructure_source)
    destination = repo.root / "referred files"
    initialize(
        repo, destination, "family", ["python"],
        source=Source(infrastructure_source, "infra", "infra/house"),
    )
    config = tomllib.loads((destination / "house.toml").read_text())
    if complete:
        assert "sync" not in config
    else:
        assert config["sync"]["files"] == sorted([*inherited, "dev.py"])
    checked = launch(destination, "check", "--ci")
    assert checked.returncode == 0, checked.stdout + checked.stderr
