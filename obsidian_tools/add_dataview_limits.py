import typer
from pathlib import Path
from typing import List, Optional
import re
from loguru import logger
import os

from beartype import beartype

from .common import backup_file, ask_user_confirmation, find_markdown_files
from .logging_utils import setup_logging

# Regular expressions for detecting dataview code blocks and limit clauses
START_BLOCK_RE = re.compile(r"^```\s*dataview\s*$", re.IGNORECASE)
END_BLOCK_RE = re.compile(r"^```\s*$")
LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)


@beartype
def process_file(path: Path, limit_value: int) -> Optional[str]:
    """Return the modified file content (or original if no change)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return None

    in_block = False
    limit_found = False
    modified = False
    output_lines: List[str] = []

    for line in lines:
        if not in_block and START_BLOCK_RE.match(line):
            in_block = True
            limit_found = False
        elif in_block:
            if END_BLOCK_RE.match(line):
                if not limit_found:
                    # Insert LIMIT clause before the closing ```
                    output_lines.append(f"LIMIT {limit_value}\n")
                    modified = True
                in_block = False
            elif LIMIT_RE.search(line):
                limit_found = True
        output_lines.append(line)

    if modified:
        return "".join(output_lines)
    return None


@beartype
def main(
    vault_path: Optional[Path] = typer.Option(
        None,
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        help="Path to the Obsidian vault. Overrides the VAULT_PATH environment variable.",
    ),
    limit: int = typer.Option(
        1000, "--limit", "-l", help="Value for the LIMIT clause."
    ),
    go: bool = typer.Option(
        False,
        "--go",
        help="Actually modify files. Defaults to a dry run.",
    ),
):
    """Append LIMIT to Obsidian Dataview queries recursively."""
    log_dir = setup_logging("add_dataview_limits")
    logger.info("Starting script...")

    if vault_path:
        vault = vault_path
    else:
        vault_env_path = os.getenv("VAULT_PATH")
        if not vault_env_path:
            logger.error("VAULT_PATH environment variable not set.")
            raise typer.Exit(code=1)
        vault = Path(vault_env_path)

    if not go:
        logger.info("Running in dry-run mode. No files will be modified.")

    markdown_files = find_markdown_files(vault)
    files_to_modify = []

    for md_file in markdown_files:
        new_content = process_file(md_file, limit)
        if new_content:
            files_to_modify.append((md_file, new_content))
            logger.info(f"Identified file to modify: {md_file}")

    if not files_to_modify:
        logger.info("No files to modify.")
        return

    if go:
        if not ask_user_confirmation(
            f"About to modify {len(files_to_modify)} files. Are you sure?"
        ):
            logger.info("User cancelled operation.")
            return

        for md_file, new_content in files_to_modify:
            try:
                backup_path = backup_file(md_file, log_dir)
                logger.debug(f"Backed up {md_file} to {backup_path}")
                md_file.write_text(new_content, encoding="utf-8")
                logger.info(f"Updated {md_file}")
            except Exception as e:
                logger.error(f"Error updating {md_file}: {e}")
    else:
        logger.info("Dry run complete. The following files would be modified:")
        for md_file, _ in files_to_modify:
            logger.info(f"- {md_file}")

    logger.info("Script finished.")


if __name__ == "__main__":
    typer.run(main)
