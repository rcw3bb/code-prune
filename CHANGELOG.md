# Changelog

## 1.1.0 - 2026-11-05

### Added

- `todo-marker` category: `TODO`/`FIXME`/`XXX` comments are reported separately
  from `obsolete` since they are not necessarily obsolete.
- `--categories` now accepts `unused-import`, `unused-local` and `unused-symbol`
  explicitly; `unused` remains as shorthand for all three.
- `category-counts` in the JSON report, and per-category counts in the HTML
  report category filter dropdown.
- A `.codepruneignore` in the target path extends the configured ignore
  patterns; it is not affected by `config.ini`.

### Changed

- The HTML report's category filter is now a dropdown of the categories present
  in the report (with counts).
- Only supported source files are read; all other files are skipped.
- `obsolete` now covers `@deprecated`-style markers and `deprecated` comments
  only (TODO/FIXME/XXX moved to `todo-marker`).
- README: installation uses `pip install code-prune`; Poetry instructions moved
  to a Development section.

### Fixed

- Comments following a terminating statement are no longer reported as
  unreachable code.
- Documentation comments (Javadoc/JSDoc `/** ... */`) are no longer reported as
  commented-out code.

## 1.0.0 - 2026-11-01

### Added

- Core dead-code CLI: `code-prune <path> [options]`, built on Click and Rich,
  mirroring the `litscan` basis project's architecture.
- Tree-sitter based detection across Python, JavaScript, TypeScript, Java,
  and Gosu for five categories of findings: unreachable code, unused imports
  & local variables, cross-file unused functions/classes/methods, obsolete
  (`@deprecated`/TODO/FIXME) markers, and commented-out code.
- `config.ini` with an `[override] ignore-file` setting, a bundled
  `.codepruneignore` (gitignore-style path exclusions), and a bundled
  `symbol_ignore` (regex symbol-name exclusions for unused-symbol findings).
- SQLite-backed `SessionStore` for concurrent per-file scanning and a
  SQL-aggregated cross-file "unused symbol" resolution pass.
- JSON and HTML report output via `--format`.

### Fixed

- Upgraded `tree-sitter-gosu` to `>=0.3.0,<0.4.0`, which decomposes `${...}`
  string interpolation into real `interpolation`/`identifier` nodes. This
  resolves a false-positive `unused-local`/`unused-import`/`unused-symbol`
  finding for Gosu names referenced only inside string interpolation (e.g.
  `"... ${myVar} ..."`).
