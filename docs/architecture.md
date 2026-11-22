# Architecture

The root launcher loads the configured pinned platform. The command interface
validates `house.toml`, registers gates and runs each selected gate through the
runner. A gate can report a finding or unavailable evidence while the other
gates still run.

Language metadata controls source identification. Indexed files exclude
gitlinks. Families extend only `house.api`. The `sync` command renders copies
from platform-owned inputs, and `synced-files` compares them with the indexed
destination files.

The private registry owns gate construction; importing an individual gate does
not initialise every other gate. Provider tool adapters enumerate indexed source
paths. Builds resolve host, fuzz and public `TreeProfile` declarations, then
merge owned compile commands, preferring host commands. Compiler dependency
output identifies reachable headers. Each scope keeps clang-tidy's normal
configuration discovery. Dependency probes and analyser calls run with one
worker per CPU available to the process (its affinity where the platform reports
one, else the system CPU count), with no fixed cap. Profiles are loaded before
workers start, and each header has a private compile database. Unit analysis
uses the first command per source, as the database merge does. Variants intended
to fail remain in their own tree for CTest to check. Findings retain source
order. The runner asks only the built-in lint gate whether
HOUSE_MATRIX_LINT_TREE leaves it to another matrix cell; that check is internal
and not part of the `house.api` gate contract.

Configuration bases are common or language-specific data. The sync renderer
accepts a fixed set of fields and types. It merges selected provider data before
explicit overlays and profile overlays.

The C++ CMake API owns compiler policy and package exports. Export identities
are explicit, so multiple packages can share one project and release version.
The consumer gate builds in temporary directories, relocates the install prefix
and configures indexed consumer projects with package registries disabled.
The producer is configured with its tests option off when the root project
declares one with `house_cxx_declare_tests_option`, so its test targets are not
built; the fuzz tree keeps its tests.
Package modes determine the install obligations; profiles carry toolchains and
environment. Source-tree helpers are not installed into consumer packages.

The context resolver uses the configured platform path, including non-default
locations, and lists root-to-leaf instructions with overrides. Normative guides
and rule chapters remain in the active checkout.

CI renders applicable group metadata and declared matrices without parsing YAML.
The synced-files check compares exact bytes. Registry creation is delayed until
rendering so individual gate imports do not initialise the registry recursively.
Tool preparation reads version references from the pinned manifest and keeps
Python packages private. The `init` command uses a clean committed local source.
It stages LF attributes before other files, then renders and commits the
selected scaffold. The `doctor` command reads hook and tool state without
installing prerequisites.

Optional family configuration merges beneath repository choices. Family gate
and tree modules import from that pinned directory through the existing public
API. [Configuration](../README.md#public-configuration-reference) owns precedence
and allowed fields. Trees resolve once per lint invocation and are passed to
entry and header processing. Consumers share a temporary producer install when
the tree and producer arguments match; expected producer refusals run separately.
CI declarations may supply container options as data; they never run locally.
