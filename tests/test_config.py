# SPDX-License-Identifier: MIT
"""Bad declarations cannot quietly select a different development contract."""

import tomllib

import pytest

from house.config import load, validate
from house.core import CannotRunError


@pytest.mark.parametrize(
    "source",
    [
        "[unknown]\nvalue=1",
        "[house]\nlanguages=['unknown']",
        "[house]\nplatform='../other'",
        "[house]\nplatform='/outside'",
        "[house]\nplatform='C:/outside'",
        "[house]\nplatform='C:outside'",
        "[house]\nlanguages=['python','python']",
        "house='invalid'",
        "[packages.sample]\nmodes={host='build'}",
        "[packages.sample]\npath='.'\nrequirement_prefixes=['LONG']",
        "[packages.sample]\npath='.'\nmodes={host=[]}",
        "[sync]\nfiles='file.txt'",
        "[sync.overlay.sample]\ndate=1979-05-27",
        "[groups]\nextra='invalid'",
        "[[gates]]\nname='sample'\nmodule='not:module'\ngroup='standards'",
    "[[gates]]\nname='sample'\nmodule='tools.sample'\ngroup='unknown'",
    "[[gates]]\nname='sample'\nmodule='tools.sample'\ngroup=[]",
        "[[gates]]\nname='a'\nmodule='tools.a'\ngroup='standards'\nrepair=1",
        "[[gates]]\nname='a'\nmodule='tools.a'\ngroup='standards'\nrepair=' '",
        "[[trees]]\nname='sample'\nprofile='not-an-import'",
        "[ci.skip]\nsample=' '",
    "[[ci.require]]\ngroup='unknown'",
    "[[ci.require]]\ngroup=[]",
        "[[ci.require]]\ngroup='build'\nmatrix={mode=[]}",
        "[[neutral.check]]\nterms='../outside'\npaths=['.']",
        "[progress]\nunknown=[]",
        "[context]\nunknown=[]",
        "[context]\nconfig_directories='sample'",
        "[context]\nconfig_directories=['Sample']",
        "[context]\nconfig_directories=['a/b']",
        "[context]\nconfig_directories=['house']",
        "[context]\nconfig_directories=['sample','sample']",
    ],
)
def test_reject_invalid_schema(source):
    with pytest.raises(CannotRunError, match=r"house\.toml"):
        validate(tomllib.loads(source))


def test_registered_config_directories_default_to_none_and_keep_order():
    assert validate({})["context"] == {"config_directories": []}
    declared = {"context": {"config_directories": ["sample", "other"]}}
    assert validate(declared)["context"]["config_directories"] == ["sample", "other"]


def test_normalize_without_mutating_declarations():
    original = {
        "house": {"platform": "./"},
        "packages": {"sample": {"path": "libs/sample/"}},
    }
    config = validate(original)
    assert config["house"]["platform"] == "."
    assert config["packages"]["sample"]["path"] == "libs/sample"
    assert original["house"]["platform"] == "./"


def test_unreadable_and_malformed_inputs(tmp_path):
    with pytest.raises(CannotRunError, match="cannot read"):
        load(tmp_path)
    (tmp_path / "house.toml").write_text("[broken")
    with pytest.raises(CannotRunError, match="cannot parse"):
        load(tmp_path)
    (tmp_path / "house.toml").write_bytes(b"\xff")
    with pytest.raises(CannotRunError, match="cannot read"):
        load(tmp_path)


def test_full_synthetic_extension_declaration():
    config = validate(
        tomllib.loads("""
[house]
languages = ["python", "markdown"]
[packages.sample]
path = "libs/sample"
budget = "libs/sample/docs/budget.txt"
modes = { host = "build-test-install" }
[groups]
alternate = ["sample"]
[[gates]]
name = "sample"
module = "tools.sample"
group = "alternate"
[[trees]]
name = "alternate"
profile = "tools.profiles:alternate"
[sync]
files = ["dev.py", ".editorconfig"]
[sync.overlay.editor]
values = ["first", "second"]
[sync.replace]
editor = ["mode"]
[ci.skip]
sample = "not applicable in this configuration"
[[ci.require]]
group = "alternate"
matrix = { mode = ["fast", "safe"] }
"""),
    )
    assert config["gates"][0]["group"] == "alternate"
    assert config["ci"]["require"][0]["matrix"]["mode"] == ["fast", "safe"]


def test_contract_is_an_unknown_key():
    with pytest.raises(CannotRunError, match=r"house: unknown keys \['contract'\]"):
        validate({"house": {"contract": "0.1"}})
