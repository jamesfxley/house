# SPDX-License-Identifier: MIT
"""Scaffold an empty checkout from one local reviewed platform pin (AR-13)."""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from house.api import Repo, Result
from house.config import load
from house.core import CannotRunError, git, read
from house.providers import get
from house.sync import defaults, sync
from house.tools import platform

PLATFORM_URL = "https://github.com/jamesfxley/house.git"
DEFAULT_PATH = "platform"
MARKER = "@PLATFORM@"
# A literal default path in a template would survive a nested render unchanged.
HARDCODED = re.compile(r"(?<![\w@/.-])platform/")


def render(text, platform_path, name):
    """Substitute the pinned platform path into one family template (AR-13)."""
    if platform_path != DEFAULT_PATH and HARDCODED.search(text):
        raise CannotRunError(f"template {name} hardcodes platform/; use {MARKER}")
    return text.replace(MARKER, platform_path)


def copy_tree(source, destination, platform_path, *, remove_in=False):
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise CannotRunError("scaffold templates cannot contain symlinks")
        if path.is_file():
            name = path.relative_to(source)
            if remove_in and name.suffix == ".in":
                name = name.with_suffix("")
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                render(read(path), platform_path, name.as_posix()),
                encoding="utf-8",
                newline="\n",
            )


def nested_pin(root, source):
    standard = source / "standard"
    if not (standard / "check.py").is_file():
        raise CannotRunError("source standard pin is absent; initialize it before init")
    git(root, "config", "submodule.standard.url", str(standard))
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "standard",
    )


def clone_kind(destination, source, kind):
    origin = source / "standard" if kind == "standard" else source
    git(
        destination.parent,
        "clone",
        "--quiet",
        "--no-hardlinks",
        str(origin),
        str(destination),
    )
    git(destination, "remote", "remove", "origin")
    if kind == "platform":
        nested_pin(destination, source)
    return Result.ok(
        f"initialized {kind} checkout at {destination}; no remote configured",
    )


def family_config(languages, platform_path, family_path=None):
    lines = [
        "[house]",
        f'platform = "{platform_path}"',
        "languages = " + json.dumps(languages),
        'licence = "MIT"',
        "",
        "[packages.root]",
        'path = "."',
    ]
    if "cxx" in languages:
        lines.extend(["[packages.root.modes]", 'host = "build-test-install"'])
    lines.extend(
        [
            "",
            "[sync]",
            "files = []",
            "",
            "[ci]",
            "skip = {}",
            "",
        ],
    )
    if family_path:
        lines[:0] = [f'family = "{family_path}"', ""]
    text = "\n".join(lines)
    return text.replace("[sync]\nfiles = []\n\n", "") if family_path else text


def submodule_name(root, path):
    rows = git(root, "config", "-f", ".gitmodules", "--get-regexp", r"\.path$")
    for row in rows.splitlines():
        key, _, value = row.partition(" ")
        if value == path:
            return key.removeprefix("submodule.").removesuffix(".path")
    raise CannotRunError(f"pinned source declares no submodule at {path}")


def pin_chain(destination, source, paths):
    """Pin the source, then its nested platform, from local reviewed checkouts."""
    pin_path, platform_path, inner = paths
    git(
        destination,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "--quiet",
        str(source),
        pin_path,
    )
    if inner == ".":
        if pin_path == DEFAULT_PATH:
            git(
                destination, "config", "-f", ".gitmodules",
                "submodule.platform.url", PLATFORM_URL,
            )
    else:
        # The published family URL is the family's to declare; nested pins
        # resolve from the reviewed local source rather than the network.
        outer = destination / pin_path
        name = submodule_name(outer, inner)
        git(outer, "config", f"submodule.{name}.url", str(source / inner))
        git(
            outer, "-c", "protocol.file.allow=always",
            "submodule", "update", "--init", inner,
        )
    nested_pin(destination / platform_path, source / inner)
    return destination / platform_path


