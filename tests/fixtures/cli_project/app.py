"""Sample application entry point used by the CLI end-to-end test."""

import os


def main():
    """Print a greeting and exit."""
    return "hello"


def orphan_function():
    """Never referenced anywhere in this fixture project."""
    unused_local = 1
    return unused_local


# TODO: remove this once the migration is complete
