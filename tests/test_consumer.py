# SPDX-License-Identifier: MIT
"""Prove separate packages and relocated consumers under one project (AR-8)."""

import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from house.config import validate
from house.core import CannotRunError
from house.gates import consumer as gate
from house.gates.consumer import (
    Consumer,
    consume,
    consumer_sources,
    producer_without_tests,
)
from house.runner import execute
from house.trees import Tree
from tests.cmake_support import MODULE, Project
from tests.conftest import axes_config, git


@pytest.fixture
def packages(repo, write):
    repo.config["house"]["languages"] = ["cxx"]
    repo.config["packages"] = {
        name: {"path": "libs/" + name, "modes": {"host": "build-test-install"}}
        for name in ("a", "b")
    }
    write(".gitignore", "build*/\n")
    write(
        "CMakeLists.txt",
        f"""
cmake_minimum_required(VERSION 3.24)
project(synthetic VERSION 9.8.7 LANGUAGES C CXX)
include({json.dumps(MODULE.as_posix())})
house_cxx_common_settings(OFF)
add_subdirectory(libs/a)
add_subdirectory(libs/b)
""",
    )
    for name, version in (("a", "0.3.1"), ("b", "1.2.3")):
        write(
            f"libs/{name}/include/synthetic_{name}/value.hpp",
            f"""
#pragma once
namespace synthetic_{name} {{ int value(); }}
""",
        )
        dependency = '#include "synthetic_a/value.hpp"\n' if name == "b" else ""
        value = "synthetic_a::value() + 1" if name == "b" else "1"
        write(
            f"libs/{name}/value.cpp",
            f"""
#include "synthetic_{name}/value.hpp"
{dependency}
namespace synthetic_{name} {{ int value() {{ return {value}; }} }}
""",
        )
        link = (
            "target_link_libraries(synthetic_b_value PUBLIC synthetic_a::value)"
            if name == "b"
            else ""
        )
        depends = "DEPENDS synthetic_a" if name == "b" else ""
        write(
            f"libs/{name}/CMakeLists.txt",
            f"""
house_cxx_add_strict_target(synthetic_{name}_strict LANGUAGES CXX)
add_library(synthetic_{name}_value STATIC value.cpp)
add_library(synthetic_{name}::value ALIAS synthetic_{name}_value)
target_sources(synthetic_{name}_value PUBLIC FILE_SET HEADERS
    BASE_DIRS include FILES include/synthetic_{name}/value.hpp)
target_include_directories(synthetic_{name}_value PUBLIC
    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
    $<INSTALL_INTERFACE:${{CMAKE_INSTALL_INCLUDEDIR}}>)
target_link_libraries(synthetic_{name}_value PRIVATE synthetic_{name}_strict)
{link}
house_cxx_install_package(PACKAGE synthetic_{name} VERSION {version}
    NAMESPACE synthetic_{name} TARGETS synthetic_{name}_value synthetic_{name}_strict
    {depends})
""",
        )
        write(
            f"libs/{name}/tests/consumer/CMakeLists.txt",
            f"""
cmake_minimum_required(VERSION 3.24)
project(consumer_{name} LANGUAGES C CXX)
find_package(synthetic_{name} {version} CONFIG REQUIRED)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE synthetic_{name}::value)
""",
        )
        write(
            f"libs/{name}/tests/consumer/main.cpp",
            f"""
#include "synthetic_{name}/value.hpp"
int main() {{ return synthetic_{name}::value() > 0 ? 0 : 1; }}
""",
        )
    return repo


def test_gate_builds_both_relocated_find_package_consumers(packages):
    entry = execute(packages, Consumer(), ci=True)
    assert entry.result.status == 0, entry.result
    assert "installed and relocated consumers built: a, b" in entry.result.message
    assert not (packages.root / "build").exists()


def test_gate_rejects_broken_consumer_accepts_repair_and_unreadable(packages, write):
    path = "libs/b/tests/consumer/main.cpp"
    old = packages.read(path)
    write(path, "int main() { return missing_name; }\n")
    entry = execute(packages, Consumer())
    assert entry.result.status == 1
    assert "missing_name" in str(entry.result)
    write(path, old)
    assert execute(packages, Consumer()).result.status == 0
    write("libs/b/tests/consumer/CMakeLists.txt", b"\xff")
    entry = execute(packages, Consumer())
    assert entry.result.status == 2
    assert "cannot read" in entry.result.message


