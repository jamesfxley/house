# SPDX-License-Identifier: MIT
"""Verify standards fault, repair and unavailable-input verdicts (AR-4)."""

import shutil

import pytest

from house.gates.deviations import Deviations
from house.gates.doc_links import DocLinks
from house.gates.spdx import Spdx
from house.gates.synced_files import SyncedFiles
from house.runner import execute
from tests.conftest import commit, git, init


def assert_fault(repo, gate, message):
    entry = execute(repo, gate)
    assert entry.result.status == 1, entry.result
    output = entry.result.message + "\n".join(f.message for f in entry.result.findings)
    assert message in output
    assert "crashed:" not in output
    return entry


def assert_pass(repo, gate, argv=()):
    entry = execute(repo, gate, argv)
    assert entry.result.status == 0, entry.result


@pytest.mark.parametrize(
    "case",
    [
        (DocLinks(), "README.md", "[x](missing.md)\n", "# Ready\n", "broken link"),
        (
            Spdx(),
            "sample.py",
            "value = 1\n",
            "# SPDX-License-Identifier: MIT\nvalue = 1\n",
            "missing # SPDX",
        ),
    ],
)
def test_simple_gate_fault_repair_unreadable(repo, write, case):
    gate, filename, fault, repair, expected = case
    write(filename, fault)
    assert_fault(repo, gate, expected)
    write(filename, repair)
    assert_pass(repo, gate)
    write(filename, b"\xff")
    entry = execute(repo, gate)
    assert entry.result.status == 2
    assert "cannot read" in entry.result.message


@pytest.mark.parametrize(
    "target",
    ["next.md", "./next.md#topic", "/next.md?q=a", "next%20file.md", "<next file.md>"],
)
def test_links_accept_tracked_targets_and_refuse_untracked(repo, write, target):
    filename = "next file.md" if "file" in target else "next.md"
    write("README.md", f"[target]({target})\n")
    (repo.root / filename).write_text("# Target\n")
    assert_fault(repo, DocLinks(), "broken link")
    git(repo.root, "add", filename)
    assert_pass(repo, DocLinks())


def test_links_fences_references_and_scheme(repo, write):
    write(
        "README.md",
        "[ref]: missing.md\n```md\n[x](ignored.md)\n```\n[x](https://example.invalid/)\n[x](#heading)\n",
    )
    assert_fault(repo, DocLinks(), "missing.md")
    write("missing.md", "# Target\n")
    assert_pass(repo, DocLinks())


def test_links_check_contents_of_a_pin(repo, write, tmp_path):

    dependency = init(tmp_path / "dep-origin")
    (dependency / "README.md").write_text("# Dependency\n")
    commit(dependency)
    git(
        repo.root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(dependency),
        "dependency",
    )
    write("README.md", "[x](dependency/absent.md)\n")
    assert_fault(repo, DocLinks(), "dependency/absent.md")
    write("README.md", "[x](dependency/README.md)\n")
    assert_pass(repo, DocLinks())
    shutil.rmtree(repo.root / "dependency")
    entry = execute(repo, DocLinks())
    assert entry.result.status == 2
    assert "submodule missing" in entry.result.message


def test_spdx_fix_keeps_shebang_and_checks_selected_licence(repo, write):
    repo.config["house"]["licence"] = "Apache-2.0"
    path = write("sample.py", "#!/usr/bin/env python3\nvalue = 1\n")
    assert_fault(repo, Spdx(), "Apache-2.0")
    assert_pass(repo, Spdx(), ("--fix",))
    assert path.read_text().splitlines()[:2] == [
        "#!/usr/bin/env python3",
        "# SPDX-License-Identifier: Apache-2.0",
    ]
    assert_pass(repo, Spdx())


def test_cxx_spdx_uses_metadata(repo, write):
    repo.config["house"]["languages"] = ["cxx"]
    write("sample.hpp", "#pragma once\n")
    assert_fault(repo, Spdx(), "missing // SPDX")
    assert_pass(repo, Spdx(), ("--fix",))
    assert_pass(repo, Spdx())


@pytest.mark.parametrize("kind", ["deviations", "synced-files"])
def test_standard_gates_name_unreadable_tracked_inputs(repo, write, kind):
    if kind == "deviations":
        path = write("unreadable.py", b"\xff")
        gate = Deviations()
    else:
        write("house/launcher/dev.py", "# Canonical\n")
        repo.config["sync"]["files"] = ["dev.py"]
        path = write("dev.py", b"\xff")
        gate = SyncedFiles()
    result = execute(repo, gate).result
    assert result.status == 2
    assert str(path) in result.message
    assert "cannot read" in result.message
