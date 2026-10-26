# C++ review checklist

What source review spends its effort on in C++. The rules are the
[`cxx-standard`](../../cxx-standard/SKILL.md) chapters; this is the order in which they tend to
matter.

clang-tidy runs on this code and blocks the build, so **do not re-report what it
already catches**. The reviewer's value is the `review` entries in the Other checks column of
[enforcement-matrix.md](../../../standard/cxx/enforcement-matrix.md), the subset of the
house rules no tool checks. Read it and work down it.

In rough order of how often they matter:

1. **Suppressions that should have been fixes** (`CXX-00.1`, `EN-00.3`). For
   every new `NOLINT`: does the justification explain why the rule's *purpose*
   is not served here, or does it just restate that the check fired? Would
   changing the design remove the need? A new scope-wide disable is a finding
   unless `docs/deviations.md` gained a matching row in the same change.

2. **Bounds on fixed-capacity storage** (`CXX-06.3`). This is the rule carrying
   the weight of a disabled check, so nothing else is looking. For every
   subscript: name the guard — a loop bound from the capacity, an early return,
   or an index type that cannot be out of range. If you cannot find one, that is
   a finding.

3. **Ownership and lifetime** (`CXX-06.5`, `CXX-06.6`, `CXX-06.7`). A stored
   `span` or `string_view`: who owns the storage and does it outlive this? A
   buffer handed to a lower layer: what says it stays valid until released?

4. **Error handling** (`CXX-07.2`). Any path that clamps, truncates, or returns
   a default where input exceeded a limit. This is the highest-severity common
   defect: the value passes every later check and is wrong.

5. **Interface design** (`CXX-04.3`, `CXX-04.5`, `CXX-04.7`). A capacity-limited
   operation returning a status that is not `[[nodiscard]]`. Two adjacent
   same-typed parameters that could be swapped. Preconditions neither checked
   nor documented.

6. **Concurrency and interrupt context** (`CXX-08.*`). Any new shared state:
   what synchronises it? Any atomic: is the memory order justified? Anything
   multi-word crossing contexts: is there a publication protocol? Any deadline
   arithmetic: is it wrap-safe?

7. **ABI and propagation** (`CXX-10.3`, `CXX-10.4`). A new compile definition
   that a consumer's translation units must see — is it `PUBLIC` on the owning
   target? This fails silently as stack corruption downstream.

In tree mode, the consumer-experience yardstick reads from the public headers
and the out-of-tree consumer test (`tests/consumer/`) outward.

8. **Installed package API.** Verify documented supported public module targets
   separately from internal strict exports needed for static-library closure.
   Consumers must not depend on internal target names. With `NAMESPACE beta`,
   `beta_core` imports as `beta::core`; external examples and consumer tests
   must use that exported spelling rather than the producer's build-tree name.
   Inspect relocated installed interfaces for producer paths, warning flags and
   missing dependency discovery. Verify required public compile definitions.

9. **Version boundaries.** The house pin selects helpers,
   without a separate helper version guard. Installed libraries retain explicit
   package versions and compatibility checks. Test accepted and refused
   `find_package` versions across major boundaries and pre-1.0 minor boundaries;
   a pin bump is not a substitute for package compatibility evidence.
