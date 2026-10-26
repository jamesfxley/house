# SPDX-License-Identifier: MIT
"""Render CI from applicable obligations without parsing workflow YAML (AR-10)."""

import importlib
import json

from house.core import CannotRunError, read

CHECKOUT = "actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8"
WORKFLOW = ".github/workflows/ci.yml"


def container(repo):
    value = repo.config["ci"].get("container")
    if value == "devcontainer":
        path = repo.root / ".devcontainer/devcontainer.json"
        try:
            value = json.loads(read(path)).get("image")
        except json.JSONDecodeError as error:
            raise CannotRunError("devcontainer CI input must be strict JSON") from error
        if not isinstance(value, str) or not value:
            raise CannotRunError("devcontainer CI requires an explicit image")
    return value


def matrix_environment(repo, matrix):
    env = {"HOUSE_MATRIX_" + key.upper(): "${{ matrix." + key + " }}" for key in matrix}
    if "build_type" in matrix:
        env["BUILD_TYPE"] = "${{ matrix.build_type }}"
    if "compiler" in matrix and "cxx" in repo.config["house"]["languages"]:
        if set(matrix["compiler"]) - {"gcc", "clang"}:
            raise CannotRunError("C++ compiler matrix supports gcc and clang")
        platform = repo.root / repo.config["house"]["platform"]
        words = [
            line.split("#", 1)[0].strip()
            for line in read(platform / "config/.clang-version").splitlines()
        ]
        major = " ".join(word for word in words if word)
        if not major.isdecimal():
            raise CannotRunError("compiler matrix needs a numeric Clang pin")
        env["CC"] = (
            "${{ matrix.compiler == 'clang' && 'clang-" + major + "' || 'gcc' }}"
        )
        env["CXX"] = (
            "${{ matrix.compiler == 'clang' && 'clang++-" + major + "' || 'g++' }}"
        )
    return env


def test_files(repo):
    return any(
        path.parts[0] in {"test", "tests"}
        and (path.match("test_*.py") or path.match("*_test.py"))
        for path in repo.tracked()
    )


def job(repo, group, requirement, image):
    weekly = requirement.get("schedule") == "weekly"
    has_tests = (
        group == "standards"
        and "python" in repo.config["house"]["languages"]
        and test_files(repo)
    )
    profile = "platform-tests" if repo.config["house"]["platform"] == "." else "tests"
    install = "python3 dev.py toolchain install --system"
    if has_tests:
        install += " --profile " + profile
    elif group == "online":
        install += " --profile online"
    steps = [
        {
            "uses": CHECKOUT,
            "with": {
                "fetch-depth": 0,
                "submodules": "recursive",
                "persist-credentials": False,
            },
        },
        {"name": "Prepare declared tools", "run": install},
        *(
            {"name": f"Prepare {group} input {number}", "run": command}
            for number, command in enumerate(requirement.get("prepare", []), 1)
        ),
        {"name": "Check " + group, "run": "python3 dev.py check --ci --group " + group},
    ]
    if has_tests:
        steps.append(
            {
                "name": "Test owned Python",
                "run": "python3 dev.py toolchain run pytest -W error",
            },
        )
    value = {
        "runs-on": "ubuntu-26.04",
        "if": (
            ("${{ github.event_name == 'schedule' || "
                "github.event_name == 'workflow_dispatch' || "
                "github.event_name == 'repository_dispatch' }}")
            if weekly
            else "${{ github.event_name != 'schedule' }}"
        ),
        "concurrency": {
            "group": (
                "${{ github.workflow }}-" + group
                + "-${{ strategy.job-index || 0 }}-"
                + ("${{ github.ref == 'refs/heads/main' "
                   "&& github.run_id || github.ref }}")
            ),
            "cancel-in-progress": "${{ github.ref != 'refs/heads/main' }}",
        },
        "steps": steps,
    }
    matrix = requirement.get("matrix", {})
    if matrix:
        value["strategy"] = {"fail-fast": False, "matrix": matrix}
        value["env"] = matrix_environment(repo, matrix)
    if group == "online":
        value["permissions"] = {
            "contents": "read", "issues": "read", "pull-requests": "read",
        }
        value.setdefault("env", {}).update({"GH_TOKEN": "${{ github.token }}"})
    job_container(repo, value, requirement, image)
    return value


def job_container(repo, value, requirement, image):
    """Render image and user/options without changing runner-only jobs (AR-15)."""
    if image:
        value["container"] = {"image": image}
        options = []
        if "container_options" in requirement:
            options.append(requirement["container_options"])
        if user := repo.config["ci"].get("container_user"):
            options.append(f"--user {user}")
        if options:
            value["container"]["options"] = " ".join(options)
    elif "container_options" in requirement:
        raise CannotRunError("container_options requires a resolved container image")



def model(repo):
    # Delayed import avoids coupling the registry to the serializer's imports.
    engine = importlib.import_module("house.cli").runner(repo)
    gates = engine.applicable_gates(all_groups=True)
    registered = {gate.name for gate in engine.gates}
    for group, members in repo.config["groups"].items():
        if set(members) - registered:
            raise CannotRunError(f"CI group {group} names unregistered gates")
    groups = [
        group
        for group in engine.groups
        if any(
            gate.group == group or gate.name in repo.config["groups"].get(group, [])
            for gate in gates
        )
    ]
    requirements = {item["group"]: item for item in repo.config["ci"]["require"]}
    if set(requirements) - set(groups):
        raise CannotRunError(
            "CI requires a group with no applicable obligations: "
            + ", ".join(sorted(set(requirements) - set(groups))),
        )
    image = container(repo)
    events = {
        "push": {},
        "pull_request": {},
        "workflow_dispatch": {},
        "repository_dispatch": {},
    }
    if any(item.get("schedule") == "weekly" for item in requirements.values()):
        events["schedule"] = [{"cron": "17 3 * * 1"}]
    return {
        "name": "Checks",
        "on": events,
        "permissions": {"contents": "read"},
        "jobs": {
            "check_" + group: job(repo, group, requirements.get(group, {}), image)
            for group in groups
        },
    }


def render(repo):
    serializer = importlib.import_module("house.sync").yaml_value
    return "# Generated by dev.py sync.\n" + serializer(model(repo)) + "\n"
