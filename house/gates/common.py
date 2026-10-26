# SPDX-License-Identifier: MIT
"""Verdicts and indexed input sets for standards gates."""

from pathlib import Path

from house.api import Finding, Result
from house.core import CannotRunError


def verdict(rule, findings, message):
    return Result(
        1 if findings else 0,
        message,
        tuple(
            item if isinstance(item, Finding) else Finding(".", 0, rule, item)
            for item in findings
        ),
    )


def no_args(argv):
    if argv:
        raise CannotRunError(f"unsupported arguments: {list(argv)}")


def optional(repo, path):
    """Read an optional file, treating a tracked missing input as unreadable."""
    path = Path(path)
    if path in repo.tracked() or (repo.root / path).exists():
        return repo.read(path)
    return ""


class Always:
    provider = None

    def applies(self, _repo):
        return True
