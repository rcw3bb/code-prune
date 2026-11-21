"""Tests for language_tables module.

Author: Ron Webb
Since: 1.3.0
"""

from __future__ import annotations

from code_prune.language_tables import EXTENSION_TO_LANGUAGE, SUPPORTED_EXTENSIONS


def test_extension_to_language_covers_all_five_languages() -> None:
    """Every supported extension should map to its expected language."""
    assert EXTENSION_TO_LANGUAGE[".py"] == "Python"
    assert EXTENSION_TO_LANGUAGE[".js"] == "JavaScript"
    assert EXTENSION_TO_LANGUAGE[".ts"] == "TypeScript"
    assert EXTENSION_TO_LANGUAGE[".java"] == "Java"
    assert EXTENSION_TO_LANGUAGE[".gs"] == "Gosu"
    assert EXTENSION_TO_LANGUAGE[".gsx"] == "Gosu"


def test_supported_extensions_matches_language_map() -> None:
    """SUPPORTED_EXTENSIONS must mirror EXTENSION_TO_LANGUAGE."""
    assert SUPPORTED_EXTENSIONS == frozenset(EXTENSION_TO_LANGUAGE)