def test_no_indexed_consumer_is_unavailable(packages):
    git(packages.root, "rm", "--cached", "libs/a/tests/consumer/CMakeLists.txt")
    entry = execute(packages, Consumer())
    assert entry.result.status == 2
    assert "a: no indexed consumer" in entry.result.message


def test_modes_exclude_uninstalled_packages_and_undeclared_trees(packages):
    packages.config["packages"]["a"]["modes"]["host"] = "build-test"
    assert [name for name, _ in consumer_sources(packages, Tree("host"))] == ["b"]
    assert consumer_sources(packages, Tree("alternate")) == []
    entry = execute(packages, Consumer(), ("--tree", "absent"))
    assert entry.result.status == 2
    assert "unknown consumer tree" in entry.result.message


def test_missing_cmake_is_unavailable(packages, monkeypatch):
    original = subprocess.run

    def missing(command, *args, **kwargs):
        if command[0] == "cmake":
            raise FileNotFoundError("cmake is absent")
        return original(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", missing)
    entry = execute(packages, Consumer())
    assert entry.result.status == 2
    assert "cannot execute cmake" in entry.result.message


def test_package_exports_are_distinct_relocatable_and_do_not_leak_flags(packages):
    project = Project(packages.root)
    project.command(
        "cmake",
        "-S",
        str(packages.root),
        "-B",
        str(project.build),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Debug",
    )
    project.compile()
    stage = packages.root / "stage"
    project.command("cmake", "--install", str(project.build), "--prefix", str(stage))
    configs = list(stage.rglob("*Config.cmake"))
    assert {p.name for p in configs} == {
        "synthetic_aConfig.cmake",
        "synthetic_bConfig.cmake",
    }
    for path in stage.rglob("*.cmake"):
        text = path.read_text()
        assert str(packages.root) not in text
        for flag in ("-Wconversion", "-Werror", "-fsanitize", "-fstack-protector"):
            assert flag not in text
    b_config = next(p for p in configs if p.name == "synthetic_bConfig.cmake")
    assert "find_dependency(synthetic_a CONFIG)" in b_config.read_text()
    assert "check_required_components(synthetic_b)" in b_config.read_text()
    relocated = packages.root / "relocated stage"
    stage.rename(relocated)
    for name in ("a", "b"):
        source = packages.root / f"libs/{name}/tests/consumer"
        build = packages.root / f"build-consumer-{name}"
        project.command(
            "cmake",
            "-S",
            str(source),
            "-B",
            str(build),
            "-G",
            "Ninja",
            "-DCMAKE_PREFIX_PATH=" + str(relocated),
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        )
        project.command("cmake", "--build", str(build))
        line = json.loads((build / "compile_commands.json").read_text())
        assert not any("-Wconversion" in item.get("command", "") for item in line)
    assert all(
        path.is_relative_to(stage)
        for path in map(
            Path,
            (project.build / "install_manifest.txt").read_text().splitlines(),
        )
    )


@pytest.mark.parametrize(
    ("package", "want", "compatible"),
    [
        ("a", "0.3.0", True),
        ("a", "0.2.0", False),
        ("a", "0.3.2", False),
        ("b", "1.1.0", True),
        ("b", "2.0.0", False),
        ("b", "1.3.0", False),
    ],
)
def test_package_version_compatibility_uses_explicit_identity(
    packages,
    package,
    want,
    compatible,
):
    project = Project(packages.root)
    project.command(
        "cmake",
        "-S",
        str(project.root),
        "-B",
        str(project.build),
        "-G",
        "Ninja",
    )
    major, minor, patch = want.split(".")
    version_file = (
        project.build / f"libs/{package}/synthetic_{package}ConfigVersion.cmake"
    )
    script = project.write(
        "version.cmake",
        f"""
set(PACKAGE_FIND_VERSION {want})
set(PACKAGE_FIND_VERSION_MAJOR {major})
set(PACKAGE_FIND_VERSION_MINOR {minor})
set(PACKAGE_FIND_VERSION_PATCH {patch})
set(PACKAGE_FIND_VERSION_COUNT 3)
set(CMAKE_SIZEOF_VOID_P 8)
include({json.dumps(version_file.as_posix())})
message(STATUS "compatible=${{PACKAGE_VERSION_COMPATIBLE}}")
""",
    )
    output = project.command("cmake", "-P", str(script))
    assert f"compatible={'TRUE' if compatible else 'FALSE'}" in output


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ("VERSION 1.0.0 NAMESPACE sample TARGETS lib", "PACKAGE is required"),
        ("PACKAGE sample NAMESPACE sample TARGETS lib", "VERSION is required"),
        ("PACKAGE sample VERSION 1.0.0 TARGETS lib", "NAMESPACE is required"),
        ("PACKAGE sample VERSION 1.0.0 NAMESPACE sample", "TARGETS is required"),
        (
            "PACKAGE sample VERSION invalid NAMESPACE sample TARGETS lib",
            "VERSION must be",
        ),
        (
            "PACKAGE sample VERSION 1.0.0 NAMESPACE sample TARGETS sample_core core",
            "another target in TARGETS already claims",
        ),
    ],
)
def test_install_argument_and_export_name_refusals(tmp_path, arguments, expected):
    project = Project(tmp_path)
    project.configure(
        "add_library(lib STATIC unit.cpp)\n"
        "add_library(sample_core INTERFACE)\nadd_library(core INTERFACE)\n"
        f"house_cxx_install_package({arguments})",
        expected=expected,
    )


