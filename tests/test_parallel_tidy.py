# SPDX-License-Identifier: MIT
"""AR-6: overlap independent work without sharing header databases or losing faults."""

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from house.core import CannotRunError
from house.gates import clang_tidy
from house.gates.lint import Lint
from house.runner import execute


@pytest.fixture
def sources(repo, write, monkeypatch):
    repo.config["house"]["languages"] = ["cxx"]
    headers = [
        write(f"include/{name}.hpp", "#pragma once\n") for name in ("alpha", "beta")
    ]
    units = [write(f"src/{name}.cpp", "int value();\n") for name in ("alpha", "beta")]
    entries = [
        {
            "directory": str(repo.root),
            "file": str(unit),
            "arguments": ["c++", "-c", str(unit)],
        }
        for unit in units
    ]
    write("compile_commands.json", json.dumps(entries))
    monkeypatch.setattr(
        clang_tidy.os, "sched_getaffinity", lambda _pid: {0, 1}, raising=False,
    )
    monkeypatch.setattr(clang_tidy, "clang", lambda *_: "synthetic-clang-tidy")

    def environment(_repo, entry, _resolved):
        assert threading.current_thread() is threading.main_thread()
        return {"ENTRY": entry["file"]}

    def arguments(_repo, _entry, _resolved):
        assert threading.current_thread() is threading.main_thread()
        return ["--extra-arg=-DSYNTHETIC=1"]

    monkeypatch.setattr(clang_tidy, "profile_environment", environment)
    monkeypatch.setattr(clang_tidy, "profile_args", arguments)
    return repo, entries, headers


def test_workers_follow_the_affinity_not_the_cpu_count(monkeypatch):
    monkeypatch.setattr(clang_tidy.os, "cpu_count", lambda: 64)
    monkeypatch.setattr(
        clang_tidy.os, "sched_getaffinity", lambda _pid: {0, 1, 2}, raising=False,
    )
    assert clang_tidy.worker_count() == 3


def test_workers_have_no_fixed_cap(monkeypatch):
    monkeypatch.setattr(
        clang_tidy.os, "sched_getaffinity", lambda _pid: set(range(32)), raising=False,
    )
    assert clang_tidy.worker_count() == 32


def test_the_pool_is_sized_by_the_available_cpus(monkeypatch):
    sizes = []

    class Recording(clang_tidy.ThreadPoolExecutor):
        def __init__(self, max_workers):
            sizes.append(max_workers)
            super().__init__(max_workers=max_workers)

    monkeypatch.setattr(clang_tidy, "ThreadPoolExecutor", Recording)
    monkeypatch.setattr(
        clang_tidy.os, "sched_getaffinity", lambda _pid: set(range(16)), raising=False,
    )
    assert clang_tidy.parallel(lambda job: job * 2, [1, 2, 3]) == [2, 4, 6]
    assert sizes == [16]


