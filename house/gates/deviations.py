# SPDX-License-Identifier: MIT
# AR-19: counts and ratchets ceilings; review checks registration.
"""Count suppressions against one ratcheting ceiling per language (EN-00.6)."""

import fnmatch
import re
import tomllib
from collections import Counter
from pathlib import Path

from house.api import Finding
from house.core import CannotRunError
from house.gates.common import Always, optional, verdict
from house.prose import C_FAMILY, comments
from house.tools import platform

PYTHON = re.compile(
    r"#\s*(?P<file>(?:ruff|flake8)\s*:\s*)?noqa\b(?:\s*:\s*(?P<codes>[A-Z]+[0-9]*(?:\s*,\s*[A-Z]+[0-9]*)*))?",
    re.IGNORECASE,
)
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?:\[([^]]+)\])?", re.IGNORECASE)
PYLINT = re.compile(r"#\s*pylint:\s*disable\s*=\s*([^#]+)", re.IGNORECASE)
CXX = re.compile(r"\bNOLINT(?:NEXTLINE|BEGIN|END)?\b(?:\(([^)]*)\))?")
IWYU = re.compile(
    r"(?://|/\*)\s*IWYU pragma:\s*"
    r"(?:keep|begin_keep|always_keep|export|begin_exports)\b",
)
SHELL = re.compile(r"#\s*shellcheck\s+disable(?:=(\S+))?")
MARKDOWN = re.compile(
    r"<!--\s*markdownlint-disable(?P<inline>-(?:line|next-line))?\s*(?P<rules>.*?)\s*-->",
)


def suppressions(repo, paths):
    counts = Counter()
    for path in paths:
        if path.suffix in C_FAMILY | {".py", ".sh", ".bash", ".md"}:
            for comment in comments(path, repo.read(path)).values():
                if path.suffix == ".py":
                    counts["python"] += sum(
                        bool(p.search(comment)) for p in (PYTHON, TYPE_IGNORE, PYLINT)
                    )
                elif path.suffix in C_FAMILY:
                    counts["cxx"] += bool(CXX.search(comment)) + bool(
                        IWYU.search(comment),
                    )
                elif path.suffix in {".sh", ".bash"}:
                    counts["shell"] += bool(SHELL.search(comment))
                else:
                    counts["markdown"] += bool(MARKDOWN.search(comment))
        if path.name in {"ruff.toml", ".ruff.toml", "pyproject.toml"}:
            counts["python"] += len(python_configuration(repo, path, paths))
        elif path.name == ".clang-tidy":
            counts["cxx"] += cxx_disables(repo, path)
        elif path.name == ".shellcheckrc":
            counts["shell"] += sum(
                len(line.split("=", 1)[1].replace(",", " ").split())
                for line in repo.read(path).splitlines()
                if line.startswith("disable=")
            )
    return +counts



def cxx_disables(repo, path):
    def tokens(text):
        visible = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        return set(re.findall(r"(?<![\w-])-(?:[a-z][\w*-]*|\*)", visible))

    canonical = platform(repo) / "config/.clang-tidy"
    if repo.root / path == canonical:
        return 0
    disabled = tokens(repo.read(path))
    if path.parent == Path() and canonical.is_file():
        disabled -= tokens(repo.read(canonical))
    return len(disabled)


def matches(pattern, path):
    name = path.as_posix()
    return (
        fnmatch.fnmatch(name, pattern)
        or ("/" not in pattern and fnmatch.fnmatch(path.name, pattern))
        or (pattern.startswith("**/") and fnmatch.fnmatch(name, pattern[3:]))
    )


def python_configuration(repo, path, paths):
    raw = tomllib.loads(repo.read(path))
    config = (
        raw.get("tool", {}).get("ruff", {}) if path.name == "pyproject.toml" else raw
    )
    lint = config.get("lint", {})
    disabled = {
        (rule, "**"): "python"
        for field in ("ignore", "extend-ignore")
        for rule in lint.get(field, [])
    }
    for field in ("per-file-ignores", "extend-per-file-ignores"):
        for pattern, rules in lint.get(field, {}).items():
            if any(matches(pattern, name) for name in paths if name.suffix == ".py"):
                disabled.update({(rule, pattern): "python" for rule in rules})
    return disabled


def budgets(repo, path, counts, *, ratchet):
    text = optional(repo, path)
    limits, findings, report = {}, [], []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([a-z]+)\s*=\s*(\d+)", line)
        if not match or match[1] in limits:
            findings.append(
                Finding(path, number, "EN-00.6", "malformed or duplicate budget"),
            )
        else:
            limits[match[1]] = int(match[2])
    for key in sorted(limits.keys() | counts.keys()):
        count, limit = counts.get(key, 0), limits.get(key, 0)
        report.append(f"{key}: {count} of {limit}")
        if count > limit:
            findings.append(
                Finding(
                    path,
                    0,
                    "EN-00.6",
                    f"{key}: {count} exceeds its ceiling of {limit}",
                ),
            )
        elif count < limit:
            report.append(f"lower {key} to {count}")
    if ratchet and not findings:
        changed = re.sub(
            r"(?m)^(\s*([a-z]+)\s*=\s*)\d+",
            lambda match: match[1] + str(counts.get(match[2], 0)),
            text,
        )
        (repo.root / path).write_text(changed, encoding="utf-8")
    return findings, "; ".join(report)


class Deviations(Always):
    name = "deviations"
    group = "standards"
    rules = ("EN-00.6",)

    def run(self, repo, argv):
        if argv not in {(), ("--ratchet",)}:
            raise CannotRunError("deviations supports only --ratchet")
        findings, reports, pending = [], [], []
        all_paths = repo.tracked()
        for package in repo.packages.values():
            root = Path(package["path"])
            nested = [
                Path(other["path"])
                for other in repo.packages.values()
                if Path(other["path"]) != root
                and Path(other["path"]).is_relative_to(root)
            ]
            paths = [
                path
                for path in all_paths
                if path.is_relative_to(root)
                and not any(path.is_relative_to(child) for child in nested)
            ]
            counts = suppressions(repo, paths)
            budget_path = Path(
                package.get("budget", str(root / "docs/deviation-budget.txt")),
            )
            faults, report = budgets(repo, budget_path, counts, ratchet=False)
            findings.extend(faults)
            reports.append(report)
            pending.append((budget_path, counts))
        if argv and not findings:
            for budget_path, counts in pending:
                budgets(repo, budget_path, counts, ratchet=True)
        return verdict(
            "EN-00.6",
            findings,
            "; ".join(reports) or "no suppressions or ceilings",
        )
