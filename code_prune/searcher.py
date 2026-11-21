"""Textual search of extra paths for symbols reported as unused.

Symbols that are only referenced from files outside the scanned project
(templates, configuration, other code bases) would otherwise be reported as
unused. :class:`SymbolSearcher` checks such files purely textually, without
parsing them. Class, function/method and field names are matched with the same
whole-word regular expression; a method or field defined inside a class is only
considered referenced when its own name *and* its enclosing class's name are
both found in the same search file.

Author: Ron Webb
Since: 1.2.0
"""

from __future__ import annotations

import re
from pathlib import Path

#: ``(name, kind, defining_file, enclosing_class)``. ``enclosing_class`` is
#: ``None`` for classes and free functions.
Candidate = tuple[str, str, str, str | None]


def _build_pattern(name: str) -> re.Pattern[str]:
    """Return a whole-word regex for *name* that also treats ``$`` as a word character.

    Author: Ron Webb
    Since: 1.2.0
    """
    return re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")


def _read_text(file_path: Path) -> str | None:
    """Return the text of *file_path*, or ``None`` for unreadable/binary files.

    Author: Ron Webb
    Since: 1.2.0
    """
    try:
        data = file_path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


class SymbolSearcher:
    """Find which symbols are textually referenced in a set of search files.

    Author: Ron Webb
    Since: 1.2.0
    """

    def __init__(self, search_files: list[Path]) -> None:
        """Store the files to search.

        Author: Ron Webb
        Since: 1.2.0
        """
        self._search_files = search_files

    def find_referenced(self, candidates: list[Candidate]) -> set[Candidate]:
        """Return the subset of *candidates* found in the search files.

        The candidate's own defining file is never counted as a reference.
        Every search file is read once and the search stops as soon as every
        candidate has been resolved.

        Author: Ron Webb
        Since: 1.2.0
        """
        pending = set(candidates)
        found: set[Candidate] = set()
        patterns: dict[str, re.Pattern[str]] = {}
        for search_file in self._search_files:
            if not pending:
                break
            text = _read_text(search_file)
            if text is None:
                continue
            resolved = _resolve(search_file)
            hits = self._matches_in_text(text, resolved, pending, patterns)
            found.update(hits)
            pending.difference_update(hits)
        return found

    @staticmethod
    def _matches_in_text(
        text: str,
        resolved_file: str,
        pending: set[Candidate],
        patterns: dict[str, re.Pattern[str]],
    ) -> set[Candidate]:
        """Return the *pending* candidates referenced in *text*.

        A plain class or free function matches once its own name is found. A
        method or field (``enclosing_class`` set) additionally requires its
        enclosing class's name to be found in the same *text*.

        Author: Ron Webb
        Since: 1.2.0
        """
        hits: set[Candidate] = set()
        for candidate in pending:
            name, _, defining_file, enclosing_class = candidate
            if _resolve(Path(defining_file)) == resolved_file:
                continue
            if not _name_matches(text, name, patterns):
                continue
            if enclosing_class and not _name_matches(text, enclosing_class, patterns):
                continue
            hits.add(candidate)
        return hits


def _name_matches(text: str, name: str, patterns: dict[str, re.Pattern[str]]) -> bool:
    """Return whether *name* occurs as a whole word in *text*.

    Author: Ron Webb
    Since: 1.2.0
    """
    if name not in text:
        return False
    pattern = patterns.setdefault(name, _build_pattern(name))
    return pattern.search(text) is not None


def _resolve(path: Path) -> str:
    """Return a normalised string form of *path* for own-file comparison.

    Author: Ron Webb
    Since: 1.2.0
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())
