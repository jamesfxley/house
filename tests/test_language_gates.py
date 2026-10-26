# SPDX-License-Identifier: MIT
"""Prove provider execution on real synthetic C++ sources and faulty evidence."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from house.api import Repo
from house.build import COMPLETE, build
from house.cli import main
from house.core import CannotRunError
from house.gates.api_docs import ApiDocs, inputs
from house.gates.build_warnings import BuildWarnings
from house.gates.clang_tidy import dependency_paths
from house.gates.compile_db import CompileDb, merge
from house.gates.format import Format
from house.gates.lint import Lint
from house.runner import Runner, execute
from house.sync import defaults, generated, sync
from tests.conftest import ROOT, axes_config, commit, git
from tests.test_standards import assert_fault, assert_pass


@pytest.fixture
def cpp(repo, write):
    repo.config["house"].update(languages=["cxx"], platform="platform")
    shutil.copytree(ROOT / "config", repo.root / "platform/config")
    shutil.copytree(ROOT / "cxx", repo.root / "platform/cxx")
    (repo.root / "platform/house/launcher").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "house/launcher/dev.py",
        repo.root / "platform/house/launcher/dev.py",
    )
    write(".gitignore", "platform/\nbuild*/\ncompile_commands.json\napi/\n")
    write("house.toml", '[house]\nplatform="platform"\nlanguages=["cxx"]\n')
    repo.config["sync"]["files"] = list(defaults(repo))
    sync(repo)
    for name in repo.config["sync"]["files"]:
        git(repo.root, "add", name)
    write(
        "CMakeLists.txt",
        """cmake_minimum_required(VERSION 3.25)
project(synthetic LANGUAGES CXX)
include(platform/cxx/cmake/house.cmake)
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(synthetic_strict LANGUAGES CXX)
enable_testing()
add_subdirectory(src/arithmetic)
add_executable(synthetic_test tests/main.cpp)
target_link_libraries(synthetic_test PRIVATE synthetic)
add_test(NAME arithmetic COMMAND synthetic_test)
""",
    )
    write(
        "src/arithmetic/CMakeLists.txt",
        """add_library(synthetic STATIC arithmetic.cpp)
target_compile_features(synthetic PUBLIC cxx_std_20)
target_include_directories(synthetic PUBLIC ${PROJECT_SOURCE_DIR}/include)
target_link_libraries(synthetic PRIVATE synthetic_strict)
""",
    )
    write(
        "include/sample.hpp",
        """// SPDX-License-Identifier: MIT
/** @file */
#pragma once

/** A synthetic library. */
namespace synthetic {
/** Return the sum of two values. */
[[nodiscard]] int add(int lhs, int rhs);
}
""",
    )
    write(
        "src/arithmetic/arithmetic.cpp",
        """// SPDX-License-Identifier: MIT
#include "sample.hpp"

namespace synthetic {
int add(int lhs, int rhs) { return lhs + rhs; }
}
""",
    )
    write(
        "tests/main.cpp",
        """// SPDX-License-Identifier: MIT
#include "sample.hpp"

