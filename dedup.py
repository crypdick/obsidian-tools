#!/usr/bin/env python3
"""Deduplicate Markdown files in a directory based on file contents.

Usage:
    python dedup.py /path/to/dir               # perform deletion (recursive)
    python dedup.py /path/to/dir --dry-run     # preview deletions (recursive)

The script keeps **one** copy of each unique file content and removes the rest.
When several files share the same content, the file with the **lowest** numeric
suffix (or no suffix) is kept. If all copies have a numeric suffix (e.g.
"note (1).md", "note (2).md"), the surviving file will be **renamed** to drop
the suffix (→ "note.md") as long as doing so doesn’t overwrite an existing
file.

Example ordering (lowest → highest suffix):
    note.md        (implicit suffix 0)
    note (1).md
    note (2).md

If all three share the same contents, only **note.md** remains.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Matches both "file.md" and "file (123).md" (case-insensitive on extension)
NUMBERED_RE = re.compile(r"^(?P<stem>.*?)(?: \((?P<num>\d+)\))?\.md$", re.IGNORECASE)


def compute_hash(path: Path, block_size: int = 1 << 20) -> str:
    """Return SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(block_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def numeric_suffix(filename: str) -> int:
    """Return numeric suffix if present, else 0.

    Examples:
        "note.md"        -> 0
        "note (1).md"    -> 1
        "note (12).md"   -> 12
    """
    match = NUMBERED_RE.match(filename)
    if match:
        num = match.group("num")
        return int(num) if num is not None else 0
    return 0  # Fallback when pattern doesn't match


def find_duplicates(md_files: List[Path]) -> Dict[str, List[Path]]:
    """Group files by content hash. Returns {hash: [paths, ...]}"""
    buckets: Dict[str, List[Path]] = {}
    for path in md_files:
        h = compute_hash(path)
        buckets.setdefault(h, []).append(path)
    return buckets


def collect_markdown_files(root: Path) -> List[Path]:
    """Return a list of Markdown files in *root* **recursively**."""
    # Path.rglob traverses sub-directories too; filter on case-insensitive extension.
    return [p for p in root.rglob("*.md") if p.is_file()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate Markdown files by content.")
    parser.add_argument("directory", help="Directory containing Markdown files to deduplicate")
    parser.add_argument("--dry-run", action="store_true", help="Preview deletions without removing files")
    args = parser.parse_args()

    target_dir = Path(args.directory).expanduser().resolve()
    if not target_dir.is_dir():
        sys.exit(f"Error: {target_dir} is not a valid directory")

    md_files = collect_markdown_files(target_dir)
    if not md_files:
        print("No Markdown files found – nothing to do.")
        return

    dup_groups = find_duplicates(md_files)

    to_delete: List[Path] = []
    rename_actions: List[Tuple[Path, Path]] = []  # (src, dest)
    for paths in dup_groups.values():
        if len(paths) < 2:
            continue  # unique file – nothing to dedupe

        # Sort by numeric suffix ascending (0,1,2,...) so index 0 is the
        # preferred survivor.
        paths.sort(key=lambda p: numeric_suffix(p.name))

        keep_path = paths[0]
        to_delete.extend(paths[1:])

        # Attempt to drop numeric suffix if the kept file still has one.
        if numeric_suffix(keep_path.name) > 0:
            # Build unsuffixed filename (e.g., "note.md")
            stem_match = NUMBERED_RE.match(keep_path.name)
            if stem_match:
                unsuffixed_name = f"{stem_match.group('stem')}.md"
                dest_path = keep_path.with_name(unsuffixed_name)
                rename_actions.append((keep_path, dest_path))

    if not to_delete:
        print("No duplicates detected – all good!")
        return

    for path in to_delete:
        if args.dry_run:
            print(f"[dry-run] Would delete: {path}")
        else:
            try:
                path.unlink()
                print(f"Deleted: {path}")
            except OSError as exc:
                print(f"Failed to delete {path}: {exc}")

    # Perform pending renames **after** deletions so we avoid collisions with
    # filenames that were just removed.
    rename_count = 0
    for src, dest in rename_actions:
        # Skip if we aren't keeping this src (it might have been deleted due
        # to earlier hash collision logic, though unlikely) or if dest exists.
        if dest.exists():
            if args.dry_run:
                print(f"[dry-run] Skipping rename: {dest} already exists.")
            else:
                print(f"Skipping rename of {src.name} → {dest.name}: destination exists.")
            continue

        if args.dry_run:
            print(f"[dry-run] Would rename: {src.name} → {dest.name}")
        else:
            try:
                src.rename(dest)
                print(f"Renamed: {src.name} → {dest.name}")
                rename_count += 1
            except OSError as exc:
                print(f"Failed to rename {src} → {dest}: {exc}")

    print("\nSummary:")
    if args.dry_run:
        print(f"{len(to_delete)} file(s) would be deleted.")
        print(f"{rename_count if rename_count else len(rename_actions)} file(s) would be renamed (subject to collisions).")
    else:
        print(f"{len(to_delete)} file(s) deleted.")
        print(f"{rename_count} file(s) renamed.")


if __name__ == "__main__":
    main()
