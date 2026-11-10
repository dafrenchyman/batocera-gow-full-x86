"""Validated OpenSSH destination data shared by host commands."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

_ASCII_SPACE = 32
_ASCII_DELETE = 127


class SettingsError(ValueError):
    """Report configuration failures without including private input values."""


@dataclass(frozen=True)
class SSHConfig:
    """Hold a target and optional key pathname, never private key contents."""

    target: str
    identity_file: str | None = None

    def __post_init__(self) -> None:
        """Validate direct construction with the same rules as selected settings."""
        if (
            not self.target
            or self.target.startswith("-")
            or not re.fullmatch(r"[A-Za-z0-9_.@:%\[\]-]+", self.target)
            or self.target.count("@") > 1
            or self.target.startswith("@")
            or self.target.endswith("@")
        ):
            message = (
                "BATOCERA_GOW_SSH_TARGET must be an OpenSSH alias, "
                "hostname or IP target"
            )
            raise SettingsError(message)
        if self.identity_file is not None and (
            not self.identity_file
            or any(
                ord(char) < _ASCII_SPACE or ord(char) == _ASCII_DELETE
                for char in self.identity_file
            )
        ):
            message = "Optional SSH identity must be a literal pathname"
            raise SettingsError(message)

    @classmethod
    def from_environment(cls, values: Mapping[str, str]) -> "SSHConfig":
        """Resolve only SSH values from an already selected configuration snapshot."""
        return cls(
            values.get("BATOCERA_GOW_SSH_TARGET", ""),
            values.get("BATOCERA_GOW_SSH_IDENTITY_FILE"),
        )

    def argv(self) -> list[str]:
        """Build noninteractive verified-host argv, retaining normal agent behavior."""
        result = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ServerAliveInterval=5",
            "-o",
            "ServerAliveCountMax=1",
        ]
        if self.identity_file is not None:
            result.extend(["-i", self.identity_file])
        return [*result, "--", self.target]
