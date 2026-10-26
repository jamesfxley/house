# SPDX-License-Identifier: MIT
"""Register the shared gate implementations without coupling their imports."""

from house.gates.api_docs import ApiDocs
from house.gates.build import Build
from house.gates.build_warnings import BuildWarnings
from house.gates.commits import Commits
from house.gates.compile_db import CompileDb
from house.gates.consumer import Consumer
from house.gates.deviations import Deviations
from house.gates.doc_links import DocLinks
from house.gates.format import Format
from house.gates.lint import Lint
from house.gates.spdx import Spdx
from house.gates.synced_files import SyncedFiles
from house.trees import profile_names


def builtin(repo=None):
    names = (
        profile_names(repo)
        if repo and "cxx" in repo.config["house"]["languages"]
        else []
    )
    return [
        Commits(),
        SyncedFiles(),
        Deviations(),
        DocLinks(),
        Spdx(),
        Format(),
        Build(),
        *(Build(name) for name in names),
        BuildWarnings(),
        CompileDb(),
        Lint(),
        *(Lint(name) for name in names),
        ApiDocs(),
        Consumer(),
    ]
