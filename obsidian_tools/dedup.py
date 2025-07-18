"""Deduplicate Markdown files in a directory based on file contents.

Usage:
    python dedup.py /path/to/dir
    python dedup.py /path/to/dir --go     # DANGEROUS!
    python dedup.py --go                  # Uses VAULT_PATH env var

The script keeps **one** copy of each unique file content and removes the rest.
When several files share the same content, the file with the **lowest** numeric
suffix (or no suffix) is kept. If all copies have a numeric suffix (e.g.
"note (1).md", "note (2).md"), the surviving file will be **renamed** to drop
the suffix (→ "note.md") as long as doing so doesn't overwrite an existing
file.

Example ordering (lowest → highest suffix):
    note.md        (implicit suffix 0)
    note (1).md
    note (2).md

If all three share the same contents, only **note.md** remains.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from beartype import beartype

from obsidian_tools.common import (
    backup_file,
    ask_user_confirmation,
    find_markdown_files,
    compute_hash,
)
from obsidian_tools.logging_utils import setup_logging

# Matches both "file.md" and "file (123).md" (case-insensitive on extension)
NUMBERED_RE = re.compile(r"^(?P<stem>.*?)(?: \((?P<num>\d+)\))?\.md$", re.IGNORECASE)


@beartype
def numeric_suffix(filename: str) -> int:
    """Return numeric suffix if present, else 0."""
    match = NUMBERED_RE.match(filename)
    if match:
        num = match.group("num")
        return int(num) if num is not None else 0
    return 0


@beartype
def find_duplicates(md_files: list[Path]) -> dict[str, list[Path]]:
    """Group files by content hash. Returns {hash: [paths, ...]}"""
    buckets: dict[str, list[Path]] = {}
    for path in md_files:
        h = compute_hash(path)
        buckets.setdefault(h, []).append(path)
    # Filter out non-duplicates
    return {h: paths for h, paths in buckets.items() if len(paths) > 1}


app = typer.Typer()


@app.command()
def main(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Directory containing Markdown files to deduplicate. If not provided, uses VAULT_PATH.",
    ),
    go: bool = typer.Option(
        False,
        "--go",
        help="Apply changes to files. Defaults to a dry run.",
    ),
):
    """Deduplicate Markdown files by content."""
    log_dir = setup_logging("dedup")
    logger.info("Starting deduplication...")
    if not go:
        logger.info("Running in dry-run mode. No files will be modified.")

    if directory is None:
        vault_path = os.getenv("VAULT_PATH")
        if not vault_path:
            logger.error(
                "No directory specified and VAULT_PATH environment variable not set."
            )
            raise typer.Exit(1)
        directory = Path(vault_path)
        logger.info(f"Using directory from VAULT_PATH: {directory}")

    # Validate the directory
    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        raise typer.Exit(1)

    if not directory.is_dir():
        logger.error(f"Path is not a directory: {directory}")
        raise typer.Exit(1)

    if not os.access(directory, os.R_OK | os.W_OK):
        logger.error(f"Directory is not readable/writable: {directory}")
        raise typer.Exit(1)

    logger.info(f"Processing directory: {directory}")

    md_files = find_markdown_files(directory)
    if not md_files:
        logger.info("No Markdown files found. Exiting.")
        return

    dup_groups = find_duplicates(md_files)
    to_delete: list[Path] = []
    rename_actions: list[tuple[Path, Path]] = []

    for h, paths in dup_groups.items():
        # Sort by numeric suffix first, then by path length (prefer shorter paths/closer to root)
        paths.sort(key=lambda p: (numeric_suffix(p.name), len(str(p))))
        keep_path = paths[0]
        for p in paths[1:]:
            to_delete.append(p)

        if numeric_suffix(keep_path.name) > 0:
            stem_match = NUMBERED_RE.match(keep_path.name)
            if stem_match:
                unsuffixed_name = f"{stem_match.group('stem')}.md"
                dest_path = keep_path.with_name(unsuffixed_name)
                # Only add rename action if destination doesn't exist
                if not dest_path.exists():
                    rename_actions.append((keep_path, dest_path))
                    # The file to be renamed should not be deleted
                    if keep_path in to_delete:
                        to_delete.remove(keep_path)

    if not to_delete and not rename_actions:
        logger.info("No duplicates found.")
        return

    if go:
        if not ask_user_confirmation(
            f"About to delete {len(to_delete)} and rename {len(rename_actions)} files. Are you sure?"
        ):
            logger.info("User cancelled operation.")
            return

        for src, dest in rename_actions:
            if dest.exists():
                logger.warning(
                    f"Skipping rename of {src.name} -> {dest.name}: destination exists."
                )
                continue
            try:
                backup_path = backup_file(src, log_dir)
                logger.debug(f"Backed up {src} to {backup_path}")
                src.rename(dest)
                logger.info(f"Renamed {src.name} -> {dest.name}")
            except OSError as e:
                logger.error(f"Failed to rename {src} -> {dest}: {e}")

        for path in to_delete:
            try:
                backup_path = backup_file(path, log_dir)
                logger.debug(f"Backed up {path} to {backup_path}")
                path.unlink()
                logger.info(f"Deleted {path}")
            except OSError as e:
                logger.error(f"Failed to delete {path}: {e}")
    else:
        logger.info("Dry run complete. The following actions would be taken:")
        for path in to_delete:
            logger.info(f"- Would delete: {path}")
        for src, dest in rename_actions:
            logger.info(f"- Would rename: {src.name} -> {dest.name}")

    logger.info("Deduplication finished.")


if __name__ == "__main__":
    app()
