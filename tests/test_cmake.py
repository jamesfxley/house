# SPDX-License-Identifier: MIT
"""Port the frozen language-level CMake regressions (AR-8)."""

import json
import re
import shutil

import pytest

from tests.cmake_support import MODULE, Project


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path)


def test_strict_options_and_c_cxx_language_scopes(project):
    project.configure(
        """
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(s_default)
house_cxx_add_strict_target(s_no_werror WERROR OFF)
house_cxx_add_strict_target(s_cxx LANGUAGES CXX)
house_cxx_add_strict_target(s_free FREESTANDING ON)
house_cxx_add_strict_target(s_vendor VENDOR_SOURCES ON)
house_cxx_add_strict_target(s_no_vendor VENDOR_SOURCES OFF)
foreach(t default no_werror cxx free vendor no_vendor)
    add_library(lib_${t} STATIC unit.c unit.cpp)
    target_link_libraries(lib_${t} PRIVATE s_${t})
endforeach()
""",
        "-DCMAKE_BUILD_TYPE=Release",
    )
    c_line = project.compile_line("lib_default", "unit.c")
    cpp = project.compile_line("lib_default")
    for flag in ("-fPIC", "-Wconversion", "-Werror", "-fstack-protector-strong"):
        assert flag in c_line
        assert flag in cpp
    assert "-std=c11" in c_line
    assert "-Wold-style-cast" not in c_line
    assert "-Wnon-virtual-dtor" not in c_line
    assert "-Wold-style-cast" in cpp
    assert cpp.index("-U_FORTIFY_SOURCE") < cpp.index("-D_FORTIFY_SOURCE=3")
    assert "-Werror " not in project.compile_line("lib_no_werror")
    assert "-Werror " not in project.compile_line("lib_vendor")
    assert "-Werror " in project.compile_line("lib_no_vendor")
    assert "-Wconversion" not in project.compile_line("lib_cxx", "unit.c")
    assert "-Wconversion" in project.compile_line("lib_cxx")
    free = project.compile_line("lib_free")
    assert "_FORTIFY_SOURCE" not in free
    assert "-fstack-protector-strong" in free
    project.compile()


@pytest.mark.parametrize(
    ("build_type", "fortify", "assertions"),
    [
        ("Debug", False, True),
        ("Release", True, False),
        ("RelWithDebInfo", True, False),
        ("MinSizeRel", True, False),
        ("", False, False),
    ],
)
def test_hardening_configuration_conditions(project, build_type, fortify, assertions):
    compiler = shutil.which("g++")
    assert compiler, "GCC is required for the libstdc++ assertions regression"
    output = project.configure(
        """
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(strict)
add_library(lib STATIC unit.cpp)
target_link_libraries(lib PRIVATE strict)
""",
        "-DCMAKE_BUILD_TYPE=" + build_type,
        "-DCMAKE_CXX_COMPILER=" + compiler,
    )
    line = project.compile_line("lib")
    assert ("-D_FORTIFY_SOURCE=3" in line) == fortify
    assert ("_GLIBCXX_ASSERTIONS" in line) == assertions
    assert "_LIBCPP_HARDENING_MODE" not in line
    assert ("-Og" in line) == (build_type == "Debug")
    if not build_type:
        assert "no CMAKE_BUILD_TYPE" in output


def test_freestanding_common_settings_and_derived_strict_default(project):
    output = project.configure(
        """
house_cxx_common_settings(ON)
set(CMAKE_CROSSCOMPILING ON)
house_cxx_add_strict_target(strict)
add_library(lib STATIC unit.c unit.cpp)
target_link_libraries(lib PRIVATE strict)
""",
        "-DCMAKE_BUILD_TYPE=Release",
    )
    assert "-std=gnu11" in project.compile_line("lib", "unit.c")
    assert "-fPIC" not in project.compile_line("lib")
    assert "_FORTIFY_SOURCE" not in project.compile_line("lib")
    assert "hardening not applied: -D_FORTIFY_SOURCE=3" in output


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (
            "house_cxx_add_strict_target(s WERROR ON VENDOR_SOURCES ON)",
            "mutually exclusive",
        ),
        ("house_cxx_add_strict_target(s LANGUAGES Cxx)", "LANGUAGES must be C or CXX"),
        ("house_cxx_werror_sources()", "no sources given"),
        ("house_cxx_werror_sources(missing.cpp)", "no such source"),
        (
            'house_cxx_werror_sources("${CMAKE_CURRENT_SOURCE_DIR}/missing.cpp")',
            "no such source",
        ),
        ("house_cxx_add_module_test(sample widget)", "no SOURCES"),
        ("house_cxx_add_fuzzer(fuzz PACKAGE sample)", "PACKAGE and SOURCE"),
        (
            (
                "house_cxx_declare_enum_option(S NAME MODE DEFAULT tiny "
                "VALUES default large)"
            ),
            "DEFAULT 'tiny' is not one of VALUES",
        ),
        (
            "house_cxx_declare_install_option(S AVAILABLE)",
            "no value given for 'AVAILABLE'",
        ),
    ],
)
def test_helper_refusals_name_the_fault(project, call, expected):
    project.configure(call, expected=expected)


