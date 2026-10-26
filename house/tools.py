# SPDX-License-Identifier: MIT
"""Execute declared tools with explicit versions and unavailable-input diagnostics."""

import os
import re
import shutil
import subprocess
import tomllib

from house.core import CannotRunError, read


def run(argv, cwd, env=None, *, input_text=None):
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            input=input_text,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
    except (OSError, UnicodeError) as error:
        raise CannotRunError(f"cannot execute {argv[0]}: {error}") from error


def platform(repo):
    return (repo.root / repo.config["house"]["platform"]).resolve()


def clang(repo, name):
    pin = " ".join(
        line.split("#", 1)[0].strip()
        for line in read(platform(repo) / "config/.clang-version").splitlines()
    ).strip()
    if not re.fullmatch(r"\d+", pin):
        raise CannotRunError("config/.clang-version names no numeric release")
    override = os.environ.get(name.upper().replace("-", "_"))
    found = override or shutil.which(name + "-" + pin) or shutil.which(name)
    if not found:
        raise CannotRunError(f"{name} {pin} is not installed")
    done = run([found, "--version"], repo.root)
    version = re.search(r"version (\d+)", done.stdout)
    if done.returncode or not version or version[1] != pin:
        raise CannotRunError(
            f"{found} is not {name} {pin}, pinned by config/.clang-version",
        )
    return found


def ruff(repo):
    config = platform(repo) / "config/ruff.toml"
    pin = tomllib.loads(read(config))["required-version"].removeprefix("==")
    override = os.environ.get("RUFF")
    private = (
        repo.root
        / ".house/toolchain"
        / ("Scripts/ruff.exe" if os.name == "nt" else "bin/ruff")
    )
    found = override or (str(private) if private.is_file() else shutil.which("ruff"))
    if found:
        done = run([found, "--version"], repo.root)
        if done.returncode == 0 and done.stdout.strip() == "ruff " + pin:
            return [found]
        if override:
            raise CannotRunError(f"{found} is not ruff {pin}")
    if shutil.which("uvx"):
        return ["uvx", "ruff@" + pin]
    raise CannotRunError(f"ruff {pin} is not installed and uvx is unavailable")


def owned(repo, suffixes):
    return tuple(path for path in repo.tracked() if path.suffix in suffixes)


def cxx_applies(repo):
    return (
        True
        if "cxx" in repo.config["house"]["languages"]
        else "no C++ provider declared"
    )


def warning(text):
    return (
        re.search(r"(?im)\bwarning(?:\s+[A-Z]+\d+)?\s*:|\bCMake Warning\b", text)
        is not None
    )


def diagnostic(done):
    return (done.stdout + done.stderr).strip()
