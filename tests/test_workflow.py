# SPDX-License-Identifier: MIT
"""Prove rendered CI covers jobs, matrices and unavailable tools (AR-10)."""

import json
from pathlib import Path

import pytest

from house.gates.format import Format
from house.gates.synced_files import SyncedFiles
from house.runner import execute
from house.sync import sync
from house.workflow import CHECKOUT, WORKFLOW, model, render
from tests.conftest import git


@pytest.fixture
def online(repo, write):
    write("weekly_fixture.py", """from house.api import Result
class Weekly:
    name = "weekly-sample"
    group = "online"
    def applies(self, repo):
        return True
    def run(self, repo, argv):
        return Result.ok()
GATE = Weekly()
""")
    repo.config["gates"] = [
        {"name": "weekly-sample", "module": "weekly_fixture", "group": "online"},
    ]
    return repo


def generated(repo, write):
    write(WORKFLOW, render(repo))
    entry = execute(repo, SyncedFiles())
    assert entry.result.status == 0, entry.result
    assert "synced files checked" in entry.result.message


def test_python_only_has_no_empty_cpp_jobs(repo, write):
    generated(repo, write)
    jobs = model(repo)["jobs"]
    assert {"check_standards", "check_lint"} == set(jobs)
    assert not repo.config["ci"]["skip"]
    checkout = jobs["check_standards"]["steps"][0]
    assert checkout == {
        "uses": CHECKOUT,
        "with": {
            "fetch-depth": 0, "submodules": "recursive", "persist-credentials": False,
        },
    }
    assert len(CHECKOUT.split("@")[1]) == 40
    assert model(repo)["on"] == {
        "push": {},
        "pull_request": {},
        "workflow_dispatch": {},
        "repository_dispatch": {},
    }


def test_markdown_only_has_no_source_lint_job(repo, write):
    repo.config["house"]["languages"] = ["markdown"]
    generated(repo, write)
    assert "check_lint" not in model(repo)["jobs"]


def test_declared_cxx_jobs_remain_when_tools_unavailable(repo, write, monkeypatch):
    repo.config["house"]["languages"].append("cxx")
    monkeypatch.setenv("CLANG_FORMAT", str(repo.root / "absent-clang-format"))
    write("sample.cpp", "int main() { return 0; }\n")
    generated(repo, write)
    assert {"check_format", "check_build", "check_docs", "check_consumer"} <= set(
        model(repo)["jobs"],
    )
    # A missing executable is unavailable, never an N/A gate or absent CI job.
    write("config/.clang-version", "20\n")
    entry = execute(repo, Format(), ci=True)
    assert entry.result.status == 2
    assert (
        "cannot read" in entry.result.message
        or "cannot execute" in entry.result.message
    )


@pytest.mark.parametrize("fault", ["online", "consumer", "board", "profile", "edit"])
def test_workflow_tampering_fails_with_expected_finding(online, write, fault):
    repo = online
    repo.config["house"]["languages"].append("cxx")
    repo.config["ci"]["require"] = [
        {
            "group": "build",
            "matrix": {"board": ["alpha", "beta"], "profile": ["host", "cross"]},
        },
        {"group": "online", "schedule": "weekly"},
    ]
    generated(repo, write)
    text = repo.read(WORKFLOW)
    if fault in {"online", "consumer"}:
        text = text.replace('"check_' + fault + '":', '"removed_' + fault + '":')
    elif fault == "board":
        text = text.replace('      - "beta"\n', "")
    elif fault == "profile":
        text = text.replace('      - "cross"\n', "")
    else:
        text += "# Manual change\n"
    assert text != repo.read(WORKFLOW)
    write(WORKFLOW, text)
    entry = execute(repo, SyncedFiles())
    assert entry.result.status == 1
    assert entry.result.findings[0].rule == "EN-05.1"
    assert (
        "synced copy differs"
        in entry.result.findings[0].message
    )
    write(WORKFLOW, render(repo))
    assert execute(repo, SyncedFiles()).result.status == 0


def test_matrix_schedule_and_container_inputs_are_rendered(online, write):
    repo = online
    repo.config["house"]["languages"].append("cxx")
    repo.config["ci"].update(
        {
            "container": "devcontainer",
            "require": [
                {
                    "group": "build",
                    "matrix": {
                        "compiler": ["gcc", "clang"],
                        "build_type": ["Debug", "Release"],
                    },
                },
                {"group": "online", "schedule": "weekly"},
            ],
        },
    )
    write("config/.clang-version", "20\n")
    write(
        ".devcontainer/devcontainer.json",
        json.dumps({"image": "example.invalid/tools:0.1"}),
    )
    generated(repo, write)
    data = model(repo)
    assert data["on"]["schedule"] == [{"cron": "17 3 * * 1"}]
    build = data["jobs"]["check_build"]
    assert build["strategy"]["matrix"]["compiler"] == ["gcc", "clang"]
    assert build["env"]["BUILD_TYPE"] == "${{ matrix.build_type }}"
    assert "clang++-20" in build["env"]["CXX"]
    assert "gcc" in build["env"]["CC"]
    assert build["container"]["image"] == "example.invalid/tools:0.1"
    assert "workflow_dispatch" in data["jobs"]["check_online"]["if"]
    assert data["jobs"]["check_online"]["env"]["GH_TOKEN"].startswith("${{")


