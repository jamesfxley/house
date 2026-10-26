# Python review checklist

Read [engineering-standard](../../engineering-standard/SKILL.md). Ruff covers
mechanical findings; review the behavior it cannot establish.

1. Trace errors through each exit path. Do faults, unavailable inputs and
   successful or inapplicable checks produce the documented status and finding?
   Refusal tests assert finding text, so a crash cannot count as correct refusal.
2. Check subprocess argument lists, working directories, inherited environment,
   encoding and paths on supported operating systems. Preserve spaces, clear
   foreign Git-local state for submodules, and do not route data through a shell.
3. Keep imports on supported public extension surfaces. Runtime code remains
   stdlib-only; a development dependency does not authorize a runtime dependency.
4. Check absent, malformed and unexpected input, partial writes, stale caches
   and stale successful evidence after failure. Do exception handlers preserve
   the cause rather than convert it to success?
5. Read each test's assertions and setup. Can a plausible defect make it fail?
   Test policy boundaries and negative diagnostics rather than matching code
   structure. Check warning output as well as status.
6. Check requirement citations, approval for exact suppressions, justified scope
   and budgets. New behavior, specification and tests must agree. Keep fixtures
   synthetic and machine facts outside shared code and documentation.
