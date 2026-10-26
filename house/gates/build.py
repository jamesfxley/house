# SPDX-License-Identifier: MIT
"""Run C++ builds and tests for declared host, fuzz and family profiles."""

import argparse

from house.build import build
from house.gates.common import Always
from house.trees import applicability


class Build(Always):
    name = "build"
    provider = "cxx"
    group = "build"
    rules = ("EN-01.3", "EN-04.2")

    def __init__(self, tree="host"):
        self.configuration = tree
        self.name = "build" if tree == "host" else "build:" + tree

    def applies(self, repo):
        return applicability(repo, self.configuration)

    def run(self, repo, argv):
        parser = argparse.ArgumentParser(prog="dev.py build")
        parser.add_argument("--tree")
        args = parser.parse_args(argv)
        return build(repo, args.tree or self.configuration)
