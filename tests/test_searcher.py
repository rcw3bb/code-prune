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
