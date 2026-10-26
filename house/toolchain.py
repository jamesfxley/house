# SPDX-License-Identifier: MIT
"""Prepare declared tools privately; native package installs are explicit (AR-11)."""

import os
import re
import shutil
import sys
import tomllib
import venv

from house.api import Result
from house.core import CannotRunError, read
from house.tools import diagnostic, platform, run, warning

PROFILES = ("tests", "platform-tests", "online")


def environment(repo):
    return repo.root / ".house/toolchain"


def executable(repo, name):
    directory = environment(repo) / ("Scripts" if os.name == "nt" else "bin")
    return directory / (name + ".exe" if os.name == "nt" else name)


def pin(repo, name, entry):
    reference = entry.get("version_ref")
    if not reference:
        return entry["minimum"]
    filename, _, key = reference.partition(":")
    target = platform(repo) / filename
    if not target.resolve().is_relative_to(platform(repo)):
        raise CannotRunError("toolchain version reference escapes the pin")
    content = read(target)
    if not key:
        value = " ".join(
            line.split("#", 1)[0].strip() for line in content.splitlines()
        ).strip()
    else:
        value = tomllib.loads(content)
        for part in key.split("."):
            value = value[part]
        if isinstance(value, list):
            values = [
                item.removeprefix(name + "==")
                for item in value
                if item.startswith(name + "==")
            ]
            if len(values) != 1:
                raise CannotRunError(f"{reference}: expected one {name} pin")
            value = values[0]
        value = value.removeprefix("==")
    if not re.fullmatch(r"\d+(?:\.\d+)*", value):
        raise CannotRunError(f"{name}: version must be numeric")
    return value


def validate_entry(name, entry):
    allowed = {
        "providers",
        "profiles",
        "executable",
        "package",
        "version_ref",
        "minimum",
        "apt",
    }
    if not isinstance(entry, dict) or set(entry) - allowed:
        raise CannotRunError(f"{name}: unsupported toolchain fields")
    if bool(entry.get("version_ref")) == bool(entry.get("minimum")):
        raise CannotRunError(f"{name}: declare one version_ref or minimum")
    for field in ("providers", "profiles"):
        value = entry.get(field, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise CannotRunError(f"{name}.{field}: expected a list of names")
    for field in set(entry) - {"providers", "profiles"}:
        if not isinstance(entry[field], str) or not entry[field]:
            raise CannotRunError(f"{name}.{field}: expected nonempty text")
    if not re.fullmatch(r"[a-z][a-z0-9+-]*", name) or "executable" not in entry:
        raise CannotRunError("toolchain names need a lowercase name and executable")


def declarations(repo, profiles=()):
    unknown = set(profiles) - set(PROFILES)
    if unknown:
        raise CannotRunError(
            "unknown toolchain profiles: " + ", ".join(sorted(unknown)),
        )
    manifest = tomllib.loads(read(platform(repo) / "toolchains.toml"))
    if set(manifest) != {"tools"} or not isinstance(manifest["tools"], dict):
        raise CannotRunError("toolchains.toml must contain a tools table")
    selected = {}
    for name, entry in manifest["tools"].items():
        validate_entry(name, entry)
        if set(entry.get("providers", [])) & set(
            repo.config["house"]["languages"],
        ) or set(entry.get("profiles", [])) & set(profiles):
            selected[name] = {**entry, "version": pin(repo, name, entry)}
    return selected


def locate(repo, entry):
    name = entry["executable"]
    private = executable(repo, name)
    if private.is_file():
        return str(private)
    versioned = name + "-" + entry["version"]
    return shutil.which(versioned) or shutil.which(name)


def inspect(repo, name, entry):
    found = locate(repo, entry)
    if not found:
        return None, f"{name} {entry['version']} is not installed"
    done = run([found, "--version"], repo.root)
    match = re.search(r"\b(\d+(?:\.\d+)+|\d+)\b", diagnostic(done))
    actual = tuple(map(int, match[1].split("."))) if match else ()
    expected = tuple(map(int, entry["version"].split(".")))
    matches = (
        actual[: len(expected)] == expected
        if "version_ref" in entry
        else actual >= expected
    )
    if done.returncode or warning(diagnostic(done)) or not actual or not matches:
        return None, f"{name}: expected {entry['version']}, got {diagnostic(done)}"
    return found, f"{name} {match[1]}: {found}"


def doctor(repo, profiles=()):
    messages = []
    missing = False
    for name, entry in declarations(repo, profiles).items():
        found, message = inspect(repo, name, entry)
        missing |= not found
        messages.append(message)
    return Result(2 if missing else 0, "\n".join(messages) or "no tools declared")


def checked(repo, argv):
    done = run(argv, repo.root)
    print(diagnostic(done))
    if done.returncode or warning(diagnostic(done)):
        raise CannotRunError(f"tool preparation failed: {argv[0]}")


def native_packages(repo, entries, *, system=False):
    missing = [
        entry
        for name, entry in entries.items()
        if "package" not in entry and not inspect(repo, name, entry)[0]
    ]
    if not missing:
        return
    if not system or sys.platform != "linux" or not shutil.which("apt-get"):
        names = ", ".join(entry["executable"] for entry in missing)
        raise CannotRunError(
            "native prerequisites missing: "
            + names
            + "; install them explicitly, then rerun toolchain install",
        )
    prefix = [] if hasattr(os, "geteuid") and os.geteuid() == 0 else ["sudo"]
    packages = sorted(
        {entry["apt"].format(version=entry["version"]) for entry in missing},
    )
    checked(repo, [*prefix, "apt-get", "update"])
    checked(
        repo,
        [*prefix, "apt-get", "install", "--yes", "--no-install-recommends", *packages],
    )


def install(repo, profiles=(), *, system=False):
    entries = declarations(repo, profiles)
    native_packages(repo, entries, system=system)
    packages = [
        entry["package"] + "==" + entry["version"]
        for name, entry in entries.items()
        if "package" in entry and not inspect(repo, name, entry)[0]
    ]
    if packages:
        destination = environment(repo)
        if not executable(repo, "python").is_file():
            venv.EnvBuilder(with_pip=True, symlinks=False).create(destination)
        # pip's user cache may belong to another user, as when a CI container runs
        # as root with the runner's HOME; pip then warns, and a warning fails.
        checked(
            repo,
            [
                str(executable(repo, "python")),
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                *packages,
            ],
        )
    return doctor(repo, profiles)


def run_tool(repo, name, args):
    profiles = ("tests",) if name == "pytest" else ()
    entries = declarations(repo, profiles)
    if name not in entries:
        raise CannotRunError(f"{name}: tool is not declared")
    found, message = inspect(repo, name, entries[name])
    if not found:
        raise CannotRunError(message)
    private = str(executable(repo, "python").parent)
    path = os.pathsep.join([private, os.environ.get("PATH", "")])
    done = run([found, *args], repo.root, {**os.environ, "PATH": path})
    print(diagnostic(done))
    return done.returncode or (1 if warning(diagnostic(done)) else 0)
