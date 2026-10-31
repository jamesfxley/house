# SPDX-License-Identifier: MIT
"""Check all branch commits, empty ranges, event selection and missing history."""

import json
import subprocess

import pytest

from house.api import Repo
from house.config import validate
from house.core import CannotRunError
from house.gates.commits import (
    Commits,
    event_selection,
    message_findings,
    selected_commits,
)
from house.runner import Runner, execute
from tests.conftest import commit, git
from tests.test_standards import assert_pass


@pytest.mark.parametrize(
    "message",
    [
        "tests: update the fixture (#12)",
        "tests: " + "x" * 65 + " (#123)",
    ],
)
def test_squash_suffix_is_neither_subject_nor_issue_reference(message):
    assert message_findings(message, "message") == []


@pytest.mark.parametrize(
    ("message", "finding"),
    [
        ("tests: Uppercase", "opening lowercase"),
        ("tests: complete.", "no final full stop"),
        ("tests: " + "x" * 70, "at most 72"),
        ("tests: update\nbody without separator", "blank line"),
        ("tests: update\n\nCo-authored-by: Example <a@example.invalid>", "trailer"),
        ("tests: update\n\nAudit-Token: any new trailer", "trailer"),
        ("tests: update\n\nGenerated with an assistant", "attribution"),
        ("tests: handle #12", "issue reference"),
        ("tests: handle #12 (#13)", "issue reference"),
        ("tests: update (#12)\n\nSee (#12)", "issue reference"),
        ("tests: update(#12)", "issue reference"),
        ("tests: update\n\nSee owner/sample#12.", "issue reference"),
        (
            "tests: update\n\nhttps://github.com/owner/sample/issues/12",
            "issue reference",
        ),
    ],
)
def test_message_negative_controls(message, finding):
    findings = message_findings(message, "message")
    assert any(finding in row.message for row in findings), findings
    assert (
        message_findings(
            "tests: update the fixture\n\nEstablish EN-07.2.",
            "message",
        )
        == []
    )




def test_root_and_branch_commits_including_bypass(repo, write):
    write("src/queue/item.py", "value = 1\n")
    first = commit(repo.root, "queue: create the fixture")
    assert_pass(repo, Commits(), ("--root",))
    git(repo.root, "checkout", "-qb", "work")
    write("src/queue/item.py", "value = 2\n")
    second = commit(repo.root, "tests: Bypass the policy")
    entry = execute(repo, Commits(), ("--range", first + "..HEAD"))
    assert entry.result.status == 1
    assert any(
        row.path == second and "opening lowercase" in row.message
        for row in entry.result.findings
    )
    write("src/queue/item.py", "value = 3\n")
    commit(repo.root, "queue: restore a valid subject")
    # A valid tip must never hide an invalid branch commit before it.
    entry = execute(repo, Commits(), ("--range", first + "..HEAD"))
    assert entry.result.status == 1
    assert any(row.path == second for row in entry.result.findings)


def test_clean_clone_simulated_push_and_next_commit(repo, write, tmp_path):
    write("tests/item.txt", "first\n")
    commit(repo.root)
    clone = tmp_path / "clone"
    git(repo.root, "clone", "--quiet", "--no-local", str(repo.root), str(clone))
    git(clone, "config", "user.name", "Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    cloned = Repo(clone, validate({"house": {"platform": "."}}))
    result = execute(cloned, Commits()).result
    assert result.status == 0
    assert "0 commits pending" in result.message
    (clone / "tests/item.txt").write_text("second\n")
    sha = commit(clone)
    assert_pass(cloned, Commits())
    git(clone, "update-ref", "refs/remotes/origin/main", sha)
    result = execute(cloned, Commits()).result
    assert result.status == 0
    assert "0 commits pending" in result.message
    git(clone, "branch", "--unset-upstream")
    assert_pass(cloned, Commits())


def test_empty_and_unresolved_ranges(repo, write):
    write("tests/item.txt", "first\n")
    commit(repo.root)
    entry = execute(repo, Commits(), ("--range", "HEAD..HEAD"))
    assert entry.result.status == 0
    assert "0 commits pending" in entry.result.message
    entry = execute(repo, Commits(), ("--range", "missing..HEAD"))
    assert entry.result.status == 2
    assert "rev-parse" in entry.result.message
    assert "crashed" not in entry.result.message




def history(repo, write):
    write("tests/one.txt", "one\n")
    base = commit(repo.root)
    write("tests/two.txt", "two\n")
    head = commit(repo.root)
    git(repo.root, "update-ref", "refs/remotes/origin/main", base)
    return base, head


@pytest.mark.parametrize(
    "event",
    ["pull_request", "push", "initial-main", "initial-branch"],
)
def test_event_payload_ranges(repo, write, event):
    base, head = history(repo, write)
    data = {
        "repository": {"default_branch": "main"},
        "ref": "refs/heads/main",
        "before": base,
        "after": head,
        "pull_request": {"base": {"sha": base}, "head": {"sha": head}},
    }
    if event.startswith("initial"):
        data["before"] = "0" * 40
        if event == "initial-branch":
            data["ref"] = "refs/heads/work"
    path = write("event.json", json.dumps(data))
    env = {
        "GITHUB_EVENT_NAME": "pull_request" if event == "pull_request" else "push",
        "GITHUB_EVENT_PATH": str(path),
        "GITHUB_SHA": head,
    }
    selection, root_head = event_selection(repo, env)
    found = selected_commits(repo, selection, root_head)
    assert found == ([base, head] if event == "initial-main" else [head])


def test_initial_main_uses_payload_tip_not_current_head(repo, write):
    base, head = history(repo, write)
    data = {
        "repository": {"default_branch": "main"},
        "ref": "refs/heads/main",
        "before": "0" * 40,
        "after": base,
    }
    path = write("event.json", json.dumps(data))
    selection, root_head = event_selection(
        repo,
        {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_EVENT_PATH": str(path),
            "GITHUB_SHA": base,
        },
    )
    assert selected_commits(repo, selection, root_head) == [base]
    assert head not in selected_commits(repo, selection, root_head)


def test_unreadable_event_payload(repo, write):
    path = write("event.json", b"\xff")
    with pytest.raises(CannotRunError, match="cannot read"):
        event_selection(
            repo,
            {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(path)},
        )


def test_shallow_checkout_cannot_prove_missing_base(repo, write, tmp_path):
    base, _head = history(repo, write)
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth=1", repo.root.as_uri(), str(clone)],
        check=True,
    )
    shallow = Repo(clone, repo.config)
    entry = execute(shallow, Commits(), ("--range", base + "..HEAD"))
    assert entry.result.status == 2
    assert "rev-parse" in entry.result.message
    entry = execute(shallow, Commits(), ("--root",))
    assert entry.result.status == 2
    assert "shallow history" in entry.result.message
    entry = execute(shallow, Commits(), ("--range", "HEAD..HEAD"))
    assert entry.result.status == 0
    assert "0 commits pending" in entry.result.message


