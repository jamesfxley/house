# SPDX-License-Identifier: MIT
"""Require complete build logs and reject warnings in owned sources."""

import argparse
import re
from pathlib import Path

from house.build import COMPLETE
from house.core import CannotRunError, read
from house.gates.common import Always, verdict
from house.tools import cxx_applies
from house.trees import trees

COMPILE = re.compile(r"Building (?:C|CXX|ASM) object |\s-c\s")
DIAGNOSTIC = re.compile(r"^(.+?):\d+(?::\d+)?:\s*(?:warning:|warning [A-Z]+\d+:)")


def inspect(repo, path, directories):
    lines = read(path).splitlines()
    if not lines or lines[0] != COMPLETE:
        raise CannotRunError(
            f"{path} lacks complete compile evidence; rebuild the tree clean",
        )
    if not any(COMPILE.search(line) for line in lines):
        raise CannotRunError(f"{path} records no compile; rebuild the tree clean")
    owned = {(repo.root / name).resolve() for name in repo.tracked()}
    warnings = []
    for line in lines:
        found = DIAGNOSTIC.match(line)
        if found:
            source = (path.parent / found[1]).resolve()
            if source in owned and (
                not directories
                or any(
                    (repo.root / directory).resolve() in source.parents
                    for directory in directories
                )
            ):
                warnings.append(line)
    return warnings


class BuildWarnings(Always):
    name = "build-warnings"
    provider = "cxx"
    group = "build"
    rules = ("EN-01.3",)
    applies = staticmethod(cxx_applies)

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py gate build-warnings")
        parser.add_argument("log", type=Path, nargs="?")
        parser.add_argument("--dirs", nargs="+", default=[])
        args = parser.parse_args(argv)
        logs = (
            [args.log.resolve()]
            if args.log
            else [tree.directory(repo) / "build.log" for tree in trees(repo)]
        )
        faults = [
            message for path in logs for message in inspect(repo, path, args.dirs)
        ]
        return verdict("EN-01.3", faults, f"{len(logs)} complete build logs checked")
