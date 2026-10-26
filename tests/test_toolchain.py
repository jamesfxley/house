# SPDX-License-Identifier: MIT
"""Check explicit preparation, version pins and missing prerequisites (AR-11)."""

import os
import shutil
from types import SimpleNamespace

import pytest

from house import toolchain
from house.core import CannotRunError
from tests.conftest import ROOT


@pytest.fixture
def declared(repo, write):
    shutil.copyfile(ROOT / "toolchains.toml", repo.root / "toolchains.toml")
    write("config/ruff.toml", 'required-version = "==0.16.4"\n')
    write("config/.clang-version", "20\n")
    write("pyproject.toml", '[dependency-groups]\ndev=["pytest==9.1.1"]\n')
    return repo


def test_manifest_selects_provider_tools_and_explicit_profiles(declared):
    assert set(toolchain.declarations(declared)) == {"ruff"}
    tools = toolchain.declarations(declared, ("tests",))
    assert tools["ruff"]["version"] == "0.16.4"
    assert tools["pytest"]["version"] == "9.1.1"
    assert "gh" in toolchain.declarations(declared, ("online",))
    declared.config["house"]["languages"] = ["markdown"]
    assert not toolchain.declarations(declared)
    declared.config["house"]["languages"] = ["cxx"]
    tools = toolchain.declarations(declared)
    assert tools["clang-tidy"]["version"] == "20"
    assert "ruff" not in tools
    assert "pytest" not in tools


def test_platform_tests_profile_includes_cpp_fixture_prerequisites(declared):
    entries = toolchain.declarations(declared, ("platform-tests",))
    assert {
        "pytest",
        "clang-format",
        "clang-tidy",
        "clang",
        "cmake",
        "ninja",
        "gcc",
        "doxygen",
    } <= set(entries)


@pytest.mark.parametrize(
    "case", ["unknown", "escape", "nonnumeric", "missing", "duplicate"],
)
def test_bad_manifest_cannot_pass(declared, write, case):
    if case == "unknown":
        with pytest.raises(CannotRunError, match="unknown toolchain profiles"):
            toolchain.declarations(declared, ("other",))
        return
    if case == "escape":
        write(
            "toolchains.toml",
            '[tools.ruff]\nproviders=["python"]\nexecutable="ruff"\nversion_ref="../other"\n',
        )
        expected = "escapes the pin"
    elif case == "nonnumeric":
        write("config/ruff.toml", 'required-version="latest"\n')
        expected = "version must be numeric"
    elif case == "duplicate":
        write(
            "pyproject.toml",
            '[dependency-groups]\ndev=["pytest==9.1.1", "pytest==8.0"]\n',
        )
        expected = "expected one pytest pin"
    else:
        (declared.root / "config/ruff.toml").unlink()
        expected = "cannot read"
    with pytest.raises(CannotRunError, match=expected):
        toolchain.declarations(declared, ("tests",))


@pytest.mark.parametrize(
    "output", ["ruff 0.16.3", "invalid", "ruff 0.16.4\nwarning: broken"],
)
def test_wrong_or_unusable_version_is_unavailable(declared, monkeypatch, output):
    monkeypatch.setattr(toolchain, "locate", lambda *_: "synthetic-ruff")
    monkeypatch.setattr(
        toolchain,
        "run",
        lambda *_: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )
    result = toolchain.doctor(declared)
    assert result.status == 2
    assert "expected 0.16.4" in result.message


def test_compatible_native_minimum_and_exact_python_pin(declared, monkeypatch):
    monkeypatch.setattr(toolchain, "locate", lambda *_: "synthetic")
    monkeypatch.setattr(
        toolchain,
        "run",
        lambda *_: SimpleNamespace(returncode=0, stdout="ruff 0.16.4", stderr=""),
    )
    assert toolchain.doctor(declared).status == 0
    entry = {"executable": "cmake", "version": "3.24", "minimum": "3.24"}
    monkeypatch.setattr(
        toolchain,
        "run",
        lambda *_: SimpleNamespace(
            returncode=0, stdout="cmake version 3.30.0", stderr="",
        ),
    )
    assert toolchain.inspect(declared, "cmake", entry)[0] == "synthetic"


