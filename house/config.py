# SPDX-License-Identifier: MIT
"""Validate the versioned repository configuration using TOML 1.0 types."""

import importlib
import re
import shlex
import sys
import tomllib
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from house.api import CONFIG_NAME
from house.core import CannotRunError, read
from house.providers import SUPPORTED

GROUPS = ("standards", "format", "lint", "build", "consumer", "docs", "online")
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]*")
MODULE = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*"


def problem(label, message):
    raise CannotRunError(f"house.toml: {label}: {message}")


def table(value, label):
    if not isinstance(value, dict):
        problem(label, "expected a table")
    return value


def keys(value, allowed, label):
    table(value, label)
    unknown = value.keys() - set(allowed)
    if unknown:
        problem(label, f"unknown keys {sorted(unknown)}; supported: {sorted(allowed)}")


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        problem(label, "expected a nonempty string")
    return value


def strings(value, label):
    if not isinstance(value, list):
        problem(label, "expected an array of strings")
    for item in value:
        text(item, label)
    if len(set(value)) != len(value):
        problem(label, "duplicate values")
    return value


def relative(value, label):
    value = text(value, label)
    if Path(value).is_absolute() or PureWindowsPath(value).drive:
        problem(label, "expected a path relative to the repository")
    if ".." in Path(value).parts or "\\" in value:
        problem(label, "use forward slashes and stay inside the repository")
    return Path(value).as_posix()


def rows(value, label):
    if not isinstance(value, list):
        problem(label, "expected an array of tables")
    for item in value:
        table(item, label)
    return value


def structured(value, label):
    """Overlays are bounded JSON-compatible data; renderers own their schemas."""
    if isinstance(value, dict):
        for key, child in value.items():
            structured(child, f"{label}.{key}")
    elif isinstance(value, list):
        for child in value:
            structured(child, label)
    elif type(value) not in {str, int, float, bool}:
        problem(label, f"unsupported value type {type(value).__name__}")


def packages(config):
    for name, package in table(config.setdefault("packages", {}), "packages").items():
        if not IDENTIFIER.fullmatch(name):
            problem("packages", f"invalid package name {name!r}")
        label = f"packages.{name}"
        keys(
            package,
            {
                "path",
                "budget",
                "modes",
                "consumer_executables",
                "consumer_cases",
            },
            label,
        )
        package["path"] = relative(package.get("path"), f"{label}.path")
        for field in ("budget",):
            if field in package:
                relative(package[field], f"{label}.{field}")
        for mode, capability in table(
            package.setdefault("modes", {}),
            f"{label}.modes",
        ).items():
            text(mode, f"{label}.modes")
            text(capability, f"{label}.modes.{mode}")
            if capability not in {
                "build",
                "build-test",
                "build-install",
                "build-test-install",
            }:
                problem(label, f"unknown mode capability {capability!r}")
        consumer_executables(package, label)
        consumer_cases(package, label)


CASE_STAGES = (
    "producer-configure",
    "producer-build",
    "consumer-configure",
    "consumer-build",
)
CASE_OWNED = {
    "producer_args": ("-S", "-B", "-G", "-DCMAKE_INSTALL_PREFIX"),
    "consumer_args": ("-S", "-B", "-G", "-DCMAKE_PREFIX_PATH"),
}


def case_args(case, key, label):
    """Validate a case's CMake arguments; the gate owns the location arguments."""
    arguments = case.get(key, [])
    if not isinstance(arguments, list):
        problem(f"{label}.{key}", "expected an array of strings")
    for argument in arguments:
        text(argument, f"{label}.{key}")
        if argument.startswith(CASE_OWNED[key]):
            problem(f"{label}.{key}", f"{argument!r} is set by the gate")
    return arguments


