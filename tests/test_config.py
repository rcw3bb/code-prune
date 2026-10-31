"""Tests for config module.

Author: Ron Webb
Since: 1.0.0
"""

from pathlib import Path

from code_prune.config import Config


def test_get_ignore_file_defaults_when_config_missing(tmp_path: Path) -> None:
    """It should fall back to '.codepruneignore' when config.ini is absent."""
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == ".codepruneignore"


def test_get_ignore_file_defaults_when_section_missing(tmp_path: Path) -> None:
    """It should fall back to '.codepruneignore' when the [override] section is absent."""
    (tmp_path / "config.ini").write_text("[other]\nkey = value\n", encoding="utf-8")
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == ".codepruneignore"


def test_get_ignore_file_reads_custom_value(tmp_path: Path) -> None:
    """It should return the configured [override] ignore-file value when present."""
    (tmp_path / "config.ini").write_text(
        "[override]\nignore-file = custom.ignore\n", encoding="utf-8"
    )
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == "custom.ignore"
