# SPDX-License-Identifier: MIT
"""Render per-group container options as data, never as a command (AR-15)."""

import re

import pytest

from house.config import validate
from house.core import CannotRunError
from house.gates.synced_files import SyncedFiles
from house.runner import execute
from house.workflow import WORKFLOW, model, render

IMAGE = "example.invalid/tools:0.1"
OPTIONS = "--user root --security-opt seccomp=unconfined"


def raw(options, *, image=True):
    ci = {"require": [{"group": "standards", "container_options": options}]}
    if image:
        ci["container"] = IMAGE
    return {"house": {"platform": ".", "languages": ["python"]}, "ci": ci}


@pytest.mark.parametrize("options", [OPTIONS, '--env "VALUE=a b"'])
def test_valid_options_are_kept_verbatim(options):
    config = validate(raw(options))
    assert config["ci"]["require"][0]["container_options"] == options


@pytest.mark.parametrize(
    ("options", "image", "expected"),
    [
        (OPTIONS, False, "requires ci.container"),
        (" ", True, "nonempty string"),
        ([], True, "nonempty string"),
        ("--user\nroot", True, "single-line"),
        ('--env "bad', True, "malformed quoting"),
        ("--network host", True, "does not support"),
        ("--network=host", True, "does not support"),
        ("--entrypoint=/bin/sh", True, "does not support"),
    ],
)
def test_invalid_options_are_refused(options, image, expected):
    with pytest.raises(CannotRunError, match=re.escape("ci.require.container_options")):
        validate(raw(options, image=image))
    with pytest.raises(CannotRunError, match=re.escape(expected)):
        validate(raw(options, image=image))


def declare(repo, options=None):
    repo.config["ci"]["container"] = IMAGE
    requirement = {"group": "lint"}
    if options is not None:
        requirement["container_options"] = options
    repo.config["ci"]["require"] = [requirement]


def test_options_apply_only_to_the_selected_group(repo):
    declare(repo, OPTIONS)
    jobs = model(repo)["jobs"]
    assert jobs["check_lint"]["container"] == {"image": IMAGE, "options": OPTIONS}
    for name, job in jobs.items():
        if name != "check_lint":
            assert job["container"] == {"image": IMAGE}


def test_omitted_options_preserve_existing_output(repo):
    declare(repo)
    before = render(repo)
    declare(repo, OPTIONS)
    with_options = render(repo)
    declare(repo)
    assert render(repo) == before
    assert "options" not in before
    assert with_options != before


def test_coverage_refuses_a_changed_or_removed_option(repo, write):
    declare(repo, OPTIONS)
    write(WORKFLOW, render(repo))
    assert execute(repo, SyncedFiles()).result.status == 0
    text = repo.read(WORKFLOW)
    line = f'"options": "{OPTIONS}"'
    assert line in text
    for edited in (
        "\n".join(row for row in text.splitlines() if line not in row) + "\n",
        text.replace("seccomp=unconfined", "seccomp=default"),
    ):
        write(WORKFLOW, edited)
        result = execute(repo, SyncedFiles()).result
        assert result.status == 1
        assert "synced copy differs" in (
            result.findings[0].message
        )
    write(WORKFLOW, render(repo))
    assert execute(repo, SyncedFiles()).result.status == 0


def test_options_without_a_resolved_image_cannot_render(repo):
    declare(repo, OPTIONS)
    del repo.config["ci"]["container"]
    with pytest.raises(CannotRunError, match="requires a resolved container image"):
        model(repo)


def test_container_user_applies_to_every_job_including_group_options(repo):
    # AR-15: family-wide user survives repository replacement of require rows.
    declare(repo, "--security-opt seccomp=unconfined")
    repo.config["ci"]["container_user"] = "0"
    for name, job in model(repo)["jobs"].items():
        expected = "--user 0"
        if name == "check_lint":
            expected = "--security-opt seccomp=unconfined " + expected
        assert job["container"] == {"image": IMAGE, "options": expected}


def test_container_user_is_validated_independently_of_image_selection():
    # AR-15: the family can declare the user before a registry digest is set.
    data = {"house": {"platform": ".", "languages": ["python"]},
            "ci": {"container_user": "0"}}
    assert validate(data)["ci"]["container_user"] == "0"
    for value in ("", "--privileged", "0\n", 0):
        data["ci"]["container_user"] = value
        with pytest.raises(CannotRunError, match=re.escape("ci.container_user")):
            validate(data)


def test_container_user_without_an_image_leaves_jobs_on_the_runner(repo):
    # AR-15: declaring the user does not select an image.
    repo.config["ci"]["container_user"] = "0"
    assert all("container" not in job for job in model(repo)["jobs"].values())
