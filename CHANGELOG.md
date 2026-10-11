# Changelog

## 0.1.0 (unreleased)

- Per-profile YAML loading (`config_{profile}.yml`) with configurable env var, default profile and filename template.
- `.env` support without mutating `os.environ` (opt in with `export_env=True`).
- `${VAR}` / `${VAR:default}` interpolation, empty defaults, embedded placeholders, `$${` escape and legacy `!ENV` tag.
- Strict mode: unset variables without a default raise `MissingVariableError`.
- `Config` with dotted lookup (including list indexes), `require`, typed getters, `bind()` and `from_dict()`.
- Optional process-wide holder: `configure()`, `current()`, `reset()`.
