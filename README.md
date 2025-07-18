# Obsidian Tools

Scripts to help manage my Obsidian 2nd brain

- `add_dataview_limits.py`: Recursively scans markdown files in an Obsidian vault and appends `LIMIT 1000` (configurable) to Dataview queries that lack a limit; supports `--dry-run` for preview-only mode. This is useful to prevent memory leaks from larger queries.
- `dedup.py`: Deduplicates Markdown files in a directory by content, keeping a single canonical copy (preferably the one without or with the lowest numeric suffix), deleting the rest, and optionally renaming the survivor; supports `--dry-run` to preview actions without making changes.
- `unclobber_yaml_frontmatter.py`: Fixes duplicate or clobbered YAML front-matter blocks (typically introduced by merge conflicts). The script merges all front-matter sections found at the top of a Markdown file, resolves conflicts (earliest timestamps, union of lists, prompts for manual choice on other types), and rewrites the file with a single clean front-matter block; supports `--dry-run` for preview-only mode.
 
## Installation

```bash
# Create (or update) the project environment and install all runtime + dev deps
uv pip install -r pyproject.toml --extra dev

# Register the Git hooks provided by pre-commit
uvx pre-commit install
```

### Running the linters & formatter

```bash
# Execute the full pre-commit suite across all files
uvx pre-commit run --all-files
```

