import pytest
from pathlib import Path
from obsidian_tools.dedup import main


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a temporary vault with some files."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "a.md").write_text("content a")
    (vault_path / "b.md").write_text("content b")
    (vault_path / "c.md").write_text("content c")
    (vault_path / "a (1).md").write_text("content a")
    (vault_path / "b (1).md").write_text("content b")
    (vault_path / "c (2).md").write_text("content c")
    (vault_path / "d (1).md").write_text("content d")
    (vault_path / "d (2).md").write_text("content d")
    return vault_path


def test_dedup_dry_run(vault: Path, caplog):
    main(directory=vault, go=False)
    assert "Dry run complete" in caplog.text
    assert "a (1).md" in caplog.text
    assert "b (1).md" in caplog.text
    assert "c (2).md" in caplog.text
    assert "d (2).md" in caplog.text
    assert "Would rename" in caplog.text
    assert "d (1).md -> d.md" in caplog.text


def test_dedup_go(vault: Path, caplog, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    main(directory=vault, go=True)
    assert "Deleted" in caplog.text
    assert not (vault / "a (1).md").exists()
    assert not (vault / "b (1).md").exists()
    assert not (vault / "c (2).md").exists()
    assert not (vault / "d (2).md").exists()
    assert (vault / "a.md").exists()
    assert (vault / "b.md").exists()
    assert (vault / "c.md").exists()
    assert (vault / "d.md").exists()
    assert not (vault / "d (1).md").exists()
