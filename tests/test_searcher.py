"""Tests for searcher module.

Author: Ron Webb
Since: 1.2.0
"""

from pathlib import Path

from code_prune.searcher import SymbolSearcher


def _write(path: Path, text: str) -> Path:
    """Write *text* to *path* and return it."""
    path.write_text(text, encoding="utf-8")
    return path


def test_class_matches_whole_word_only(tmp_path: Path) -> None:
    """A class name must match as a whole word, not as part of another name."""
    hit = _write(tmp_path / "a.xml", '<bean class="com.acme.Widget"/>')
    miss = _write(tmp_path / "b.xml", "<bean class='WidgetFactory'/>")
    widget = ("Widget", "class", "src.py", None)
    gadget = ("Gadget", "class", "src.py", None)

    assert SymbolSearcher([hit, miss]).find_referenced([widget, gadget]) == {widget}
    assert SymbolSearcher([miss]).find_referenced([widget]) == set()


def test_free_function_matches_with_word_boundary_regex(tmp_path: Path) -> None:
    """A free function's name matches at word boundaries, '$' counting as a word char."""
    target = _write(tmp_path / "t.txt", "call: obj.run_job(1)\n$run_job2 other")
    run_job = ("run_job", "function", "src.py", None)
    run = ("run", "function", "src.py", None)
    run_job2 = ("run_job2", "function", "src.py", None)

    found = SymbolSearcher([target]).find_referenced([run_job, run, run_job2])

    assert found == {run_job}


def test_method_requires_both_class_and_method_name_in_same_file(
    tmp_path: Path,
) -> None:
    """A method is only referenced when its class and method names co-occur."""
    both = _write(tmp_path / "both.txt", "Job().run()")
    method_only = _write(tmp_path / "method_only.txt", "run()")
    class_only = _write(tmp_path / "class_only.txt", "Job()")
    candidate = ("run", "function", "src.py", "Job")

    assert SymbolSearcher([both]).find_referenced([candidate]) == {candidate}
    assert SymbolSearcher([method_only]).find_referenced([candidate]) == set()
    assert SymbolSearcher([class_only]).find_referenced([candidate]) == set()


def test_method_class_and_name_need_not_be_adjacent(tmp_path: Path) -> None:
    """The class and method names may appear far apart, in any order, in one file."""
    apart = _write(
        tmp_path / "apart.txt",
        "The Job class configures a pipeline.\n"
        + ("filler line\n" * 20)
        + "Call run() once the pipeline is ready.",
    )
    candidate = ("run", "function", "src.py", "Job")

    assert SymbolSearcher([apart]).find_referenced([candidate]) == {candidate}


def test_method_class_and_name_match_regardless_of_order(tmp_path: Path) -> None:
    """The method name may be mentioned before its class name in the same file."""
    reversed_order = _write(tmp_path / "reversed.txt", "run() is called by Job.")
    candidate = ("run", "function", "src.py", "Job")

    assert SymbolSearcher([reversed_order]).find_referenced([candidate]) == {candidate}


def test_method_class_and_name_must_be_in_same_search_file(tmp_path: Path) -> None:
    """Class and method names found in different files must not count as a match."""
    class_file = _write(tmp_path / "class_only.txt", "Job()")
    method_file = _write(tmp_path / "method_only.txt", "run()")
    candidate = ("run", "function", "src.py", "Job")

    found = SymbolSearcher([class_file, method_file]).find_referenced([candidate])

    assert found == set()


def test_field_requires_both_class_and_field_name_in_same_file(tmp_path: Path) -> None:
    """A field follows the method rule: field and class names must co-occur."""
    both = _write(tmp_path / "both.txt", "config.Job.timeout")
    field_only = _write(tmp_path / "field_only.txt", "timeout")
    candidate = ("timeout", "field", "src.py", "Job")

    assert SymbolSearcher([both]).find_referenced([candidate]) == {candidate}
    assert SymbolSearcher([field_only]).find_referenced([candidate]) == set()


def test_defining_file_is_ignored(tmp_path: Path) -> None:
    """The symbol's own file never counts as a reference."""
    own = _write(tmp_path / "own.py", "def orphan():\n    pass\n")
    candidate = ("orphan", "function", str(own), None)

    assert SymbolSearcher([own]).find_referenced([candidate]) == set()


