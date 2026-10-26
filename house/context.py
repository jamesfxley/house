# SPDX-License-Identifier: MIT
"""Resolve agreements, guides and rules from the active checkout (AR-9)."""

from pathlib import Path

from house.api import user_config_dir
from house.core import CannotRunError, read
from house.providers import get
from house.tools import platform


def checked_path(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise CannotRunError(f"context path escapes checkout: {path}")
    return resolved


def instruction_paths(root, target):
    directory = target if target.is_dir() else target.parent
    directories = [root]
    for part in directory.relative_to(root).parts:
        directories.append(directories[-1] / part)
    found = []
    for directory_path in directories:
        for name in ("AGENTS.override.md", "AGENTS.md"):
            candidate = directory_path / name
            if candidate.is_file() and read(candidate).strip():
                found.append(candidate)
                break
    return found


def guide_names(repo, target, *, all_languages=False):
    names = ["engineering-standard"]
    cxx = "cxx" in repo.config["house"]["languages"]
    if cxx and (
        all_languages
        or target.suffix in get("cxx").suffixes
        or target.suffix == ".cmake"
        or target.name == "CMakeLists.txt"
    ):
        names.extend(("cxx-standard", "cxx-testing", "cxx-build-and-toolchain"))
    if all_languages or target.name in {"AGENTS.md", "house.toml", "pyproject.toml"}:
        names.append("new-repo")
    return [*names, "review"]


def bindings(repo, path=None):
    root = repo.root.resolve()
    target = root if path is None else checked_path(root, Path(path).absolute())
    pinned = checked_path(root, platform(repo))
    agreements = pinned / "agents/AGENTS.md"
    read(agreements)
    guides = [
        pinned / "guides" / name / "SKILL.md"
        for name in guide_names(repo, target, all_languages=path is None)
    ]
    for guide in guides:
        read(guide)
    standard = pinned / "standard"
    rules = sorted((standard / "engineering").glob("*.md"))
    if "cxx-standard" in {guide.parent.name for guide in guides}:
        rules.extend(sorted((standard / "cxx").glob("*.md")))
    if not rules:
        raise CannotRunError("pinned standard contains no rule chapters")
    for rule in rules:
        read(rule)
    config_directory = user_config_dir("house")
    notes = config_directory / "local.md"
    documents = []
    for package in repo.packages.values():
        package_path = root / package["path"]
        if path is None or target.is_relative_to(package_path):
            documents.extend(sorted((package_path / "docs").glob("*.md")))
    for document in documents:
        read(document)
    if notes.is_file():
        read(notes)
    return {
        "root": str(root),
        "target": str(target),
        "platform": str(pinned),
        "agreements": [str(agreements)],
        "instructions": [str(value) for value in instruction_paths(root, target)],
        "guides": [str(value) for value in guides],
        "rules": [str(value) for value in rules],
        "documents": [str(value) for value in documents],
        "local_notes": [str(notes)] if notes.is_file() else [],
        "house_config": {
            "directory": str(config_directory),
            "local_notes_present": notes.is_file(),
        },
        "config_directories": {
            name: str(user_config_dir(name))
            for name in repo.config["context"]["config_directories"]
        },
    }


def render(data):
    lines = [
        f"Repository: {data['root']}",
        f"Path: {data['target']}",
        f"Pinned platform: {data['platform']}",
    ]
    for key in (
        "agreements",
        "instructions",
        "guides",
        "rules",
        "documents",
        "local_notes",
    ):
        lines.extend(f"{key}: {path}" for path in data[key])
    house = data["house_config"]
    lines.append(f"House config directory: {house['directory']}")
    lines.append(
        "local.md: " + ("present" if house["local_notes_present"] else "absent"),
    )
    lines.extend(
        f"{name} config directory: {path}"
        for name, path in data["config_directories"].items()
    )
    return "\n".join(lines)