def family(destination, source, languages, paths=(DEFAULT_PATH, DEFAULT_PATH, ".")):
    destination.mkdir(parents=True, exist_ok=True)
    git(destination, "init", "--quiet", "--initial-branch=main")
    # Stage attributes before any other file, including submodule metadata.
    attributes = destination / ".gitattributes"
    attributes.write_text("* text=auto eol=lf\n", encoding="utf-8", newline="\n")
    git(destination, "add", ".gitattributes")
    pinned = pin_chain(destination, source, paths)
    platform_path = paths[1]
    templates = pinned / "templates/family"
    copy_tree(templates / "files", destination, platform_path)
    family_path = (
        paths[0] if paths[2] != "." and (source / "family.toml").is_file() else None
    )
    for name in ("AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"):
        template = name + ".in" if name == "CONTRIBUTING.md" else name
        text = render(read(templates / template), platform_path, template)
        if name == "AGENTS.md" and family_path:
            start = text.index("| Work |")
            end = text.index("\n\n", start)
            text = (
                text[:start]
                + (
                    f"Before work, read `{family_path}/agents/AGENTS.md`; it routes to "
                    "the family's and the platform's guides."
                )
                + text[end:]
            )
        (destination / name).write_text(
            text,
            encoding="utf-8",
            newline="\n",
        )
    shutil.copyfile(pinned / "LICENSE", destination / "LICENSE")
    for language in languages:
        if language == "markdown" and set(languages) & {"python", "cxx"}:
            continue
        directory = templates / language
        if directory.is_dir():
            copy_tree(directory, destination, platform_path, remove_in=True)
    config_path = destination / "house.toml"
    config_path.write_text(
        family_config(
            languages,
            platform_path,
            family_path,
        ),
        encoding="utf-8",
        newline="\n",
    )
    repo = Repo(destination, load(destination))
    copies = sorted(
        {*defaults(repo), *repo.config["sync"]["files"], ".github/workflows/ci.yml"},
    )
    text = config_path.read_text()
    text = (
        text + "\n[sync]\nfiles = " + json.dumps(copies) + "\n"
        if family_path and copies != sorted(repo.config["sync"]["files"])
        else text.replace("files = []", "files = " + json.dumps(copies))
    )
    config_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )
    # Indexed discovery determines the Python test step, so stage owned inputs
    # before rendering and then stage the generated outputs as well.
    git(destination, "add", "--all")
    repo = Repo(destination, load(destination))
    sync(repo)
    git(destination, "add", "--all")
    git(
        destination,
        "commit",
        "--quiet",
        "-m",
        "tooling: scaffold the initial repository",
        "-m",
        "Establish the sample requirement, tests and pinned checks (AR-1).",
    )
    return Result.ok(
        f"initialized family at {destination}; run python3 dev.py check --ci",
    )


def reserved_names(pinned, languages):
    """Return the top-level names a family scaffold writes, in lower case."""
    templates = pinned / "templates/family"
    names = {
        ".git", ".gitattributes", ".gitmodules", ".github", "dev.py", "house.toml",
        "LICENSE", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md",
    }
    for directory in (templates / "files", *(templates / name for name in languages)):
        if directory.is_dir():
            names.update(path.name.removesuffix(".in") for path in directory.iterdir())
    for language in languages:
        copies = get(language).sync_defaults
        names.update(PurePosixPath(path).parts[0] for path in copies)
    return {name.casefold() for name in names}


def refuse_collision(pin_path, pinned, languages):
    """Refuse a pin path that would overwrite or sit inside scaffold output."""
    first = PurePosixPath(pin_path).parts[0]
    if first.casefold() in reserved_names(pinned, languages):
        raise CannotRunError(
            f"--pin-path {pin_path} collides with the scaffold's own {first}; "
            "choose a directory the scaffold does not write",
        )


def scaffold_paths(pin_path, platform_path):
    """Validate where a family pins its source and where House sits inside it."""
    pin = DEFAULT_PATH if pin_path is None else pin_path
    inner_platform = pin if platform_path is None else platform_path
    for label, value in (("--pin-path", pin), ("--platform-path", inner_platform)):
        if "\\" in value:
            raise CannotRunError(f"{label} must use forward slashes")
        posix = PurePosixPath(value)
        if (
            posix.is_absolute()
            or PureWindowsPath(value).drive
            or ".." in posix.parts
            or value in {"", "."}
            or not value.strip()
        ):
            raise CannotRunError(f"{label} must be a relative subdirectory")
    pin, inner_platform = PurePosixPath(pin), PurePosixPath(inner_platform)
    if inner_platform != pin and pin not in inner_platform.parents:
        raise CannotRunError("--platform-path must be inside the pin path")
    return pin.as_posix(), inner_platform.as_posix(), (
        inner_platform.relative_to(pin).as_posix()
    )


@dataclass(frozen=True)
class Source:
    """A reviewed local checkout, and where a family pins it and finds House."""

    path: Path | None = None
    pin_path: str | None = None
    platform_path: str | None = None


def initialize(repo, destination, kind, languages, *, source=None):
    target = Path(destination).absolute()
    if not isinstance(source, Source):
        source = Source(source)
    if kind != "family" and (source.pin_path or source.platform_path):
        raise CannotRunError(
            "--pin-path and --platform-path apply only for --kind family",
        )
    paths = scaffold_paths(source.pin_path, source.platform_path)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise CannotRunError(
            "init requires an empty destination; existing files are preserved",
        )
    selected = list(dict.fromkeys(languages or ["python", "markdown"]))
    for language in selected:
        get(language)
    origin = Path(source.path).resolve() if source.path else platform(repo)
    pinned = origin / paths[2]
    if not (pinned / "house/launcher/dev.py").is_file():
        raise CannotRunError("init requires a local platform checkout")
    if not (pinned / "standard/check.py").is_file():
        raise CannotRunError("source standard pin is absent; initialize it before init")
    # Refuse an unpublished worktree state instead of silently pinning an older
    # implementation than the one used to render its files.
    if git(origin, "status", "--porcelain", "--untracked-files=normal").strip():
        raise CannotRunError("init requires a clean, committed platform source")
    if kind == "family":
        refuse_collision(paths[0], pinned, selected)
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind in {"standard", "platform"}:
        return clone_kind(target, pinned, kind)
    return family(target, origin, selected, paths)
