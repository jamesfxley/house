# Usage

The sample value function returns one (AR-1). Run the root check command
after changing it. C++ consumers use `sample::value` as the imported CMake
target; strict interface exports are internal and must not be linked directly.

The configuration and scaffolding sections of `@PLATFORM@/README.md` describe
family configuration, repository precedence and the supplied standard, guides,
configuration, tool preparation and runner. The environment comes from
`python3 dev.py toolchain install`.
