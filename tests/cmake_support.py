# SPDX-License-Identifier: MIT
"""Execute actual CMake projects without network or a shell test harness."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tests.conftest import ROOT

MODULE = ROOT / "cxx/cmake/house.cmake"


@dataclass
class Project:
    root: Path

    @property
    def build(self):
        return self.root / "build"

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def command(self, *args, expected=None, expected_warning=None):
        env = dict(os.environ)
        for key in ("CFLAGS", "CXXFLAGS", "CMAKE_GENERATOR"):
            env.pop(key, None)
        done = subprocess.run(
            args,
            cwd=self.root,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        output = done.stdout + done.stderr
        if expected is None:
            assert done.returncode == 0, output
            if expected_warning:
                assert expected_warning in " ".join(output.split()), output
            else:
                assert "warning:" not in output.lower(), output
                assert "CMake Warning" not in output, output
        else:
            assert done.returncode != 0, output
            assert expected in " ".join(output.split()), output
        return output

    def configure(
        self, body, *args, expected=None, languages="C CXX", expected_warning=None,
    ):
        self.write("unit.c", "int c_value(void) { return 1; }\n")
        self.write("unit.cpp", "int value() { return 1; }\n")
        self.write(
            "CMakeLists.txt",
            "cmake_minimum_required(VERSION 3.24)\n"
            f"include({json.dumps(MODULE.as_posix())})\n"
            f"project(synthetic VERSION 1.2.3 LANGUAGES {languages})\n"
            "set(CMAKE_EXPORT_COMPILE_COMMANDS ON)\n" + body,
        )
        return self.command(
            "cmake",
            "-S",
            str(self.root),
            "-B",
            str(self.build),
            "-G",
            "Ninja",
            *args,
            expected=expected,
            expected_warning=expected_warning,
        )

    def compile(self, expected=None):
        return self.command("cmake", "--build", str(self.build), expected=expected)

    def compile_line(self, target, filename="unit.cpp"):
        entries = json.loads((self.build / "compile_commands.json").read_text())
        matches = [
            entry["command"]
            for entry in entries
            if Path(entry["file"]).name == filename
            and f"{target}.dir/" in entry["command"].replace("\\", "/")
        ]
        assert len(matches) == 1, entries
        return matches[0]
