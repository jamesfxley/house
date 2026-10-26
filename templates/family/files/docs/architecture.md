# Architecture

The repository inputs and their checks are owned here. The platform is pinned
once under @PLATFORM@; its standard is pinned once beneath it. Extensions use
only the platform public API.

Optional `family` in `house.toml` reads the pinned `family.toml`; repository
settings win and inherited gate/tree modules import directly from the family.
See the pinned platform README for the configuration reference. Init supplies
the standard, guides, tool configuration, tool preparation and runner.
The environment comes from `python3 dev.py toolchain install`.
