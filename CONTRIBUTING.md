# Contributing

Read the [pinned engineering standard](standard/README.md), whose `EN-` IDs
describe the common requirements. The [README](README.md) names the local gate,
test and lint commands. Run them against the final change and report what they
printed; an unavailable check is not a pass (EN-01.8).

Initialise pinned dependencies with `git submodule update --init --recursive`.
Develop on a branch and open a pull request; fork first if you lack write
access. Respect the protection on main. A branch with an issue begins with its
number, followed by a descriptive lowercase slug. Follow
[EN-07.2 to EN-07.4](standard/engineering/07-version-control.md) for commit
subjects, bodies, trailers and issue references. A reviewed change lands as one
squash commit. The merger keeps its subject exactly the pull request title,
removing anything GitHub appends, and writes its body as the change's argument
(`EN-07.3`).

Warnings and lint findings block. The suppression procedure is
[EN-00.3 to EN-00.7](standard/engineering/00-conformance.md). Change behaviour,
its specification and its tests together, with stable requirement IDs. Keep
documents about the current state. Source files carry the SPDX identifier for
the [licence](LICENSE).

Issue titles state an observable fact, without type prefixes. Discuss substantial
changes before implementation, and record deliberately deferred work in
`docs/future-work.md` (`EN-03.7`); the tracker holds defects. Security-sensitive
reports follow [SECURITY.md](SECURITY.md).
