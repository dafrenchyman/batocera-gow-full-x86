"""One stdlib compare-and-activate transaction for local and remote callers."""

import hashlib
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path


class ActivationError(RuntimeError):
    """Refuse a changed source before overwriting or restarting Wolf."""


def source_hash(text: str) -> str:
    """Return the SHA-256 of the exact UTF-8 configuration bytes."""
    return hashlib.sha256(text.encode()).hexdigest()


def activate_config(  # noqa: PLR0913, PLR0917  # Three transaction inputs and three independent effect callbacks.
    config_path: Path,
    expected_hash: str,
    text: str,
    idle: Callable[[], None],
    restart: Callable[[], object],
    ownership: Callable[[bool], object],
    *,
    retry_restart: bool = False,
) -> bool:
    """Compare and idle-gate twice, replace atomically, then restart only Wolf.

    Args:
        config_path: Canonical config destination, already ownership-validated.
        expected_hash: Digest of the source used for transformation.
        text: Complete intended configuration. Never saved to a backup.
        idle: Establish idle immediately before mutation, twice.
        restart: Restart Wolf, propagating failure without false activation.
        ownership: Persist false after replacement, true after successful restart.
        retry_restart: Retry an earlier failed restart even if bytes match.

    Returns:
        Whether the configuration bytes changed.

    Raises:
        ActivationError: If the source changes before replacement.
        OSError: If config or transaction storage cannot be accessed.
    """

    def unchanged() -> None:
        if hashlib.sha256(config_path.read_bytes()).hexdigest() != expected_hash:
            message = "source config changed; no overwrite or restart"
            raise ActivationError(message)

    unchanged()
    idle()
    unchanged()
    metadata = config_path.stat()
    attributes = {
        name: os.getxattr(config_path, name) for name in os.listxattr(config_path)
    }
    data = text.encode()
    idle()
    unchanged()
    changed = config_path.read_bytes() != data
    if changed:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".gow-full-x86-", dir=config_path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
                os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
                for name, value in attributes.items():
                    os.setxattr(stream.fileno(), name, value)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            unchanged()
            Path(temporary).replace(config_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        ownership(False)  # noqa: FBT003  # Callable[[bool], object] persists activation state.
    if changed or retry_restart:
        restart()
        ownership(True)  # noqa: FBT003  # Callable[[bool], object] persists activation state.
    return changed
