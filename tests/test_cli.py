"""Tests for cli module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from braincraft.ignorefile import IgnoreFile
from click.testing import CliRunner

from code_prune import cli

_FIXTURES = Path(__file__).parent / "fixtures"
_CLI_PROJECT = _FIXTURES / "cli_project"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def test_parse_extensions_normalises_and_dots() -> None:
    """Extensions should be lowercased and dot-prefixed when missing."""
    assert cli._parse_extensions("py,JS, .ts") == [".py", ".js", ".ts"]


def test_parse_paths_multiple_paths() -> None:
    """A semicolon-separated string should parse into multiple Path objects."""
    assert cli._parse_paths("src; lib ; tests") == [
        Path("src"),
        Path("lib"),
        Path("tests"),
    ]


def test_parse_paths_ignores_empty_segments() -> None:
    """Empty segments from trailing/double semicolons should be skipped."""
    assert cli._parse_paths("src;;lib;") == [Path("src"), Path("lib")]


def test_read_target_list_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    """Blank lines and '#' comments should be skipped."""
    list_file = tmp_path / "targets.txt"
    list_file.write_text("src\n\n# a comment\n  \nlib\n", encoding="utf-8")
    assert cli._read_target_list(list_file) == [Path("src"), Path("lib")]


def test_parse_categories_defaults_to_all() -> None:
    """All CLI categories should be accepted together."""
    result = cli._parse_categories("unreachable,unused,obsolete,commented-out")
    assert result == {"unreachable", "unused", "obsolete", "commented-out"}


def test_parse_categories_rejects_unknown_category() -> None:
    """An unrecognised category name should raise a UsageError."""
    with pytest.raises(click.UsageError):
        cli._parse_categories("unreachable,bogus")


def test_category_enabled_maps_unused_subcategories() -> None:
    """unused-import/unused-local/unused-symbol should all map to 'unused'."""
    categories = {"unused"}
    assert cli._category_enabled("unused-import", categories)
    assert cli._category_enabled("unused-local", categories)
    assert cli._category_enabled("unused-symbol", categories)
    assert not cli._category_enabled("unreachable", categories)


# ---------------------------------------------------------------------------
# discover_files
# ---------------------------------------------------------------------------


def test_discover_files_for_file_and_dir(tmp_path: Path) -> None:
    """Files should be discovered from both file and directory inputs."""
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("x = 1\n", encoding="utf-8")
    nested = tmp_path / "pkg"
    nested.mkdir()
    nested_file = nested / "mod.py"
    nested_file.write_text("y = 2\n", encoding="utf-8")

    assert cli.discover_files(sample_file, []) == [sample_file]
    assert nested_file in cli.discover_files(tmp_path, [])


def test_discover_files_extension_filter(tmp_path: Path) -> None:
    """Only files matching the given extensions should be returned."""
    py_file = tmp_path / "app.py"
    py_file.write_text("x = 1", encoding="utf-8")
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    result = cli.discover_files(tmp_path, [".py"])

    assert py_file in result
    assert txt_file not in result


def test_discover_files_nonexistent_path_returns_empty(tmp_path: Path) -> None:
    """A path that does not exist should yield an empty list."""
    assert cli.discover_files(tmp_path / "missing", []) == []


def test_discover_files_prunes_ignored_directory(tmp_path: Path) -> None:
    """discover_files must not descend into a directory matched by the ignore file."""
    kept = tmp_path / "kept.py"
    kept.write_text("x = 1\n", encoding="utf-8")
    ignored_dir = tmp_path / "dist"
    ignored_dir.mkdir()
    (ignored_dir / "hidden.py").write_text("y = 2\n", encoding="utf-8")

    ignore_file = tmp_path / ".codepruneignore"
    ignore_file.write_text("dist/\n", encoding="utf-8")
    ignore = IgnoreFile(ignore_file, base_dir=tmp_path)

    result = cli.discover_files(tmp_path, [], ignore)

    assert kept in result
    assert not any(p.parent == ignored_dir for p in result)


def test_build_ignore_returns_none_when_file_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """_build_ignore must return None when neither ignore file exists."""
    monkeypatch.setattr(cli, "CONF_DIR", str(tmp_path))
    monkeypatch.setattr(cli._config, "get_ignore_file", lambda: ".codepruneignore")
    monkeypatch.setattr(cli, "PATH_IGNORE_PATH", tmp_path / ".codepruneignore")

    assert cli._build_ignore(tmp_path) is None


def test_build_ignore_uses_configured_custom_filename(
    tmp_path: Path, monkeypatch
) -> None:
    """_build_ignore must use the config.ini-configured filename when present."""
    custom_file = tmp_path / "custom.ignore"
    custom_file.write_text("*.log\n", encoding="utf-8")
    monkeypatch.setattr(cli, "CONF_DIR", str(tmp_path))
    monkeypatch.setattr(cli._config, "get_ignore_file", lambda: "custom.ignore")
    monkeypatch.setattr(cli, "PATH_IGNORE_PATH", tmp_path / ".codepruneignore")

    result = cli._build_ignore(tmp_path)

    assert result is not None
    assert result.is_ignored(tmp_path / "app.log")


def test_build_ignore_falls_back_to_default_when_custom_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """_build_ignore must fall back to the bundled default ignore file."""
    default_file = tmp_path / ".codepruneignore"
    default_file.write_text("*.log\n", encoding="utf-8")
    monkeypatch.setattr(cli, "CONF_DIR", str(tmp_path))
    monkeypatch.setattr(cli._config, "get_ignore_file", lambda: "custom.ignore")
    monkeypatch.setattr(cli, "PATH_IGNORE_PATH", default_file)

    result = cli._build_ignore(tmp_path)

    assert result is not None
    assert result.is_ignored(tmp_path / "app.log")


# ---------------------------------------------------------------------------
# main (end-to-end via CliRunner)
# ---------------------------------------------------------------------------


def test_main_returns_zero_when_no_files(tmp_path: Path) -> None:
    """The command should exit zero when there are no files to scan."""
    runner = CliRunner()
    result = runner.invoke(cli.main, [str(tmp_path)])
    assert result.exit_code == 0
    assert "No files found" in result.output


def test_main_writes_json_with_findings(tmp_path: Path) -> None:
    """A dead-code sample should produce a JSON report with findings."""
    sample = tmp_path / "a.py"
    sample.write_text("def foo():\n    return 1\n    dead()\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])
    data = json.loads((out_dir / "code-prune-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert any(f["category"] == "unreachable" for f in data["findings"])


def test_main_format_html_writes_html_file(tmp_path: Path) -> None:
    """--format html should write only an HTML report."""
    sample = tmp_path / "a.py"
    sample.write_text("def foo():\n    return 1\n    dead()\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--output-dir", str(out_dir), "--format", "html"]
    )

    assert result.exit_code == 0
    assert (out_dir / "code-prune-output.html").exists()
    assert not (out_dir / "code-prune-output.json").exists()


def test_main_format_all_writes_both_files(tmp_path: Path) -> None:
    """--format all should write both JSON and HTML reports."""
    sample = tmp_path / "a.py"
    sample.write_text("x = 1\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--output-dir", str(out_dir), "--format", "all"]
    )

    assert result.exit_code == 0
    assert (out_dir / "code-prune-output.json").exists()
    assert (out_dir / "code-prune-output.html").exists()


def test_main_ext_flag_filters_files(tmp_path: Path) -> None:
    """--ext should restrict scanning to the given extensions."""
    (tmp_path / "a.py").write_text(
        "def foo():\n    return 1\n    dead()\n", encoding="utf-8"
    )
    (tmp_path / "b.txt").write_text("not code", encoding="utf-8")
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--output-dir", str(out_dir), "--ext", "py"]
    )
    data = json.loads((out_dir / "code-prune-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert all("a.py" in f["file"] for f in data["findings"])


def test_main_categories_flag_restricts_findings(tmp_path: Path) -> None:
    """Selecting only 'obsolete' should exclude unreachable-code findings."""
    sample = tmp_path / "a.py"
    sample.write_text(
        "# TODO fix\ndef foo():\n    return 1\n    dead()\n", encoding="utf-8"
    )
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main,
        [str(tmp_path), "--output-dir", str(out_dir), "--categories", "obsolete"],
    )
    data = json.loads((out_dir / "code-prune-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    categories_found = {f["category"] for f in data["findings"]}
    assert categories_found == {"obsolete"}


def test_main_unknown_category_fails(tmp_path: Path) -> None:
    """An unknown --categories value should fail with a usage error."""
    runner = CliRunner()
    result = runner.invoke(cli.main, [str(tmp_path), "--categories", "bogus"])
    assert result.exit_code != 0


def test_main_target_list_scans_listed_targets(tmp_path: Path) -> None:
    """--target-list should treat PATH as a file listing target paths."""
    sample = tmp_path / "a.py"
    sample.write_text("x = 1\n", encoding="utf-8")
    list_file = tmp_path / "targets.txt"
    list_file.write_text(str(sample) + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main,
        [str(list_file), "--output-dir", str(out_dir), "--target-list"],
    )

    assert result.exit_code == 0
    assert (out_dir / "code-prune-output.json").exists()


def test_main_target_list_rejects_directory_path(tmp_path: Path) -> None:
    """--target-list combined with a directory PATH should raise a usage error."""
    runner = CliRunner()
    result = runner.invoke(cli.main, [str(tmp_path), "--target-list"])
    assert result.exit_code != 0


def test_main_version_flag_prints_version() -> None:
    """--version should print the application name and version."""
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert "code-prune" in result.output


def test_main_cross_file_unused_symbol_resolved_across_project(tmp_path: Path) -> None:
    """A function used only from another file must not be flagged unused."""
    (tmp_path / "a.py").write_text(
        "def used_elsewhere():\n    return 1\n\ndef orphan():\n    return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "def main():\n    return used_elsewhere()\n", encoding="utf-8"
    )
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])
    data = json.loads((out_dir / "code-prune-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    unused_names = {
        f["name"] for f in data["findings"] if f["category"] == "unused-symbol"
    }
    assert "used_elsewhere" not in unused_names
    assert "main" not in unused_names  # excluded via bundled symbol_ignore
    assert "orphan" in unused_names


def test_cli_command_scans_fixture_project(tmp_path: Path) -> None:
    """The full cli_project fixture should scan cleanly end to end."""
    out_dir = tmp_path / "out"
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(_CLI_PROJECT), "--output-dir", str(out_dir), "--format", "all"]
    )

    assert result.exit_code == 0
    assert (out_dir / "code-prune-output.json").exists()
    assert (out_dir / "code-prune-output.html").exists()
