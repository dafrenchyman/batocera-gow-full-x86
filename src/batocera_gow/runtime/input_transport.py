"""Disposable input-transport supervisor; never substitutes Batocera mappings."""

import array
import ctypes
import errno
import fcntl
import json
import os
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack, suppress
from pathlib import Path
from types import FrameType, TracebackType
from typing import Protocol

from .resources import RUNTIME_ROOT
from .udev_input import UdevPublisher

MAX_COMMAND_BYTES = 4096
MAX_PIDFILE_BYTES = 32
UID_LIMIT = 4294967295
MUTATE_IOCTL_BUFFER = True


STATUS = Path("/run/gow-full-x86-input-transport.json")
UI_GET_SYSNAME = 0x8080552C
LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.syscall.restype = ctypes.c_long


class ProcessFactory(Protocol):
    """Configured process creation used for broker-owned children."""

    def __call__(
        self,
        command: list[str],
        *,
        pass_fds: tuple[int, ...] = (),
        preexec_fn: Callable[[], None] | None = None,
    ) -> subprocess.Popen[bytes]:
        """Start a child whose process lifetime transfers to the broker."""
        ...


def start_process(
    command: list[str],
    *,
    pass_fds: tuple[int, ...] = (),
    preexec_fn: Callable[[], None] | None = None,
) -> subprocess.Popen[bytes]:
    """Start an argv-only broker child with configured descriptor/privilege policy."""
    # The broker constructs fixed executables and passes arguments without a shell.
    return subprocess.Popen(  # noqa: S603 - argv is validated at broker admission.
        command,
        pass_fds=pass_fds,
        preexec_fn=preexec_fn,  # noqa: PLW1509 - single-threaded PID-one broker must set PR_SET_NO_NEW_PRIVS before exec.
    )


def live(pidfd: int) -> bool:
    """Report whether the pinned process has not exited."""
    return not select.select([pidfd], [], [], 0)[0]


def process_stat(pid: int) -> tuple[int, int]:
    """Read a live process's parent PID and immutable kernel start tick."""
    text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    fields = text[text.rindex(")") + 2 :].split()
    if fields[0] in ("Z", "X", "x"):
        raise ProcessLookupError(pid)
    return int(fields[1]), int(fields[19])


