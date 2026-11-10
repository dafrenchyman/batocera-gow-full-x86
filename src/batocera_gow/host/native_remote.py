"""Ephemeral stdlib-only native test operations, delivered over SSH stdin.

No request, API response, configuration or environment dump is saved remotely.
Importing this module has no effects. The host owns sequencing and deadlines;
each invocation independently validates identities before an owned effect.
"""

import base64
import hashlib
import json
import math
import os
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

LINUX_MAX_ERRNO = 4095
ASCII_SPACE = 32
MAX_PROCESS_ID = (1 << 31) - 1
MAX_USER_ID = (1 << 32) - 2
PRIVATE_FILE_MODE = 0o600
PROCESS_TABLE_COLUMNS = 4
SCRIPT_ACTION_INDEX = 2
MOUNTINFO_PREFIX_FIELDS = 6
DEVICE_TABLE_COLUMNS = 2
INPUT_DEVICE_MAJOR = 13
IMAGE_CHUNK_BYTES = 64 * 1024**2


class NativeError(RuntimeError):
    """A prerequisite, observation or owned operation failed closed."""


OPERATION_FAILURES = {
    "External operation failed: docker": "docker-command",
    "Bounded external operation unavailable or timed out": "external-unavailable",
    "Owned container is absent or ambiguous": "owned-container-unresolved",
    "Owned container identity mismatch": "owned-container-identity",
    "Control directory changed before lease update": "lease-control-identity",
    "Remote operation deadline expired": "deadline",
    "Native operation deadline expired": "deadline",
}

