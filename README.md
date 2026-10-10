# profileconf

Spring-style **profile configuration** for Python: one YAML file per profile, optional `.env`, and
`${VAR:default}` placeholders. Typed getters, strict missing-variable errors, no global side effects.

```text
config/
  config_local.yml
  config_prod.yml
.env                 # APP_ENV=local
```

## Install

```bash
pip install profileconf              # PyYAML + python-dotenv
pip install "profileconf[pydantic]"  # only needed to bind() pydantic models
```

Python 3.10+. (Not yet published to PyPI.)

## Quick start

```yaml
# config/config_local.yml
persistence:
  postgres:
    host: localhost
    port: ${DB_PORT:5432}
    password: ${DB_PASSWORD:}
cors:
  origins: ${CORS_ORIGINS:http://localhost:5173,http://127.0.0.1:5173}
  allow_credentials: ${CORS_ALLOW_CREDENTIALS:false}
```

```python
from profileconf import LoadOptions, load

config = load(LoadOptions(config_dir="config"))

config.profile                                   # "local"
config.get("persistence.postgres.host")          # "localhost"
config.get_int("persistence.postgres.port")      # 5432
config.get_bool("cors.allow_credentials")        # False  (not the truthy string "false")
config.get_list("cors.origins")                  # ["http://localhost:5173", "http://127.0.0.1:5173"]
config.require("persistence.postgres.password")  # raises MissingKeyError if absent or null
```

Typed settings:

```python
@dataclass
class Postgres:
    host: str
    port: int
    password: str

postgres = config.bind(Postgres, prefix="persistence.postgres")   # dataclass or pydantic v2 model
```

## How a profile is chosen

First match wins:

1. `LoadOptions(profile=...)`
2. the `APP_ENV` process environment variable (name configurable with `profile_env_var`)
3. `APP_ENV` in the `.env` file
4. `default_profile` (`"dev"`)

The name is lower-cased and mapped to `config_{profile}.yml` (`filename_template` is configurable, for
example `application-{profile}.yml`). An unknown profile raises `ProfileNotFoundError` listing the profiles
found. Profile names are restricted to letters, digits, `_`, `.` and `-` so they cannot escape `config_dir`.

## Placeholders

| Syntax | Result |
|---|---|
| `${VAR}` | value of `VAR`; raises `MissingVariableError` if unset (`strict=False` gives `None`) |
| `${VAR:default}` | value of `VAR`, else `default` |
| `${VAR:}` | value of `VAR`, else empty string |
| `a-${X}-b` | embedded use |
| `$${VAR}` | literal `${VAR}` |

Value precedence: **process environment > `.env` file > inline default**. A variable set to an empty
string counts as set and wins over the inline default. Resolved values are strings;
use `get_int` / `get_bool` / `get_list` / `bind` to convert. The legacy `pyaml_env` `!ENV` tag is accepted and
ignored, including its optional type tag, so existing YAML files load unchanged (use `get_bool` where you
relied on `!ENV tag:yaml.org,2002:bool`).

`.env` is read without modifying `os.environ`. Pass `LoadOptions(export_env=True)` to also export its
variables (existing variables are never overridden).

## Process-wide instance (optional)

```python
import profileconf

profileconf.configure(LoadOptions(config_dir="config"))   # once, at startup
profileconf.current().get("app.name")                     # anywhere
profileconf.current()                                     # loads with default options if never configured
```

In tests, replace the instance instead of writing fakes:

```python
profileconf.configure(Config.from_dict({"jwt": {"secret_key": "test"}}))
profileconf.reset()
```

## Coming from Spring Boot

| Spring Boot | profileconf |
|---|---|
| `spring.profiles.active` | `APP_ENV` |
| `application-{profile}.yml` | `config_{profile}.yml` (or set `filename_template`) |
| `${VAR:default}` | `${VAR:default}` |
| `@Value("${a.b}")` | `config.require("a.b")` |
| `@ConfigurationProperties` | `config.bind(Model, prefix="a")` |

There is no base file merged with a profile overlay yet; each profile file is complete.

## Errors

All derive from `ProfileconfError`: `ProfileNotFoundError`, `MissingVariableError`, `MissingKeyError`,
`ConfigTypeError`, `ConfigParseError`.

## Migrating from a hand-rolled `AppConfig` + `pyaml_env`

- `AppConfig.instance().get_config("a.b", d)` becomes `profileconf.current().get("a.b", d)`.
- Remove checks for the `"N/A"` sentinel: unset variables now raise, or are `None` with `strict=False`.
- Replace `int(...)` / `bool(...)` casts and manual comma-splitting with `get_int` / `get_bool` / `get_list`.
- `repr(config)` masks values under keys containing `secret`, `password`, `token`, `key` or `dsn`.

## Development

```bash
pip install -e ".[pydantic]" pytest pytest-cov ruff mypy types-PyYAML
ruff check . && ruff format --check . && mypy src && pytest --cov=profileconf
```

## License

MIT