def test_workers_fall_back_to_the_cpu_count_without_affinity(monkeypatch):
    monkeypatch.delattr(clang_tidy.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(clang_tidy.os, "cpu_count", lambda: 6)
    assert clang_tidy.worker_count() == 6


def test_workers_are_one_when_the_cpu_count_is_unknown(monkeypatch):
    monkeypatch.delattr(clang_tidy.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(clang_tidy.os, "cpu_count", lambda: None)
    assert clang_tidy.worker_count() == 1


def test_dependency_probes_overlap_and_keep_order(sources, monkeypatch):
    repo, entries, headers = sources
    entries = [
        *entries,
        *[
            {**entries[0], "file": str(repo.root / f"src/{name}.cpp")}
            for name in ("gamma", "delta")
        ],
    ]
    monkeypatch.setattr(clang_tidy.os, "cpu_count", lambda: 8)  # affinity still wins
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    active = peak = 0

    def probe(entry, environment):
        nonlocal active, peak
        assert environment["ENTRY"] == entry["file"]
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait(timeout=5)
        with lock:
            active -= 1
        return set(headers)

    monkeypatch.setattr(clang_tidy, "reached", probe)
    assert clang_tidy.header_contexts(repo, entries, "host", []) == [
        (entry, set(headers)) for entry in entries
    ]
    assert peak == 2


def test_parallel_headers_have_private_databases_and_keep_warnings(
    sources, monkeypatch,
):
    repo, entries, headers = sources
    monkeypatch.setattr(
        clang_tidy,
        "header_contexts",
        lambda *_: [(entry, set(headers)) for entry in entries],
    )
    barrier = threading.Barrier(2)
    databases = set()
    lock = threading.Lock()

    def run(command, _root, environment):
        filename = Path(command[-1])
        assert "--extra-arg=-DSYNTHETIC=1" in command
        assert environment["ENTRY"] in {entry["file"] for entry in entries}
        if filename.suffix == ".cpp":
            barrier.wait(timeout=5)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        database = Path(command[command.index("-p") + 1]) / "compile_commands.json"
        with lock:
            databases.add(database)
        barrier.wait(timeout=5)
        assert json.loads(database.read_text())[0]["file"] == str(filename)
        return SimpleNamespace(
            returncode=0, stdout="", stderr=f"warning: {filename.name}",
        )

    monkeypatch.setattr(clang_tidy, "run", run)
    result = clang_tidy.tidy(repo)
    assert result.status == 1
    assert [finding.path for finding in result.findings] == [
        Path("include/alpha.hpp"),
        Path("include/beta.hpp"),
    ]
    assert all("warning:" in finding.message for finding in result.findings)
    assert len(databases) == 2


def test_dependency_probe_failure_is_unavailable_not_a_crash(sources, monkeypatch):
    repo, _entries, _headers = sources

    def probe(_entry, _environment):
        raise CannotRunError("synthetic dependency probe failure")

    monkeypatch.setattr(clang_tidy, "reached", probe)
    entry = execute(repo, Lint())
    assert entry.result.status == 2
    assert entry.result.message == "synthetic dependency probe failure"
    assert "crashed" not in entry.result.message


def test_tree_uses_one_canonical_command_per_source(sources, write, monkeypatch):
    repo, entries, _headers = sources
    refused = {**entries[0], "arguments": [*entries[0]["arguments"], "-DREFUSE=1"]}
    database = write("build/compile_commands.json", json.dumps([*entries, refused]))
    original = database.read_bytes()
    monkeypatch.setattr(clang_tidy, "header_contexts", lambda *_: [])
    monkeypatch.setattr(clang_tidy, "scoped_headers", lambda *_: [])
    observed = []
    lock = threading.Lock()

    def run(command, _root, _environment):
        path = Path(command[command.index("-p") + 1]) / "compile_commands.json"
        loaded = json.loads(path.read_text())
        valid = len(loaded) == 1 and "-DREFUSE=1" not in loaded[0]["arguments"]
        with lock:
            observed.extend(loaded)
        return SimpleNamespace(returncode=0 if valid else 1, stdout="",
                               stderr="" if valid else "unselected refusal command ran")

    monkeypatch.setattr(clang_tidy, "run", run)
    result = clang_tidy.tidy(repo, "host")
    assert result.status == 0, result.findings
    assert sorted(observed, key=lambda entry: entry["file"]) == entries
    assert database.read_bytes() == original


def test_trees_resolve_once_for_all_entries_and_again_next_run(sources, monkeypatch):
    repo, _entries, headers = sources
    resolutions = []
    original = clang_tidy.trees

    def resolve(current):
        resolutions.append(current)
        return original(current)

    monkeypatch.setattr(clang_tidy, "trees", resolve)
    monkeypatch.setattr(clang_tidy, "reached", lambda *_: set(headers))
    monkeypatch.setattr(
        clang_tidy, "run",
        lambda *_: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert clang_tidy.tidy(repo).status == 0
    assert resolutions == [repo]
    assert clang_tidy.tidy(repo).status == 0
    assert resolutions == [repo, repo]
