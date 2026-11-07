"""Tests for reporter module.

Author: Ron Webb
Since: 1.0.0
"""

import json
from pathlib import Path

from code_prune.reporter import write_outputs


def _finding(
    category: str = "unreachable", name: str = "x", message: str = "msg"
) -> dict[str, object]:
    """Return a minimal finding dict for testing."""
    return {
        "category": category,
        "file": "a.py",
        "line": 1,
        "column": 0,
        "name": name,
        "message": message,
    }


def test_write_outputs_json_creates_file_with_expected_schema(tmp_path: Path) -> None:
    """JSON output should include application metadata and the findings list."""
    written = write_outputs(
        [_finding()],
        tmp_path,
        "report",
        "json",
        paths_scanned=["src"],
        categories=["unreachable"],
    )
    assert len(written) == 1
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["application"] == "code-prune"
    assert data["paths-scanned"] == ["src"]
    assert data["categories"] == ["unreachable"]
    assert len(data["findings"]) == 1
    assert data["findings"][0]["name"] == "x"
    assert data["category-counts"] == {"unreachable": 1}


def test_json_category_counts_include_each_category(tmp_path: Path) -> None:
    """category-counts must count findings per category, zeros included."""
    findings = [_finding("obsolete"), _finding("obsolete"), _finding("unreachable")]
    written = write_outputs(
        findings,
        tmp_path,
        "report",
        "json",
        paths_scanned=["src"],
        categories=["obsolete", "todo-marker", "unreachable"],
    )
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["category-counts"] == {
        "obsolete": 2,
        "todo-marker": 0,
        "unreachable": 1,
    }


def test_html_category_filter_is_dropdown_of_available_categories(
    tmp_path: Path,
) -> None:
    """The HTML category filter must be a <select> of categories with findings."""
    written = write_outputs(
        [_finding("obsolete"), _finding("obsolete"), _finding("unreachable")],
        tmp_path,
        "report",
        "html",
        paths_scanned=["src"],
        categories=["obsolete", "todo-marker", "unreachable"],
    )
    html = written[0].read_text(encoding="utf-8")
    assert '<select id="filter-category"' in html
    assert '<option value="">All categories</option>' in html
    assert '<option value="obsolete">obsolete (2)</option>' in html
    assert '<option value="unreachable">unreachable (1)</option>' in html
    assert 'value="todo-marker"' not in html
    assert 'type="text" id="filter-category"' not in html
    assert "Found 3 finding(s)</p>" in html
    assert "obsolete: 2" not in html


def test_write_outputs_html_creates_valid_html(tmp_path: Path) -> None:
    """HTML output should contain the report title and an escaped message."""
    written = write_outputs(
        [_finding(message="<script>alert(1)</script>")],
        tmp_path,
        "report",
        "html",
        paths_scanned=["src"],
        categories=["unreachable"],
    )
    html = written[0].read_text(encoding="utf-8")
    assert "code-prune" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_outputs_all_writes_both_files(tmp_path: Path) -> None:
    """fmt='all' should write both a JSON and an HTML file."""
    written = write_outputs(
        [_finding()],
        tmp_path,
        "report",
        "all",
        paths_scanned=["src"],
        categories=["unreachable"],
    )
    suffixes = sorted(p.suffix for p in written)
    assert suffixes == [".html", ".json"]


def test_write_outputs_creates_missing_output_dir(tmp_path: Path) -> None:
    """The output directory should be created when it does not already exist."""
    target_dir = tmp_path / "nested" / "reports"
    written = write_outputs(
        [_finding()],
        target_dir,
        "report",
        "json",
        paths_scanned=["src"],
        categories=["unreachable"],
    )
    assert written[0].exists()


def test_write_outputs_empty_findings_still_writes_valid_report(tmp_path: Path) -> None:
    """An empty findings list should still produce a valid, empty report."""
    written = write_outputs(
        [], tmp_path, "report", "json", paths_scanned=["src"], categories=[]
    )
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["findings"] == []