@pytest.mark.parametrize("extra", ["NX", "OFF", "0", "NOTFOUND"])
@pytest.mark.parametrize(
    "call",
    [
        "house_cxx_common_settings(OFF {extra})",
        "house_cxx_declare_tests_option(S {extra})",
        "house_cxx_declare_fuzzers_option(S {extra})",
        "house_cxx_enable_gtest({extra})",
        "house_cxx_enable_sanitizers(S {extra})",
        "house_cxx_version_definitions(lib sample PUBLIC {extra})",
        "house_cxx_add_strict_target(s {extra})",
    ],
)
def test_unparsed_arguments_include_false_constants(project, extra, call):
    project.configure(
        call.format(extra=extra),
        expected=f"unrecognised arguments '{extra}'",
    )


def test_werror_source_flags_append_and_generated_paths(project):
    project.configure("""
house_cxx_common_settings(OFF)
set_property(SOURCE unit.cpp APPEND PROPERTY COMPILE_OPTIONS -DALREADY_HERE)
configure_file(unit.cpp ${CMAKE_CURRENT_BINARY_DIR}/copied.cpp COPYONLY)
add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/made.cpp
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_CURRENT_SOURCE_DIR}/unit.cpp
        ${CMAKE_CURRENT_BINARY_DIR}/made.cpp)
add_library(lib STATIC unit.cpp ${CMAKE_CURRENT_BINARY_DIR}/copied.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/made.cpp)
house_cxx_werror_sources(unit.cpp copied.cpp ${CMAKE_CURRENT_BINARY_DIR}/made.cpp)
""")
    assert "-DALREADY_HERE" in project.compile_line("lib")
    for name in ("unit.cpp", "copied.cpp", "made.cpp"):
        assert "-Werror" in project.compile_line("lib", name)
    project.compile()


def test_vendor_diagnostics_reach_only_owned_linked_sources_once(project):
    project.write("sub/own.cpp", "int own() { return 1; }\n")
    project.write("sub/own.c", "int own_c(void) { return 1; }\n")
    project.write("vendor.cpp", "int vendor() { return 1; }\n")
    project.write(
        "sub/CMakeLists.txt",
        """
add_library(own STATIC own.cpp own.c)
target_link_libraries(own PRIVATE strict vendor)
add_library(again STATIC own.cpp)
target_link_libraries(again PRIVATE strict)
add_library(plain STATIC own.cpp)
""",
    )
    project.configure("""
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(strict VENDOR_SOURCES ON LANGUAGES CXX)
add_library(vendor INTERFACE)
target_sources(vendor INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/vendor.cpp)
add_subdirectory(sub)
""")
    own = project.compile_line("own", "own.cpp")
    assert own.split().count("-Wconversion") == 1
    assert "-Werror " not in own
    assert "-Wold-style-cast" in own
    vendor = project.compile_line("own", "vendor.cpp")
    assert "-Wconversion" not in vendor
    assert "-fstack-protector-strong" in vendor
    assert "-Wconversion" not in project.compile_line("plain", "own.cpp")
    assert "-Wconversion" not in project.compile_line("own", "own.c")
    project.compile()


