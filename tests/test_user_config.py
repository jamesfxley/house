# SPDX-License-Identifier: MIT
"""Prove the per-user configuration resolver on every platform branch (AR-17)."""

import sys
from pathlib import Path

import pytest

from house.api import CONFIG_HOME_VARIABLE, user_config_dir
from house.core import CannotRunError


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """Give the test a home directory and none of the resolver's variables."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in (CONFIG_HOME_VARIABLE, "APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    return home


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
@pytest.mark.usefixtures("machine")
def test_the_override_wins_on_every_platform(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv(CONFIG_HOME_VARIABLE, str(tmp_path / "chosen"))
    assert user_config_dir("sample") == tmp_path / "chosen/sample"


@pytest.mark.parametrize("value", ["relative/path", ".", "", "~/notes"])
@pytest.mark.usefixtures("machine")
def test_a_relative_override_is_refused_naming_the_variable(monkeypatch, value):
    monkeypatch.setenv(CONFIG_HOME_VARIABLE, value)
    with pytest.raises(CannotRunError, match=CONFIG_HOME_VARIABLE):
        user_config_dir("house")


@pytest.mark.usefixtures("machine")
def test_windows_uses_the_roaming_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "ignored"))
    assert user_config_dir("house") == tmp_path / "roaming/house"


@pytest.mark.parametrize("value", [None, ""])
@pytest.mark.usefixtures("machine")
def test_windows_without_the_roaming_directory_refuses(monkeypatch, value):
    monkeypatch.setattr(sys, "platform", "win32")
    if value is not None:
        monkeypatch.setenv("APPDATA", value)
    with pytest.raises(CannotRunError, match=f"APPDATA.*{CONFIG_HOME_VARIABLE}"):
        user_config_dir("house")


def test_macos_uses_application_support(machine, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "ignored"))
    assert user_config_dir("house") == machine / "Library/Application Support/house"


@pytest.mark.usefixtures("machine")
def test_an_absolute_xdg_base_is_used(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert user_config_dir("sample") == tmp_path / "xdg/sample"


@pytest.mark.parametrize("value", ["relative", "", "./here"])
def test_a_relative_xdg_base_is_ignored(machine, monkeypatch, value):
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    assert user_config_dir("sample") == machine / ".config/sample"


def test_linux_keeps_the_established_house_directory(machine):
    assert user_config_dir("house") == machine / ".config/house"
    assert Path.home() == machine


@pytest.mark.usefixtures("machine")
def test_a_missing_home_directory_refuses_naming_the_override(monkeypatch):
    def refuse():
        raise RuntimeError("no home")

    monkeypatch.setattr(Path, "home", refuse)
    with pytest.raises(CannotRunError, match=CONFIG_HOME_VARIABLE):
        user_config_dir("house")


@pytest.mark.parametrize(
    "name",
    ["", "House", "a/b", "a\\b", "..", ".", "a b", "1x", "-x", "x.y", "x/", "é"],
)
@pytest.mark.usefixtures("machine")
def test_a_name_must_be_one_lowercase_segment(name):
    with pytest.raises(CannotRunError, match="one lowercase path segment"):
        user_config_dir(name)


@pytest.mark.parametrize("name", ["house", "sample", "a1", "a_b", "a-b"])
def test_a_valid_name_is_one_segment_under_the_base(machine, name):
    assert user_config_dir(name) == machine / ".config" / name


def test_resolving_creates_nothing(machine):
    user_config_dir("house")
    assert not (machine / ".config").exists()
