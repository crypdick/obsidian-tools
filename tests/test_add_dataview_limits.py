import pytest
from pathlib import Path
from typer.testing import CliRunner

from obsidian_tools.add_dataview_limits import app

runner = CliRunner()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a temporary vault with some files."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "no_dataview.md").write_text("no dataview here")
    (vault_path / "dataview_no_limit.md").write_text(
        "```dataview\nTABLE file.mtime\nFROM #tasks\n```"
    )
    (vault_path / "dataview_with_limit.md").write_text(
        "```dataview\nTABLE file.mtime\nFROM #tasks\nLIMIT 10\n```"
    )
    return vault_path


def test_add_dataview_limits_dry_run(vault: Path, caplog):
    result = runner.invoke(app, ["--vault-path", str(vault)])
    assert result.exit_code == 0
    assert "Running in dry-run mode" in caplog.text
    assert "Identified file to modify" in caplog.text
    assert "dataview_no_limit.md" in caplog.text
    assert "Dry run complete" in caplog.text
    assert "dataview_no_limit.md" in caplog.text

    # check that the file was not modified
    content = (vault / "dataview_no_limit.md").read_text()
    assert "LIMIT 1000" not in content


def test_add_dataview_limits_go(vault: Path, caplog, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(app, ["--vault-path", str(vault), "--go"])
    assert result.exit_code == 0
    assert "Updated" in caplog.text
    assert "dataview_no_limit.md" in caplog.text

    # check that the file was modified
    content = (vault / "dataview_no_limit.md").read_text()
    assert "LIMIT 1000" in content
