---
name: new-repo
description: "Read when scaffolding a repository or adopting the pinned standard and platform in an existing repository."
---

# Scaffold a repository

Read [engineering-standard](../engineering-standard/SKILL.md). Choose a library
or application shape: a library owes an external consumer build for its public
surface; an application with a reusable core must test that core as a library.
Keep reusable platform behavior in the platform, family behavior in the family,
and machine notes in `local.md` in your House config directory (`python3
dev.py context` prints where that is).

Use `init` from a clean committed platform checkout. Standalone repositories
receive the environment through `dev.py toolchain install`. A family may supply
a devcontainer build or image through its sync overlay. Optional family
references in `house.toml` read the pinned `family.toml`; repository settings
win and gate/tree modules import directly without adapters. For an empty Python family:

```text
python3 dev.py init --kind family --lang python ../sample-family
```

The kind is `standard`, `platform` or `family`. Repeat `--lang` for additional
providers. Only the family kind renders `templates/` from the configured
platform path, creates local Git state and configures one pin per level.
Standard and platform kinds clone their corresponding source. Existing
nonempty destinations are preserved. Prepare declared tools explicitly, then run
`python3 dev.py check --ci` in the generated family before adoption.
Templates provide initial content, not a second source of shared rules.
Pinned guides remain authoritative, synced copies are hash-checked, and declared
overlays are the only extension path. Use no symlinks or global runtime install.
Adding a dependency or submodule needs specific approval.

## Repository content

The root AGENTS.md states what the repository is, its done command and a routing
table. Standard repositories route to their own rules and run `python3 check.py`.
Platform repositories route to `guides/`; families route to guides under the
configured platform path and their own `docs/`. Keep the instruction file under
4 KiB. End with the
instruction never to create tool-specific instruction files. Do not copy guide
rules or duplicate a platform release number in a template.

Provide README, LICENSE, CONTRIBUTING and SECURITY files. Copy approved licence
text exactly; every tracked source names its licence with an SPDX identifier.
Community policy lives in each repository, rather than depending on an archived
account-level repository. Contributions name the local commands and commit
policy; security guidance names the repository's reporting route.

Each configured package has documents with one owner per fact:

| File under docs/ | Purpose |
|---|---|
| README.md | Route every document to its reader and question |
| technical-specification.md | Normative requirements, stable IDs, named tests and pass criteria |
| architecture.md | Describe implementation structure |
| usage-guide.md | Explain practical use of the public surface |
| orientation.md | Record local invariants and traps |
| future-work.md | Deferred work as `FW-<n>` entries; says so when it has none (`EN-03.7`) |
| deviations.md | Approved standing deviations, rationale, risk and review date |
| deviation-budget.txt | One approved ceiling per language |
| requirement-prefixes.txt | Declare local ID prefixes |
| traceability-exceptions.txt | Explain requirements with no possible citable file, never missing tests |

Keep initial registers and exceptions empty; start suppression ceilings at zero.
If omitting a document is permitted by the applicable contract, record the
routing decision. Review the document set against the pinned standard.
Release notes belong at the release, with approval, rather than in a changelog.
Deferred work is a `docs/future-work.md` entry (`EN-03.7`), and the tracker holds
defects only. Tracker labels and every other GitHub write need their own approval.

## Publication

A repository that becomes public meets these requirements; each is a GitHub
write that needs its own approval. Before the repository is public, the files
`dev.py sync` writes under `.github/` (the defect form and the pull-request
template) are in its tree.

- Secret scanning and push protection are enabled.
- Private vulnerability reporting is enabled; `SECURITY.md` names it as the
  route.
- `main` is protected: strict required status checks naming the CI jobs, a pull
  request required with zero required approvals, protection enforced for
  administrators, and no push restrictions. The root commit is the bootstrap
  exception (`EN-07.5`).
- Squash merge is the only merge method, with the squash commit title taken from
  the pull request title and a blank message (`EN-07.5`). Merge commits and
  rebase merges are disabled.
- Head branches are deleted when merged.
- The label `defect` exists (`EN-07.6`), because an issue form cannot apply a
  label the repository lacks.

## Language, CI and disclosure

For C++, follow [build and toolchain](../cxx-build-and-toolchain/SKILL.md) and
[testing](../cxx-testing/SKILL.md). Other languages use declared provider tooling
at the engineering standard's strictness; a provider's existence is not evidence
that a gate ran.

Follow the pinned CI chapter: build and test, format, lint, standards, installed
consumers, then scheduled long-budget work in its own concurrency group. Derive
obligations from applicable gates and declared package modes. Preserve failures
through logging pipelines; a logger's exit status cannot stand in for a build.
Use the platform's Python commands across operating systems and verify generated
workflow coverage. An unavailable renderer or gate blocks that acceptance.

Describe AI assistance once at repository level, without per-commit attribution.
A suitable README disclosure is:

> This project is developed with AI assistance. Design decisions, review and
> acceptance are human; an AI agent writes and refactors code under direction
> and against a written engineering standard. Every change passes the
> repository's own gates before it lands.

Name only the gates actually run. Refer to the root licence and its disclaimer;
do not add a competing warranty statement to the licence.

## Adoption and verification

For an existing repository, inspect and preserve its changes first. Wire the
pinned tooling, isolate any mechanical reformat in its own commit, then read and
fix the diagnostics. Remaining suppressions and the measured opening ceilings
need approval; do not absorb findings by silently weakening configuration.

Stage only the intended files before indexed gates, then run the repository's
done command, language checks and final diff review. Set the approved ceiling
from justified surviving exceptions; increases need their own reasoned commit
(EN-00.6). Check links and routing after rendering
AGENTS.md at the repository root; paths in template content are root-relative.
Do not claim a scaffold accepted until its applicable gates and fresh-checkout
acceptance run. Never activate user-home configuration as part of scaffolding.
