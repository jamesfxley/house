# SPDX-License-Identifier: MIT
# AR-20: reuse matching producers; run expected refusals separately.
"""Prove installable packages through relocated find_package consumers (AR-8)."""

import argparse
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from house.api import Finding, Result
from house.core import CannotRunError
from house.gates.common import Always
from house.tools import diagnostic, run, warning
from house.trees import configure_args, tests_prefix, trees

PRODUCER = ("producer-configure", "producer-build", "producer-install")


def consumer_sources(repo, tree):
    sources = []
    tracked = set(repo.tracked())
    for name, package in repo.packages.items():
        modes = package.get("modes", {})
        default = (
            "build-test-install" if not modes and tree.name == "host" else "build-test"
        )
        mode = modes.get(tree.name, default)
        if "install" not in mode.split("-"):
            continue
        path = Path(package["path"]) / "tests/consumer/CMakeLists.txt"
        if path not in tracked:
            raise CannotRunError(f"{name}: no indexed consumer at {path}")
        repo.read(path)
        sources.append((name, repo.root / path.parent))
    return sources


@dataclass(frozen=True)
class Execute:
    """A built consumer program the gate runs; it passes only on exit status 0."""

    package: str
    name: str
    path: Path


def executed(step, repo, environment):
    if not step.path.is_file():
        return Result.fail(
            Finding(
                ".",
                0,
                "EN-04.5",
                f"{step.package}: consumer executable {step.name} was not built; "
                "the consumer build produced no file at that path",
            ),
        )
    done = run([str(step.path)], repo.root, environment)
    if done.returncode:
        return Result.fail(
            Finding(
                ".",
                0,
                "EN-04.5",
                f"{step.package}: consumer executable {step.name} exited with "
                f"status {done.returncode}\n{diagnostic(done)}",
            ),
        )
    return None


def checked(command, repo, environment):
    done = run(command, repo.root, environment)
    if done.returncode or warning(diagnostic(done)):
        return Result.fail(Finding(".", 0, "EN-04.5", diagnostic(done)))
    return None


def producer_without_tests(repo, tree):
    """Return the option that keeps the producer's test targets out of the build.

    The fuzz tree's targets live in the test tree, so that tree keeps its tests.
    """
    prefix = tests_prefix(repo)
    return [f"-D{prefix}_ENABLE_TESTS=OFF"] if prefix and tree.name != "fuzz" else []


class Installs:
    """Relocated producer installs that consumers with identical producers share.

    A producer is keyed by its tree and every argument that shapes it. A consumer
    shares an install only when its producer command would have been identical.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.found = {}

    def directory(self):
        made = self.root / f"producer-{len(self.found)}"
        made.mkdir(parents=True, exist_ok=True)
        return made


def producer_key(repo, tree, producer_args):
    return (
        tree.name,
        tuple(configure_args(repo, tree, Path())),
        tuple(producer_without_tests(repo, tree)),
        tuple(producer_args),
    )


def consumer_commands(repo, tree, directory, sources, reused=None):
    build = directory / "producer"
    prefix = directory / "stage"
    if reused:
        yield from consumers(repo, tree, directory, sources, reused)
        return
    yield [
        "cmake",
        "-S",
        str(repo.root),
        "-B",
        str(build),
        "-G",
        "Ninja",
        *configure_args(repo, tree, build),
        *producer_without_tests(repo, tree),
        "-DCMAKE_INSTALL_PREFIX=" + str(prefix),
    ]
    yield ["cmake", "--build", str(build)]
    yield ["cmake", "--install", str(build)]
    relocated = directory / "relocated prefix"
    if not prefix.is_dir():
        raise CannotRunError("producer installed no prefix; no install rules ran")
    prefix.rename(relocated)
    yield from consumers(repo, tree, directory, sources, relocated)


def consumers(repo, tree, directory, sources, relocated):
    for name, source in sources:
        consumer = directory / ("consumer-" + name)
        yield [
            "cmake",
            "-S",
            str(source),
            "-B",
            str(consumer),
            "-G",
            "Ninja",
            *configure_args(repo, tree, consumer, axes=False),
            "-DCMAKE_PREFIX_PATH=" + str(relocated),
            "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
            "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF",
        ]
        yield ["cmake", "--build", str(consumer)]
        if tree.name == "host":
            for executable in repo.packages[name].get("consumer_executables", ()):
                yield Execute(name, executable, consumer / executable)


def squashed(text):
    """Collapse whitespace; CMake wraps the text of an error across lines."""
    return re.sub(r"\s+", " ", text).strip()


def case_sources(repo, tree):
    """Return (package, case, consumer source directory) for the tree's cases."""
    tracked = set(repo.tracked())
    found = []
    for name, package in repo.packages.items():
        for case in package.get("consumer_cases", ()):
            if case["tree"] != tree.name:
                continue
            default = Path(package["path"]) / "tests/consumer"
            directory = Path(case.get("source") or default)
            if directory / "CMakeLists.txt" not in tracked:
                raise CannotRunError(
                    f"{name}: case {case['name']} has no indexed consumer at "
                    f"{directory / 'CMakeLists.txt'}",
                )
            repo.read(directory / "CMakeLists.txt")
            found.append((name, case, repo.root / directory))
    return found


