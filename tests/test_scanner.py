"""Tests for scanner module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

from pathlib import Path

from code_prune.scanner import (
    CATEGORY_COMMENTED_OUT,
    CATEGORY_OBSOLETE,
    CATEGORY_UNREACHABLE,
    CATEGORY_UNUSED_IMPORT,
    CATEGORY_UNUSED_LOCAL,
    EXTENSION_TO_LANGUAGE,
    Finding,
    load_name_ignore_patterns,
    scan_file,
    scan_source,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _categories(findings: list[Finding]) -> list[str]:
    return [f.category for f in findings]


def _names_for(findings: list[Finding], category: str) -> list[str]:
    return [f.name for f in findings if f.category == category]


# ---------------------------------------------------------------------------
# EXTENSION_TO_LANGUAGE mapping
# ---------------------------------------------------------------------------


def test_extension_to_language_covers_all_five_languages() -> None:
    """Every supported extension should map to its expected language."""
    assert EXTENSION_TO_LANGUAGE[".py"] == "Python"
    assert EXTENSION_TO_LANGUAGE[".js"] == "JavaScript"
    assert EXTENSION_TO_LANGUAGE[".ts"] == "TypeScript"
    assert EXTENSION_TO_LANGUAGE[".java"] == "Java"
    assert EXTENSION_TO_LANGUAGE[".gs"] == "Gosu"
    assert EXTENSION_TO_LANGUAGE[".gsx"] == "Gosu"


# ---------------------------------------------------------------------------
# Unreachable code
# ---------------------------------------------------------------------------


def test_unreachable_after_return_python() -> None:
    """Statements after a return in Python must be flagged unreachable."""
    src = b"def foo():\n    return 1\n    unused_stmt()\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_UNREACHABLE in _categories(result.findings)


def test_unreachable_dead_if_false_branch_python() -> None:
    """A body under `if False:` must be flagged unreachable in Python."""
    src = b"def foo():\n    if False:\n        dead()\n    return 1\n"
    result = scan_source(src, Path("a.py"), "Python")
    reachable_msgs = [
        f.message for f in result.findings if f.category == CATEGORY_UNREACHABLE
    ]
    assert any("always false" in m for m in reachable_msgs)


def test_reachable_code_not_flagged_python() -> None:
    """Ordinary sequential statements must not be flagged unreachable."""
    src = b"def foo():\n    x = 1\n    y = 2\n    return x + y\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_UNREACHABLE not in _categories(result.findings)


def test_unreachable_after_throw_javascript() -> None:
    """Statements after a throw in JavaScript must be flagged unreachable."""
    src = b"function foo() {\n  throw new Error('x');\n  unused();\n}\n"
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert CATEGORY_UNREACHABLE in _categories(result.findings)


def test_unreachable_dead_if_false_branch_java() -> None:
    """A body under `if (false)` must be flagged unreachable in Java."""
    src = (
        b"public class Foo {\n"
        b"  public void bar() {\n"
        b"    if (false) {\n"
        b"      dead();\n"
        b"    }\n"
        b"  }\n"
        b"}\n"
    )
    result = scan_source(src, Path("Foo.java"), "Java")
    assert CATEGORY_UNREACHABLE in _categories(result.findings)


def test_unreachable_after_return_gosu() -> None:
    """Statements after a return in Gosu must be flagged unreachable."""
    src = b"class Foo {\n  function bar() {\n    return 1\n    dead()\n  }\n}\n"
    result = scan_source(src, Path("Foo.gs"), "Gosu")
    assert CATEGORY_UNREACHABLE in _categories(result.findings)


# ---------------------------------------------------------------------------
# Unused imports / locals
# ---------------------------------------------------------------------------


def test_unused_import_flagged_python() -> None:
    """A plain import never referenced again must be flagged unused."""
    src = b"import os\n\ndef foo():\n    return 1\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "os" in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_used_import_not_flagged_python() -> None:
    """An import referenced elsewhere in the file must not be flagged."""
    src = b"import os\n\ndef foo():\n    return os.getcwd()\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "os" not in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_from_import_alias_binds_alias_not_module_python() -> None:
    """`from sys import path as p` binds only `p`, not `sys`."""
    src = b"from sys import path as p\n\ndef foo():\n    return 1\n"
    result = scan_source(src, Path("a.py"), "Python")
    unused = _names_for(result.findings, CATEGORY_UNUSED_IMPORT)
    assert unused == ["p"]


def test_dotted_import_binds_first_segment_python() -> None:
    """`import os.path` binds `os`, matching Python's own import semantics."""
    src = b"import os.path\n\ndef foo():\n    return 1\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "os" in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_unused_import_flagged_javascript() -> None:
    """A named import never referenced again must be flagged unused."""
    src = b"import { a } from 'mod';\nfunction foo() {\n  return 1;\n}\n"
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert "a" in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_unused_import_flagged_java() -> None:
    """An unused Java import must be flagged with its simple class name."""
    src = b"import java.util.List;\n\npublic class Foo {\n}\n"
    result = scan_source(src, Path("Foo.java"), "Java")
    assert "List" in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_unused_import_flagged_gosu() -> None:
    """An unused Gosu `uses` clause must be flagged with its simple class name."""
    src = b"uses java.util.List\n\nclass Foo {\n}\n"
    result = scan_source(src, Path("Foo.gs"), "Gosu")
    assert "List" in _names_for(result.findings, CATEGORY_UNUSED_IMPORT)


