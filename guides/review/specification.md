# Specification review

You audit whether a project's specification, code and tests still agree. Report
findings; do not edit.

Load [engineering-standard](../engineering-standard/SKILL.md), chapters
`02-spec-and-traceability` and `03-documentation`.

## Start with the gates

Run the repository's suppression count and document link checks first.
Review requirement citations and the prose deviation register. The repository names its gates in
one place: its gate entry point, which lists them, or its `AGENTS.md`. Run them as named there; do not guess a path.

Report their failures, then audit what they cannot see.

## What the gates cannot see

**Citations that point nowhere** (`EN-02.2`). Grep the code for requirement-ID
patterns and for section references. Two findings: an ID cited in code but not
defined in the specification, and any citation of a *section number* rather than
an ID — the latter is silently wrong the next time the document is reorganised.

**Matrix rows without a real pass criterion** (`EN-02.5`). A criterion that
restates the requirement ("behaves correctly") is not one. A criterion with no
named test is not one either.

**Requirements with no behavioural content.** A row that cannot be failed by any
input is decoration; it inflates the traceability count and establishes nothing.

**Measurements in the normative document** (`EN-03.2`). A specification may state
a gate ("at most 7 sample requests, checked by test_request_limit"); it may not state a measured value. Look for
numbers with units that read as observations rather than limits, and for anything
naming a date or a run.

**Run records without conditions** (`EN-06.7`). A committed measurement missing
build type, target or configuration cannot be compared with the next one, which
is the only thing measurements are for.

**Roadmap content presented as normative** (`EN-03.3`). A planning document
stating what the system *does* rather than what is planned. This is how an
unimplemented design gets treated as a commitment.

**Expired or hollow standing deviations** (`EN-00.5`). Check dates as well as a rationale that says the rule is inconvenient rather than
inapplicable, or a risk column that names no mitigation.

**Exceptions used as a parking space** (`EN-02.7`). An entry in the traceability
exceptions file whose reason amounts to "no test yet" — that is an uncited
requirement, which review must identify.

## Coverage

Use the explicit scope recorded by the [review guide](SKILL.md). For a whole
surface review, list files and relevant requirements, matrix rows, suppressions,
exit paths and test cases before reading. Judge each as ok, finding or unchecked
with a reason; report every gap. A test-case verdict means the assertion can
fail for a plausible defect, not merely that its label names a behavior.

## How to report

Group by document. Most severe first: things that are *wrong* before things that
are *missing*.

For each: the file and line, what disagrees with what, and what to change. Where
the fix is a judgement between updating the specification and updating the code,
say which one you think is authoritative and why — that is usually the useful
part of the finding.

An audit with nothing to report is a legitimate result. Say so plainly rather
than manufacturing observations.

## Close with coverage and decisions

List the reviewed scope and any unchecked items with reasons. Separate defects
introduced by this diff from pre-existing findings. Do not create a ledger.
Distinguish ordinary corrections from decisions requiring approval under the
working agreements. Report-only review grants no permission to change a
specification, public API, dependency or deviation; check the current request's
authorization before applying those changes.

Every specification edit is a normative-document checkpoint. Use explicit
authorization already covering the change; otherwise prepare the concrete
correction and ask before applying it.
