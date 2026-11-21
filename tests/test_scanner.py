"""Tests for scanner module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

from pathlib import Path

from code_prune.scanner import (
    CATEGORY_COMMENTED_OUT,
    CATEGORY_OBSOLETE,
    CATEGORY_TODO_MARKER,
    CATEGORY_UNREACHABLE,
    CATEGORY_UNUSED_IMPORT,
    CATEGORY_UNUSED_LOCAL,
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


def test_method_definition_records_enclosing_class_python() -> None:
    """A method's Definition must carry its directly enclosing class's name."""
    src = (
        b"def foo():\n    pass\n\n"
        b"class Bar:\n"
        b"    def method(self):\n"
        b"        def nested():\n"
        b"            pass\n"
    )
    result = scan_source(src, Path("a.py"), "Python")
    enclosing = {d.name: d.enclosing_class for d in result.definitions}
    assert enclosing["foo"] is None
    assert enclosing["Bar"] is None
    assert enclosing["method"] == "Bar"
    assert enclosing["nested"] is None


def _fields(source: bytes, filename: str, language: str) -> dict[str, str | None]:
    result = scan_source(source, Path(filename), language)
    return {d.name: d.enclosing_class for d in result.definitions if d.kind == "field"}


def test_python_class_and_self_attributes_collected_as_fields() -> None:
    """Class-level and first ``self.x`` assignments are fields of their class."""
    src = (
        b"class Bar:\n"
        b"    x: int = 1\n"
        b"    y = 2\n"
        b"    def __init__(self):\n"
        b"        self.z = 3\n"
        b"        self.y = 4\n"
        b"        local = 5\n"
        b"        return local\n"
    )
    assert _fields(src, "a.py", "Python") == {"x": "Bar", "y": "Bar", "z": "Bar"}
    result = scan_source(src, Path("a.py"), "Python")
    assert [d.name for d in result.definitions].count("y") == 1
    assert not {"x", "y", "z"} & set(result.usages)
    assert "z" not in _names_for(result.findings, CATEGORY_UNUSED_LOCAL)


def test_python_used_self_attribute_registers_usage() -> None:
    """Reading ``self.z`` elsewhere counts as a usage of the field name."""
    src = (
        b"class Bar:\n"
        b"    def __init__(self):\n"
        b"        self.z = 3\n"
        b"    def get(self):\n"
        b"        return self.z\n"
    )
    result = scan_source(src, Path("a.py"), "Python")
    assert "z" in result.usages


def test_module_level_assignment_is_not_a_field_python() -> None:
    """Assignments outside a class body are not fields."""
    src = b"CONST = 1\n\ndef foo():\n    other.attr = 2\n"
    assert not _fields(src, "a.py", "Python")


def test_javascript_class_fields_including_private() -> None:
    """JavaScript field definitions, including ``#private`` ones, are fields."""
    src = b"class A {\n  x = 1;\n  static y = 2;\n  #p = 3;\n  get() { return this.#p; }\n}\n"
    assert _fields(src, "a.js", "JavaScript") == {"x": "A", "y": "A", "#p": "A"}
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert "#p" in result.usages
    assert "x" not in result.usages


def test_typescript_fields_interface_properties_and_parameter_properties() -> None:
    """TypeScript fields, interface properties and constructor parameter properties."""
    src = (
        b"class A {\n  x: number = 1;\n  private y = 2;\n"
        b"  constructor(private q: number, plain: string) {}\n}\n"
        b"interface I { f: string; }\n"
    )
    assert _fields(src, "a.ts", "TypeScript") == {
        "x": "A",
        "y": "A",
        "q": "A",
        "f": "I",
    }


def test_java_fields_and_enum_constants() -> None:
    """Java fields (including multiple declarators) and enum constants are fields."""
    src = (
        b"class A {\n  private int x = 1, y;\n  static final int Z = 2;\n"
        b"  void run() { int local = 1; }\n}\n"
        b"enum E { ONE, TWO }\n"
    )
    assert _fields(src, "A.java", "Java") == {
        "x": "A",
        "y": "A",
        "Z": "A",
        "ONE": "E",
        "TWO": "E",
    }


def test_gosu_fields_skip_aliased_property_fields() -> None:
    """Gosu ``var`` fields are fields; one with an ``as`` alias is exposed as a property."""
    src = b"class A {\n  var _x : int = 1\n  private var _y : String\n  var _a : int as Prop\n}\n"
    assert _fields(src, "a.gs", "Gosu") == {"_x": "A", "_y": "A"}


