# SPDX-License-Identifier: MIT
"""Keep path boundaries, retired citations and expected failures distinguishable."""

import pytest

from house.core import CannotRunError
from house.runner import Runner, execute
from tests.test_runner import Probe


@pytest.mark.parametrize("phase", ["applies", "run"])
def test_expected_cannot_run_has_no_crash_or_traceback(repo, caplog, phase):
    gate, survivor = Probe("expected"), Probe("survivor")

    def unavailable(*_args):
        raise CannotRunError("input is not available")

    setattr(gate, phase, unavailable)
    entries = Runner(repo, [gate, survivor]).run()
    assert entries[0].result.status == 2
    assert entries[0].result.message == "input is not available"
    assert entries[1].verdict == "PASS"
    assert "Traceback" not in caplog.text
    assert "crashed" not in caplog.text
    if phase == "applies":
        entries = Runner(repo, [gate, survivor]).listed()
        assert entries[0].result.status == 2
        assert entries[0].verdict == "cannot assess: input is not available"
        assert "Traceback" not in caplog.text


def test_genuine_crash_keeps_exception_and_traceback(repo):
    gate = Probe("broken")

    def crash(*_args):
        return {}["missing"]

    gate.run = crash
    entry = execute(repo, gate)
    assert entry.result.status == 2
    assert "crashed: KeyError: 'missing'" in entry.result.message
    assert "Traceback (most recent call last)" in entry.result.message
