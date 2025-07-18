import argparse
import re
from pathlib import Path
from typing import List
import sys
import difflib

# Regular expressions for detecting dataview code blocks and limit clauses
START_BLOCK_RE = re.compile(r"^```\s*dataview\s*$", re.IGNORECASE)
END_BLOCK_RE = re.compile(r"^```\s*$")
LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)


def find_markdown_files(root: Path) -> List[Path]:
    """Recursively collect all markdown files under *root*."""
    return [p for p in root.rglob("*.md") if p.is_file()]


def process_file(path: Path, limit_value: int) -> str:
    """Return the modified file content (or original if no change)."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    in_block = False
    limit_found = False
    modified = False
    output_lines: List[str] = []

    for line in lines:
        # Enter dataview block
        if not in_block and START_BLOCK_RE.match(line):
            in_block = True
            limit_found = False
            output_lines.append(line)
            continue

        # Inside a dataview block
        if in_block:
            if END_BLOCK_RE.match(line):  # block ends here
                if not limit_found:
                    output_lines.append(f"LIMIT {limit_value}\n")
                    modified = True
                output_lines.append(line)
                in_block = False
                continue

            if LIMIT_RE.search(line):
                limit_found = True
            output_lines.append(line)
            continue

        # Normal line outside any block
        output_lines.append(line)

    if modified:
        return "".join(output_lines)
    return None  # type: ignore[return-value]


def apply_changes(file_path: Path, new_content: str, dry_run: bool):
    if dry_run:
        old_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=str(file_path),
            tofile=f"{file_path} (modified)",
        )
        sys.stdout.writelines(diff)
    else:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Updated {file_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Append LIMIT to Obsidian Dataview queries recursively."
    )
    parser.add_argument(
        "vault",
        nargs="?",
        default=Path(".").resolve(),
        type=Path,
        help="Path to the Obsidian vault (defaults to current directory)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Value for the LIMIT clause (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the diff instead of modifying files",
    )

    args = parser.parse_args()
    vault_path: Path = args.vault.expanduser().resolve()

    if not vault_path.exists():
        print(f"Vault path {vault_path} does not exist", file=sys.stderr)
        sys.exit(1)

    markdown_files = find_markdown_files(vault_path)
    if not markdown_files:
        print("No markdown files found.")
        return

    for md_file in markdown_files:
        new_content = process_file(md_file, args.limit)
        if new_content is not None:
            apply_changes(md_file, new_content, args.dry_run)

    if args.dry_run:
        print("\nDry run complete. No files were modified.")


if __name__ == "__main__":
    main()
