from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import yaml

from profileconf import (
    ConfigParseError,
    LoadOptions,
    MissingVariableError,
    ProfileNotFoundError,
    load,
)

if TYPE_CHECKING:
    from pathlib import Path


def write(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def options(config_dir: Path, **overrides: object) -> LoadOptions:
    return LoadOptions(config_dir=config_dir, **overrides)  # type: ignore[arg-type]


def test_default_profile_is_dev(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "app:\n  name: demo\n")
    config = load(options(config_dir))
    assert config.profile == "dev"
    assert config.get("app.name") == "demo"


def test_profile_from_process_env_is_lowercased(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_dir, "config_prod.yml", "level: prod\n")
    monkeypatch.setenv("APP_ENV", "PROD")
    assert load(options(config_dir)).get("level") == "prod"


def test_profile_from_dotenv_only(config_dir: Path, tmp_path: Path) -> None:
    write(config_dir, "config_local.yml", "level: local\n")
    env_file = write(tmp_path, ".env", "APP_ENV=local\n")
    config = load(options(config_dir, env_file=env_file))
    assert config.profile == "local"


def test_profile_precedence_argument_then_process_then_dotenv(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("explicit", "process", "dotenv", "dev"):
        write(config_dir, f"config_{name}.yml", f"picked: {name}\n")
    env_file = write(tmp_path, ".env", "APP_ENV=dotenv\n")
    assert load(options(config_dir, env_file=env_file)).get("picked") == "dotenv"
    monkeypatch.setenv("APP_ENV", "process")
    assert load(options(config_dir, env_file=env_file)).get("picked") == "process"
    assert load(options(config_dir, env_file=env_file, profile="explicit")).get("picked") == "explicit"


def test_custom_env_var_and_filename_template(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(config_dir, "application-staging.yml", "ok: true\n")
    monkeypatch.setenv("APP_PROFILE", "staging")
    loaded = load(options(config_dir, profile_env_var="APP_PROFILE", filename_template="application-{profile}.yml"))
    assert loaded.profile == "staging"
    assert loaded.get("ok") is True


def test_unknown_profile_lists_available(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "a: 1\n")
    write(config_dir, "config_prod.yml", "a: 1\n")
    with pytest.raises(ProfileNotFoundError, match=r"'qa'.*Available profiles: dev, prod"):
        load(options(config_dir, profile="qa"))


def test_unknown_profile_with_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ProfileNotFoundError, match="Available profiles: none"):
        load(options(tmp_path / "absent"))


@pytest.mark.parametrize("profile", ["../secrets", "a/b", "..", ".hidden"])
def test_path_traversal_profile_names_are_rejected(config_dir: Path, profile: str) -> None:
    with pytest.raises(ProfileNotFoundError, match="Invalid profile"):
        load(options(config_dir, profile=profile))


def test_filename_template_requires_placeholder() -> None:
    with pytest.raises(ValueError, match="profile"):
        LoadOptions(filename_template="config.yml")


def test_process_env_beats_dotenv_beats_inline_default(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(config_dir, "config_dev.yml", "a: ${ALPHA:inline}\nb: ${BETA:inline}\nc: ${GAMMA:inline}\n")
    env_file = write(tmp_path, ".env", "ALPHA=dotenv\nBETA=dotenv\n")
    monkeypatch.setenv("ALPHA", "process")
    config = load(options(config_dir, env_file=env_file))
    assert (config.get("a"), config.get("b"), config.get("c")) == ("process", "dotenv", "inline")


def test_legacy_env_tags_are_accepted(config_dir: Path) -> None:
    write(
        config_dir,
        "config_dev.yml",
        "url: !ENV ${URL:http://localhost:5173}\nflag: !ENV tag:yaml.org,2002:bool ${FLAG:false}\n",
    )
    config = load(options(config_dir))
    assert config.get("url") == "http://localhost:5173"
    assert config.get_bool("flag") is False


def test_strict_missing_variable_raises(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "jwt:\n  secret_key: ${JWT_SECRET}\n")
    with pytest.raises(MissingVariableError, match=r"jwt\.secret_key"):
        load(options(config_dir))


def test_non_strict_missing_variable_is_none(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "dsn: ${SENTRY_DSN}\n")
    assert load(options(config_dir, strict=False)).get("dsn", "default") is None


def test_load_does_not_modify_global_yaml_loader(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "a: !ENV ${X:1}\n")
    constructors_before = dict(yaml.SafeLoader.yaml_constructors)
    resolvers_before = dict(yaml.SafeLoader.yaml_implicit_resolvers)
    load(options(config_dir))
    assert yaml.SafeLoader.yaml_constructors == constructors_before
    assert yaml.SafeLoader.yaml_implicit_resolvers == resolvers_before
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("a: !ENV x")


def test_environment_is_untouched_by_default(config_dir: Path, tmp_path: Path) -> None:
    write(config_dir, "config_dev.yml", "a: 1\n")
    env_file = write(tmp_path, ".env", "PROFILECONF_PROBE=value\n")
    load(options(config_dir, env_file=env_file))
    assert "PROFILECONF_PROBE" not in os.environ


def test_export_env_sets_missing_variables_without_overriding(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(config_dir, "config_dev.yml", "a: 1\n")
    env_file = write(tmp_path, ".env", "PROFILECONF_NEW=from-dotenv\nPROFILECONF_OLD=from-dotenv\n")
    monkeypatch.setenv("PROFILECONF_OLD", "from-process")
    monkeypatch.delenv("PROFILECONF_NEW", raising=False)
    load(options(config_dir, env_file=env_file, export_env=True))
    assert os.environ["PROFILECONF_NEW"] == "from-dotenv"
    assert os.environ["PROFILECONF_OLD"] == "from-process"
    monkeypatch.delenv("PROFILECONF_NEW")


def test_defaults_to_current_directory(tmp_path: Path) -> None:
    write(tmp_path, "config_dev.yml", "where: cwd\n")
    write(tmp_path, ".env", "UNUSED=1\n")
    assert load().get("where") == "cwd"


def test_empty_file_gives_empty_config(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "")
    assert load(options(config_dir)).as_dict() == {}


def test_invalid_yaml_raises_parse_error(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "a: [unclosed\n")
    with pytest.raises(ConfigParseError, match=r"config_dev\.yml"):
        load(options(config_dir))


def test_non_mapping_root_raises_parse_error(config_dir: Path) -> None:
    write(config_dir, "config_dev.yml", "- a\n- b\n")
    with pytest.raises(ConfigParseError, match="mapping"):
        load(options(config_dir))


def test_blank_profile_everywhere_raises_clear_error(config_dir: Path) -> None:
    with pytest.raises(ProfileNotFoundError, match="No profile"):
        load(options(config_dir, default_profile=" "))
