"""Per-language tree-sitter node-type tables used by the scanner.

The node types were verified empirically against each tree-sitter grammar
before being hard-coded here.

Author: Ron Webb
Since: 1.3.0
"""

from __future__ import annotations

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

#: File extensions the scanner can parse.
SUPPORTED_EXTENSIONS = frozenset(EXTENSION_TO_LANGUAGE)

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

#: Field/attribute declaration node types, per language. Python class-level
#: fields are plain ``assignment`` nodes; ``self.x = ...`` attributes are found
#: separately inside methods.
FIELD_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"assignment"}),
    "JavaScript": frozenset({"field_definition"}),
    "TypeScript": frozenset({"public_field_definition", "property_signature"}),
    "Java": frozenset({"field_declaration", "enum_constant"}),
    "Gosu": frozenset({"field_declaration"}),
}

#: Grammar field holding the declared name of a field node (default ``name``).
FIELD_NAME_FIELD: dict[str, str] = {"Python": "left", "JavaScript": "property"}

#: Node types a field name may have.
FIELD_NAME_NODE_TYPES = frozenset(
    {"identifier", "property_identifier", "private_property_identifier"}
)

#: Modifiers that turn a TypeScript constructor parameter into a field.
PARAMETER_PROPERTY_MODIFIERS = frozenset({"accessibility_modifier", "readonly"})

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
        {
            "identifier",
            "property_identifier",
            "private_property_identifier",
            "shorthand_property_identifier",
        }
    ),
    "TypeScript": frozenset(
        {
            "identifier",
            "property_identifier",
            "private_property_identifier",
            "shorthand_property_identifier",
            "type_identifier",
        }
    ),
    "Java": frozenset({"identifier", "type_identifier"}),
    "Gosu": frozenset({"identifier"}),
}
