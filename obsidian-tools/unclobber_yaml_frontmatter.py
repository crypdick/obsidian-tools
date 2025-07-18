"""
Recursively scans a directory for Markdown files and merges multiple
YAML frontmatter blocks into a single block.

This script is designed to fix "clobbered" frontmatter that can occur
during version control merges, where a file might end up with duplicated
or concatenated frontmatter sections.

Usage:
    python unclobber_yaml_frontmatter.py /path/to/vault
    python unclobber_yaml_frontmatter.py /path/to/vault --dry-run
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter
import re


# Add a representer to handle set -> list conversion for clean YAML output
def represent_set_as_list(representer: RoundTripRepresenter, data: set):
    return representer.represent_list(sorted(list(data)))


RoundTripRepresenter.add_representer(set, represent_set_as_list)


def is_datestamp(value: Any) -> bool:
    """Check if a value is a string that looks like a datetime."""
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def merge_frontmatters(blocks: List[Dict[str, Any]], file_path: Path) -> Dict[str, Any]:
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
                merged[key] = min(existing, value)
            elif isinstance(existing, list) and isinstance(value, list):
                merged[key] = sorted(list(set(existing) | set(value)))
            elif isinstance(existing, list) and not isinstance(value, list):
                # If one is a list and the other isn't, merge the scalar into the list
                merged[key] = sorted(list(set(existing) | {value}))
            elif not isinstance(existing, list) and isinstance(value, list):
                merged[key] = sorted(list(set(value) | {existing}))
            elif existing != value:
                print(f"\nConflict for key '{key}' in {file_path}")
                print(f"  1: {existing}")
                print(f"  2: {value}")
                choice = ""
                while choice not in ["1", "2"]:
                    choice = input("Choose which value to keep (1 or 2): ")
                if choice == "2":
                    merged[key] = value
    return merged


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
        for line in yaml_str.splitlines():
            if re.match(pattern, line, flags=re.IGNORECASE):
                # Explicit null detected; this key is fine
                break
        else:
            # No matching explicit null line => implicit null
            return True
    return False


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

    for i, part in enumerate(parts):
        if is_body:
            body_content_parts.append(part)
            continue
        try:
            # A part is considered frontmatter if it's valid YAML.
            # Once we hit non-YAML, we assume it's the start of the body.
            data = yaml.safe_load(io.StringIO(part))
            if isinstance(data, dict):
                # Treat as front-matter only if it **does not** contain implicit nulls.
                if contains_implicit_null(part, data):
                    is_body = True
                    body_content_parts.append(part)
                else:
                    frontmatters.append(data)
            else:  # Not a dictionary, probably body content
                is_body = True
                body_content_parts.append(part)

        except (yaml.YAMLError, AttributeError):
            is_body = True
            body_content_parts.append(part)

    # Re-join the body parts with the original delimiter
    body = "\n---\n".join(body_content_parts)
    return frontmatters, body.strip()


def process_file(file_path: Path, dry_run: bool = False) -> None:
    """
    Analyzes a single Markdown file for multiple frontmatter blocks,
    merges them, and rewrites the file.
    """
    try:
        original_content = file_path.read_text("utf-8")
    except UnicodeDecodeError:
        print(f"Warning: Skipping {file_path} due to encoding error.", file=sys.stderr)
        return

    frontmatters, body = extract_frontmatter_and_body(original_content)

    if len(frontmatters) <= 1:
        return  # No duplicates found, nothing to do

    print(f"Found {len(frontmatters)} frontmatter blocks in: {file_path}")

    merged_fm = merge_frontmatters(frontmatters, file_path)

    # Use ruamel.yaml to dump with preserved formatting and order where possible
    yaml_dumper = YAML()
    yaml_dumper.indent(mapping=2, sequence=4, offset=2)
    string_stream = io.StringIO()
    yaml_dumper.dump(merged_fm, string_stream)
    new_fm_str = string_stream.getvalue()

    new_content = f"---\n{new_fm_str}---\n\n{body}\n"

    if dry_run:
        print("--- [DRY-RUN] ORIGINAL ---")
        print(original_content[:500])
        print("--- [DRY-RUN] NEW ---")
        print(new_content[:500])
        print("-" * 20)
    else:
        try:
            file_path.write_text(new_content, "utf-8")
            print(f"Successfully merged and updated {file_path}")
        except IOError as e:
            print(f"Error writing to {file_path}: {e}", file=sys.stderr)


# --- File System Operations ---


def collect_markdown_files(root: Path) -> List[Path]:
    """Return a list of Markdown files in *root* **recursively**."""
    return [p for p in root.rglob("*.md") if p.is_file()]


# --- Main Execution ---


def main() -> None:
    """Main function to parse arguments and run the script."""
    parser = argparse.ArgumentParser(
        description="Unclobber YAML frontmatter in Markdown files.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "directory", help="Directory containing Markdown files to process."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files.",
    )
    args = parser.parse_args()

    target_dir = Path(args.directory).expanduser().resolve()
    if not target_dir.is_dir():
        sys.exit(f"Error: Not a valid directory: {target_dir}")

    print(f"Scanning for Markdown files in: {target_dir}")
    md_files = collect_markdown_files(target_dir)

    if not md_files:
        print("No Markdown files found. Nothing to do.")
        return

    print(f"Found {len(md_files)} Markdown files to check.")
    for file_path in md_files:
        try:
            process_file(file_path, dry_run=args.dry_run)
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)

    print("\nScan complete.")


if __name__ == "__main__":
    main()
