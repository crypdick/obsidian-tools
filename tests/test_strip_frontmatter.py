from pathlib import Path
import tempfile
from obsidian_tools.strip_frontmatter import process_file


def test_strip_frontmatter_basic():
    """Test basic frontmatter stripping functionality."""
    content_with_frontmatter = """---
title: Test Note
tags: [test, example]
created: 2023-01-01
---

# This is the main content

Some body text here.
"""

    expected_content = """# This is the main content

Some body text here."""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content_with_frontmatter)
        temp_path = Path(f.name)

    try:
        result = process_file(temp_path)
        assert result is not None
        assert result.strip() == expected_content.strip()
    finally:
        temp_path.unlink()


def test_strip_frontmatter_no_frontmatter():
    """Test that files without frontmatter are left unchanged."""
    content_without_frontmatter = """# This is a regular markdown file

No frontmatter here, just content.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content_without_frontmatter)
        temp_path = Path(f.name)

    try:
        result = process_file(temp_path)
        assert result is None  # No changes needed
    finally:
        temp_path.unlink()


def test_strip_frontmatter_empty_file():
    """Test handling of empty files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("")
        temp_path = Path(f.name)

    try:
        result = process_file(temp_path)
        assert result is None  # No changes needed
    finally:
        temp_path.unlink()


def test_strip_frontmatter_only_frontmatter():
    """Test files that contain only frontmatter."""
    content_only_frontmatter = """---
title: Test Note
tags: [test, example]
---"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content_only_frontmatter)
        temp_path = Path(f.name)

    try:
        result = process_file(temp_path)
        assert result is not None
        assert result.strip() == ""
    finally:
        temp_path.unlink()
