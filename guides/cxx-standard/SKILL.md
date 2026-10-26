---
name: cxx-standard
description: "Load before writing, reviewing or refactoring C++ (.cpp/.cc/.cxx/.h/.hpp/.ipp), and before choosing between language constructs, resolving a clang-tidy or compiler diagnostic, or deciding whether something warrants a suppression. Contents: the house C++ coding standard - naming, types, expressions, interfaces, classes, resources and lifetime, error handling, concurrency, templates, headers and ABI, constrained-target subset, security. Rule IDs are CXX-<chapter>.<n>. Assumes engineering-standard for the deviation procedure and gate policy."
---

# C++ coding standard

Rule IDs are `CXX-<chapter>.<n>`. This standard assumes
[engineering-standard](../engineering-standard/SKILL.md) and cites `EN-*` rules
rather than restating them — in particular the deviation procedure (`EN-00.3`
through `EN-00.7`), which governs every suppression mentioned here.

The C++ language version and the clang major version are each repository's,
selected by its build configuration and the pinned platform's
`config/.clang-version` (`CXX-13.4`,
`EN-01.7`).

The [pinned standard](../../standard/README.md) owns the rules, rule format
and citation conventions. Follow this checkout's pin, including when this guide
is under the configured platform path in a family.

Chapters load on demand:

| Chapter | Load it when |
|---|---|
| [00-conformance.md](../../standard/cxx/00-conformance.md) | Resolving a diagnostic, or deciding how to suppress one |
| [01-lexical-and-naming.md](../../standard/cxx/01-lexical-and-naming.md) | Naming anything; adding a header; ordering includes |
| [02-types-and-declarations.md](../../standard/cxx/02-types-and-declarations.md) | Choosing a type; declaring a constant; initialising |
| [03-expressions-and-statements.md](../../standard/cxx/03-expressions-and-statements.md) | Casting, arithmetic, loops, control flow |
| [04-functions-and-interfaces.md](../../standard/cxx/04-functions-and-interfaces.md) | Designing a signature; passing parameters; preconditions |
| [05-classes-and-inheritance.md](../../standard/cxx/05-classes-and-inheritance.md) | Adding a type; special members; virtual functions |
| [06-resources-and-lifetime.md](../../standard/cxx/06-resources-and-lifetime.md) | Ownership, allocation, spans and views, dangling |
| [07-error-handling.md](../../standard/cxx/07-error-handling.md) | Reporting failure; capacity limits; input validation |
| [08-concurrency.md](../../standard/cxx/08-concurrency.md) | Shared state, atomics, interrupt context |
| [09-templates.md](../../standard/cxx/09-templates.md) | Writing a template; constraining it; forwarding |
| [10-headers-and-abi.md](../../standard/cxx/10-headers-and-abi.md) | Header layout; compile definitions; export names |
| [11-constrained-targets.md](../../standard/cxx/11-constrained-targets.md) | Freestanding, embedded, or fixed-capacity work |
| [12-security.md](../../standard/cxx/12-security.md) | Handling untrusted input; anything with a trust boundary |
| [13-repository-layout.md](../../standard/cxx/13-repository-layout.md) | Placing a file; adding a module; adding a test directory |
| [enforcement-matrix.md](../../standard/cxx/enforcement-matrix.md) | Auditing whether a rule is actually checked |

## Where these rules come from

The C++ Core Guidelines for design and safety, the Google style guide for
formatting only, and CERT C++ for security — each adopted in part, with the
departures reasoned. The standards repository's README carries the detail,
including why MISRA's text appears nowhere.

## If you read one rule

**CXX-00.1.** A diagnostic is a defect until shown otherwise. The order of
preference is: fix the code, then change the design so the rule stops applying,
then suppress at the site with the rule named and a justification above it. A
scope-wide disable is a registered standing deviation (`EN-00.5`), never a
config line added in passing.

For review, read the [C++ checklist](../review/checklists/cxx.md).