def case_steps(repo, tree, case, source, directory):
    """Return (stage, command) pairs, ending where a case needs no more."""
    build = directory / "producer"
    prefix = directory / "stage"
    relocated = directory / "relocated prefix"
    consumer = directory / "consumer"
    yield "producer-configure", [
        "cmake",
        "-S",
        str(repo.root),
        "-B",
        str(build),
        "-G",
        "Ninja",
        *configure_args(repo, tree, build),
        *producer_without_tests(repo, tree),
        *case["producer_args"],
        "-DCMAKE_INSTALL_PREFIX=" + str(prefix),
    ]
    yield "producer-build", ["cmake", "--build", str(build)]
    yield "producer-install", ["cmake", "--install", str(build)]
    yield "relocate", [prefix, relocated]
    yield "consumer-configure", [
        "cmake",
        "-S",
        str(source),
        "-B",
        str(consumer),
        "-G",
        "Ninja",
        *configure_args(repo, tree, consumer, axes=False),
        "-DCMAKE_PREFIX_PATH=" + str(relocated),
        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
        "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF",
        *case["consumer_args"],
    ]
    yield "consumer-build", ["cmake", "--build", str(consumer)]


def case_failure(label, text):
    return Result.fail(Finding(".", 0, "EN-04.5", f"{label}: {text}"))


def refusal(label, stage, done, message):
    """Return a failure unless the stage failed and said the declared message."""
    if not done.returncode:
        return case_failure(label, f"{stage} succeeded but was expected to fail")
    if squashed(message) not in squashed(diagnostic(done)):
        return case_failure(
            label,
            f"{stage} failed without saying {message!r}\n{diagnostic(done)}",
        )
    return None


def success(label, stage, done, expected):
    """Return a failure unless a stage ahead of the expected one succeeded."""
    if done.returncode or warning(diagnostic(done)):
        ahead = f" before the expected {expected} failure" if expected else ""
        return case_failure(label, f"{stage} failed{ahead}\n{diagnostic(done)}")
    return None


def relocate(prefix, relocated):
    if not prefix.is_dir():
        raise CannotRunError("producer installed no prefix; no install rules ran")
    prefix.rename(relocated)


def case_programs(repo, package, directory, environment):
    for executable in repo.packages[package].get("consumer_executables", ()):
        step = Execute(package, executable, directory / "consumer" / executable)
        failure = executed(step, repo, environment)
        if failure:
            return failure
    return None


def produce(repo, tree, entry, environment, base):
    """Build, install and relocate the case's producer under base.

    Return (failure or None, relocated prefix). A failure ends the case.
    """
    package, case, source = entry
    label = f"{package}: case {case['name']}"
    expected = case.get("stage")
    for stage, command in case_steps(repo, tree, case, source, base):
        if stage == "relocate":
            relocate(*command)
            return None, base / "relocated prefix"
        done = run(command, repo.root, environment)
        if stage == expected:
            return refusal(label, stage, done, case["message"]), None
        failure = success(label, stage, done, expected)
        if failure:
            return failure, None
    return None, None


