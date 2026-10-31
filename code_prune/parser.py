"""Tree-sitter language loading and source parsing utilities.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import importlib
import logging
from functools import lru_cache

from tree_sitter import Language, Parser, Tree

_logger = logging.getLogger(__name__)

# Maps language name -> (module, callable-name) for dynamic import.
_LANG_MODULES: dict[str, tuple[str, str]] = {
    "Python": ("tree_sitter_python", "language"),
    "JavaScript": ("tree_sitter_javascript", "language"),
    "TypeScript": ("tree_sitter_typescript", "language_typescript"),
    "Java": ("tree_sitter_java", "language"),
    "Gosu": ("tree_sitter_gosu", "language"),
}


@lru_cache(maxsize=None)
def get_language(language_name: str) -> Language | None:
    """Return the tree-sitter :class:`Language` object for *language_name*.

    Results are cached so the binding is loaded only once per interpreter
    session.  Returns ``None`` when the language name is not recognised or
    the corresponding grammar package is unavailable.

    Author: Ron Webb
    Since: 1.0.0
    """
    spec = _LANG_MODULES.get(language_name)
    if spec is None:
        return None
    module_name, func_name = spec
    try:
        module = importlib.import_module(module_name)
        return Language(getattr(module, func_name)())
    except Exception:  # pylint: disable=broad-exception-caught
        _logger.warning("Failed to load tree-sitter language: %s", language_name)
        return None


def parse(source_bytes: bytes, language_name: str) -> Tree | None:
    """Parse *source_bytes* with a fresh :class:`Parser` for *language_name*.

    A new :class:`Parser` instance is created on every call so that no internal
    C extension state carries over between files (tree-sitter 0.26+ requirement).
    Returns ``None`` when the language cannot be loaded or parsing fails.

    Author: Ron Webb
    Since: 1.0.0
    """
    language = get_language(language_name)
    if language is None:
        return None
    try:
        return Parser(language).parse(source_bytes)
    except Exception:  # pylint: disable=broad-exception-caught
        _logger.warning("Failed to parse source as %s", language_name)
        return None
