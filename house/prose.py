# SPDX-License-Identifier: MIT
"""Extract comments without treating fixture strings as suppressions."""

import io
import re
import tokenize
from pathlib import Path

from house.core import CannotRunError

HASH_COMMENTED = frozenset({".cmake", ".sh", ".bash", ".yml", ".yaml", ".txt"})


C_FAMILY = frozenset(
    {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".tpp", ".inl"},
)
RAW_STRING = re.compile(r'R"([^ ()\\\t\n]{0,16})\(')


def hash_comments(text: str) -> dict[int, str]:
    """Map each line to its `#` comment.

    A comment is a `#` outside quotes that opens the line or follows whitespace.
    """
    found = {}
    for number, line in enumerate(text.splitlines(), 1):
        quote = ""
        for i, char in enumerate(line):
            if quote:
                if char == "\\" and quote == '"':
                    continue
                quote = "" if char == quote and line[i - 1] != "\\" else quote
            elif char in "\"'":
                quote = char
            elif char == "#" and (i == 0 or line[i - 1].isspace()):
                found[number] = line[i:]
                break
    return found


def in_number(text: str, at: int) -> bool:
    """Say whether the apostrophe at `at` separates digits, as in 0xAB'CD."""
    start = at
    while start and (text[start - 1].isalnum() or text[start - 1] in "'._"):
        start -= 1
    return start < at and text[start].isdigit()


def c_comments(text: str) -> list[tuple[int, str]]:
    """Return the comments of a C or C++ source, line by line.

    Every string, character and raw string literal is skipped.
    """
    found: dict[int, list[str]] = {}
    line, i, size = 1, 0, len(text)

    def keep(start: int, end: int, at: int) -> int:
        for offset, part in enumerate(text[start:end].split("\n")):
            found.setdefault(at + offset, []).append(part)
        return at + text[start:end].count("\n")

    while i < size:
        char = text[i]
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = size if end < 0 else end
            line = keep(i, end, line)
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = size if end < 0 else end + 2
            line = keep(i, end, line)
            i = end
        elif (raw := RAW_STRING.match(text, i)) is not None:
            end = text.find(f'){raw.group(1)}"', raw.end())
            end = size if end < 0 else end + len(raw.group(1)) + 2
            line += text.count("\n", i, end)
            i = end
        elif char in "\"'" and not (char == "'" and in_number(text, i)):
            j = i + 1
            while j < size and text[j] not in (char, "\n"):
                j += 2 if text[j] == "\\" else 1
            line += text.count("\n", i, min(j, size))
            i = j + 1 if j < size and text[j] == char else j
        else:
            line += char == "\n"
            i += 1
    return [(n, " ".join(parts)) for n, parts in sorted(found.items())]


def comments(path: Path, text: str) -> dict[int, str]:
    """Map each line holding a comment to that comment, by the file's language.

    Python's comments come from its tokenizer, so a `#` inside a string is not
    one; a `#`-commented language's are the text from a `#` that opens a line
    or follows whitespace. Any other file maps every line to itself.
    """
    if path.suffix == ".py":
        return {
            t.start[0]: t.string
            for t in python_tokens(text)
            if t.type == tokenize.COMMENT
        }
    if path.suffix in HASH_COMMENTED or path.name == "CMakeLists.txt":
        return hash_comments(text)
    if path.suffix in C_FAMILY:
        return dict(c_comments(text))
    return dict(enumerate(text.splitlines(), 1))


def python_tokens(text: str) -> list[tokenize.TokenInfo]:
    try:
        return list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError) as error:
        raise CannotRunError(f"cannot tokenize Python: {error}") from error