def test_explicit_config_snippet_and_duplicate_package_are_checked(tmp_path):
    project = Project(tmp_path)
    project.write("snippet.cmake", 'set(sample_extra "${CMAKE_CURRENT_LIST_DIR}")\n')
    body = """
add_library(lib STATIC unit.cpp)
house_cxx_install_package(PACKAGE sample VERSION 0.1.0 NAMESPACE sample
    TARGETS lib CONFIG_SNIPPET ${CMAKE_CURRENT_SOURCE_DIR}/snippet.cmake)
"""
    project.configure(body)
    config = (project.build / "sampleConfig.cmake").read_text()
    assert 'set(sample_extra "${CMAKE_CURRENT_LIST_DIR}")' in config
    project.configure(
        body + "\nhouse_cxx_install_package(PACKAGE sample VERSION 0.1.0 "
        "NAMESPACE sample TARGETS lib)",
        expected="is already registered",
    )


def test_consumer_gate_is_not_applicable_without_cpp(repo):
    entry = execute(repo, Consumer(), ci=True)
    assert entry.verdict == "N/A"
    assert entry.result.message == "cxx not declared"


def test_profile_arguments_and_environment_reach_producer_and_consumers(
    packages, write,
):
    for package in packages.config["packages"].values():
        package["modes"]["alternate"] = "build-install"
    guard = """
if(NOT SAMPLE_PROFILE)
    message(FATAL_ERROR "profile argument missing")
endif()
if(NOT "$ENV{SAMPLE_ENV}" STREQUAL "profile-value")
    message(FATAL_ERROR "profile environment missing")
endif()
"""
    for path in (
        "CMakeLists.txt",
        "libs/a/tests/consumer/CMakeLists.txt",
        "libs/b/tests/consumer/CMakeLists.txt",
    ):
        write(path, packages.read(path) + guard)
    tree = Tree("alternate", ("-DSAMPLE_PROFILE=ON",), {"SAMPLE_ENV": "profile-value"})
    result = consume(packages, tree)
    assert result.status == 0, result
    assert "consumers built: a, b" in result.message


def test_producer_without_install_rules_is_unavailable(packages, write):
    write(
        "CMakeLists.txt",
        """cmake_minimum_required(VERSION 3.24)
project(no_install LANGUAGES C CXX)
add_library(lib STATIC unit.cpp)
""",
    )
    write("unit.cpp", "int value() { return 1; }\n")
    entry = execute(packages, Consumer())
    assert entry.result.status == 2
    assert "no install rules ran" in entry.result.message


def exit_with(write, name, status):
    write(
        f"libs/{name}/tests/consumer/main.cpp",
        f"""
#include "synthetic_{name}/value.hpp"
int main() {{ return synthetic_{name}::value() > 0 ? {status} : 1; }}
""",
    )


def test_named_consumer_executables_run_and_pass_on_exit_zero(packages):
    for package in packages.config["packages"].values():
        package["consumer_executables"] = ["consumer"]
    entry = execute(packages, Consumer(), ci=True)
    assert entry.result.status == 0, entry.result
    assert "consumers built: a, b; ran: a:consumer, b:consumer" in entry.result.message


