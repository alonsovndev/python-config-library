from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from profileconf.errors import MissingVariableError

if TYPE_CHECKING:
    from collections.abc import Mapping

_PLACEHOLDER = re.compile(r"\$\$\{|\$\{(?P<name>[^}:]+)(?::(?P<default>[^}]*))?\}")
_ESCAPED_OPENING = "$${"


def interpolate(tree: Any, variables: Mapping[str, str], strict: bool) -> Any:
    """Return a copy of ``tree`` with ``${VAR}`` / ``${VAR:default}`` placeholders in strings resolved.

    ``$${`` is an escape that yields a literal ``${``. A value that is exactly one placeholder with
    no value and no default becomes ``None`` when ``strict`` is false; otherwise it raises.
    """
    return _resolve(tree, variables, strict, path="")


def _resolve(node: Any, variables: Mapping[str, str], strict: bool, path: str) -> Any:
    if isinstance(node, dict):
        return {key: _resolve(value, variables, strict, _join(path, str(key))) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve(item, variables, strict, _join(path, str(index))) for index, item in enumerate(node)]
    if isinstance(node, str):
        return _resolve_string(node, variables, strict, path)
    return node


def _join(path: str, segment: str) -> str:
    return f"{path}.{segment}" if path else segment


def _resolve_string(text: str, variables: Mapping[str, str], strict: bool, path: str) -> str | None:
    unset_names: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        if match.group(0) == _ESCAPED_OPENING:
            return "${"
        name = match.group("name")
        if name in variables:
            return variables[name]
        default = match.group("default")
        if default is not None:
            return default
        if strict:
            raise MissingVariableError(f"Variable '{name}' is not set and has no default (config key '{path}')")
        unset_names.append(name)
        return ""

    resolved = _PLACEHOLDER.sub(substitute, text)
    if unset_names and _PLACEHOLDER.fullmatch(text):
        return None
    return resolved