class OwnedProcess:
    """Own a pidfd and authorize operations only against its original process."""

    def __init__(self, pid: int, parent: "OwnedProcess | None" = None) -> None:
        """Pin a live process, optionally requiring an already admitted parent."""
        self.pid = pid
        self.fd = os.pidfd_open(pid)
        # Admission errors must unwind through the same pidfd cleanup.
        try:
            if not live(self.fd):
                raise ProcessLookupError(pid)  # noqa: TRY301
            self.parent, self.start = process_stat(pid)
            if parent is not None and (not parent.valid() or self.parent != parent.pid):
                error_message = "unverified ancestry"
                raise ProcessLookupError(error_message)  # noqa: TRY301
            if not self.valid() or (parent is not None and not parent.valid()):
                error_message = "process identity changed"
                raise ProcessLookupError(error_message)  # noqa: TRY301
        except BaseException:
            os.close(self.fd)
            raise

    def valid(self) -> bool:
        """Require both the pinned pidfd and unchanged kernel start identity."""
        if not live(self.fd):
            return False
        try:
            _, start = process_stat(self.pid)
            return start == self.start and live(self.fd)
        except (FileNotFoundError, ProcessLookupError):
            return False

    def duplicate(self, number: int) -> int:
        """Duplicate a creator descriptor while retaining pinned process identity."""
        if not self.valid():
            error_message = self.pid
            raise ProcessLookupError(error_message)
        result: int = LIBC.syscall(438, self.fd, number, 0)
        if result < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        fcntl.fcntl(result, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        if not self.valid():
            os.close(result)
            error_message = self.pid
            raise ProcessLookupError(error_message)
        return result

    def send(self, number: int) -> None:
        """Signal only this still-live pidfd, never a reused numeric PID."""
        if live(self.fd):
            with suppress(ProcessLookupError):
                signal.pidfd_send_signal(self.fd, number)

    def close(self) -> None:
        """Release the owned pidfd."""
        os.close(self.fd)


class ProcessTree:
    """Own pidfds discovered through verified application ancestry."""

    def __init__(self, child: subprocess.Popen[bytes]) -> None:
        """Pin the borrowed child process without taking ownership of its Popen."""
        root = OwnedProcess(child.pid)
        self.records = {root.pid: root}

    def scan(self) -> None:
        """Admit live descendants, including children that create new sessions."""
        candidates: dict[int, tuple[int, int]] = {}
        for entry in Path("/proc").iterdir():
            if entry.name.isdecimal() and int(entry.name) not in self.records:
                with suppress(FileNotFoundError, ProcessLookupError, PermissionError):
                    candidates[int(entry.name)] = process_stat(int(entry.name))
        # A scan may see several generations before their first discovery.
        while candidates:
            added = False
            for pid, (ppid, start) in list(candidates.items()):
                parent = self.records.get(ppid)
                if parent is None:
                    continue
                del candidates[pid]
                with suppress(FileNotFoundError, ProcessLookupError):
                    record = OwnedProcess(pid, parent)
                    if record.start != start:
                        record.close()
                        continue
                    self.records[pid] = record
                    added = True
            if not added:
                break

    def close(self) -> None:
        """Release every admitted process handle even if one close fails."""
        records, self.records = self.records, {}
        with ExitStack() as cleanup:
            for record in records.values():
                cleanup.callback(record.close)


def sysname(fd: int) -> str:
    """Read the kernel identity of a created uinput device from its creator FD."""
    data = bytearray(128)
    fcntl.ioctl(fd, UI_GET_SYSNAME, data, MUTATE_IOCTL_BUFFER)
    name = data.split(b"\0", 1)[0].decode("ascii")
    if not re.fullmatch(r"input[0-9]+", name):
        error_message = "invalid kernel uinput sysname"
        raise RuntimeError(error_message)
    return name


def device_identity(name: str) -> tuple[str, int]:
    """Resolve one pinned sysfs input identity to its event name and device number."""
    if not re.fullmatch(r"input[0-9]+", name):
        error_message = "invalid kernel input identity"
        raise RuntimeError(error_message)
    parent = Path("/sys/devices/virtual/input") / name
    if parent.resolve(strict=True) != parent:
        error_message = "unexpected kernel input symlink"
        raise RuntimeError(error_message)
    events = [
        entry for entry in parent.iterdir() if re.fullmatch(r"event[0-9]+", entry.name)
    ]
    if len(events) != 1:
        error_message = "expected one kernel event device"
        raise RuntimeError(error_message)
    event = events[0]
    if event.resolve(strict=True) != event:
        error_message = "unexpected kernel event symlink"
        raise RuntimeError(error_message)
    value = (event / "dev").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+:[0-9]+", value):
        error_message = "invalid kernel character device number"
        raise RuntimeError(error_message)
    major, minor = map(int, value.split(":"))
    return event.name, os.makedev(major, minor)


def node_identity(info: os.stat_result) -> tuple[int, int, int]:
    """Return inode and device identity used to refuse foreign replacements."""
    return info.st_dev, info.st_ino, info.st_rdev


class EventNode:
    """Own only an event node created by this adapter."""

    def __init__(self, path: Path, devt: int, gid: int) -> None:
        """Create or borrow the exact kernel device without adopting foreign nodes."""
        self.path = path
        self.created = False
        self.identity: tuple[int, int, int] | None = None
        parent = self.path.parent
        parent.mkdir(mode=0o755, exist_ok=True)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            error_message = "input node directory must be root-controlled"
            raise RuntimeError(error_message)
        try:
            os.mknod(self.path, stat.S_IFCHR | 0o660, devt)
            self.created = True
            self.identity = node_identity(self.path.lstat())
            os.chown(self.path, 0, gid, follow_symlinks=False)
            self.path.chmod(0o660, follow_symlinks=False)
        except FileExistsError:
            pass
        except BaseException:
            self.close()
            raise
        info = self.path.lstat()
        if not stat.S_ISCHR(info.st_mode) or info.st_rdev != devt:
            self.close()
            error_message = "conflicting input node: " + str(self.path)
            raise RuntimeError(error_message)
        if self.identity is None:
            self.identity = node_identity(info)

    def open(self) -> int:
        """Open the exact pinned event inode without following replacements."""
        fd = os.open(
            self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        if node_identity(os.fstat(fd)) != self.identity:
            os.close(fd)
            error_message = "input node changed during open"
            raise RuntimeError(error_message)
        return fd

    def close(self) -> None:
        """Unlink only a created inode whose full identity still matches."""
        if self.created and self.identity is not None:
            with suppress(FileNotFoundError):
                if node_identity(self.path.lstat()) == self.identity:
                    self.path.unlink()
            self.created = False


def process_command_matches(process: OwnedProcess, command: list[str]) -> bool:
    """Narrow metadata publication to the live, already admitted probe creator."""
    if not process.valid():
        return False
    try:
        with Path(f"/proc/{process.pid}/cmdline").open("rb") as stream:
            actual = stream.read(4097)
        expected = b"".join(os.fsencode(value) + b"\0" for value in command)
        return (
            len(actual) <= MAX_COMMAND_BYTES
            and actual == expected
            and Path(f"/proc/{process.pid}/exe").samefile(command[0])
            and process.valid()
        )
    except (FileNotFoundError, ProcessLookupError):
        return False


class Source:
    """Own one creator descriptor, event node, reader and optional publication."""

    # acquire initializes these under __init__ cleanup before publishing the source.
    devt: int  # pyright: ignore[reportUninitializedInstanceVariable]
    name: str  # pyright: ignore[reportUninitializedInstanceVariable]
    final: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        process: OwnedProcess,
        creator: tuple[int, int],
        name: str,
        gid: int,
        *,
        suite: bool = False,
    ) -> None:
        """Take ownership of creator even if initialization subsequently fails."""
        self.process = process
        self.number, creator_fd = creator
        self.creator: int | None = creator_fd
        self.sysname = name
        self.suite_command = (
            ["/usr/bin/python3", "/opt/gow-full-x86/emulator_probe.py"]
            if suite
            else None
        )
        self.node: EventNode | None = None
        self.reader: int | None = None
        self.sent = False
        self.udev: UdevPublisher | None = None
        try:
            self.acquire(gid, suite=suite)
        except BaseException:
            self.close()
            raise

    def acquire(self, gid: int, *, suite: bool) -> None:
        """Acquire the event reader and optional metadata under creator ownership."""
        creator = self.creator
        if creator is None:
            message = "source creator was already closed"
            raise RuntimeError(message)
        name = self.sysname
        process = self.process
        event, self.devt = device_identity(name)
        self.node = EventNode(Path("/dev/input") / event, self.devt, gid)
        self.reader = self.node.open()
        # No event may be consumed or handed off before final live checks.
        if sysname(creator) != name or device_identity(name) != (event, self.devt):
            error_message = "kernel input changed during acquisition"
            raise RuntimeError(error_message)
        if not process.valid():
            raise ProcessLookupError(process.pid)
        data = bytearray(256)
        fcntl.ioctl(
            self.reader, 0x81004506, data, MUTATE_IOCTL_BUFFER
        )  # EVIOCGNAME(256)
        self.name = data.split(b"\0", 1)[0].decode("utf-8", "replace")
        self.final = self.name == "batocera hotkeys"
        suite_pad = False
        if suite:
            definition = json.loads(
                (RUNTIME_ROOT / "suite-gamepad.json").read_text(encoding="utf-8")
            )
            identity = array.array("H", [0, 0, 0, 0])
            fcntl.ioctl(
                self.reader, 0x80084502, identity, MUTATE_IOCTL_BUFFER
            )  # EVIOCGID
            suite_pad = self.name == definition["name"] and list(identity) == [
                definition[key] for key in ("bus", "vendor", "product", "version")
            ]
        if self.final or suite_pad:
            if not self.node.created:
                error_message = "cannot publish metadata for a preexisting input node"
                raise RuntimeError(error_message)
            self.udev = UdevPublisher(
                Path("/sys/devices/virtual/input") / name / event,
                self.node.path,
                self.devt,
                self.valid,
                required_class="ID_INPUT_KEY" if self.final else "ID_INPUT_JOYSTICK",
            )

    def valid(self) -> bool:
        """Require live process, creator descriptor and kernel device agreement."""
        if self.node is None or self.creator is None:
            return False
        if not self.process.valid():
            return False
        if self.suite_command is not None and not process_command_matches(
            self.process, self.suite_command
        ):
            return False
        try:
            current = self.process.duplicate(self.number)
            try:
                info = os.fstat(current)
                return (
                    stat.S_ISCHR(info.st_mode)
                    and info.st_rdev == Path("/dev/uinput").stat().st_rdev
                    and sysname(current) == self.sysname
                    and sysname(self.creator) == self.sysname
                    and device_identity(self.sysname)
                    == (self.node.path.name, self.devt)
                )
            finally:
                os.close(current)
        except ProcessLookupError:
            return False
        except OSError as error:
            if error.errno in (
                errno.ENOENT,
                errno.ENODEV,
                errno.EBADF,
                errno.ESRCH,
                errno.EINVAL,
            ):
                return False
            raise

    def close(self) -> None:
        """Withdraw metadata and release all owned pins despite teardown errors."""
        # Revoke classification before unlinking the node or dropping its pins.
        creator, self.creator = self.creator, None
        reader, self.reader = self.reader, None
        publisher, self.udev = self.udev, None
        with ExitStack() as cleanup:
            if creator is not None:
                cleanup.callback(os.close, creator)
            if reader is not None:
                cleanup.callback(os.close, reader)
            if self.node is not None:
                cleanup.callback(self.node.close)
            if publisher is not None:
                cleanup.callback(publisher.close)

    def summary(self) -> dict[str, object]:
        """Return public device metadata without leaking creator descriptors."""
        if self.node is None:
            message = "source is not initialized"
            raise RuntimeError(message)
        value: dict[str, object] = {
            "sysname": self.sysname,
            "name": self.name,
            "node": str(self.node.path),
            "source_pid": self.process.pid,
            "role": "final" if self.final else "semantic",
        }
        if self.udev is not None:
            value["udev_properties"] = self.udev.properties
            value["udev_classifier_sha256"] = self.udev.classifier_sha256
        return value


def send_message(
    connection: socket.socket, value: dict[str, object], fd: int | None = None
) -> None:
    """Send one broker message and optionally transfer a duplicate descriptor."""
    ancillary = (
        []
        if fd is None
        else [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [fd]))]
    )
    connection.sendmsg([json.dumps(value).encode()], ancillary)


