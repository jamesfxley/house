# Product family

This repository owns a product family's packages, dependency graph, profiles
and target-specific behavior. Its `house.toml` selects the pinned platform, optional `family` reference and
package modes. A family reference reads the pin's `family.toml`; repository
settings win, and inherited gates and trees import directly from that pin. Read README.md, CONTRIBUTING.md and docs/README.md before work.

Done means `python3 dev.py check` passes against the final state and the final
diff is reviewed. Use `py -3 dev.py check` on Windows where installed.
`python3 dev.py check --list` names applicable gates; `--all` adds online checks.
Warnings fail. Report unavailable checks as missing evidence, never as passes.

| Work | Read from the repository root |
|---|---|
| Shared working agreements | `@PLATFORM@/agents/AGENTS.md` |
| Engineering rules, any language | `@PLATFORM@/guides/engineering-standard/SKILL.md` |
| C/C++ | `@PLATFORM@/guides/cxx-standard/SKILL.md` |
| C++ tests | `@PLATFORM@/guides/cxx-testing/SKILL.md` |
| CMake, toolchains and installed packages | `@PLATFORM@/guides/cxx-build-and-toolchain/SKILL.md` |
| New repositories | `@PLATFORM@/guides/new-repo/SKILL.md` |
| Every ready diff | `@PLATFORM@/guides/review/SKILL.md` |
| Local invariants | `docs/orientation.md` |
| Requirements and pass criteria | `docs/technical-specification.md` |
| Implementation structure | `docs/architecture.md` |
| Document routing | `docs/README.md` |

Keep family facts here. Machine notes live in `local.md` in your House config
directory; `python3 dev.py context` prints where that is. Extend the platform
only through its declared configuration and `house.api`; do not edit pinned or
synced files. Initialize recursive submodules before checks.
Use pinned guide links, not installed copies. Document public installed module
targets separately from internal exports. Commit subjects name the changed
directory or dominant area; no trailers. The working agreements' approval
boundaries apply.

never create `CLAUDE.md` or `CLAUDE.local.md`
