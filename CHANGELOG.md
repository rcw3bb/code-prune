# Changelog

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
