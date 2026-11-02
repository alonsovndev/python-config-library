from __future__ import annotations

import pytest

from profileconf.errors import MissingVariableError
from profileconf.interpolation import interpolate


def resolve(tree: object, variables: dict[str, str] | None = None, strict: bool = True) -> object:
    return interpolate(tree, variables or {}, strict)


def test_variable_value_wins_over_inline_default() -> None:
    assert resolve({"host": "${HOST:localhost}"}, {"HOST": "db"}) == {"host": "db"}


def test_inline_default_used_when_variable_unset() -> None:
    assert resolve({"url": "${URL:http://localhost:5173}"}) == {"url": "http://localhost:5173"}


def test_empty_default_gives_empty_string() -> None:
    assert resolve({"password": "${PASSWORD:}"}) == {"password": ""}


def test_embedded_placeholders() -> None:
    assert resolve("a-${X}-b-${Y:z}", {"X": "1"}) == "a-1-b-z"


def test_escape_yields_literal_placeholder() -> None:
    assert resolve("$${NOT_A_VAR}") == "${NOT_A_VAR}"


def test_nested_lists_and_non_strings_are_preserved() -> None:
    tree = {"origins": ["${A:x}", 3, True, None]}
    assert resolve(tree) == {"origins": ["x", 3, True, None]}


def test_strict_missing_variable_names_variable_and_key_path() -> None:
    with pytest.raises(MissingVariableError, match=r"'SECRET'.*'jwt.secret_key'"):
        resolve({"jwt": {"secret_key": "${SECRET}"}})


def test_non_strict_whole_value_placeholder_becomes_none() -> None:
    assert resolve({"dsn": "${DSN}"}, strict=False) == {"dsn": None}


def test_non_strict_embedded_placeholder_becomes_empty() -> None:
    assert resolve({"url": "http://${HOST}/x"}, strict=False) == {"url": "http:///x"}


def test_input_tree_is_not_mutated() -> None:
    tree = {"a": ["${X:1}"]}
    resolve(tree)
    assert tree == {"a": ["${X:1}"]}