def test_missing_native_prerequisites_never_install_implicitly(declared, monkeypatch):
    declared.config["house"]["languages"] = ["cxx"]
    monkeypatch.setattr(toolchain, "inspect", lambda *_: (None, "missing"))
    calls = []
    monkeypatch.setattr(toolchain, "checked", lambda *args: calls.append(args))
    with pytest.raises(
        CannotRunError, match=r"native prerequisites missing:.*install them explicitly",
    ):
        toolchain.install(declared)
    assert calls == []
    # Even --system reports prerequisites on native Windows, without installation.
    monkeypatch.setattr(toolchain.sys, "platform", "win32")
    with pytest.raises(CannotRunError, match="native prerequisites missing"):
        toolchain.install(declared, system=True)
    assert calls == []


def test_explicit_linux_system_install_uses_declared_packages(declared, monkeypatch):
    entry = {
        "executable": "clang-format",
        "version": "20",
        "apt": "clang-format-{version}",
    }
    monkeypatch.setattr(toolchain, "inspect", lambda *_: (None, "missing"))
    monkeypatch.setattr(toolchain.sys, "platform", "linux")
    monkeypatch.setattr(toolchain.shutil, "which", lambda _: "apt-get")
    calls = []
    monkeypatch.setattr(toolchain, "checked", lambda _repo, argv: calls.append(argv))
    toolchain.native_packages(declared, {"clang-format": entry}, system=True)
    assert calls[0][-2:] == ["apt-get", "update"]
    assert calls[1][-2:] == ["--no-install-recommends", "clang-format-20"]


def test_install_reuses_compatible_tools_without_creating_environment(
    declared, monkeypatch,
):
    monkeypatch.setattr(toolchain, "inspect", lambda *_: ("synthetic", "compatible"))
    assert toolchain.install(declared).status == 0
    assert not toolchain.environment(declared).exists()


def test_python_install_is_private_and_pinned(declared, monkeypatch):
    monkeypatch.setattr(toolchain, "inspect", lambda *_: (None, "missing"))
    creations = []
    options = []

    def builder(**kwargs):
        options.append(kwargs)
        return SimpleNamespace(create=creations.append)

    monkeypatch.setattr(toolchain.venv, "EnvBuilder", builder)
    calls = []
    monkeypatch.setattr(toolchain, "checked", lambda _repo, argv: calls.append(argv))
    result = toolchain.install(declared, ("tests",))
    assert result.status == 2  # Mock installation supplies no real executables.
    assert options == [{"with_pip": True, "symlinks": False}]
    assert creations == [declared.root / ".house/toolchain"]
    assert calls == [
        [
            str(toolchain.executable(declared, "python")),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "ruff==0.16.4",
            "pytest==9.1.1",
        ],
    ]


def test_tool_run_refuses_undeclared_or_missing_tools(declared, monkeypatch):
    with pytest.raises(CannotRunError, match="tool is not declared"):
        toolchain.run_tool(declared, "clang", [])
    monkeypatch.setattr(
        toolchain, "inspect", lambda *_: (None, "pytest 9.1.1 is not installed"),
    )
    with pytest.raises(CannotRunError, match=r"pytest 9\.1\.1 is not installed"):
        toolchain.run_tool(declared, "pytest", ["-q"])


def test_tool_run_finds_private_tools_first(declared, monkeypatch):
    # AR-11: a tool started by `toolchain run` resolves sibling tools, such as
    # Ruff under pytest, from the private environment before the host PATH.
    found = str(toolchain.executable(declared, "pytest"))
    monkeypatch.setattr(toolchain, "inspect", lambda *_: (found, ""))
    monkeypatch.setenv("PATH", "/host/bin")
    seen = {}

    def launched(argv, cwd, env=None):
        seen.update(argv=argv, cwd=cwd, path=env["PATH"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(toolchain, "run", launched)
    assert toolchain.run_tool(declared, "pytest", ["-q"]) == 0
    private = str(toolchain.executable(declared, "python").parent)
    assert seen == {
        "argv": [found, "-q"],
        "cwd": declared.root,
        "path": private + os.pathsep + "/host/bin",
    }
