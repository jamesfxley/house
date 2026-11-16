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

A seam is an interface between portable code and an environment dependency. Each
dependency has one interface and one fake (`EN-04.1`). A thin adapter holds the
hardware code; the rest runs on a developer machine in milliseconds.

The fake implements the dependency's contract. An adapter that returns an error
where the contract says success traps a caller in its drain loop, even when
tests against the fake pass. Where a contract has a subtle clause ("returns
success for an empty bus and clears the latch"), the fake must be able to
produce that case, and a test must exercise it.

Choose the smallest interface that models the dependency contract. Keep target
adapters and their policies in the family; test the portable behaviour with a
fake that implements the contract.

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

**Boundary triples.** Each capacity is tested one below, exactly at and one
above its limit, and each counter at its wrap point.

**Allocation counting.** Where the project commits to no post-initialisation
allocation, override global `operator new`/`delete` to count. That override is
malloc and free by definition and needs file-scope state, because `operator new`
takes no context argument. Any required deviation still needs approval and
registration; this pattern does not grant an exemption.

## Sanitizers

```
-D<PREFIX>_SANITIZE=address    # ASan + UBSan, before creating compiled targets
-D<PREFIX>_SANITIZE=thread     # TSan + UBSan without vptr; never with ASan
```

House's `sanitize` tree sets `ASAN_OPTIONS=detect_leaks=1` for `address` and
`TSAN_OPTIONS=halt_on_error=1` for `thread`, and compiles with
`-fno-sanitize-recover=all`, so undefined behaviour fails at the report rather
than continuing. Run threaded tests under `thread` (CXX-08.1). Any
`UBSAN_OPTIONS` setting is the CI author's choice.
A sanitizer whose reports are counted and ignored provides no blocking check.

## Fuzzing

Fuzzing uses libFuzzer with Clang, with one target per parse entry point.

Use `house_cxx_add_fuzzer` from the [CMake API](../../cxx/README.md), with a
synthetic parser input and explicit bounds. Prefer forming a span at the entry
point to spreading pointer arithmetic through the parser. The
[EN-00.4 suppression procedure](../../standard/engineering/00-conformance.md)
applies to unavoidable suppressions.

Cache the corpus between CI runs. Starting empty every night rediscovers shallow
states and never reaches the deep ones, which is where the bugs are. Fuzzing runs
with a short budget on push and a long budget on the schedule (`EN-05.4`).

## Test-tree literals

Literal sizes, offsets and expected values define the test case. Giving each
value a name moves it away from the assertion that uses it (`EN-04.7`).

Do not disable a check just because this is a test directory. Measure the
findings and follow the
[deviation procedure, EN-00.3 to EN-00.6](../../standard/engineering/00-conformance.md).
Implement the approved scope configuration only after approval. This guide
grants no suppression or ceiling increase.

Fixture state, stack-owned test doubles and allocation counters still need
site-specific reasoning; none is a blanket exemption.

## Asserting on an optional without a suppression

`bugprone-unchecked-optional-access` fires on every dereference guarded by
`ASSERT_TRUE(result.has_value())`. Its dataflow analysis cannot see through the
GoogleTest macro's early return. That limitation is not tunable, and `.value()`
also triggers the check.

A suppression would recur at every test of an API returning `std::optional`,
using the language's suppression ceiling for a tool limitation. Follow
[EN-00.3](../../standard/engineering/00-conformance.md). Guard with a plain
`if`, which the analysis understands:

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
