# Usage

Run `python3 dev.py check` from a checkout, or `py -3 dev.py check` on Windows.
`check --list` reports applicability. `check --all` adds the online state checks;
`check --ci` requires a reason for a skip. `gate NAME` selects one gate.

`python3 dev.py sync` writes declared configuration copies; `sync --check`
checks their content. `synced-files` checks copied files and generated CI.
[Configuration](../README.md#public-configuration-reference) describes optional
family references and repository precedence. The [suppression budget](../README.md#suppression-budget)
is one ceiling per language; the register and requirement citations are reviewed.

For C++, run `python3 dev.py build`, `python3 dev.py format --check`, and
`python3 dev.py lint`. A full build group also checks its compile database
and complete warning logs. `gate api-docs` checks the
package Doxyfiles. Clang tooling must match the pinned major; Python lint uses
the pinned Ruff version. A valid input is UTF-8. Unavailable tools or unreadable
inputs return 2; real diagnostics return 1.

Use `python3 dev.py gate consumer` for installed package checks, or select a
single tree with `--tree NAME`. Each installable package supplies an indexed
`tests/consumer/CMakeLists.txt` under its declared path. A package that lists
`consumer_executables` also has the named host programs run, and the gate fails
on any non-zero exit. A package that declares `consumer_cases` also has each
case installed, relocated and built with its own arguments, and a case that
expects a refusal fails the gate unless the named stage fails with its message.
See the [C++ API](../cxx/README.md) for the helpers, profile expectations and a tested
install/export example. A gate belonging to an undeclared provider is N/A;
it needs no CI skip allowance.

Use `python3 dev.py context src/example.cpp` to locate binding instructions and
pinned chapters before work. It lists paths rather than duplicating rule text,
and prints your House config directory, where `local.md` holds machine notes.
Set `HOUSE_CONFIG_HOME` to an absolute path to choose that location.

Prepare tools explicitly with `python3 dev.py toolchain install`; add
`--profile tests` for family Python tests or `--profile platform-tests` for House's
C++ fixtures. `toolchain doctor` inspects prerequisites. `doctor` also checks
hooks and declared tools. Neither doctor command installs tools.
See the [tool preparation and init commands](../README.md#tool-preparation-and-scaffolding)
for local scaffolding and the [CI renderer](../README.md#generated-ci) for
matrices, schedules and exact coverage checks.

The [configuration reference](../README.md) describes the optional devcontainer
sync overlay and family routes. `house_cxx_enable_sanitizers(PREFIX)` declares
House's sanitize tree; set `HOUSE_MATRIX_SANITIZE=ON` to run build:sanitize and
lint:sanitize with Debug and leak detection. Standalone environments use
`python3 dev.py toolchain install`.