def write_status(value: dict[str, object]) -> None:
    """Atomically replace the adapter's public status record."""
    temporary = STATUS.with_suffix(".partial")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
        temporary.replace(STATUS)
    finally:
        temporary.unlink(missing_ok=True)


def no_new_privileges() -> None:
    """Prevent a child from gaining privileges through a later executable."""
    if LIBC.prctl(38, 1, 0, 0, 0):  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "cannot confine child privilege gains")


def verify_application(process: OwnedProcess, uid: int, gid: int) -> None:
    """Require a live capability-free creator using only the application identity."""
    status = dict(
        line.split(":", 1)
        for line in Path(f"/proc/{process.pid}/status")
        .read_text(encoding="utf-8")
        .splitlines()
        if ":" in line
    )
    if (
        any(int(value) != uid for value in status["Uid"].split())
        or any(int(value) != gid for value in status["Gid"].split())
        or any(
            int(status[name], 16) for name in ("CapEff", "CapPrm", "CapAmb", "CapInh")
        )
        or int(status["NoNewPrivs"]) != 1
        or not process.valid()
    ):
        error_message = "input creator is not the capability-free app identity"
        raise RuntimeError(error_message)


def read_pidfile(path: str | Path, uid: int) -> int | None:
    """Read an owned stock PID record; an unflushed empty file is not a PID."""
    path = Path(path)
    directory = os.open(
        path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        info = os.fstat(directory)
        if info.st_uid not in (0, uid) or info.st_mode & 0o022:
            error_message = "unsafe stock pidfile directory"
            raise RuntimeError(error_message)
        fd = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=directory,
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != uid
                or info.st_nlink != 1
                or info.st_mode & 0o022
                or info.st_size > MAX_PIDFILE_BYTES
            ):
                error_message = "unsafe stock hotkeygen pidfile"
                raise RuntimeError(error_message)
            data = os.read(fd, 33)
            if not data:
                return None  # The stock writer has created but not flushed it yet.
            if len(data) > MAX_PIDFILE_BYTES or not re.fullmatch(
                rb"[1-9][0-9]*\n?", data
            ):
                error_message = "invalid stock hotkeygen pidfile"
                raise RuntimeError(error_message)
            return int(data)
        finally:
            os.close(fd)
    finally:
        os.close(directory)


