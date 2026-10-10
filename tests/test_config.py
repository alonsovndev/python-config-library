from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from profileconf import Config, ConfigTypeError, MissingKeyError

DATA = {
    "app": {"name": "demo", "debug": "false", "port": "8080", "ratio": "0.5", "nothing": None, "empty": ""},
    "cors": {"origins": ["http://a", "http://b"], "csv": "a, b ,,c"},
    "jwt": {"secret_key": "s3cret", "algorithm": "HS256"},
    "db": {"host": "localhost", "port": 5432},
}


@pytest.fixture
def config() -> Config:
    return Config.from_dict(DATA, profile="local")


def test_get_dotted_path_and_default(config: Config) -> None:
    assert config.get("app.name") == "demo"
    assert config.get("app.missing", "fallback") == "fallback"
    assert config.get("app.name.deeper", "fallback") == "fallback"


def test_get_list_index(config: Config) -> None:
    assert config.get("cors.origins.1") == "http://b"
    assert config.get("cors.origins.9", "none") == "none"


def test_present_null_is_not_replaced_by_default(config: Config) -> None:
    assert config.get("app.nothing", "fallback") is None


def test_require_raises_for_missing_and_null(config: Config) -> None:
    assert config.require("app.name") == "demo"
    with pytest.raises(MissingKeyError, match=r"app\.missing"):
        config.require("app.missing")
    with pytest.raises(MissingKeyError):
        config.require("app.nothing")


def test_get_bool_parses_text_not_truthiness(config: Config) -> None:
    assert config.get_bool("app.debug") is False
    assert config.get_bool("app.missing", True) is True
    assert config.get_bool("app.empty", True) is True


def test_get_bool_rejects_garbage() -> None:
    with pytest.raises(ConfigTypeError, match="x"):
        Config.from_dict({"x": "maybe"}).get_bool("x")


def test_get_int_and_float(config: Config) -> None:
    assert config.get_int("app.port") == 8080
    assert config.get_int("db.port") == 5432
    assert config.get_int("app.missing", 7) == 7
    assert config.get_float("app.ratio") == 0.5


def test_get_int_rejects_non_numeric(config: Config) -> None:
    with pytest.raises(ConfigTypeError):
        config.get_int("app.name")


def test_get_str_converts_values(config: Config) -> None:
    assert config.get_str("db.port") == "5432"
    assert config.get_str("app.nothing", "d") == "d"


def test_get_list_from_list_and_csv(config: Config) -> None:
    assert config.get_list("cors.origins") == ["http://a", "http://b"]
    assert config.get_list("cors.csv") == ["a", "b", "c"]
    assert config.get_list("cors.missing") == []
    assert config.get_list("cors.missing", ["x"]) == ["x"]


def test_get_list_rejects_scalar_number() -> None:
    with pytest.raises(ConfigTypeError):
        Config.from_dict({"x": 3}).get_list("x")


def test_as_dict_is_a_deep_copy(config: Config) -> None:
    snapshot = config.as_dict()
    snapshot["app"]["name"] = "changed"
    assert config.get("app.name") == "demo"


def test_constructor_copies_input() -> None:
    source = {"a": {"b": 1}}
    config = Config.from_dict(source)
    source["a"]["b"] = 2
    assert config.get("a.b") == 1


def test_repr_masks_secret_values(config: Config) -> None:
    text = repr(config)
    assert "s3cret" not in text
    assert "HS256" in text
    assert "profile='local'" in text


def test_bind_dataclass(config: Config) -> None:
    @dataclass
    class Database:
        host: str
        port: int

    assert config.bind(Database, prefix="db") == Database(host="localhost", port=5432)


def test_bind_pydantic_coerces_text(config: Config) -> None:
    class App(BaseModel):
        model_config = {"extra": "ignore"}
        name: str
        debug: bool
        port: int

    bound = config.bind(App, prefix="app")
    assert (bound.name, bound.debug, bound.port) == ("demo", False, 8080)


def test_bind_missing_prefix_raises(config: Config) -> None:
    with pytest.raises(MissingKeyError):
        config.bind(dict, prefix="nope")


def test_bind_rejects_unsupported_type(config: Config) -> None:
    class Plain:
        pass

    with pytest.raises(TypeError):
        config.bind(Plain, prefix="db")


def test_bind_requires_mapping_subtree(config: Config) -> None:
    @dataclass
    class Anything:
        pass

    with pytest.raises(ConfigTypeError):
        config.bind(Anything, prefix="app.name")


def test_get_float_rejects_non_numeric_and_defaults(config: Config) -> None:
    assert config.get_float("app.missing", 1.5) == 1.5
    with pytest.raises(ConfigTypeError):
        config.get_float("app.name")


def test_get_bool_accepts_real_booleans_and_numeric_text() -> None:
    config = Config.from_dict({"a": True, "b": "1", "c": "off"})
    assert (config.get_bool("a"), config.get_bool("b"), config.get_bool("c")) == (True, True, False)


def test_bind_dataclass_coerces_text_to_declared_scalar_types() -> None:
    @dataclass
    class Server:
        port: int
        ratio: float
        debug: bool
        name: str

    config = Config.from_dict({"server": {"port": "8080", "ratio": "0.5", "debug": "false", "name": "x"}})
    assert config.bind(Server, prefix="server") == Server(port=8080, ratio=0.5, debug=False, name="x")


def test_bind_dataclass_reports_invalid_text_with_field_name() -> None:
    @dataclass
    class Server:
        port: int

    with pytest.raises(ConfigTypeError, match="port"):
        Config.from_dict({"port": "abc"}).bind(Server)


def test_bind_dataclass_with_unresolvable_annotation_skips_coercion() -> None:
    @dataclass
    class Server:
        port: UndefinedType  # type: ignore[name-defined]  # noqa: F821

    assert Config.from_dict({"port": "8080"}).bind(Server) == Server(port="8080")


def test_repr_masks_list_and_dict_values_under_secret_keys() -> None:
    config = Config.from_dict({"api_keys": ["aaa", "bbb"], "secrets": {"db": "hunter2"}, "plain": ["ok"]})
    text = repr(config)
    assert "aaa" not in text
    assert "hunter2" not in text
    assert "ok" in text


def test_type_errors_do_not_echo_secret_values() -> None:
    with pytest.raises(ConfigTypeError) as error:
        Config.from_dict({"jwt": {"secret": "hunter2"}}).get_int("jwt.secret")
    assert "hunter2" not in str(error.value)


def test_get_returns_copies_of_containers() -> None:
    config = Config.from_dict({"a": {"b": [1]}})
    config.get("a")["b"].append(2)
    config.require("a")["b"].append(3)
    assert config.get("a.b") == [1]


def test_get_int_rejects_bool_and_fractional_float() -> None:
    config = Config.from_dict({"flag": True, "ratio": 1.9, "whole": 2.0})
    with pytest.raises(ConfigTypeError):
        config.get_int("flag")
    with pytest.raises(ConfigTypeError):
        config.get_int("ratio")
    assert config.get_int("whole") == 2


def test_get_list_treats_empty_string_as_unset() -> None:
    assert Config.from_dict({"e": ""}).get_list("e", ["d"]) == ["d"]


def test_bind_dataclass_unknown_key_raises_config_type_error() -> None:
    @dataclass
    class Server:
        port: int

    with pytest.raises(ConfigTypeError, match="Server"):
        Config.from_dict({"port": 1, "extra": 2}).bind(Server)
