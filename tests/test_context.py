# SPDX-License-Identifier: MIT
"""Resolve pinned context without agent installation (AR-9, AR-17)."""

import json
import shutil
from pathlib import Path

import pytest

from house.cli import main
from house.context import bindings, render
from house.core import CannotRunError
from house.guides import GUIDE_NAMES


@pytest.fixture
def assets(repo, write, tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_CONFIG_HOME", str(tmp_path / "empty-config"))
    repo.config["house"].update(platform="platform", languages=["python", "cxx"])
    write("house.toml", '[house]\nplatform="platform"\nlanguages=["python","cxx"]\n')
    write("AGENTS.md", "# Root instructions\n")
    write("platform/agents/AGENTS.md", "# Shared agreements\n")
    for name in GUIDE_NAMES:
        write(
            f"platform/guides/{name}/SKILL.md",
            (
                f'---\nname: {name}\ndescription: "Rich trigger for {name}."\n'
                f'---\n# {name}\nPinned fixture rule.\n'
            ),
        )
    write("platform/standard/engineering/00-conformance.md", "# Engineering\n")
    write("platform/standard/cxx/00-conformance.md", "# C++\n")
    return repo


def test_context_keeps_instruction_order_override_and_pin(assets, write, monkeypatch):
    write("src/AGENTS.md", "# Intermediate\n")
    write("src/deep/AGENTS.md", "# Shadowed\n")
    write("src/deep/AGENTS.override.md", "# Specific\n")
    source = write("src/deep/unit.cpp", "int value();\n")
    monkeypatch.chdir(source.parent)
    data = bindings(assets, Path("unit.cpp"))
    assert data["instructions"] == [
        str(assets.root / path)
        for path in ("AGENTS.md", "src/AGENTS.md", "src/deep/AGENTS.override.md")
    ]
    assert all("platform/guides/" in path for path in data["guides"])
    assert any("cxx-standard" in path for path in data["guides"])
    assert any("standard/cxx/" in path for path in data["rules"])
    assert "Pinned platform:" in render(data)


def test_context_at_root_includes_root_instructions_and_python_omits_cpp(assets):
    assets.config["house"]["languages"] = ["python"]
    data = bindings(assets)
    assert data["instructions"] == [str(assets.root / "AGENTS.md")]
    assert not any("cxx" in path for path in data["guides"])
    assert not any("standard/cxx" in path for path in data["rules"])


def test_context_rejects_outside_path_and_missing_pin_inputs(assets):
    with pytest.raises(CannotRunError, match="escapes checkout"):
        bindings(assets, assets.root.parent / "outside")
    (assets.root / "platform/guides/review/SKILL.md").unlink()
    with pytest.raises(CannotRunError, match="cannot read"):
        bindings(assets)


def test_context_uses_custom_platform_and_reports_local_notes(
    assets, tmp_path, monkeypatch,
):
    shutil.move(assets.root / "platform", assets.root / "tools")
    assets.config["house"]["platform"] = "tools"
    notes = tmp_path / "user/house/local.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Machine notes\n")
    monkeypatch.setenv("HOUSE_CONFIG_HOME", str(tmp_path / "user"))
    data = bindings(assets)
    assert data["platform"] == str(assets.root / "tools")
    assert data["local_notes"] == [str(notes)]
    assert all("/tools/guides/" in path for path in data["guides"])


def test_context_reports_the_config_directories_in_text(assets, tmp_path):
    assets.config["context"]["config_directories"] = ["sample", "other"]
    lines = render(bindings(assets)).splitlines()
    base = tmp_path / "empty-config"
    assert f"House config directory: {base / 'house'}" in lines
    assert "local.md: absent" in lines
    assert f"sample config directory: {base / 'sample'}" in lines
    assert f"other config directory: {base / 'other'}" in lines


def test_context_reports_present_notes_and_registered_directories_in_json(
    assets, write, tmp_path, capsys,
):
    write(
        "house.toml",
        '[house]\nplatform="platform"\nlanguages=["python","cxx"]\n'
        '[context]\nconfig_directories=["sample"]\n',
    )
    notes = tmp_path / "empty-config/house/local.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Machine notes\n")
    assert main(assets.root, ["context", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["house_config"] == {
        "directory": str(tmp_path / "empty-config/house"),
        "local_notes_present": True,
    }
    assert data["config_directories"] == {
        "sample": str(tmp_path / "empty-config/sample"),
    }
    assert data["local_notes"] == [str(notes)]


def test_context_without_registered_directories_lists_only_house(assets, capsys):
    assert main(assets.root, ["context", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["config_directories"] == {}
    assert main(assets.root, ["context"]) == 0
    assert " config directory: " in capsys.readouterr().out


def test_context_refuses_a_relative_override_with_exit_two(
    assets, monkeypatch, capsys,
):
    monkeypatch.setenv("HOUSE_CONFIG_HOME", "relative")
    assert main(assets.root, ["context"]) == 2
    assert "HOUSE_CONFIG_HOME" in capsys.readouterr().err
