import pytest
from pathlib import Path
from obsidian_tools.dedup import main, numeric_suffix


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


@pytest.fixture
def vault_with_duplicates(tmp_path: Path) -> Path:
    """Create a vault with duplicate files."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create duplicate scenario: base file + numbered duplicate
    (vault_path / "note.md").write_text("# Note\n\nThis is a note.")
    (vault_path / "note (1).md").write_text("# Note\n\nThis is a note.")

    # Add some other files
    (vault_path / "other.md").write_text("Different content")
    (vault_path / "another (1).md").write_text("Another content")
    (vault_path / "another (2).md").write_text("Another content")

    return vault_path


@pytest.fixture
def vault_with_subdirs(tmp_path: Path) -> Path:
    """Create a vault with subdirectories."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create subdirectory
    subdir_path = vault_path / "subdir"
    subdir_path.mkdir()

    # Create files with same content in different directories
    (subdir_path / "note.md").write_text("# Note\n\nSame content.")
    (subdir_path / "note (1).md").write_text("# Note\n\nSame content.")

    # Create some files in the root
    (vault_path / "root.md").write_text("Root content")
    (vault_path / "root (1).md").write_text("Root content")

    return vault_path


@pytest.fixture
def vault_all_numbered_files(tmp_path: Path) -> Path:
    """Create a vault where ALL duplicate files have numeric suffixes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Case where all files have numeric suffixes
    (vault_path / "file (1).md").write_text("# File\n\nContent here.")
    (vault_path / "file (2).md").write_text("# File\n\nContent here.")

    # Another example
    (vault_path / "notes (1).md").write_text("Notes content")
    (vault_path / "notes (3).md").write_text("Notes content")

    return vault_path


@pytest.fixture
def vault_rename_conflict(tmp_path: Path) -> Path:
    """Create a vault that has a rename conflict scenario."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create an existing base file with different content
    (vault_path / "note.md").write_text("# Different Content\n\nThis is different.")

    # Create numbered duplicates with same content
    (vault_path / "note (1).md").write_text("# Same Content\n\nThis is the same.")
    (vault_path / "note (2).md").write_text("# Same Content\n\nThis is the same.")

    return vault_path


def test_numeric_suffix_function():
    """Test the numeric_suffix function with various inputs."""
    assert numeric_suffix("file.md") == 0
    assert numeric_suffix("file (1).md") == 1
    assert numeric_suffix("file (2).md") == 2
    assert numeric_suffix("file (10).md") == 10
    assert numeric_suffix("complex name with spaces.md") == 0
    assert numeric_suffix("complex name with spaces (5).md") == 5


def test_prefers_shorter_paths_for_same_content_and_name(
    vault_with_subdirs: Path, caplog
):
    """Test that when files have same content and name, it prefers files with shorter paths."""
    main(directory=vault_with_subdirs, go=False)

    subdir_file = vault_with_subdirs / "subdir" / "note.md"
    subdir_file_1 = vault_with_subdirs / "subdir" / "note (1).md"

    # Should delete the numbered file from the subdirectory
    assert f"Would delete: {subdir_file_1}" in caplog.text
    assert f"Would delete: {subdir_file}" not in caplog.text


def test_numbered_files_without_base(vault_all_numbered_files: Path, caplog):
    """Test case where all duplicate files have numeric suffixes."""
    main(directory=vault_all_numbered_files, go=False)

    file_1 = vault_all_numbered_files / "file (1).md"
    file_2 = vault_all_numbered_files / "file (2).md"

    # Check that the correct file is marked for deletion
    assert f"Would delete: {file_2}" in caplog.text
    assert f"Would delete: {file_1}" not in caplog.text

    # Check that the rename action is planned
    assert "Would rename: file (1).md -> file.md" in caplog.text


def test_rename_conflict_scenario(vault_rename_conflict: Path, caplog):
    """Test scenario where rename would conflict with existing file."""
    main(directory=vault_rename_conflict, go=False)

    base_file = vault_rename_conflict / "note.md"
    numbered_file_1 = vault_rename_conflict / "note (1).md"
    numbered_file_2 = vault_rename_conflict / "note (2).md"

    # The numbered duplicates should be handled separately from the base file
    # One of the numbered files should be deleted
    assert (f"Would delete: {numbered_file_1}" in caplog.text) or (
        f"Would delete: {numbered_file_2}" in caplog.text
    )

    # Base file should NOT be deleted (it has different content)
    assert f"Would delete: {base_file}" not in caplog.text


def test_dry_run_should_not_show_impossible_renames(
    vault_rename_conflict: Path, caplog
):
    """Test that dry run should not show rename actions that would be skipped due to destination existing."""
    main(directory=vault_rename_conflict, go=False)

    # The dry run should NOT show a rename that would fail due to destination existing
    assert "Would rename: note (1).md -> note.md" not in caplog.text

    # It should only show the deletion that would actually happen
    assert f"Would delete: {vault_rename_conflict / 'note (2).md'}" in caplog.text


def test_dedup_dry_run(vault: Path, caplog):
    """Test basic dry run functionality."""
    main(directory=vault, go=False)
    assert "Dry run complete" in caplog.text
    assert "a (1).md" in caplog.text
    assert "b (1).md" in caplog.text
    assert "c (2).md" in caplog.text
    assert "d (2).md" in caplog.text
    assert "Would rename" in caplog.text
    assert "d (1).md -> d.md" in caplog.text


def test_dedup_go(vault: Path, caplog, monkeypatch):
    """Test actual deduplication with file operations."""
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


def test_base_file_should_be_kept_over_numbered_duplicate(
    vault_with_duplicates: Path, caplog
):
    """Test that base files are kept and numbered duplicates are deleted."""
    main(directory=vault_with_duplicates, go=False)

    # Verify dry run messages
    assert "Dry run complete" in caplog.text

    # Base file should NOT be marked for deletion (it should be kept)
    assert "Would delete: " + str(vault_with_duplicates / "note.md") not in caplog.text

    # Numbered duplicate SHOULD be marked for deletion
    assert "Would delete: " + str(vault_with_duplicates / "note (1).md") in caplog.text

    # Higher numbered file should be deleted (keeping the (1) version which will be renamed)
    assert (
        "Would delete: " + str(vault_with_duplicates / "another (2).md") in caplog.text
    )
    assert "Would rename: another (1).md -> another.md" in caplog.text
