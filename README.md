# Obsidian Tools

Scripts to help manage my Obsidian 2nd brain

- `add_dataview_limits.py`: Recursively scans markdown files in an Obsidian vault and appends `LIMIT 1000` (configurable) to Dataview queries that lack a limit; supports `--dry-run` for preview-only mode. This is useful to prevent memory leaks from larger queries.
- `dedup.py`: Deduplicates Markdown files in a directory by content, keeping a single canonical copy (preferably the one without or with the lowest numeric suffix), deleting the rest, and optionally renaming the survivor; supports `--dry-run` to preview actions without making changes.

