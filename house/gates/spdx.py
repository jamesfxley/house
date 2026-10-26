# SPDX-License-Identifier: MIT
"""Provider-specific licence identifiers on owned sources."""

from house.api import Finding
from house.gates.common import Always, no_args, verdict
from house.providers import get


class Spdx(Always):
    name = "spdx"
    group = "standards"
    rules = ("EN-06.8",)

    def run(self, repo, argv):
        fix = argv == ("--fix",)
        if not fix:
            no_args(argv)
        providers = [get(name) for name in repo.config["house"]["languages"]]
        findings, count = [], 0
        for path in repo.tracked():
            provider = next(
                (item for item in providers if path.suffix in item.suffixes),
                None,
            )
            if provider is None or provider.spdx_line is None:
                continue
            count += 1
            expected = provider.spdx_line.format(
                licence=repo.config["house"]["licence"],
            )
            if expected not in (
                line.rstrip() for line in repo.read(path).splitlines()[:3]
            ):
                if fix:
                    lines = repo.read(path).splitlines(keepends=True)
                    at = 1 if lines and lines[0].startswith("#!") else 0
                    lines.insert(at, expected + "\n")
                    (repo.root / path).write_text("".join(lines), encoding="utf-8")
                else:
                    findings.append(Finding(path, 1, "EN-06.8", f"missing {expected}"))
        return verdict("EN-06.8", findings, f"{count} sources checked")