int main() { return synthetic::add(1, 2) == 3 ? 0 : 1; }
""",
    )
    write(
        "docs/Doxyfile",
        "OUTPUT_DIRECTORY = api\nGENERATE_LATEX = NO\nQUIET = YES\n"
        "WARN_IF_UNDOCUMENTED = YES\nINPUT = include\nFILE_PATTERNS = *.hpp\n",
    )
    assert_pass(repo, Format(), ("--write",))
    return repo


def test_real_synthetic_cpp_passes_format_lint_build_groups(cpp, capsys):
    assert main(cpp.root, ["check", "--ci", "--group", "format,lint,build"]) == 0
    output = capsys.readouterr().out
    for name in ["format", "lint", "build", "compile-db", "build-warnings"]:
        assert name + " [" in output
    assert ": FAIL" not in output
    assert "CANNOT_RUN" not in output
    assert_pass(cpp, ApiDocs())


def test_format_rejects_fault_accepts_repair_and_unreadable(cpp, write):
    write("src/arithmetic/arithmetic.cpp", "int    value( ){return 1;}\n")
    assert_fault(cpp, Format(), "clang-format")
    assert_pass(cpp, Format(), ("--write",))
    assert_pass(cpp, Format())
    write("src/arithmetic/arithmetic.cpp", b"\xff")
    entry = execute(cpp, Format())
    assert entry.result.status == 2
    assert "cannot read" in entry.result.message


def test_compile_db_coverage_merge_and_cross(cpp):
    database = cpp.root / "compile_commands.json"
    database.write_text("[]\n")
    assert_fault(cpp, CompileDb(), "missing from compile database")
    assert build(cpp).status == 0
    assert_pass(cpp, CompileDb())
    entry = execute(cpp, CompileDb(), ("cross", "--triple", "synthetic-cross"))
    assert entry.result.status == 1
    assert "no synthetic-cross cross entry" in str(entry.result)
    original = json.loads(database.read_text())
    original[0]["arguments"] = ["synthetic-cross-compiler", "-c", original[0]["file"]]
    original[0].pop("command", None)
    database.write_text(json.dumps(original))
    assert_pass(cpp, CompileDb(), ("cross", "--triple", "synthetic-cross"))
    database.write_bytes(b"\xff")
    entry = execute(cpp, CompileDb())
    assert entry.result.status == 2
    assert "cannot read" in entry.result.message


def test_build_warning_negative_controls(cpp):
    name = cpp.root / "build.log"
    content = COMPLETE + "\n[1/1] Building CXX object arithmetic.o\n"
    name.write_text(
        content
        + str(cpp.root / "src/arithmetic/arithmetic.cpp")
        + ":2: warning: faulty build\n",
    )
    entry = execute(cpp, BuildWarnings(), (str(name),))
    assert entry.result.status == 1
    assert "faulty build" in str(entry.result)
    name.write_text(content)
    assert_pass(cpp, BuildWarnings(), (str(name),))
    name.write_text("ninja: no work to do.\n")
    entry = execute(cpp, BuildWarnings(), (str(name),))
    assert entry.result.status == 2
    assert "rebuild" in entry.result.message




def test_docs_covers_every_public_input(cpp, write):
    write(
        "include/second/extra.hpp",
        "/** @file */\n/** A documented value. */\nextern int documented;\n",
    )
    write(
        "other/include/other.hpp",
        "/** @file */\n/** A documented value. */\nextern int other_value;\n",
    )
    assert_fault(cpp, ApiDocs(), "other/include is not in")
    path = cpp.root / "docs/Doxyfile"
    path.write_text(path.read_text() + "INPUT += other/include\n")
    assert_pass(cpp, ApiDocs())
    write("include/sample.hpp", "/** @file */\n#pragma once\nint undocumented_value;\n")
    assert_fault(cpp, ApiDocs(), "undocumented_value")
    path.write_bytes(b"\xff")
    entry = execute(cpp, ApiDocs())
    assert entry.result.status == 2
    assert "cannot read" in entry.result.message


def test_python_lint_excludes_all_gitlinks(repo, write):
    repo.config["house"]["platform"] = "platform"
    shutil.copytree(ROOT / "config", repo.root / "platform/config")
    shutil.copytree(ROOT / "cxx", repo.root / "platform/cxx")
    (repo.root / "platform/house/launcher").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "house/launcher/dev.py",
        repo.root / "platform/house/launcher/dev.py",
    )
    write("sample.py", "# SPDX-License-Identifier: MIT\nVALUE = 1\n")
    sha = commit(repo.root)
    git(repo.root, "update-index", "--add", "--cacheinfo", "160000", sha, "dependency")
    (repo.root / "dependency").mkdir()
    (repo.root / "dependency/broken.py").write_text("import not_an_actual_package\n")
    assert_pass(repo, Lint())
    write("sample.py", "# SPDX-License-Identifier: MIT\nimport os\n")
    assert_fault(repo, Lint(), "F401")


def test_python_only_sync_omits_cpp_files(repo):
    repo.config["house"]["platform"] = "platform"
    shutil.copytree(ROOT / "config", repo.root / "platform/config")
    shutil.copytree(ROOT / "cxx", repo.root / "platform/cxx")
    (repo.root / "platform/house/launcher").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "house/launcher/dev.py",
        repo.root / "platform/house/launcher/dev.py",
    )
    names = defaults(repo)
    assert ".editorconfig" in names
    assert not any("clang" in name or "cmake" in name.lower() for name in names)
    repo.config["sync"]["files"] = list(names)
    output = generated(repo)
    assert not any("CMake" in text for text in output.values())


def test_tidy_keeps_parent_checks_under_a_scope_config(cpp, write):
    write(
        ".clang-tidy",
        "Checks: '-*,modernize-use-nullptr,readability-identifier-naming'\n"
        "WarningsAsErrors: '*'\nHeaderFilterRegex: '.*'\nCheckOptions:\n"
        "  readability-identifier-naming.FunctionCase: lower_case\n",
    )
    write(
        "src/arithmetic/.clang-tidy",
        "InheritParentConfig: true\nChecks: '-readability-identifier-naming'\n",
    )
    path = cpp.root / "src/arithmetic/arithmetic.cpp"
    path.write_text(path.read_text() + "\nint* BadName() { return 0; }\n")
    assert build(cpp).status == 0
    entry = execute(cpp, Lint())
    assert entry.result.status == 1
    assert "modernize-use-nullptr" in str(entry.result)
    assert "readability-identifier-naming" not in str(entry.result)
    path.write_text(path.read_text().replace("return 0;", "return nullptr;"))
    assert_pass(cpp, Lint())


def test_unreached_header_is_refused(cpp, write):
    assert build(cpp).status == 0
    write("include/orphan.hpp", "// SPDX-License-Identifier: MIT\n#pragma once\n")
    assert_fault(cpp, Lint(), "header unreached")
    git(cpp.root, "rm", "-f", "include/orphan.hpp")
    assert_pass(cpp, Lint())


def test_missing_tidy_is_unavailable(cpp, monkeypatch):
    monkeypatch.setenv("CLANG_TIDY", "/missing/tool/clang-tidy")
    entry = execute(cpp, Lint())
    assert entry.result.status == 2
    assert "cannot execute" in entry.result.message
    assert "Traceback" not in entry.result.message


def test_inherited_and_extended_python_ignores_are_both_effective(repo, write):
    repo.config["house"]["platform"] = "platform"
    shutil.copytree(ROOT / "config", repo.root / "platform/config")
    shutil.copytree(ROOT / "cxx", repo.root / "platform/cxx")
    write("tests/__init__.py", "# SPDX-License-Identifier: MIT\n")
    write(
        "tests/example.py",
        "# SPDX-License-Identifier: MIT\nimport os\n\n\n"
        "def has_value(value):\n    assert value\n",
    )
    write(
        "ruff.toml",
        'extend = "platform/config/ruff.toml"\n'
        '[lint.extend-per-file-ignores]\n"tests/**"=["F401"]\n',
    )
    assert_pass(repo, Lint())
    write(
        "ruff.toml",
        'extend = "platform/config/ruff.toml"\n'
        '[lint.per-file-ignores]\n"tests/**"=["F401"]\n',
    )
    assert_fault(repo, Lint(), "S101")


def test_classified_cpp_overlay_preserves_base_and_is_stable(cpp):
    cpp.config["sync"]["files"] = [".clangd", ".devcontainer/devcontainer.json"]
    cpp.config["sync"]["overlay"] = {
        "clangd": {"CompileFlags": {"Add": ["--target=synthetic-target"]}},
        "devcontainer": {
            "image": "sample",
            "customizations": {
                "vscode": {
                    "settings": {
                        "clangd.arguments": ["--query-driver=/**/synthetic-cxx"],
                    },
                },
            },
        },
    }
    first = generated(cpp)
    assert "-Wno-unknown-warning-option" in first[".clangd"]
    assert "--target=synthetic-target" in first[".clangd"]
    settings = json.loads(first[".devcontainer/devcontainer.json"])["customizations"][
        "vscode"
    ]["settings"]
    assert "--background-index" in settings["clangd.arguments"]
    assert "--query-driver=/**/synthetic-cxx" in settings["clangd.arguments"]
    sync(cpp)
    assert generated(cpp) == first
    assert sync(cpp, check=True) == []


def test_failed_build_is_not_marked_complete_and_repair_passes(cpp):
    path = cpp.root / "src/arithmetic/arithmetic.cpp"
    original = path.read_text()
    path.write_text(original + '\n#warning "synthetic compiler warning"\n')
    result = build(cpp)
    assert result.status == 1
    assert "synthetic compiler warning" in str(result)
    assert not (cpp.root / "build/build.log").read_text().startswith(COMPLETE)
    path.write_text(original)
    assert build(cpp).status == 0
    assert (cpp.root / "build/build.log").read_text().startswith(COMPLETE)
    assert build(cpp).status == 0
    assert_pass(cpp, BuildWarnings())


def test_declared_profile_receives_arguments_and_environment(cpp, monkeypatch):
    module = "synthetic_build_profile"
    profile = SimpleNamespace(
        name="alternate",
        enabled=True,
        cmake_args=("-DSELECTED_PROFILE=sample value",),
        env={"PROFILE_SIGNAL": "visible"},
        sync_overlay={},
    )
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(profile=profile))
    cpp.config["trees"] = [{"name": "alternate", "profile": module + ":profile"}]
    path = cpp.root / "CMakeLists.txt"
    extra = '\nfile(WRITE "${CMAKE_BINARY_DIR}/profile.txt" '
    extra += '"${SELECTED_PROFILE}|$ENV{PROFILE_SIGNAL}")\n'
    path.write_text(path.read_text() + extra)
    assert build(cpp, "alternate").status == 0
    assert (
        cpp.root / "build-alternate/profile.txt"
    ).read_text() == "sample value|visible"
    profile.enabled = False
    with pytest.raises(CannotRunError, match="unknown build tree"):
        build(cpp, "alternate")


def test_missing_doxygen_is_unavailable(cpp, monkeypatch):
    monkeypatch.setattr("house.gates.api_docs.shutil.which", lambda _name: None)
    entry = execute(cpp, ApiDocs())
    assert entry.result.status == 2
    assert "doxygen is not installed" in entry.result.message


def test_host_database_wins_and_dependency_sources_are_excluded(
    cpp,
    write,
    monkeypatch,
):
    assert build(cpp).status == 0
    original = json.loads((cpp.root / "compile_commands.json").read_text())
    write("src/extra.cpp", "int extra();\n")
    module = "synthetic_merge_profile"
    profile = SimpleNamespace(name="alternate", enabled=True, cmake_args=(), env={})
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(profile=profile))
    cpp.config["trees"] = [{"name": "alternate", "profile": module + ":profile"}]
    (cpp.root / "build-alternate").mkdir()
    rows = [
        {
            "directory": str(cpp.root),
            "file": "src/arithmetic/arithmetic.cpp",
            "command": "synthetic-cross-compiler duplicate",
        },
        {
            "directory": str(cpp.root),
            "file": "src/extra.cpp",
            "command": "synthetic-cross-compiler extra",
        },
        {
            "directory": str(cpp.root),
            "file": "build/_deps/external.cpp",
            "command": "synthetic-cross-compiler external",
        },
    ]
    (cpp.root / "build-alternate/compile_commands.json").write_text(json.dumps(rows))
    assert merge(cpp) == 3
    merged = json.loads((cpp.root / "compile_commands.json").read_text())
    assert merged[:2] == original
    assert len(merged) == 3
    assert "synthetic-cross-compiler extra" in str(merged)
    assert "synthetic-cross-compiler duplicate" not in str(merged)
    assert "external.cpp" not in str(merged)


def test_cpp_build_and_header_lint_handle_spaces_and_quotes(cpp):
    destination = cpp.root.parent / "synthetic library's checkout"
    shutil.copytree(cpp.root, destination)
    moved = Repo(destination, cpp.config)
    assert build(moved).status == 0
    assert_pass(moved, Lint())


def test_cmake_warnings_block_and_repair_passes(cpp):
    path = cpp.root / "CMakeLists.txt"
    original = path.read_text()
    path.write_text(original + '\nmessage(WARNING "synthetic configure warning")\n')
    result = build(cpp)
    assert result.status == 1
    assert "synthetic configure warning" in str(result)
    path.write_text(original)
    assert build(cpp).status == 0


def test_fuzz_tree_uses_the_pinned_compiler(cpp):
    path = cpp.root / "CMakeLists.txt"
    extra = """