def test_a_named_executable_that_exits_nonzero_fails_with_its_status(packages, write):
    exit_with(write, "b", 3)
    for package in packages.config["packages"].values():
        package["consumer_executables"] = ["consumer"]
    entry = execute(packages, Consumer())
    assert entry.result.status == 1
    assert "b: consumer executable consumer exited with status 3" in str(entry.result)


def test_a_named_executable_that_was_not_built_fails_clearly(packages):
    packages.config["packages"]["a"]["consumer_executables"] = ["absent"]
    entry = execute(packages, Consumer())
    assert entry.result.status == 1
    assert "a: consumer executable absent was not built" in str(entry.result)


def test_without_the_key_a_failing_program_is_built_but_not_run(packages, write):
    exit_with(write, "a", 3)
    entry = execute(packages, Consumer())
    assert entry.result.status == 0, entry.result
    assert "consumers built: a, b" in entry.result.message
    assert "ran:" not in entry.result.message


def test_trees_other_than_host_build_their_consumers_without_running_them(
    packages,
    write,
):
    exit_with(write, "a", 3)
    for package in packages.config["packages"].values():
        package["modes"]["alternate"] = "build-install"
    packages.config["packages"]["a"]["consumer_executables"] = ["consumer"]
    result = consume(packages, Tree("alternate"))
    assert result.status == 0, result
    assert "ran:" not in result.message
    assert execute(packages, Consumer()).result.status == 1


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("consumer_executables='consumer'", "expected an array of strings"),
        ("consumer_executables=[]", "expected at least one executable"),
        ("consumer_executables=[1]", "expected a nonempty string"),
        ("consumer_executables=[' ']", "expected a nonempty string"),
        ("consumer_executables=['a','a']", "duplicate values"),
        ("consumer_executables=['/bin/true']", "relative to the repository"),
        ("consumer_executables=['../x']", "stay inside the repository"),
        ("consumer_executables=['bin\\\\x']", "forward slashes"),
        (
            "consumer_executables=['c']\nmodes={host='build-test'}",
            "needs an installable host mode",
        ),
        (
            "consumer_executables=['c']\nmodes={firmware='build-install'}",
            "needs an installable host mode",
        ),
    ],
)
def test_a_malformed_consumer_executables_key_is_refused(source, expected):
    document = tomllib.loads("[packages.sample]\npath='.'\n" + source)
    with pytest.raises(CannotRunError, match=expected):
        validate(document)


def test_a_wellformed_consumer_executables_key_is_kept():
    document = tomllib.loads(
        "[packages.sample]\npath='.'\nconsumer_executables=['consumer', 'bin/run']",
    )
    config = validate(document)
    assert config["packages"]["sample"]["consumer_executables"] == [
        "consumer",
        "bin/run",
    ]


@pytest.fixture
def rooted(repo, write):
    """One package at the root whose test tree cannot compile."""
    repo.config["house"]["languages"] = ["cxx"]
    repo.config["packages"] = {
        "rooted": {
            "path": ".",
            "modes": {"host": "build-test-install"},
            "consumer_executables": ["consumer"],
        },
    }
    write(".gitignore", "build*/\n")
    write(
        "CMakeLists.txt",
        f"""
cmake_minimum_required(VERSION 3.24)
project(rooted VERSION 1.2.3 LANGUAGES C CXX)
include({json.dumps(MODULE.as_posix())})
house_cxx_common_settings(OFF)
house_cxx_declare_tests_option(ROOTED)
house_cxx_add_strict_target(rooted_strict LANGUAGES CXX)
add_library(rooted_value STATIC value.cpp)
add_library(rooted::value ALIAS rooted_value)
target_sources(rooted_value PUBLIC FILE_SET HEADERS
    BASE_DIRS include FILES include/rooted/value.hpp)
target_include_directories(rooted_value PUBLIC
    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
    $<INSTALL_INTERFACE:${{CMAKE_INSTALL_INCLUDEDIR}}>)
target_link_libraries(rooted_value PRIVATE rooted_strict)
house_cxx_install_package(PACKAGE rooted VERSION 1.2.3 NAMESPACE rooted
    TARGETS rooted_value rooted_strict)
if(ROOTED_ENABLE_TESTS)
    add_subdirectory(tests)
endif()
""",
    )
    write(
        "include/rooted/value.hpp",
        "#pragma once\nnamespace rooted { int value(); }\n",
    )
    write(
        "value.cpp",
        '#include "rooted/value.hpp"\nnamespace rooted { int value() { return 1; } }\n',
    )
    write("tests/CMakeLists.txt", "add_executable(rooted_tests broken_test.cpp)\n")
    write("tests/broken_test.cpp", '#error "the producer built its tests"\n')
    write(
        "tests/consumer/CMakeLists.txt",
        """
cmake_minimum_required(VERSION 3.24)
project(consumer_rooted LANGUAGES C CXX)
find_package(rooted 1.2.3 CONFIG REQUIRED)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE rooted::value)
""",
    )
    write(
        "tests/consumer/main.cpp",
        '#include "rooted/value.hpp"\n'
        "int main() { return rooted::value() > 0 ? 0 : 1; }\n",
    )
    return repo


