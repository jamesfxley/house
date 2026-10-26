# SPDX-License-Identifier: MIT
"""The runner preserves verdicts, selection boundaries and strict CI skips."""

import pytest

from house.api import Finding, Result
from house.core import CannotRunError
from house.runner import Runner, exit_code


class Probe:
    rules = ("EN-01.8",)

    def __init__(self, name, group="standards", *, outcome=None, applicable=True):
        self.name = name
        self.group = group
        self.outcome = outcome if outcome is not None else Result.ok()
        self.applicable = applicable
        self.calls = 0

    def applies(self, _repo):
        return self.applicable

    def run(self, _repo, _argv):
        self.calls += 1
        return self.outcome


def test_default_all_and_explicit_selection(repo):
    offline, online = Probe("offline"), Probe("network", "online")
    runner = Runner(repo, [offline, online])
    assert exit_code(runner.run()) == 0
    assert (offline.calls, online.calls) == (1, 0)
    runner.run(all_groups=True)
    assert (offline.calls, online.calls) == (2, 1)
    runner.run(["online"])
    assert (offline.calls, online.calls) == (2, 2)


def test_unavailable_is_not_pass_and_fault_takes_precedence(repo):
    failure = Probe(
        "fault",
        outcome=Result.fail(Finding("sample.py", 1, "EN-01.8", "fault")),
    )
    missing = Probe("missing", outcome=Result.cannot_run("tool absent"))
    assert exit_code(Runner(repo, [missing]).run()) == 2
    assert exit_code(Runner(repo, [failure, missing]).run()) == 1


def test_strict_ci_skip_needs_reason_and_does_not_waive_inability(repo):
    gate = Probe("sample", applicable="no matching source")
    runner = Runner(repo, [gate])
    assert exit_code(runner.run()) == 0
    assert exit_code(runner.run(ci=True)) == 1
    repo.config["ci"]["skip"]["sample"] = "not applicable to this job"
    assert exit_code(runner.run(ci=True)) == 0
    assert gate.calls == 0
    gate.applicable = True
    gate.outcome = Result.cannot_run("cannot read input")
    assert exit_code(runner.run(ci=True)) == 2


def test_list_does_not_execute_gate(repo):
    gate = Probe("sample")
    gate.package, gate.configuration = "example", "safe"
    (entry,) = Runner(repo, [gate]).listed()
    assert (
        entry.name,
        entry.group,
        entry.package,
        entry.configuration,
        entry.verdict,
    ) == (
        "sample",
        "standards",
        "example",
        "safe",
        "applicable",
    )
    assert gate.calls == 0


@pytest.mark.parametrize("groups", [["unknown"], ["lint"], ["standards", "lint"]])
def test_unknown_or_empty_requested_group_is_not_green(repo, groups):
    with pytest.raises(CannotRunError):
        Runner(repo, [Probe("sample")]).run(groups)


def test_invalid_gate_contract_is_not_green(repo):
    gate = Probe("sample", applicable=False)
    assert exit_code(Runner(repo, [gate]).run()) == 2
    assert exit_code(Runner(repo, [gate]).listed()) == 2
    gate.applicable = True
    gate.outcome = object()
    assert exit_code(Runner(repo, [gate]).run()) == 2


def test_duplicate_gates_refused(repo):
    with pytest.raises(CannotRunError, match="duplicate"):
        Runner(repo, [Probe("same"), Probe("same")])


def test_custom_group_alias_runs_once(repo):
    repo.config["groups"]["audit"] = ["sample"]
    gate = Probe("sample")
    Runner(repo, [gate]).run(["audit", "standards"])
    assert gate.calls == 1


@pytest.mark.parametrize("phase", ["applies", "run"])
@pytest.mark.parametrize("error", [KeyError("missing"), AttributeError("bad"),
                                  AssertionError("broken")])
def test_gate_crashes_report_traceback_and_continue(repo, phase, error):
    gate, survivor = Probe("broken"), Probe("survivor")

    def crash(*_args):
        raise error

    setattr(gate, phase, crash)
    entries = Runner(repo, [gate, survivor]).run()
    assert exit_code(entries) == 2
    assert entries[0].verdict == "CANNOT_RUN"
    assert f"crashed: {type(error).__name__}:" in entries[0].result.message
    assert "Traceback (most recent call last)" in entries[0].result.message
    assert entries[1].verdict == "PASS"
    assert survivor.calls == 1
    if phase == "applies":
        listed = Runner(repo, [gate, survivor]).listed()
        assert exit_code(listed) == 2
        assert "crashed:" in listed[0].verdict
        assert listed[1].verdict == "applicable"


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(7)])
@pytest.mark.parametrize("phase", ["applies", "run"])
def test_process_control_exceptions_propagate(repo, phase, error):
    gate = Probe("stop")

    def interrupt(*_args):
        raise error

    setattr(gate, phase, interrupt)
    with pytest.raises(type(error)):
        Runner(repo, [gate]).run()


def test_undeclared_provider_is_not_a_skip_or_ci_obligation(repo):
    gate = Probe("cpp", "format", applicable="tool missing")
    gate.provider = "cxx"
    runner = Runner(repo, [gate])
    (entry,) = runner.run(ci=True)
    assert entry.verdict == "N/A"
    assert entry.result.message == "cxx not declared"
    assert exit_code((entry,)) == 0
    assert runner.listed()[0].verdict == "n/a: cxx not declared"
    assert runner.applicable_gates() == ()
    assert gate.calls == 0
    repo.config["house"]["languages"].append("cxx")
    assert runner.applicable_gates() == (gate,)
    assert runner.run(ci=True)[0].verdict == "SKIP"
    assert exit_code(runner.run(ci=True)) == 1
    gate.applicable = True
    gate.outcome = Result.cannot_run("clang-format is not installed")
    (entry,) = runner.run(ci=True)
    assert entry.verdict == "CANNOT_RUN"
    assert "clang-format is not installed" in entry.result.message
    assert exit_code((entry,)) == 2


def test_undeclared_provider_does_not_evaluate_applicability(repo):
    gate = Probe("cpp")
    gate.provider = "cxx"

    def crash(_repo):
        raise AssertionError("an undeclared provider must not be probed")

    gate.applies = crash
    assert Runner(repo, [gate]).listed()[0].verdict == "n/a: cxx not declared"
    assert exit_code(Runner(repo, [gate]).run(ci=True)) == 0
