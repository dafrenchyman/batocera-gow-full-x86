"""Resolve explicit host configuration without discovery or environment mutation."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from dotenv import dotenv_values

from batocera_gow.host.ssh_config import SettingsError, SSHConfig


@dataclass(frozen=True)
class HostSettings:
    """An invocation's immutable values; configuration never grants authorization."""

    values: Mapping[str, str]

    def __post_init__(self) -> None:
        """Copy caller values into a read-only per-invocation snapshot."""
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @classmethod
    def resolve(
        cls,
        *,
        env_file: Path | None = None,
        overrides: Mapping[str, str] | None = None,
        environ: Mapping[str, str] | None = None,
        defaults: Mapping[str, str] | None = None,
    ) -> "HostSettings":
        """Snapshot CLI > environment > selected file > defaults, without I/O later.

        Args:
            env_file: Explicit file selection. None performs no file search.
            overrides: Explicit command values, including invalid empty values.
            environ: Supplied environment, or the current process environment.
            defaults: Safe defaults for absent values only.

        Raises:
            SettingsError: If a selected file cannot be read or decoded.
        """
        values = dict(defaults or {})
        if env_file is not None:
            try:
                # Opening explicitly prevents python-dotenv's missing-file fallback.
                with env_file.open(encoding="utf-8") as stream:
                    parsed = dotenv_values(stream=stream, interpolate=False)
            except (OSError, UnicodeError) as error:
                message = "Cannot read the explicitly selected environment file"
                raise SettingsError(message) from error
            values.update(
                {
                    key: value if value is not None else ""
                    for key, value in parsed.items()
                }
            )
        values.update(os.environ if environ is None else environ)
        if overrides is not None:
            values.update(overrides)
        return cls(values)

    def get(self, key: str, default: str | None = None) -> str | None:
        """Read one resolved value without consulting ambient sources again."""
        return self.values.get(key, default)

    def ssh(self) -> SSHConfig:
        """Validate SSH only when a caller actually needs a remote connection."""
        return SSHConfig.from_environment(self.values)
