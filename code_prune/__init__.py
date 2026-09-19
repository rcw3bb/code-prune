"""
Package initialization for code_prune.

Bootstraps the configuration directory and logging setup.

Author: Ron Webb
Since: 1.0.0
"""

from env_dir_bootstrap import EnvDirBootstrap

__version__ = "1.0.0"

_bootstrapper = EnvDirBootstrap(
    env_var="CODE_PRUNE_CONFIG_DIR",
    resources=["logging.ini"],
    package="code_prune",
)

_bootstrapper.setup()

CONF_DIR = str(_bootstrapper.get_dir())