function(house_cxx_declare_fuzzers_option prefix)
  option(${prefix}_ENABLE_FUZZERS "Enable synthetic fuzz target" OFF)
endfunction()
house_cxx_declare_fuzzers_option(SYNTHETIC)
if(SYNTHETIC_ENABLE_FUZZERS)
  file(WRITE "${CMAKE_BINARY_DIR}/fuzz-enabled" "yes")
endif()
"""
    path.write_text(path.read_text() + extra)
    assert build(cpp).status == 0
    assert (cpp.root / "build-fuzz/fuzz-enabled").read_text() == "yes"
    database = json.loads((cpp.root / "build-fuzz/compile_commands.json").read_text())
    assert "clang++-20" in database[0]["command"]


def test_wrong_formatter_version_is_unavailable(cpp, monkeypatch):
    monkeypatch.setenv("CLANG_FORMAT", "synthetic-formatter")
    monkeypatch.setattr(
        "house.tools.run",
        lambda *_args: subprocess.CompletedProcess([], 0, "LLVM version 18.0.0", ""),
    )
    entry = execute(cpp, Format())
    assert entry.result.status == 2
    assert "is not clang-format 20" in entry.result.message


def test_failed_reconfigure_invalidates_previous_complete_build_log(cpp):
    assert build(cpp).status == 0
    path = cpp.root / "CMakeLists.txt"
    path.write_text(
        path.read_text() + '\nmessage(FATAL_ERROR "synthetic configure failure")\n',
    )
    with pytest.raises(CannotRunError, match="synthetic configure failure"):
        build(cpp)
    entry = execute(cpp, BuildWarnings())
    assert entry.result.status == 2
    assert "lacks complete compile evidence" in entry.result.message


def test_profile_environment_reaches_dependency_probe_and_tidy(cpp, write, monkeypatch):
    module = "synthetic_include_profile"
    directory = cpp.root / "profile includes"
    write(
        "profile includes/profile.hpp",
        "// SPDX-License-Identifier: MIT\n#pragma once\n"
        "namespace synthetic { inline int profile_value() { return 0; } }\n",
    )
    source = cpp.root / "src/arithmetic/arithmetic.cpp"
    source.write_text(
        source.read_text()
        .replace(
            '#include "sample.hpp"',
            '#include "sample.hpp"\n#include "profile.hpp"',
        )
        .replace("return lhs + rhs;", "return lhs + rhs + profile_value();"),
    )
    profile = SimpleNamespace(
        name="alternate",
        enabled=True,
        cmake_args=(),
        env={"CPATH": str(directory)},
        sync_overlay={},
    )
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(profile=profile))
    cpp.config["trees"] = [{"name": "alternate", "profile": module + ":profile"}]
    assert build(cpp, "alternate").status == 0
    assert_pass(cpp, Lint())


def test_fuzz_declaration_in_a_comment_does_not_enable_a_tree(cpp):
    path = cpp.root / "CMakeLists.txt"
    path.write_text(
        path.read_text() + "\n# house_cxx_declare_fuzzers_option(SYNTHETIC)\n",
    )
    assert build(cpp).status == 0
    assert not (cpp.root / "build-fuzz").exists()


def test_build_args_keep_values_with_spaces(cpp, monkeypatch):
    path = cpp.root / "CMakeLists.txt"
    extra = '\nfile(WRITE "${CMAKE_BINARY_DIR}/values.txt" '
    extra += '"${SETTING_ONE}|${SETTING_TWO}")\n'
    path.write_text(path.read_text() + extra)
    monkeypatch.setenv(
        "BUILD_ARGS",
        "-DSETTING_ONE=first value\n-DSETTING_TWO=second value",
    )
    assert build(cpp).status == 0
    assert (cpp.root / "build/values.txt").read_text() == "first value|second value"


def test_existing_build_type_is_preserved_without_override(cpp, monkeypatch):
    assert build(cpp).status == 0
    cache = cpp.root / "build/CMakeCache.txt"
    assert "CMAKE_BUILD_TYPE:STRING=Debug" in cache.read_text()
    monkeypatch.setenv("BUILD_TYPE", "Release")
    assert build(cpp).status == 0
    monkeypatch.delenv("BUILD_TYPE")
    assert build(cpp).status == 0
    assert "CMAKE_BUILD_TYPE:STRING=Release" in cache.read_text()


def test_profile_group_builds_and_lints_the_selected_tree(cpp, write, capsys):
    write(
        "synthetic_profile.py",
        """class Profile:
    name = "alternate"
    enabled = True
    cmake_args = ()
    env = {}
    sync_overlay = {}
