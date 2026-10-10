class ProfileconfError(Exception):
    """Base class for every error raised by profileconf."""


class ProfileNotFoundError(ProfileconfError):
    """The profile name is invalid or has no configuration file."""


class MissingVariableError(ProfileconfError):
    """A ``${VAR}`` placeholder has no value and no default (strict mode)."""


class MissingKeyError(ProfileconfError, KeyError):
    """A required configuration key is absent or null."""

    def __str__(self) -> str:
        # KeyError.__str__ would repr() the message.
        return str(self.args[0]) if self.args else ""


class ConfigTypeError(ProfileconfError, ValueError):
    """A configuration value cannot be converted to the requested type."""


class ConfigParseError(ProfileconfError):
    """The configuration file is not valid YAML or not a mapping at the top level."""