def test_unused_local_flagged_python() -> None:
    """A local variable assigned but never read must be flagged unused."""
    src = b"def foo():\n    unused_var = 1\n    return 2\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "unused_var" in _names_for(result.findings, CATEGORY_UNUSED_LOCAL)


def test_used_local_not_flagged_python() -> None:
    """A local variable that is later read must not be flagged unused."""
    src = b"def foo():\n    x = 1\n    return x\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "x" not in _names_for(result.findings, CATEGORY_UNUSED_LOCAL)


def test_class_level_attribute_not_flagged_as_unused_local_python() -> None:
    """A class-body attribute assignment (not inside a method) is not a local."""
    src = b"class Foo:\n    class_var = 1\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "class_var" not in _names_for(result.findings, CATEGORY_UNUSED_LOCAL)


# ---------------------------------------------------------------------------
# Cross-file definitions collected for the "unused symbol" pass
# ---------------------------------------------------------------------------


def test_definitions_collected_for_function_and_class_python() -> None:
    """Function and class definitions must be collected with correct kinds."""
    src = b"def foo():\n    pass\n\nclass Bar:\n    def method(self):\n        pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    kinds = {d.name: d.kind for d in result.definitions}
    assert kinds["foo"] == "function"
    assert kinds["Bar"] == "class"
    assert kinds["method"] == "function"


def test_usages_exclude_definition_name_nodes_python() -> None:
    """A definition's own name token must not count as a usage of itself."""
    src = b"def foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "foo" not in result.usages


def test_usages_include_call_site_python() -> None:
    """Calling a function elsewhere must register as a usage of its name."""
    src = b"def foo():\n    pass\n\ndef bar():\n    return foo()\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "foo" in result.usages


def test_local_used_only_in_gosu_string_interpolation_not_flagged_unused() -> None:
    """A Gosu local referenced only via `${...}` string interpolation must count as used.

    Gosu's ``string_literal`` grammar node is a single opaque token (unlike
    Python's ``string`` or JS/TS's ``template_string``, which decompose
    interpolations into real identifier nodes), so this requires a regex
    fallback over the raw string text.
    """
    src = (
        b"class Foo {\n"
        b"  function bar() : String {\n"
        b'    var _defaultValue = "fallback"\n'
        b'    return "value is ${_defaultValue} end"\n'
        b"  }\n"
        b"}\n"
    )
    result = scan_source(src, Path("Foo.gs"), "Gosu")
    assert "_defaultValue" not in _names_for(result.findings, CATEGORY_UNUSED_LOCAL)
    assert "_defaultValue" in result.usages


