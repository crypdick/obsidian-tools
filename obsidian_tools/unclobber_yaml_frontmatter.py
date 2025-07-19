"""
Recursively scans a directory for Markdown files and merges multiple
YAML frontmatter blocks into a single block.

This script is designed to fix "clobbered" frontmatter that can occur
during version control merges, where a file might end up with duplicated
or concatenated frontmatter sections.

Usage:
    uv run unclobber_yaml_frontmatter.py /path/to/vault
    uv run unclobber_yaml_frontmatter.py /path/to/vault --go
    uv run unclobber_yaml_frontmatter.py --go  # Uses VAULT_PATH env var
"""

from __future__ import annotations
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml
from loguru import logger
from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

from beartype import beartype

from obsidian_tools.common import (
    backup_file,
    ask_user_confirmation,
    find_markdown_files,
    is_datestamp,
)
from obsidian_tools.logging_utils import setup_logging


# Add a representer to handle set -> list conversion for clean YAML output
@beartype
def represent_set_as_list(representer: RoundTripRepresenter, data: set):
    return representer.represent_list(sorted(list(data)))


RoundTripRepresenter.add_representer(set, represent_set_as_list)


@beartype
def merge_frontmatters(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple frontmatter blocks into one, handling conflicts."""
    merged: Dict[str, Any] = {}
    for block in blocks:
        for key, value in block.items():
            if key not in merged:
                merged[key] = value
                continue

            # --- Conflict Resolution ---
            existing = merged[key]
            if is_datestamp(existing) and is_datestamp(value):
                merged[key] = max(existing, value)  # Keep the most recent
            elif isinstance(existing, list) and isinstance(value, list):
                merged[key] = sorted(list(set(existing) | set(value)))
            elif isinstance(existing, list):
                merged[key] = sorted(list(set(existing) | {value}))
            elif isinstance(value, list):
                merged[key] = sorted(list(set(value) | {existing}))
            elif existing != value:
                logger.warning(
                    f"Conflict for key '{key}'. Using new value '{value}' over old value '{existing}'."
                )
                merged[key] = value
    return merged


@beartype
def contains_implicit_null(yaml_str: str, data: Dict[str, Any]) -> bool:
    """Return True if *data* has any keys that map to an **implicit** null value.

    An implicit null occurs when the original YAML had a key followed directly
    by a newline (e.g. ``question:``). Explicit nulls such as ``key: null`` or
    ``key: ~`` are **not** considered implicit and therefore still valid.
    """
    for key, value in data.items():
        if value is not None:
            # Non-null value → definitely explicit
            continue
        pattern = rf"^\s*{re.escape(str(key))}\s*:\s*(null|~)\s*$"
        if not any(
            re.match(pattern, line, flags=re.IGNORECASE)
            for line in yaml_str.splitlines()
        ):
            # No matching explicit null line => implicit null
            return True
    return False


@beartype
def extract_frontmatter_and_body(text: str) -> tuple[list[dict], str]:
    """
    Parses and extracts all consecutive YAML frontmatter blocks from the start
    of a text, separating them from the body.
    """
    if not text.lstrip().startswith("---"):
        return [], text

    # Split by the YAML delimiter '---' on its own line.
    # The first element will be empty if the file starts with '---'.
    parts = text.split("\n---\n")

    if not parts or (len(parts) == 1 and not parts[0].strip()):
        return [], text  # Empty file or just '---'

    # Handle the case where the file starts with '---'
    if parts[0].strip() == "":
        parts.pop(0)

    frontmatters = []
    body_content_parts = []
    is_body = False

    for part in parts:
        if is_body:
            body_content_parts.append(part)
            continue
        try:
            # A part is considered frontmatter if it's valid YAML.
            # Once we hit non-YAML, we assume it's the start of the body.
            data = yaml.safe_load(io.StringIO(part))
            if isinstance(data, dict) and not contains_implicit_null(part, data):
                frontmatters.append(data)
            else:
                is_body = True
                body_content_parts.append(part)

        except (yaml.YAMLError, AttributeError):
            is_body = True
            body_content_parts.append(part)

    # Re-join the body parts with the original delimiter
    body = "\n---\n".join(body_content_parts)
    return frontmatters, body.strip()


@beartype
def process_file(file_path: Path) -> str | None:
    """
    Analyzes a single Markdown file for multiple frontmatter blocks,
    merges them, and rewrites the file.
    """
    try:
        original_content = file_path.read_text("utf-8")
    except UnicodeDecodeError:
        logger.warning(f"Skipping {file_path} due to encoding error.")
        return None

    frontmatters, body = extract_frontmatter_and_body(original_content)

    if len(frontmatters) <= 1:
        return None

    logger.info(f"Found {len(frontmatters)} frontmatter blocks in: {file_path}")

    merged_fm = merge_frontmatters(frontmatters)

    # Use ruamel.yaml to dump with preserved formatting and order where possible
    yaml_dumper = YAML()
    yaml_dumper.indent(mapping=2, sequence=4, offset=2)
    string_stream = io.StringIO()
    yaml_dumper.dump(merged_fm, string_stream)
    new_fm_str = string_stream.getvalue()

    return f"---\n{new_fm_str}---\n\n{body}\n"


# --- File System Operations ---


@beartype
def main(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Directory containing Markdown files to process. Defaults to VAULT_PATH.",
    ),
    go: bool = typer.Option(
        False,
        "--go",
        help="Apply changes to files. Defaults to a dry run.",
    ),
):
    """Main function to parse arguments and run the script."""
    log_dir = setup_logging("unclobber_yaml")
    logger.info("Starting script...")
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

    md_files = find_markdown_files(directory)
    files_to_modify = {}

    for file_path in md_files:
        try:
            new_content = process_file(file_path)
            if new_content:
                files_to_modify[file_path] = new_content
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    if not files_to_modify:
        logger.info("No files to modify.")
        return

    if go:
        if not ask_user_confirmation(
            f"About to modify {len(files_to_modify)} files. Are you sure?"
        ):
            logger.info("User cancelled operation.")
            return

        for file_path, new_content in files_to_modify.items():
            try:
                backup_path = backup_file(file_path, log_dir)
                logger.debug(f"Backed up {file_path} to {backup_path}")
                file_path.write_text(new_content, "utf-8")
                logger.info(f"Successfully merged and updated {file_path}")
            except IOError as e:
                logger.error(f"Error writing to {file_path}: {e}")
    else:
        logger.info("Dry run complete. The following files would be modified:")
        for file_path in files_to_modify:
            logger.info(f"- {file_path}")

    logger.info("Scan complete.")


if __name__ == "__main__":
    typer.run(main)