def consumer_cases(package, label):
    """Validate the consumer cases the consumer gate builds beyond the default."""
    label += ".consumer_cases"
    cases = rows(package.setdefault("consumer_cases", []), label)
    names = set()
    for case in cases:
        keys(
            case,
            {
                "name",
                "tree",
                "producer_args",
                "consumer_args",
                "source",
                "expect",
                "stage",
                "message",
            },
            label,
        )
        name = text(case.get("name"), f"{label}.name")
        if not IDENTIFIER.fullmatch(name) or name in names:
            problem(label, f"case name {name!r} must be valid and unique")
        names.add(name)
        label_case = f"{label}.{name}"
        text(case.setdefault("tree", "host"), f"{label_case}.tree")
        for key in ("producer_args", "consumer_args"):
            case[key] = case_args(case, key, label_case)
        if "source" in case:
            case["source"] = relative(case["source"], f"{label_case}.source")
        expect = case.get("expect")
        if expect not in {"runs", "fails"}:
            problem(f"{label_case}.expect", 'expected "runs" or "fails"')
        if expect == "runs":
            extra = {"stage", "message"} & case.keys()
            if extra:
                problem(label_case, f'{sorted(extra)} only apply to expect = "fails"')
        else:
            if case.get("stage") not in CASE_STAGES:
                problem(f"{label_case}.stage", f"expected one of {list(CASE_STAGES)}")
            text(case.get("message"), f"{label_case}.message")


def case_trees(config):
    """Refuse a case that names a tree other than host, fuzz or a declared one."""
    declared = {"host", "fuzz", *(item["name"] for item in config["trees"])}
    for name, package in config["packages"].items():
        for case in package["consumer_cases"]:
            if case["tree"] not in declared:
                problem(
                    f"packages.{name}.consumer_cases.{case['name']}.tree",
                    f"unknown tree {case['tree']!r}; declared: {sorted(declared)}",
                )


def consumer_executables(package, label):
    """Validate the host consumer programs the consumer gate runs (AR-8)."""
    if "consumer_executables" not in package:
        return
    label += ".consumer_executables"
    names = strings(package["consumer_executables"], label)
    if not names:
        problem(label, "expected at least one executable, or omit the key")
    for name in names:
        relative(name, label)
    modes = package["modes"]
    default = "build-test" if modes else "build-test-install"
    if "install" not in modes.get("host", default).split("-"):
        problem(label, "needs an installable host mode")


def container_options(requirement, ci):
    """Validate GitHub job options as data; never run Docker or a shell (AR-15)."""
    if "container_options" not in requirement:
        return
    label = "ci.require.container_options"
    if "container" not in ci:
        problem(label, "requires ci.container")
    value = text(requirement["container_options"], label)
    if any(ord(char) < 32 for char in value):
        problem(label, "expected a single-line string")
    try:
        words = shlex.split(value)
    except ValueError as error:
        raise CannotRunError(f"house.toml: {label}: malformed quoting") from error
    if any(word.split("=", 1)[0] in {"--network", "--entrypoint"} for word in words):
        problem(label, "GitHub does not support --network or --entrypoint")


def ci_prepare(requirement):
    """Validate group preparation commands as data; House never runs them (AR-16)."""
    if "prepare" not in requirement:
        return
    label = "ci.require.prepare"
    commands = strings(requirement["prepare"], label)
    if not commands:
        problem(label, "expected at least one command")
    if any(ord(char) < 32 for command in commands for char in command):
        problem(label, "each command must be a single-line string")


def declared_gate(gate, seen, groups):
    keys(gate, {"name", "module", "group", "repair"}, "gates")
    name = text(gate.get("name"), "gates.name")
    if not IDENTIFIER.fullmatch(name) or name in seen:
        problem("gates.name", f"invalid or duplicate name {name!r}")
    seen.add(name)
    if not re.fullmatch(MODULE, text(gate.get("module"), "gates.module")):
        problem("gates.module", "expected a dotted Python module name")
    if "repair" in gate:
        text(gate["repair"], "gates.repair")
    group = text(gate.get("group"), "gates.group")
    if group not in {*GROUPS, *groups}:
        problem("gates.group", f"unknown group {gate.get('group')!r}")


