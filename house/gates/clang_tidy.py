# SPDX-License-Identifier: MIT
# AR-20: lint resolves trees once for each invocation.
"""Lint owned units and headers with discovery and profile flags (AR-6)."""

import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from house.api import Finding
from house.core import CannotRunError, read
from house.gates.common import verdict
from house.gates.compile_db import DATABASE, arguments, entries, lintable, source
from house.prose import C_FAMILY
from house.tools import clang, diagnostic, run, warning
from house.trees import trees


def worker_count():
    """Return the CPUs available to this process, with no fixed cap."""
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0)) or 1
    return os.cpu_count() or 1


def parallel(function, jobs):
    with ThreadPoolExecutor(max_workers=worker_count()) as pool:
        return list(pool.map(function, jobs))


def without_output(entry, *, omit_unit=False):
    argv, skip = [], False
    unit = source(entry)
    for word in arguments(entry):
        if skip:
            skip = False
        elif word == "-o":
            skip = True
        elif word != "-c" and not (
            omit_unit and (Path(entry["directory"]) / word).resolve() == unit
        ):
            argv.append(word)
    return argv


def dependency_paths(text):
    """Decode Make dependency escaping, where quote characters are literal."""
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    found, current, escaped = [], [], False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char.isspace():
            if current:
                found.append("".join(current).replace("$$", "$"))
                current = []
        else:
            current.append(char)
    if current:
        found.append("".join(current).replace("$$", "$"))
    return found


def reached(entry, environment=None):
    # Close the compiler's output file before spawning it, including on Windows.
    with tempfile.TemporaryDirectory(prefix="house-deps-") as temporary:
        path = Path(temporary) / "includes.d"
        done = run(
            [*without_output(entry), "-M", "-MG", "-MF", str(path)],
            Path(entry["directory"]),
            environment,
        )
        if done.returncode:
            raise CannotRunError(
                "compiler dependency probe failed:\n" + diagnostic(done),
            )
        text = read(path)
    _, separator, dependencies = text.partition(": ")
    if not separator:
        raise CannotRunError("compiler dependency probe emitted no dependency list")
    return {
        (Path(entry["directory"]) / name).resolve()
        for name in dependency_paths(dependencies)
    }


def header_entry(header, entry):
    argv = without_output(entry, omit_unit=True)
    language = "c-header" if source(entry).suffix == ".c" else "c++-header"
    return {
        "directory": entry["directory"],
        "file": str(header),
        "arguments": [argv[0], "-x", language, *argv[1:], str(header)],
    }


def profile_environment(repo, entry, resolved):
    directory = Path(entry["directory"]).resolve()
    for tree in resolved:
        if directory.is_relative_to(tree.directory(repo).resolve()):
            return {**os.environ, **(tree.env or {})}
    return dict(os.environ)


def profile_args(repo, entry, resolved):
    directory = Path(entry["directory"]).resolve()
    for tree in resolved:
        if directory.is_relative_to(tree.directory(repo).resolve()):
            raw = (tree.env or {}).get("HOUSE_CLANG_TIDY_ARGS", "[]")
            try:
                args = json.loads(raw)
            except json.JSONDecodeError as error:
                raise CannotRunError(
                    "HOUSE_CLANG_TIDY_ARGS must be a JSON string array",
                ) from error
            if not isinstance(args, list) or not all(
                isinstance(word, str) for word in args
            ):
                raise CannotRunError(
                    "HOUSE_CLANG_TIDY_ARGS must be a JSON string array",
                )
            return args
    return []


def header_contexts(repo, selected, tree_name, resolved):
    contexts = list(selected)
    if tree_name is None:
        owned_sources = {(repo.root / path).resolve() for path in lintable(repo)}
        for tree in resolved:
            path = tree.directory(repo) / DATABASE
            if path.is_file():
                contexts.extend(
                    entry for entry in entries(path) if source(entry) in owned_sources
                )
    unique = {json.dumps(entry, sort_keys=True): entry for entry in contexts}
    # Resolve profile modules before workers run; loading them changes sys.path.
    jobs = [
        (entry, profile_environment(repo, entry, resolved)) for entry in unique.values()
    ]

    def probe(job):
        entry, environment = job
        return entry, reached(entry, environment)

    return parallel(probe, jobs)