profile = Profile()
""",
    )
    path = cpp.root / "house.toml"
    path.write_text(
        path.read_text()
        + """
[groups]
alternate = ["build:alternate", "lint:alternate"]
[[trees]]
name = "alternate"
profile = "synthetic_profile:profile"
""",
    )
    assert main(cpp.root, ["check", "--ci", "--group", "alternate"]) == 0
    output = capsys.readouterr().out
    assert "build:alternate [build/repository/alternate]: PASS" in output
    assert "lint:alternate [lint/repository/alternate]: PASS" in output
    assert not (cpp.root / "build").exists()


def test_header_reachability_includes_alternate_compile_contexts(
    cpp,
    write,
    monkeypatch,
):
    write(
        "include/profile.hpp",
        "// SPDX-License-Identifier: MIT\n#pragma once\n"
        "namespace synthetic { inline int profile_value() { return 0; } }\n",
    )
    write(
        "src/arithmetic/arithmetic.cpp",
        """// SPDX-License-Identifier: MIT
#include "sample.hpp"
#ifdef SYNTHETIC_PROFILE
#include "profile.hpp"
#endif
namespace synthetic {
int add(int lhs, int rhs) {
#ifdef SYNTHETIC_PROFILE
    return lhs + rhs + profile_value();
#else
    return lhs + rhs;
#endif
}
}
""",
    )
    module = "synthetic_context_profile"
    profile = SimpleNamespace(
        name="alternate",
        enabled=True,
        cmake_args=("-DCMAKE_CXX_FLAGS=-DSYNTHETIC_PROFILE",),
        env={},
        sync_overlay={},
    )
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(profile=profile))
    cpp.config["trees"] = [{"name": "alternate", "profile": module + ":profile"}]
    assert build(cpp).status == 0
    assert_pass(cpp, Lint())


def test_package_doxyfile_uses_package_relative_inputs(cpp, write):
    cpp.config["packages"] = {"alpha": {"path": "libs/alpha"}}
    write(
        "libs/alpha/include/alpha.hpp",
        "/** @file */\n/** A documented value. */\nextern int alpha_value;\n",
    )
    write(
        "libs/alpha/docs/Doxyfile",
        "OUTPUT_DIRECTORY = api\nGENERATE_LATEX = NO\nQUIET = YES\n"
        "WARN_IF_UNDOCUMENTED = YES\nINPUT = include\n",
    )
    assert_pass(cpp, ApiDocs())
    assert (cpp.root / "libs/alpha/api/html/index.html").is_file()


def test_other_build_owned_sources_can_be_declared_in_lintignore(cpp, write):
    assert build(cpp).status == 0
    write("tests/device/other.cpp", "int separately_built();\n")
    write("tests/device/orphan.hpp", "#pragma once\n")
    assert_fault(cpp, CompileDb(), "source missing from compile database")
    write(".lintignore", "# Built by a separately checked project.\ntests/device/*\n")
    assert_pass(cpp, CompileDb())
    assert_pass(cpp, Lint())


def test_dependency_parser_accepts_crlf_continuations_and_literal_quotes():
    text = "source.cpp \\\r\n directory\\ with\\ spaces/header's.hpp\r\n"
    assert dependency_paths(text) == [
        "source.cpp",
        "directory with spaces/header's.hpp",
    ]


def test_documentation_input_continuations_accept_crlf():
    text = "INPUT = include \\\r\n other/include\r\n"
    assert inputs(text) == {Path("include"), Path("other/include")}




def test_declared_cpp_missing_formatter_still_blocks_ci(cpp, monkeypatch):
    monkeypatch.delenv("CLANG_FORMAT", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert cpp.config["ci"]["skip"] == {}
    (entry,) = Runner(cpp, [Format()]).run(ci=True)
    assert entry.result.status == 2
    assert entry.verdict == "CANNOT_RUN"
    assert "clang-format 20 is not installed" in entry.result.message


def test_the_build_gate_configures_every_tree_with_the_variable(
    cpp, monkeypatch,
):
    path = cpp.root / "CMakeLists.txt"
    path.write_text(
        path.read_text()
        + 'if(NOT SAMPLE_PROFILE STREQUAL "large")\n'
        '  message(FATAL_ERROR "profile was ${SAMPLE_PROFILE}")\nendif()\n',
    )
    cpp.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    with pytest.raises(CannotRunError, match="profile was"):
        build(cpp)
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "large")
    assert build(cpp).status == 0
    cache = (cpp.root / "build/CMakeCache.txt").read_text()
    assert "SAMPLE_PROFILE:UNINITIALIZED=large" in cache
