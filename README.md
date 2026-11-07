# code-prune

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/rcw3bb/code-prune/blob/main/LICENSE) [![Version](https://img.shields.io/badge/Version-1.1.0-green.svg)](https://github.com/rcw3bb/code-prune/blob/main/CHANGELOG.md) [![Python](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/) [![PyPI](https://img.shields.io/badge/PyPI-code--prune-orange)](https://pypi.org/project/code-prune/)


A CLI tool that scans a codebase for unreachable, unused, and obsolete code,
helping you find dead code before it becomes technical debt.

## Features

`code-prune` parses source files with [tree-sitter](https://tree-sitter.github.io/tree-sitter/)
and reports six categories of findings across **Python, JavaScript,
TypeScript, Java, and Gosu**:

- **Unreachable code** — statements after `return`/`raise`/`throw`/`break`/
  `continue`, and `if` branches whose condition is a constant falsy literal
  (`False`/`false`/`0`). Comments are never reported as unreachable.
- **Unused imports & local variables** — per-file, syntactic detection of
  bindings that are never referenced again in the same file.
- **Unused functions/classes/methods** — cross-file detection of definitions
  that are never referenced anywhere in the scanned project.
- **Obsolete markers** — `@deprecated`/`@Deprecated`-style decorators and
  annotations, plus comments mentioning `deprecated`.
- **TODO markers** — `TODO`/`FIXME`/`XXX` comment tags (not necessarily
  obsolete, so reported separately).
- **Commented-out code** — comments whose content heuristically resembles
  source code. Documentation comments (Javadoc/JSDoc `/** ... */`) and Python
  docstrings are not treated as commented-out code.

Only supported files (`.py`, `.pyi`, `.js`, `.mjs`, `.cjs`, `.ts`, `.tsx`,
`.java`, `.gs`, `.gsx`) are read; every other file is skipped.

> Detection is heuristic and syntactic rather than a full scope- or
> call-graph-aware analysis — treat findings as a starting point for review,
> not a guarantee.

## Requirements

- Python `>=3.14`

## Installation

```powershell
pip install code-prune
```

## Usage

```powershell
code-prune <path> [options]
```

Common options:

| Option            | Description                                                                 |
|-------------------|------------------------------------------------------------------------------|
| `--ext`           | Comma-separated extensions to include (e.g. `py,js,ts,java,gs,gsx`). Omit to scan every supported file. |
| `--categories`    | Comma-separated categories to report: `unreachable`, `unused-import`, `unused-local`, `unused-symbol`, `obsolete`, `todo-marker`, `commented-out`. `unused` is shorthand for all three `unused-*` categories (default: all). |
| `--format`        | Output format: `json`, `html`, or `all` (default: `json`).                  |
| `--output`        | Base output filename without extension (default: `code-prune-output`).     |
| `--output-dir`    | Directory for the report file(s) (default: `reports`).                     |
| `--workers`       | Number of parallel worker threads used to scan files.                      |
| `--db`            | Path to the SQLite scratch database used during a scan run.                |
| `--target-list`   | Treat `path` as a file listing target paths, one per line.                 |

Example:

```powershell
code-prune src --categories unreachable,unused-import,todo-marker --format all
```

### Reports

Both report formats include the number of findings per category: the JSON
report has a `category-counts` object, and the HTML report shows the counts in
its summary and in a category dropdown filter listing the categories present
in the report.

## Configuration

Logging is bootstrapped via `env-dir-bootstrap`. Set the `CODE_PRUNE_CONFIG_DIR`
environment variable to override the default configuration directory used to
resolve `logging.ini`, `config.ini`, `.codepruneignore`, and `symbol_ignore`.

### Ignoring files and directories

`.codepruneignore` holds gitignore-style patterns for files/directories to
exclude from scanning (mirroring `.gitignore` syntax). Override the filename
used in the configuration directory via `config.ini`:

```ini
[override]
ignore-file = .codepruneignore
```

In addition, a `.codepruneignore` placed in the target path (the scanned
directory, or the directory containing a scanned file) extends those patterns.
It always uses that fixed name and is not affected by `config.ini`.

### Ignoring symbol names

`symbol_ignore` holds one regex pattern per line, matched against symbol
names to suppress from "unused function/class/method" findings — useful for
dunder methods, `main`, test hooks (`test_*`, `setUp`), and similar
intentionally-unreferenced symbols.

## Development

Development uses [Poetry](https://python-poetry.org/) `2.2`.

Install the project and its dev dependencies:

```powershell
poetry install
```

Run the CLI from the working tree:

```powershell
poetry run code-prune <path> [options]
```

Run tests with coverage and generate an HTML report:

```powershell
poetry run pytest --cov=code_prune tests --cov-report html
```

Format and lint the code:

```powershell
poetry run black code_prune; poetry run pylint code_prune
```

## License

This project is licensed under the [MIT License](LICENSE).
