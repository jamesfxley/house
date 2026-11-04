# Sample family

## Quick start

The smallest working example and its prerequisites belong here.

## Layout

The public modules and their source directories belong here.

## Building & tests

The commands for each supported build and test environment belong here.

Run `python3 dev.py check --ci` after initialising recursive submodules. Prepare
declared tools explicitly with `python3 dev.py toolchain install`. Python
families add `--profile tests`, then run
`python3 dev.py toolchain run pytest -W error`. C++ families use
`python3 dev.py build` and `python3 dev.py gate consumer`. On Windows use
`python3` or the optional `py -3` launcher.

## Documentation

[Documentation](docs/README.md) explains the sample and its requirements.

## Releases

Release links and compatibility information belong here.

## AI-assisted development

This repository is developed with AI assistance; the maintainer owns design,
review and acceptance.