def extensions(config):
    groups = table(config.setdefault("groups", {}), "groups")
    for name, members in groups.items():
        if not IDENTIFIER.fullmatch(name):
            problem("groups", f"invalid group {name!r}")
        strings(members, f"groups.{name}")
    seen = set()
    for gate in rows(config.setdefault("gates", []), "gates"):
        declared_gate(gate, seen, groups)
    seen = set()
    for tree in rows(config.setdefault("trees", []), "trees"):
        keys(tree, {"name", "profile"}, "trees")
        name = text(tree.get("name"), "trees.name")
        if not IDENTIFIER.fullmatch(name) or name in seen:
            problem("trees.name", f"invalid or duplicate tree {name!r}")
        seen.add(name)
        if not re.fullmatch(
            MODULE + r":[A-Za-z_]\w*",
            text(tree.get("profile"), "trees.profile"),
        ):
            problem("trees.profile", "expected module:attribute")


def ci_image(ci):
    """Validate image and optional family-wide job user (AR-15)."""
    if "container" in ci:
        text(ci["container"], "ci.container")
    if "container_user" in ci:
        value = text(ci["container_user"], "ci.container_user")
        user = r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*"
        if not re.fullmatch(rf"{user}(?::{user})?", value):
            problem("ci.container_user", "expected a user or user:group")


def ci_settings(config):
    ci = config.setdefault("ci", {})
    keys(ci, {"container", "container_user", "skip", "require", "axes"}, "ci")
    ci_image(ci)
    for name, reason in table(ci.setdefault("skip", {}), "ci.skip").items():
        text(name, "ci.skip")
        text(reason, f"ci.skip.{name}")
    seen = set()
    for requirement in rows(ci.setdefault("require", []), "ci.require"):
        keys(
            requirement,
            {"group", "matrix", "schedule", "container_options", "prepare"},
            "ci.require",
        )
        group = text(requirement.get("group"), "ci.require.group")
        if group not in {*GROUPS, *config["groups"]}:
            problem("ci.require.group", f"unknown group {requirement.get('group')!r}")
        if group in seen:
            problem("ci.require.group", "duplicate requirement for group")
        seen.add(group)
        container_options(requirement, ci)
        ci_prepare(requirement)
        for axis, values in table(
            requirement.get("matrix", {}),
            "ci.require.matrix",
        ).items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", axis):
                problem(
                    "ci.require.matrix",
                    "axis must use lowercase letters, digits and underscores",
                )
            if not strings(values, f"ci.require.matrix.{axis}"):
                problem("ci.require.matrix", "an axis must have at least one value")
        if "schedule" in requirement and requirement["schedule"] != "weekly":
            problem("ci.require.schedule", "only weekly is supported")
    matrix_axes(ci)


AXIS = re.compile(r"[a-z][a-z0-9_]*")
VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HOUSE_VARIABLES = {
    "CMAKE_BUILD_TYPE",
    "CMAKE_C_COMPILER",
    "CMAKE_CXX_COMPILER",
    "CMAKE_EXPORT_COMPILE_COMMANDS",
    "CMAKE_FIND_USE_PACKAGE_REGISTRY",
    "CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY",
    "CMAKE_INSTALL_PREFIX",
    "CMAKE_PREFIX_PATH",
}
RESERVED_AXES = {"build_type", "compiler"}


def matrix_axes(ci):
    """Validate the axes that set a CMake cache variable in every tree."""
    axes = table(ci.setdefault("axes", {}), "ci.axes")
    used = {axis for item in ci["require"] for axis in item.get("matrix", {})}
    seen = {}
    for axis, variable in axes.items():
        label = f"ci.axes.{axis}"
        if not AXIS.fullmatch(axis) or axis in RESERVED_AXES:
            problem(label, "expected a lowercase axis other than build_type, compiler")
        if axis not in used:
            problem(label, "names no axis of a ci.require matrix")
        if not VARIABLE.fullmatch(text(variable, label)):
            problem(label, f"{variable!r} is not a CMake variable name")
        if variable in HOUSE_VARIABLES or variable.endswith(
            ("_ENABLE_TESTS", "_ENABLE_FUZZERS"),
        ):
            problem(label, f"{variable} is set by House")
        if variable in seen:
            problem(label, f"{variable} is already set by axis {seen[variable]}")
        seen[variable] = axis


