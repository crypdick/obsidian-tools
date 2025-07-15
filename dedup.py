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
import re
import sys
import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Matches both "file.md" and "file (123).md" (case-insensitive on extension)
NUMBERED_RE = re.compile(r"^(?P<stem>.*?)(?: \((?P<num>\d+)\))?\.md$", re.IGNORECASE)


def _strip_frontmatter(text: str) -> str:
    """Return *text* with leading YAML frontmatter removed if present.

    YAML frontmatter is defined as a block that starts at the very first line
    with a line consisting solely of three dashes ("---") and ends at the
    next line that is also exactly "---". Both delimiter lines (opening and
    closing) are removed along with the lines in-between. Whitespace surrounding
    the dashes is ignored.
    """

    if not text.lstrip().startswith("---"):
        return text  # Quick exit – no leading frontmatter

    # Work line-by-line to locate the closing delimiter.
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text  # Safety check – unexpected, but abort stripping

    # Find the index of the closing '---'. Start searching from line 1.
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            # Return everything after the closing delimiter.
            return "".join(lines[idx + 1 :])

    # No closing delimiter – treat file as-is to avoid data loss.
    return text


def compute_hash(path: Path) -> str:
    """Return SHA-256 hash of a Markdown file **excluding YAML frontmatter**."""

    text: str
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback: read as binary and decode with replacement to ensure we can hash.
        text = path.read_bytes().decode("utf-8", errors="replace")

    content_without_frontmatter = _strip_frontmatter(text)

    return hashlib.sha256(content_without_frontmatter.encode("utf-8")).hexdigest()


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
    parser = argparse.ArgumentParser(
        description="Deduplicate Markdown files by content."
    )
    parser.add_argument(
        "directory", help="Directory containing Markdown files to deduplicate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deletions without removing files",
    )
    args = parser.parse_args()

    target_dir = Path(args.directory).expanduser().resolve()
    if not target_dir.is_dir():
        sys.exit(f"Error: {target_dir} is not a valid directory")

    md_files = collect_markdown_files(target_dir)
    initial_file_count = len(md_files)
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
    skipped_renames = 0  # Count of rename attempts skipped due to existing destination
    skipped_examples: List[str] = []  # Short console messages for first few skips
    sample_entries = []  # Detailed info (path, hash, snippets) for log file
    for src, dest in rename_actions:
        # Skip if we aren't keeping this src (it might have been deleted due
        # to earlier hash collision logic, though unlikely) or if dest exists.
        if dest.exists():
            # Record statistics & a few illustrative examples for debugging.
            skipped_renames += 1
            if len(skipped_examples) < 5:  # limit to first few to avoid spam
                try:
                    src_hash = compute_hash(src)[:8]
                    dest_hash = compute_hash(dest)[:8]
                except Exception:
                    src_hash = dest_hash = "<error>"
                skipped_examples.append(
                    f"- {src} (hash {src_hash}) vs {dest} (hash {dest_hash})"
                )

                if len(sample_entries) < 5:

                    def _snippet(path: Path, max_chars: int = 2000) -> str:
                        try:
                            return path.read_text(encoding="utf-8")[:max_chars]
                        except UnicodeDecodeError:
                            return path.read_bytes().decode("utf-8", errors="replace")[
                                :max_chars
                            ]

                    sample_entries.append(
                        {
                            "src": src,
                            "dest": dest,
                            "src_hash": src_hash,
                            "dest_hash": dest_hash,
                            "src_snip": _snippet(src),
                            "dest_snip": _snippet(dest),
                        }
                    )

            if args.dry_run:
                print(f"[dry-run] Skipping rename: {dest} already exists.")
            else:
                print(
                    f"Skipping rename of {src.name} → {dest.name}: destination exists."
                )
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
        print(f"Starting with {initial_file_count} file(s).")
        print(f"{len(to_delete)} file(s) would be deleted.")
        print(f"Ending with {initial_file_count - len(to_delete)} file(s).")
        print(
            f"{rename_count if rename_count else len(rename_actions)} file(s) would be renamed (subject to collisions)."
        )
    else:
        print(f"Started with {initial_file_count} file(s).")
        print(f"{len(to_delete)} file(s) deleted.")
        print(f"Ended with {initial_file_count - len(to_delete)} file(s).")
        print(f"{rename_count} file(s) renamed.")

        # --- Debug information -------------------------------------------------
        if skipped_examples:
            print("\nExample skipped renames (source vs destination):")
            for example in skipped_examples:
                print(example)
            remaining = skipped_renames - len(skipped_examples)
            if remaining > 0:
                print(f"...and {remaining} more skip(s) not shown.")

        # Write detailed log file with content snippets for debugging
        if sample_entries:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            repo_root = Path(__file__).resolve().parent
            log_path = repo_root / f"skipped_renames_{timestamp}.log"
            try:
                with log_path.open("w", encoding="utf-8") as lf:
                    lf.write(
                        "This log contains up to five examples where a rename was\n"
                        "skipped because the destination file already existed with\n"
                        "different content. Contents are truncated to the first 2000\n"
                        " characters to keep the log manageable.\n\n"
                    )
                    for idx, entry in enumerate(sample_entries, 1):
                        lf.write(f"===== Example {idx} =====\n")
                        lf.write(f"Source: {entry['src']}\n")
                        lf.write(f"Destination: {entry['dest']}\n")
                        lf.write(f"Source hash: {entry['src_hash']}\n")
                        lf.write(f"Destination hash: {entry['dest_hash']}\n\n")
                        lf.write("--- Source content (truncated) ---\n")
                        lf.write(entry["src_snip"] + "\n")
                        lf.write("--- Destination content (truncated) ---\n")
                        lf.write(entry["dest_snip"] + "\n\n")

                print(f"Detailed skip log written to: {log_path}")
            except OSError as exc:
                print(f"Failed to write log file {log_path}: {exc}")


if __name__ == "__main__":
    main()
