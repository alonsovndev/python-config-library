from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import profileconf
from profileconf import Config, LoadOptions

if TYPE_CHECKING:
    from pathlib import Path


def test_current_lazily_loads_defaults_from_cwd(tmp_path: Path) -> None:
    (tmp_path / "config_dev.yml").write_text("a: 1\n", encoding="utf-8")
    assert profileconf.current().get("a") == 1


def test_current_returns_same_instance(tmp_path: Path) -> None:
    (tmp_path / "config_dev.yml").write_text("a: 1\n", encoding="utf-8")
    assert profileconf.current() is profileconf.current()


def test_configure_with_options_loads_and_stores(config_dir: Path) -> None:
    (config_dir / "config_dev.yml").write_text("a: 2\n", encoding="utf-8")
    loaded = profileconf.configure(LoadOptions(config_dir=config_dir))
    assert profileconf.current() is loaded


def test_configure_with_ready_config_replaces_fakes() -> None:
    fake = Config.from_dict({"jwt": {"secret_key": "test"}})
    profileconf.configure(fake)
    assert profileconf.current().require("jwt.secret_key") == "test"


def test_reset_forgets_config(tmp_path: Path) -> None:
    profileconf.configure(Config.from_dict({"a": 1}))
    profileconf.reset()
    with pytest.raises(profileconf.ProfileNotFoundError):
        profileconf.current()
