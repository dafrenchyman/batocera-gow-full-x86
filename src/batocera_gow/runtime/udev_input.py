"""Publish stock classification for pinned, already admitted app-local devices."""

import base64
import errno
import hashlib
import os
import re
import secrets
import stat
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

MAX_CLASSIFICATION_BYTES = 4096


def input_properties(output: str, required_class: str) -> dict[str, str]:
    """Accept stock input flags only when the caller's required class is present.

    Args:
        output: Stock input_id stdout, never caller-supplied replacement flags.
        required_class: Key or joystick class required for this admitted source.

    Raises:
        ValueError: The requested publication class is unsupported.
        RuntimeError: Output is oversized, malformed, ambiguous or lacks the class.
    """
    if required_class not in ("ID_INPUT_KEY", "ID_INPUT_JOYSTICK"):
        error_message = "unsupported publication class"
        raise ValueError(error_message)
    if len(output) > MAX_CLASSIFICATION_BYTES or not output.isascii():
        error_message = "invalid stock input classification"
        raise RuntimeError(error_message)
    properties = {}
    for line in output.splitlines():
        if not re.fullmatch(r"ID_INPUT(?:_[A-Z0-9]+)*=1", line):
            error_message = "unexpected stock input classification"
            raise RuntimeError(error_message)
        key, value = line.split("=")
        if key in properties:
            error_message = "duplicate stock input classification"
            raise RuntimeError(error_message)
        properties[key] = value
    if properties.get("ID_INPUT") != "1" or properties.get(required_class) != "1":
        error_message = "device lacks required stock input classification"
        raise RuntimeError(error_message)
    return properties


def validate_record_directory(info: os.stat_result) -> None:
    """Require the pinned publication directory to remain root-controlled."""
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        message = "udev data directory must be root-controlled"
        raise RuntimeError(message)


def require_live(valid: Callable[[], bool], stage: str) -> None:
    """Require the source pins to remain valid at each publication boundary."""
    if not valid():
        message = "input ownership lost " + stage
        raise ProcessLookupError(message)


class OwnedRecord:
    """Publish without clobbering; remove only the pinned owned inode/content."""

    def __init__(self, directory: str | Path, name: str, content: bytes) -> None:
        """Publish immutable bytes without adopting any existing record."""
        self.fd: int | None = None
        self.identity: tuple[int, int] | None = None
        self.name, self.content = name, content
        if not re.fullmatch(r"c[0-9]+:[0-9]+", name):
            error_message = "invalid udev record identity"
            raise RuntimeError(error_message)
        self.fd = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        temporary = ".gow-input-" + secrets.token_hex(12)
        try:
            info = os.fstat(self.fd)
            validate_record_directory(info)
            output = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self.fd,
            )
            try:
                with os.fdopen(output, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fchmod(stream.fileno(), 0o644)
                    info = os.fstat(stream.fileno())
                os.link(
                    temporary,
                    name,
                    src_dir_fd=self.fd,
                    dst_dir_fd=self.fd,
                    follow_symlinks=False,
                )
                self.identity = info.st_dev, info.st_ino
            finally:
                os.unlink(temporary, dir_fd=self.fd)
        except BaseException:
            self.close()
            raise

    def close(self) -> bool:
        """Remove only the unchanged owned inode and release its directory handle."""
        removed = False
        if self.fd is None:
            return removed
        try:
            if self.identity is not None:
                try:
                    target = os.open(
                        self.name,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                        dir_fd=self.fd,
                    )
                except FileNotFoundError:
                    return removed
                except OSError as error:
                    if error.errno != errno.ELOOP:
                        raise
                    return removed
                try:
                    info = os.fstat(target)
                    if (
                        stat.S_ISREG(info.st_mode)
                        and (info.st_dev, info.st_ino) == self.identity
                        and info.st_uid == os.geteuid()
                        and info.st_nlink == 1
                        and not info.st_mode & 0o022
                        and os.read(target, len(self.content) + 1) == self.content
                    ):
                        current = os.stat(
                            self.name, dir_fd=self.fd, follow_symlinks=False
                        )
                        if (current.st_dev, current.st_ino) == self.identity:
                            os.unlink(self.name, dir_fd=self.fd)
                            removed = True
                finally:
                    os.close(target)
        finally:
            os.close(self.fd)
            self.fd = None
        return removed


class UdevPublisher:
    """Own one stock-classified record and its app-local device advertisement."""

    def __init__(
        self,
        syspath: Path,
        node: Path,
        devt: int,
        valid: Callable[[], bool],
        *,
        required_class: str,
    ) -> None:
        """Classify a pinned source and publish metadata while it remains live."""
        self.record: OwnedRecord | None = None
        self.advertised = False
        require_live(valid, "before classification")
        with Path("/usr/bin/udevadm").open("rb") as stream:
            self.classifier_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        result = subprocess.run(  # noqa: S603 - fixed executable, argv only.
            ["/usr/bin/udevadm", "test-builtin", "input_id", str(syspath)],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        with Path("/usr/bin/udevadm").open("rb") as stream:
            if (
                hashlib.file_digest(stream, "sha256").hexdigest()
                != self.classifier_sha256
            ):
                error_message = "stock classifier changed during classification"
                raise RuntimeError(error_message)
        self.properties = input_properties(result.stdout, required_class)
        self.event = {
            "DEVPATH": str(syspath).removeprefix("/sys"),
            "DEVNAME": str(node),
            "SUBSYSTEM": "input",
            "MAJOR": str(os.major(devt)),
            "MINOR": str(os.minor(devt)),
            "USEC_INITIALIZED": str(time.monotonic_ns() // 1000),
            **self.properties,
        }
        require_live(valid, "during classification")
        try:
            content = "".join(
                "E:" + key + "=" + value + "\n"
                for key, value in self.properties.items()
            ).encode("ascii")
            self.record = OwnedRecord(
                "/run/udev/data", f"c{os.major(devt)}:{os.minor(devt)}", content
            )
            require_live(valid, "during publication")
            self.notify("add")
            self.advertised = True
            require_live(valid, "during notification")
        except BaseException:
            self.close()
            raise

    def notify(self, action: str) -> None:
        """Send this device's app-local event through Wolf's existing sender."""
        properties = {
            "ACTION": action,
            "SEQNUM": str(time.monotonic_ns()),
            **self.event,
        }
        payload = "".join(
            key + "=" + value + "\0" for key, value in properties.items()
        ).encode("ascii")
        result = subprocess.run(  # noqa: S603 - fixed executable, argv only.
            ["/usr/bin/fake-udev", "-m", base64.b64encode(payload).decode("ascii")],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode:
            error_message = (
                "fake-udev "
                + action
                + " failed: "
                + (result.stdout + result.stderr).decode("utf-8", "replace")[
                    :MAX_CLASSIFICATION_BYTES
                ]
            )
            raise RuntimeError(error_message)

    def close(self) -> None:
        """Remove the owned record, then withdraw its advertisement if still owned."""
        if self.record is not None:
            record, self.record = self.record, None
            if record.close() and self.advertised:
                self.notify("remove")
