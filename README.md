# code-prune

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/rcw3bb/code-prune/blob/main/LICENSE) [![Version](https://img.shields.io/badge/Version-1.0.0-green.svg)](https://github.com/rcw3bb/code-prune/blob/main/CHANGELOG.md) [![Python](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/) [![PyPI](https://img.shields.io/badge/PyPI-code-prune-orange)](https://pypi.org/project/code-prune/)


A CLI tool that scans a codebase for unreachable, unused, and obsolete code,
helping you find dead code before it becomes technical debt.

## Features

`code-prune` parses source files with [tree-sitter](https://tree-sitter.github.io/tree-sitter/)
and reports five categories of findings across **Python, JavaScript,
TypeScript, Java, and Gosu**:

- **Unreachable code** — statements after `return`/`raise`/`throw`/`break`/
  `continue`, and `if` branches whose condition is a constant falsy literal
  (`False`/`false`/`0`).
- **Unused imports & local variables** — per-file, syntactic detection of
  bindings that are never referenced again in the same file.
- **Unused functions/classes/methods** — cross-file detection of definitions
  that are never referenced anywhere in the scanned project.
- **Obsolete markers** — `@deprecated`/`@Deprecated`-style decorators and
  annotations, plus `TODO`/`FIXME`/`XXX` comment tags.
- **Commented-out code** — comments whose content heuristically resembles
  source code.

> Detection is heuristic and syntactic rather than a full scope- or
> call-graph-aware analysis — treat findings as a starting point for review,
> not a guarantee.

## Requirements

- Python `>=3.14`
- Poetry `2.2`

## Installation

```powershell
poetry install
```

## Usage

```powershell
poetry run code-prune <path> [options]
```

Common options:

| Option            | Description                                                                 |
|-------------------|------------------------------------------------------------------------------|
| `--ext`           | Comma-separated extensions to include (e.g. `py,js,ts,java,gs,gsx`).         |
| `--categories`    | Comma-separated categories to report: `unreachable,unused,obsolete,commented-out` (default: all). |
| `--format`        | Output format: `json`, `html`, or `all` (default: `json`).                  |
| `--output`        | Base output filename without extension (default: `code-prune-output`).     |
| `--output-dir`    | Directory for the report file(s) (default: `reports`).                     |
| `--workers`       | Number of parallel worker threads used to scan files.                      |
| `--db`            | Path to the SQLite scratch database used during a scan run.                |
| `--target-list`   | Treat `path` as a file listing target paths, one per line.                 |

Example:

```powershell
poetry run code-prune src --categories unreachable,unused --format all
```

## Configuration

Logging is bootstrapped via `env-dir-bootstrap`. Set the `CODE_PRUNE_CONFIG_DIR`
environment variable to override the default configuration directory used to
resolve `logging.ini`, `config.ini`, `.codepruneignore`, and `symbol_ignore`.

### Ignoring files and directories

`.codepruneignore` holds gitignore-style patterns for files/directories to
exclude from scanning (mirroring `.gitignore` syntax). Override the filename
via `config.ini`:

```ini
[override]
ignore-file = .codepruneignore
```

### Ignoring symbol names

`symbol_ignore` holds one regex pattern per line, matched against symbol
names to suppress from "unused function/class/method" findings — useful for
dunder methods, `main`, test hooks (`test_*`, `setUp`), and similar
intentionally-unreferenced symbols.

## Development

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
