# SPDX-License-Identifier: MIT
"""The command interface called by the checkout's launcher."""

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path

from house import VERSION, context, hooks, initialize, toolchain
from house.api import Finding, Repo, Result
from house.build import build as build_all
from house.config import extension_module, load
from house.core import CannotRunError
from house.providers import get
from house.registry import builtin
from house.runner import Runner, execute, exit_code
from house.sync import sync

logger = logging.getLogger(__name__)


def parser():
    result = argparse.ArgumentParser(prog="dev.py")
    result.add_argument("--version", action="version", version=VERSION)
    commands = result.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="run registered gates")
    check.add_argument("--group", action="append", default=[])
    check.add_argument("--all", action="store_true", dest="all_groups")
    check.add_argument("--ci", action="store_true")
    check.add_argument("--list", action="store_true", dest="listed")
    gate = commands.add_parser("gate", help="run one registered gate")
    gate.add_argument("name")
    gate.add_argument("args", nargs=argparse.REMAINDER)
    commits = commands.add_parser("commits", help="check every selected commit")
    selection = commits.add_mutually_exclusive_group()
    selection.add_argument("--range")
    selection.add_argument("--root", action="store_true")
    hook = commands.add_parser("hook", help="install or run pinned git hooks")
    hook.add_argument("action", choices=("install", "pre-commit", "commit-msg"))
    hook.add_argument("args", nargs=argparse.REMAINDER)
    diagnosis = commands.add_parser(
        "doctor", help="check hooks and declared tools",
    )
    diagnosis.add_argument(
        "--hooks", action="store_true", help="inspect only Git hooks",
    )
    building = commands.add_parser(
        "build",
        help="configure, clean-build and test C++ trees",
    )
    building.add_argument("--tree")
    formatting = commands.add_parser("format", help="format owned provider sources")
    formatting.add_argument("--check", action="store_true")
    commands.add_parser("lint", help="lint owned provider sources")
    syncing = commands.add_parser("sync", help="render tracked configuration copies")
    syncing.add_argument("--check", action="store_true")
    contextual = commands.add_parser(
        "context",
        help="show pinned instructions for a path",
    )
    contextual.add_argument("path", type=Path, nargs="?")
    contextual.add_argument("--json", action="store_true")
    infrastructure_parsers(commands)
    return result


def infrastructure_parsers(commands):
    scaffolding = commands.add_parser("init", help="scaffold an empty local checkout")
    scaffolding.add_argument("destination", type=Path, nargs="?", default=Path.cwd())
    scaffolding.add_argument(
        "--kind", choices=("standard", "platform", "family"), required=True,
    )
    scaffolding.add_argument("--lang", action="append", default=[])
    scaffolding.add_argument("--platform-source", type=Path)
    scaffolding.add_argument("--pin-path")
    scaffolding.add_argument("--platform-path")
    chain = commands.add_parser("toolchain", help="prepare or inspect declared tools")
    chain_commands = chain.add_subparsers(dest="action", required=True)
    for action in ("install", "doctor"):
        task = chain_commands.add_parser(action)
        task.add_argument(
            "--profile", action="append", choices=toolchain.PROFILES, default=[],
        )
        if action == "install":
            task.add_argument("--system", action="store_true")
    execution = chain_commands.add_parser("run")
    execution.add_argument("tool")
    execution.add_argument("args", nargs=argparse.REMAINDER)


class MissingGate:
    """Stands in for a declared gate whose module is absent, so it fails with a repair.

    The declaration's `repair` text names the command that regenerates the
    module. Without it, an absent module stays unavailable.
    """

    rules = ("EN-01.8",)
    provider = None

    def __init__(self, declaration):
        self.declaration = declaration
        self.name = declaration["name"]
        self.group = declaration["group"]

    def applies(self, _repo):
        return True

    def run(self, _repo, _argv):
        module = self.declaration["module"]
        return Result.fail(
            Finding(
                module.replace(".", "/") + ".py", 0, "EN-01.8",
                f"declared gate module {module} is missing; "
                f"{self.declaration['repair']}",
            ),
        )


def declared_module_is_absent(error, module):
    """Return whether the import failed on the declared module or its package."""
    return error.name is not None and (
        module == error.name or module.startswith(error.name + ".")
    )


def local_gates(repo: Repo):
    gates = []
    # The CLI may also be called programmatically, without the root on sys.path.
    sys.path.insert(0, str(repo.root))
    try:
        for declaration in repo.config["gates"]:
            try:
                module = (
                    extension_module(repo, declaration["module"])
                    if declaration["module"] in repo.config.get("_family_modules", {})
                    else importlib.import_module(declaration["module"])
                )
            except ModuleNotFoundError as error:
                if "repair" in declaration and declared_module_is_absent(
                    error, declaration["module"],
                ):
                    gates.append(MissingGate(declaration))
                    continue
                raise
            gate = getattr(module, "GATE", None)
            if (
                gate is None
                or getattr(gate, "name", None) != declaration["name"]
                or getattr(gate, "group", None) != declaration["group"]
                or not callable(getattr(gate, "run", None))
                or not callable(getattr(gate, "applies", None))
            ):
                raise CannotRunError(
                    f"local module {declaration['module']}: "
                    "GATE metadata differs from declaration",
                )
            gates.append(gate)
    finally:
        sys.path.pop(0)
    return gates


