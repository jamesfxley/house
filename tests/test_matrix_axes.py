# SPDX-License-Identifier: MIT
"""Matrix axes that set a CMake cache variable in every tree."""

import pytest

from house.core import CannotRunError
from house.trees import Tree, axis_args, configure_args
from tests.conftest import REQUIRE, axes_config


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("HOUSE_MATRIX_PROFILE", "HOUSE_MATRIX_OTHER", "BUILD_ARGS"):
        monkeypatch.delenv(name, raising=False)


def test_a_declared_axis_sets_its_variable_from_the_environment(repo, monkeypatch):
    repo.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "large")
    args = configure_args(repo, Tree("host", ("-DTREE=1",)))
    assert "-DSAMPLE_PROFILE=large" in args
    assert args.index("-DSAMPLE_PROFILE=large") < args.index("-DTREE=1")


def test_an_axis_the_environment_leaves_unset_or_empty_sets_nothing(repo, monkeypatch):
    repo.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    assert axis_args(repo) == []
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "")
    assert axis_args(repo) == []


def test_without_axes_the_arguments_are_unchanged(repo, monkeypatch):
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "large")
    before = configure_args(repo, Tree("host"))
    repo.config["ci"] = axes_config("")["ci"]
    assert configure_args(repo, Tree("host")) == before
    assert not any("PROFILE" in arg for arg in before)


def test_a_consumer_project_can_decline_the_axes(repo, monkeypatch):
    repo.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", "large")
    tree = Tree("host")
    assert "-DSAMPLE_PROFILE=large" not in configure_args(repo, tree, axes=False)


@pytest.mark.parametrize("value", ["a b", "x;y", "-DEVIL=1 ", "a\nb", "$(x)"])
def test_an_unsafe_axis_value_is_refused(repo, monkeypatch, value):
    repo.config["ci"] = axes_config("[ci.axes]\nprofile='SAMPLE_PROFILE'\n")["ci"]
    monkeypatch.setenv("HOUSE_MATRIX_PROFILE", value)
    with pytest.raises(CannotRunError, match="HOUSE_MATRIX_PROFILE"):
        axis_args(repo)


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ("[ci.axes]\nprofile='9BAD'\n", "is not a CMake variable name"),
        ("[ci.axes]\nprofile='A-B'\n", "is not a CMake variable name"),
        ("[ci.axes]\nprofile=''\n", "expected a nonempty string"),
        ("[ci.axes]\nprofile=3\n", "expected a nonempty string"),
        ("[ci.axes]\nprofile='CMAKE_BUILD_TYPE'\n", "is set by House"),
        ("[ci.axes]\nprofile='CMAKE_PREFIX_PATH'\n", "is set by House"),
        ("[ci.axes]\nprofile='SAMPLE_ENABLE_TESTS'\n", "is set by House"),
        ("[ci.axes]\nprofile='SAMPLE_ENABLE_FUZZERS'\n", "is set by House"),
        ("[ci.axes]\nprofile='V'\nother='V'\n", "already set by axis profile"),
        ("[ci.axes]\nabsent='V'\n", "names no axis of a ci.require matrix"),
        ("[ci.axes]\nBad='V'\n", "expected a lowercase axis"),
    ],
)
def test_a_malformed_axis_declaration_is_refused(extra, expected):
    with pytest.raises(CannotRunError, match=expected):
        axes_config(extra)


def test_axes_must_be_a_table():
    with pytest.raises(CannotRunError, match=r"ci\.axes: expected a table"):
        axes_config("", "[ci]\naxes='V'\n" + REQUIRE)


@pytest.mark.parametrize("axis", ["build_type", "compiler"])
def test_the_axes_that_map_to_other_settings_cannot_be_redeclared(axis):
    require = f"[[ci.require]]\ngroup='build'\nmatrix={{{axis}=['x']}}\n"
    with pytest.raises(CannotRunError, match="other than build_type, compiler"):
        axes_config(f"[ci.axes]\n{axis}='SAMPLE_VARIABLE'\n", require)
