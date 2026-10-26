---
name: cxx-build-and-toolchain
description: "Read when editing CMake, debugging builds, changing diagnostic or sanitizer flags, updating tools, or wiring C++ packages and installed consumers."
---

# C++ build and toolchain

Read [cxx-standard](../cxx-standard/SKILL.md),
[engineering-standard](../engineering-standard/SKILL.md) and the
[CMake API](../../cxx/README.md). Use the API and configuration at this
checkout's pin. Family profiles own cross compilers, SDKs and target policies.

## Commands and evidence

Run from the repository root with Python 3.11 or later (`py -3` on Windows
where installed). `python3 dev.py check --list` identifies applicable gates.
`python3 dev.py check` is the done command; `--all` adds online checks.
`python3 dev.py build` configures, clean-builds and tests declared trees.
`python3 dev.py format --check` checks formatting; `python3 dev.py lint` runs
the lint group. `python3 dev.py check --group build` additionally checks compile
database coverage and complete warning evidence.
Paths passed as arguments remain relative to the caller's directory.

Build configures on every invocation, then clean-builds and runs CTest. Existing
build types survive unless explicitly overridden with `BUILD_TYPE`. `BUILD_ARGS`
is one CMake argument per line; never split a whitespace-delimited argument
string, because paths and values can contain spaces. The launcher locates the
checkout from its own path, without shell wrappers or symlinks.

Retain complete configure, compilation and test logs. Warnings fail checks.
A failed attempt must not leave stale successful evidence. Build the enabled
host, fuzz and declared profile trees before linting. The compile database is
merged with host entries preferred and profile-only units retained; owned
translation units must all be covered, and headers must be reached by a unit.
An IDE's guessed command is not evidence of lint coverage.

## Tool versions and analyser configuration

Formatter and analyser major versions come from the pin's
`config/.clang-version`; a mismatch refuses to run. A tool upgrade needs
approval. Re-derive canonical check names and aliases from the new tool's
official documentation, reformat in a separate commit, and fix or obtain
approval for each remaining finding. Never silently increase a deviation budget.

After a clang-tidy configuration edit, inspect `--dump-config` and
`--list-checks` for the pinned executable. Verify the intended set of checks,
not merely the command's exit status. `Checks:` is a folded YAML scalar:
embedded `#` text is part of its value, and a missing comma can swallow a
negation. Put rationale above it and options under `CheckOptions:`.
Suppressions must name the enabled canonical check, not a disabled alias.

Keep clang-tidy's configuration discovery; a scope file must inherit its parent.
Headers are analysed in their including translation unit's context, so a
header-adjacent exemption may not apply. Measure proposed scope disables before
requesting approval. Run automated fixes one check at a time, inspect the diff,
and rebuild every relevant configuration, including Release for optimisation
sensitive warnings. A fix can delete an initialiser needed only under another
compile definition, or rename `sample::value` without updating a string-keyed lookup.
Do not regex-rename identifiers through include paths and string literals.

Cross-toolchain system includes are supplied by family profile arguments and
environment. Standalone clang-tidy does not accept clangd's `--query-driver`.
For system-header parse failures, investigate include order before proposing
force-included shims; target-specific remedies belong in family documentation.

## CMake ordering and diagnostic ownership

The included module defines helpers without acting until called. Run common
settings after `project()`, sanitizer setup before compiled targets and
GoogleTest, then create libraries and tests. Host sanitizer setup refuses
cross-compilation. Use [cxx-testing](../cxx-testing/SKILL.md) for fixtures and
per-module tests. Use explicit documentation groups and caller-supplied names.

Link diagnostic targets privately. A target compiling third-party sources uses
the API's explicit vendor-source path; apply `house_cxx_werror_sources` to owned
sources and retain the owned-warning log gate. Do not weaken warnings globally.
A freestanding configure reports omitted hardening rather than implying that
unsupported protection is active.

The pinned house commit selects the helper API. Do not
introduce an independent helper release or version guard. Library package
versions and `find_package` compatibility are a separate public contract.

## Public packages and external consumers

Declare package identity explicitly with `house_cxx_install_package`:
`PACKAGE`, `VERSION`, `NAMESPACE`, `TARGETS` and any `DEPENDS`. Package exports
and config/version files derive from the package, independently of the enclosing
project. `DEPENDS` generates `find_dependency` calls. Config snippets must remain
relocatable and must not assume producer paths.

For a synthetic package `beta`, the build target `beta_core` exports as
`beta::core` with `NAMESPACE beta`. External consumers use the imported spelling:

```cmake
find_package(beta CONFIG REQUIRED)
target_link_libraries(app PRIVATE beta::core)
```

Document supported public module targets separately. Strict interface targets
exported to close static-library link references are internal implementation
details. Their visibility in installed CMake files does not make them public;
consumers must not link or depend on their names. There is no reserved naming
scheme for these targets. Build-only diagnostics and producer paths must not
leak through the installed interface.

Run `python3 dev.py gate consumer` for installable package modes. It builds
producers in isolation, installs, relocates the prefix, and builds the indexed
`tests/consumer/CMakeLists.txt` projects with package registries disabled. Those
projects use `find_package` and documented imported targets. Verify installed
package version boundaries: compatibility stays within a major and, below 1.0,
within a minor. A successful in-tree alias build proves neither installed
spelling nor compatibility. Profile consumers must use the profile's arguments;
cross-compiled executables are built rather than run.

For library version changes, update the declared package version, public header
constants and their binding test together (EN-06.2). Tests compare constants
with build-provided version definitions, not copied literals. Where an owned
translation unit exists, also use a compile-time comparison for cross builds;
keep test-only definitions off installed interfaces. Public compile definitions
needed for ABI consistency belong on the owning target with PUBLIC propagation.

For source fetching, initialize recursive submodule pins. A Git fetch must keep
nested pins; archive downloads are unsupported. Do not substitute sibling
working trees for a pin when recording versioned measurements. Record actual
revision, build type and configuration with measurements.
