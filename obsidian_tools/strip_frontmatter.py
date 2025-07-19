"""
Recursively scans a directory for Markdown files and strips YAML frontmatter
from each file, leaving only the body content.

This script removes the YAML frontmatter block (everything between the first
pair of '---' delimiters) from Markdown files, keeping only the main content.

Usage:
    uv run strip_frontmatter.py /path/to/flashcards
    uv run strip_frontmatter.py /path/to/flashcards --go
    uv run strip_frontmatter.py --go  # Uses FLASHCARDS_PATH or VAULT_PATH/flashcards
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from beartype import beartype

from obsidian_tools.common import (
    backup_file,
    ask_user_confirmation,
    find_markdown_files,
    _strip_frontmatter,
)
from obsidian_tools.logging_utils import setup_logging


@beartype
def process_file(file_path: Path) -> str | None:
    """
    Analyzes a single Markdown file and removes YAML frontmatter.
    Returns the modified content or None if no changes needed.
    """
    try:
        original_content = file_path.read_text("utf-8")
    except UnicodeDecodeError:
        logger.warning(f"Skipping {file_path} due to encoding error.")
        return None

    # Use the existing _strip_frontmatter function from common.py
    stripped_content = _strip_frontmatter(original_content)

    # Only return content if it was actually modified
    if stripped_content != original_content:
        return stripped_content

    return None


@beartype
def main(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Directory containing Markdown files to process. Defaults to FLASHCARDS_PATH env var or VAULT_PATH/flashcards.",
    ),
    go: bool = typer.Option(
        False,
        "--go",
        help="Apply changes to files. Defaults to a dry run.",
    ),
):
    """Main function to parse arguments and run the script."""
    log_dir = setup_logging("strip_frontmatter")
    logger.info("Starting frontmatter stripping script...")
    if not go:
        logger.info("Running in dry-run mode. No files will be modified.")

    if directory is None:
        # Check for FLASHCARDS_PATH first, then fall back to VAULT_PATH/flashcards
        flashcards_path = os.getenv("FLASHCARDS_PATH")
        if flashcards_path:
            directory = Path(flashcards_path)
            logger.info(f"Using FLASHCARDS_PATH: {directory}")
        else:
            vault_path = os.getenv("VAULT_PATH", ".")
            directory = Path(vault_path) / "flashcards"
            logger.info(f"Using default flashcards directory: {directory}")

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

    md_files = find_markdown_files(directory)
    files_to_modify = {}
    files_with_errors = 0
    files_successfully_modified = 0

    for file_path in md_files:
        try:
            new_content = process_file(file_path)
            if new_content is not None:
                files_to_modify[file_path] = new_content
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            files_with_errors += 1

    if not files_to_modify:
        logger.info("No files found with YAML frontmatter to strip.")
    else:
        logger.info(
            f"Found {len(files_to_modify)} files with YAML frontmatter to strip."
        )

    if go and files_to_modify:
        if not ask_user_confirmation(
            f"About to strip frontmatter from {len(files_to_modify)} files. Are you sure?"
        ):
            logger.info("User cancelled operation.")
            return

        for file_path, new_content in files_to_modify.items():
            try:
                backup_path = backup_file(file_path, log_dir)
                logger.debug(f"Backed up {file_path} to {backup_path}")
                file_path.write_text(new_content, "utf-8")
                logger.info(f"Successfully stripped frontmatter from {file_path}")
                files_successfully_modified += 1
            except IOError as e:
                logger.error(f"Error writing to {file_path}: {e}")
                files_with_errors += 1
    elif not go and files_to_modify:
        logger.info("Dry run complete. The following files would be modified:")
        for file_path in files_to_modify:
            logger.info(f"- {file_path}")

    # Print summary statistics
    logger.info("=" * 50)
    logger.info("SUMMARY STATISTICS")
    logger.info("=" * 50)
    logger.info(f"Total markdown files scanned: {len(md_files)}")
    logger.info(f"Files with frontmatter found: {len(files_to_modify)}")
    logger.info(
        f"Files without frontmatter: {len(md_files) - len(files_to_modify) - files_with_errors}"
    )
    if go:
        logger.info(f"Files successfully modified: {files_successfully_modified}")
        if files_with_errors > 0:
            logger.info(f"Files with errors: {files_with_errors}")
    else:
        logger.info("Mode: DRY RUN (use --go to apply changes)")
    logger.info("=" * 50)

    logger.info("Frontmatter stripping complete.")


if __name__ == "__main__":
    typer.run(main)
