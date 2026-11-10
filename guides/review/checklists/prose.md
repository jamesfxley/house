# Prose review checklist

Applies to documents and to comments in source. The rules are
[EN-03.9 to EN-03.13](../../../standard/engineering/03-documentation.md) and
[EN-00.9](../../../standard/engineering/00-conformance.md). A finding names the
rule and quotes the text.

## Documents

1. The document serves the reader its routing row names, in one register
   throughout. Agent instructions appear only in documents written for agents
   (`EN-03.9`).
2. Sentences are full, with one claim each, in the fewest words that keep the
   reasons. There are no stacked nouns, distant referents, filler, slogans or
   emphasis for tone (`EN-03.10`).
3. Spelling is British; identifiers keep their own spelling (`EN-03.10`).
4. Each term the reader may not know is defined at first use or in a linked
   glossary, and each concept has one name (`EN-03.11`).
5. Each fact is stated once; other documents link to its owner. Policy the
   standard owns is cited by ID (`EN-03.13`).
6. Requirement IDs are trailing tags, absent from headings outside the
   specification and absent from READMEs (`EN-02.1`).

## Comments

1. Each comment states what the code does not show: a contract, a unit, an
   invariant, a hazard, a required order or an external source (`EN-03.12`).
2. No comment restates the code, defends it against an alternative, addresses
   a reviewer or a tool, or repeats the specification. The suppression
   justification `EN-00.4` requires is the exception (`EN-03.12`).
3. A doc comment is as long as its contract; a simple member has a one-line
   brief (`EN-03.12`).
4. Rule IDs appear only in suppression justifications and in code that checks
   the rule (`EN-00.9`). Requirement IDs follow the sentence they support
   (`EN-02.1`).
5. Comments on changed code were updated or removed (`EN-03.12`).
6. Each comment reads on its own. Its subject and every referent ("the
   guarantee", "this reason", "as above") are in the comment or in the code
   beside it. When a change shortens or deletes a comment, re-read the
   comments around it: a comment that relied on the removed text is now
   incomplete (`EN-03.10`).

## Reference examples

Each pair shows a passage before and after the rules.

A doc comment, before (17 lines; excerpt):

```cpp
/// Drop an assertion a transfer the host has already performed answered.
///
/// The hub asserts once per transfer, not once per cargo: ... A host that
/// retrieves one cargo in two transfers is therefore owed two assertions, and
/// the second announces the transfer it has just finished rather than a new
/// cargo. ... Left latched, either outlives its assertion: ...
```

After:

```cpp
/// Clear the flag for an assertion that announces a transfer already made.
///
/// The hub asserts once per transfer, not once per cargo (1000-3535 §2.6).
/// A cargo read in two transfers, or a reply to WAKE, therefore leaves an
/// assertion with nothing new behind it. Unlike consume(), this counts no
/// level fallback and leaves the timestamps unchanged (HR-1, HR-5, HR-6).
```

A README paragraph, before:

> lwIP requires the application to provide `lwipopts.h`, and
> `PICO_LWIPOPTS_TARGET` **must** name the INTERFACE target carrying yours —
> configuration fails without it. There is deliberately no default: the Pico
> SDK compiles lwIP into whichever target links its INTERFACE libraries, so a
> fallback would build a *second* lwIP against a configuration your
> application does not use, whose struct layouts and memory-pool tables
> disagree with the one the rest of your stack uses.

After:

> Your application provides lwIP's `lwipopts.h`. Set `PICO_LWIPOPTS_TARGET` to
> the INTERFACE target that carries it. There is no default: the SDK builds
> lwIP into each target that links it, so a default would build a second,
> differently configured lwIP.

A reference paragraph, before:

> `python3 dev.py sync` renders declared copies; `sync --check` compares their
> exact content. Copy-only files refuse overlays. Structured clangd and VS Code
> overlays merge maps, extend lists without duplicates and refuse conflicting
> scalars unless `sync.replace` lists the field. Unknown keys and unsupported
> types return exit 2.

After:

> `python3 dev.py sync` writes the files House manages, and `sync --check`
> reports any that differ. A copied file accepts no overlay. A structured file
> (clangd or VS Code settings) accepts one: maps merge, lists extend without
> duplicates, and a conflicting scalar is an error unless `sync.replace` names
> it. An unknown key or unsupported type exits with status 2.