# Only fixed messages raised by the packaged read-only inspect_runtime path.
# Unknown DiagnosticError messages must never become public diagnostics.
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
INSPECTION_EXCEPTION_CLASSES = (
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


# These are complete fixed fatal lines from the packaged startup entry points,
# not substrings of arbitrary exceptions or a general container-log sanitizer.
STARTUP_FAILURES = {
    (
        "gow-full-x86: Wolf session Pulse server, sink and source are required"
    ): "runtime-audio-contract",
    "gow-full-x86: Wolf WAYLAND_DISPLAY is missing": "runtime-wayland-display-missing",
    "gow-full-x86: Wolf XDG_RUNTIME_DIR is missing": "runtime-directory-missing",
    (
        "gow-full-x86: authenticated Xwayland readiness timed out after ten seconds"
    ): "runtime-xwayland-timeout",
    "gow-full-x86: D-Bus readiness timed out": "runtime-dbus-timeout",
    (
        "gow-full-x86: hotkeygen reload-handler readiness timed out"
    ): "runtime-hotkeys-timeout",
    (
        "gow-input-transport: input transport readiness timed out"
    ): "transport-readiness-timeout",
    (
        "gow-input-transport: input worker closed while application remained running"
    ): "transport-worker-closed",
}
STARTUP_ROLES = (
    "supervisor",
    "input-worker",
    "runtime-entrypoint",
    "runtime-session",
    "runtime-hotkeys",
    "runtime-frontend",
    "frontend-observer",
    "receiver-probe",
    "emulator-probe",
    "stock-launcher",
    "retroarch",
    "duckstation-qt",
    "xemu",
    "xwayland",
    "session-bus",
    "window-manager",
    "emulationstation",
)
STARTUP_OUTPUT_BYTES = 64 * 1024
STARTUP_PROCESS_LIMIT = 64
EMULATOR_BOUNDARY_FILES = (
    "emulator-before-chord.json",
    "emulator-chord-pressed.json",
    "emulator-chord-released.json",
    "emulator-launcher-exit.json",
    "emulator-failure.json",
    "emulator-cleanup-start.json",
    "emulator-cleanup-returned.json",
)
SELECTED_EVIDENCE = frozenset(
    (
        "startup.json",
        "selection.json",
        "selected.log",
        "frontend-probe.json",
        "transport-probe.json",
        "emulator-probe.json",
        *EMULATOR_BOUNDARY_FILES,
        "frontend-ready.png",
        "frontend-failure.png",
        "emulator-before-exit.png",
        "emulator-failure.png",
        "receiver-failure.png",
        "stock_combo_exit_held_and_pointer_reset.png",
        "stock_context_pointer_button.png",
        "context_switch_without_semantic_leakage.png",
        "held_graceful_source_removal_and_recreation.png",
        "stock_command_once_per_stock_release.png",
    )
)


class InspectionError(NativeError):
    """Carry only validated inspection codes across both helper boundaries."""

    def __init__(self, failure: dict[str, object]) -> None:
        """Accept only fixed inspection categories and bounded platform errno."""
        code = failure.get("code")
        if not isinstance(code, str) or code not in (
            *INSPECTION_FAILURES.values(),
            "unknown-diagnostic",
            "os-error",
            "unexpected-exception",
            "response-too-large",
        ):
            msg = "Invalid inspection failure category"
            raise NativeError(msg)
        self.failure: dict[str, object] = {"code": code}
        message = "Packaged inspection failed: " + code
        if code in ("os-error", "unexpected-exception"):
            kind = failure.get("exception_class")
            if not isinstance(kind, str) or kind not in INSPECTION_EXCEPTION_CLASSES:
                msg = "Invalid inspection exception category"
                raise NativeError(msg)
            self.failure["exception_class"] = kind
            message += "; " + kind
            errno = failure.get("errno")
            if (
                code == "os-error"
                and type(errno) is int
                and 0 < errno <= LINUX_MAX_ERRNO
            ):
                self.failure["errno"] = errno
                message += "; errno=" + str(errno)
        super().__init__(message)


def record(value: object) -> dict[str, object]:
    """Validate an external object without admitting non-string keys."""
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        msg = "Expected an object"
        raise NativeError(msg)
    return {str(k): v for k, v in value.items()}


def sequence(value: object) -> list[object]:
    """Validate an external array."""
    if not isinstance(value, list):
        msg = "Expected an array"
        raise NativeError(msg)
    return list(value)


def text(value: object) -> str:
    """Require nonempty non-control text at a request boundary."""
    if (
        not isinstance(value, str)
        or not value
        or any(ord(c) < ASCII_SPACE for c in value)
    ):
        msg = "Expected nonempty literal text"
        raise NativeError(msg)
    return value


def number(value: object) -> float:
    """Require a positive finite duration."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = "Expected finite positive duration"
        raise NativeError(msg)
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        msg = "Expected finite positive duration"
        raise NativeError(msg)
    return result


def operation_failure(value: object) -> dict[str, object]:
    """Accept only fixed failure categories and numeric errno, never messages."""
    failure = record(value)
    errno_value = failure.get("errno")
    if (
        set(failure) != {"category", "code", "errno"}
        or failure["category"] not in ("native", "os", "value", "subprocess")
        or failure["code"] not in (*OPERATION_FAILURES.values(), "unclassified")
        or (
            errno_value is not None
            and (
                type(errno_value) is not int or not 1 <= errno_value <= LINUX_MAX_ERRNO
            )
        )
    ):
        msg = "Invalid delivered operation failure"
        raise NativeError(msg)
    return failure


def _startup_state(state: dict[str, object]) -> None:
    """Accept only complete fixed startup state and bounded numeric identities."""
    if set(state) != {
        "running",
        "paused",
        "restarting",
        "dead",
        "oom_killed",
        "exit_code",
        "pid",
    } or any(
        type(state.get(key)) is not bool
        for key in ("running", "paused", "restarting", "dead", "oom_killed")
    ):
        msg = "Invalid startup state observation"
        raise NativeError(msg)
    for key in ("exit_code", "pid"):
        number_value = state.get(key)
        if type(number_value) is not int or not 0 <= number_value <= MAX_PROCESS_ID:
            msg = "Invalid startup numeric state"
            raise NativeError(msg)


def _startup_roles(processes: dict[str, object]) -> None:
    """Accept only known process roles and numeric identities, never process args."""
    roles = sequence(processes["roles"])
    if len(roles) > STARTUP_PROCESS_LIMIT or (
        processes["status"] == "unavailable" and roles
    ):
        msg = "Invalid startup process count"
        raise NativeError(msg)
    for raw_role in roles:
        role = record(raw_role)
        if (
            set(role) != {"role", "pid", "parent_pid", "uid"}
            or role.get("role") not in STARTUP_ROLES
        ):
            msg = "Invalid startup process role"
            raise NativeError(msg)
        for key in ("pid", "parent_pid", "uid"):
            number_value = role.get(key)
            maximum = MAX_USER_ID if key == "uid" else MAX_PROCESS_ID
            minimum = 1 if key == "pid" else 0
            if type(number_value) is not int or not minimum <= number_value <= maximum:
                msg = "Invalid startup process identity"
                raise NativeError(msg)


def startup_observation(value: object) -> dict[str, object]:
    """Validate the entire privacy-safe startup schema before host persistence.

    Diagnostic process roles and log findings are observations, never authority
    for input or teardown. Unknown and proven-absent containers remain distinct.
    No dynamic text or unrecognized fields may cross this boundary.
    """
    observed = record(value)
    presence = observed.get("container")
    if presence in ("absent", "unknown") and set(observed) == {"container"}:
        return observed
    if presence != "present" or set(observed) != {
        "container",
        "state",
        "logs",
        "processes",
    }:
        msg = "Invalid startup observation"
        raise NativeError(msg)
    _startup_state(record(observed["state"]))
    logs, processes = record(observed["logs"]), record(observed["processes"])
    if set(logs) != {"status", "failure_codes"} or set(processes) != {
        "status",
        "roles",
    }:
        msg = "Invalid startup evidence fields"
        raise NativeError(msg)
    for source in (logs, processes):
        if source.get("status") not in ("complete", "truncated", "unavailable"):
            msg = "Invalid startup evidence availability"
            raise NativeError(msg)
    codes = sequence(logs["failure_codes"])
    if (
        len(codes) > len(STARTUP_FAILURES)
        or any(
            not isinstance(code, str) or code not in STARTUP_FAILURES.values()
            for code in codes
        )
        or len(set(codes)) != len(codes)
        or (logs["status"] == "unavailable" and codes)
    ):
        msg = "Invalid startup failure categories"
        raise NativeError(msg)
    _startup_roles(processes)
    return observed


def _startup_role(
    arguments: list[str], scripts: dict[str, str], executables: dict[str, str]
) -> str | None:
    """Classify only approved executable or exact installed script roles."""
    executable = Path(arguments[0]).name
    role = executables.get(executable)
    if re.fullmatch(r"python(?:3(?:\.12)?)?", executable) and len(arguments) > 1:
        role = scripts.get(arguments[1])
        if len(arguments) > SCRIPT_ACTION_INDEX:
            if arguments[1] == "/opt/gow-full-x86/runtime.py" and arguments[2] in (
                "entrypoint",
                "session",
                "hotkeys",
                "frontend",
            ):
                role = "runtime-" + arguments[2]
            elif arguments[1:3] == [
                "/opt/gow-full-x86/native_diagnostics.py",
                "frontend",
            ]:
                role = "frontend-observer"
    return role


def startup_processes(output: bytes, status: str) -> dict[str, object]:
    """Select only numeric identities and known roles from bounded Docker top."""
    unavailable: dict[str, object] = {"status": "unavailable", "roles": []}
    if status == "unavailable":
        return unavailable
    lines = output.decode("utf-8", errors="replace").splitlines()
    if not lines or lines[0].split() != ["PID", "PPID", "UID", "COMMAND"]:
        return unavailable
    scripts = {
        "/opt/gow-full-x86/input_transport.py": "supervisor",
        "/opt/gow-full-x86/input_worker.py": "input-worker",
        "/opt/gow-full-x86/transport_probe.py": "receiver-probe",
        "/opt/gow-full-x86/emulator_probe.py": "emulator-probe",
        "/usr/bin/emulatorlauncher": "stock-launcher",
    }
    executables = {
        "Xwayland": "xwayland",
        "dbus-daemon": "session-bus",
        "openbox": "window-manager",
        "emulationstation": "emulationstation",
        "emulatorlauncher": "stock-launcher",
        "retroarch": "retroarch",
        "duckstation-qt": "duckstation-qt",
        "xemu": "xemu",
    }
    roles: list[object] = []
    for line in lines[1 : STARTUP_PROCESS_LIMIT + 1]:
        fields = line.split(None, 3)
        if len(fields) != PROCESS_TABLE_COLUMNS or any(
            re.fullmatch(r"[0-9]+", field) is None for field in fields[:3]
        ):
            return unavailable
        arguments = fields[3].split()
        if not arguments:
            return unavailable
        role = _startup_role(arguments, scripts, executables)
        if role is not None:
            roles.append(
                {
                    "role": role,
                    "pid": int(fields[0]),
                    "parent_pid": int(fields[1]),
                    "uid": int(fields[2]),
                }
            )
    return {
        "status": "truncated"
        if status == "truncated" or len(lines) > STARTUP_PROCESS_LIMIT + 1
        else "complete",
        "roles": roles,
    }


def identity(info: os.stat_result) -> list[int]:
    """Pin filesystem identity, including owner/group and file type."""
    return [
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_uid,
        info.st_gid,
    ]


def open_directory(path: Path) -> int:
    """Open every absolute component without following symlinks.

    Returns:
        An owned directory descriptor, which the caller must close.
    """
    if not path.is_absolute() or ".." in path.parts:
        msg = "Expected canonical absolute directory"
        raise NativeError(msg)
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def read_at(
    directory: int,
    name: str,
    maximum: int = 16 * 1024 * 1024,
    *,
    owner: tuple[int, int] | None = None,
) -> bytes:
    """Read a bounded regular file, optionally requiring private owned evidence."""
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            msg = "Evidence is not a bounded regular file"
            raise NativeError(msg)
        if owner is not None and (
            (before.st_uid, before.st_gid) != owner
            or stat.S_IMODE(before.st_mode) != PRIVATE_FILE_MODE
            or before.st_nlink != 1
        ):
            msg = "Evidence is not an exclusively owned private file"
            raise NativeError(msg)
        chunks = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if remaining == 0 or (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            msg = "Evidence changed during read"
            raise NativeError(msg)
        if owner is not None and (
            identity(before) != identity(after)
            or before.st_mode != after.st_mode
            or before.st_nlink != after.st_nlink
            or before.st_ctime_ns != after.st_ctime_ns
            or identity(os.stat(name, dir_fd=directory, follow_symlinks=False))
            != identity(after)
        ):
            msg = "Owned evidence identity changed during read"
            raise NativeError(msg)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def write_at(directory: int, name: str, data: bytes, mode: int = 0o600) -> None:
    """Publish a new regular file exclusively, refusing replacements."""
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
        dir_fd=directory,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def validate_shared_root(
    root: Path,
    local_root: str,
    mounts: list[dict[str, object]],
    local_identity: list[int],
    protected: list[str],
) -> list[int]:
    """Validate actual root backing and protected overlap before any write."""
    descriptor = open_directory(root)
    try:
        info = os.fstat(descriptor)
        pin = identity(info)
        if (info.st_uid != 0 and info.st_uid != os.geteuid()) or info.st_mode & 0o022:
            msg = "Shared state root has unsafe ownership/mode"
            raise NativeError(msg)
    finally:
        os.close(descriptor)
    mapping = [
        m
        for m in mounts
        if m.get("Destination") == local_root
        and m.get("Source") == str(root)
        and m.get("Type") == "bind"
        and m.get("RW") is True
    ]
    if len(mapping) != 1 or local_identity != pin[:2]:
        msg = "Host/local Wolf shared backing is not proven"
        raise NativeError(msg)
    test_parent = root / "test-runs"
    if test_parent.resolve() != test_parent:
        msg = "Owned test-runs parent is symlinked"
        raise NativeError(msg)
    for name in protected:
        path = Path(name)
        if not path.is_absolute() or ".." in path.parts:
            msg = "Protected root is not an absolute literal"
            raise NativeError(msg)
        # Existing authorized content binds may use a host symlink. Resolve only
        # on this Docker host for overlap refusal; never mutate that target.
        canonical = path.resolve()
        if canonical.is_relative_to(test_parent) or test_parent.is_relative_to(
            canonical
        ):
            msg = "Test state overlaps protected state/content"
            raise NativeError(msg)
    return pin


class OwnedState:
    """One exclusively allocated home below a verified shared Wolf root."""

    def __init__(self, root: Path, run_id: str, token: str, uid: int, gid: int) -> None:
        """Bind owned identity and non-root credentials without effects."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{15,95}", run_id):
            msg = "Invalid native run identity"
            raise NativeError(msg)
        self.root, self.run_id, self.token = root, run_id, token
        self.uid, self.gid = uid, gid
        self.path = root / "test-runs" / run_id

    def allocate(self) -> dict[str, object]:
        """Allocate exclusively and remove pinned partial state if setup fails."""
        root = open_directory(self.root)
        try:
            with suppress(FileExistsError):
                os.mkdir("test-runs", 0o711, dir_fd=root)
            parent = os.open(
                "test-runs",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root,
            )
            try:
                parent_info = os.fstat(parent)
                if parent_info.st_uid != os.geteuid() or parent_info.st_mode & 0o022:
                    msg = "Unsafe test-runs parent"
                    raise NativeError(msg)
                home = -1
                allocated = False
                completed = False
                try:
                    os.mkdir(self.run_id, 0o750, dir_fd=parent)
                    allocated = True
                    home = os.open(
                        self.run_id,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=parent,
                    )
                    os.fchown(home, self.uid, self.gid)
                    write_at(home, ".native-owner", self.token.encode())
                    os.mkdir(".native-control", 0o755, dir_fd=home)
                    os.mkdir(".native-evidence", 0o700, dir_fd=home)
                    os.chown(
                        ".native-evidence",
                        self.uid,
                        self.gid,
                        dir_fd=home,
                        follow_symlinks=False,
                    )
                    result: dict[str, object] = {
                        "root": identity(os.fstat(root)),
                        "parent": identity(parent_info),
                        "home": identity(os.fstat(home)),
                        "control": identity(
                            os.stat(
                                ".native-control", dir_fd=home, follow_symlinks=False
                            )
                        ),
                        "evidence": identity(
                            os.stat(
                                ".native-evidence", dir_fd=home, follow_symlinks=False
                            )
                        ),
                        "marker": identity(
                            os.stat(".native-owner", dir_fd=home, follow_symlinks=False)
                        ),
                    }
                    completed = True
                    return result
                finally:
                    try:
                        if allocated and not completed:
                            if home < 0:
                                os.rmdir(self.run_id, dir_fd=parent)
                            elif identity(
                                os.stat(
                                    self.run_id, dir_fd=parent, follow_symlinks=False
                                )
                            ) == identity(os.fstat(home)):
                                shutil.rmtree(self.run_id, dir_fd=parent)
                            else:
                                msg = (
                                    "Partial native state identity changed "
                                    "before cleanup"
                                )
                                raise NativeError(msg)
                    finally:
                        if home >= 0:
                            os.close(home)
            finally:
                os.close(parent)
        finally:
            os.close(root)

    def _check_marker(self, home: int, pin: dict[str, object]) -> None:
        """Check the pinned home and private owner marker through one live fd."""
        if identity(os.fstat(home)) != pin.get("home"):
            msg = "Home changed while validating marker"
            raise NativeError(msg)
        if (
            identity(os.stat(".native-owner", dir_fd=home, follow_symlinks=False))
            != pin.get("marker")
            or read_at(home, ".native-owner", 4096) != self.token.encode()
        ):
            msg = "Native state marker changed"
            raise NativeError(msg)

    def checked(self, pin: dict[str, object]) -> int:
        """Revalidate the complete pinned path and ownership marker."""
        paths = (
            (self.root, "root"),
            (self.path.parent, "parent"),
            (self.path, "home"),
            (self.path / ".native-control", "control"),
            (self.path / ".native-evidence", "evidence"),
        )
        for path, key in paths:
            descriptor = open_directory(path)
            try:
                if identity(os.fstat(descriptor)) != pin.get(key):
                    raise NativeError("Native state identity changed: " + key)
            finally:
                os.close(descriptor)
        home = open_directory(self.path)
        try:
            self._check_marker(home, pin)
        except BaseException:
            os.close(home)
            raise
        return home

    def remove(self, pin: dict[str, object]) -> None:
        """Remove pinned state only after the caller has proved native absence."""
        for line in (
            Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        ):
            fields = line.split()
            if len(fields) < MOUNTINFO_PREFIX_FIELDS:
                msg = "Cannot qualify cleanup mount boundaries"
                raise NativeError(msg)
            name = re.sub(
                r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4]
            )
            if Path(name).is_relative_to(self.path):
                msg = "Nested mount forbids recursive state removal"
                raise NativeError(msg)
        descriptor = self.checked(pin)
        os.close(descriptor)
        parent = open_directory(self.path.parent)
        try:
            if identity(os.fstat(parent)) != pin.get("parent"):
                msg = "Parent changed before removal"
                raise NativeError(msg)
            if identity(
                os.stat(self.run_id, dir_fd=parent, follow_symlinks=False)
            ) != pin.get("home"):
                msg = "Home replaced before removal"
                raise NativeError(msg)
            if not shutil.rmtree.avoids_symlink_attacks:
                msg = "Platform lacks descriptor-safe recursive removal"
                raise NativeError(msg)
            shutil.rmtree(self.run_id, dir_fd=parent)
        finally:
            os.close(parent)


