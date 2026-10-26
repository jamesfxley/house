# House development tools

House supplies pinned development tools, guides and working agreements. Read
README.md, CONTRIBUTING.md and the pinned standard before work. Runtime code
uses the Python 3.11 stdlib; families import only `house.api`. Optional `family`
references read the pin's `family.toml`; repository settings win and inherited
gate/tree modules import directly from that pin.

Done means `python3 dev.py check`, `uvx --from pytest==9.1.1 pytest` and the
pinned Ruff check named in README.md pass in the final state, and the final
diff is reviewed. Use `py -3 dev.py check` on Windows where installed. Warnings
fail. Report results; review checks conventions that need judgement.

| Work | Read from the repository root |
|---|---|
| Shared working agreements | `agents/AGENTS.md` |
| Engineering rules, any language | `guides/engineering-standard/SKILL.md` |
| C/C++ | `guides/cxx-standard/SKILL.md` |
| C++ tests | `guides/cxx-testing/SKILL.md` |
| CMake, toolchains and installed packages | `guides/cxx-build-and-toolchain/SKILL.md` |
| New repositories | `guides/new-repo/SKILL.md` |
| Every ready diff | `guides/review/SKILL.md` |
| Local design and requirements | `docs/README.md` |

Keep family, device, SDK and machine facts out of shared code and guides; use
synthetic examples. Guide links enter `standard/` at this pin. Do not copy
rules into installed dispatchers. Commit subjects name the changed directory
or dominant area; no trailers. Approval boundaries in the agreements apply.

never create `CLAUDE.md` or `CLAUDE.local.md`