def recorded(monkeypatch):
    """Return the (command, output) pairs the consumer gate ran."""
    seen, original = [], gate.run

    def spy(command, *args, **kwargs):
        done = original(command, *args, **kwargs)
        seen.append((command, done.stdout + done.stderr))
        return done

    monkeypatch.setattr(gate, "run", spy)
    return seen


def test_the_producer_is_configured_without_its_tests_and_builds_none(
    rooted, monkeypatch,
):
    seen = recorded(monkeypatch)
    entry = execute(rooted, Consumer())
    assert entry.result.status == 0, entry.result
    assert "ran: rooted:consumer" in entry.result.message
    configure = next(c for c, _ in seen if "-DROOTED_ENABLE_TESTS=OFF" in c)
    assert "producer" in configure[configure.index("-B") + 1]
    producer = [output for c, output in seen if "producer" in " ".join(c)]
    assert not any("rooted_tests" in output for output in producer)
    assert not any("broken_test" in output for output in producer)


def test_the_producer_still_installs_and_the_relocated_consumer_runs(rooted):
    entry = execute(rooted, Consumer(), ("--tree", "host"))
    assert entry.result.status == 0, entry.result
    assert "installed and relocated consumers built: rooted" in entry.result.message


def test_a_failing_consumer_still_fails_without_the_producers_tests(rooted, write):
    write("tests/consumer/main.cpp", "int main() { return missing_name; }\n")
    entry = execute(rooted, Consumer())
    assert entry.result.status == 1
    assert "missing_name" in str(entry.result)


def test_a_failing_consumer_program_still_fails_its_gate(rooted, write):
    write(
        "tests/consumer/main.cpp",
        '#include "rooted/value.hpp"\nint main() { return rooted::value() + 2; }\n',
    )
    entry = execute(rooted, Consumer())
    assert entry.result.status == 1
    assert "rooted: consumer executable consumer exited with status 3" in str(
        entry.result,
    )


def test_a_fuzz_tree_keeps_the_tests_its_targets_live_in(rooted, write):
    write(
        "CMakeLists.txt",
        rooted.read("CMakeLists.txt").replace(
            "house_cxx_declare_tests_option(ROOTED)",
            "house_cxx_declare_tests_option(ROOTED)\n"
            "house_cxx_declare_fuzzers_option(ROOTED)",
        ),
    )
    assert producer_without_tests(rooted, Tree("host")) == [
        "-DROOTED_ENABLE_TESTS=OFF",
    ]
    assert producer_without_tests(rooted, Tree("fuzz")) == []


def test_a_package_without_a_declared_tests_option_is_configured_as_before(packages):
    assert producer_without_tests(packages, Tree("host")) == []


def declare_case(repo, package="a", **case):
    """Add a validated consumer case to a package of the synthetic repository."""
    case.setdefault("name", "sample")
    case.setdefault("expect", "runs")
    raw = {
        "house": {"platform": ".", "languages": ["cxx"]},
        "trees": [{"name": "alternate", "profile": "profiles:alternate"}],
        "packages": {package: {"path": "libs/" + package, "consumer_cases": [case]}},
    }
    declared = validate(raw)["packages"][package]["consumer_cases"]
    cases = repo.config["packages"][package].setdefault("consumer_cases", [])
    cases.extend(declared)


