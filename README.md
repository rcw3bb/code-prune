# code-prune

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/rcw3bb/code-prune/blob/main/LICENSE) [![Version](https://img.shields.io/badge/Version-1.0.0-green.svg)](https://github.com/rcw3bb/code-prune/blob/main/CHANGELOG.md) [![Python](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/) [![PyPI](https://img.shields.io/badge/PyPI-code-prune-orange)](https://pypi.org/project/code-prune/)


Find unreachable, unused, and obsolete code before it becomes technical debt.

## Requirements

- Python `>=3.14`
- Poetry `2.2`

## Installation

```powershell
poetry install
```

## Configuration

Logging is bootstrapped via `env-dir-bootstrap`. Set the `CODE_PRUNE_CONFIG_DIR`
environment variable to override the default configuration directory used to
resolve `logging.ini`.

## Development

Run tests with coverage and generate an HTML report:

```powershell
poetry run pytest --cov=code_prune tests --cov-report html
```

Format and lint the code:

```powershell
poetry run black code_prune; poetry run pylint code_prune
```

## License

This project is licensed under the [MIT License](LICENSE).
