"""Session-scoped SQLite store for scan findings and cross-file analysis.

Per-file findings, together with the definitions and usage names collected
while scanning, are written directly to an SQLite database instead of being
accumulated in memory. Every scan run is assigned a UUID so multiple
concurrent invocations share the same database file without interference.
Once every file has been scanned, :meth:`SessionStore.compute_unused_symbols`
resolves :data:`~code_prune.scanner.CATEGORY_UNUSED_SYMBOL` findings by
aggregating definitions against usages in SQL. After the report is written
the caller deletes the session records, keeping the database lean.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from .scanner import CATEGORY_UNUSED_SYMBOL, Definition, Finding

_CREATE_FINDINGS_TABLE = (
    "CREATE TABLE IF NOT EXISTS findings ("
    "    session_id TEXT NOT NULL,"
    "    category   TEXT NOT NULL,"
    "    file_path  TEXT NOT NULL,"
    "    line       INTEGER NOT NULL,"
    "    col        INTEGER NOT NULL,"
    "    name       TEXT NOT NULL,"
    "    message    TEXT NOT NULL"
    ")"
)
_CREATE_DEFINITIONS_TABLE = (
    "CREATE TABLE IF NOT EXISTS definitions ("
    "    session_id TEXT NOT NULL,"
    "    file_path  TEXT NOT NULL,"
    "    line       INTEGER NOT NULL,"
    "    col        INTEGER NOT NULL,"
    "    name       TEXT NOT NULL,"
    "    kind       TEXT NOT NULL"
    ")"
)
_CREATE_IDENTIFIERS_TABLE = (
    "CREATE TABLE IF NOT EXISTS identifiers ("
    "    session_id TEXT NOT NULL,"
    "    name       TEXT NOT NULL"
    ")"
)
_CREATE_FINDINGS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_findings_session ON findings (session_id)"
)
_CREATE_DEFINITIONS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_definitions_session ON definitions (session_id)"
)
_CREATE_IDENTIFIERS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_identifiers_session_name"
    " ON identifiers (session_id, name)"
)

_INSERT_FINDING = (
    "INSERT INTO findings (session_id, category, file_path, line, col, name, message)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
)
_INSERT_DEFINITION = (
    "INSERT INTO definitions (session_id, file_path, line, col, name, kind)"
    " VALUES (?, ?, ?, ?, ?, ?)"
)
_INSERT_IDENTIFIER = "INSERT INTO identifiers (session_id, name) VALUES (?, ?)"

_SELECT_FINDINGS = (
    "SELECT category, file_path, line, col, name, message FROM findings"
    " WHERE session_id = ? ORDER BY file_path ASC, line ASC, col ASC"
)
_SELECT_UNUSED_DEFINITIONS = (
    "SELECT d.file_path, d.line, d.col, d.name, d.kind"
    " FROM definitions d"
    " WHERE d.session_id = ?"
    " AND NOT EXISTS ("
    "   SELECT 1 FROM identifiers i"
    "   WHERE i.session_id = d.session_id AND i.name = d.name"
    " )"
    " ORDER BY d.file_path ASC, d.line ASC"
)

_DELETE_FINDINGS = "DELETE FROM findings WHERE session_id = ?"
_DELETE_DEFINITIONS = "DELETE FROM definitions WHERE session_id = ?"
_DELETE_IDENTIFIERS = "DELETE FROM identifiers WHERE session_id = ?"


class SessionStore:
    """SQLite-backed session store for dead-code scan results.

    A single database file is shared across all threads and concurrent runs.
    Every run is identified by a *session_id* (UUID string) so records are
    always isolated. The cross-file "unused symbol" pass is performed entirely
    in SQL via a ``NOT EXISTS`` anti-join so Python never has to materialise
    every identifier in memory to resolve it.

    Author: Ron Webb
    Since: 1.0.0
    """

    def __init__(self, db_path: Path) -> None:
        """Open (or create) the SQLite database at *db_path*.

        WAL journal mode is enabled so reads and writes do not block each
        other; a threading lock serialises Python-side connection calls since
        :mod:`sqlite3` connection objects are not thread-safe.

        Author: Ron Webb
        Since: 1.0.0
        """
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(_CREATE_FINDINGS_TABLE)
            self._conn.execute(_CREATE_DEFINITIONS_TABLE)
            self._conn.execute(_CREATE_IDENTIFIERS_TABLE)
            self._conn.execute(_CREATE_FINDINGS_INDEX)
            self._conn.execute(_CREATE_DEFINITIONS_INDEX)
            self._conn.execute(_CREATE_IDENTIFIERS_INDEX)
            self._conn.commit()

    def insert_findings(self, session_id: str, findings: list[Finding]) -> None:
        """Persist *findings* for *session_id* in the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        rows = [
            (
                session_id,
                f.category,
                str(f.file_path),
                f.line,
                f.column,
                f.name,
                f.message,
            )
            for f in findings
        ]
        with self._lock:
            self._conn.executemany(_INSERT_FINDING, rows)
            self._conn.commit()

    def insert_definitions(
        self, session_id: str, definitions: list[Definition]
    ) -> None:
        """Persist *definitions* for *session_id* in the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        rows = [
            (session_id, str(d.file_path), d.line, d.column, d.name, d.kind)
            for d in definitions
        ]
        with self._lock:
            self._conn.executemany(_INSERT_DEFINITION, rows)
            self._conn.commit()

    def insert_identifiers(self, session_id: str, names: list[str]) -> None:
        """Persist usage *names* for *session_id* in the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        rows = [(session_id, name) for name in names]
        with self._lock:
            self._conn.executemany(_INSERT_IDENTIFIER, rows)
            self._conn.commit()

    def read_findings(self, session_id: str) -> list[dict[str, object]]:
        """Return every per-file finding recorded for *session_id*.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            rows = self._conn.execute(_SELECT_FINDINGS, (session_id,)).fetchall()
        return [
            {
                "category": row[0],
                "file": row[1],
                "line": row[2],
                "column": row[3],
                "name": row[4],
                "message": row[5],
            }
            for row in rows
        ]

    def compute_unused_symbols(
        self, session_id: str, ignore_patterns: list[re.Pattern[str]]
    ) -> list[dict[str, object]]:
        """Return a finding for every definition never referenced elsewhere.

        A definition is "unused" when its name never appears in the
        project-wide ``identifiers`` table collected for *session_id*. Names
        matching any of *ignore_patterns* (e.g. dunder methods, ``main``,
        test hooks) are suppressed.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            rows = self._conn.execute(
                _SELECT_UNUSED_DEFINITIONS, (session_id,)
            ).fetchall()
        results: list[dict[str, object]] = []
        for file_path, line, col, name, kind in rows:
            if any(p.search(name) for p in ignore_patterns):
                continue
            results.append(
                {
                    "category": CATEGORY_UNUSED_SYMBOL,
                    "file": file_path,
                    "line": line,
                    "column": col,
                    "name": name,
                    "message": f"{kind.capitalize()} '{name}' is never referenced.",
                }
            )
        return results

    def delete_session(self, session_id: str) -> None:
        """Remove every record belonging to *session_id* from the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            self._conn.execute(_DELETE_FINDINGS, (session_id,))
            self._conn.execute(_DELETE_DEFINITIONS, (session_id,))
            self._conn.execute(_DELETE_IDENTIFIERS, (session_id,))
            self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SessionStore:
        """Return *self* to support use as a context manager.

        Author: Ron Webb
        Since: 1.0.0
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Close the database connection on context manager exit.

        Author: Ron Webb
        Since: 1.0.0
        """
        self.close()