# ---------------------------------------------------------------------------
# Obsolete markers
# ---------------------------------------------------------------------------


def test_deprecated_decorator_flagged_python() -> None:
    """A `@deprecated`-style decorator must be flagged obsolete."""
    src = b"@deprecated\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_OBSOLETE in _categories(result.findings)


def test_deprecated_annotation_flagged_java() -> None:
    """A `@Deprecated` annotation must be flagged obsolete in Java."""
    src = b"public class Foo {\n  @Deprecated\n  public void bar() {}\n}\n"
    result = scan_source(src, Path("Foo.java"), "Java")
    assert CATEGORY_OBSOLETE in _categories(result.findings)


def test_deprecated_annotation_flagged_gosu() -> None:
    """A `@Deprecated` annotation must be flagged obsolete in Gosu."""
    src = b"@Deprecated\nclass Foo {\n}\n"
    result = scan_source(src, Path("Foo.gs"), "Gosu")
    assert CATEGORY_OBSOLETE in _categories(result.findings)


def test_todo_comment_flagged_python() -> None:
    """A TODO comment must be flagged obsolete."""
    src = b"# TODO: clean this up\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "TODO" in _names_for(result.findings, CATEGORY_OBSOLETE)


def test_jsdoc_deprecated_comment_flagged_typescript() -> None:
    """A JSDoc `@deprecated` comment must be flagged obsolete in TypeScript."""
    src = b"/**\n * @deprecated use bar instead\n */\nfunction foo(): void {}\n"
    result = scan_source(src, Path("a.ts"), "TypeScript")
    assert CATEGORY_OBSOLETE in _categories(result.findings)


def test_plain_comment_not_flagged_obsolete_python() -> None:
    """An ordinary comment without a marker keyword must not be flagged."""
    src = b"# just a normal note\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_OBSOLETE not in _categories(result.findings)


# ---------------------------------------------------------------------------
# Commented-out code
# ---------------------------------------------------------------------------


def test_commented_out_function_flagged_python() -> None:
    """A commented-out function definition must be flagged."""
    src = b"# def old_func():\n#     return 1\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_COMMENTED_OUT in _categories(result.findings)


def test_plain_comment_not_flagged_commented_out_python() -> None:
    """A descriptive comment must not be flagged as commented-out code."""
    src = b"# this function returns the answer\ndef foo():\n    return 42\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_COMMENTED_OUT not in _categories(result.findings)


def test_commented_out_assignment_flagged_javascript() -> None:
    """A commented-out assignment statement must be flagged in JavaScript."""
    src = b"// let legacy = 1;\nfunction foo() {\n  return 1;\n}\n"
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert CATEGORY_COMMENTED_OUT in _categories(result.findings)


# ---------------------------------------------------------------------------
# scan_file
# ---------------------------------------------------------------------------


def test_scan_file_unsupported_extension_returns_empty(tmp_path: Path) -> None:
    """An unsupported file extension must yield an empty scan result."""
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")
    result = scan_file(target)
    assert result.findings == []
    assert result.definitions == []
    assert result.usages == []


def test_scan_file_reads_and_scans_python_file(tmp_path: Path) -> None:
    """scan_file must read a real file from disk and scan it."""
    target = tmp_path / "a.py"
    target.write_text("def foo():\n    return 1\n    dead()\n", encoding="utf-8")
    result = scan_file(target)
    assert CATEGORY_UNREACHABLE in _categories(result.findings)


# ---------------------------------------------------------------------------
# load_name_ignore_patterns
# ---------------------------------------------------------------------------


def test_load_name_ignore_patterns_skips_comments_and_blanks(tmp_path: Path) -> None:
    """Blank lines and `#` comments in the ignore file must be skipped."""
    ignore_file = tmp_path / "symbol_ignore"
    ignore_file.write_text("# comment\n\n^main$\n^test_\n", encoding="utf-8")
    patterns = load_name_ignore_patterns(ignore_file)
    assert len(patterns) == 2
    assert any(p.search("main") for p in patterns)
    assert any(p.search("test_foo") for p in patterns)
