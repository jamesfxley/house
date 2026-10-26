# C++ CMake API

Include `platform/cxx/cmake/house.cmake` from the pinned platform. The include
only defines helpers; common settings run explicitly after
`project()`. CMake 3.24 or later, Ninja and GCC or Clang are required for the
current C++ build commands. Formatter and analyser versions come from the pin.

A minimal library with an installable package:

```cmake
cmake_minimum_required(VERSION 3.24)
project(synthetic VERSION 0.1.0 LANGUAGES CXX)
include(platform/cxx/cmake/house.cmake)
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(synthetic_strict LANGUAGES CXX)
add_library(synthetic_core STATIC src/core.cpp)
add_library(synthetic::core ALIAS synthetic_core)
target_sources(synthetic_core PUBLIC FILE_SET HEADERS
    BASE_DIRS include FILES include/synthetic/core.hpp)
target_include_directories(synthetic_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
target_link_libraries(synthetic_core PRIVATE synthetic_strict)
house_cxx_install_package(PACKAGE synthetic VERSION ${PROJECT_VERSION}
    NAMESPACE synthetic TARGETS synthetic_core synthetic_strict)
```

`house_cxx_install_package` requires `PACKAGE`, `VERSION`, `NAMESPACE` and
`TARGETS`. Pass the namespace without `::`; `synthetic_core` exports as
`synthetic::core`. Each package owns its export set and config/version files,
independently of `PROJECT_NAME`. Multiple packages can share a project.
`DEPENDS <package>...` emits `find_dependency(<package> CONFIG)` calls.
`CONFIG_SNIPPET <file>` appends caller-owned config after the imported targets;
relative paths resolve from the calling source directory. Installed config must
remain relocatable. Version compatibility shares the major, and below 1.0 the
minor too. Exported strict targets carry no build-only flags to consumers.

Strict targets in `TARGETS` are internal exports needed to close static-library
link references. For example, `synthetic::strict` is internal even though CMake
can see it. Consumers must link only the documented public module targets, such
as `synthetic::core`, and must not depend on strict target names. Package API
documentation must distinguish public targets from these internal exports.

The pinned house commit selects the helper API. There is
no separate CMake helper version or version guard. Installed library packages
retain their explicit versions and `find_package` compatibility checks.

| Helper | Contract |
|---|---|
| `house_cxx_common_settings(<freestanding>)` | C11/C++20, compile commands, PIC on hosted builds; explicit freestanding mode permits C extensions and turns PIC off |
| `house_cxx_add_strict_target(<name> [LANGUAGES C CXX] [FREESTANDING ON/OFF] [VENDOR_SOURCES ON/OFF] [WERROR ON/OFF])` | Interface diagnostics and hardening; WERROR and VENDOR_SOURCES are mutually exclusive; freestanding defaults to cross-compiling |
| `house_cxx_werror_sources(<sources>...)` | Append source-scoped Werror; refuse missing paths, accept generated and binary-directory sources |
| `house_cxx_enable_sanitizers(<prefix>)` | Prefix_SANITIZE controls directory-scope ASan/UBSan before targets; cross-compiling is refused |
| `house_cxx_enable_gtest()` | Enable CTest and GoogleTest as described below |
| `house_cxx_add_module_test(<package> <module> SOURCES ... [NAME ...] [LIBRARIES ...])` | Link package strict/module targets and GTest; discover individual cases with a package test prefix |
| `house_cxx_add_fuzzer(<name> PACKAGE ... SOURCE ... [LIBRARIES ...] [OUTPUT_DIR ...] [CORPUS <dir>] [RUNS <n>])` | Option-controlled strict fuzz entry point, default build/fuzzers output, and a bounded CTest run over the seed corpus |
| `house_cxx_version_definitions(<target> <package> <scope>)` | Publish PACKAGE_CMAKE_VERSION_MAJOR/MINOR/PATCH from the project in the requested scope |
| `house_cxx_declare_tests_option(<prefix>)` | Tests default on only for a top-level host project |
| `house_cxx_declare_install_option(<prefix> [AVAILABLE ON/OFF])` | Install defaults on for a top-level available package; family code owns mode restrictions |
| `house_cxx_declare_fuzzers_option(<prefix>)` | Fuzzing requires tests, runs before compiled targets and instruments libraries as well as entry points |
| `house_cxx_declare_enum_option(<prefix> NAME ... DEFAULT ... VALUES ... [DOC ...])` | Cache enum with explicit validation, including empty and spaced values |

`house_cxx_enable_gtest` downloads GoogleTest 1.14.0 from GitHub at configure
time, pinned by URL and SHA-256, unless a `GTest::gtest_main` target already
exists. A network-free build provides that target first. Call the helper after
sanitizer setup.

With `VENDOR_SOURCES ON`, diagnostics reach owned target SOURCES through direct,
alias and interface links, once per directory and only for the linked target.
Vendor INTERFACE_SOURCES retain code-generation hardening without the project's
diagnostic set. Call `house_cxx_werror_sources` on owned sources when Werror is
source-scoped. Unsupported generator-expression sources/links are refused.
Hardening conditions and omitted protections are reported during configure.