@pytest.mark.parametrize(
    "line",
    ["Audit-Token: custom metadata", "🤖 Generated with a helper"],
)
def test_trailer_spacing_and_tool_footer(line):
    findings = message_findings("tests: update\n\n" + line, "message")
    assert any(item.rule == "EN-07.4" for item in findings)


@pytest.mark.parametrize(
    "event", ["schedule", "workflow_dispatch", "repository_dispatch"],
)
def test_events_without_new_commits_pass_strict_ci_without_a_payload(
    repo, monkeypatch, event,
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    entry = Runner(repo, [Commits()]).run(ci=True)[0]
    assert entry.result.status == 0, entry.result
    assert entry.verdict == "PASS"
    assert entry.result.message == (
        event + " introduces no commits; ranges are checked on push and pull_request"
    )
    assert entry.result.findings == ()


def test_unrecognised_event_still_cannot_run(repo, write, monkeypatch):
    path = write("event.json", "{}")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "merge_group")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    entry = execute(repo, Commits())
    assert entry.result.status == 2
    assert entry.result.message == "unsupported commit range event: merge_group"
    assert entry.verdict == "CANNOT_RUN"


@pytest.mark.parametrize(
    "event", ["schedule", "workflow_dispatch", "repository_dispatch"],
)
@pytest.mark.parametrize("selection", ["root", "range"])
def test_explicit_selection_still_checks_commits_for_no_commit_events(
    repo,
    write,
    monkeypatch,
    event,
    selection,
):
    write("tests/item.txt", "first\n")
    base = commit(repo.root)
    write("tests/item.txt", "second\n")
    bad = commit(repo.root, "tests: Bypass the hook")
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    argv = ("--root",) if selection == "root" else ("--range", base + "..HEAD")
    entry = execute(repo, Commits(), argv)
    assert entry.result.status == 1
    assert any(
        row.path == bad and "opening lowercase" in row.message
        for row in entry.result.findings
    )


def test_format_does_not_derive_area_or_branch_policy(repo, write):
    write("x.txt", "fixture\n")
    commit(repo.root, "unrelated: accept a valid message")
    git(repo.root, "switch", "-c", "feature/Uppercase")
    assert_pass(repo, Commits(), ("--root",))


@pytest.mark.parametrize(
    "sentence",
    [
        "Two cases remain: the parser and the docs.",
        "The root cause is simple: a stale path.",
    ],
)
@pytest.mark.parametrize("final", [False, True])
def test_prose_colons_are_not_trailers(sentence, final):
    body = sentence if final else sentence + "\n\nEstablish EN-07.3."
    assert message_findings("tests: explain the change\n\n" + body, "message") == []


@pytest.mark.parametrize("line", ["Reviewed-by: Sample Person", "Signed-off-by: x"])
def test_final_paragraph_trailers_are_refused(line):
    findings = message_findings("tests: update\n\n" + line, "message")
    assert any("trailer" in item.message for item in findings)


@pytest.mark.parametrize("area", [".github", "house/gates", "docs"])
def test_directory_paths_are_valid_areas(area):
    assert message_findings(area + ": explain the change", "message") == []


def test_generic_trailer_shape_only_applies_to_final_body_paragraph():
    message = "tests: explain the change\n\nToken: quoted input\n\nExplain EN-07.3."
    assert message_findings(message, "message") == []
    assert message_findings("tests: explain the change\n\nToken: value", "message")
    assert message_findings("tests: explain the change\n\n2-Token: value", "message")
    assert message_findings("tests: explain the change\nToken: value", "message")


def test_absolute_or_empty_directory_areas_are_refused():
    for area in ["/house/gates", "house//gates", "house/"]:
        findings = message_findings(area + ": explain the change", "message")
        assert any(item.rule == "EN-07.2" for item in findings)


@pytest.mark.parametrize("area", [".", "-x", "/docs"])
def test_commit_areas_require_named_directory_segments(area):
    findings = message_findings(area + ": explain the change", "message")
    assert any(item.rule == "EN-07.2" for item in findings)