def run_case(repo, tree, entry, environment, installs=None):
    """Run one declared case; return a failing Result, or None when it held."""
    _, case, _ = entry
    expected = case.get("stage")
    with tempfile.TemporaryDirectory(prefix="house-case-") as temporary:
        directory = Path(temporary)
        if installs is None or expected in PRODUCER:
            failure, relocated = produce(repo, tree, entry, environment, directory)
            if failure or relocated is None:
                return failure
        else:
            key = producer_key(repo, tree, case["producer_args"])
            if key not in installs.found:
                failure, relocated = produce(
                    repo, tree, entry, environment, installs.directory(),
                )
                if failure:
                    return failure
                installs.found[key] = relocated
            relocated = installs.found[key]
        return run_case_consumer(repo, tree, entry, directory, relocated)


def run_case_consumer(repo, tree, entry, directory, relocated):
    package, case, source = entry
    environment = {**os.environ, **(tree.env or {})}
    label = f"{package}: case {case['name']}"
    expected = case.get("stage")
    for stage, original in case_steps(repo, tree, case, source, directory):
        if stage in PRODUCER or stage == "relocate":
            continue
        command = [
            "-DCMAKE_PREFIX_PATH=" + str(relocated)
            if str(word).startswith("-DCMAKE_PREFIX_PATH=") else word
            for word in original
        ]
        done = run(command, repo.root, environment)
        if stage == expected:
            return refusal(label, stage, done, case["message"])
        failure = success(label, stage, done, expected)
        if failure:
            return failure
    if tree.name == "host":
        return case_programs(repo, package, directory, environment)
    return None


def consume_cases(repo, tree, environment, installs=None):
    """Run the tree's declared cases; return (failure or None, case labels)."""
    entries = case_sources(repo, tree)
    labels = []
    for entry in entries:
        failure = run_case(repo, tree, entry, environment, installs)
        if failure:
            return failure, labels
        case = entry[1]
        outcome = "runs" if case["expect"] == "runs" else "refused at " + case["stage"]
        labels.append(f"{entry[0]}:{case['name']} ({outcome})")
    return None, labels


def consume(repo, tree):
    with tempfile.TemporaryDirectory(prefix="house-installs-") as shared:
        return consume_in(repo, tree, Installs(shared))


def consume_in(repo, tree, installs):
    sources = consumer_sources(repo, tree)
    environment = {**os.environ, **(tree.env or {})}
    failure, cases = consume_cases(repo, tree, environment, installs)
    if failure:
        return failure
    suffix = "; cases: " + ", ".join(cases) if cases else ""
    if not sources:
        return Result.ok(
            tree.name + ": no installable package modes declared" + suffix,
        )
    with tempfile.TemporaryDirectory(prefix="house-consumer-") as temporary:
        ran = []
        reused = installs.found.get(producer_key(repo, tree, [])) if installs else None
        for command in consumer_commands(repo, tree, Path(temporary), sources, reused):
            if isinstance(command, Execute):
                failure = executed(command, repo, environment)
                ran.append(f"{command.package}:{command.name}")
            else:
                failure = checked(command, repo, environment)
            if failure:
                return failure
    message = (
        tree.name
        + ": installed and relocated consumers built: "
        + ", ".join(name for name, _ in sources)
    )
    ran_text = "; ran: " + ", ".join(ran) if ran else ""
    return Result.ok(message + ran_text + suffix)


class Consumer(Always):
    name = "consumer"
    group = "consumer"
    provider = "cxx"
    rules = ("EN-04.5",)

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py gate consumer")
        parser.add_argument("--tree")
        args = parser.parse_args(argv)
        selected = [
            tree for tree in trees(repo) if not args.tree or tree.name == args.tree
        ]
        if not selected:
            raise CannotRunError(f"unknown consumer tree: {args.tree}")
        results = [consume(repo, tree) for tree in selected]
        findings = tuple(finding for result in results for finding in result.findings)
        return Result(
            1 if findings else 0,
            "\n".join(result.message for result in results),
            findings,
        )
