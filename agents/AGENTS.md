# Working agreements

These apply in every repository and session. Read the repository's AGENTS.md
and its pinned guides before work. Repository facts belong there; family facts
belong in family documentation. Machine notes live in `local.md` in your House
config directory; `python3 dev.py context` prints where that is. If the file
exists, read it. Do not copy those notes into shared content.

## Git and GitHub

- Every push and every GitHub write needs approval for that specific action:
  pushes, issue and pull-request creation or edits, merges, comments, labels,
  releases and tag pushes. Show the exact proposed content before asking.
  An earlier approval does not cover the next action. Prepare a pull request's
  title and body for the user; do not open, edit, approve or merge it yourself
  without explicit authorization for that action.
- Work on the branch required by the repository's contribution policy. Local
  commits and read-only Git or GitHub queries need no approval.
- Commit messages carry no trailers: no Co-Authored-By, generated footer or
  ticket trailer (EN-07.4). Put issue references in the pull-request body.
- Under the standard, follow EN-07. Subjects are `<area>: <summary>` within
  72 characters. The area names the directory changed; a repository-wide change
  names its dominant area or is split. Use an imperative lowercase summary
  without a final full stop. An issue branch starts with its issue number;
  an issue title states an observable fact. Follow the local policy for bodies.

## Blocked calls

When the permission system, a hook or the user denies a call, say what was
blocked and why it was needed. Do not obtain the same outcome another way.
Continue independent work. A tool bug or documented deprecation is not a denial.

## Quality and review

Warnings and lint findings fail checks. Fix code first, then change the design
so the rule stops applying, before proposing a suppression (EN-00.3).
A suppression needs specific approval, names the exact check, has a preceding
justification and covers one site (EN-00.4). Scope disables require an approved
standing deviation, risk, review date and budget; never widen a budget silently. A ceiling increase needs its own approved commit
with the reason (EN-00.6).

Done means the applicable gates ran against the final state (EN-01.8). Report
the commands and what they printed. Name unavailable or unrun gates and the
missing evidence; they are not passes. Review the final diff with the pinned
review guide, fix introduced findings and record remaining work before commit.
There is no review ledger or required reviewer subagent.

Load the engineering guide for every language, and the applicable language,
testing and build guides when entering that area. A language without a guide
still follows the engineering standard and its repository's strict tooling.

## When to stop and ask

The following need approval unless the current request explicitly authorizes
that specific work:

1. A push or any GitHub write, each as a separate action.
2. A delete, overwrite or history rewrite. Inspect the target first and explain
   what would be lost. Amending, squashing or reordering unpushed commits made
   in the current session is exempt.
3. A version bump, tag or release.
4. A suppression or deviation, new dependency or submodule, or public API change.

Do the concrete, reviewable preparation first. Elsewhere, make the call, explain
it briefly and continue. Clarify only when two readings materially change the
work. Explain the stakes before asking, with one question per decision and the
most correct option first, even when it costs more. State each option's cost;
a relaxed threshold or repeated measurement that leaves the question unanswered
is not a recommended solution. Finish the authorized work; if part is blocked,
complete independent work and say exactly what remains.

## Sourcing truth

Protocol, hardware and API behavior comes from official documentation, not
another open-source implementation. If authoritative documentation is silent,
mark the behavior `UNCONFIRMED` and request the authoritative document.
Use `pdftotext -layout` when extracting vendor PDFs, including tables.
Implementation claims about the current repository must be checked against its
tree; they do not establish an external protocol's contract.

## Writing

Documentation, comments and commit messages state what is true now. Omit
history, narrative, dates and shipping notes from current-state prose; measured
results and their conditions belong in run records. Markdown intended for
pasting elsewhere, including issue and pull-request bodies and commit messages,
goes in a fenced code block.
