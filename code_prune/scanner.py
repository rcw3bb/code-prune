"""Dead-code scanner: unreachable, unused, and obsolete code detectors.

Five tree-sitter grammars are supported: Python, JavaScript, TypeScript, Java,
and Gosu. Detection is intentionally heuristic/syntactic rather than a full
scope- or call-graph-aware analysis, matching the spirit of a fast, best-effort
static-analysis CLI tool.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Node, Tree  # type: ignore[import-untyped]

from .parser import parse

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Finding categories
# --------------------------------------------------------------------------

CATEGORY_UNREACHABLE = "unreachable"
CATEGORY_UNUSED_IMPORT = "unused-import"
CATEGORY_UNUSED_LOCAL = "unused-local"
CATEGORY_UNUSED_SYMBOL = "unused-symbol"
CATEGORY_OBSOLETE = "obsolete"
CATEGORY_COMMENTED_OUT = "commented-out"

#: Categories a user may toggle via ``--categories``. ``unused`` expands to
#: both :data:`CATEGORY_UNUSED_IMPORT`/:data:`CATEGORY_UNUSED_LOCAL` (per-file)
#: and :data:`CATEGORY_UNUSED_SYMBOL` (cross-file).
CLI_CATEGORIES = ("unreachable", "unused", "obsolete", "commented-out")

# --------------------------------------------------------------------------
# Per-language grammar node-type tables (verified empirically against each
# tree-sitter grammar before being hard-coded here).
# --------------------------------------------------------------------------

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".gs": "Gosu",
    ".gsx": "Gosu",
}

#: Function/method definition node types, per language.
FUNCTION_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"function_definition"}),
    "JavaScript": frozenset(
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        }
    ),
    "TypeScript": frozenset(
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        }
    ),
    "Java": frozenset({"method_declaration", "constructor_declaration"}),
    "Gosu": frozenset({"function_declaration", "constructor_declaration"}),
}

#: Class/interface definition node types, per language.
CLASS_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"class_definition"}),
    "JavaScript": frozenset({"class_declaration"}),
    "TypeScript": frozenset({"class_declaration", "interface_declaration"}),
    "Java": frozenset(
        {"class_declaration", "interface_declaration", "enum_declaration"}
    ),
    "Gosu": frozenset({"class_declaration"}),
}

#: Import/uses-clause node types, per language.
IMPORT_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"import_statement", "import_from_statement"}),
    "JavaScript": frozenset({"import_statement"}),
    "TypeScript": frozenset({"import_statement"}),
    "Java": frozenset({"import_declaration"}),
    "Gosu": frozenset({"uses_declaration"}),
}

#: Local-variable declaration/assignment node types, per language.
LOCAL_DECL_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"assignment"}),
    "JavaScript": frozenset({"variable_declarator"}),
    "TypeScript": frozenset({"variable_declarator"}),
    "Java": frozenset({"variable_declarator"}),
    "Gosu": frozenset({"local_variable_declaration"}),
}

#: Statements that terminate control flow within a block, per language.
TERMINATING_STATEMENT_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset(
        {"return_statement", "raise_statement", "break_statement", "continue_statement"}
    ),
    "JavaScript": frozenset(
        {"return_statement", "throw_statement", "break_statement", "continue_statement"}
    ),
    "TypeScript": frozenset(
        {"return_statement", "throw_statement", "break_statement", "continue_statement"}
    ),
    "Java": frozenset(
        {"return_statement", "throw_statement", "break_statement", "continue_statement"}
    ),
    "Gosu": frozenset(
        {"return_statement", "throw_statement", "break_statement", "continue_statement"}
    ),
}

#: Node types whose direct named children form a sequential statement list.
BLOCK_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"block"}),
    "JavaScript": frozenset({"statement_block"}),
    "TypeScript": frozenset({"statement_block"}),
    "Java": frozenset({"block"}),
    "Gosu": frozenset({"statement_block"}),
}

#: Comment node types, per language.
COMMENT_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"comment"}),
    "JavaScript": frozenset({"comment"}),
    "TypeScript": frozenset({"comment"}),
    "Java": frozenset({"line_comment", "block_comment"}),
    "Gosu": frozenset({"line_comment", "block_comment"}),
}

#: Decorator/annotation node types consulted for deprecation markers.
DECORATOR_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"decorator"}),
    "JavaScript": frozenset(),
    "TypeScript": frozenset({"decorator"}),
    "Java": frozenset({"marker_annotation", "annotation"}),
    "Gosu": frozenset({"annotation"}),
}

#: Identifier-like node types counted as a "usage" of a name.
USAGE_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"identifier"}),
    "JavaScript": frozenset(
        {"identifier", "property_identifier", "shorthand_property_identifier"}
    ),
    "TypeScript": frozenset(
        {
            "identifier",
            "property_identifier",
            "shorthand_property_identifier",
            "type_identifier",
        }
    ),
    "Java": frozenset({"identifier", "type_identifier"}),
    "Gosu": frozenset({"identifier"}),
}

#: Regex matching a condition expression that is always false (after
#: optionally stripping surrounding parentheses added by some grammars).
_FALSY_CONDITION_RE = re.compile(r"^\(*\s*(False|false|0)\s*\)*$")

#: Regex matching obsolete markers inside comment text.
_OBSOLETE_COMMENT_RE = re.compile(r"\b(TODO|FIXME|XXX|deprecated)\b", re.IGNORECASE)

#: Regex fragments that suggest a comment line contains commented-out code.
_CODE_LIKE_RE = re.compile(
    r"^\s*(def\s+\w+\(|class\s+\w+|function\s*\w*\(|public\s|private\s|protected\s|"
    r"static\s|if\s*\(|for\s*\(|while\s*\(|return\b|import\s|from\s+\S+\s+import|"
    r"var\s+\w+\s*=|let\s+\w+\s*=|const\s+\w+\s*=|package\s|uses\s)"
)
_ASSIGNMENT_RE = re.compile(r"[^=!<>+\-*/]=[^=]")


@dataclass(frozen=True)
class Finding:
    """A single detected issue in source code.

    Author: Ron Webb
    Since: 1.0.0
    """

    category: str
    file_path: Path
    line: int
    column: int
    name: str
    message: str


@dataclass(frozen=True)
class Definition:
    """A function/class/method definition discovered in one file.

    Author: Ron Webb
    Since: 1.0.0
    """

    name: str
    kind: str
    file_path: Path
    line: int
    column: int


@dataclass
class ScanResult:
    """Aggregated results of scanning a single file.

    ``usages`` holds every non-binding identifier-like name found in the file;
    callers feed it into a project-wide tally to resolve cross-file
    :data:`CATEGORY_UNUSED_SYMBOL` findings once every file has been scanned.

    Author: Ron Webb
    Since: 1.0.0
    """

    findings: list[Finding] = field(default_factory=list)
    definitions: list[Definition] = field(default_factory=list)
    usages: list[str] = field(default_factory=list)


def _decode(source_bytes: bytes, node: Node) -> str:
    """Return the UTF-8 decoded text spanned by *node*.

    Author: Ron Webb
    Since: 1.0.0
    """
    return source_bytes[node.start_byte : node.end_byte].decode(
        "utf-8", errors="replace"
    )


def _iter_nodes(node: Node) -> Generator[Node, None, None]:
    """Recursively yield *node* and every descendant.

    Author: Ron Webb
    Since: 1.0.0
    """
    yield node
    for child in node.children:
        yield from _iter_nodes(child)


# --------------------------------------------------------------------------
# Unreachable code
# --------------------------------------------------------------------------


def _is_dead_condition(source_bytes: bytes, condition: Node | None) -> bool:
    """Return ``True`` when *condition* always evaluates to a falsy constant.

    Author: Ron Webb
    Since: 1.0.0
    """
    if condition is None:
        return False
    return bool(_FALSY_CONDITION_RE.match(_decode(source_bytes, condition).strip()))


def detect_unreachable(
    tree: Tree, source_bytes: bytes, language: str, file_path: Path
) -> list[Finding]:
    """Detect statements that can never execute.

    Two patterns are recognised: statements following a terminating statement
    (``return``/``raise``/``throw``/``break``/``continue``) within the same
    block, and the body of an ``if`` whose condition is a constant falsy
    literal (``False``/``false``/``0``).

    Author: Ron Webb
    Since: 1.0.0
    """
    block_types = BLOCK_NODE_TYPES.get(language, frozenset())
    terminating_types = TERMINATING_STATEMENT_TYPES.get(language, frozenset())
    findings: list[Finding] = []

    for node in _iter_nodes(tree.root_node):
        if node.type in block_types:
            findings.extend(
                _unreachable_after_terminator(node, terminating_types, file_path)
            )
        elif node.type == "if_statement":
            findings.extend(_unreachable_dead_branch(node, source_bytes, file_path))

    return findings


def _unreachable_after_terminator(
    block: Node, terminating_types: frozenset[str], file_path: Path
) -> list[Finding]:
    """Flag statements following a terminator within *block*.

    Author: Ron Webb
    Since: 1.0.0
    """
    findings: list[Finding] = []
    statements = block.named_children
    terminator_index: int | None = None
    for index, statement in enumerate(statements):
        if terminator_index is not None:
            row, col = statement.start_point
            findings.append(
                Finding(
                    category=CATEGORY_UNREACHABLE,
                    file_path=file_path,
                    line=row + 1,
                    column=col,
                    name=statement.type,
                    message="Unreachable code after a terminating statement.",
                )
            )
        elif statement.type in terminating_types:
            terminator_index = index
    return findings


def _unreachable_dead_branch(
    if_node: Node, source_bytes: bytes, file_path: Path
) -> list[Finding]:
    """Flag the body of an ``if`` whose condition is always falsy.

    Author: Ron Webb
    Since: 1.0.0
    """
    condition = if_node.child_by_field_name("condition")
    consequence = if_node.child_by_field_name("consequence")
    if consequence is None or not _is_dead_condition(source_bytes, condition):
        return []
    row, col = consequence.start_point
    return [
        Finding(
            category=CATEGORY_UNREACHABLE,
            file_path=file_path,
            line=row + 1,
            column=col,
            name=if_node.type,
            message="Unreachable branch: condition is always false.",
        )
    ]


# --------------------------------------------------------------------------
# Bindings (imports / locals / definitions) and usages
# --------------------------------------------------------------------------


@dataclass
class _Bindings:
    """Intermediate state collected while walking a file once.

    Author: Ron Webb
    Since: 1.0.0
    """

    import_bindings: list[tuple[Node, str]] = field(default_factory=list)
    local_bindings: list[tuple[Node, str]] = field(default_factory=list)
    definitions: list[Definition] = field(default_factory=list)
    excluded_positions: set[int] = field(default_factory=set)


def _import_bound_name_nodes(import_node: Node, language: str) -> list[Node]:
    """Return the identifier nodes that *import_node* binds locally.

    Author: Ron Webb
    Since: 1.0.0
    """
    if language == "Python":
        return _python_import_bound_names(import_node)
    if language in ("JavaScript", "TypeScript"):
        return [
            n
            for n in _iter_nodes(import_node)
            if n.type in ("identifier", "property_identifier") and n != import_node
        ]
    # Java import_declaration / Gosu uses_declaration: bind the last identifier
    # in the dotted/scoped name (the simple class name); skip wildcard imports.
    identifiers = [n for n in import_node.named_children if n.type == "identifier"]
    tail = _last_identifier(import_node)
    return [tail] if tail is not None else identifiers


def _python_import_bound_names(import_node: Node) -> list[Node]:
    """Return bound-name identifier nodes for a Python import statement.

    ``import a.b.c`` binds ``a``; ``import a.b.c as x`` and
    ``from m import a as x`` bind ``x``; ``from m import a`` binds ``a``.
    The ``from``-clause module path itself (``module_name`` field) is never a
    binding and is excluded.

    Author: Ron Webb
    Since: 1.0.0
    """
    module_name = import_node.child_by_field_name("module_name")
    bound: list[Node] = []
    for child in import_node.named_children:
        if child == module_name:
            continue
        if child.type == "aliased_import":
            alias = child.named_children[-1] if child.named_children else None
            if alias is not None:
                bound.append(alias)
        elif child.type == "dotted_name":
            is_from_import = import_node.type == "import_from_statement"
            target = (
                child.named_children[-1] if is_from_import else child.named_children[0]
            )
            if target is not None:
                bound.append(target)
    return bound


def _last_identifier(node: Node) -> Node | None:
    """Return the last ``identifier`` descendant of *node*, if any.

    Author: Ron Webb
    Since: 1.0.0
    """
    identifiers = [n for n in _iter_nodes(node) if n.type == "identifier"]
    return identifiers[-1] if identifiers else None


def _local_bound_name_node(decl_node: Node, language: str) -> Node | None:
    """Return the identifier node bound by a local-variable declaration.

    Author: Ron Webb
    Since: 1.0.0
    """
    if language == "Gosu":
        return next(
            (c for c in decl_node.named_children if c.type == "identifier"), None
        )
    name = decl_node.child_by_field_name("name")
    if name is not None and name.type in ("identifier",):
        return name
    left = decl_node.child_by_field_name("left")
    if left is not None and left.type == "identifier":
        return left
    return None


def _collect_bindings(
    tree: Tree, source_bytes: bytes, language: str, file_path: Path
) -> _Bindings:
    """Walk *tree* once, collecting import/local/definition bindings.

    Author: Ron Webb
    Since: 1.0.0
    """
    bindings = _Bindings()
    import_types = IMPORT_NODE_TYPES.get(language, frozenset())
    local_types = LOCAL_DECL_NODE_TYPES.get(language, frozenset())
    function_types = FUNCTION_NODE_TYPES.get(language, frozenset())
    class_types = CLASS_NODE_TYPES.get(language, frozenset())

    def walk(node: Node, inside_function: bool) -> None:
        if node.type in import_types:
            for name_node in _import_bound_name_nodes(node, language):
                bindings.import_bindings.append(
                    (name_node, _decode(source_bytes, name_node))
                )
                bindings.excluded_positions.add(name_node.start_byte)
            return
        if node.type in local_types and inside_function:
            name_node = _local_bound_name_node(node, language)
            if name_node is not None:
                bindings.local_bindings.append(
                    (name_node, _decode(source_bytes, name_node))
                )
                bindings.excluded_positions.add(name_node.start_byte)
        if node.type in function_types or node.type in class_types:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                kind = "class" if node.type in class_types else "function"
                bindings.definitions.append(
                    Definition(
                        name=_decode(source_bytes, name_node),
                        kind=kind,
                        file_path=file_path,
                        line=name_node.start_point[0] + 1,
                        column=name_node.start_point[1],
                    )
                )
                bindings.excluded_positions.add(name_node.start_byte)
            inside_function = inside_function or node.type in function_types
        for child in node.children:
            walk(child, inside_function)

    walk(tree.root_node, False)
    return bindings


def _collect_usage_names(
    tree: Tree, source_bytes: bytes, language: str, excluded_positions: set[int]
) -> list[str]:
    """Return every usage-identifier name in *tree*, skipping binding sites.

    Author: Ron Webb
    Since: 1.0.0
    """
    usage_types = USAGE_NODE_TYPES.get(language, frozenset())
    return [
        _decode(source_bytes, node)
        for node in _iter_nodes(tree.root_node)
        if node.type in usage_types and node.start_byte not in excluded_positions
    ]


def detect_unused_bindings(
    tree: Tree, source_bytes: bytes, language: str, file_path: Path
) -> tuple[list[Finding], list[Definition], list[str]]:
    """Detect unused imports/locals and collect data for cross-file analysis.

    Returns a 3-tuple of ``(findings, definitions, usage_names)``. Imports and
    local variables are resolved immediately (per-file); ``definitions`` and
    ``usage_names`` are returned so the caller can resolve
    :data:`CATEGORY_UNUSED_SYMBOL` once every file in the scan has been
    processed.

    Author: Ron Webb
    Since: 1.0.0
    """
    bindings = _collect_bindings(tree, source_bytes, language, file_path)
    usage_names = _collect_usage_names(
        tree, source_bytes, language, bindings.excluded_positions
    )
    usage_counts = Counter(usage_names)

    findings: list[Finding] = []
    findings.extend(
        _unused_binding_findings(
            bindings.import_bindings,
            usage_counts,
            CATEGORY_UNUSED_IMPORT,
            file_path,
            "Unused import",
        )
    )
    findings.extend(
        _unused_binding_findings(
            bindings.local_bindings,
            usage_counts,
            CATEGORY_UNUSED_LOCAL,
            file_path,
            "Unused local variable",
        )
    )
    return findings, bindings.definitions, usage_names


def _unused_binding_findings(
    bindings: Iterable[tuple[Node, str]],
    usage_counts: Counter[str],
    category: str,
    file_path: Path,
    message_prefix: str,
) -> list[Finding]:
    """Build :class:`Finding` objects for bindings never used elsewhere.

    Author: Ron Webb
    Since: 1.0.0
    """
    findings: list[Finding] = []
    for name_node, name in bindings:
        if usage_counts[name] == 0:
            row, col = name_node.start_point
            findings.append(
                Finding(
                    category=category,
                    file_path=file_path,
                    line=row + 1,
                    column=col,
                    name=name,
                    message=f"{message_prefix} '{name}'.",
                )
            )
    return findings


# --------------------------------------------------------------------------
# Obsolete markers
# --------------------------------------------------------------------------


def detect_obsolete_markers(
    tree: Tree, source_bytes: bytes, language: str, file_path: Path
) -> list[Finding]:
    """Detect deprecation decorators/annotations and TODO/FIXME-style comments.

    Author: Ron Webb
    Since: 1.0.0
    """
    findings: list[Finding] = []
    decorator_types = DECORATOR_NODE_TYPES.get(language, frozenset())
    comment_types = COMMENT_NODE_TYPES.get(language, frozenset())

    for node in _iter_nodes(tree.root_node):
        if decorator_types and node.type in decorator_types:
            text = _decode(source_bytes, node)
            if re.search(r"deprecated", text, re.IGNORECASE):
                row, col = node.start_point
                findings.append(
                    Finding(
                        category=CATEGORY_OBSOLETE,
                        file_path=file_path,
                        line=row + 1,
                        column=col,
                        name=node.type,
                        message="Deprecated marker found.",
                    )
                )
        elif node.type in comment_types:
            text = _decode(source_bytes, node)
            match = _OBSOLETE_COMMENT_RE.search(text)
            if match:
                row, col = node.start_point
                findings.append(
                    Finding(
                        category=CATEGORY_OBSOLETE,
                        file_path=file_path,
                        line=row + 1,
                        column=col,
                        name=match.group(1).upper(),
                        message=f"Obsolete marker '{match.group(1)}' found in comment.",
                    )
                )
    return findings


# --------------------------------------------------------------------------
# Commented-out code
# --------------------------------------------------------------------------


def _strip_comment_markers(text: str) -> str:
    """Strip ``#``/``//``/``/* */`` comment delimiters from *text*.

    Author: Ron Webb
    Since: 1.0.0
    """
    stripped = text.strip()
    for prefix in ("///", "//", "#"):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    if stripped.startswith("/*") and stripped.endswith("*/"):
        return stripped[2:-2].strip()
    return stripped.lstrip("*").strip()


def _looks_like_code(text: str) -> bool:
    """Heuristically determine whether *text* resembles source code.

    Author: Ron Webb
    Since: 1.0.0
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    if _CODE_LIKE_RE.match(stripped):
        return True
    if _ASSIGNMENT_RE.search(stripped) and stripped.endswith((";", ":")):
        return True
    return stripped.endswith(("{", "}")) and len(stripped) > 1


