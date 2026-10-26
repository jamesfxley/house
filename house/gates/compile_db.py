# SPDX-License-Identifier: MIT
"""Merge owned compile commands and verify source coverage across declared trees."""

import argparse
import json
import shlex
from pathlib import Path

from house.api import Finding
from house.core import CannotRunError, read
from house.gates.common import Always, verdict
from house.tools import cxx_applies
from house.trees import trees

DATABASE = "compile_commands.json"
UNITS = {".c", ".cc", ".cpp", ".cxx"}


def lintable(repo, suffixes=UNITS):
    exclusions = []
    path = Path(".lintignore")
    if path in repo.tracked():
        for raw in repo.read(path).splitlines():
            line = raw.split("#", 1)[0].strip()
            if line:
                exclusions.append(":!:" + line)
    return tuple(path for path in repo.tracked(*exclusions) if path.suffix in suffixes)


def entries(path):
    try:
        loaded = json.loads(read(path))
    except json.JSONDecodeError as error:
        raise CannotRunError(f"{path} is not JSON: {error}") from error
    if not isinstance(loaded, list) or not all(
        isinstance(item, dict) for item in loaded
    ):
        raise CannotRunError(f"{path} is not a compile database")
    for entry in loaded:
        if not isinstance(entry.get("file"), str) or not isinstance(
            entry.get("directory"), str,
        ):
            raise CannotRunError(
                f"{path}: compile entry needs file and directory strings",
            )
        if not isinstance(entry.get("command"), str) and not (
            isinstance(entry.get("arguments"), list)
            and entry["arguments"]
            and all(isinstance(word, str) for word in entry["arguments"])
        ):
            raise CannotRunError(f"{path}: compile entry needs command or arguments")
    return loaded


def source(entry):
    return (Path(entry["directory"]) / entry["file"]).resolve()


def arguments(entry):
    return (
        list(entry["arguments"])
        if entry.get("arguments")
        else shlex.split(entry["command"])
    )


def merge(repo):
    own = {(repo.root / path).resolve() for path in lintable(repo)}
    merged = {}
    for tree in trees(repo):
        database = tree.directory(repo) / DATABASE
        if database.is_file():
            for entry in entries(database):
                if source(entry) in own:
                    merged.setdefault(str(source(entry)), entry)
    path = repo.root / DATABASE
    path.write_text(
        json.dumps(list(merged.values()), indent=2) + "\n", encoding="utf-8",
    )
    return len(merged)


class CompileDb(Always):
    name = "compile-db"
    provider = "cxx"
    group = "build"
    rules = ("CXX-00.6",)
    applies = staticmethod(cxx_applies)

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py gate compile-db")
        parser.add_argument(
            "mode",
            choices=("merge", "coverage", "cross"),
            default="coverage",
            nargs="?",
        )
        parser.add_argument("--triple")
        args = parser.parse_args(argv)
        if args.mode == "merge":
            return verdict(
                "CXX-00.6", [], f"{merge(repo)} owned compile entries merged",
            )
        loaded = entries(repo.root / DATABASE)
        if args.mode == "cross":
            if not args.triple:
                raise CannotRunError(
                    "cross mode requires an explicit --triple from the family profile",
                )
            cross = [
                entry for entry in loaded if args.triple in " ".join(arguments(entry))
            ]
            faults = [] if cross else [f"no {args.triple} cross entry"]
        else:
            covered = {source(entry) for entry in loaded}
            faults = [
                Finding(path, 0, "CXX-00.6", "source missing from compile database")
                for path in lintable(repo)
                if (repo.root / path).resolve() not in covered
            ]
        return verdict("CXX-00.6", faults, f"{len(loaded)} compile entries checked")
