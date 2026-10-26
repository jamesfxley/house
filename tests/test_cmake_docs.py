# SPDX-License-Identifier: MIT
"""Port documentation-example extraction and failure regressions (AR-8)."""

import pytest

from tests.cmake_support import Project

DOC_CALL = """
house_cxx_common_settings(OFF)
house_cxx_add_strict_target(doc_strict)
house_cxx_add_doc_examples(examples PACKAGE doc DOCUMENTS guide.md
    HARNESS_DIR harness GROUPS alternate)
"""


@pytest.fixture
def document(tmp_path):
    project = Project(tmp_path)
    project.write("harness/answer.cpp", '#include "answer.inc"\n')
    return project


def test_document_bytes_fences_indentation_and_rebuild(document):
    body = r"""const char* token = "@SAMPLE_SC@";
int answer() {
    int digits[2] = {4, 2};
    const char* escaped = "a\\b;c";
    return digits[0] * 10 + digits[1] + (escaped[1] == '\\' ? 0 : 1);
}
"""
    text = (
        "<!-- example: answer -->\n```cpp\n"
        + body
        + "```\n"
        + """
<!-- example: none -->
```cpp
this is an illustration
```
```sh
a non-C++ block
```
````markdown
```text
nested prose
```
````
- A list item:

  <!-- example: listed -->
  ~~~C++ title="example"
  int listed() { return 1; }
  ~~~
"""
    )
    document.write("guide.md", text)
    document.write("harness/listed.cpp", '#include "listed.inc"\n')
    document.configure(DOC_CALL)
    assert (document.build / "examples/answer.inc").read_text() == body
    assert (
        document.build / "examples/listed.inc"
    ).read_text() == "int listed() { return 1; }\n"
    document.compile()
    document.write("guide.md", text.replace("digits[0] * 10", "undefined_name"))
    document.compile(expected="undefined_name")
    document.write("guide.md", text)
    document.compile()


@pytest.mark.parametrize(
    "fence",
    [
        '```cpp title="x"',
        "   ```cpp",
        "~~~cpp",
        "```C++",
        "```cxx",
        "```cc",
    ],
)
def test_every_cpp_fence_requires_a_marker(document, fence):
    document.write("guide.md", fence + "\nint unmarked() { return 0; }\n```\n")
    document.configure(DOC_CALL, expected="is not marked")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<!-- example: answer -->\nprose\n", "is not followed by a C++ block"),
        ("<!-- example: answer -->\n", "is not followed by a C++ block"),
        ("<!-- example: answer -->\n````cpp\nint answer();\n```\n", "is never closed"),
        ("<!-- example: answer -->\n```cpp\nint answer();\n", "is never closed"),
        (
            "<!-- example: none -->\n```cpp\nillustration\n```\n",
            "no example to compile",
        ),
        (
            "<!-- example: other/answer -->\n```cpp\nint answer();\n```\n",
            "unknown group 'other'",
        ),
        ("\x01", "holds a control character"),
        (
            "````markdown\n```text\ninside\n```\n````\n```cpp\nint answer();\n```\n",
            "is not marked",
        ),
        (
            "- Item\n\n  ```text\n  inside\n\n```cpp\nint answer();\n```\n",
            "indented less than its opening fence",
        ),
        (
            (
                "- Item\n\n  ```text\n  inside\n```\nprose\n```\n"
                "```cpp\nint answer();\n```\n"
            ),
            "indented less than its opening fence",
        ),
    ],
)
def test_document_parse_faults_are_diagnostic(document, text, expected):
    document.write("guide.md", text)
    document.configure(DOC_CALL, expected=expected)


def test_missing_stale_and_duplicate_harness_contracts(document):
    text = "<!-- example: answer -->\n```cpp\nint answer() { return 1; }\n```\n"
    document.write("guide.md", text)
    document.write("harness/stale.cpp", '#include "stale.inc"\n')
    document.configure(DOC_CALL, expected="names no example")
    (document.root / "harness/stale.cpp").unlink()
    (document.root / "harness/answer.cpp").unlink()
    document.configure(DOC_CALL, expected="has no harness")
    document.write("harness/answer.cpp", '#include "answer.inc"\n')
    document.write("guide.md", text + text)
    document.configure(DOC_CALL, expected="is named twice")


def test_document_examples_use_the_platform_strict_target(document):
    document.write(
        "guide.md",
        """<!-- example: answer -->
```cpp
[[nodiscard]] int refuse();
void caller() { refuse(); }
```
""",
    )
    document.configure(DOC_CALL)
    document.compile(expected="unused-result")


def test_document_groups_are_declared_and_compiled_separately(document):
    document.write(
        "guide.md",
        """<!-- example: answer -->
```cpp
int answer() { return 1; }
```
<!-- example: alternate/other -->
```cpp
int other() { return 2; }
```
""",
    )
    document.write("alternate/other.cpp", '#include "other.inc"\n')
    first = DOC_CALL.replace(
        "DOCUMENTS guide.md",
        "DOCUMENTS guide.md GROUP_DOCUMENTS guide.md",
    )
    second = """
house_cxx_add_doc_examples(alternate_examples PACKAGE doc GROUP alternate
    GROUPS alternate DOCUMENTS guide.md HARNESS_DIR alternate)
"""
    document.configure(first + second)
    document.compile()
    assert (document.build / "examples/answer.inc").is_file()
    assert not (document.build / "examples/other.inc").exists()
    assert (document.build / "alternate_examples/other.inc").is_file()
    assert not (document.build / "alternate_examples/answer.inc").exists()
    document.configure(DOC_CALL + second, expected="not among the GROUP_DOCUMENTS")
    document.configure(
        first + second.replace("GROUP alternate", "GROUP unknown"),
        expected="GROUP 'unknown' is not a group",
    )
    document.configure(
        first
        + second.replace("GROUP alternate", "GROUP alternate GROUP_DOCUMENTS guide.md"),
        expected="GROUP_DOCUMENTS is the ungrouped call's",
    )
    (document.root / "alternate/other.cpp").unlink()
    document.configure(first + second, expected="has no harness")


@pytest.mark.parametrize("order", ["guide.md other.md", "other.md guide.md"])
def test_names_are_unique_across_documents_and_groups(document, order):
    document.write(
        "guide.md",
        """<!-- example: alternate/answer -->
```cpp
int alternate() { return 1; }
```
""",
    )
    document.write(
        "other.md",
        """<!-- example: answer -->
```cpp
int answer() { return 1; }
```
""",
    )
    call = DOC_CALL.replace(
        "DOCUMENTS guide.md",
        "DOCUMENTS " + order + " GROUP_DOCUMENTS guide.md",
    )
    document.configure(call, expected="is named twice")
