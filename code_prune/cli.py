"""Command-line interface for code_prune.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import click
from braincraft.ignorefile import IgnoreFile
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from logenrich import setup_logger

from . import __version__
from . import __app_name__ as _APP_NAME
from . import CONF_DIR
from . import PATH_IGNORE_PATH
from . import SYMBOL_IGNORE_PATH
from .config import Config
from .reporter import write_outputs
from .scanner import CLI_CATEGORIES, load_name_ignore_patterns, scan_file
from .store import SessionStore

_VALID_FORMATS = ("json", "html", "all")


def _configure_stream_encoding(stream: object) -> None:
    """Force *stream* to UTF-8 with a replacing error handler when possible.

    Prevents UnicodeEncodeError on legacy Windows code pages or restrictive
    locales. Streams without ``reconfigure`` (e.g. click's test runner) are
    left untouched instead of raising.

    Author: Ron Webb
    Since: 1.0.0
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


_configure_stream_encoding(sys.stdout)
_configure_stream_encoding(sys.stderr)
_console = Console(stderr=True)
_logger = setup_logger(__name__, conf_dir=CONF_DIR)
_config = Config()


def _parse_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extension string into a normalised list.

    Each entry is lowercased and prefixed with a dot when absent.
    Example: ``"py,js, TS"`` -> ``['.py', '.js', '.ts']``

    Author: Ron Webb
    Since: 1.0.0
    """
    result: list[str] = []
    for part in raw.split(","):
        ext = part.strip().lower()
        if ext and not ext.startswith("."):
            ext = "." + ext
        if ext:
            result.append(ext)
    return result


def _parse_paths(raw: str) -> list[Path]:
    """Parse a semicolon-separated path string into a list of Path objects.

    Example: ``"/src/a; /src/b"`` -> ``[Path('/src/a'), Path('/src/b')]``

    Author: Ron Webb
    Since: 1.0.0
    """
    result: list[Path] = []
    for part in raw.split(";"):
        stripped = part.strip()
        if stripped:
            result.append(Path(stripped))
    return result


def _read_target_list(list_file: Path) -> list[Path]:
    """Read one target path per line from *list_file*.

    Blank lines and lines starting with ``#`` are skipped.

    Author: Ron Webb
    Since: 1.0.0
    """
    result: list[Path] = []
    for line in list_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.append(Path(stripped))
    return result


def _parse_categories(raw: str) -> set[str]:
    """Parse a comma-separated category string into a validated set.

    Raises :class:`click.UsageError` when an unknown category is given.

    Author: Ron Webb
    Since: 1.0.0
    """
    requested = {part.strip().lower() for part in raw.split(",") if part.strip()}
    unknown = requested - set(CLI_CATEGORIES)
    if unknown:
        raise click.UsageError(
            f"Unknown categories: {', '.join(sorted(unknown))}. "
            f"Valid categories: {', '.join(CLI_CATEGORIES)}."
        )
    return requested


def _scan_and_store(task: tuple[Path, SessionStore, str, set[str]]) -> None:
    """Scan one file and write its results to the session store.

    Accepts a 4-tuple so the function can be passed directly to
    :meth:`concurrent.futures.Executor.map` without a closure.

    Author: Ron Webb
    Since: 1.0.0
    """
    file_path, store, session_id, categories = task
    result = scan_file(file_path)
    findings = [f for f in result.findings if _category_enabled(f.category, categories)]
    store.insert_findings(session_id, findings)
    if "unused" in categories:
        store.insert_definitions(session_id, result.definitions)
    store.insert_identifiers(session_id, result.usages)


def _category_enabled(category: str, categories: set[str]) -> bool:
    """Return whether *category* should be reported given selected *categories*.

    Author: Ron Webb
    Since: 1.0.0
    """
    if category == "unreachable":
        return "unreachable" in categories
    if category in ("unused-import", "unused-local", "unused-symbol"):
        return "unused" in categories
    if category == "obsolete":
        return "obsolete" in categories
    if category == "commented-out":
        return "commented-out" in categories
    return False


def _load_ignore_file(ignore_path: Path, base_dir: Path) -> IgnoreFile | None:
    """Load an :class:`IgnoreFile` from *ignore_path*, logging failures.

    Returns ``None`` on a missing or non-UTF-8 file instead of raising.

    Author: Ron Webb
    Since: 1.0.0
    """
    try:
        return IgnoreFile(ignore_path, base_dir=base_dir)
    except FileNotFoundError:
        _logger.warning("Ignore file not found at %s", ignore_path)
        return None
    except UnicodeDecodeError as exc:
        _logger.warning("Ignore file at %s is not valid UTF-8: %s", ignore_path, exc)
        return None


def _build_ignore(base_dir: Path) -> IgnoreFile | None:
    """Build a path-ignore matcher anchored at *base_dir*.

    The ignore filename is resolved from ``config.ini``'s
    ``[override] ignore-file`` setting under :data:`CONF_DIR`; when that file
    is missing, the bundled default ``.codepruneignore`` is tried instead.
    Returns ``None`` when neither ignore file is usable, so callers can
    proceed without path filtering instead of failing the whole scan.

    Author: Ron Webb
    Since: 1.0.0
    """
    custom_path = Path(CONF_DIR) / _config.get_ignore_file()
    ignore = _load_ignore_file(custom_path, base_dir)
    _logger.debug("Loaded ignore file from %s: %s", custom_path, ignore)
    if ignore is not None:
        return ignore
    if custom_path == Path(PATH_IGNORE_PATH):
        return None
    return _load_ignore_file(Path(PATH_IGNORE_PATH), base_dir)


def _walk_unignored(
    root: Path, ignore: IgnoreFile | None
) -> Generator[Path, None, None]:
    """Recursively yield files under *root*, pruning directories matched by *ignore*.

    Author: Ron Webb
    Since: 1.0.0
    """
    for entry in root.iterdir():
        if ignore is not None and ignore.is_ignored(entry):
            continue
        if entry.is_dir():
            yield from _walk_unignored(entry, ignore)
        elif entry.is_file():
            yield entry


def discover_files(
    path: Path, extensions: list[str], ignore: IgnoreFile | None = None
) -> list[Path]:
    """Discover files under *path* that match the given extensions.

    When *extensions* is empty every file is included.
    Both files and directories are accepted; for a plain file the extension
    filter still applies. When *ignore* is given, matching files are skipped
    and matching directories are pruned from the walk entirely.

    Author: Ron Webb
    Since: 1.0.0
    """
    candidates: list[Path]
    if path.is_file():
        candidates = [] if ignore is not None and ignore.is_ignored(path) else [path]
    elif path.is_dir():
        candidates = sorted(_walk_unignored(path, ignore))
    else:
        return []

    if not extensions:
        return candidates
    return [f for f in candidates if f.suffix.lower() in extensions]


def _run_concurrent_scan(
    files: list[Path],
    store: SessionStore,
    session_id: str,
    workers: int,
    categories: set[str],
) -> None:
    """Scan *files* concurrently and store results under *session_id*.

    Displays a live progress bar via the module-level rich console.

    Author: Ron Webb
    Since: 1.0.0
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Scanning\u2026", total=len(files))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_scan_and_store, (f, store, session_id, categories)): f
                for f in files
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    _logger.warning("Failed to scan %s: %s", futures[future], exc)
                progress.advance(task)


@click.command()
@click.version_option(
    version=__version__, prog_name=_APP_NAME, message="%(prog)s v%(version)s"
)
@click.argument("path")
@click.option(
    "--ext",
    default="",
    help=(
        "Comma-separated file extensions to include "
        "(e.g. py,java,js,ts,gs,gsx). Omit to scan all files."
    ),
)
@click.option(
    "--output",
    default="code-prune-output",
    help=(
        "Base name (without extension) for the output file(s) "
        "(default: code-prune-output)."
    ),
)
@click.option(
    "--output-dir",
    "output_dir",
    default="reports",
    type=click.Path(path_type=Path),
    help=(
        "Directory where the output file will be written "
        "(default: reports). "
        "The filename from --output is placed inside this directory."
    ),
)
@click.option(
    "--format",
    "fmt",
    default="json",
    type=click.Choice(_VALID_FORMATS),
    help="Output format: json, html, or all (default: json).",
)
@click.option(
    "--workers",
    type=int,
    default=min(32, (os.cpu_count() or 1) + 4),
    help=(
        "Number of parallel worker threads used to scan files "
        "(default: min(32, cpu_count + 4))."
    ),
)
@click.option(
    "--db",
    "db_path",
    default=str(Path(tempfile.gettempdir()) / "code_prune.db"),
    type=click.Path(path_type=Path),
    help=(
        "Path to the SQLite scratch database used to store scan results "
        "during a run (default: <system-temp>/code_prune.db). "
        "Session records are removed after the report is written."
    ),
)
@click.option(
    "--categories",
    default=",".join(CLI_CATEGORIES),
    help=(
        "Comma-separated categories to report: "
        f"{', '.join(CLI_CATEGORIES)} (default: all). "
        "'unused' covers unused imports, local variables, and "
        "cross-file-unused functions/classes/methods."
    ),
)
@click.option(
    "--target-list",
    "target_list",
    is_flag=True,
    default=False,
    help=(
        "Treat PATH as a single existing file listing target paths (files "
        "and/or directories), one per line, instead of a semicolon-separated "
        "path list. Blank lines and lines starting with '#' are skipped."
    ),
)
def main(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    path: str,
    ext: str,
    output: str,
    output_dir: Path,
    fmt: str,
    workers: int,
    db_path: Path,
    categories: str,
    target_list: bool,
) -> None:
    """Scan source files for unreachable, unused, and obsolete code.

    Author: Ron Webb
    Since: 1.0.0
    """
    _header = f"{_APP_NAME} v{__version__}"
    _logger.info(_header)
    _console.print(f"[bold]{_header}[/bold]")
    extensions = _parse_extensions(ext) if ext else []
    selected_categories = _parse_categories(categories)
    paths = _parse_paths(path)
    if target_list:
        if len(paths) != 1 or not paths[0].is_file():
            raise click.UsageError(
                "--target-list requires PATH to be a single existing file."
            )
        paths = _read_target_list(paths[0])

    files = _discover_all_files(paths, extensions)
    if not files:
        _logger.info("No files found in %s", path)
        _console.print("[yellow]No files found.[/yellow]")
        return

    _console.print(f"[bold]Scanning[/bold] {len(files)} file(s)\u2026")

    findings, interrupted = _scan_project(files, db_path, workers, selected_categories)

    if interrupted:
        raise SystemExit(1)

    stem = Path(output).stem
    written = write_outputs(
        findings,
        output_dir,
        stem,
        fmt,
        paths_scanned=[str(p) for p in paths],
        categories=sorted(selected_categories),
    )

    _logger.info(
        "Found %s finding(s) -> %s", len(findings), ", ".join(str(w) for w in written)
    )
    _console.print(
        f"[bold green]Found {len(findings)} finding(s)[/bold green] -> "
        + ", ".join(str(w) for w in written)
    )


def _discover_all_files(paths: list[Path], extensions: list[str]) -> list[Path]:
    """Discover the de-duplicated set of files to scan across *paths*.

    Author: Ron Webb
    Since: 1.0.0
    """
    seen: set[Path] = set()
    files: list[Path] = []
    with _console.status("[bold cyan]Discovering files\u2026", spinner="dots"):
        for target_path in paths:
            ignore = _build_ignore(target_path)
            for found_file in discover_files(target_path, extensions, ignore):
                if found_file not in seen:
                    seen.add(found_file)
                    files.append(found_file)
    return files


def _scan_project(
    files: list[Path], db_path: Path, workers: int, categories: set[str]
) -> tuple[list[dict[str, object]], bool]:
    """Run the full scan pipeline and return ``(findings, interrupted)``.

    Author: Ron Webb
    Since: 1.0.0
    """
    session_id = str(uuid.uuid4())
    store = SessionStore(db_path)
    interrupted = False
    findings: list[dict[str, object]] = []
    try:
        _run_concurrent_scan(files, store, session_id, workers, categories)
        findings = store.read_findings(session_id)
        if "unused" in categories:
            name_ignore_patterns = load_name_ignore_patterns(Path(SYMBOL_IGNORE_PATH))
            findings.extend(
                store.compute_unused_symbols(session_id, name_ignore_patterns)
            )
    except KeyboardInterrupt:
        interrupted = True
        _console.print("[yellow]Scan interrupted by user.[/yellow]")
    finally:
        store.delete_session(session_id)
        store.close()
    return findings, interrupted
