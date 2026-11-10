"""Read-only native inspection entry points with bounded, private-safe output."""

import builtins
import hashlib
import importlib
import json
import os
import stat
import sys
from pathlib import Path
from types import TracebackType
from typing import Self

LINUX_MAX_ERRNO = 4095
EXPECTED_ARGC = 2

INSPECTION_FAILURES = {
    "Diagnostic object missing": "diagnostic-object-missing",
    "Invalid integrity inspection path": "invalid-integrity-path",
    "Packaged source/stock integrity mismatch": "integrity-mismatch",
    "Additive package is writable or has ACLs": "package-writable-or-acl",
    "Userdata is not confined to the native disposable home": "userdata-not-confined",
    "App real/effective/saved identity differs": "app-identity-mismatch",
    "Capability-free non-root app ancestry not observed": "app-ancestry-missing",
    "Supervisor PID/app identity is not established": "supervisor-identity-missing",
    "Effective container seccomp filter missing": "seccomp-missing",
    "Native uinput device missing": "uinput-not-character-device",
    "Native app cannot read/write uinput": "app-uinput-access",
}
EXCEPTION_CLASSES = (
    "OSError",
    "FileNotFoundError",
    "PermissionError",
    "NotADirectoryError",
    "IsADirectoryError",
    "ValueError",
    "TypeError",
    "KeyError",
    "RuntimeError",
    "ImportError",
    "ModuleNotFoundError",
    "SyntaxError",
    "AttributeError",
    "Exception",
)


def record(value: object) -> dict[str, object]:
    """Require a JSON object with string keys at the reader boundary."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        message = "Invalid native reader object"
        raise ValueError(message)
    return dict(value)


def text(value: object) -> str:
    """Require a nonempty textual identity without exposing the invalid value."""
    if not isinstance(value, str) or not value:
        message = "Invalid native reader identity"
        raise ValueError(message)
    return value


def digest(path: Path, *, readonly: bool = False) -> str:
    """Hash a stable regular input and optionally require its mount read-only."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size == 0:
            message = "Nonregular native input"
            raise ValueError(message)
        if readonly and not os.fstatvfs(stream.fileno()).f_flag & os.ST_RDONLY:
            message = "Writable native firmware"
            raise ValueError(message)
        value = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            message = "Native input changed during inspection"
            raise ValueError(message)
        return value


def qualified_input(expected: dict[str, object], *, root: Path = Path("/")) -> bool:
    """Match installed inputs below an explicit filesystem root without launch."""
    # Import only after the entry point has suppressed incidental library output.
    from batocera_gow.runtime.mounted_media import read_selection  # noqa: PLC0415 - import only inside redirected output envelope.

    selection = read_selection(
        root / "home/retro/.native-control/selection.json",
        root / "home/retro/userdata/roms",
        catalog_path=root / "usr/share/emulationstation/es_systems.cfg",
    )
    profile = record(expected["profile"])
    media = record(expected["media"])
    template = root / "opt/gow-full-x86/suite-es-input.cfg"
    mapping = template.read_text(encoding="utf-8").replace(
        "{guid}", text(profile["guid"])
    )
    matched = (
        selection.system == expected["system"]
        and selection.digest == media["identity"]
        and hashlib.sha256(mapping.encode()).hexdigest() == profile["sha256"]
        and digest(template) == profile["template_sha256"]
        and digest(root / "opt/gow-full-x86/suite-gamepad.json")
        == profile["definition_sha256"]
    )
    prerequisites = record(expected.get("prerequisites", {}))
    if expected["backend"] == "duckstation":
        generator = importlib.import_module(
            "configgen.generators.duckstation.duckstationGenerator"
        )
        finder: object = vars(generator)["find_bios"]
        if not callable(finder):
            message = "Stock firmware finder unavailable"
            raise ValueError(message)
        found: object = finder(vars(generator)["bios_lists"])
        identities = sorted(
            (region, digest(root / "userdata/bios" / text(name), readonly=True))
            for region, name in record(found).items()
        )
        matched = (
            matched
            and bool(identities)
            and hashlib.sha256(
                json.dumps(identities).encode(),
            ).hexdigest()
            == record(prerequisites["bios"])["identity"]
        )
    elif expected["backend"] == "xemu":
        matched = (
            matched
            and all(
                digest(root / path.lstrip("/"), readonly=True)
                == record(prerequisites[key])["identity"]
                for key, path in (
                    ("mcpx", "/userdata/bios/mcpx_1.0.bin"),
                    ("bios", "/userdata/bios/Complex_4627.bin"),
                )
            )
            and digest(root / "usr/share/xemu/data/xbox_hdd.qcow2")
            == record(prerequisites["hdd"])["source_identity"]
        )
    return matched


