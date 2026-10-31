"""User-configurable overrides for code_prune, read from ``config.ini``.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import configparser
from pathlib import Path

from . import CONF_DIR

_DEFAULT_IGNORE_FILE = ".codepruneignore"


class Config:
    """Reads user-configurable overrides from ``config.ini`` in *conf_dir*.

    Author: Ron Webb
    Since: 1.0.0
    """

    def __init__(self, conf_dir: str | None = None) -> None:
        """Load ``config.ini`` from *conf_dir* (defaults to ``CONF_DIR``).

        Author: Ron Webb
        Since: 1.0.0
        """
        self._config = configparser.ConfigParser()
        config_path = Path(conf_dir or CONF_DIR) / "config.ini"
        self._config.read(config_path)

    def get_ignore_file(self) -> str:
        """Return the configured ``.codepruneignore`` filename override.

        Falls back to ``.codepruneignore`` when the section/key is absent.

        Author: Ron Webb
        Since: 1.0.0
        """
        return self._config.get(
            "override", "ignore-file", fallback=_DEFAULT_IGNORE_FILE
        )
