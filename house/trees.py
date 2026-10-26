# SPDX-License-Identifier: MIT
"""Resolve host, fuzz and declared profile trees without family assumptions."""

import os
import re
import sys
from dataclasses import dataclass

from house.config import extension_module
from house.core import CannotRunError, read
from house.tools import clang


@dataclass(frozen=True)
class Tree:
    name: str
    args: tuple = ()
    env: dict | None = None

    def directory(self, repo):
        return repo.root / ("build" if self.name == "host" else "build-" + self.name)


def profiles(repo):
    found = []
    sys.path.insert(0, str(repo.root))
    try:
        for declaration in repo.config["trees"]:
            module, name = declaration["profile"].split(":")
            profile = getattr(extension_module(repo, module), name)
            if profile.name != declaration["name"] or type(profile.enabled) is not bool:
                raise CannotRunError(
                    f"invalid tree profile metadata: {declaration['profile']}",
                )
            if profile.enabled:
                args = tuple(profile.cmake_args)
                env = dict(profile.env)
                if not all(isinstance(arg, str) for arg in args) or not all(
                    isinstance(value, str) for value in env.values()
                ):
                    raise CannotRunError(
                        "profile arguments and environment must be strings",
                    )
                found.append(Tree(profile.name, args, env))
    finally:
        sys.path.pop(0)
    return found


def declared_prefix(repo, macro):
    path = repo.root / "CMakeLists.txt"
    text = read(path) if path.is_file() else ""
    match = re.search(rf"^\s*{macro}\(\s*(\w+)\s*\)", text, re.MULTILINE)
    return match[1] if match else None


def fuzz_prefix(repo):
    return declared_prefix(repo, "house_cxx_declare_fuzzers_option")


def sanitize_prefix(repo):
    return declared_prefix(repo, "house_cxx_enable_sanitizers")


def tests_prefix(repo):
    return declared_prefix(repo, "house_cxx_declare_tests_option")


def profile_names(repo):
    names = [declaration["name"] for declaration in repo.config["trees"]]
    names += [*(["sanitize"] if sanitize_prefix(repo) else []),
              *(["fuzz"] if fuzz_prefix(repo) else [])]
    if len(set(names)) != len(names):
        raise CannotRunError("duplicate host, fuzz or declared tree name")
    return names


def applicability(repo, name):
    if "cxx" not in repo.config["house"]["languages"]:
        return "no C++ provider declared"
    if name == "sanitize" and sanitize_prefix(repo):
        return (
            True
            if os.environ.get("HOUSE_MATRIX_SANITIZE") == "ON"
            else ("tree sanitize disabled")
        )
    if name == "host" or (name == "fuzz" and fuzz_prefix(repo)):
        return True
    return (
        True
        if name in {tree.name for tree in profiles(repo)}
        else f"tree {name} disabled"
    )


def trees(repo):
    found = [Tree("host"), *profiles(repo)]
    prefix = sanitize_prefix(repo)
    if prefix and any(tree["name"] == "sanitize" for tree in repo.config["trees"]):
        raise CannotRunError("duplicate host, fuzz or declared tree name")
    if prefix and os.environ.get("HOUSE_MATRIX_SANITIZE") == "ON":
        found.append(
            Tree(
                "sanitize",
                ("-DCMAKE_BUILD_TYPE=Debug", f"-D{prefix}_SANITIZE=ON"),
                {"ASAN_OPTIONS": "detect_leaks=1"},
            ),
        )
    prefix = fuzz_prefix(repo)
    if prefix:
        compiler = clang(repo, "clang")
        cxx = clang(repo, "clang++")
        found.append(
            Tree(
                "fuzz",
                (
                    f"-D{prefix}_ENABLE_FUZZERS=ON",
                    "-DCMAKE_CXX_COMPILER=" + cxx,
                ),
                {"CC": compiler},
            ),
        )
    if len({tree.name for tree in found}) != len(found):
        raise CannotRunError("duplicate host, fuzz or declared tree name")
    return found


AXIS_VALUE = re.compile(r"[A-Za-z0-9_.+-]+")


def axis_args(repo):
    """Return -D<variable>=<value> for each declared axis the environment selects.

    An axis reaches the check as HOUSE_MATRIX_<AXIS>; one the environment leaves
    unset or empty sets nothing.
    """
    args = []
    for axis, variable in repo.config.get("ci", {}).get("axes", {}).items():
        name = "HOUSE_MATRIX_" + axis.upper()
        value = os.environ.get(name, "")
        if not value:
            continue
        if not AXIS_VALUE.fullmatch(value):
            raise CannotRunError(
                f"{name}={value!r} must use letters, digits and _.+- only",
            )
        args.append(f"-D{variable}={value}")
    return args


def configure_args(repo, tree, directory=None, *, axes=True):
    """Return the arguments every configure of `tree` shares.

    Declared matrix axes apply unless `axes` is false, as for a consumer project
    that does not declare the variables.
    """
    directory = directory or tree.directory(repo)
    args = ["-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
    if os.environ.get("BUILD_TYPE") or not (directory / "CMakeCache.txt").exists():
        args.append("-DCMAKE_BUILD_TYPE=" + os.environ.get("BUILD_TYPE", "Debug"))
    args.extend(arg for arg in os.environ.get("BUILD_ARGS", "").splitlines() if arg)
    return [*args, *(axis_args(repo) if axes else []), *tree.args]