def inspection(request: dict[str, object]) -> dict[str, object]:
    """Translate packaged inspector failures without returning arbitrary messages."""
    # Stock diagnostic imports may print; main has already suppressed both FDs.
    from batocera_gow.runtime.native_diagnostics import (  # noqa: PLC0415 - stock imports may print before privacy envelope.
        DiagnosticError,
        inspect_runtime,
    )

    try:
        return {"ok": True, "result": inspect_runtime(request)}
    except DiagnosticError as error:
        message = error.args[0] if len(error.args) == 1 else None
        code = (
            INSPECTION_FAILURES.get(message, "unknown-diagnostic")
            if isinstance(message, str)
            else "unknown-diagnostic"
        )
        return {"ok": False, "inspection_failure": {"code": code}}


class _Envelope:
    """Own output descriptors and sanitize every exception crossing the reader."""

    def __init__(self, operation: str) -> None:
        """Prepare operation-specific privacy state without redirecting on import."""
        self.operation = operation
        self.response: dict[str, object] = {}
        self.output = -1
        self.error_output = -1

    def __enter__(self) -> Self:
        """Redirect both borrowed process streams for the checked operation."""
        self.output = os.dup(1)
        try:
            self.error_output = os.dup(2)
            with Path(os.devnull).open("w", encoding="utf-8") as discard:
                os.dup2(discard.fileno(), 1)
                os.dup2(discard.fileno(), 2)
        except OSError:
            os.close(self.output)
            if self.error_output >= 0:
                os.close(self.error_output)
            raise
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Emit only a sanitized bounded response and restore owned descriptors."""
        # This is the process privacy boundary, including unknown dependency
        # exception subclasses. Never serialize their messages or tracebacks.
        if error is not None:
            known_types = {getattr(builtins, name): name for name in EXCEPTION_CLASSES}
            failure: dict[str, object] = {
                "code": "os-error"
                if isinstance(error, OSError)
                else "unexpected-exception",
                "exception_class": known_types.get(type(error), "Exception"),
            }
            if (
                isinstance(error, OSError)
                and type(error.errno) is int
                and 0 < error.errno <= LINUX_MAX_ERRNO
            ):
                failure["errno"] = error.errno
            self.response = (
                {"matched": False}
                if self.operation == "qualified"
                else {"ok": False, "inspection_failure": failure}
            )
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            encoded = json.dumps(self.response).encode("utf-8")
            if len(encoded) > 24 * 1024 * 1024:
                encoded = (
                    b'{"ok":false,"inspection_failure":{"code":"response-too-large"}}'
                )
            os.dup2(self.output, 1)
            os.dup2(self.error_output, 2)
            with os.fdopen(self.output, "wb", closefd=False) as stream:
                stream.write(encoded)
        finally:
            os.close(self.output)
            os.close(self.error_output)
        return error is not None


def main() -> int:
    """Emit one bounded JSON envelope, never incidental stdout or stderr."""
    operation = sys.argv[1] if len(sys.argv) == EXPECTED_ARGC else ""
    with _Envelope(operation) as envelope:
        request = record(json.load(sys.stdin))
        if operation == "inspect":
            envelope.response = inspection(request)
        elif operation == "qualified":
            envelope.response = {"matched": qualified_input(request)}
        else:
            message = "Unknown native reader operation"
            raise ValueError(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
