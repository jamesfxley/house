# SPDX-License-Identifier: MIT
"""Compare copied root files and the workflow with their pinned sources (AR-3)."""

from pathlib import Path

from house.api import Finding
from house.gates.common import Always, no_args, verdict
from house.sync import generated
from house.workflow import WORKFLOW, render


class SyncedFiles(Always):
    name = "synced-files"
    group = "standards"
    rules = ("EN-05.1",)

    def run(self, repo, argv):
        no_args(argv)
        tracked = set(repo.tracked())
        output = {**generated(repo), WORKFLOW: render(repo)}
        findings = []
        for name, content in output.items():
            if Path(name) not in tracked:
                message = "synced file is not tracked; run dev.py sync and git add"
            elif repo.read(name) != content:
                message = "synced copy differs; run dev.py sync"
            else:
                continue
            findings.append(Finding(name, 0, "EN-05.1", message))
        return verdict("EN-05.1", findings, f"{len(output)} synced files checked")