def scoped_headers(repo, contexts, tree_name):
    return [
        path
        for path in lintable(repo, C_FAMILY)
        if path.suffix not in {".c", ".cc", ".cpp", ".cxx"}
        and (
            tree_name is None
            or any((repo.root / path).resolve() in deps for _, deps in contexts)
        )
    ]


def header_work(repo, contexts, headers, resolved):
    header_jobs = []
    for path in headers:
        header = (repo.root / path).resolve()
        entry = next((item for item, deps in contexts if header in deps), None)
        header_jobs.append(
            (
                path,
                header,
                entry,
                profile_args(repo, entry, resolved) if entry else [],
                profile_environment(repo, entry, resolved) if entry else {},
            ),
        )

    return header_jobs


def tidy(repo, tree_name=None):
    resolved = trees(repo)
    tool = clang(repo, "clang-tidy")
    database = repo.root / DATABASE
    if tree_name:
        selected_tree = next(
            (tree for tree in resolved if tree.name == tree_name),
            None,
        )
        if selected_tree is None:
            raise CannotRunError(f"unknown lint tree: {tree_name}")
        database = selected_tree.directory(repo) / DATABASE
    loaded = entries(database)
    # Match merge(): the first command for each source is canonical.
    by_source = {source(entry): entry for entry in reversed(loaded)}
    units = lintable(repo)
    if tree_name:
        units = tuple(
            path for path in units if (repo.root / path).resolve() in by_source
        )
    missing = [path for path in units if (repo.root / path).resolve() not in by_source]
    if missing:
        return verdict(
            "CXX-00.6",
            [f"{path}: missing compile command" for path in missing],
            "compile database coverage checked",
        )
    selected = [by_source[(repo.root / path).resolve()] for path in units]
    findings = []
    contexts = header_contexts(repo, selected, tree_name, resolved)
    compatibility = [
        "--extra-arg=-Wno-unknown-warning-option",
        "--extra-arg=-Wno-unused-command-line-argument",
    ]
    unit_jobs = [
        (
            entry,
            profile_args(repo, entry, resolved),
            profile_environment(repo, entry, resolved),
        )
        for entry in selected
    ]

    def check_unit(job):
        entry, extra, environment = job
        # A raw tree can list deliberate refusal variants of the same source.
        # Match compile-db merge's first command without mutating that tree.
        with tempfile.TemporaryDirectory(prefix="house-unit-") as temporary:
            scratch = Path(temporary)
            (scratch / DATABASE).write_text(json.dumps([entry]), encoding="utf-8")
            done = run(
                [
                    tool,
                    "--quiet",
                    "-p",
                    str(scratch),
                    *compatibility,
                    *extra,
                    str(source(entry)),
                ],
                repo.root,
                environment,
            )
        if done.returncode or warning(diagnostic(done)):
            return Finding(source(entry), 0, "EN-01.2", diagnostic(done))
        return None

    findings.extend(finding for finding in parallel(check_unit, unit_jobs) if finding)
    headers = scoped_headers(repo, contexts, tree_name)
    header_jobs = header_work(repo, contexts, headers, resolved)

    def check_header(job):
        path, header, entry, extra, environment = job
        if entry is None:
            return Finding(
                path,
                0,
                "CXX-01.5",
                "header unreached by any owned translation unit",
            )
        # Every concurrent header owns its database until its analyser exits.
        with tempfile.TemporaryDirectory(prefix="house-headers-") as temporary:
            scratch = Path(temporary)
            (scratch / DATABASE).write_text(
                json.dumps([header_entry(header, entry)]),
                encoding="utf-8",
            )
            done = run(
                [
                    tool,
                    "--quiet",
                    "-p",
                    str(scratch),
                    *compatibility,
                    *extra,
                    "--checks=-*,misc-include-cleaner",
                    str(header),
                ],
                repo.root,
                environment,
            )
        if done.returncode or warning(diagnostic(done)):
            return Finding(path, 0, "CXX-01.5", diagnostic(done))
        return None

    findings.extend(
        finding for finding in parallel(check_header, header_jobs) if finding
    )
    return verdict(
        "EN-01.2",
        findings,
        f"{len(units)} translation units and {len(headers)} headers checked",
    )
