# SPDX-License-Identifier: MIT
"""Resolve Markdown links against indexed paths, including pinned submodules."""

import re
from pathlib import Path
from urllib.parse import unquote

from house.api import Finding
from house.core import CannotRunError, foreign_git_environment, git
from house.gates.common import Always, no_args, verdict

INLINE = re.compile(
    r'!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+["\'][^"\']*["\'])?\s*\)',
)
REFERENCE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def links(text):
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
        elif not fence:
            reference = REFERENCE.match(line)
            targets = [reference.groups()] if reference else INLINE.findall(line)
            for angled, bare in targets:
                yield number, angled or bare


def indexed(root, prefix=Path(), *, foreign=False):
    """Walk gitlinks at their recorded commits; never guess files inside a pin."""
    names = set()
    env = foreign_git_environment() if foreign else None
    for row in git(root, "ls-files", "--stage", "-z", env=env).split("\0"):
        if not row:
            continue
        metadata, name = row.split("\t", 1)
        mode, sha, stage = metadata.split()
        if stage != "0":
            raise CannotRunError(f"unmerged index entry: {prefix / name}")
        path = prefix / name
        names.add(path)
        if mode == "160000":
            child = root / name
            if not (child / ".git").exists():
                raise CannotRunError(
                    f"submodule missing: {path}; initialise recursively",
                )
            actual = git(
                child,
                "rev-parse",
                "HEAD",
                env=foreign_git_environment(),
            ).strip()
            if actual != sha:
                raise CannotRunError(
                    f"submodule {path}: index pin {sha}, checkout {actual}",
                )
            names.update(indexed(child, path, foreign=True))
    return names


class DocLinks(Always):
    name = "doc-links"
    group = "standards"
    rules = ("EN-03.8",)

    def run(self, repo, argv):
        no_args(argv)
        known = indexed(repo.root)
        known.update(parent for path in tuple(known) for parent in path.parents)
        findings, count = [], 0
        for path in repo.tracked("*.md"):
            for number, target in links(repo.read(path)):
                part = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not part or SCHEME.match(target):
                    continue
                count += 1
                base = repo.root if part.startswith("/") else (repo.root / path).parent
                resolved = (base / part.lstrip("/")).resolve()
                if (
                    not resolved.is_relative_to(repo.root)
                    or resolved.relative_to(repo.root) not in known
                ):
                    findings.append(
                        Finding(path, number, "EN-03.8", f"broken link: {target}"),
                    )
                elif not resolved.exists():
                    raise CannotRunError(f"cannot read link target: {resolved}")
        return verdict("EN-03.8", findings, f"{count} relative links checked")
