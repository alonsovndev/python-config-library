"""Spring-style profile configuration: per-profile YAML files, .env support and ${VAR:default} placeholders."""

import logging
from importlib.metadata import PackageNotFoundError, version

from profileconf.config import Config
from profileconf.errors import (
    ConfigParseError,
    ConfigTypeError,
    MissingKeyError,
    MissingVariableError,
    ProfileconfError,
    ProfileNotFoundError,
)
from profileconf.loader import LoadOptions, load
from profileconf.registry import configure, current, reset

logging.getLogger(__name__).addHandler(logging.NullHandler())

try:
    __version__ = version("profileconf")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "Config",
    "ConfigParseError",
    "ConfigTypeError",
    "LoadOptions",
    "MissingKeyError",
    "MissingVariableError",
    "ProfileNotFoundError",
    "ProfileconfError",
    "__version__",
    "configure",
    "current",
    "load",
    "reset",
]