def test_tests_are_owned_and_python_only(repo, write):
    write("tests/test_sample.py", "# Synthetic tests\n")
    steps = model(repo)["jobs"]["check_standards"]["steps"]
    assert steps[-1]["run"] == "python3 dev.py toolchain run pytest -W error"
    assert "--profile platform-tests" in steps[1]["run"]
    repo.config["house"]["platform"] = "platform"
    steps = model(repo)["jobs"]["check_standards"]["steps"]
    assert "--profile tests" in steps[1]["run"]
    git(repo.root, "rm", "--cached", "tests/test_sample.py")
    assert len(model(repo)["jobs"]["check_standards"]["steps"]) == 3


@pytest.mark.parametrize(
    "case", ["group", "matrix", "container", "unreadable", "unindexed"],
)
def test_invalid_or_unavailable_workflow_inputs_cannot_pass(repo, write, case):
    generated(repo, write)
    if case == "group":
        repo.config["ci"]["require"] = [{"group": "format"}]
        expected = "no applicable obligations"
    elif case == "matrix":
        repo.config["house"]["languages"].append("cxx")
        repo.config["ci"]["require"] = [
            {"group": "build", "matrix": {"compiler": ["other"]}},
        ]
        expected = "supports gcc and clang"
    elif case == "container":
        repo.config["ci"]["container"] = "devcontainer"
        write(".devcontainer/devcontainer.json", '{"build": "Dockerfile"}')
        expected = "explicit image"
    elif case == "unindexed":
        git(repo.root, "rm", "--cached", WORKFLOW)
        expected = "synced file is not tracked"
    else:
        (repo.root / WORKFLOW).write_bytes(b"\xff")
        expected = "cannot read"
    result = execute(repo, SyncedFiles()).result
    assert result.status == (1 if case == "unindexed" else 2)
    assert expected in result.message + " ".join(f.message for f in result.findings)
    assert "crashed:" not in result.message


def test_sync_renders_the_covered_workflow(repo):
    repo.config["sync"]["files"] = [WORKFLOW]
    sync(repo)
    assert (repo.root / WORKFLOW).read_text() == render(repo)
    assert sync(repo, check=True) == []
    assert Path(WORKFLOW) not in repo.tracked()


def test_distinct_custom_groups_keep_distinct_jobs(repo):
    repo.config["groups"].update({"source-lint": ["lint"], "source_lint": ["lint"]})
    jobs = model(repo)["jobs"]
    assert "check_source-lint" in jobs
    assert "check_source_lint" in jobs


@pytest.mark.parametrize("languages", [["python"], ["cxx"]])
def test_all_rendered_checkouts_and_main_concurrency_obey_policy(online, languages):
    repo = online
    repo.config["house"]["languages"] = languages
    repo.config["ci"]["require"] = [{"group": "online", "schedule": "weekly"}]
    jobs = model(repo)["jobs"]
    for job in jobs.values():
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False
        assert job["concurrency"]["cancel-in-progress"] == (
            "${{ github.ref != 'refs/heads/main' }}"
        )
    assert len({job["concurrency"]["group"] for job in jobs.values()}) == len(jobs)
    for job in jobs.values():
        assert "strategy.job-index" in job["concurrency"]["group"]
        assert "github.run_id" in job["concurrency"]["group"]


@pytest.mark.parametrize("include_online", [False, True])
def test_permissions_follow_rendered_online_job(online, include_online):
    if not include_online:
        online.config["gates"] = []
    data = model(online)
    assert data["permissions"] == {"contents": "read"}
    assert ("check_online" in data["jobs"]) == include_online
    for name, job in data["jobs"].items():
        expected = {"contents": "read"}
        if name == "check_online":
            expected.update({"issues": "read", "pull-requests": "read"})
        assert job.get("permissions", data["permissions"]) == expected


@pytest.mark.parametrize("languages", [["python"], ["cxx"]])
def test_every_rendered_job_and_step_is_non_advisory(online, languages):
    online.config["house"]["languages"] = languages
    data = model(online)
    for job in data["jobs"].values():
        assert "continue-on-error" not in job
        assert all("continue-on-error" not in step for step in job["steps"])


@pytest.mark.parametrize("path", ["tests/helper.py", "test/nested/helper.py"])
def test_python_controls_do_not_request_pytest(repo, write, path):
    write(path, "# CTest control, not a pytest test.\n")
    steps = model(repo)["jobs"]["check_standards"]["steps"]
    assert not any(step.get("name") == "Test owned Python" for step in steps)
    assert "--profile" not in steps[1]["run"]


@pytest.mark.parametrize("path", ["tests/test_unit.py", "test/nested/unit_test.py"])
def test_discovered_python_tests_request_pytest(repo, write, path):
    write(path, "def test_unit(): pass\n")
    steps = model(repo)["jobs"]["check_standards"]["steps"]
    assert any(step.get("name") == "Test owned Python" for step in steps)
    assert "--profile" in steps[1]["run"]
