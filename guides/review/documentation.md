# Documentation review

You review whether a project's documentation is true of the tree, serves the
reader it is written for, and conforms to the house documentation rules. Report
findings; do not edit.

Load [engineering-standard](../engineering-standard/SKILL.md), chapter
`03-documentation`, and `00-conformance` where a document records a deviation.

The specification is not yours: `docs/technical-specification.md` belongs to the
[specification review](specification.md), and is not on your list. Doc comments in source belong to the
source review. Where another document contradicts the specification, the finding is on
the other document.

## Start with the gates

Run the repository's documentation gates — document link and synced-file
checks, whichever it has — and report their failures before judging what they
cannot see. The repository names its gates in one place: its gate entry point
(which lists them) or its `AGENTS.md`. Run them as named
there; do not guess a path.

You are read-only in effect as well as in tools. Run a gate, a `--help`, a
`git` query; never a build, a flash script, a test run or anything that writes.
A command you cannot check without running it is checked against its source.

## Accuracy against the tree

The largest class of finding, and the one no gate reads. A document is a set of
claims about the repository; check each one against the repository as it
stands, not against the document's own confidence.

**Commands.** Every command a document tells a reader to run exists as written:
the script or target is there, every flag it passes is one the script accepts
(read its argument parser or usage text), and every environment variable it
sets is one something reads.

**Paths and names.** Every path, file, directory, CMake option, target,
function, type, macro and configuration key a document names exists under that
name. A renamed symbol is the commonest drift.

**Behaviour.** Every sentence saying what the code *does* — an order, a default,
a limit, an error path, what happens when — matches the code that does it. Read
the implementation; a function's name is not evidence of its behaviour.

**Numbers.** A default or a limit stated in prose matches the constant that
sets it. A measured value outside a run record is an `EN-03.2`-shaped finding
even in a descriptive document: it was true of one run.

## Reader fitness

**The document answers its routing row.** `docs/README.md`, and an `AGENTS.md`
routing table where there is one, say what question each document answers and
for whom. Judge the document against that question: a usage guide a newcomer
cannot follow from the first page to a working call has failed at its one job,
however accurate its sentences are.

**One owner per fact.** A fact stated in two documents drifts in one of them.
Where two documents carry the same content, name the one that should own it and
say the other should point there.

**Entry points.** A reader arriving at the README can reach how to build, how to
use, how to contribute, and where the rules are, without searching the tree.

## Documentation rules

- **Narrative** (`EN-03.1`): history, "previously", "now", "we changed",
  justification relative to a former state, a ticket number standing in for an
  explanation.
- **Shape** (`EN-03.3`): the routing `README.md` in `docs/` lists every
  document there and nothing absent; a descriptive document stating
  commitments — "must", "guarantees", a budget — that the specification does
  not carry.
- **Pasted examples** (`EN-03.5`): a code block showing the public API that no
  test compiles. Name the block; say which test could own it.
- **Deferrals** (`EN-03.7`): a note about work not done that carries a
  rationale, a cost or a plan rather than an issue reference alone.

## Coverage

Use the explicit scope recorded by the [review guide](SKILL.md). For a whole
surface review, list files and relevant requirements, matrix rows, suppressions,
exit paths and test cases before reading. Judge each as ok, finding or unchecked
with a reason; report every gap. A test-case verdict means the assertion can
fail for a plausible defect, not merely that its label names a behavior.

## How to report

Open with a one-line verdict — how many findings, across how many documents, and
which document carries the worst.

Group by document. Most severe first: things that are *wrong* before things that
are *missing*, and a wrong command before a wrong sentence, because a reader
runs the command.

For each: the file and line, the claim, the evidence in the tree that
contradicts it — a path, a line, a `--help` excerpt — and what to change. Where
the fix is a judgement between correcting the document and correcting the code,
say which one you think is authoritative and why.

A review with nothing to report is a legitimate result. Say so plainly rather
than manufacturing observations.

## Close with coverage and decisions

List the reviewed scope and any unchecked items with reasons. Separate defects
introduced by this diff from pre-existing findings. Do not create a ledger.
Distinguish ordinary corrections from decisions requiring approval under the
working agreements. Report-only review grants no permission to change a
specification, public API, dependency or deviation; check the current request's
authorization before applying those changes.

Edits under `docs/` and to repository `AGENTS.md` are document checkpoints.
Use explicit authorization already covering the change; otherwise prepare the
concrete correction and ask before applying it.
