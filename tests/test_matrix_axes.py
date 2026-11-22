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


INCLUDE = (
    "[[ci.require]]\ngroup='lint'\n"
    "matrix={include=[{lint_tree='all'}, {lint_tree='sanitize', sanitize='thread'}]}\n"
)


def test_an_include_matrix_is_accepted_and_its_keys_count_as_axes():
    config = axes_config("[ci.axes]\nsanitize='SAMPLE_SANITIZE'\n", INCLUDE)
    assert config["ci"]["require"][0]["matrix"]["include"][1] == {
        "lint_tree": "sanitize", "sanitize": "thread",
    }


@pytest.mark.parametrize(
    ("include", "expected"),
    [
        ("include='all'", "expected a nonempty list of tables"),
        ("include=[]", "expected a nonempty list of tables"),
        ("include=['all']", "expected a table"),
        ("include=[{}]", "must name at least one axis"),
        ("include=[{Lint='all'}]", "lowercase letters"),
        ("include=[{lint_tree=''}]", "expected a nonempty string"),
        ("include=[{lint_tree=['all']}]", "expected a nonempty string"),
    ],
)
def test_a_malformed_include_matrix_is_refused(include, expected):
    require = f"[[ci.require]]\ngroup='lint'\nmatrix={{{include}}}\n"
    with pytest.raises(CannotRunError, match=expected):
        axes_config("", require)


@pytest.mark.parametrize(
    "axes",
    [
        "build_type=['Debug', 'Release'], sanitize=['address', 'thread'], ",
        "lwipopts=['fallback'], ",
        "lint_tree=['all'], ",
    ],
)
def test_lint_tree_in_include_with_a_list_axis_is_refused(axes):
    # GitHub would merge each entry into the list axes' combinations.
    require = (
        f"[[ci.require]]\ngroup='lint'\nmatrix={{{axes}include=["
        "{lint_tree='all'}, {lint_tree='fuzz'}, {lint_tree='sanitize'}]}\n"
    )
    with pytest.raises(CannotRunError, match="cannot be combined with a list axis"):
        axes_config("", require)


def test_include_without_lint_tree_may_join_list_axes():
    require = (
        "[[ci.require]]\ngroup='lint'\nmatrix={sanitize=['address', 'thread'], "
        "include=[{sanitize='thread', extra='x'}]}\n"
    )
    assert axes_config("", require)["ci"]["require"][0]["matrix"]["include"]


def test_lint_tree_in_include_with_list_axes_is_allowed_outside_lint():
    require = (
        "[[ci.require]]\ngroup='build'\nmatrix={build_type=['Debug'], "
        "include=[{lint_tree='all'}]}\n"
    )
    assert axes_config("", require)["ci"]["require"][0]["matrix"]["build_type"]


@pytest.mark.parametrize(("value", "expected"), [("", "Debug"), ("Release", "Release")])
def test_an_empty_build_type_counts_as_unset_in_a_fresh_tree(
    repo, monkeypatch, value, expected,
):
    # An include cell without build_type renders BUILD_TYPE empty.
    monkeypatch.setenv("BUILD_TYPE", value)
    args = configure_args(repo, Tree("host"))
    assert f"-DCMAKE_BUILD_TYPE={expected}" in args
    assert "-DCMAKE_BUILD_TYPE=" not in args


def test_an_empty_build_type_keeps_an_existing_cache_type(repo, monkeypatch):
    (repo.root / "build").mkdir()
    (repo.root / "build/CMakeCache.txt").write_text("")
    monkeypatch.setenv("BUILD_TYPE", "")
    args = configure_args(repo, Tree("host"))
    assert not any(arg.startswith("-DCMAKE_BUILD_TYPE") for arg in args)
