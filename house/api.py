# SPDX-License-Identifier: MIT
"""The public interfaces available to repository extensions."""

import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from house import core
from house.core import CannotRunError

CONFIG_HOME_VARIABLE = "HOUSE_CONFIG_HOME"
CONFIG_NAME = re.compile(r"[a-z][a-z0-9_-]*")


def user_config_dir(name: str) -> Path:
    """Return this user's configuration directory for `name`; never create it.

    The base is, in order: the variable named by CONFIG_HOME_VARIABLE, which must
    be absolute; on Windows the roaming application-data directory; on macOS the
    user's Application Support directory; otherwise the XDG base directory when
    it is set and absolute, else the user's .config directory. `name` is one
    lowercase path segment. Raises CannotRunError for a refused value.
    """
    if not CONFIG_NAME.fullmatch(name):
        raise CannotRunError(
            f"configuration name {name!r} must be one lowercase path segment",
        )
    override = os.environ.get(CONFIG_HOME_VARIABLE)
    if override is not None:
        if not Path(override).is_absolute():
            raise CannotRunError(
                f"{CONFIG_HOME_VARIABLE} must be an absolute path, not {override!r}",
            )
        return Path(override) / name
    if sys.platform == "win32":
        roaming = os.environ.get("APPDATA")
        if not roaming:
            raise CannotRunError(
                f"APPDATA is not set; set {CONFIG_HOME_VARIABLE} to an absolute path",
            )
        return Path(roaming) / name
    try:
        home = Path.home()
    except RuntimeError as error:
        raise CannotRunError(
            f"no home directory; set {CONFIG_HOME_VARIABLE} to an absolute path",
        ) from error
    if sys.platform == "darwin":
        return home / "Library/Application Support" / name
    base = os.environ.get("XDG_CONFIG_HOME", "")
    return (Path(base) if Path(base).is_absolute() else home / ".config") / name


@dataclass(frozen=True)
class Finding:
    path: Path | str
    line: int
    rule: str
    message: str


@dataclass(frozen=True)
class Result:
    status: int
    message: str = ""
    findings: tuple[Finding, ...] = ()

    @classmethod
    def ok(cls, message: str = "") -> "Result":
        return cls(0, message)

    @classmethod
    def fail(cls, *findings: Finding, message: str = "") -> "Result":
        return cls(1, message, tuple(findings))

    @classmethod
    def cannot_run(cls, message: str) -> "Result":
        return cls(2, message)


@dataclass(frozen=True)
class Repo:
    root: Path
    config: Mapping

    @property
    def packages(self) -> Mapping:
        return self.config.get("packages") or {"root": {"path": "."}}

    def tracked(self, *patterns: str) -> tuple[Path, ...]:
        """Return owned indexed paths relative to the repository root."""
        platform = self.config["house"]["platform"]
        return core.tracked(self.root, platform, *patterns)

    def read(self, path: Path | str) -> str:
        """Read a repository-relative path, or an explicitly absolute path."""
        return core.read(self.root / path)

    def git(self, *args: str) -> str:
        return core.git(self.root, *args)


class Gate(Protocol):
    # Omitted provider metadata is treated as None for existing extensions.
    provider: str | tuple[str, ...] | None
    name: str
    group: str
    rules: tuple[str, ...]

    def applies(self, repo: Repo) -> bool | str: ...

    def run(self, repo: Repo, argv: tuple[str, ...]) -> Result: ...


class TreeProfile(Protocol):
    name: str
    enabled: bool
    cmake_args: tuple[str, ...]
    env: Mapping[str, str]
    sync_overlay: Mapping


class Provider(Protocol):
    name: str
    suffixes: tuple[str, ...]
    test_paths: tuple[str, ...]
    comment_tokens: tuple[str, ...]
    inline_suppressions: tuple[str, ...]
    scope_disables: tuple[str, ...]
    spdx_line: str | None
    version_sites: tuple[str, ...]
    format_cmd: tuple[str, ...]
    lint_cmd: tuple[str, ...]
    sync_defaults: tuple[str, ...]
