# SPDX-License-Identifier: MIT
"""Read tool-neutral metadata from pinned guide frontmatter (AR-9)."""

import json
import re

from house.core import CannotRunError, read

GUIDE_NAMES = (
    "engineering-standard",
    "cxx-standard",
    "cxx-testing",
    "cxx-build-and-toolchain",
    "new-repo",
    "review",
)


def metadata(pinned, name):
    path = pinned / "guides" / name / "SKILL.md"
    lines = read(path).splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise CannotRunError(f"{path}: missing guide frontmatter")
    fields = {}
    for line in lines[1 : lines.index("---", 1)]:
        match = re.fullmatch(r"(name|description):\s*(.*)", line)
        if not match:
            continue
        key, value = match.groups()
        if key in fields:
            raise CannotRunError(f"{path}: duplicate {key}")
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise CannotRunError(
                    f"{path}: {key} must be a quoted string",
                ) from error
        elif value.startswith(("|", ">", "[", "{", "'")):
            raise CannotRunError(f"{path}: use a single-line JSON-quoted {key}")
        if not isinstance(value, str) or not value.strip():
            raise CannotRunError(f"{path}: {key} must be a nonempty string")
        fields[key] = value
    if fields.get("name") != name or not fields.get("description"):
        raise CannotRunError(f"{path}: matching name and description are required")
    return fields
