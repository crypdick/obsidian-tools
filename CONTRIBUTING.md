# Conventions used in this repo

# Style

- Use idiomatic Python 3.13. This includes but is not limited to type hints.
- Use `.env` files for secrets.
- Use the DRY principle. Check `utils.py`, `constants.py`, etc. for existing functions that can be recycled.
- Use `typer` instead of argparse.

# Dependency management

- Do not manually edit dependencies into pyproject.toml. Use `uv add DEP` or `uv remove DEP`.
- For dev dependencies, use `uv add --dev DEP` instead.
- Run using `uv run examples.py`


# Safe-guards

- Always run scripts in "dry run" mode by default, to prevent distructive edits. Use `--go` for a
  "wet run". Confirm that the user is sure with "N/y" input. 
- Create detailed logs in the logs/ directory. Each session should have its own unique folder.
- When making file edits, backup the files into the session's log folder in such a way that it can 
  be rescued if needed.
- Use loguru for logging. See `logging_utils.py` for helpers.

# Testing

- Run tests with `uv run pytest tests`
- Use test-driven development