def test_binary_and_missing_files_are_skipped(tmp_path: Path) -> None:
    """Binary and unreadable files are skipped instead of raising."""
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"orphan\x00orphan")
    candidate = ("orphan", "function", "src.py", None)

    searcher = SymbolSearcher([binary, tmp_path / "missing.txt"])

    assert searcher.find_referenced([candidate]) == set()


def test_file_count_reports_number_of_search_files(tmp_path: Path) -> None:
    """file_count must report the number of files the searcher was built with."""
    a = _write(tmp_path / "a.txt", "a")
    b = _write(tmp_path / "b.txt", "b")

    assert SymbolSearcher([a, b]).file_count == 2
    assert SymbolSearcher([]).file_count == 0


def test_on_progress_called_once_per_search_file(tmp_path: Path) -> None:
    """on_progress fires once per search file, including skipped/binary ones."""
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\x00")
    missing = tmp_path / "missing.txt"
    hit = _write(tmp_path / "hit.txt", "orphan")
    candidate = ("orphan", "function", "src.py", None)
    calls: list[None] = []

    found = SymbolSearcher([binary, missing, hit]).find_referenced(
        [candidate], on_progress=lambda: calls.append(None)
    )

    assert found == {candidate}
    assert len(calls) == 3


def test_on_progress_not_called_past_early_exit(tmp_path: Path) -> None:
    """on_progress is not invoked for files after every candidate is resolved."""
    hit = _write(tmp_path / "hit.txt", "orphan")
    never_reached = _write(tmp_path / "never.txt", "orphan")
    candidate = ("orphan", "function", "src.py", None)
    calls: list[None] = []

    SymbolSearcher([hit, never_reached]).find_referenced(
        [candidate], on_progress=lambda: calls.append(None)
    )

    assert len(calls) == 1


def test_parallel_workers_match_serial_results(tmp_path: Path) -> None:
    """Multiple reader threads yield the same hits and one progress call per file."""
    files = [_write(tmp_path / f"f{i}.txt", f"token{i} Job run") for i in range(25)]
    candidates = [
        ("token3", "class", "src.py", None),
        ("token24", "class", "src.py", None),
        ("run", "function", "src.py", "Job"),
        ("absent", "class", "src.py", None),
    ]
    calls: list[None] = []

    serial = SymbolSearcher(files).find_referenced(candidates)
    parallel = SymbolSearcher(files, workers=4).find_referenced(
        candidates, on_progress=lambda: calls.append(None)
    )

    assert parallel == serial == set(candidates[:3])
    assert len(calls) == len(files)


def test_parallel_workers_stop_after_last_candidate_resolved(tmp_path: Path) -> None:
    """Early exit and ordered progress still hold with a thread pool."""
    files = [_write(tmp_path / f"f{i}.txt", "orphan") for i in range(30)]
    candidate = ("orphan", "function", "src.py", None)
    calls: list[None] = []

    found = SymbolSearcher(files, workers=4).find_referenced(
        [candidate], on_progress=lambda: calls.append(None)
    )

    assert found == {candidate}
    assert len(calls) == 1


def test_names_with_non_word_characters_use_regex_fallback(tmp_path: Path) -> None:
    """Names containing non-word characters are still matched as whole words."""
    target = _write(tmp_path / "t.txt", "uses a-b here, but not a-bc")
    hit = ("a-b", "function", "src.py", None)
    miss = ("a-bd", "function", "src.py", None)

    assert SymbolSearcher([target]).find_referenced([hit, miss]) == {hit}


def test_candidate_found_in_later_file_after_own_file_skipped(tmp_path: Path) -> None:
    """A candidate skipped in its own file is still resolved by another file."""
    own = _write(tmp_path / "own.py", "def orphan(): pass")
    other = _write(tmp_path / "other.txt", "orphan()")
    candidate = ("orphan", "function", str(own), None)

    assert SymbolSearcher([own, other], workers=2).find_referenced([candidate]) == {
        candidate
    }


def test_no_candidates_reads_nothing(tmp_path: Path) -> None:
    """Without candidates no file is considered and no progress is reported."""
    only = _write(tmp_path / "a.txt", "x")
    calls: list[None] = []

    found = SymbolSearcher([only]).find_referenced([], lambda: calls.append(None))

    assert found == set()
    assert calls == []
