# SPDX-License-Identifier: MIT
"""Copied root files and generated workflows stay exact (AR-3, AR-10)."""

from house.gates.synced_files import SyncedFiles
from house.sync import sync
from house.workflow import WORKFLOW, render
from tests.test_standards import assert_fault, assert_pass


def test_synced_files_fault_repair_missing_and_line_endings(repo, write):
    write("house/launcher/dev.py", "# Canonical\n")
    repo.config["sync"]["files"] = ["dev.py", WORKFLOW]
    write("dev.py", "# Edited\n")
    write(WORKFLOW, render(repo))
    assert_fault(repo, SyncedFiles(), "synced copy differs")
    sync(repo)
    assert_pass(repo, SyncedFiles())
    write("dev.py", b"# Canonical\r\n")
    assert_fault(repo, SyncedFiles(), "synced copy differs")
    sync(repo)
    repo.git("add", "dev.py")
    repo.git("rm", "--cached", "dev.py")
    assert_fault(repo, SyncedFiles(), "synced file is not tracked")


def test_workflow_is_compared_even_when_not_in_sync_files(repo, write):
    write(WORKFLOW, render(repo) + "# Edited\n")
    assert_fault(repo, SyncedFiles(), "synced copy differs")
    write(WORKFLOW, render(repo))
    assert_pass(repo, SyncedFiles())
