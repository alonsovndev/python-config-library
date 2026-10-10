from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from dotenv import dotenv_values

from profileconf.config import Config
from profileconf.errors import ConfigParseError, ProfileNotFoundError
from profileconf.interpolation import interpolate

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

_PROFILE_PLACEHOLDER = "{profile}"
_VALID_PROFILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_TYPE_TAG_PREFIX = re.compile(r"^tag:\S+\s+")


@dataclass(frozen=True)
class LoadOptions:
    """How to locate and resolve a configuration.

    Profile precedence: ``profile`` argument, process env var ``profile_env_var``, the same
    variable in the ``.env`` file, then ``default_profile``. Placeholder values come from the
    process environment first, then the ``.env`` file, then the inline default.
    """

    config_dir: Path | str | None = None
    env_file: Path | str | None = None
    profile: str | None = None
    profile_env_var: str = "APP_ENV"
    default_profile: str = "dev"
    filename_template: str = "config_{profile}.yml"
    strict: bool = True
    export_env: bool = False

    def __post_init__(self) -> None:
        if _PROFILE_PLACEHOLDER not in self.filename_template:
            raise ValueError(f"filename_template must contain '{_PROFILE_PLACEHOLDER}': {self.filename_template!r}")


class _ConfigLoader(yaml.SafeLoader):
    """Private loader so the global ``yaml.SafeLoader`` is never modified."""


def _construct_env_scalar(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
    text = loader.construct_scalar(node)
    # Legacy pyaml_env form: `!ENV tag:yaml.org,2002:bool ${VAR:false}`. The type tag is ignored.
    return _TYPE_TAG_PREFIX.sub("", str(text))


_ConfigLoader.add_constructor("!ENV", _construct_env_scalar)


def load(options: LoadOptions | None = None) -> Config:
    """Resolve the profile, read its YAML file, interpolate placeholders and return a Config."""
    options = options or LoadOptions()
    config_dir = Path(options.config_dir) if options.config_dir is not None else Path.cwd()
    env_file = Path(options.env_file) if options.env_file is not None else Path.cwd() / ".env"

    dotenv_variables = _read_dotenv(env_file)
    profile = _resolve_profile(options, dotenv_variables)
    config_path = _config_path(config_dir, profile, options.filename_template)

    raw_tree = _read_yaml(config_path)
    variables = {**dotenv_variables, **os.environ}
    resolved_tree = interpolate(raw_tree, variables, options.strict)

    if options.export_env:
        for name, value in dotenv_variables.items():
            os.environ.setdefault(name, value)

    logger.debug("Loaded profile '%s' from %s", profile, config_path)
    return Config(resolved_tree, profile)


def _read_dotenv(env_file: Path) -> dict[str, str]:
    if not env_file.is_file():
        return {}
    return {name: value for name, value in dotenv_values(env_file).items() if value is not None}


def _resolve_profile(options: LoadOptions, dotenv_variables: Mapping[str, str]) -> str:
    candidates = (
        options.profile,
        os.environ.get(options.profile_env_var),
        dotenv_variables.get(options.profile_env_var),
        options.default_profile,
    )
    profile = next((candidate.strip() for candidate in candidates if candidate and candidate.strip()), None)
    if profile is None:
        raise ProfileNotFoundError("No profile could be resolved: profile, env var and default_profile are all empty")
    return profile.lower()


def _config_path(config_dir: Path, profile: str, filename_template: str) -> Path:
    if not _VALID_PROFILE.fullmatch(profile) or ".." in profile:
        raise ProfileNotFoundError(f"Invalid profile name: {profile!r}")
    path = config_dir / filename_template.format(profile=profile)
    if not path.is_file():
        available = ", ".join(_available_profiles(config_dir, filename_template)) or "none"
        raise ProfileNotFoundError(
            f"No configuration file for profile '{profile}': expected {path}. Available profiles: {available}"
        )
    return path


def _available_profiles(config_dir: Path, filename_template: str) -> list[str]:
    prefix, suffix = filename_template.split(_PROFILE_PLACEHOLDER, 1)
    pattern = re.compile(f"{re.escape(prefix)}(?P<profile>.+){re.escape(suffix)}")
    if not config_dir.is_dir():
        return []
    matches = (pattern.fullmatch(entry.name) for entry in config_dir.iterdir() if entry.is_file())
    return sorted(match.group("profile") for match in matches if match)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            tree = yaml.load(stream, Loader=_ConfigLoader)  # noqa: S506 - _ConfigLoader extends SafeLoader
    except yaml.YAMLError as error:
        raise ConfigParseError(f"Invalid YAML in {path}: {error}") from error
    if tree is None:
        return {}
    if not isinstance(tree, dict):
        raise ConfigParseError(f"{path} must contain a mapping at the top level, got {type(tree).__name__}")
    return tree