@pytest.fixture
def cases(packages, write):
    """Give package a a level, a producer mode and consumer switches to refuse."""
    write(
        "CMakeLists.txt",
        packages.read("CMakeLists.txt").replace(
            "add_subdirectory(libs/a)",
            """set(SYNTH_LEVEL 1 CACHE STRING "")
set(SYNTH_MODE "" CACHE STRING "")
if(SYNTH_MODE STREQUAL "configure-bad")
    message(FATAL_ERROR "synthetic mode configure-bad is not supported by this "
        "library because the sample refuses it at the first configure step")
endif()
if(SYNTH_MODE STREQUAL "warn")
    message(WARNING "synthetic warning from the producer")
endif()
if(SYNTH_MODE STREQUAL "build-bad")
    add_custom_target(boom ALL COMMAND ${CMAKE_COMMAND} -E echo "boom happened"
        COMMAND ${CMAKE_COMMAND} -E false)
endif()
add_subdirectory(libs/a)""",
        ),
    )
    write(
        "libs/a/CMakeLists.txt",
        packages.read("libs/a/CMakeLists.txt")
        + "target_compile_definitions(synthetic_a_value PUBLIC "
        "SYNTH_LEVEL=${SYNTH_LEVEL})\n",
    )
    write(
        "libs/a/tests/consumer/CMakeLists.txt",
        packages.read("libs/a/tests/consumer/CMakeLists.txt")
        + 'if(CONSUMER_MODE STREQUAL "bad")\n'
        '    message(FATAL_ERROR "consumer mode bad is refused")\n'
        "endif()\n",
    )
    write(
        "cases/level/CMakeLists.txt",
        """cmake_minimum_required(VERSION 3.24)
project(level LANGUAGES C CXX)
find_package(synthetic_a 0.3.1 CONFIG REQUIRED)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE synthetic_a::value)
""",
    )
    write(
        "cases/level/main.cpp",
        """#include "synthetic_a/value.hpp"
static_assert(SYNTH_LEVEL == 5, "level did not reach the consumer");
int main() { return synthetic_a::value() > 0 ? 0 : 1; }
""",
    )
    return packages


def case_run(cases, tree="host"):
    return consume(cases, Tree(tree))


def test_a_runs_case_builds_against_its_producer_arguments_and_source(cases):
    declare_case(
        cases,
        name="level",
        producer_args=["-DSYNTH_LEVEL=5"],
        source="cases/level",
    )
    result = case_run(cases)
    assert result.status == 0, result
    assert "cases: a:level (runs)" in result.message
    assert "consumers built: a, b" in result.message


def test_a_runs_case_whose_definition_did_not_arrive_fails_by_name(cases):
    declare_case(cases, name="level", source="cases/level")
    result = case_run(cases)
    assert result.status == 1
    assert "a: case level: consumer-build failed" in str(result)
    assert "level did not reach the consumer" in str(result)


def test_a_runs_case_runs_the_named_executables_of_its_consumer(cases, write):
    cases.config["packages"]["a"]["consumer_executables"] = ["consumer"]
    write(
        "cases/level/main.cpp",
        '#include "synthetic_a/value.hpp"\nint main() { return 3; }\n',
    )
    declare_case(cases, name="level", source="cases/level")
    result = case_run(cases)
    assert result.status == 1
    assert "a: consumer executable consumer exited with status 3" in str(result)


@pytest.mark.parametrize(
    ("stage", "arguments", "message"),
    [
        (
            "producer-configure",
            {"producer_args": ["-DSYNTH_MODE=configure-bad"]},
            "is not supported by this library because the sample refuses it",
        ),
        (
            "producer-build",
            {"producer_args": ["-DSYNTH_MODE=build-bad"]},
            "boom happened",
        ),
        (
            "consumer-configure",
            {"consumer_args": ["-DCONSUMER_MODE=bad"]},
            "consumer mode bad is refused",
        ),
        (
            "consumer-build",
            {"source": "cases/level"},
            "level did not reach the consumer",
        ),
    ],
)
def test_a_fails_case_passes_when_its_stage_fails_with_its_message(
    cases,
    stage,
    arguments,
    message,
):
    declare_case(
        cases,
        name="refused",
        expect="fails",
        stage=stage,
        message=message,
        **arguments,
    )
    result = case_run(cases)
    assert result.status == 0, result
    assert f"a:refused (refused at {stage})" in result.message


def test_a_warning_before_the_expected_stage_fails_the_case(cases):
    declare_case(
        cases,
        name="noisy",
        expect="fails",
        stage="consumer-configure",
        message="consumer mode bad is refused",
        producer_args=["-DSYNTH_MODE=warn"],
        consumer_args=["-DCONSUMER_MODE=bad"],
    )
    result = case_run(cases)
    assert result.status == 1
    assert "a: case noisy: producer-configure failed before the expected" in str(result)
    assert "synthetic warning" in str(result)


