# House

House supplies development commands to repositories through a pinned submodule.
Each checkout's `dev.py` loads its own platform revision without installing a
global package. Python 3.11 or later is the runtime prerequisite; gates may
require the tools declared for their language.

Run these commands with your installed Python 3.11 or later. Use `python3`,
or `py -3` on Windows where that optional launcher is installed:

```text
python3 dev.py check
python3 dev.py check --list
python3 dev.py check --group standards
python3 dev.py check --all
python3 dev.py --version
```

The same launcher works when named from a nested directory. Its configuration
and imports resolve from the launcher location. Path arguments retain their
caller's working directory. Missing pinned code returns exit 2 with a submodule
initialisation command.

## Registered checks

| Gate | Module | Coverage |
|---|---|---|
| `synced-files` | `house.gates.synced_files` | Copied root files and workflow equal generated output |
| `deviations` | `house.gates.deviations` | Suppression counts and one ratcheting ceiling per language |
| `doc-links` | `house.gates.doc_links` | Tracked relative Markdown targets, including paths inside submodules |
| `spdx` | `house.gates.spdx` | Provider licence identifiers on owned sources; `--fix` inserts missing identifiers |
| `commits` | `house.gates.commits` | Every selected commit: message format and no trailers |
| `format` | `house.gates.format` | Owned C/C++ sources against the pinned formatter and canonical style |
| `lint` | `house.gates.lint` | Owned Python through pinned Ruff; owned C++ units and reachable headers through clang-tidy |
| `build` | `house.gates.build` | Configure, clean-build and test host/fuzz/declared profiles |
| `compile-db` | `house.gates.compile_db` | Host-preferred owned-source merge and translation-unit coverage |
| `build-warnings` | `house.gates.build_warnings` | Complete build evidence and owned-source warning backstop |
| `consumer` | `house.gates.consumer` | Isolated install, prefix relocation and indexed find_package consumer builds per installable package mode, and the host programs a package names in `consumer_executables` |
| `api-docs` | `house.gates.api_docs` | Public input directories and Doxygen warning checks |

Unknown gates and empty requested groups return exit 2.

`check` selects registered groups other than `online`; `--all` adds that group.
`--group` accepts repeated options or comma-separated names. `--ci` fails a
skipped gate unless `ci.skip` records its reason. An unavailable input or tool
still fails, even when a skip allowance exists. Exit 0 means the selected gates
passed or were explicitly inapplicable, 1 means a fault, and 2 means the checks
could not establish a verdict. Faults take precedence over unavailable checks.

## Configuration and extensions

`house.toml` declares a compatibility line, a platform path, languages, packages,
group extensions, local gate modules, tree profiles, sync inputs, CI obligations
and optional family references. Unknown keys and malformed declarations return exit 2.
C++ format, lint and build execution and Python lint are implemented. Markdown
uses document links and suppression counts. Synced files compare the committed workflow
with deterministic output from applicable groups and declared obligations.
The [C++ CMake API](cxx/README.md) supplies strict targets and package exports;
`python3 dev.py gate consumer` proves their installed consumption.
A package may add `consumer_executables`, the host consumer programs that gate
also runs, and `consumer_cases`, installed-consumer variants that must run or must
be refused with a stated message; see the [C++ API](cxx/README.md).

A local gate module exports `GATE`, with the declared name and group, and
implements `applies(repo)` and `run(repo, argv)`. It imports public types from
`house.api`: `Repo`, `Finding`, `Result`, `Gate`, `TreeProfile`, and `Provider`.
`applies` returns `True` or a nonempty reason; `run` returns a `Result`.
A declaration may add `repair`, the command that regenerates the module. When
the declared module is absent, that gate fails with the module's path and the
repair text while every other gate still runs; without `repair`, or when the
module exists but fails to import, the run is unavailable.
Language metadata defines source and licence conventions. Suppression names,
justification, approval and the prose register are checked by review.

### Public configuration reference

The optional root `family` key names a repository-relative pinned family.
The family file uses the same section syntax as repository configuration.
It may set `gates`, `trees`, `groups`, `house.languages`, `house.licence`,
`sync`, `ci` and `context`. It may not set `family`, `packages`,
`house.platform`. Missing files, escaping paths, forbidden
keys and failed module imports report the offending input as unavailable.
Family paths must stay inside the checkout, including after symlink resolution.

Repository settings win recursively. Arrays are replaced, except `gates` and
`trees` merge by `name`, and `ci.require` merges by `group`; a repository row
replaces the matching family row. Modules of inherited gates and trees import
from the family directory, without local adapters. Use a distinct Python package
name for each family's modules. Other relative paths remain repository-relative.

A repository's `house.toml`:

