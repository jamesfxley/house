---
name: review
description: "Review each ready diff against the pinned engineering and language rules, documentation truth, specification agreement and machinery cost before committing."
---

# Review the change

The agent making a change reviews its final diff before commit. No ledger,
review-inventory tool or reviewer subagent is required. Read
[engineering-standard](../engineering-standard/SKILL.md) and the language
checklists below. Use the repository's AGENTS.md and command listing to discover
checks; do not guess commands or infer enforcement from registration.

Record the base revision, changed-file list and languages. Review the complete
diff including staged changes and new files. Gates must be green before the
ready-to-commit review; if a check is unavailable, record that limitation and
review what can be reviewed without claiming acceptance. Report mechanical
failures first and concentrate judgment on what tooling cannot catch.

| Surface | Read |
|---|---|
| Source diff or explicitly requested whole tree | [Source review](source.md) |
| Requirements, citations, tests and matrix | [Specification review](specification.md) |
| Descriptive documents and instructions | [Documentation review](documentation.md) |
| Build, gates, workflow or process machinery | [Machinery cost](machinery.md) |
| C/C++ | [C++ checklist](checklists/cxx.md) |
| Python | [Python checklist](checklists/python.md) |
| Markdown | [Markdown checklist](checklists/markdown.md) |

A whole-tree review also judges the design against the specification and the
public consumer experience. Fix its scope before reading and account for each
item as ok, finding or unchecked with a reason. A diff review judges introduced
defects and records pre-existing defects separately without expanding the fix.
No silent coverage gaps and no persistent review ledger.

## Report and fix

Open with mode, scope, finding count and the most severe finding. For each
finding give severity, rule or contract, file and line, evidence and a concrete
failure. Distinguish confirmed from plausible reachability. Wrong commands
precede wrong prose; wrong claims precede omissions. Drop style preferences
without a concrete failure. An empty review is a valid result.

A source defect needs a failing reproducer before the fix. Check negative tests
for expected finding text as well as status so a crash cannot satisfy refusal.
Do not change an existing test's expectation to fit a fix without approval.
Search everywhere the changed policy applies, including sibling gates. Verify
every specification, comment and message claim against the tree. Keep the fix
bounded to the finding; wider cleanup needs a separate decision.

Review a finding's fix once for introduced defects, then stop the review chain.
A defect introduced by that fix needs a failing test and a mutation proving the
test detects it, rather than another review cycle. For a prose or link
correction, check the claim or target directly instead of inventing a code test.
Rerun affected gates in the final state. Record pre-existing defects and any
remaining unchecked scope in the handoff, without a ledger.

Close by separating ordinary corrections from decisions requiring approval:
public API, dependency, suppression or deviation, version, destructive changes,
and conflicting design choices. A report-only audit does not authorize edits.
Honor authorization already present in the user's request; review is not a new
approval barrier for ordinary authorized corrections.
