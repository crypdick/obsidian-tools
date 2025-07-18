from __future__ import annotations

import shutil
import hashlib
from pathlib import Path
from typing import Any
from loguru import logger
from datetime import datetime
from beartype import beartype


@beartype
def backup_file(file_path: Path, backup_dir: Path) -> Path:
    """Backs up a file to the specified backup directory."""
    backup_file_path = backup_dir / file_path.name
    shutil.copy2(file_path, backup_file_path)
    return backup_file_path


@beartype
def ask_user_confirmation(prompt: str) -> bool:
    """Asks the user for confirmation."""
    response = input(f"{prompt} [N/y] ").lower()
    return response == "y"


@beartype
def find_markdown_files(root: Path) -> list[Path]:
    """Recursively find all Markdown files in a directory."""
    logger.info(f"Searching for markdown files in {root}...")
    files = list(root.rglob("*.md"))
    logger.info(f"Found {len(files)} markdown files.")
    return files


@beartype
def _strip_frontmatter(text: str) -> str:
    """Return *text* with leading YAML frontmatter removed if present."""
    if not text.lstrip().startswith("---"):
        return text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[idx + 1 :])

    return text


@beartype
def compute_hash(path: Path) -> str:
    """Return SHA-256 hash of a Markdown file **excluding YAML frontmatter**."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_bytes().decode("utf-8", errors="replace")
        logger.warning(
            f"File {path} was not valid UTF-8. Used replacement characters for hashing."
        )

    content_without_frontmatter = _strip_frontmatter(text)
    return hashlib.sha256(content_without_frontmatter.encode("utf-8")).hexdigest()


@beartype
def is_datestamp(value: Any) -> bool:
    """Check if a value is a string that looks like a datetime."""
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False