def test_field_in_nested_function_class_is_not_attributed_to_outer_class() -> None:
    """A field belongs to its direct class, not an outer one."""
    src = b"class Outer:\n    def run(self):\n        class Inner:\n            v = 1\n"
    assert _fields(src, "a.py", "Python") == {"v": "Inner"}


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
    """A TODO comment must be flagged as a todo-marker, not obsolete."""
    src = b"# TODO: clean this up\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "TODO" in _names_for(result.findings, CATEGORY_TODO_MARKER)
    assert CATEGORY_OBSOLETE not in _categories(result.findings)


def test_fixme_and_xxx_comments_flagged_as_todo_marker() -> None:
    """FIXME and XXX comments must also be todo-markers."""
    src = b"// FIXME broken\n// XXX hack\nfunction foo() {}\n"
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert _names_for(result.findings, CATEGORY_TODO_MARKER) == ["FIXME", "XXX"]


def test_deprecated_comment_flagged_obsolete_python() -> None:
    """The word 'deprecated' in a comment stays in the obsolete category."""
    src = b"# deprecated: use bar\ndef foo():\n    pass\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert "DEPRECATED" in _names_for(result.findings, CATEGORY_OBSOLETE)
    assert CATEGORY_TODO_MARKER not in _categories(result.findings)


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
# Comments are never unreachable
# ---------------------------------------------------------------------------


def test_comment_after_return_not_unreachable_python() -> None:
    """A comment after a terminating statement must not be flagged unreachable."""
    src = b"def foo():\n    return 1\n    # trailing note\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_UNREACHABLE not in _categories(result.findings)


def test_comment_after_return_not_unreachable_java_and_js() -> None:
    """Line and block comments after return are ignored in brace languages."""
    java = (
        b"class A {\n  int f() {\n    return 1;\n    // note\n    /* more */\n  }\n}\n"
    )
    js = b"function f() {\n  return 1;\n  // note\n}\n"
    assert CATEGORY_UNREACHABLE not in _categories(
        scan_source(java, Path("A.java"), "Java").findings
    )
    assert CATEGORY_UNREACHABLE not in _categories(
        scan_source(js, Path("a.js"), "JavaScript").findings
    )


def test_code_after_return_still_unreachable_with_comment_between() -> None:
    """Real statements after a terminator (and a comment) remain unreachable."""
    src = b"def foo():\n    return 1\n    # note\n    dead()\n"
    result = scan_source(src, Path("a.py"), "Python")
    assert _categories(result.findings).count(CATEGORY_UNREACHABLE) == 1


# ---------------------------------------------------------------------------
# Commented-out code
# ---------------------------------------------------------------------------


def test_javadoc_not_flagged_commented_out_java() -> None:
    """Javadoc content that looks like code must not be flagged."""
    src = (
        b"class A {\n"
        b"  /**\n   * Example:\n   * return foo();\n   * if (x) {\n   */\n"
        b"  int f() { return 1; }\n}\n"
    )
    result = scan_source(src, Path("A.java"), "Java")
    assert CATEGORY_COMMENTED_OUT not in _categories(result.findings)


def test_jsdoc_not_flagged_commented_out_javascript() -> None:
    """JSDoc content that looks like code must not be flagged."""
    src = b"/**\n * const x = 1;\n * return x;\n */\nfunction f() { return 1; }\n"
    result = scan_source(src, Path("a.js"), "JavaScript")
    assert CATEGORY_COMMENTED_OUT not in _categories(result.findings)


def test_gosu_doc_comment_not_flagged_commented_out() -> None:
    """Gosu doc comments must not be flagged as commented-out code."""
    src = b"class Foo {\n  /**\n   * return foo();\n   */\n  function f() {}\n}\n"
    result = scan_source(src, Path("Foo.gs"), "Gosu")
    assert CATEGORY_COMMENTED_OUT not in _categories(result.findings)


def test_plain_block_comment_code_still_flagged_java() -> None:
    """A regular (non-doc) block comment holding code is still flagged."""
    src = b"class A {\n  /* return foo(); */\n  int f() { return 1; }\n}\n"
    result = scan_source(src, Path("A.java"), "Java")
    assert CATEGORY_COMMENTED_OUT in _categories(result.findings)


def test_python_docstring_not_flagged_commented_out() -> None:
    """A Python docstring containing code-like text is not a comment."""
    src = (
        b'def foo():\n    """\n    return bar()\n    import os\n    """\n    return 1\n'
    )
    result = scan_source(src, Path("a.py"), "Python")
    assert CATEGORY_COMMENTED_OUT not in _categories(result.findings)


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
