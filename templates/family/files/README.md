# Sample family

Run `python3 dev.py check --ci` after initializing recursive submodules.
Prepare declared tools explicitly with `python3 dev.py toolchain install`.
Python families add `--profile tests`, then run
`python3 dev.py toolchain run pytest -W error`. C++ families use
`python3 dev.py build` and `python3 dev.py gate consumer`.
On Windows use `python3` or the optional `py -3` launcher.

[Documentation](docs/README.md) explains the sample and its requirements.
This repository is developed with AI assistance; the maintainer owns design,
review and acceptance.