def runner(repo: Repo):
    for name in repo.config["house"]["languages"]:
        get(name)
    return Runner(repo, [*builtin(repo), *local_gates(repo)])


def display(entries):
    for entry in entries:
        print(
            f"{entry.name} [{entry.group}/{entry.package}/"
            f"{entry.configuration}]: {entry.verdict}",
        )
        if entry.result.message:
            print(entry.result.message)
        for finding in entry.result.findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.message}")


def report(result):
    if result.message:
        print(result.message)
    for finding in result.findings:
        print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.message}")
    return result.status


def hook_command(repo, args):
    if args.action == "commit-msg":
        if len(args.args) != 1:
            raise CannotRunError("hook commit-msg requires one message file")
        return report(hooks.commit_message(repo, args.args[0]))
    if args.args:
        raise CannotRunError(f"hook {args.action} takes no arguments")
    if args.action == "install":
        return report(hooks.install(repo))
    entries = hooks.pre_commit(repo, runner(repo))
    display(entries)
    return exit_code(entries)


def agent_command(repo, args):
    if args.command == "context":
        data = context.bindings(repo, args.path)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(context.render(data))
        return 0
    return None


def doctor_command(repo, args):
    if args.hooks:
        return report(hooks.doctor(repo))
    codes = []
    for inspect in (hooks.doctor, toolchain.doctor):
        try:
            codes.append(report(inspect(repo)))
        except CannotRunError as error:
            print(f"cannot run: {error}")
            codes.append(2)
    return 1 if 1 in codes else 2 if 2 in codes else 0


def infrastructure_command(repo, args):
    if args.command == "init":
        return report(
            initialize.initialize(
                repo,
                args.destination,
                args.kind,
                args.lang,
                source=initialize.Source(
                    args.platform_source, args.pin_path, args.platform_path,
                ),
            ),
        )
    if args.command == "toolchain":
        if args.action == "run":
            return toolchain.run_tool(repo, args.tool, args.args)
        if args.action == "install":
            return report(toolchain.install(repo, args.profile, system=args.system))
        return report(toolchain.doctor(repo, args.profile))
    if args.command == "doctor":
        return doctor_command(repo, args)
    return None


def auxiliary(repo, args):
    agent_result = agent_command(repo, args)
    if agent_result is not None:
        return agent_result
    infrastructure_result = infrastructure_command(repo, args)
    if infrastructure_result is not None:
        return infrastructure_result
    if args.command == "build":
        if "cxx" not in repo.config["house"]["languages"]:
            raise CannotRunError("build requires a C++ provider")
        return report(build_all(repo, args.tree))
    if args.command == "hook":
        return hook_command(repo, args)
    if args.command == "sync":
        drift = sync(repo, check=args.check)
        for name in drift:
            print(f"synced copy differs: {name}")
        return 1 if drift else 0
    return None


def provider_arguments(args):
    if args.command == "build":
        return ["--tree", args.tree] if args.tree else []
    if args.command == "format":
        return ["--check"] if args.check else ["--write"]
    return []


def run_check(engine, args):
    groups = tuple(group for value in args.group for group in value.split(","))
    if args.listed:
        entries = engine.listed(groups, all_groups=args.all_groups)
        print("gate\tgroup\tpackage\tconfiguration\tapplicability")
        for entry in entries:
            print(
                entry.name,
                entry.group,
                entry.package,
                entry.configuration,
                entry.verdict,
                sep="\t",
            )
    else:
        entries = engine.run(groups, all_groups=args.all_groups, ci=args.ci)
        display(entries)
    return exit_code(entries)


def main(repo_root: Path, argv) -> int:
    try:
        args = parser().parse_args(argv)
        repo = Repo(repo_root.resolve(), load(repo_root))
        early = auxiliary(repo, args)
        if early is not None:
            return early
        engine = runner(repo)
        if args.command == "commits":
            arguments = (
                ["--range", args.range]
                if args.range is not None
                else ["--root"]
                if args.root
                else []
            )
            entries = (execute(repo, engine.named("commits"), arguments),)
        elif args.command == "lint":
            entries = engine.run(("lint",))
        elif args.command == "format":
            entries = (
                execute(repo, engine.named(args.command), provider_arguments(args)),
            )
        elif args.command == "gate":
            found = engine.named(args.name)
            entries = (execute(repo, found, tuple(args.args)),)
        else:
            return run_check(engine, args)
        display(entries)
        return exit_code(entries)
    except (CannotRunError, ImportError, OSError, UnicodeError, ValueError) as error:
        print(f"cannot run: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"cannot run: crashed: {type(error).__name__}: {error}", file=sys.stderr)
        logger.exception("pinned platform crashed")
        return 2
