# SPDX-License-Identifier: MIT
"""Direct users to the repository launcher."""

import sys

print(
    "run python3 dev.py from the checkout, or py -3 dev.py on Windows",
    file=sys.stderr,
)
raise SystemExit(2)
