---
name: cxx-testing
description: "Load before adding or restructuring a C++ test, and before designing an interface that touches hardware or the network, configuring sanitizers or fuzzing, or deciding what to fake. Contents: GoogleTest layout and CTest targets, designing a host-testable seam with a fake, fixture patterns that find real defects, sanitizer and libFuzzer configuration, and how to handle a test tree's literal values without a blanket lint disable. Pairs with cxx-standard, which still governs the test code itself."
---

# C++ testing

Read [engineering testing](../../standard/engineering/04-testing.md) and
[cxx-standard](../cxx-standard/SKILL.md). This guide supplies C++ mechanics.

## Layout

Tests live under `tests/`, mirroring `src/` (`CXX-13.2`), one CTest target per
module:

```
src/<module>/
├── include/<project>/<module>/…
└── …
src/testing/                    <- fakes, shipped, not test-only
tests/<module>/
├── CMakeLists.txt              -> <project>_<module>_tests
└── <subject>_test.cpp
```

`src/` holds no test code, so an install rule, a footprint measurement or a lint
scope over `src/` needs no exclusion for it.

One target per module keeps a failure attributable and lets a module's suite be
re-run alone. `gtest_discover_tests` registers cases individually so a failure
names the case.

`src/testing/` is part of the shipped library, not the test tree: downstream
projects need the fake to test their own code against this one.

## The seam

One interface per environment dependency, one fake behind it (`EN-04.1`). The
part that needs real hardware shrinks to a thin adapter; everything else runs on
a developer machine in milliseconds.

Two things decide whether this works:

**The fake implements the contract, not just the signature.** An adapter that
returns an error where the contract says success will wedge a caller's drain
loop — and a fake written to the contract will never show it. Where a contract
has a subtle clause ("returns success for an empty bus and clears the latch"),
the fake must be able to produce that case, and a test must exercise it.

Choose the smallest interface that models the dependency contract. Keep target
adapters and their policies in the family; test the portable behavior with a
contract-faithful fake.

## Fixture patterns worth reusing

**Split equivalence.** Feed the input whole, then one byte at a time, and assert
the same verdict (`EN-04.5`). Segmentation is chosen by the network, so any
state kept across a call boundary is exercised by this and by nothing else. This
is the highest-yield test shape for a parser or protocol engine.

```cpp
template <typename Limits = DefaultLimits>
ParseResult parse_all(Parser<Limits>&, std::string_view, std::size_t& consumed);

// The incremental state machine must reach exactly the same verdict
// regardless of segmentation.
template <typename Limits = DefaultLimits>
ParseResult parse_byte_by_byte(Parser<Limits>&, std::string_view);
```

**Boundary triples.** For every capacity: one below, exactly at, one above. For
every counter: the wrap point.

**Allocation counting.** Where the project commits to no post-initialisation
allocation, override global `operator new`/`delete` to count. That override is
malloc and free by definition and needs file-scope state, because `operator new`
takes no context argument. Any required deviation still needs approval and
registration; this pattern does not grant an exemption.

## Sanitizers

```
-D<PREFIX>_SANITIZE=ON    # ASan + UBSan, before creating compiled targets
```

House's `sanitize` tree sets `ASAN_OPTIONS=detect_leaks=1` and compiles with
`-fno-sanitize-recover=all`, so undefined behaviour fails at the report rather
than continuing. Any `UBSAN_OPTIONS` setting is the CI author's choice.
A sanitizer whose reports are counted and ignored provides no blocking check.

## Fuzzing

libFuzzer, Clang only. One target per parse entry point.

Use `house_cxx_add_fuzzer` from the [CMake API](../../cxx/README.md), with a
synthetic parser input and explicit bounds. Prefer forming a span at the entry
point to spreading pointer arithmetic through the parser. Any unavoidable
suppression still needs specific approval, a named check and justification.

Cache the corpus between CI runs. Starting empty every night rediscovers shallow
states and never reaches the deep ones, which is where the bugs are. Short budget
on push, long budget on the schedule (`EN-05.4`).

## Test-tree literals

Literal sizes, offsets and expected values in a test are the case under test, not
a value shared with production code — hoisting each to a named constant moves the
expected value away from the assertion that reads it (`EN-04.7`).

Do not disable a check just because this is a test directory. Measure the
findings and fix the design first. A scope disable needs specific approval and
a matching standing-deviation row naming the tool's exact check, the rule ID in
the rationale, risk mitigation and review date. Any ceiling increase needs its own approved commit with the reason (EN-00.6).
Implement the bounded scope configuration only after approval.
Follow the [deviation procedure](../../standard/engineering/00-conformance.md);
this guide grants no suppression or budget increase.

Fixture state, stack-owned test doubles and allocation counters still need
site-specific reasoning; none is a blanket exemption.

## Asserting on an optional without a suppression

`bugprone-unchecked-optional-access` fires on every dereference guarded by
`ASSERT_TRUE(result.has_value())`. Its dataflow analysis cannot see through the
GoogleTest macro's early return, and this is not tunable — `.value()` fires
too, so swapping the accessor does not help.

Suppressing it per site is legal but wrong-headed: an API returning
`std::optional` is the house idiom, so the suppression recurs on every test of
every such function and spends the language suppression budget on a tool limitation rather
than on a real deviation. `EN-00.3` says fix before suppressing, and here there
is a fix. Guard with a plain `if`, which the analysis does understand:

```cpp
const auto value = reader.read_u16();
if (!value.has_value()) {
    FAIL() << "read_u16 rejected a two-byte buffer";
    return;
}
EXPECT_EQ(*value, 0x1234);
```

`FAIL()` records the failure; the `return` is what both the analysis and the
reader need, and it makes the test's precondition explicit. Reserve
`ASSERT_TRUE` plus a suppression for the case where the guard genuinely cannot
be restructured.