def test_vendor_reach_across_directories_interfaces_aliases_and_objects(project):
    project.write(
        "lib/CMakeLists.txt",
        """
house_cxx_add_strict_target(strict++ VENDOR_SOURCES ON LANGUAGES CXX)
add_library(strict_alias ALIAS strict++)
""",
    )
    project.write(
        "sibling/CMakeLists.txt",
        """
add_library(sibling STATIC ../unit.cpp)
target_link_libraries(sibling PRIVATE strict_alias)
""",
    )
    project.configure("""
house_cxx_common_settings(OFF)
add_subdirectory(lib)
add_subdirectory(sibling)
add_library(mid INTERFACE)
target_link_libraries(mid INTERFACE strict++)
add_library(top STATIC unit.cpp)
target_link_libraries(top PRIVATE mid)
add_library(objs OBJECT unit.cpp)
target_link_libraries(objs PRIVATE strict++)
add_library(fromobjs STATIC $<TARGET_OBJECTS:objs>)
target_link_libraries(fromobjs PRIVATE strict++)
add_library(private_lib STATIC unit.cpp)
target_link_libraries(private_lib PRIVATE strict++)
add_library(beyond STATIC unit.cpp)
target_link_libraries(beyond PRIVATE private_lib)
add_library(other STATIC unit.cpp)
target_link_libraries(other PRIVATE $<$<CONFIG:NoSuchConfig>:strict++_extra>)
""")
    for target in ("sibling", "top", "objs", "private_lib"):
        assert "-Wconversion" in project.compile_line(target)
    for target in ("beyond", "other"):
        assert "-Wconversion" not in project.compile_line(target)
    project.compile()


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        (
            (
                "add_library(lib STATIC $<1:unit.cpp>)\n"
                "target_link_libraries(lib PRIVATE strict)"
            ),
            "cannot apply the warning set to the generator-expression source",
        ),
        (
            (
                "add_library(lib STATIC unit.cpp)\n"
                "target_link_libraries(lib PRIVATE $<1:strict>)"
            ),
            "warning set cannot follow",
        ),
    ],
)
def test_vendor_unresolvable_generator_expressions_are_refused(project, part, expected):
    project.configure(
        "house_cxx_add_strict_target(strict VENDOR_SOURCES ON)\n" + part,
        expected=expected,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("enormous", "got 'enormous'"),
        ("", "got ''"),
        ("has space", "got 'has space'"),
    ],
)
def test_enum_values_are_validated_without_parse_errors(project, value, expected):
    project.configure(
        "house_cxx_declare_enum_option(S NAME MODE DEFAULT default "
        "VALUES default large)",
        "-DS_MODE=" + value,
        expected=expected,
    )


def test_option_defaults_overrides_and_subproject_scope(project):
    project.write(
        "child/CMakeLists.txt",
        f"""
include({json.dumps(MODULE.as_posix())})
project(child LANGUAGES NONE)
house_cxx_declare_tests_option(CHILD)
house_cxx_declare_install_option(CHILD)
message(STATUS "child=${{CHILD_ENABLE_TESTS}}/${{CHILD_ENABLE_INSTALL}}")
""",
    )
    output = project.configure(
        """
house_cxx_declare_tests_option(S)
house_cxx_declare_install_option(S)
house_cxx_declare_install_option(ABSENT AVAILABLE OFF)
house_cxx_declare_install_option(PRESENT AVAILABLE ON)
house_cxx_declare_enum_option(S NAME MODE DEFAULT default VALUES default large)
message(STATUS "root=${S_ENABLE_TESTS}/${S_ENABLE_INSTALL}/${S_MODE}")
message(STATUS "available=${ABSENT_ENABLE_INSTALL}/${PRESENT_ENABLE_INSTALL}")
add_subdirectory(child)
""",
        "-DS_MODE=large",
    )
    assert "root=ON/ON/large" in output
    assert "available=OFF/ON" in output
    assert "child=OFF/OFF" in output
    output = project.command(
        "cmake",
        "-S",
        str(project.root),
        "-B",
        str(project.build),
        "-DS_ENABLE_TESTS=OFF",
    )
    assert "root=OFF/ON/large" in output


def test_cross_default_disables_tests_and_sanitizers_refuse(project):
    output = project.configure("""
set(CMAKE_CROSSCOMPILING ON)
house_cxx_declare_tests_option(S)
message(STATUS "tests=${S_ENABLE_TESTS}")
""")
    assert "tests=OFF" in output
    project.configure(
        "set(CMAKE_CROSSCOMPILING ON)\nhouse_cxx_enable_sanitizers(S)",
        "-DS_SANITIZE=ON",
        expected="cross-compiling build",
    )