`house_cxx_add_doc_examples(<target> PACKAGE ... DOCUMENTS ... HARNESS_DIR ...
[LIBRARIES ...] [GROUP <name>] [GROUPS <names>...] [GROUP_DOCUMENTS <files>...])`
extracts marked C++ blocks and compiles matching harness files through the
package strict target. Use `<!-- example: name -->`, or `<!-- example: none -->`
for illustrations. Declared groups use `<!-- example: group/name -->`; ungrouped
calls list grouped documents in GROUP_DOCUMENTS so they cannot silently lose
examples. The grouped call lists its own DOCUMENTS and matching harness folder.
Duplicate names, unmarked/unclosed fences and missing/stale harnesses fail.

A fuzzer built with `house_cxx_add_fuzzer` also registers the CTest test
`<name>_bounded_run`, labelled `fuzz`, so the `build` gate of the fuzz tree runs it.
The test executes the fuzzer for a fixed number of runs over a seed corpus:

```cmake
house_cxx_add_fuzzer(parser_fuzz PACKAGE sample SOURCE fuzz.cpp
    LIBRARIES sample::parser CORPUS tests/corpus/parser RUNS 2000)
```

- `CORPUS` is a directory of seed inputs, relative to the calling `CMakeLists.txt`.
  It defaults to `corpus/<name>`. A directory that does not exist is a configure
  error, so a mistyped path cannot leave a fuzzer with nothing to replay.
- `RUNS` is a positive integer and defaults to 1000. It is passed as `-runs=<n>`.
- The command is `<fuzzer> <work> <corpus> -runs=<n> -seed=1
  -artifact_prefix=<work>/`. libFuzzer reads every corpus directory and writes new
  inputs to the first, so `<work>`, a directory in the build tree, comes first and
  the committed seeds are only read. A fixed `-seed` keeps the run reproducible, and
  `-artifact_prefix` keeps crash files in the build tree. Each flag is described in
  the [libFuzzer options](https://llvm.org/docs/LibFuzzer.html#options).
- A crash, sanitizer report or non-zero exit fails the test. Long exploratory runs
  are a scheduled workflow job and are not part of the check.

`python3 dev.py gate consumer [--tree <name>]` configures and builds producers in
a temporary directory, with `<prefix>_ENABLE_TESTS=OFF` when the root
`CMakeLists.txt` calls `house_cxx_declare_tests_option(<prefix>)` (the fuzz tree
keeps its tests), installs to a temporary prefix, relocates it, then builds
each indexed `<package path>/tests/consumer/CMakeLists.txt`. Package modes decide
which trees support install. An omitted modes table defaults to install on host;
an unspecified tree in an explicit table contributes no install obligation.
The toolchain arguments and environment come from the tree profile. Consumer
projects must consume those profile arguments; warnings fail. Package registries
are disabled, and the temporary prefix supplies find_package lookup. The gate
builds consumers. It runs a consumer program only when the package names it:

```toml
[packages.root]
path = "."
modes = { host = "build-test-install" }
consumer_executables = ["consumer"]
```

`consumer_executables` is an array of unique, nonempty paths relative to the
consumer's build directory, in the form the generator writes the program there.
It needs a package whose `host` mode includes `install`; an empty array, a
non-string, an absolute or `..` path, a backslash, a duplicate or a package
without an installable host mode makes `house.toml` malformed (exit 2). After
the consumer builds against the relocated prefix, the gate runs each named
program from the repository root with the tree's environment. It passes only on
exit status 0; a non-zero status fails with the package, the program and the
status, and a named program the build did not produce fails with that name.
With no key nothing runs. Programs of every tree other than `host` are built and
never run, because cross-compiled executables cannot run on the host.

A package may declare further cases under `consumer_cases`. Each case installs the
producer with its own arguments, relocates the prefix and configures a consumer
from an indexed source, so a setting that changes what the installed package
means is proved the way the default is:

```toml
[[packages.root.consumer_cases]]
name = "level-five"
producer_args = ["-DSAMPLE_LEVEL=5"]
source = "tests/consumer-level"
expect = "runs"

[[packages.root.consumer_cases]]
name = "unsupported-mode"
tree = "alternate"
consumer_args = ["-DSAMPLE_MODE=unsupported"]
expect = "fails"
stage = "consumer-configure"
message = "mode unsupported is not available"
```

- `name` is a lowercase identifier, unique within the package.
- `tree` is `host` (the default), `fuzz` or a tree declared under `[[trees]]`. A case
  runs in that tree's pass of the gate, with that tree's profile arguments and
  environment, and not at all when the tree is disabled.
- `producer_args` and `consumer_args` are arrays of CMake arguments added after the
  tree's own. The gate owns the source, build, generator, install-prefix and
  prefix-path arguments, so `-S`, `-B`, `-G`, `-DCMAKE_INSTALL_PREFIX` and, for the
  consumer, `-DCMAKE_PREFIX_PATH` make `house.toml` malformed.
- `source` is a directory relative to the repository holding an indexed
  `CMakeLists.txt`. Its default is the package's `tests/consumer`. To prove that a
  definition reached the consumer, give the case a source that `static_assert`s it.
- `expect = "runs"` builds the consumer and, in the `host` tree, runs the package's
  `consumer_executables`, as the default consumer does.
- `expect = "fails"` needs `stage`, one of `producer-configure`, `producer-build`,
  `consumer-configure` or `consumer-build`, and `message`. The case passes only
  when every earlier stage succeeds without warnings, the named stage exits
  non-zero, and its output contains `message` (whitespace runs count as one, because
  CMake wraps error text). A case whose stage succeeds, fails at an earlier stage,
  or fails without the message fails the gate and names the case and the stage.
- `stage` and `message` are refused on a `runs` case.

Cases add to the default consumers. With no `consumer_cases`, only the default
consumers run.
