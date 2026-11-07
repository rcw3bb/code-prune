"""Report generation for code_prune: JSON and HTML output writers.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime
from pathlib import Path

from . import __version__

_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f5f7fa;
    color: #2c3e50;
    padding: 2em;
  }
  header {
    background: #1a3a5c;
    color: #ffffff;
    border-radius: 8px;
    padding: 1.2em 1.8em;
    margin-bottom: 1.5em;
  }
  header h1 { font-size: 1.6em; font-weight: 700; letter-spacing: 0.02em; }
  header p  { font-size: 0.9em; margin-top: 0.3em; opacity: 0.85; }
  .summary {
    font-size: 0.9em;
    color: #555;
    margin-bottom: 1em;
  }
  .table-wrap { overflow-x: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
  table {
    border-collapse: collapse;
    width: 100%;
    background: #ffffff;
    font-size: 0.88em;
  }
  thead tr { background: #1a3a5c; color: #ffffff; }
  th {
    padding: 0.75em 1em;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { background: #254e80; }
  th.sortable .sort-icon { margin-left: 0.4em; font-size: 0.8em; }
  th.sortable.asc .sort-icon::after { content: '\\25b2'; }
  th.sortable.desc .sort-icon::after { content: '\\25bc'; }
  th.sortable:not(.asc):not(.desc) .sort-icon::after { content: '\\21c5'; opacity: 0.6; }
  .filter-row th { background: #1a3a5c; padding: 0.3em 1em 0.5em; }
  .filter-row input, .filter-row select {
    width: 100%;
    padding: 0.3em 0.5em;
    border: 1px solid #3d6b9e;
    border-radius: 4px;
    background: #1e4575;
    color: #fff;
    font-size: 0.85em;
    outline: none;
  }
  .filter-row input::placeholder { color: #aac4e8; }
  .filter-row input:focus, .filter-row select:focus { border-color: #7eb3e8; background: #255085; }
  td {
    padding: 0.6em 1em;
    border-bottom: 1px solid #e8ecf0;
    vertical-align: top;
  }
  tbody tr.alt-row { background: #f0f4f8; }
  tbody tr:hover { background: #dde9f7; }
  td.row-num { text-align: right; color: #7f8c8d; font-variant-numeric: tabular-nums; width: 3em; }
  td.category code {
    background: #eef2f7;
    border-radius: 3px;
    padding: 0.1em 0.4em;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 0.9em;
  }
  td.location { font-family: 'Consolas', 'Courier New', monospace; font-size: 0.85em; color: #555; }
  td.name code { font-family: 'Consolas', 'Courier New', monospace; font-size: 0.9em; }
  td.message { word-break: break-word; }
  footer { margin-top: 1.5em; font-size: 0.8em; color: #aaa; text-align: center; }
"""


