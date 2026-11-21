"""Textual search of extra paths for symbols reported as unused.

Symbols that are only referenced from files outside the scanned project
(templates, configuration, other code bases) would otherwise be reported as
unused. :class:`SymbolSearcher` checks such files purely textually, without
parsing them. Class, function/method and field names are matched with the same
whole-word regular expression; a method or field defined inside a class is only
considered referenced when its own name *and* its enclosing class's name are
both found in the same search file.

Each search file is read and tokenized once (``[\\w$]+`` words) and the tokens
are intersected with the set of names being looked for, so the cost per file
does not grow with the number of candidates. Files are read on a thread pool
and consumed in order, keeping early exit and progress reporting deterministic.

Author: Ron Webb
Since: 1.2.0
"""

from __future__ import annotations

import concurrent.futures
import re
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from itertools import islice
from pathlib import Path

#: ``(name, kind, defining_file, enclosing_class)``. ``enclosing_class`` is
#: ``None`` for classes and free functions.
Candidate = tuple[str, str, str, str | None]

_WORD_RE = re.compile(r"[\w$]+")
_PLAIN_NAME_RE = re.compile(r"[\w$]+")
#: In-flight read tasks per worker thread; bounds memory held by pending reads.
_WINDOW_PER_WORKER = 4


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


def _read_names(
    file_path: Path,
    plain_names: frozenset[str],
    special_patterns: dict[str, re.Pattern[str]],
) -> tuple[set[str], str] | None:
    """Return ``(names_present, resolved_path)`` for *file_path*, or ``None``.

    *plain_names* consist solely of word characters, so they are found by one
    tokenization pass. *special_patterns* holds the rare other names, each
    looked up with its own whole-word regex. ``None`` marks an unreadable or
    binary file.

    Author: Ron Webb
    Since: 1.4.0
    """
    text = _read_text(file_path)
    if text is None:
        return None
    present = set(plain_names.intersection(_WORD_RE.findall(text)))
    for name, pattern in special_patterns.items():
        if name in text and pattern.search(text):
            present.add(name)
    return present, _resolve(file_path)


class _CandidateIndex:
    """Pending candidates grouped by name, for lookups against a file's names.

    Author: Ron Webb
    Since: 1.4.0
    """

    def __init__(self, candidates: Iterable[Candidate]) -> None:
        """Group *candidates* by name and derive the names to search for.

        Author: Ron Webb
        Since: 1.4.0
        """
        self._by_name: dict[str, list[Candidate]] = {}
        self._resolved_files: dict[str, str] = {}
        needed: set[str] = set()
        for candidate in set(candidates):
            name, _, _, enclosing_class = candidate
            self._by_name.setdefault(name, []).append(candidate)
            needed.add(name)
            if enclosing_class:
                needed.add(enclosing_class)
        self.plain_names = frozenset(n for n in needed if _PLAIN_NAME_RE.fullmatch(n))
        self.special_patterns = {
            n: _build_pattern(n) for n in needed if n not in self.plain_names
        }

    def __bool__(self) -> bool:
        """Return whether any candidate is still unresolved.

        Author: Ron Webb
        Since: 1.4.0
        """
        return bool(self._by_name)

    def resolve(self, names_present: set[str], resolved_file: str) -> set[Candidate]:
        """Remove and return the candidates referenced by a file.

        A plain class or free function matches once its own name is present. A
        method or field (``enclosing_class`` set) additionally requires its
        enclosing class's name to be present. A candidate's own defining file
        never counts.

        Author: Ron Webb
        Since: 1.4.0
        """
        hits: set[Candidate] = set()
        for name in names_present.intersection(self._by_name):
            remaining: list[Candidate] = []
            for candidate in self._by_name[name]:
                _, _, defining_file, enclosing_class = candidate
                if self._is_own_file(defining_file, resolved_file) or (
                    enclosing_class and enclosing_class not in names_present
                ):
                    remaining.append(candidate)
                else:
                    hits.add(candidate)
            if remaining:
                self._by_name[name] = remaining
            else:
                del self._by_name[name]
        return hits

    def _is_own_file(self, defining_file: str, resolved_file: str) -> bool:
        """Return whether *defining_file* is the file at *resolved_file*.

        Each defining file is resolved on the file system only once.

        Author: Ron Webb
        Since: 1.4.0
        """
        if defining_file not in self._resolved_files:
            self._resolved_files[defining_file] = _resolve(Path(defining_file))
        return self._resolved_files[defining_file] == resolved_file


class SymbolSearcher:
    """Find which symbols are textually referenced in a set of search files.

    Author: Ron Webb
    Since: 1.2.0
    """

    def __init__(self, search_files: list[Path], workers: int = 1) -> None:
        """Store the files to search and the number of reader threads.

        Author: Ron Webb
        Since: 1.2.0
        """
        self._search_files = search_files
        self._workers = max(1, workers)

    @property
    def file_count(self) -> int:
        """Return the number of search files this searcher was built with.

        Lets callers (e.g. the CLI) size a progress indicator without
        reaching into the private file list.

        Author: Ron Webb
        Since: 1.4.0
        """
        return len(self._search_files)

    def find_referenced(
        self,
        candidates: list[Candidate],
        on_progress: Callable[[], None] | None = None,
    ) -> set[Candidate]:
        """Return the subset of *candidates* found in the search files.

        The candidate's own defining file is never counted as a reference.
        Every search file is read once and the search stops as soon as every
        candidate has been resolved. When given, *on_progress* is called once
        per search file considered (including skipped/binary/missing ones and
        the one that resolves the last pending candidate), so a caller can
        drive a progress indicator over a potentially long-running search.

        Author: Ron Webb
        Since: 1.2.0
        """
        index = _CandidateIndex(candidates)
        found: set[Candidate] = set()
        if not index:
            return found
        results = self._iter_file_names(index.plain_names, index.special_patterns)
        try:
            for result in results:
                if result is not None:
                    names_present, resolved_file = result
                    found.update(index.resolve(names_present, resolved_file))
                if on_progress is not None:
                    on_progress()
                if not index:
                    break
        finally:
            results.close()
        return found

    def _iter_file_names(
        self,
        plain_names: frozenset[str],
        special_patterns: dict[str, re.Pattern[str]],
    ) -> Iterator[tuple[set[str], str] | None]:
        """Yield :func:`_read_names` for every search file, in file order.

        With more than one worker, files are read ahead on a thread pool
        through a bounded window; leftover reads are cancelled when the
        consumer stops early.

        Author: Ron Webb
        Since: 1.4.0
        """

        def read(file_path: Path) -> tuple[set[str], str] | None:
            return _read_names(file_path, plain_names, special_patterns)

        files = iter(self._search_files)
        if self._workers == 1:
            yield from map(read, files)
            return
        with concurrent.futures.ThreadPoolExecutor(self._workers) as executor:
            window = deque(
                executor.submit(read, f)
                for f in islice(files, self._workers * _WINDOW_PER_WORKER)
            )
            try:
                while window:
                    result = window.popleft().result()
                    window.extend(executor.submit(read, f) for f in islice(files, 1))
                    yield result
            finally:
                for future in window:
                    future.cancel()


def _resolve(path: Path) -> str:
    """Return a normalised string form of *path* for own-file comparison.

    Author: Ron Webb
    Since: 1.2.0
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())
