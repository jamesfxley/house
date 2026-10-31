# SPDX-License-Identifier: MIT
"""Check selected commit message format, not merge policy (AR-5, AR-19)."""

import argparse
import json
import os
import re
from pathlib import Path

from house.api import Finding, Result
from house.core import CannotRunError, read
from house.gates.common import Always, verdict

NO_COMMIT_EVENTS = frozenset({"schedule", "workflow_dispatch", "repository_dispatch"})

SUBJECT = re.compile(
    r"(?P<area>(?:[a-z0-9][a-z0-9_-]*|\.[a-z][a-z0-9_-]*)"
    r"(?:/[a-z0-9][a-z0-9_-]*)*): (?P<summary>[a-z0-9].*)",
)
TRAILER = re.compile(r"^[A-Za-z0-9-]+:[ \t]+\S")
FOOTER = re.compile(
    r"^\W*(?:co-authored-by|signed-off-by|generated (?:with|by))\b",
    re.IGNORECASE,
)
SQUASH_SUFFIX = re.compile(r" \(#[1-9]\d*\)$")
ISSUE = re.compile(
    r"(?<!\w)(?:[\w.-]+/[\w.-]+)?#[1-9]\d*\b|https?://github\.com/[^\s/]+/[^\s/]+/(?:issues|pull)/\d+\b",
)


def message_findings(message, path):
    lines = message.splitlines() or [""]
    lines[0] = SQUASH_SUFFIX.sub("", lines[0], count=1)
    subject = lines[0]
    findings = []
    match = SUBJECT.fullmatch(subject)
    if not match:
        findings.append(
            Finding(
                path,
                1,
                "EN-07.2",
                "subject must be <area>: <summary>, opening lowercase",
            ),
        )
    if len(subject) > 72 or subject.endswith("."):
        findings.append(
            Finding(
                path,
                1,
                "EN-07.2",
                "subject must be at most 72 characters with no final full stop",
            ),
        )
    if len(lines) > 1 and lines[1].strip():
        findings.append(
            Finding(path, 2, "EN-07.3", "subject and body require a blank line"),
        )
    body = "\n".join(lines[2:]).strip()
    final_start = len(lines)
    if body:
        final_start = len(lines) - 1
        while final_start > 1 and not lines[final_start].strip():
            final_start -= 1
        while final_start > 1 and lines[final_start - 1].strip():
            final_start -= 1
    for number, line in enumerate(lines, 1):
        if ISSUE.search(line):
            findings.append(
                Finding(
                    path,
                    number,
                    "EN-07.4",
                    "issue reference belongs in the pull request",
                ),
            )
        if number > 1 and (
            FOOTER.search(line)
            or (body and number > final_start and TRAILER.search(line))
        ):
            findings.append(
                Finding(
                    path,
                    number,
                    "EN-07.4",
                    "trailer or attribution line is forbidden",
                ),
            )
    return findings


def resolve(repo, revision):
    if not isinstance(revision, str) or not revision or revision.startswith("-"):
        raise CannotRunError(f"invalid commit endpoint: {revision!r}")
    return repo.git(
        "rev-parse",
        "--verify",
        "--end-of-options",
        revision + "^{commit}",
    ).strip()


def local_selection(repo):
    branch = repo.git("branch", "--show-current").strip()
    upstream = (
        repo.git("for-each-ref", "--format=%(upstream)", "refs/heads/" + branch).strip()
        if branch
        else ""
    )
    if upstream:
        return upstream + "..HEAD"
    return "origin/main..HEAD" if repo.git("remote").strip() else None


def payload_field(data, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise CannotRunError("event payload is missing " + ".".join(keys))
        current = current[key]
    if not isinstance(current, str) or not current:
        raise CannotRunError(
            "event payload field must be a nonempty string: " + ".".join(keys),
        )
    return current


def event_selection(repo, env):
    """Select event endpoints, or return None when the event introduces no commits."""
    event = env["GITHUB_EVENT_NAME"]
    if event in NO_COMMIT_EVENTS:
        return None
    if event not in {"pull_request", "push"}:
        raise CannotRunError(f"unsupported commit range event: {event}")
    location = env.get("GITHUB_EVENT_PATH")
    if not location:
        raise CannotRunError("GITHUB_EVENT_PATH is required for event ranges")
    data = json.loads(read(Path(location)))
    if event == "pull_request":
        return (
            payload_field(data, "pull_request", "base", "sha")
            + ".."
            + payload_field(data, "pull_request", "head", "sha"),
            "HEAD",
        )
    before = payload_field(data, "before")
    head = env.get("GITHUB_SHA") or payload_field(data, "after")
    if not re.fullmatch(r"0{40}|0{64}", before):
        return before + ".." + head, "HEAD"
    default = payload_field(data, "repository", "default_branch")
    branch = payload_field(data, "ref")
    if branch == "refs/heads/" + default:
        return None, head
    base = repo.git(
        "merge-base",
        resolve(repo, "origin/" + default),
        resolve(repo, head),
    ).strip()
    return base + ".." + head, "HEAD"


def selected_commits(repo, selection, root_head="HEAD"):
    if selection is None:
        tip = resolve(repo, root_head)
    else:
        parts = selection.split("..")
        if len(parts) != 2 or not all(parts) or "..." in selection:
            raise CannotRunError("expected a two-endpoint BASE..HEAD range")
        base, head = (resolve(repo, part) for part in parts)
        tip = base + ".." + head
    commits = repo.git("rev-list", "--reverse", tip).splitlines()
    if commits and repo.git("rev-parse", "--is-shallow-repository").strip() == "true":
        raise CannotRunError(
            "shallow history cannot prove the selected range; fetch full history",
        )
    return commits


def check_commit(repo, sha):
    message = repo.git("show", "--no-patch", "--format=%B", sha)
    return message_findings(message, sha)


class Commits(Always):
    name = "commits"
    group = "standards"
    rules = ("EN-07.2", "EN-07.3", "EN-07.4")

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py commits")
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument("--range")
        selection.add_argument("--root", action="store_true")
        args = parser.parse_args(argv)
        root_head = "HEAD"
        if args.root:
            selected = None
        elif args.range is not None:
            selected = args.range
        elif os.environ.get("GITHUB_EVENT_NAME"):
            event_range = event_selection(repo, os.environ)
            if event_range is None:
                return Result.ok(
                    f"{os.environ['GITHUB_EVENT_NAME']} introduces no commits; "
                    "ranges are checked on push and pull_request",
                )
            selected, root_head = event_range
        else:
            selected = local_selection(repo)
        commits = selected_commits(repo, selected, root_head)
        findings = []
        for sha in commits:
            findings.extend(check_commit(repo, sha))
        return verdict(
            "EN-07.2",
            findings,
            f"{len(commits)} commits pending; checked every selected commit",
        )