def detect_commented_out_code(
    tree: Tree, source_bytes: bytes, language: str, file_path: Path
) -> list[Finding]:
    """Detect comments whose content heuristically resembles source code.

    Consecutive single-line comments are grouped into one block before the
    heuristic is applied, so a multi-line commented-out snippet produces a
    single finding.

    Author: Ron Webb
    Since: 1.0.0
    """
    comment_types = COMMENT_NODE_TYPES.get(language, frozenset())
    if not comment_types:
        return []
    comments = [n for n in _iter_nodes(tree.root_node) if n.type in comment_types]
    comments.sort(key=lambda n: n.start_point)

    findings: list[Finding] = []
    run: list[Node] = []

    def flush() -> None:
        if not run:
            return
        lines = [_strip_comment_markers(_decode(source_bytes, n)) for n in run]
        if any(_looks_like_code(line) for line in lines):
            row, col = run[0].start_point
            snippet = next(line for line in lines if _looks_like_code(line))
            findings.append(
                Finding(
                    category=CATEGORY_COMMENTED_OUT,
                    file_path=file_path,
                    line=row + 1,
                    column=col,
                    name="",
                    message=f"Possible commented-out code: {snippet[:80]!r}.",
                )
            )
        run.clear()

    previous: Node | None = None
    single_line_types = frozenset({"line_comment", "comment"})
    for comment in comments:
        is_adjacent = (
            previous is not None
            and previous.type in single_line_types
            and comment.type in single_line_types
            and comment.start_point[0] == previous.end_point[0] + 1
        )
        if run and not is_adjacent:
            flush()
        run.append(comment)
        previous = comment
    flush()

    return findings


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def scan_source(source_bytes: bytes, file_path: Path, language: str) -> ScanResult:
    """Run every detector against *source_bytes* and return a combined result.

    Author: Ron Webb
    Since: 1.0.0
    """
    tree = parse(source_bytes, language)
    if tree is None:
        return ScanResult()

    findings: list[Finding] = []
    findings.extend(detect_unreachable(tree, source_bytes, language, file_path))
    unused_findings, definitions, usages = detect_unused_bindings(
        tree, source_bytes, language, file_path
    )
    findings.extend(unused_findings)
    findings.extend(detect_obsolete_markers(tree, source_bytes, language, file_path))
    findings.extend(detect_commented_out_code(tree, source_bytes, language, file_path))

    return ScanResult(findings=findings, definitions=definitions, usages=usages)


def scan_file(file_path: Path) -> ScanResult:
    """Read *file_path* from disk and scan it for dead-code findings.

    The tree-sitter language is determined from the file extension via
    :data:`EXTENSION_TO_LANGUAGE`. Files with unsupported extensions are
    skipped with a warning and an empty result is returned.

    Author: Ron Webb
    Since: 1.0.0
    """
    language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
    if language is None:
        _logger.warning(
            "Unsupported extension '%s' — skipping %s", file_path.suffix, file_path
        )
        return ScanResult()
    source_bytes = file_path.read_bytes()
    return scan_source(source_bytes, file_path, language)


def load_name_ignore_patterns(path: Path) -> list[re.Pattern[str]]:
    """Load regex symbol-name ignore patterns from *path*.

    Lines starting with ``#`` and blank lines are skipped. Author: Ron Webb
    Since: 1.0.0
    """
    patterns: list[re.Pattern[str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(re.compile(stripped))
    return patterns
