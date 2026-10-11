from __future__ import annotations

from threading import Lock

from profileconf.config import Config
from profileconf.loader import LoadOptions, load

_lock = Lock()
_current: Config | None = None


def configure(source: LoadOptions | Config | None = None) -> Config:
    """Set the process-wide Config, loading it from ``source`` options or installing a ready Config."""
    global _current
    config = source if isinstance(source, Config) else load(source)
    with _lock:
        _current = config
    return config


def current() -> Config:
    """Return the process-wide Config, loading it with default options on first use."""
    global _current
    with _lock:
        if _current is None:
            _current = load()
        return _current


def reset() -> None:
    """Forget the process-wide Config (for tests)."""
    global _current
    with _lock:
        _current = None