class Operations:
    """Bounded Docker/API inspection and effects for one configured target."""

    def __init__(self, request: dict[str, object]) -> None:
        """Borrow one private request and establish its finite operation deadline."""
        self.request = request
        self.deadline = time.monotonic() + number(request.get("timeout"))
        self.wolf = text(request.get("wolf_container"))
        self.socket = text(request.get("api_socket"))

    def remaining(self) -> float:
        """Return the invocation's remaining finite call budget."""
        result = self.deadline - time.monotonic()
        if result <= 0:
            msg = "Remote operation deadline expired"
            raise NativeError(msg)
        return result

    def _command_result(
        self, argv: list[str], data: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Retain bounded output privately for exact operation-specific admission."""
        try:
            completed = subprocess.run(  # noqa: S603 - checked argv boundary; no shell and arbitrary stderr is discarded.
                argv,
                input=data,
                text=True,
                capture_output=True,
                timeout=self.remaining(),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            msg = "Bounded external operation unavailable or timed out"
            raise NativeError(msg) from error
        if len(completed.stdout) > 24 * 1024 * 1024:
            msg = "External response exceeded limit"
            raise NativeError(msg)
        return completed

    def command(self, argv: list[str], data: str | None = None) -> str:
        """Execute argv without a shell and never expose arbitrary stderr."""
        completed = self._command_result(argv, data)
        if completed.returncode:
            raise NativeError("External operation failed: " + argv[0])
        return completed.stdout

    def docker(self, *args: str) -> str:
        """Use root Docker privileges inherited from the authorized SSH entry."""
        return self.command(["docker", *args])

    def api(
        self, endpoint: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Keep private API payloads solely in memory and stdin."""
        argv = [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            str(self.remaining()),
            "--unix-socket",
            self.socket,
            "http://localhost/api/v1/" + endpoint,
        ]
        if payload is not None:
            argv.extend(
                ["--header", "Content-Type: application/json", "--data-binary", "@-"]
            )
        value = record(
            json.loads(
                self.command(argv, json.dumps(payload) if payload is not None else None)
            )
        )
        if value.get("success") is not True:
            raise NativeError("API did not confirm success: " + endpoint)
        return value

    def inspect_all(self) -> list[dict[str, object]]:
        """Require every listed row, except conclusively absent bound owned state."""
        ids = self.docker("ps", "-aq", "--no-trunc").split()
        if len(set(ids)) != len(ids) or any(
            re.fullmatch(r"[0-9a-f]{64}", identifier) is None for identifier in ids
        ):
            msg = "Incomplete Docker container listing"
            raise NativeError(msg)
        if not ids:
            return []
        completed = self._command_result(["docker", "inspect", *ids])
        expected = self.request.get("container_id")
        missing = completed.returncode != 0
        if missing:
            if (
                completed.returncode != 1
                or not isinstance(expected, str)
                or expected not in ids
                or self.request.get("startup_resolved") is not True
                or completed.stderr.splitlines()
                != ["Error: No such object: " + expected]
            ):
                msg = "External operation failed: docker"
                raise NativeError(msg)
            # The host only binds this ID after independent owner/image/home
            # discovery. Revalidate its pinned home/marker before using absence.
            home = self.state().checked(record(self.request.get("pin")))
            os.close(home)
        containers = [record(v) for v in sequence(json.loads(completed.stdout))]
        observed = [text(container.get("Id")) for container in containers]
        wanted = set(ids) - ({expected} if missing else set())
        if len(set(observed)) != len(observed) or set(observed) != wanted:
            msg = "Incomplete Docker container inspection"
            raise NativeError(msg)
        if missing and self.exact_container_present(text(expected)):
            msg = "Owned container absence was not confirmed"
            raise NativeError(msg)
        return containers

    def _read_startup_pipe(
        self, child: subprocess.Popen[bytes], max_lines: int
    ) -> tuple[bytes, str]:
        """Read one live pipe with finite byte, line and operation time bounds."""
        if child.stdout is None:
            msg = "Startup observation pipe unavailable"
            raise NativeError(msg)
        descriptor = child.stdout.fileno()
        os.set_blocking(descriptor, False)
        output = bytearray()
        line_count = 0
        while True:
            if not select.select([descriptor], [], [], self.remaining())[0]:
                return b"", "unavailable"
            data = os.read(
                descriptor, min(4096, STARTUP_OUTPUT_BYTES + 1 - len(output))
            )
            if not data:
                break
            output.extend(data)
            line_count += data.count(b"\n")
            if line_count > max_lines:
                return (
                    b"".join(output.splitlines(keepends=True)[:max_lines]),
                    "truncated",
                )
            if len(output) > STARTUP_OUTPUT_BYTES:
                return bytes(output[:STARTUP_OUTPUT_BYTES]), "truncated"
        if child.wait(timeout=self.remaining()):
            return b"", "unavailable"
        return bytes(output), "complete"

    def bounded_startup_output(
        self, *args: str, max_lines: int = 64
    ) -> tuple[bytes, str]:
        """Read bounded bytes/lines without persisting raw logs or process args."""
        child = None
        try:
            self.remaining()
            child = subprocess.Popen(  # noqa: S603 - maintained read-only Docker argv; never a shell.
                ["docker", *args],  # noqa: S607 - installed target Docker binary.
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            return self._read_startup_pipe(child, max_lines)
        except (NativeError, OSError, subprocess.SubprocessError):
            return b"", "unavailable"
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                # Independent bounded reaping also runs after the observation's
                # own deadline. No helper child may inherit an unbounded wait.
                child.wait(timeout=1)
                if child.stdout is not None:
                    child.stdout.close()

    def observe_startup(self) -> dict[str, object]:
        """Attribute missing startup only to revalidated owned-container evidence."""
        try:
            container = self.owned_container(allow_absent=True)
        except (NativeError, OSError, ValueError):
            return {"container": "unknown"}
        if not container:
            return {"container": "absent"}
        state = record(container.get("State"))
        state_observation = {
            key: state.get(source)
            for key, source in (
                ("running", "Running"),
                ("paused", "Paused"),
                ("restarting", "Restarting"),
                ("dead", "Dead"),
                ("oom_killed", "OOMKilled"),
                ("exit_code", "ExitCode"),
                ("pid", "Pid"),
            )
        }
        identifier = text(container.get("Id"))
        raw_logs, log_status = self.bounded_startup_output(
            "logs", "--tail", "64", identifier
        )
        # Only complete exact lines qualify. A truncated final line cannot
        # fabricate a fatal message by losing its private suffix.
        lines = raw_logs.splitlines()
        if raw_logs and not raw_logs.endswith((b"\n", b"\r")):
            lines = lines[:-1]
        codes = sorted(
            {
                STARTUP_FAILURES[line]
                for raw_line in lines[:64]
                if (line := raw_line.decode("utf-8", errors="replace"))
                in STARTUP_FAILURES
            }
        )
        raw_processes, process_status = self.bounded_startup_output(
            "top", identifier, "-eo", "pid,ppid,uid,args", max_lines=65
        )
        return startup_observation(
            {
                "container": "present",
                "state": state_observation,
                "logs": {"status": log_status, "failure_codes": codes},
                "processes": startup_processes(raw_processes, process_status),
            }
        )

    def state(self) -> OwnedState:
        """Construct only the explicitly selected disposable state capability."""
        uid, gid = self.request.get("uid"), self.request.get("gid")
        if type(uid) is not int or type(gid) is not int or uid <= 0 or gid <= 0:
            msg = "Non-root app UID/GID required"
            raise NativeError(msg)
        return OwnedState(
            Path(text(self.request.get("host_root"))),
            text(self.request.get("case_id")),
            text(self.request.get("token")),
            uid,
            gid,
        )

    def exact_container_present(self, expected: str) -> bool:
        """Query all Docker states for one complete ID, never a prefix or name."""
        if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            msg = "Complete owned container ID required"
            raise NativeError(msg)
        observed = self.docker("ps", "-aq", "--no-trunc", "--filter", "id=" + expected)
        if observed == "":
            return False
        if observed not in (expected, expected + "\n"):
            msg = "Incomplete exact container presence observation"
            raise NativeError(msg)
        return True

    def owned_container(self, *, allow_absent: bool = False) -> dict[str, object]:
        """Revalidate exact Docker ID, image, marker and native home before effects."""
        expected = text(self.request.get("container_id"))
        if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            msg = "Complete owned container ID required"
            raise NativeError(msg)
        if allow_absent and not self.exact_container_present(expected):
            return {}
        try:
            observed = self.docker("inspect", expected)
        except NativeError:
            if allow_absent and not self.exact_container_present(expected):
                return {}
            raise
        containers = [record(v) for v in sequence(json.loads(observed))]
        if len(containers) != 1 or containers[0].get("Id") != expected:
            msg = "Owned container is absent or ambiguous"
            raise NativeError(msg)
        container = containers[0]
        config = record(container.get("Config"))
        labels = record(config.get("Labels") or {})
        mounts = [record(v) for v in sequence(container.get("Mounts"))]
        homes = [
            v
            for v in mounts
            if str(v.get("Destination", "")).rstrip("/") == "/home/retro"
        ]
        if (
            container.get("Image") != self.request.get("image")
            or labels.get("io.gow.integration.owner") != self.request.get("token")
            or len(homes) != 1
            or homes[0].get("Source") != str(self.state().path)
        ):
            msg = "Owned container identity mismatch"
            raise NativeError(msg)
        return container

    def snapshot(self) -> dict[str, object]:
        """Return minimal discovery fields, never raw session/config/env records."""
        sessions = sequence(self.api("sessions").get("sessions"))
        lobbies = [record(v) for v in sequence(self.api("lobbies").get("lobbies"))]
        selected = []
        for lobby in lobbies:
            runner = record(lobby.get("runner"))
            # Runner contains only suite-selected values when owned. Return a digest
            # for comparison, not private env or the PIN.
            selected.append(
                {
                    "id": text(lobby.get("id")),
                    "name": text(lobby.get("name")),
                    "profile": text(lobby.get("started_by_profile_id")),
                    "pin_required": lobby.get("pin_required"),
                    "connected": len(sequence(lobby.get("connected_sessions"))),
                    "runner_hash": hashlib.sha256(
                        json.dumps(
                            runner, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                }
            )
        containers = []
        for container in self.inspect_all():
            config = record(container.get("Config"))
            state = record(container.get("State"))
            mounts = [record(v) for v in sequence(container.get("Mounts"))]
            labels = record(config.get("Labels") or {})
            containers.append(
                {
                    "id": text(container.get("Id")),
                    "name": text(container.get("Name")),
                    "image": text(container.get("Image")),
                    "running": state.get("Running"),
                    "paused": state.get("Paused"),
                    "status": state.get("Status"),
                    "owner": labels.get("io.gow.integration.owner"),
                    "home": [
                        m.get("Source")
                        for m in mounts
                        if str(m.get("Destination", "")).rstrip("/") == "/home/retro"
                    ],
                    "native": any(
                        str(m.get("Destination", "")).rstrip("/")
                        in ("/home/retro", "/run/udev")
                        for m in mounts
                    )
                    or bool(
                        re.search(
                            r"_(?:[0-9]+|[0-9a-fA-F-]{36})$",
                            str(container.get("Name", "")),
                        )
                    ),
                }
            )
        return {
            "session_count": len(sessions),
            "lobbies": selected,
            "containers": containers,
        }

    def docker_inspect_runtime(self) -> dict[str, object]:
        """Execute packaged read-only inspection, never an app/probe launcher."""
        argv = [
            "docker",
            "exec",
            "-i",
            text(self.request.get("container_id")),
            "/usr/bin/python3",
            "-B",
            "/opt/gow-full-x86/native_checks.py",
            "inspect",
        ]
        data = self.command(
            argv,
            json.dumps(
                {
                    "hashes": self.request.get("hashes"),
                    "uid": self.request.get("uid"),
                    "gid": self.request.get("gid"),
                }
            ),
        )
        response = record(json.loads(data))
        if response.get("ok") is not True:
            raise InspectionError(record(response.get("inspection_failure")))
        return record(response.get("result"))

    def verified_image(self) -> dict[str, object]:
        """Validate immutable image labels and startup commands before use."""
        images = sequence(
            json.loads(self.docker("image", "inspect", text(self.request.get("image"))))
        )
        if len(images) != 1:
            msg = "Exact local image unavailable"
            raise NativeError(msg)
        image = record(images[0])
        config = record(image.get("Config"))
        labels = record(config.get("Labels") or {})
        if (
            image.get("Id") != self.request.get("image")
            or labels.get("org.opencontainers.image.revision")
            != self.request.get("source")
            or labels.get("io.gow.full-x86.input.sha256")
            != self.request.get("stock_sha256")
            or labels.get("org.opencontainers.image.version") != "43.1"
            or labels.get("io.gow.full-x86.experimental") != "true"
        ):
            msg = "Image/source/stock provenance mismatch"
            raise NativeError(msg)
        entry = [
            "/usr/bin/python3",
            "/opt/gow-full-x86/input_transport.py",
            "--",
            "/opt/gow-full-x86/entrypoint.sh",
        ]
        if config.get("Entrypoint") != entry or config.get("Cmd") != [
            "/opt/gow-full-x86/frontend.sh"
        ]:
            msg = "Packaged supervisor/default frontend ancestry mismatch"
            raise NativeError(msg)
        selected_source = text(self.request.get("source"))
        source_kind = (
            "worktree" if selected_source.startswith("worktree-sha256:") else "git"
        )
        if labels.get("io.gow.full-x86.source.kind") != source_kind or (
            source_kind == "worktree"
            and labels.get("io.gow.full-x86.source.sha256")
            != selected_source.removeprefix("worktree-sha256:")
        ):
            msg = "Image source-kind identity is inconsistent"
            raise NativeError(msg)
        return image

    def _runtime_mounts(
        self, env: dict[str, str], mounts: list[dict[str, object]]
    ) -> tuple[Path, Path, dict[str, object] | None]:
        """Resolve installed socket backing and optional GPU driver volume."""
        local_runtime = Path(env.get("XDG_RUNTIME_DIR", "/tmp/sockets"))  # noqa: S108 - stock Wolf socket mount contract, never a temporary file publication.
        if not local_runtime.is_absolute() or ".." in local_runtime.parts:
            msg = "Native runtime socket root is not absolute/literal"
            raise NativeError(msg)
        candidates = [
            m
            for m in mounts
            if m.get("Type") == "bind"
            and local_runtime.is_relative_to(Path(text(m.get("Destination"))))
        ]
        if not candidates:
            msg = "Native runtime socket backing is unknown"
            raise NativeError(msg)
        runtime_mount = max(
            candidates, key=lambda m: len(Path(text(m.get("Destination"))).parts)
        )
        host_runtime = (
            Path(text(runtime_mount.get("Source")))
            / local_runtime.relative_to(Path(text(runtime_mount.get("Destination"))))
        ).resolve(strict=True)
        runtime_fd = open_directory(host_runtime)
        os.close(runtime_fd)
        driver_mount: dict[str, object] | None = None
        if env.get("NVIDIA_DRIVER_VOLUME_NAME"):
            volume = record(
                sequence(
                    json.loads(
                        self.docker(
                            "volume", "inspect", env["NVIDIA_DRIVER_VOLUME_NAME"]
                        )
                    )
                )[0]
            )
            driver_mount = {
                "name": env["NVIDIA_DRIVER_VOLUME_NAME"],
                "source": text(volume.get("Mountpoint")),
            }
        return local_runtime, host_runtime, driver_mount

    @staticmethod
    def _native_device_rules() -> list[str]:
        """Read effective kernel character-device majors required by native input."""
        majors: dict[str, int] = {}
        for line in Path("/proc/devices").read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) == DEVICE_TABLE_COLUMNS and fields[0].isdecimal():
                majors[fields[1]] = int(fields[0])
        if majors.get("input") != INPUT_DEVICE_MAJOR or "hidraw" not in majors:
            msg = "Native input/hidraw cgroup capabilities are incomplete"
            raise NativeError(msg)
        return ["c 13:* rwm", "c " + str(majors["hidraw"]) + ":* rwm"]

    def preflight(self) -> dict[str, object]:
        """Inspect installed roots and exact already-local packaged image."""
        wolf_values = sequence(json.loads(self.docker("inspect", self.wolf)))
        if len(wolf_values) != 1:
            msg = "Expected one Wolf container"
            raise NativeError(msg)
        wolf = record(wolf_values[0])
        environment = sequence(record(wolf.get("Config")).get("Env"))
        env = dict(text(v).split("=", 1) for v in environment if "=" in text(v))
        host_root = Path(text(self.request.get("host_root")))
        local_root = text(self.request.get("local_root"))
        # HOST_APPS_STATE_FOLDER is Wolf's local/container root. Wolf derives
        # the Docker-host root through its own container mount introspection.
        if env.get("HOST_APPS_STATE_FOLDER", "/etc/wolf") != local_root:
            msg = "Configured Wolf local state root disagrees with request"
            raise NativeError(msg)
        content_roots = record(self.request.get("content_roots"))
        for key in ("roms", "bios"):
            if not Path(text(content_roots.get(key))).resolve(strict=True).is_dir():
                msg = "Authorized content source is not a directory"
                raise NativeError(msg)
        render_node = Path(text(self.request.get("render_node")))
        if not stat.S_ISCHR(render_node.stat().st_mode):
            msg = "Selected native render node is not available"
            raise NativeError(msg)
        mounts = [record(v) for v in sequence(wolf.get("Mounts"))]
        local_stat = [
            int(v)
            for v in self.docker(
                "exec", text(wolf.get("Id")), "stat", "-Lc", "%d %i", local_root
            ).split()
        ]
        root_pin = validate_shared_root(
            host_root,
            local_root,
            mounts,
            local_stat,
            [text(v) for v in sequence(self.request.get("protected"))],
        )
        wolf_image = record(
            sequence(
                json.loads(self.docker("image", "inspect", text(wolf.get("Image"))))
            )[0]
        )
        wolf_revision = record(
            record(wolf_image.get("Config")).get("Labels") or {}
        ).get("org.opencontainers.image.revision")
        if (
            # pragma: allowlist nextline secret
            wolf_revision != "ee271038da2b81c9e54c28c9daa7558692d415d6"
            or record(wolf.get("State")).get("Running") is not True
        ):
            msg = "Installed Wolf lifecycle/API revision is not qualified"
            raise NativeError(msg)
        profiles = [record(v) for v in sequence(self.api("profiles").get("profiles"))]
        if (
            len([p for p in profiles if p.get("id") == self.request.get("profile")])
            != 1
        ):
            msg = "Expected existing profile is unavailable"
            raise NativeError(msg)
        image = (
            {"Id": None}
            if self.request.get("prepare_image") is True
            else self.verified_image()
        )
        local_runtime, host_runtime, driver_mount = self._runtime_mounts(env, mounts)
        device_rules = self._native_device_rules()
        return {
            "wolf_id": text(wolf.get("Id")),
            "wolf_revision": wolf_revision,
            "root_pin": root_pin,
            "runtime_local": str(local_runtime),
            "runtime_host": str(host_runtime),
            "driver_mount": driver_mount,
            "device_rules": device_rules,
            "stop_container_on_exit": env.get("WOLF_STOP_CONTAINER_ON_EXIT") == "TRUE",
            "image": image.get("Id"),
            "source": self.request.get("source"),
            "stock_sha256": self.request.get("stock_sha256"),
            "snapshot": self.snapshot(),
            "automatic_pull_race": (
                "Exact local image exists now; concurrent external removal can "
                "still trigger stock Wolf's automatic pull fallback."
            ),
        }

    def image_status(self) -> dict[str, object]:
        """Inspect immutable remote image availability without loading or pulling."""
        wanted = text(self.request.get("image"))
        available = self.docker("image", "ls", "--quiet", "--no-trunc").split()
        if wanted not in available:
            return {"present": False}
        return {"present": True, "image": self.verified_image().get("Id")}

    def allocate(self, state: OwnedState) -> dict[str, object]:
        """Allocate only beneath the previously pinned authorized shared root."""
        descriptor = open_directory(state.root)
        try:
            if identity(os.fstat(descriptor)) != self.request.get("root_pin"):
                msg = "Shared root identity changed before allocation"
                raise NativeError(msg)
        finally:
            os.close(descriptor)
        return {"pin": state.allocate()}

    def transfer_image(
        self, state: OwnedState, pin: dict[str, object]
    ) -> dict[str, object]:
        """Transfer bounded owned bytes or verify and load the image archive."""
        action = text(self.request.get("action"))
        home = state.checked(pin)
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            offset = self.request.get("offset")
            if type(offset) is not int or offset < 0 or offset > 32 * 1024**3:
                msg = "Invalid bounded image transfer offset"
                raise NativeError(msg)
            if action == "image_chunk" and offset == 0:
                flags |= os.O_CREAT | os.O_EXCL
            descriptor = os.open(".native-image.tar", flags, 0o600, dir_fd=home)
            with os.fdopen(descriptor, "r+b") as archive:
                info = os.fstat(archive.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or info.st_nlink != 1
                    or info.st_size != offset
                ):
                    msg = "Owned image transfer identity changed"
                    raise NativeError(msg)
                if action == "image_chunk":
                    data = base64.b64decode(
                        text(self.request.get("data")), validate=True
                    )
                    if (
                        not data
                        or len(data) > IMAGE_CHUNK_BYTES
                        or offset + len(data) > 32 * 1024**3
                    ):
                        msg = "Image transfer exceeded bounded storage"
                        raise NativeError(msg)
                    archive.seek(offset)
                    archive.write(data)
                    archive.flush()
                    os.fsync(archive.fileno())
                    return {"offset": archive.tell()}
                expected = text(self.request.get("sha256"))
                if hashlib.file_digest(archive, "sha256").hexdigest() != expected:
                    msg = "Transferred image archive integrity mismatch"
                    raise NativeError(msg)
                archive.seek(0)
                completed = subprocess.run(
                    ["docker", "image", "load"],  # noqa: S607 - installed Docker binary; immutable archive is supplied on stdin.
                    stdin=archive,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=self.remaining(),
                    check=False,
                )
                if completed.returncode:
                    msg = "Bounded image load failed"
                    raise NativeError(msg)
                return {"image": self.verified_image().get("Id")}
        finally:
            os.close(home)

    def create_lobby(
        self, state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Create exactly the lobby whose payload names this disposable state."""
        payload = record(self.request.get("payload"))
        if (
            payload.get("runner_state_folder") != "test-runs/" + state.run_id
            or payload.get("name") != state.run_id
            or payload.get("profile_id") != self.request.get("profile")
        ):
            msg = "Create request does not match owned state"
            raise NativeError(msg)
        return self.api("lobbies/create", payload)

    def inspect_container(
        self, _state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Inspect the owned container and canonicalize actual bind sources."""
        container = self.owned_container()
        roots = record(self.request.get("content_roots"))
        canonical_roots: dict[str, object] = {}
        for key in ("roms", "bios"):
            canonical = Path(text(roots.get(key))).resolve(strict=True)
            if not canonical.is_dir():
                msg = "Authorized content source is not a directory"
                raise NativeError(msg)
            canonical_roots[key] = str(canonical)
        observed_mounts = [record(v) for v in sequence(container.get("Mounts"))]
        for mount in observed_mounts:
            if mount.get("Type") == "bind":
                mount["Source"] = str(
                    Path(text(mount.get("Source"))).resolve(strict=True)
                )
        container["Mounts"] = observed_mounts
        return {"container": container, "content_roots": canonical_roots}

    def inspect_integrity(
        self, _state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Invoke the checked installed read-only integrity inspector."""
        self.owned_container()
        return self.docker_inspect_runtime()

    def seed_selection(
        self, state: OwnedState, pin: dict[str, object]
    ) -> dict[str, object]:
        """Seed one bounded private replay record for the exact selected case."""
        container = self.owned_container()
        environment = sequence(record(container.get("Config")).get("Env"))
        selected = [
            text(setting).removeprefix("GOW_EMULATOR_CASE=")
            for setting in environment
            if text(setting).startswith("GOW_EMULATOR_CASE=")
        ]
        system = text(self.request.get("system"))
        value = record(self.request.get("selection"))
        data = json.dumps(value, sort_keys=True).encode("utf-8")
        if (
            value.get("schema") != 1
            or len(selected) != 1
            or not selected[0].startswith(system + "-")
            or not state.run_id.endswith("-" + selected[0])
            or value.get("system") != system
            or len(data) > 1024 * 1024
        ):
            msg = "Invalid bounded selected-case reproduction record"
            raise NativeError(msg)
        control = open_directory(state.path / ".native-control")
        try:
            if identity(os.fstat(control)) != pin.get("control"):
                msg = "Control identity changed before reproduction seed"
                raise NativeError(msg)
            write_at(control, "selection.json", data)
            os.chown(
                "selection.json",
                state.uid,
                state.gid,
                dir_fd=control,
                follow_symlinks=False,
            )
        finally:
            os.close(control)
        return {"seeded": True}

    def verify_qualified(
        self, state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Recheck the qualified case through the checked installed reader."""
        container = self.owned_container()
        expected = record(self.request.get("expected"))
        case = text(expected.get("case"))
        environment = sequence(record(container.get("Config")).get("Env"))
        if (
            not state.run_id.endswith("-" + case)
            or "GOW_EMULATOR_CASE=" + case not in environment
            or expected.get("backend") not in ("libretro", "duckstation", "xemu")
        ):
            msg = "Qualified case does not match owned native session"
            raise NativeError(msg)
        actor = str(state.uid) + ":" + str(state.gid)
        prefix = [
            "docker",
            "exec",
            "-i",
            "--user",
            actor,
            text(self.request.get("container_id")),
            "/usr/bin/python3",
            "-B",
        ]
        response = record(
            json.loads(
                self.command(
                    [*prefix, "/opt/gow-full-x86/native_checks.py", "qualified"],
                    json.dumps(expected),
                )
            )
        )
        return {"matched": response.get("matched") is True}

    def update_lease(
        self, state: OwnedState, pin: dict[str, object]
    ) -> dict[str, object]:
        """Publish or revoke only the pinned owned control lease."""
        action = text(self.request.get("action"))
        if action == "lease":
            self.owned_container()
        control = open_directory(state.path / ".native-control")
        try:
            if identity(os.fstat(control)) != pin.get("control"):
                msg = "Control directory changed before lease update"
                raise NativeError(msg)
            if action == "revoke":
                with suppress(FileNotFoundError):
                    os.unlink("lease", dir_fd=control)
            else:
                data = json.dumps(
                    {
                        "expires": time.monotonic()
                        + number(self.request.get("lease_seconds"))
                    }
                ).encode()
                write_at(control, "lease-next", data, 0o644)
                os.replace(
                    "lease-next", "lease", src_dir_fd=control, dst_dir_fd=control
                )
        finally:
            os.close(control)
        return {"confirmed": True}

    def collect_evidence(
        self, state: OwnedState, pin: dict[str, object]
    ) -> dict[str, object]:
        """Read independently completed allowlisted owned evidence files."""
        evidence = open_directory(state.path / ".native-evidence")
        files: dict[str, object] = {}
        try:
            info = os.fstat(evidence)
            if identity(info) != pin.get("evidence"):
                msg = "Evidence directory changed before collection"
                raise NativeError(msg)
            selected = [text(name) for name in sequence(self.request.get("files"))]
            if any(name not in SELECTED_EVIDENCE for name in selected):
                msg = "Invalid selected evidence name"
                raise NativeError(msg)
            unavailable: list[str] = []
            # Final names are exclusive atomic publications. A final report
            # is not a completion barrier for independently completed files.
            for name in selected:
                try:
                    data = read_at(
                        evidence,
                        name,
                        owner=(info.st_uid, info.st_gid),
                    )
                except FileNotFoundError:
                    continue
                except (NativeError, OSError, ValueError):
                    unavailable.append(name)
                    continue
                files[name] = base64.b64encode(data).decode("ascii")
        finally:
            os.close(evidence)
        result: dict[str, object] = {"files": files, "unavailable": unavailable}
        if ("startup.json" in selected and "startup.json" not in files) or (
            self.request.get("observe_incomplete") is True
            and not any(
                name.endswith("-probe.json") and name in files for name in selected
            )
        ):
            result["startup_observation"] = self.observe_startup()
        return result

    def stop_lobby(
        self, _state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Stop only the exact observed lobby identity."""
        wanted = text(self.request.get("lobby_id"))
        matches = [
            v
            for v in sequence(self.snapshot().get("lobbies"))
            if record(v).get("id") == wanted
        ]
        if not matches:
            return {"already_absent": True}
        if (
            len(matches) != 1
            or record(matches[0]).get("runner_hash") != self.request.get("runner_hash")
            or record(matches[0]).get("name") != self.request.get("case_id")
            or record(matches[0]).get("profile") != self.request.get("profile")
        ):
            msg = "Lobby identity changed before stop"
            raise NativeError(msg)
        return self.api(
            "lobbies/stop",
            {"lobby_id": wanted, "pin": self.request.get("lobby_pin")},
        )

    def stop_container(
        self, _state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Stop the exact owned container and resolve concurrent absence."""
        if not self.owned_container(allow_absent=True):
            return {"already_absent": True}
        try:
            self.docker("stop", "--time", "3", text(self.request.get("container_id")))
        except NativeError:
            if self.exact_container_present(text(self.request.get("container_id"))):
                raise
            return {"already_absent": True}
        return {"confirmed": True}

    def remove_container(
        self, _state: OwnedState, _pin: dict[str, object]
    ) -> dict[str, object]:
        """Remove only a proven stopped owned container."""
        container = self.owned_container(allow_absent=True)
        if not container:
            return {"already_absent": True}
        status = record(container.get("State"))
        if status.get("Running") is not False or status.get("Paused") is not False:
            msg = "Refusing to remove a running or unknown container"
            raise NativeError(msg)
        try:
            self.docker("rm", text(self.request.get("container_id")))
        except NativeError:
            if self.exact_container_present(text(self.request.get("container_id"))):
                raise
            return {"already_absent": True}
        return {"confirmed": True}

    def remove_state(
        self, state: OwnedState, pin: dict[str, object]
    ) -> dict[str, object]:
        """Remove pinned state only after independent process/lobby absence proof."""
        if self.request.get("startup_resolved") is not True:
            msg = "Unresolved startup forbids state removal"
            raise NativeError(msg)
        snapshot = self.snapshot()
        for container_value in sequence(snapshot.get("containers")):
            container = record(container_value)
            if container.get("owner") == self.request.get("token") or str(
                state.path
            ) in sequence(container.get("home")):
                msg = "Container may still use disposable state"
                raise NativeError(msg)
        for lobby_value in sequence(snapshot.get("lobbies")):
            lobby = record(lobby_value)
            if lobby.get("name") == self.request.get("case_id") or lobby.get(
                "runner_hash"
            ) == self.request.get("runner_hash"):
                msg = "Lobby may still use disposable state"
                raise NativeError(msg)
        state.remove(pin)
        return {"removed": True}

    def dispatch(self) -> dict[str, object]:
        """Validate shared ownership once before dispatching a checked operation."""
        action = text(self.request.get("action"))
        readonly = {
            "preflight": self.preflight,
            "snapshot": self.snapshot,
            "image_status": self.image_status,
        }
        if action in readonly:
            return readonly[action]()
        state = self.state()
        if action == "allocate":
            return self.allocate(state)
        pin = record(self.request.get("pin"))
        home = state.checked(pin)
        os.close(home)
        handlers = {
            "image_chunk": self.transfer_image,
            "image_load": self.transfer_image,
            "create": self.create_lobby,
            "inspect": self.inspect_container,
            "integrity": self.inspect_integrity,
            "seed_selection": self.seed_selection,
            "verify_qualified": self.verify_qualified,
            "lease": self.update_lease,
            "revoke": self.update_lease,
            "collect": self.collect_evidence,
            "stop_lobby": self.stop_lobby,
            "stop_container": self.stop_container,
            "remove_container": self.remove_container,
            "remove_state": self.remove_state,
        }
        handler = handlers.get(action)
        if handler is None:
            msg = "Unknown native operation"
            raise NativeError(msg)
        return handler(state, pin)


def main() -> int:
    """Accept one private JSON request and emit one bounded public response."""

    def expired(_signum: int, _frame: object) -> None:
        msg = "Native operation deadline expired"
        raise NativeError(msg)

    try:
        request = record(json.load(sys.stdin))
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, number(request.get("timeout")))
        response = Operations(request).dispatch()
        json.dump({"ok": True, "result": response}, sys.stdout)
    except InspectionError as error:
        json.dump(
            {"ok": False, "inspection_failure": error.failure},
            sys.stdout,
        )
        return 1
    except (NativeError, OSError, ValueError, subprocess.SubprocessError) as error:
        # Do not serialize arbitrary Docker/API/configuration exception payloads.
        json.dump(
            {
                "ok": False,
                "operation_failure": {
                    "category": (
                        "native"
                        if isinstance(error, NativeError)
                        else "os"
                        if isinstance(error, OSError)
                        else "subprocess"
                        if isinstance(error, subprocess.SubprocessError)
                        else "value"
                    ),
                    "code": OPERATION_FAILURES.get(str(error), "unclassified"),
                    "errno": (
                        error.errno
                        if isinstance(error, OSError)
                        and type(error.errno) is int
                        and 1 <= error.errno <= LINUX_MAX_ERRNO
                        else None
                    ),
                },
                "error": (
                    "Native operation failed closed; inspect the reported phase "
                    "and owned identities."
                ),
            },
            sys.stdout,
        )
        return 1
    else:
        return 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
