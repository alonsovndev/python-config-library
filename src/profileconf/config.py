from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable, Mapping
from typing import Any, TypeVar, get_type_hints

from profileconf.errors import ConfigTypeError, MissingKeyError

T = TypeVar("T")

_MISSING: Any = object()
_SECRET_KEY_MARKERS = ("secret", "password", "token", "key", "dsn")
_MASK = "******"
_TRUE_TEXTS = frozenset({"true", "1", "yes", "on"})
_FALSE_TEXTS = frozenset({"false", "0", "no", "off"})


class Config:
    """Read-only view over a resolved configuration tree for one profile; accessors return copies."""

    def __init__(self, data: Mapping[str, Any], profile: str) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self._profile = profile

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], profile: str = "test") -> Config:
        """Build a Config from an in-memory mapping, without touching files or the environment."""
        return cls(data, profile)

    @property
    def profile(self) -> str:
        return self._profile

    def get(self, key: str, default: Any = None) -> Any:
        """Look up a dotted path (``a.b.0.c``); return ``default`` only when the path is absent."""
        value = self._lookup(key)
        return default if value is _MISSING else copy.deepcopy(value)

    def require(self, key: str) -> Any:
        value = self._lookup(key)
        if value is _MISSING or value is None:
            raise MissingKeyError(f"Required configuration key '{key}' is missing (profile '{self._profile}')")
        return copy.deepcopy(value)

    def get_str(self, key: str, default: str | None = None) -> str | None:
        value = self._lookup(key)
        if value is _MISSING or value is None:
            return default
        return str(value)

    def get_int(self, key: str, default: int | None = None) -> int | None:
        value = self._lookup(key)
        return default if _is_unset(value) else _to_int(value, key)

    def get_float(self, key: str, default: float | None = None) -> float | None:
        value = self._lookup(key)
        return default if _is_unset(value) else _to_float(value, key)

    def get_bool(self, key: str, default: bool | None = None) -> bool | None:
        value = self._lookup(key)
        return default if _is_unset(value) else _to_bool(value, key)

    def get_list(self, key: str, default: list[Any] | None = None) -> list[Any]:
        """Return a list; a comma-separated string is split and stripped, empty items dropped."""
        value = self._lookup(key)
        if _is_unset(value):
            return [] if default is None else list(default)
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise ConfigTypeError(f"Configuration key '{key}' is not a list: {_shown(value, key)}")

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def bind(self, model: type[T], prefix: str = "") -> T:
        """Instantiate a pydantic v2 model or a dataclass from the subtree at ``prefix``.

        Dataclass fields annotated exactly ``int``, ``float`` or ``bool`` are converted from text;
        other types (``Optional[int]``, nested dataclasses) are passed through unchanged. Use pydantic for those.
        """
        subtree = self.require(prefix) if prefix else self._data
        if not isinstance(subtree, Mapping):
            raise ConfigTypeError(f"Configuration key '{prefix}' is not a mapping: {_shown(subtree, prefix)}")
        data = copy.deepcopy(dict(subtree))
        model_validate = getattr(model, "model_validate", None)
        if model_validate is not None:
            return model_validate(data)  # type: ignore[no-any-return]
        if dataclasses.is_dataclass(model):
            try:
                return model(**_coerce_dataclass_fields(model, data))
            except TypeError as error:
                raise ConfigTypeError(f"Cannot bind '{prefix}' to {model.__name__}: {error}") from error
        raise TypeError(f"Cannot bind to {model!r}: expected a pydantic v2 model or a dataclass")

    def _lookup(self, key: str) -> Any:
        node: Any = self._data
        for segment in key.split("."):
            if isinstance(node, dict) and segment in node:
                node = node[segment]
            elif isinstance(node, list) and segment.isdecimal() and int(segment) < len(node):
                node = node[int(segment)]
            else:
                return _MISSING
        return node

    def __repr__(self) -> str:
        return f"Config(profile={self._profile!r}, data={_mask_secrets(self._data)!r})"


def _shown(value: Any, key: str) -> str:
    return _MASK if _is_secret_key(key.rsplit(".", 1)[-1]) else repr(value)


def _to_int(value: Any, key: str) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise ConfigTypeError(f"Configuration key '{key}' is not an integer: {_shown(value, key)}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ConfigTypeError(f"Configuration key '{key}' is not an integer: {_shown(value, key)}") from error


def _to_float(value: Any, key: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ConfigTypeError(f"Configuration key '{key}' is not a number: {_shown(value, key)}") from error


def _to_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_TEXTS:
        return True
    if text in _FALSE_TEXTS:
        return False
    raise ConfigTypeError(f"Configuration key '{key}' is not a boolean: {_shown(value, key)}")


_TEXT_CONVERTERS: dict[Any, Callable[[Any, str], Any]] = {int: _to_int, float: _to_float, bool: _to_bool}


def _coerce_dataclass_fields(model: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Convert interpolated text to the int/float/bool declared on a dataclass field; other types pass through."""
    try:
        hints = get_type_hints(model)
    except NameError:
        return data
    return {
        name: _TEXT_CONVERTERS[hints[name]](value, name)
        if isinstance(value, str) and hints.get(name) in _TEXT_CONVERTERS
        else value
        for name, value in data.items()
    }


def _is_unset(value: Any) -> bool:
    return value is _MISSING or value is None or value == ""


def _mask_secrets(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _mask_entry(key, value) for key, value in node.items()}
    if isinstance(node, list):
        return [_mask_secrets(item) for item in node]
    return node


def _mask_entry(key: Any, value: Any) -> Any:
    if value is not None and _is_secret_key(key):
        return _MASK
    return _mask_secrets(value)


def _is_secret_key(key: Any) -> bool:
    return isinstance(key, str) and any(marker in key.lower() for marker in _SECRET_KEY_MARKERS)
