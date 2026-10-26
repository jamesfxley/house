# Usage

The sample value function returns one (AR-1). Run the root check command
after changing it. C++ consumers use `sample::value` as the imported CMake
target; strict interface exports are internal and must not be linked directly.

Optional `family` in `house.toml` reads the pinned `family.toml`; repository
settings win and inherited gate/tree modules import directly from the family.
See the pinned platform README for the configuration reference. Init supplies
the standard, guides, tool configuration, tool preparation and runner.
The environment comes from `python3 dev.py toolchain install`.
