# SPDX-License-Identifier: MIT
"""Render declared group preparation as workflow steps, never locally (AR-16)."""

import re

import pytest

from house.api import Repo
from house.config import load, validate
from house.core import CannotRunError
from house.gates.synced_files import SyncedFiles
from house.runner import execute
from house.workflow import WORKFLOW, model, render

PREPARE = ["python3 infra/family.py prepare"]


def raw(prepare):
    ci = {"require": [{"group": "standards", "prepare": prepare}]}
    return {"house": {"platform": ".", "languages": ["python"]}, "ci": ci}


def test_valid_commands_are_kept_in_order():
    commands = ["python3 a.py", "python3 b.py --flag 'quoted value'"]
    assert validate(raw(commands))["ci"]["require"][0]["prepare"] == commands


@pytest.mark.parametrize(
    ("prepare", "expected"),
    [
        ([], "at least one command"),
        ("python3 a.py", "expected an array of strings"),
        ([" "], "nonempty string"),
        (["python3 a.py\nrm -rf ."], "single-line"),
        (["python3 a.py", "python3 a.py"], "duplicate values"),
    ],
)
def test_invalid_preparation_is_refused(prepare, expected):
    with pytest.raises(CannotRunError, match=re.escape("ci.require.prepare")):
        validate(raw(prepare))
    with pytest.raises(CannotRunError, match=re.escape(expected)):
        validate(raw(prepare))


def declare(repo, prepare=None):
    requirement = {"group": "standards"}
    if prepare is not None:
        requirement["prepare"] = prepare
    repo.config["ci"]["require"] = [requirement]


def test_steps_follow_tool_preparation_in_the_selected_group_only(repo):
    declare(repo, PREPARE)
    jobs = model(repo)["jobs"]
    names = [step.get("name") for step in jobs["check_standards"]["steps"]]
    assert names[1:4] == [
        "Prepare declared tools",
        "Prepare standards input 1",
        "Check standards",
    ]
    assert jobs["check_standards"]["steps"][2]["run"] == PREPARE[0]
    for name, job in jobs.items():
        if name != "check_standards":
            assert all(
                not str(step.get("name", "")).startswith("Prepare standards input")
                for step in job["steps"]
            )


def test_omitted_preparation_preserves_existing_output(repo):
    declare(repo)
    before = render(repo)
    declare(repo, PREPARE)
    assert render(repo) != before
    declare(repo)
    assert render(repo) == before


def test_coverage_accepts_and_then_refuses_an_edited_step(repo, write):
    declare(repo, PREPARE)
    write(WORKFLOW, render(repo))
    result = execute(repo, SyncedFiles()).result
    assert result.status == 0, result
    text = repo.read(WORKFLOW)
    assert PREPARE[0] in text
    for edited in (
        text.replace(PREPARE[0], "python3 infra/family.py prepare --skip"),
        "\n".join(row for row in text.splitlines() if PREPARE[0] not in row) + "\n",
    ):
        write(WORKFLOW, edited)
        result = execute(repo, SyncedFiles()).result
        assert result.status == 1
        assert "synced copy differs" in result.findings[0].message
    write(WORKFLOW, render(repo))
    assert execute(repo, SyncedFiles()).result.status == 0


def test_family_preparation_renders_and_repository_group_replaces_it(repo, write):
    """Family CI rows inherit and repository rows replace by group (AR-16, AR-18)."""
    repository = 'family = "infra"\n[house]\nplatform = "."\nlanguages = ["python"]\n'
    write("house.toml", repository)
    write(
        "infra/family.toml",
        """[[ci.require]]
group = "lint"
prepare = ["python3 dev.py build", "python3 dev.py gate build-warnings"]
""",
    )
    inherited = Repo(repo.root, load(repo.root))
    steps = model(inherited)["jobs"]["check_lint"]["steps"]
    assert steps[2:4] == [
        {"name": "Prepare lint input 1", "run": "python3 dev.py build"},
        {"name": "Prepare lint input 2", "run": "python3 dev.py gate build-warnings"},
    ]
    write(
        "house.toml",
        repository + """[[ci.require]]
group = "lint"
prepare = ["python3 local.py build"]
""",
    )
    overridden = Repo(repo.root, load(repo.root))
    steps = model(overridden)["jobs"]["check_lint"]["steps"]
    assert steps[2:4] == [
        {"name": "Prepare lint input 1", "run": "python3 local.py build"},
        {"name": "Check lint", "run": "python3 dev.py check --ci --group lint"},
    ]
    assert "python3 dev.py build" not in render(overridden)
    assert "python3 dev.py gate build-warnings" not in render(overridden)
