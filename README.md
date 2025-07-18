# Obsidian Tools

Scripts to help manage my Obsidian 2nd brain

- `add_dataview_limits.py`: Recursively scans markdown files in an Obsidian vault and appends `LIMIT 1000` (configurable) to Dataview queries that lack a limit. This is useful to prevent memory leaks from larger queries. Use `--go` to apply changes.
- `dedup.py`: Deduplicates Markdown files in a directory by content, keeping a single canonical copy (preferably the one without or with the lowest numeric suffix), deleting the rest, and optionally renaming the survivor. Use `--go` to apply changes.
- `unclobber_yaml_frontmatter.py`: Fixes duplicate or clobbered YAML front-matter blocks (typically introduced by merge conflicts). The script merges all front-matter sections found at the top of a Markdown file, resolves conflicts (earliest timestamps, union of lists, prompts for manual choice on other types), and rewrites the file with a single clean front-matter block. Use `--go` to apply changes.
 
## Installation

```bash
# Create (or update) the project environment and install all runtime + dev deps
uv pip install -e '.[dev]'

# Register the Git hooks provided by pre-commit
uvx pre-commit install
```

### Running the linters & formatter

```bash
# Execute the full pre-commit suite across all files
uvx pre-commit run --all-files
```

### Running the tests

```bash
# Run the tests
uv run pytest
```

# Contributing

See CONTRIBUTING.md before making edits.
