# SPDX-License-Identifier: MIT
"""Format or check owned C and C++ sources using the pinned style."""

from house.api import Finding
from house.core import CannotRunError
from house.gates.common import Always, verdict
from house.providers import get
from house.tools import clang, diagnostic, owned, platform, run, warning


class Format(Always):
    name = "format"
    provider = "cxx"
    group = "format"
    rules = ("EN-01.2",)

    def applies(self, repo):
        return (
            True
            if "cxx" in repo.config["house"]["languages"]
            else "no C++ formatter applies"
        )

    def run(self, repo, argv):
        if argv not in {(), ("--check",), ("--write",)}:
            raise CannotRunError("format supports --check or --write")
        paths = owned(repo, get("cxx").suffixes)
        if not paths:
            return verdict("EN-01.2", [], "0 C/C++ sources to format")
        tool = clang(repo, "clang-format")
        mode = ["-i"] if argv == ("--write",) else ["--dry-run", "--Werror"]
        faults = []
        for path in paths:
            repo.read(path)
            done = run(
                [
                    tool,
                    *mode,
                    "--style=file:" + str(platform(repo) / "config/.clang-format"),
                    str(repo.root / path),
                ],
                repo.root,
            )
            if done.returncode or warning(diagnostic(done)):
                faults.append(Finding(path, 0, "EN-01.2", diagnostic(done)))
        return verdict("EN-01.2", faults, f"{len(paths)} owned C/C++ sources formatted")
