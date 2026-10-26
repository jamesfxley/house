# SPDX-License-Identifier: MIT
"""Language discovery and metadata, independent of consumer identity."""

import importlib
from dataclasses import dataclass

from house.core import CannotRunError

PROVIDERS = {
    "cxx": "house.providers.cxx",
    "python": "house.providers.python",
    "markdown": "house.providers.markdown",
}
SUPPORTED = frozenset(PROVIDERS)


@dataclass(frozen=True)
class Language:
    name: str
    suffixes: tuple[str, ...]
    test_paths: tuple[str, ...]
    comment_tokens: tuple[str, ...]
    inline_suppressions: tuple[str, ...]
    scope_disables: tuple[str, ...]
    spdx_line: str | None
    version_sites: tuple[str, ...]
    format_cmd: tuple[str, ...]
    lint_cmd: tuple[str, ...]
    sync_defaults: tuple[str, ...]


def get(name: str) -> Language:
    module = PROVIDERS.get(name)
    if module is None:
        raise CannotRunError(
            f"provider {name!r} is not implemented in this platform revision",
        )
    return importlib.import_module(module).PROVIDER