def test_version_definitions_obey_requested_visibility(project):
    project.configure("""
add_library(lib STATIC unit.cpp)
house_cxx_version_definitions(lib sample PUBLIC)
add_library(user STATIC unit.cpp)
target_link_libraries(user PRIVATE lib)
add_library(priv STATIC unit.cpp)
house_cxx_version_definitions(priv hidden PRIVATE)
add_library(user_private STATIC unit.cpp)
target_link_libraries(user_private PRIVATE priv)
""")
    assert "SAMPLE_CMAKE_VERSION_MAJOR=1" in project.compile_line("lib")
    assert "SAMPLE_CMAKE_VERSION_MINOR=2" in project.compile_line("user")
    assert "SAMPLE_CMAKE_VERSION_PATCH=3" in project.compile_line("user")
    assert "HIDDEN_CMAKE_VERSION_MAJOR=1" in project.compile_line("priv")
    assert "HIDDEN_CMAKE_VERSION" not in project.compile_line("user_private")


def test_sanitizers_instrument_linked_and_subdirectory_targets(project):
    project.write("child/CMakeLists.txt", "add_library(child STATIC ../unit.cpp)\n")
    project.configure(
        """
house_cxx_enable_sanitizers(S)
add_subdirectory(child)
add_executable(app unit.cpp)
""",
        "-DS_SANITIZE=ON",
    )
    assert "-fsanitize=address,undefined" in project.compile_line("app")
    assert "-fno-sanitize-recover=all" in project.compile_line("child")
    assert "-fsanitize=address,undefined" in (project.build / "build.ninja").read_text()


def test_gtest_ordering_and_module_tests_without_network(project):
    project.write(
        "framework/CMakeLists.txt",
        """
add_library(gtest_main INTERFACE)
add_library(GTest::gtest_main ALIAS gtest_main)
""",
    )
    configure = """
house_cxx_enable_gtest()
house_cxx_enable_sanitizers(S)
"""
    project.configure(configure, "-DS_SANITIZE=ON", expected="before this macro")
    # Existing framework targets exercise ordering without downloading a framework.
    body = """
add_subdirectory(framework)
house_cxx_enable_gtest()
house_cxx_add_strict_target(sample_strict)
add_library(sample_widget INTERFACE)
add_library(sample::widget ALIAS sample_widget)
house_cxx_add_module_test(sample widget SOURCES unit.cpp)
house_cxx_add_module_test(sample widget SOURCES unit.cpp NAME second_tests)
"""
    project.configure(body, "-DS_SANITIZE=OFF", "-DCMAKE_BUILD_TYPE=Debug")
    line = project.compile_line("sample_widget_tests")
    assert "-Wconversion" in line
    assert "-Werror " in line
    ctest = (project.build / "CTestTestfile.cmake").read_text()
    # GoogleTest discovery files: CMake 4.2 names them target[N]_include.cmake;
    # CMake 4.4 uses target_<first 8 hex of the argument SHA-256>_include.cmake.
    for target in ("sample_widget_tests", "second_tests"):
        discovery = re.escape(target) + r"(\[\d+\]|_[0-9a-f]{8})_include\.cmake"
        assert re.search(discovery, ctest)
    project.configure(
        "set(UNRELATED_SANITIZE ON)\nadd_compile_options(-fsanitize=address)\n" + body,
    )


