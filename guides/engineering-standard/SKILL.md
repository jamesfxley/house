---
name: engineering-standard
description: "Load at the start of work in a repository under the house standard, and before adding a suppression or lint exception, writing or changing a specification or any docs/ file, setting up CI, or cutting a release. Contents: the house engineering standard, independent of language - quality gates and the deviation procedure for suppressions, requirement IDs and traceability, documentation and specification structure, testing philosophy, CI shape, release and versioning. Rule IDs are EN-<chapter>.<n>. Bind it to a language with the matching <lang>-standard skill."
---

# Engineering standard

Rules that survive a change of language. Rule IDs are `EN-<chapter>.<n>`.
A language's own rules live in its `<lang>-standard` skill and cite these rather
than restating them.

The [pinned standard](../../standard/README.md) owns the rules, rule format
and citation conventions. Follow this checkout's pin, including when this guide
is under the configured platform path in a family.

Chapters load on demand:

| Chapter | Load it when |
|---|---|
| [00-conformance.md](../../standard/engineering/00-conformance.md) | Adding a suppression, granting an exception, or reading a rule's normative force |
| [01-quality-gates.md](../../standard/engineering/01-quality-gates.md) | Setting up or changing linting, warnings, sanitizers, coverage |
| [02-spec-and-traceability.md](../../standard/engineering/02-spec-and-traceability.md) | Writing a requirement, citing one from code, or reviewing requirement citations |
| [03-documentation.md](../../standard/engineering/03-documentation.md) | Writing or restructuring anything in `docs/` |
| [04-testing.md](../../standard/engineering/04-testing.md) | Adding tests, designing a seam, choosing what to fake |
| [05-ci-shape.md](../../standard/engineering/05-ci-shape.md) | Creating or editing a CI workflow |
| [06-release-and-versioning.md](../../standard/engineering/06-release-and-versioning.md) | Cutting a release, bumping a version, changing a public API |
| [07-version-control.md](../../standard/engineering/07-version-control.md) | Naming a branch, writing a commit subject, opening an issue or a pull request |