```toml
family = "infra"

[house]
platform = "infra/house"
languages = ["python"]

[packages.root]
path = "."
```

The pinned neutral family's `family.toml`:

```toml
[house]
languages = ["python"]

[[gates]]
name = "sample-check"
module = "sample_family.gate"
group = "standards"

[[trees]]
name = "sample-host"
profile = "sample_family.profiles:host"
```

The module exports the existing public gate or TreeProfile interface. A repository
can declare its own gates and trees using the same syntax. Package options are
`path`, optional `budget`, `modes`, `consumer_executables` and `consumer_cases`.
The [C++ API](cxx/README.md) specifies the consumer options. `[groups]` names
additional gate lists. `[sync]` selects `files`, structured `overlay` data and
explicit scalar `replace` lists. `[ci]` selects `container`, `container_user`, `skip`, `require`
and `axes`; see [generated CI](#generated-ci). `[context]` registers
`config_directories`; see [context](#agent-conveniences). `[house]` declares
`platform`, `languages` and `licence`.

### Suppression budget

Each package's `budget` defaults to `docs/deviation-budget.txt` beneath its path.
The file has one nonnegative ceiling per language, with optional comments:

```text
cxx = 2
python = 1
```

Each suppression directive counts once, including file and scope directives;
configuration disables count each named check or negative pattern and scope.
The pinned C++ configuration is the baseline; root additions and nested disables
count. C++ comment text is excluded from this count. String literals do not
count. Missing language ceilings mean zero. Counts above ceilings fail; lower
counts report `lower LANGUAGE to COUNT`. `gate deviations --ratchet` writes
those lower ceilings only when every package passes. Approval, exact check
names, reasons and register completeness remain review obligations.

## Development

Tests are development-only. They run without installing House:

```text
uvx --from pytest==9.1.1 pytest
uvx ruff@0.16.4 check --config config/ruff.toml dev.py house tests
```

`standard/` pins the rule contract. `house/launcher/dev.py` is the canonical
launcher; the root copy must match it. `house/api.py` defines extension surfaces;
the other modules are private implementations. Tests use synthetic repositories
and actual Git submodule pins. [CONTRIBUTING.md](CONTRIBUTING.md) describes
changes and messages; [SECURITY.md](SECURITY.md) describes vulnerability reports.

`python3 dev.py sync` renders declared copies; `sync --check` compares their exact
content. Copy-only files refuse overlays. Structured clangd and VS Code overlays
merge maps, extend lists without duplicates and refuse conflicting scalars unless
`sync.replace` lists the field. Unknown keys and unsupported types return exit 2.
The CI workflow is rendered through the same command. Ruff configuration is
repository-owned and extends the pinned base rather than being synced.

`python3 dev.py commits --range BASE..HEAD` checks every commit in a range;
`commits --root` checks all history reachable from HEAD. With neither option,
local checks use the upstream, then `origin/main`, then all commits when no
remote exists. A resolved empty range passes. Missing endpoints or nonempty
shallow history return exit 2. Pull-request and push event payloads choose the
configured CI endpoints, including initial pushes.

`python3 dev.py hook install` writes executable `.house/hooks` shims and sets
local `core.hooksPath`. Both shims call this checkout's launcher through the
installing interpreter. Existing custom hook settings and edited files cause
a refusal. `hook pre-commit` runs standards except commits; `hook commit-msg FILE`
checks a pending message. `python3 dev.py doctor` checks installed hook paths,
declared tool versions without changing settings.
Review still checks imperative meaning, body reasoning and the dominant area.

For `schedule`, `workflow_dispatch` and `repository_dispatch`, the commits gate
reports PASS because those events introduce no commits; ranges are checked on
push and pull_request. An explicit `--range` or `--root` still checks that
selection. Every other unrecognised event returns exit 2. The default local
range covers commits pending against the upstream; after a bypassed commit is
pushed, hosted push checks are the backstop.

`python3 dev.py build [--tree NAME]` configures enabled trees and runs a clean
compilation plus CTest. Host uses `build/`; declared profiles use `build-NAME/`.
A declared `house_cxx_declare_fuzzers_option(PREFIX)` also enables a fuzz tree
using pinned Clang. `BUILD_ARGS` contributes one CMake argument per line, so
spaces survive. `BUILD_TYPE` overrides the type; an existing cache keeps its type
when no override is supplied. Package mode declarations control whether tests
are required. Configure, compile and test warnings fail. Failed attempts
invalidate old complete logs; successful clean builds retain complete evidence.
No build tree is deleted by the Python helper.

`python3 dev.py format --check` checks owned C++ files; omitting `--check`
formats them. `python3 dev.py lint` runs declared source linters. Python lint
enumerates indexed files while excluding every gitlink. C++ uses the root merged
compile database, tree discovery for scope configuration, and a closed temporary
dependency file. Unreached headers fail; included headers get main-file include
checks. Profiles may supply `HOUSE_CLANG_TIDY_ARGS` as a JSON string array in
`env`, alongside compiler environment variables. No cross compiler, target or
SDK is assumed by House.

C++ formatter/analyser major versions come from `config/.clang-version`; Ruff's
exact version comes from `config/ruff.toml`. Missing or mismatched tools return
exit 2. Doxygen is required for the C++ docs gate. `house.sync.defaults` selects
copy/renderer destinations per language; Python-only output contains `dev.py`,
the workflow, `.editorconfig` and the GitHub issue and pull-request files. Ruff remains repo-owned with its native
`extend` mechanism.
The bounded clangd schema supports the existing nonnegative TypeNameLimit
integer as well as its string/bool/list/map fields. All other numeric fields
remain unsupported. House declares Python and Markdown; C++ gates are N/A and need no
CI skip allowances.

Named profiles register `build:NAME` and `lint:NAME` instances for custom groups.
The base build instance is host; `dev.py build` runs all enabled trees. Named
lint instances analyse that tree's commands and reached headers; the base lint
instance checks merged ownership and header coverage across available compile
contexts. `dev.py lint` runs the lint group, including named instances, so
conditional profile code is checked under its own flags. Package Doxyfiles run
from their package roots; explicit shared Doxyfiles run from the checkout root.

A gate may declare a `provider` name, a tuple of alternative provider names,
or `None` for repository-wide gates. A tuple applies when any owner is declared.
Existing extensions that omit it are repository-wide. An undeclared provider
shows `n/a: <provider> not declared` in `check --list` and `N/A` in results;
it needs no CI skip allowance. Declared gates still fail CI when skipped without
an allowance or when required tools cannot run. `Runner.applicable_gates()`
provides the obligation set for CI rendering and coverage.

## Agent conveniences

`python3 dev.py context [path]` lists agreements, local instruction files,
pinned guides, rule chapters and package documents for the path. Relative paths
use the caller's working directory; `--json` provides the same bindings as JSON.
Review checks root routing pointers and instruction size limits.

Machine notes live in `local.md` in the House config directory. `context` also
prints that directory, whether `local.md` exists in it, and the directory of each
name the repository registers in `house.toml`:

```toml
[context]
config_directories = ["sample"]   # lowercase names, none of them "house"
```

The text form adds `House config directory: PATH`, `local.md: present` or
`local.md: absent`, and one `NAME config directory: PATH` line per registered
name. `--json` adds `house_config` (`directory`, `local_notes_present`) and
`config_directories` (name to path); `local_notes` keeps its list of existing
files. An unresolvable location returns exit 2.

`house.api.user_config_dir(name)` resolves `<base>/<name>` without creating it;
`name` is one lowercase path segment (`[a-z][a-z0-9_-]*`). The base is, in order:

`HOUSE_CONFIG_HOME`, when set, must be absolute and nonempty. Otherwise the
resolver uses the native per-user configuration base, honouring an absolute
XDG configuration override where supported. An unavailable required base is
refused. Use `context` to locate your House config directory; shared documents
refer to that directory by name.

A refusal raises `house.api.CannotRunError`. Text in an indexed file names a
configuration directory by its name, never by path; `context` prints the path.

## Tool preparation and scaffolding

`toolchains.toml` selects prerequisites from declared providers and optional
`tests`, `platform-tests` and `online` profiles. Version references point to the
configuration that owns each pin. Python packages stay in `.house/toolchain/`;
compatible existing tools are reused. Runtime commands need no installed House
package. These are explicit installation commands:

```text
python3 dev.py toolchain doctor
python3 dev.py toolchain install --profile platform-tests
python3 dev.py toolchain run pytest -W error
```

The platform-tests profile includes tools used by House's C++ fixtures. A family
with Python tests uses `--profile tests` instead. Missing native prerequisites
are reported; install them explicitly and rerun. `--system` explicitly permits
APT installation on Linux. It never installs native packages on Windows.
Neither command installs `uvx` or edits PATH. `doctor --hooks` limits inspection
to installed Git hooks when language prerequisites are not available.

From a clean committed platform checkout, create an empty sibling checkout:

```text
python3 dev.py init --kind family --lang python ../sample-family
```

A family whose infrastructure repository pins House one level down passes that
checkout and both paths:

```text
python3 dev.py init --kind family --lang python ../sample-family \
    --platform-source ../family-infra --pin-path infra --platform-path infra/house
```

Init supplies the standard, guides, tool configuration, tool preparation and
runner. The environment is provided by `python3 dev.py toolchain install`.

Templates render the configured platform path; a template that hardcodes the
default path is refused. A pin path that is empty, or that equals or lies under
a top-level path the scaffold writes (`docs`, `tests`, `.github`), is refused
before anything is created. Nested pins initialize from the local source. When
the source has `family.toml`, init records its path in the root `family` key. The
family then sets the published URL of its pin, which House cannot know.

Init creates the initial local commit using your configured Git author identity.
It preserves nonempty destinations and installs no tools or home configuration.
The generated family pins the current platform commit; `--platform-source PATH`
selects another clean local platform checkout. Its tracked submodule URL is the
final distribution URL, with local clone sources configured before initialization.
Until publication, configure local sources before a fresh submodule init too.
One nested standard pin is retained. C++ and Markdown are other `--lang` choices;
repeat the option for multiple providers. Python-only output has no C++ copies
or skip allowances. `--kind platform` clones a local platform with its standard
pin, while `--kind standard` clones that standalone standard without a platform
pointer. Those two kinds retain their source history and have no configured remote.

## Generated CI

Include `.github/workflows/ci.yml` in `sync.files`. Each applicable group gets a
job; undeclared providers contribute none, while declared unavailable gates keep
their obligations. `[ci].require` adds matrices and `schedule = "weekly"`.
Weekly jobs run on schedule or dispatch; other groups run on pushes, pull requests
and dispatches. Checkout uses an immutable action pin, recursive submodules and
full history. Preparation installs declared tools; owned Python tests also run
in the standards job with warnings as errors.

Every matrix axis reaches the check as `HOUSE_MATRIX_<UPPERCASE_AXIS>`.
`build_type` also sets `BUILD_TYPE`; C++ `compiler = ["gcc", "clang"]` sets
`CC` and `CXX`, using the pinned Clang major. Other axes reach profiles through
the environment, or name a CMake cache variable under `[ci.axes]`:

```toml
[[ci.require]]
group = "build"
matrix = { build_type = ["Debug"], profile = ["default", "large"] }

[ci.axes]
profile = "SAMPLE_PROFILE"
```

Every configure House makes of a tree (the build and consumer gates, and the
consumer gate's producer) then adds `-DSAMPLE_PROFILE=<value>` when
`HOUSE_MATRIX_PROFILE` is set and not empty, so the generated job's leg and a local
`HOUSE_MATRIX_PROFILE=large python3 dev.py check` configure the same way. A consumer
project the consumer gate builds is not given the variable, because it declares
none. A key is a lowercase axis that appears in a `[[ci.require]]` matrix, other than
`build_type` and `compiler`; a value is a CMake variable name that House does not
set itself (`CMAKE_BUILD_TYPE`, the compiler, install and prefix variables,
`<PREFIX>_ENABLE_TESTS`, `<PREFIX>_ENABLE_FUZZERS`) and no other axis names. A value
of the environment variable may use letters, digits and `_.+-`. A malformed
declaration makes `house.toml` malformed (exit 2). A literal `ci.container` selects the job image; `"devcontainer"`
reads the strict JSON file's explicit image. Build-only devcontainers need an
image selection before rendering. `ci.container_user` selects the user (or
user:group) for every job container; it is appended as `--user VALUE` after
per-group options and has no effect when no job image is selected. A `[[ci.require]]` entry's single-line
`container_options` string is copied into that group's job only; it requires
`ci.container`, and GitHub-unsupported `--network` and `--entrypoint` are
refused. House never runs the options locally. A `prepare` array of single-line
commands renders, in order, as named steps after tool preparation in that group's
job; House never runs them locally either, and `synced-files` refuses an edited or
removed step. Checkout disables persisted credentials. Main runs and matrix legs
use distinct concurrency groups.
The committed workflow must equal the generated output; `synced-files` reports
edits with the regeneration command. Review checks the declared obligations.

The optional `.devcontainer/devcontainer.json` sync file uses the `devcontainer`
overlay ID. Its base contains editor settings and extensions; repositories or
families supply `image` or `build`, plus `name` and `runArgs` as needed. Rendering
refuses a devcontainer with neither build nor image. No language selects this
file by default. Family init keeps the repository's instructions and refers to
`<family>/agents/AGENTS.md` in place of its route table; standalone init retains
the table. The environment comes from `python3 dev.py toolchain install`.

A `house_cxx_enable_sanitizers(PREFIX)` call declares the built-in `sanitize`
tree, enabled only by `HOUSE_MATRIX_SANITIZE=ON`. It adds Debug after the normal
build-type arguments, `<PREFIX>_SANITIZE=ON`, and `ASAN_OPTIONS=detect_leaks=1`.
The per-tree checks are `build:sanitize` and `lint:sanitize`; a declared profile
with the same name is refused.
