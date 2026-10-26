# SPDX-License-Identifier: MIT
"""Require API inputs and fail on documentation warnings."""

import argparse
import re
import shutil
from pathlib import Path

from house.core import CannotRunError, read
from house.gates.common import Always, verdict
from house.tools import diagnostic, run, warning

INPUT = re.compile(r"^\s*INPUT\s*\+?=((?:.*\\\n)*.*)$", re.MULTILINE)


def inputs(text):
    clean = re.sub(r"#.*", "", text.replace("\r\n", "\n"))
    return {
        Path(word.strip('"').rstrip("/"))
        for block in INPUT.findall(clean)
        for word in block.replace("\\\n", " ").split()
    }


def public_directories(repo, package):
    root = Path(package["path"])
    return {
        Path(*path.parts[: path.parts.index("include") + 1])
        for path in repo.tracked()
        if path.is_relative_to(root) and "include" in path.parts
    }


class ApiDocs(Always):
    name = "api-docs"
    provider = "cxx"
    group = "docs"
    rules = ("EN-03.4",)

    def applies(self, repo):
        return (
            True
            if "cxx" in repo.config["house"]["languages"]
            else "no C++ API documentation declared"
        )

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py gate api-docs")
        parser.add_argument("doxyfile", nargs="?", type=Path)
        args = parser.parse_args(argv)
        configs = (
            [(args.doxyfile.resolve(), package) for package in repo.packages.values()]
            if args.doxyfile
            else [
                (repo.root / package["path"] / "docs/Doxyfile", package)
                for package in repo.packages.values()
            ]
        )
        faults = []
        tool = shutil.which("doxygen")
        for path, package in configs:
            working = repo.root if args.doxyfile else repo.root / package["path"]
            declared = {(working / value).resolve() for value in inputs(read(path))}
            public = public_directories(repo, package)
            absent = [
                f"{directory} is not in {path} INPUT"
                for directory in sorted(public)
                if (repo.root / directory).resolve() not in declared
            ]
            faults.extend(absent)
            if absent:
                continue
            if not tool:
                raise CannotRunError("doxygen is not installed")
            done = run([tool, str(path)], working)
            if done.returncode or warning(diagnostic(done)):
                faults.append(diagnostic(done))
        return verdict(
            "EN-03.4",
            faults,
            f"{len(configs)} API documentation configurations checked",
        )
