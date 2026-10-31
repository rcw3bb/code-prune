"""Tests for store module.

Author: Ron Webb
Since: 1.0.0
"""

import re
from pathlib import Path

from code_prune.scanner import CATEGORY_UNREACHABLE, Definition, Finding
from code_prune.store import SessionStore


def _make_finding(
    name: str, line: int = 1, category: str = CATEGORY_UNREACHABLE
) -> Finding:
    """Return a minimal Finding for testing."""
    return Finding(
        category=category,
        file_path=Path("code.py"),
        line=line,
        column=0,
        name=name,
        message=f"finding for {name}",
    )


def _make_definition(name: str, kind: str = "function", line: int = 1) -> Definition:
    """Return a minimal Definition for testing."""
    return Definition(
        name=name, kind=kind, file_path=Path("code.py"), line=line, column=0
    )


def test_insert_and_read_findings(tmp_path: Path) -> None:
    """Inserted findings should appear in read_findings for the same session."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_findings("session-1", [_make_finding("a"), _make_finding("b")])
        findings = store.read_findings("session-1")
        names = [f["name"] for f in findings]
        assert "a" in names
        assert "b" in names
    finally:
        store.close()


def test_read_findings_ordered_by_file_and_line(tmp_path: Path) -> None:
    """read_findings should order results by file path then line number."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_findings(
            "s", [_make_finding("later", line=5), _make_finding("earlier", line=1)]
        )
        findings = store.read_findings("s")
        assert [f["name"] for f in findings] == ["earlier", "later"]
    finally:
        store.close()


def test_sessions_are_isolated(tmp_path: Path) -> None:
    """Findings from different sessions must not mix."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_findings("alpha", [_make_finding("alpha-finding")])
        store.insert_findings("beta", [_make_finding("beta-finding")])

        alpha_names = [f["name"] for f in store.read_findings("alpha")]
        beta_names = [f["name"] for f in store.read_findings("beta")]

        assert "alpha-finding" in alpha_names
        assert "beta-finding" not in alpha_names
        assert "beta-finding" in beta_names
    finally:
        store.close()


def test_delete_session_removes_only_that_session(tmp_path: Path) -> None:
    """delete_session should remove only the specified session's records."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_findings("to-delete", [_make_finding("gone")])
        store.insert_findings("to-keep", [_make_finding("stays")])

        store.delete_session("to-delete")

        assert store.read_findings("to-delete") == []
        kept = [f["name"] for f in store.read_findings("to-keep")]
        assert "stays" in kept
    finally:
        store.close()


def test_read_findings_empty_for_unknown_session(tmp_path: Path) -> None:
    """read_findings should return an empty list for an unknown session."""
    store = SessionStore(tmp_path / "test.db")
    try:
        assert store.read_findings("nonexistent-session") == []
    finally:
        store.close()


def test_compute_unused_symbols_flags_never_referenced_definition(
    tmp_path: Path,
) -> None:
    """A definition with no matching identifier usage must be reported unused."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_definitions("s", [_make_definition("orphan_func")])
        store.insert_identifiers("s", ["something_else"])
        results = store.compute_unused_symbols("s", [])
        names = [r["name"] for r in results]
        assert "orphan_func" in names
    finally:
        store.close()


def test_compute_unused_symbols_excludes_referenced_definition(tmp_path: Path) -> None:
    """A definition referenced elsewhere must not be reported unused."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_definitions("s", [_make_definition("used_func")])
        store.insert_identifiers("s", ["used_func"])
        results = store.compute_unused_symbols("s", [])
        names = [r["name"] for r in results]
        assert "used_func" not in names
    finally:
        store.close()


def test_compute_unused_symbols_applies_name_ignore_patterns(tmp_path: Path) -> None:
    """A definition matching an ignore pattern must be excluded even if unused."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_definitions("s", [_make_definition("main")])
        patterns = [re.compile("^main$")]
        results = store.compute_unused_symbols("s", patterns)
        names = [r["name"] for r in results]
        assert "main" not in names
    finally:
        store.close()


def test_compute_unused_symbols_cross_file_resolution(tmp_path: Path) -> None:
    """Usages from a different file in the same session must still count."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_definitions(
            "s",
            [
                Definition(
                    name="shared",
                    kind="function",
                    file_path=Path("a.py"),
                    line=1,
                    column=0,
                )
            ],
        )
        store.insert_identifiers("s", ["shared"])
        results = store.compute_unused_symbols("s", [])
        names = [r["name"] for r in results]
        assert "shared" not in names
    finally:
        store.close()


def test_delete_session_clears_definitions_and_identifiers(tmp_path: Path) -> None:
    """delete_session must also clear the definitions/identifiers tables."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_definitions("s", [_make_definition("orphan")])
        store.insert_identifiers("s", ["noise"])
        store.delete_session("s")
        results = store.compute_unused_symbols("s", [])
        assert results == []
    finally:
        store.close()


def test_insert_empty_lists_are_noop(tmp_path: Path) -> None:
    """Inserting empty lists should not raise and should produce no records."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_findings("s", [])
        store.insert_definitions("s", [])
        store.insert_identifiers("s", [])
        assert store.read_findings("s") == []
    finally:
        store.close()


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    """Using SessionStore as a context manager should close it on exit."""
    with SessionStore(tmp_path / "test.db") as store:
        store.insert_findings("s", [_make_finding("x")])
        assert store.read_findings("s")
