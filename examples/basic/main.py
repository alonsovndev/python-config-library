"""Run with: APP_ENV=local python examples/basic/main.py  (or APP_ENV=prod with the variables set)."""

from dataclasses import dataclass
from pathlib import Path

from profileconf import LoadOptions, load

HERE = Path(__file__).parent


@dataclass
class Postgres:
    host: str
    port: int
    password: str


config = load(LoadOptions(config_dir=HERE, env_file=HERE / ".env"))

print(f"profile: {config.profile}")
print(f"frontend: {config.require('app.frontend_base_url')}")
print(f"cors origins: {config.get_list('cors.origins')}")
print(f"cors credentials: {config.get_bool('cors.allow_credentials')}")
print(f"postgres: {config.bind(Postgres, prefix='persistence.postgres')!r}")
print(config)