def sync_settings(config):
    sync = config.setdefault("sync", {})
    keys(sync, {"files", "overlay", "replace"}, "sync")
    for path in strings(sync.setdefault("files", []), "sync.files"):
        relative(path, "sync.files")
    structured(table(sync.setdefault("overlay", {}), "sync.overlay"), "sync.overlay")
    for file_id, fields in table(
        sync.setdefault("replace", {}),
        "sync.replace",
    ).items():
        text(file_id, "sync.replace")
        strings(fields, f"sync.replace.{file_id}")


def context_settings(config):
    """Validate the per-user directory names a family has context report."""
    settings = config.setdefault("context", {})
    keys(settings, {"config_directories"}, "context")
    names = strings(
        settings.setdefault("config_directories", []),
        "context.config_directories",
    )
    for name in names:
        if not CONFIG_NAME.fullmatch(name) or name == "house":
            problem(
                "context.config_directories",
                f"{name!r} must be one lowercase path segment other than house",
            )


def validate(raw):
    config = deepcopy(raw)
    keys(
        config,
        {
            "family",
            "house",
            "packages",
            "groups",
            "gates",
            "trees",
            "ci",
            "sync",
            "context",
        },
        "root",
    )
    if "family" in config:
        config["family"] = relative(config["family"], "family")
    house = config.setdefault("house", {})
    keys(house, {"platform", "languages", "licence"}, "house")
    house["platform"] = relative(
        house.setdefault("platform", "platform"),
        "house.platform",
    )
    languages = strings(house.setdefault("languages", []), "house.languages")
    if set(languages) - SUPPORTED:
        problem("house.languages", f"supported providers: {sorted(SUPPORTED)}")
    text(house.setdefault("licence", "MIT"), "house.licence")
    packages(config)
    extensions(config)
    case_trees(config)
    ci_settings(config)
    sync_settings(config)
    context_settings(config)
    return config


FAMILY_KEYS = {"house", "groups", "gates", "trees", "ci", "sync", "context"}


def beneath(base, own, key=""):
    """Repository settings win; declarations with distinct names coexist (AR-18)."""
    if isinstance(base, dict) and isinstance(own, dict):
        return {
            **base,
            **{
                name: beneath(base[name], value, name) if name in base else value
                for name, value in own.items()
            },
        }
    identity = {"gates": "name", "trees": "name", "require": "group"}.get(key)
    if identity and isinstance(base, list) and isinstance(own, list):
        replaced = {row.get(identity) for row in own if isinstance(row, dict)}
        return [
            row
            for row in base
            if isinstance(row, dict) and row.get(identity) not in replaced
        ] + own
    return own


def load(root: Path):
    try:
        raw = tomllib.loads(read(root / "house.toml"))
        origins = {}
        if "family" in raw:
            path = relative(raw["family"], "family")
            family = (root / path).resolve()
            if not family.is_relative_to(root.resolve()):
                problem("family", f"path outside repository: {path}")
            inherited = tomllib.loads(read(family / "family.toml"))
            keys(inherited, FAMILY_KEYS, "family.toml")
            keys(
                inherited.get("house", {}),
                {"languages", "licence"},
                "family.toml.house",
            )
            # Overrides must not hide malformed family declarations.
            validate(inherited)
            for field, module_key in (("gates", "module"), ("trees", "profile")):
                overrides = {row.get("name") for row in rows(raw.get(field, []), field)}
                for row in inherited.get(field, []):
                    if row["name"] not in overrides:
                        origins[row[module_key].split(":")[0]] = str(family)
            raw = beneath(inherited, raw)
        config = validate(raw)
        config["_family_modules"] = origins
    except tomllib.TOMLDecodeError as error:
        raise CannotRunError(f"cannot parse configuration: {error}") from error
    else:
        return config


def extension_module(repo, name):
    """Import an extension from its declared repository or pinned family (AR-18)."""
    source = repo.config.get("_family_modules", {}).get(name, str(repo.root))
    sys.path.insert(0, source)
    try:
        module = importlib.import_module(name)
    except Exception as error:
        raise CannotRunError(
            f"cannot import module {name} from {source}: {error}",
        ) from error
    finally:
        sys.path.pop(0)
    if name in repo.config.get("_family_modules", {}) and not Path(
        module.__file__ or "",
    ).resolve().is_relative_to(Path(source)):
        raise CannotRunError(f"module {name} is not from pinned family {source}")
    return module