def test_a_fails_case_that_succeeds_is_a_failure_naming_the_case(cases):
    declare_case(
        cases,
        name="quiet",
        expect="fails",
        stage="producer-configure",
        message="anything",
    )
    result = case_run(cases)
    assert result.status == 1
    assert "a: case quiet: producer-configure succeeded but was expected" in str(result)


def test_a_fails_case_with_another_message_is_a_failure(cases):
    declare_case(
        cases,
        name="wrong",
        expect="fails",
        stage="producer-configure",
        message="a message nobody prints",
        producer_args=["-DSYNTH_MODE=configure-bad"],
    )
    result = case_run(cases)
    assert result.status == 1
    assert "a: case wrong: producer-configure failed without saying" in str(result)
    assert "configure-bad" in str(result)


def test_a_fails_case_that_fails_earlier_than_stated_is_a_failure(cases):
    declare_case(
        cases,
        name="early",
        expect="fails",
        stage="consumer-build",
        message="configure-bad",
        producer_args=["-DSYNTH_MODE=configure-bad"],
    )
    result = case_run(cases)
    assert result.status == 1
    assert "producer-configure failed before the expected consumer-build" in str(result)


def test_cases_run_only_in_the_tree_they_name(cases):
    declare_case(
        cases,
        name="elsewhere",
        tree="alternate",
        expect="fails",
        stage="producer-configure",
        message="configure-bad",
        producer_args=["-DSYNTH_MODE=configure-bad"],
    )
    assert "cases:" not in case_run(cases).message
    for package in cases.config["packages"].values():
        package["modes"]["alternate"] = "build-install"
    assert "a:elsewhere (refused at producer-configure)" in (
        case_run(cases, "alternate").message
    )


def test_cases_run_when_no_package_mode_installs(cases):
    for package in cases.config["packages"].values():
        package["modes"] = {"host": "build-test"}
    declare_case(
        cases,
        name="level",
        source="cases/level",
        producer_args=["-DSYNTH_LEVEL=5"],
    )
    result = case_run(cases)
    assert result.status == 0, result
    assert "cases: a:level (runs)" in result.message


def test_a_case_source_must_be_indexed(cases):
    declare_case(cases, name="level", source="cases/absent")
    entry = execute(cases, Consumer())
    assert entry.result.status == 2
    assert "case level has no indexed consumer at cases/absent/CMakeLists.txt" in (
        entry.result.message
    )


def test_without_cases_the_gate_reports_exactly_what_it_did_before(packages):
    result = consume(packages, Tree("host"))
    assert result.status == 0
    assert result.message == (
        "host: installed and relocated consumers built: a, b"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("consumer_cases = 'x'", "expected an array of tables"),
        ("consumer_cases = [{expect = 'runs'}]", "expected a nonempty string"),
        ("consumer_cases = [{name = 'Bad', expect = 'runs'}]", "must be valid"),
        (
            ("consumer_cases = [{name = 'a', expect = 'runs'}, "
             "{name = 'a', expect = 'runs'}]"),
            "must be valid and unique",
        ),
        ("consumer_cases = [{name = 'a'}]", 'expected "runs" or "fails"'),
        ("consumer_cases = [{name = 'a', expect = 'pass'}]", 'expected "runs"'),
        ("consumer_cases = [{name = 'a', expect = 'fails'}]", "expected one of"),
        (
            "consumer_cases = [{name = 'a', expect = 'fails', stage = 'link'}]",
            "expected one of",
        ),
        (
            ("consumer_cases = [{name = 'a', expect = 'fails', "
             "stage = 'producer-build'}]"),
            "expected a nonempty string",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', message = 'x'}]",
            "only apply to expect",
        ),
        (
            ("consumer_cases = [{name = 'a', expect = 'runs', "
             "stage = 'consumer-build'}]"),
            "only apply to expect",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', producer_args = 'x'}]",
            "expected an array of strings",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', consumer_args = [1]}]",
            "expected a nonempty string",
        ),
        (
            ("consumer_cases = [{name = 'a', expect = 'runs', "
             "producer_args = ['-DCMAKE_INSTALL_PREFIX=/x']}]"),
            "is set by the gate",
        ),
        (
            ("consumer_cases = [{name = 'a', expect = 'runs', "
             "consumer_args = ['-DCMAKE_PREFIX_PATH=/x']}]"),
            "is set by the gate",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', source = '../x'}]",
            "stay inside the repository",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', tree = 'firmware'}]",
            "unknown tree 'firmware'",
        ),
        (
            "consumer_cases = [{name = 'a', expect = 'runs', colour = 'red'}]",
            "unknown keys",
        ),
    ],
)
def test_a_malformed_consumer_case_declaration_is_refused(source, expected):
    with pytest.raises(CannotRunError, match=expected):
        validate(
            tomllib.loads(f"[packages.sample]\npath='.'\n{source}"),
        )


