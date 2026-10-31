"""Helper module used by the cli_project fixture."""


def greet(name: str) -> str:
    """Return a greeting for *name*."""
    if False:
        return "unreachable"
    return f"hello {name}"