class Broker:
    """Own input sources and child processes for one private container session."""

    def __init__(
        self,
        command: list[str],
        identity: tuple[int, int],
        process_factory: ProcessFactory,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        """Borrow configured collaborators without allocating process resources."""
        self.process_factory = process_factory
        self.monotonic = monotonic
        self.sleep = sleep
        self.command = command
        self.uid, self.gid = identity
        self.sources: dict[str, Source] = {}
        self.acknowledged: set[str] = set()
        self.stopping = False
        self.worker_ready, self.reload_pending = False, False
        self.last_status: dict[str, object] | None = None
        self.failure: str | None = None
        self.closing_deadline: float | None = None
        self.tree: ProcessTree | None = None
        self.connection: socket.socket | None = None

    def stop(self, number: int, frame: FrameType | None) -> None:
        """Request orderly teardown from the signal boundary."""
        del number, frame
        self.stopping = True

    def worker_closed(self) -> None:
        """Allow the normal frontend to return after Xwayland teardown begins."""
        if self.closing_deadline is None:
            # The unchanged session tears Xwayland down before returning its
            # frontend's exit code. Keep revoking sources during that interval.
            self.closing_deadline = self.monotonic() + 4
            self.worker_ready = False
            self.acknowledged.clear()

    def publish(self, error: BaseException | str | None = None) -> None:
        """Publish status only when consumer-visible state changes."""
        sources = [source.summary() for source in self.sources.values()]
        value: dict[str, object] = {
            "ready": bool(self.acknowledged),
            "worker_connected": self.worker_ready,
            "sources": sources,
            "pid": os.getpid(),
            "app_uid": self.uid,
            "approved_process_ids": sorted(self.tree.records)
            if self.tree is not None
            else [],
            "strict_device_lifetime_isolation": False,
        }
        if error is not None:
            self.failure = str(error)
        if self.failure is not None:
            value.update(ready=False, error=self.failure)
        if value != self.last_status:
            write_status(value)
            self.last_status = value

    def revoke(self, name: str) -> None:
        """Revoke worker holds and close the source even if the socket has failed."""
        source = self.sources.pop(name)
        try:
            if self.worker_ready and self.connection is not None:
                send_message(
                    self.connection,
                    {"op": "remove" if source.final else "reset", "source": name},
                )
        finally:
            self.acknowledged.discard(name)
            source.close()

    def close_sources(self) -> Exception | None:
        """Attempt all source teardowns, returning the first cleanup failure."""
        failure: Exception | None = None

        def remember_failure(
            kind: type[BaseException] | None,
            error: BaseException | None,
            traceback: TracebackType | None,
        ) -> bool:
            """Record operational failures while still attempting every owned close."""
            nonlocal failure
            del kind, traceback
            if isinstance(error, Exception):
                if failure is None:
                    failure = error
                return True
            return False

        # Each close has its own exception consumer; LIFO registration keeps the
        # original source order and does not let one failure hide later cleanup.
        with ExitStack() as cleanup:
            for source in reversed(self.sources.values()):
                cleanup.push(remember_failure)
                cleanup.callback(source.close)
        self.sources.clear()
        self.acknowledged.clear()
        return failure

    def discover(self) -> None:
        """Discover only live admitted descendants' created uinput devices."""
        if self.tree is None:
            message = "application ancestry is not initialized"
            raise RuntimeError(message)
        uinput = Path("/dev/uinput").stat().st_rdev
        for process in self.tree.records.values():
            if process.valid():
                self.discover_process(process, uinput)

    def discover_process(self, process: OwnedProcess, uinput: int) -> None:
        """Inspect one admitted process, tolerating only disappearing kernel state."""
        try:
            descriptors = list(Path(f"/proc/{process.pid}/fd").iterdir())
        except FileNotFoundError:
            return
        for descriptor in descriptors:
            try:
                self.acquire_source(process, descriptor, uinput)
            except ProcessLookupError:
                pass
            except OSError as error:
                if error.errno not in (
                    errno.ENOENT,
                    errno.ESRCH,
                    errno.EBADF,
                    errno.ENODEV,
                    errno.EINVAL,
                ):
                    raise

    def acquire_source(
        self, process: OwnedProcess, descriptor: Path, uinput: int
    ) -> None:
        """Transfer an admitted creator FD exactly once, including setup failure."""
        info = descriptor.stat()
        if not stat.S_ISCHR(info.st_mode) or info.st_rdev != uinput:
            return
        number = int(descriptor.name)
        if any(
            source.process is process and source.number == number
            for source in self.sources.values()
        ):
            return
        fd = process.duplicate(number)
        transferred = False
        try:
            actual = os.fstat(fd)
            if not stat.S_ISCHR(actual.st_mode) or actual.st_rdev != uinput:
                return
            name = sysname(fd)
            if name in self.sources:
                return
            verify_application(process, self.uid, self.gid)
            transferred = True  # Source owns fd even when its constructor fails.
            self.sources[name] = Source(
                process,
                (number, fd),
                name,
                self.gid,
                suite=self.command
                == [
                    "/opt/gow-full-x86/entrypoint.sh",
                    "/usr/bin/python3",
                    "/opt/gow-full-x86/emulator_probe.py",
                ]
                and process_command_matches(process, self.command[1:]),
            )
            self.reload_pending = True
        finally:
            if not transferred:
                os.close(fd)

    def reload(self) -> None:
        """Notify only the pinned stock daemon once its reload handler is ready."""
        if not self.reload_pending or self.tree is None:
            return
        with suppress(FileNotFoundError):
            pid = read_pidfile("/var/run/hotkeygen.pid", self.uid)
            if pid is None:
                return
            daemon = self.tree.records.get(pid)
            if daemon is None or not daemon.valid():
                return
            if not any(
                source.final and source.process is daemon
                for source in self.sources.values()
            ):
                error_message = "hotkeygen pid does not own the final output"
                raise RuntimeError(error_message)
            status = Path(f"/proc/{daemon.pid}/status").read_text(encoding="utf-8")
            caught = next(
                int(line.split()[1], 16)
                for line in status.splitlines()
                if line.startswith("SigCgt:")
            )
            if not caught & (1 << (signal.SIGHUP - 1)):
                return
            # Stock --reload is SIGHUP; use the verified pidfd, not a PID.
            daemon.send(signal.SIGHUP)
            self.reload_pending = False

    def run(self) -> int:
        """Supervise one session and deterministically release owned input resources."""
        with ExitStack() as resources:
            previous_term = signal.signal(signal.SIGTERM, self.stop)
            resources.callback(signal.signal, signal.SIGTERM, previous_term)
            previous_int = signal.signal(signal.SIGINT, self.stop)
            resources.callback(signal.signal, signal.SIGINT, previous_int)
            parent, child_socket = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_SEQPACKET
            )
            resources.callback(parent.close)
            resources.callback(child_socket.close)
            return self.run_children(parent, child_socket)

    def run_children(self, parent: socket.socket, child_socket: socket.socket) -> int:
        """Borrow socket endpoints and own the worker/application process lifetimes."""
        self.connection = parent
        worker: subprocess.Popen[bytes] | None = None
        worker_identity: OwnedProcess | None = None
        application: subprocess.Popen[bytes] | None = None
        try:
            worker = self.process_factory(
                [
                    sys.executable,
                    str(RUNTIME_ROOT / "input_worker.py"),
                    str(child_socket.fileno()),
                    str(self.uid),
                    str(self.gid),
                ],
                pass_fds=(child_socket.fileno(),),
            )
            child_socket.close()
            worker_identity = OwnedProcess(worker.pid)
            application = self.process_factory(
                self.command,
                preexec_fn=no_new_privileges,
            )
            self.tree = ProcessTree(application)
            return self.supervise_loop(application, worker, parent)
        except BaseException as error:
            self.publish(error)
            raise
        finally:
            self.shutdown_children(parent, worker, worker_identity, application)

    def supervise_loop(
        self,
        application: subprocess.Popen[bytes],
        worker: subprocess.Popen[bytes],
        parent: socket.socket,
    ) -> int:
        """Poll owned processes and preserve ordered source discovery and handoff."""
        tree = self.tree
        if tree is None:
            reason = "application ancestry is not initialized"
            raise RuntimeError(reason)
        deadline = self.monotonic() + 30
        while not self.stopping:
            result = application.poll()
            if result is not None:
                return result
            worker_result = worker.poll()
            if worker_result is not None and self.closing_deadline is None:
                self.worker_closed()
            tree.scan()
            for name, source in list(self.sources.items()):
                if not source.valid():
                    self.revoke(name)
            if self.closing_deadline is None:
                self.discover()
                self.reload()
            self.receive_worker_messages(parent)
            self.handoff_sources(parent)
            self.publish()
            self.check_deadlines(deadline)
            self.sleep(0.05)
        return 128 + signal.SIGTERM

    def check_deadlines(self, readiness_deadline: float) -> None:
        """Refuse a dead worker or a session which never handed off a source."""
        if self.closing_deadline is not None:
            if self.monotonic() >= self.closing_deadline:
                message = "input worker closed while application remained running"
                raise RuntimeError(message)
        elif not self.acknowledged and self.monotonic() > readiness_deadline:
            message = "input transport readiness timed out"
            raise RuntimeError(message)

    def receive_worker_messages(self, parent: socket.socket) -> None:
        """Accept ordered readiness acknowledgements from the capability-free worker."""
        while self.closing_deadline is None and select.select([parent], [], [], 0)[0]:
            data = parent.recv(8192)
            if not data:
                self.worker_closed()
                break
            message: object = json.loads(data)
            if not isinstance(message, dict):
                reason = "invalid input worker message"
                raise TypeError(reason)
            if "error" in message:
                error_message = "input worker: " + str(message["error"])
                raise RuntimeError(error_message)
            if message.get("op") == "ready":
                self.worker_ready = True
            elif message.get("op") == "source_ready":
                source_name = message.get("source")
                if isinstance(source_name, str) and source_name in self.sources:
                    self.acknowledged.add(source_name)

    def handoff_sources(self, parent: socket.socket) -> None:
        """Transfer live final event descriptors after worker authentication."""
        if self.worker_ready:
            for source in self.sources.values():
                if source.final and not source.sent:
                    if not source.valid():
                        continue
                    send_message(
                        parent,
                        {"op": "add", "source": source.sysname},
                        source.reader,
                    )
                    source.sent = True

    def shutdown_children(
        self,
        parent: socket.socket,
        worker: subprocess.Popen[bytes] | None,
        worker_identity: OwnedProcess | None,
        application: subprocess.Popen[bytes] | None,
    ) -> None:
        """Attempt process and input teardown after successful or partial startup."""
        with ExitStack() as cleanup:
            cleanup.callback(self.release_connection)
            if worker_identity is not None:
                cleanup.callback(worker_identity.close)
            if self.tree is not None:
                cleanup.callback(self.tree.close)
            cleanup.callback(self.finish_sources)
            self.request_shutdown(parent, worker_identity)
            self.wait_for_shutdown(worker_identity)
            self.kill_children(worker, worker_identity, application)
            if worker is not None:
                worker.wait()
            if application is not None:
                application.wait()
            self.reap_adopted_children()

    def request_shutdown(
        self, parent: socket.socket, worker_identity: OwnedProcess | None
    ) -> None:
        """Ask admitted descendants to exit and the authenticated worker to close."""
        if self.tree is not None:
            for record in self.tree.records.values():
                record.send(signal.SIGTERM)
        if (
            self.worker_ready
            and worker_identity is not None
            and live(worker_identity.fd)
        ):
            with suppress(OSError):
                send_message(parent, {"op": "close"})

    def wait_for_shutdown(self, worker_identity: OwnedProcess | None) -> None:
        """Allow owned descendants and the worker a bounded graceful exit."""
        limit = self.monotonic() + 3
        while self.monotonic() < limit:
            records = () if self.tree is None else self.tree.records.values()
            worker_live = worker_identity is not None and live(worker_identity.fd)
            if not any(live(record.fd) for record in records) and not worker_live:
                break
            self.sleep(0.05)

    def kill_children(
        self,
        worker: subprocess.Popen[bytes] | None,
        worker_identity: OwnedProcess | None,
        application: subprocess.Popen[bytes] | None,
    ) -> None:
        """Force remaining admitted processes down without trusting recycled PIDs."""
        if self.tree is not None:
            for record in self.tree.records.values():
                record.send(signal.SIGKILL)
        if worker_identity is not None:
            worker_identity.send(signal.SIGKILL)
        elif worker is not None and worker.poll() is None:
            worker.kill()
        if application is not None and self.tree is None and application.poll() is None:
            application.kill()

    @staticmethod
    def reap_adopted_children() -> None:
        """Reap exited descendants adopted by this private PID-one supervisor."""
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0:
                    break
            except ChildProcessError:
                break

    def release_connection(self) -> None:
        """Forget the borrowed broker connection after children release their inputs."""
        self.connection = None

    def finish_sources(self) -> None:
        """Release source allocations and retain cleanup failure in public status."""
        cleanup_error = self.close_sources()
        self.publish(self.failure or cleanup_error)
        if cleanup_error is not None:
            raise cleanup_error


def main() -> int:
    """Validate container isolation and supervise the unchanged entrypoint."""
    if os.geteuid() != 0 or os.getpid() != 1:
        error_message = "diagnostic broker must be root PID 1 in a private container"
        raise RuntimeError(error_message)
    if os.uname().machine != "x86_64":
        error_message = "diagnostic pidfd_getfd syscall is x86_64 only"
        raise RuntimeError(error_message)
    values = [os.environ.get("PUID", "1000"), os.environ.get("PGID", "1000")]
    if any(
        not re.fullmatch(r"[1-9][0-9]*", value) or int(value) >= UID_LIMIT
        for value in values
    ):
        error_message = "diagnostic requires nonzero numeric app UID/GID"
        raise RuntimeError(error_message)
    command = sys.argv[1:]
    if not command or command.pop(0) != "--" or not command:
        error_message = (
            "usage: input_transport.py -- unchanged-entrypoint [command ...]"
        )
        raise RuntimeError(error_message)
    uid, gid = map(int, values)
    return Broker(command, (uid, gid), start_process, time.monotonic, time.sleep).run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        sys.stderr.write("gow-input-transport: " + str(error) + "\n")
        sys.stderr.flush()
        sys.exit(1)