def test_wellformed_cases_are_kept_and_a_declared_tree_is_accepted():
    config = validate(
        tomllib.loads(
            "[[trees]]\nname='firmware'\nprofile='p:q'\n"
            "[packages.sample]\npath='.'\n"
            "[[packages.sample.consumer_cases]]\nname='board'\ntree='firmware'\n"
            "expect='fails'\nstage='consumer-configure'\nmessage='needs the feature'\n"
            "consumer_args=['-DSAMPLE_VARIANT=other']\n",
        ),
    )
    (case,) = config["packages"]["sample"]["consumer_cases"]
    assert case["tree"] == "firmware"
    assert case["producer_args"] == []
    assert case["consumer_args"] == ["-DSAMPLE_VARIANT=other"]


def test_without_the_key_a_package_declares_no_cases():
    config = validate(tomllib.loads("[packages.sample]\npath='.'\n"))
    assert config["packages"]["sample"]["consumer_cases"] == []


def test_the_consumer_gate_gives_its_producer_the_variable_and_not_its_consumers(
    packages,
    monkeypatch,
):
    path = packages.root / "libs/a/CMakeLists.txt"
    path.write_text(
        path.read_text()
        + 'if(NOT SAMPLE_PROFILE STREQUAL "large")\n'
        '  message(FATAL_ERROR "profile was ${SAMPLE_PROFILE}")\nendif()\n',
    )
    packages.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "large")
    entry = execute(packages, Consumer())
    assert entry.result.status == 0, entry.result
    assert "consumers built: a, b" in entry.result.message


def test_case_consumers_are_not_given_the_axis_variables(cases, monkeypatch):
    cases.config["ci"] = axes_config("[ci.axes]\nprofile='SYNTH_MODE'\n")["ci"]
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "fine")
    declare_case(
        cases,
        name="level",
        source="cases/level",
        producer_args=["-DSYNTH_LEVEL=5"],
    )
    result = case_run(cases)
    assert result.status == 0, result
    assert "cases: a:level (runs)" in result.message


def test_identical_cases_and_default_share_one_install(cases, monkeypatch):
    declare_case(cases, name="first")
    declare_case(cases, package="b", name="second")
    seen = recorded(monkeypatch)
    result = case_run(cases)
    assert result.status == 0, result
    assert sum(command[:2] == ["cmake", "--install"] for command, _ in seen) == 1
    assert "a:first (runs)" in result.message
    assert "b:second (runs)" in result.message
    assert "consumers built: a, b" in result.message


def test_distinct_producer_arguments_get_distinct_installs(cases, monkeypatch):
    declare_case(
        cases, name="large", producer_args=["-DSYNTH_LEVEL=5"], source="cases/level",
    )
    declare_case(
        cases, name="same-large", producer_args=["-DSYNTH_LEVEL=5"],
        source="cases/level",
    )
    seen = recorded(monkeypatch)
    result = case_run(cases)
    assert result.status == 0, result
    assert sum(command[:2] == ["cmake", "--install"] for command, _ in seen) == 2


def test_expected_producer_refusal_is_never_reused(cases, monkeypatch):
    for name in ("first", "second"):
        declare_case(
            cases, name=name, expect="fails", stage="producer-configure",
            producer_args=["-DSYNTH_MODE=configure-bad"], message="configure-bad",
        )
    seen = recorded(monkeypatch)
    result = case_run(cases)
    assert result.status == 0, result
    refused = [
        command for command, _ in seen if "-DSYNTH_MODE=configure-bad" in command
    ]
    assert len(refused) == 2
    assert "a:first (refused at producer-configure)" in result.message
    assert "a:second (refused at producer-configure)" in result.message
