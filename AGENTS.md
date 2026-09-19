## Purpose

`code-prune` is a Python `>=3.14` tool that finds unreachable, unused, and obsolete
code before it becomes technical debt. It is packaged with Poetry `2.2` using
PEP 621 metadata. Logging uses `logenrich` (`setup_logger`) and configuration
directory bootstrapping uses `env-dir-bootstrap` (`EnvDirBootstrap`), wired up in
`code_prune/__init__.py`, which exposes `CONF_DIR` and `__version__`.

- Install: `poetry install`
- Test + coverage: `poetry run pytest --cov=code_prune tests --cov-report html`
- Format + lint: `poetry run black code_prune; poetry run pylint code_prune`
- Lint must always score 10.00/10 (config in `.pylintrc`).
- Minimum test coverage: 80%.

## Tree

- code_prune/ — main package; all new modules go here
- code_prune/__init__.py — defines `__version__`, bootstraps `CONF_DIR` via `env-dir-bootstrap`
- code_prune/logging.ini — `logenrich` logging config, packaged as a resource (log file: `code_prune.log`)
- tests/ — test package, mirrors `code_prune/` structure; modules named `test_*.py`
- .pylintrc — Pylint configuration (must score 10/10)
- pyproject.toml — PEP 621 project metadata, `[dependency-groups] dev`, `[tool.poetry]` packages/include
- CHANGELOG.md — Keep a Changelog format
- README.md — includes license and version badges
- LICENSE — MIT License

## Rules

- Place all new modules in `code_prune/`, mirrored by a `test_*.py` module in `tests/` in the same relative location.
- Use relative imports within the package.
- Add docstrings to every module, class, and method; include `Author: Ron Webb` and `Since: <version>` in module docstrings (add author/since to new methods/classes in existing modules only when the project version is not 1.0.0).
- Use type hints for all arguments and return values; use `collections.abc`, never deprecated `typing` aliases.
- Naming: snake_case for methods/variables, PascalCase for classes, UPPER_CASE for constants. Prefix private/protected members with `_`.
- Follow SOLID and DRY; prefer composition over inheritance; use dependency injection where applicable; decompose large methods into smaller private ones.
- Use `logenrich`'s `setup_logger` with `conf_dir=CONF_DIR` for any module that logs; do not hand-roll logging config.
- Use `python-dotenv` whenever reading `.env` values.
- Use `poetry add` / `poetry add --group dev` to manage dependencies — never hand-edit dependency version strings without re-running these.
- Never modify `pyproject.toml`'s `[tool.poetry]`, `[build-system]`, or dependency-group format without re-checking this file's Purpose section.
- Before releasing a version bump, update `CHANGELOG.md` (Keep a Changelog format) and the version badge in `README.md`.
- When you create or discover new files, update the Tree above.

## Note-taking

- After each task, log any correction, preference, or pattern learned.
- Write one dated line in plain language under a "Session learnings" note below;
  if none fits, add to Rules above instead.
  e.g. "Prefer X over Y for Z (learned 9/20)"
- 3+ related notes on one topic → create a `docs/` context file, move the notes
  there, and update the Tree. Keep this file under 100 lines.

### Session learnings

(Notes will be added here as the AI learns from each task.)
