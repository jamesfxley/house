# SPDX-License-Identifier: MIT
"""Preserve gate verdicts and unavailable evidence (AR-2, AR-7)."""

import logging
import traceback
from dataclasses import dataclass

from house.api import Gate, Repo, Result
from house.config import GROUPS
from house.core import CannotRunError


@dataclass(frozen=True)
class Entry:
    name: str
    group: str
    package: str
    configuration: str
    verdict: str
    result: Result


logger = logging.getLogger(__name__)


def describe(gate: Gate, verdict: str, result: Result) -> Entry:
    return Entry(
        gate.name,
        gate.group,
        getattr(gate, "package", "repository"),
        getattr(gate, "configuration", "default"),
        verdict,
        result,
    )


def provider_reason(repo: Repo, gate: Gate):
    """Only declared providers contribute CI obligations and rendered jobs."""
    provider = getattr(gate, "provider", None)
    if provider is None:
        return None
    owners = (provider,) if isinstance(provider, str) else provider
    if (
        not isinstance(owners, tuple)
        or not owners
        or any(not isinstance(name, str) or not name for name in owners)
    ):
        raise CannotRunError(
            f"{gate.name}: provider must be a name, names tuple or None",
        )
    if not set(owners) & set(repo.config["house"]["languages"]):
        return " or ".join(owners) + " not declared"
    return None


def applies(repo: Repo, gate: Gate):
    applicable = gate.applies(repo)
    if applicable is not True and (
        not isinstance(applicable, str) or not applicable.strip()
    ):
        raise CannotRunError(
            f"{gate.name}: applies must return True or a nonempty reason",
        )
    return applicable


def valid_result(name, result):
    if (
        not isinstance(result, Result)
        or type(result.status) is not int
        or result.status not in {0, 1, 2}
    ):
        raise CannotRunError(f"{name}: invalid gate result")
    return result


def execute(repo: Repo, gate: Gate, argv=(), *, ci=False) -> Entry:
    try:
        reason = provider_reason(repo, gate)
        if reason:
            return describe(gate, "N/A", Result.ok(reason))
        applicable = applies(repo, gate)
        if applicable is not True:
            reason = repo.config["ci"]["skip"].get(gate.name)
            code = 1 if ci and not reason else 0
            detail = applicable + (f"; CI allowance: {reason}" if reason else "")
            return describe(gate, "SKIP", Result(code, detail))
        result = valid_result(gate.name, gate.run(repo, tuple(argv)))
    except CannotRunError as error:
        result = Result.cannot_run(str(error))
    except Exception as error:
        logger.exception("gate %s crashed", gate.name)
        detail = traceback.format_exc()
        result = Result.cannot_run(
            f"crashed: {type(error).__name__}: {error}\n{detail}",
        )
    return describe(
        gate,
        {0: "PASS", 1: "FAIL", 2: "CANNOT_RUN"}[result.status],
        result,
    )


def exit_code(entries) -> int:
    codes = {entry.result.status for entry in entries}
    return 1 if 1 in codes else 2 if 2 in codes else 0


class Runner:
    def __init__(self, repo: Repo, gates):
        self.repo = repo
        self.gates = tuple(gates)
        names = [gate.name for gate in self.gates]
        if len(set(names)) != len(names):
            raise CannotRunError("duplicate registered gate name")
        self.groups = (
            *GROUPS,
            *(name for name in repo.config["groups"] if name not in GROUPS),
        )
        if any(gate.group not in self.groups for gate in self.gates):
            raise CannotRunError("registered gate has an undeclared group")

    def named(self, name):
        found = next((gate for gate in self.gates if gate.name == name), None)
        if found is None:
            names = [gate.name for gate in self.gates]
            raise CannotRunError(f"unknown gate {name!r}; registered: {names}")
        return found

    def select(self, groups=(), *, all_groups=False):
        selected = (
            list(groups)
            if groups
            else [name for name in self.groups if name != "online"]
        )
        if all_groups and "online" not in selected:
            selected.append("online")
        unknown = set(selected) - set(self.groups)
        if unknown:
            raise CannotRunError(f"unknown groups: {sorted(unknown)}")
        members = {
            member
            for group in selected
            for member in self.repo.config["groups"].get(group, [])
        }
        for group in groups:
            own_members = self.repo.config["groups"].get(group, [])
            if not any(
                gate.group == group or gate.name in own_members for gate in self.gates
            ):
                raise CannotRunError(f"no gates registered for selected group: {group}")
        found = tuple(
            gate
            for gate in self.gates
            if gate.group in selected or gate.name in members
        )
        if groups and not found:
            raise CannotRunError(f"no gates registered for selected groups: {selected}")
        return found

    def applicable_gates(self, groups=(), *, all_groups=False):
        """Exclude undeclared providers; unavailable declared gates still count."""
        return tuple(
            gate
            for gate in self.select(groups, all_groups=all_groups)
            if provider_reason(self.repo, gate) is None
        )

    def run(self, groups=(), *, all_groups=False, ci=False):
        return tuple(
            execute(self.repo, gate, ci=ci)
            for gate in self.select(groups, all_groups=all_groups)
        )

    def listed(self, groups=(), *, all_groups=False):
        entries = []
        for gate in self.select(groups, all_groups=all_groups):
            try:
                reason = provider_reason(self.repo, gate)
                if reason:
                    entries.append(describe(gate, f"n/a: {reason}", Result.ok(reason)))
                    continue
                applicable = applies(self.repo, gate)
                verdict = "applicable" if applicable is True else f"skip: {applicable}"
            except CannotRunError as error:
                entries.append(
                    describe(
                        gate,
                        f"cannot assess: {error}",
                        Result.cannot_run(str(error)),
                    ),
                )
                continue
            except Exception as error:
                logger.exception("gate %s applicability crashed", gate.name)
                detail = traceback.format_exc()
                verdict = f"crashed: {type(error).__name__}: {error}"
                entries.append(
                    describe(gate, verdict, Result.cannot_run(f"{verdict}\n{detail}")),
                )
                continue
            entries.append(describe(gate, verdict, Result.ok()))
        return tuple(entries)