def test_fuzz_option_off_on_instrumentation_and_output_directory(project):
    compiler = shutil.which("clang++-20") or shutil.which("clang++")
    assert compiler, "clang++ is required for the real fuzzer regression"
    project.write(
        "fuzz.cpp",
        """
#include <cstddef>
#include <cstdint>
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t*, std::size_t) { return 0; }
""",
    )
    body = """
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(sample_strict)
house_cxx_declare_tests_option(SAMPLE)
house_cxx_declare_fuzzers_option(SAMPLE)
add_library(lib STATIC unit.cpp)
house_cxx_add_fuzzer(parser_fuzz PACKAGE sample SOURCE fuzz.cpp LIBRARIES lib
    OUTPUT_DIR ${CMAKE_BINARY_DIR}/elsewhere)
"""
    project.write("corpus/parser_fuzz/seed", "seed")
    project.configure(body, "-DCMAKE_CXX_COMPILER=" + compiler)
    assert "parser_fuzz.dir" not in (project.build / "build.ninja").read_text()
    default_body = body.replace("OUTPUT_DIR ${CMAKE_BINARY_DIR}/elsewhere", "")
    project.configure(default_body, "-DSAMPLE_ENABLE_FUZZERS=ON")
    assert "fuzzers/parser_fuzz" in (project.build / "build.ninja").read_text()
    project.configure(body, "-DSAMPLE_ENABLE_FUZZERS=ON")
    assert "-fsanitize=fuzzer-no-link,address,undefined" in project.compile_line("lib")
    assert "-fsanitize=fuzzer,address" in project.compile_line(
        "parser_fuzz",
        "fuzz.cpp",
    )
    assert "-Wconversion" in project.compile_line("parser_fuzz", "fuzz.cpp")
    assert "elsewhere/parser_fuzz" in (project.build / "build.ninja").read_text()
    project.compile()
    project.configure(
        body,
        "-DSAMPLE_ENABLE_TESTS=OFF",
        expected="requires SAMPLE_ENABLE_TESTS=ON",
    )


def test_fuzz_option_before_targets(project):
    compiler = shutil.which("clang++-20") or shutil.which("clang++")
    project.configure(
        """
add_library(early STATIC unit.cpp)
house_cxx_declare_tests_option(S)
house_cxx_declare_fuzzers_option(S)
""",
        "-DCMAKE_CXX_COMPILER=" + compiler,
        "-DS_ENABLE_FUZZERS=ON",
        expected="runs after target early",
    )


def test_include_is_definition_only_and_helpers_reach_sibling_projects(project):
    output = project.configure(
        "",
        "--trace-format=json-v1",
        "--trace-source=" + str(MODULE),
        languages="NONE",
    )
    commands = [
        json.loads(line) for line in output.splitlines() if line.startswith('{"args":')
    ]
    assert commands
    for item in commands:
        assert item["cmd"] in {
            "include_guard", "function", "endfunction", "macro", "endmacro",
        }
    for name in ("a", "b"):
        project.write(
            name + "/CMakeLists.txt",
            f"""
include({json.dumps(MODULE.as_posix())})
if(NOT COMMAND house_cxx_common_settings)
    message(FATAL_ERROR "shared helper definitions missing")
endif()
message(STATUS "{name}=helpers available")
""",
        )
    output = project.configure(
        "add_subdirectory(a)\nadd_subdirectory(b)\n",
        languages="NONE",
    )
    assert "a=helpers available" in output
    assert "b=helpers available" in output


def test_documented_cmake_example_builds_and_installs(project):
    text = (MODULE.parent.parent / "README.md").read_text()
    example = text.split("```cmake\n", 1)[1].split("```", 1)[0]
    project.write("CMakeLists.txt", example)
    destination = project.root / "platform/cxx/cmake"
    destination.mkdir(parents=True)
    shutil.copyfile(MODULE, destination / "house.cmake")
    project.write(
        "src/core.cpp",
        '#include "synthetic/core.hpp"\nint value() { return 1; }\n',
    )
    project.write("include/synthetic/core.hpp", "#pragma once\nint value();\n")
    project.command(
        "cmake",
        "-S",
        str(project.root),
        "-B",
        str(project.build),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Debug",
    )
    project.compile()
    project.command(
        "cmake",
        "--install",
        str(project.build),
        "--prefix",
        str(project.root / "prefix"),
    )
    assert list((project.root / "prefix").rglob("syntheticConfig.cmake"))


def test_unavailable_fuzzer_warns_and_emits_no_target(project):
    compiler = shutil.which("g++")
    assert compiler, "GCC is required for the unsupported fuzzer regression"
    project.write("corpus/sample_fuzz/seed", "seed")
    project.configure(
        """
set(S_ENABLE_FUZZERS ON)
house_cxx_add_fuzzer(sample_fuzz PACKAGE s SOURCE unit.cpp)
""",
        "-DCMAKE_CXX_COMPILER=" + compiler,
        expected_warning="lacks -fsanitize=fuzzer",
    )
    assert "sample_fuzz.dir" not in (project.build / "build.ninja").read_text()