def _category_counts(
    findings: list[dict[str, object]], categories: list[str]
) -> dict[str, int]:
    """Return the number of findings per category, sorted by category name.

    Every selected category is present, with ``0`` when it has no findings.

    Author: Ron Webb
    Since: 1.1.0
    """
    counts = dict.fromkeys(categories, 0)
    for finding in findings:
        category = str(finding["category"])
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _write_json(
    findings: list[dict[str, object]],
    path: Path,
    run_date: str,
    paths_scanned: list[str],
    categories: list[str],
) -> None:
    """Write findings as a JSON file.

    Author: Ron Webb
    Since: 1.0.0
    """
    report = {
        "application": "code-prune",
        "version": __version__,
        "run-date": run_date,
        "paths-scanned": paths_scanned,
        "categories": categories,
        "category-counts": _category_counts(findings, categories),
        "findings": findings,
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _build_category_select(counts: dict[str, int]) -> str:
    """Return the category ``<select>`` listing categories that have findings.

    Author: Ron Webb
    Since: 1.1.0
    """
    options = ['<option value="">All categories</option>']
    for category, count in counts.items():
        if count:
            escaped = _html.escape(category, quote=True)
            options.append(f'<option value="{escaped}">{escaped} ({count})</option>')
    return (
        '<select id="filter-category" onchange="codePruneFilter()">'
        + "".join(options)
        + "</select>"
    )


def _build_thead_html(counts: dict[str, int]) -> str:
    """Return the HTML ``<thead>`` element with sortable headers and a filter row.

    Author: Ron Webb
    Since: 1.0.0
    """
    return (
        "    <thead>\n"
        "      <tr>"
        "<th>#</th>"
        '<th class="sortable" onclick="codePruneSortBy(0)">Category<span class="sort-icon"></span></th>'
        '<th class="sortable" onclick="codePruneSortBy(1)">Location<span class="sort-icon"></span></th>'
        '<th class="sortable" onclick="codePruneSortBy(2)">Name<span class="sort-icon"></span></th>'
        "<th>Message</th>"
        "</tr>\n"
        '      <tr class="filter-row">'
        "<th></th>"
        f"<th>{_build_category_select(counts)}</th>"
        '<th><input type="text" id="filter-location" placeholder="Filter location\u2026"'
        ' oninput="codePruneFilter()"></th>'
        '<th><input type="text" id="filter-name" placeholder="Filter name\u2026"'
        ' oninput="codePruneFilter()"></th>'
        "<th></th>"
        "</tr>\n"
        "    </thead>\n"
    )


def _build_summary(total: int) -> str:
    """Return the summary line with the total number of findings.

    Author: Ron Webb
    Since: 1.1.0
    """
    return f"Found {total} finding(s)"


def _build_html_scaffold(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    run_date: str,
    total: int,
    rows_html: str,
    script: str,
    paths_scanned: list[str],
    categories: list[str],
    counts: dict[str, int],
) -> str:
    """Wrap the table body and script into a complete HTML document.

    Author: Ron Webb
    Since: 1.0.0
    """
    thead = _build_thead_html(counts)
    paths_html = "<br>".join(_html.escape(p, quote=False) for p in paths_scanned)
    categories_html = (
        ", ".join(_html.escape(c, quote=False) for c in categories) or "(none)"
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>code-prune {__version__} Report</title>\n"
        "  <style>\n"
        f"{_CSS}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <header>\n"
        f"    <h1>code-prune {__version__} Report</h1>\n"
        f"    <p>Date Run: {run_date}</p>\n"
        f"    <p>Paths scanned: {paths_html}</p>\n"
        f"    <p>Categories: {categories_html}</p>\n"
        "  </header>\n"
        f'  <p class="summary">{_build_summary(total)}</p>\n'
        '  <div class="table-wrap">\n'
        "  <table>\n"
        f"{thead}"
        "    <tbody>\n"
        f"{rows_html}\n"
        "    </tbody>\n"
        "  </table>\n"
        "  </div>\n"
        f"  <footer>Generated by code-prune {__version__}</footer>\n"
        f"{script}"
        "</body>\n"
        "</html>\n"
    )


_SCRIPT = (
    "<script>\n"
    "(function () {\n"
    "  var sortCol = -1, sortDir = 1;\n"
    "\n"
    "  function sortBy(col) {\n"
    "    if (sortCol === col) { sortDir = -sortDir; }\n"
    "    else { sortCol = col; sortDir = 1; }\n"
    "    applySort();\n"
    "  }\n"
    "\n"
    "  function applySort() {\n"
    "    var tbody = document.querySelector('tbody');\n"
    "    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));\n"
    "    var keys = ['category', 'location', 'name'];\n"
    "    rows.sort(function (a, b) {\n"
    "      if (sortCol < 0 || sortCol > 2) return 0;\n"
    "      var key = keys[sortCol];\n"
    "      var va = (a.dataset[key] || '').toLowerCase();\n"
    "      var vb = (b.dataset[key] || '').toLowerCase();\n"
    "      if (va < vb) return -sortDir;\n"
    "      if (va > vb) return sortDir;\n"
    "      return 0;\n"
    "    });\n"
    "    rows.forEach(function (r) { tbody.appendChild(r); });\n"
    "    updateNumbers();\n"
    "    restripe();\n"
    "    updateSortIcons();\n"
    "  }\n"
    "\n"
    "  function updateSortIcons() {\n"
    "    var ths = document.querySelectorAll('thead tr:first-child th.sortable');\n"
    "    ths.forEach(function (th, i) {\n"
    "      th.classList.remove('asc', 'desc');\n"
    "      if (i === sortCol) { th.classList.add(sortDir === 1 ? 'asc' : 'desc'); }\n"
    "    });\n"
    "  }\n"
    "\n"
    "  function applyFilter() {\n"
    "    var catFilter = document.getElementById('filter-category').value;\n"
    "    var locFilter = document.getElementById('filter-location').value.toLowerCase();\n"
    "    var nameFilter = document.getElementById('filter-name').value.toLowerCase();\n"
    "    var tbody = document.querySelector('tbody');\n"
    "    tbody.querySelectorAll('tr').forEach(function (row) {\n"
    "      var catMatch = !catFilter || row.dataset.category === catFilter;\n"
    "      var locMatch = !locFilter || row.dataset.location.toLowerCase().indexOf(locFilter) !== -1;\n"
    "      var nameMatch = !nameFilter || row.dataset.name.toLowerCase().indexOf(nameFilter) !== -1;\n"
    "      row.style.display = (catMatch && locMatch && nameMatch) ? '' : 'none';\n"
    "    });\n"
    "    updateNumbers();\n"
    "    restripe();\n"
    "  }\n"
    "\n"
    "  function updateNumbers() {\n"
    "    var num = 1;\n"
    "    document.querySelectorAll('tbody tr').forEach(function (row) {\n"
    "      if (row.style.display !== 'none') {\n"
    "        row.querySelector('.row-num').textContent = num++;\n"
    "      }\n"
    "    });\n"
    "  }\n"
    "\n"
    "  function restripe() {\n"
    "    var num = 0;\n"
    "    document.querySelectorAll('tbody tr').forEach(function (row) {\n"
    "      if (row.style.display !== 'none') {\n"
    "        num++;\n"
    "        row.classList.toggle('alt-row', num % 2 === 0);\n"
    "      }\n"
    "    });\n"
    "  }\n"
    "\n"
    "  window.codePruneSortBy = sortBy;\n"
    "  window.codePruneFilter = applyFilter;\n"
    "})();\n"
    "</script>\n"
)


def _build_html(
    findings: list[dict[str, object]],
    run_date: str,
    paths_scanned: list[str],
    categories: list[str],
) -> str:
    """Build an HTML report string for the given findings.

    Author: Ron Webb
    Since: 1.0.0
    """
    rows: list[str] = []
    for idx, finding in enumerate(findings, start=1):
        category = str(finding["category"])
        location = f"{finding['file']}:{finding['line']}:{finding['column']}"
        name = str(finding["name"])
        message = str(finding["message"])
        alt = " alt-row" if idx % 2 == 0 else ""
        rows.append(
            f'      <tr class="data-row{alt}"'
            f' data-idx="{idx}"'
            f' data-category="{_html.escape(category, quote=True)}"'
            f' data-location="{_html.escape(location, quote=True)}"'
            f' data-name="{_html.escape(name, quote=True)}">'
            f'<td class="row-num">{idx}</td>'
            f'<td class="category"><code>{_html.escape(category, quote=False)}</code></td>'
            f'<td class="location">{_html.escape(location, quote=False)}</td>'
            f'<td class="name"><code>{_html.escape(name, quote=False)}</code></td>'
            f'<td class="message">{_html.escape(message, quote=False)}</td>'
            f"</tr>"
        )
    rows_html = "\n".join(rows)
    return _build_html_scaffold(
        run_date,
        len(findings),
        rows_html,
        _SCRIPT,
        paths_scanned,
        categories,
        _category_counts(findings, categories),
    )


def _write_html(
    findings: list[dict[str, object]],
    path: Path,
    run_date: str,
    paths_scanned: list[str],
    categories: list[str],
) -> None:
    """Write findings as an HTML report file.

    Author: Ron Webb
    Since: 1.0.0
    """
    path.write_text(
        _build_html(findings, run_date, paths_scanned, categories), encoding="utf-8"
    )


def write_outputs(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    findings: list[dict[str, object]],
    output_dir: Path,
    stem: str,
    fmt: str,
    paths_scanned: list[str],
    categories: list[str] | None = None,
) -> list[Path]:
    """Write output files according to the requested format.

    Returns the list of paths written.

    Author: Ron Webb
    Since: 1.0.0
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now().strftime(_DATE_FORMAT)
    categories = categories or []
    written: list[Path] = []
    if fmt in ("json", "all"):
        json_path = output_dir / f"{stem}.json"
        _write_json(findings, json_path, run_date, paths_scanned, categories)
        written.append(json_path)
    if fmt in ("html", "all"):
        html_path = output_dir / f"{stem}.html"
        _write_html(findings, html_path, run_date, paths_scanned, categories)
        written.append(html_path)
    return written