FUZZ_BODY = """
enable_testing()
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(sample_strict)
house_cxx_declare_tests_option(SAMPLE)
house_cxx_declare_fuzzers_option(SAMPLE)
add_library(lib STATIC unit.cpp)
house_cxx_add_fuzzer(parser_fuzz PACKAGE sample SOURCE fuzz.cpp LIBRARIES lib
    {options})
"""


def fuzz_project(project, options="", trap="", seeds=("seed",)):
    compiler = shutil.which("clang++-20") or shutil.which("clang++")
    assert compiler, "clang++ is required for the real fuzzer regression"
    project.write(
        "fuzz.cpp",
        f"""
#include <cstddef>
#include <cstdint>
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {{
    {trap}
    (void)data;
    (void)size;
    return 0;
}}
""",
    )
    for seed in seeds:
        project.write(f"corpus/parser_fuzz/{seed}", seed)
    project.configure(
        FUZZ_BODY.format(options=options),
        "-DCMAKE_CXX_COMPILER=" + compiler,
        "-DSAMPLE_ENABLE_FUZZERS=ON",
    )
    project.compile()


def run_fuzz_test(project, expected=None):
    return project.command(
        "ctest",
        "--test-dir",
        str(project.build),
        "-R",
        "parser_fuzz_bounded_run",
        "--output-on-failure",
        "-V",
        expected=expected,
    )


def test_a_fuzzer_registers_a_bounded_run_over_its_seed_corpus(project):
    fuzz_project(project, "RUNS 7")
    listing = project.command("ctest", "--test-dir", str(project.build), "-N")
    assert "parser_fuzz_bounded_run" in listing
    labelled = project.command(
        "ctest", "--test-dir", str(project.build), "-N", "-L", "fuzz",
    )
    assert "parser_fuzz_bounded_run" in labelled
    output = run_fuzz_test(project)
    assert "Done 7 runs" in output
    assert "seed" in output
    assert sorted(p.name for p in (project.root / "corpus/parser_fuzz").iterdir()) == [
        "seed",
    ]


def test_the_bounded_run_replays_the_seed_corpus(project):
    fuzz_project(
        project,
        "RUNS 5",
        trap="if (size == 1 && data[0] == 'X') { __builtin_trap(); }",
        seeds=("X",),
    )
    run_fuzz_test(project, expected="parser_fuzz_bounded_run")


def test_the_default_run_count_and_a_named_corpus_directory(project):
    project.write("elsewhere/one", "1")
    fuzz_project(project, "CORPUS elsewhere")
    output = run_fuzz_test(project)
    assert "Done 1000 runs" in output
    assert "elsewhere" in output


def test_a_missing_seed_corpus_directory_is_a_configure_error(project):
    compiler = shutil.which("clang++-20") or shutil.which("clang++")
    project.write("fuzz.cpp", "int main() { return 0; }\n")
    project.configure(
        FUZZ_BODY.format(options=""),
        "-DCMAKE_CXX_COMPILER=" + compiler,
        "-DSAMPLE_ENABLE_FUZZERS=ON",
        expected="the seed corpus directory",
    )


@pytest.mark.parametrize("runs", ["0", "-1", "many", "1.5"])
def test_a_run_count_must_be_a_positive_integer(project, runs):
    compiler = shutil.which("clang++-20") or shutil.which("clang++")
    project.write("fuzz.cpp", "int main() { return 0; }\n")
    project.write("corpus/parser_fuzz/seed", "seed")
    project.configure(
        FUZZ_BODY.format(options="RUNS " + runs),
        "-DCMAKE_CXX_COMPILER=" + compiler,
        "-DSAMPLE_ENABLE_FUZZERS=ON",
        expected="RUNS must be a positive integer",
    )


def test_with_fuzzers_off_no_corpus_is_needed_and_no_run_is_registered(project):
    project.write("fuzz.cpp", "int main() { return 0; }\n")
    project.configure(FUZZ_BODY.format(options=""))
    listing = project.command("ctest", "--test-dir", str(project.build), "-N")
    assert "parser_fuzz_bounded_run" not in listing
