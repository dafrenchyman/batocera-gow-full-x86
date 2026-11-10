"""Capability-free X11 worker receiving only broker-pinned evdev descriptors."""

import array
import errno
import json
import os
import re
import select
import socket
import stat
import struct
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol

from .input_transport import no_new_privileges, send_message
from .x11_input import InputSink, InputState, XTestSink

MAX_MESSAGE_BYTES = 8192
MAX_AUTHORITY_BYTES = 65536
PRIVATE_RUNTIME_MODE = 448
AUTHORITY_MODE = 384


EVENT = struct.Struct("llHHi")


class WorkerSink(InputSink, Protocol):
    """Desktop connection allocated by the worker's configured sink factory."""

    def close(self) -> None:
        """Release this connection, including after failed held-state cleanup."""
        ...


def check_credentials(uid: int, gid: int) -> None:
    """Refuse execution unless every identity and capability matches the app."""
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines()
        if ":" in line
    )
    if any(int(value) != uid for value in status["Uid"].split()):
        error_message = "worker did not drop all app UIDs"
        raise RuntimeError(error_message)
    if any(int(value) != gid for value in status["Gid"].split()):
        error_message = "worker did not drop all app GIDs"
        raise RuntimeError(error_message)
    if any(int(status[name], 16) for name in ("CapEff", "CapPrm", "CapAmb", "CapInh")):
        error_message = "worker retains capabilities"
        raise RuntimeError(error_message)
    if int(status["NoNewPrivs"]) != 1:
        error_message = "worker can gain new privileges"
        raise RuntimeError(error_message)


def validate_metadata_file(info: os.stat_result) -> None:
    """Reject metadata which is not bounded and controlled by root."""
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or info.st_mode & 0o022
        or info.st_size > MAX_MESSAGE_BYTES
    ):
        message = "unsafe session metadata"
        raise RuntimeError(message)


def session_runtime(uid: int, gid: int) -> Path:
    """Validate trusted session metadata and return its private cookie directory."""
    parent = Path("/run").lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        error_message = "session metadata directory is not root-controlled"
        raise RuntimeError(error_message)
    fd = os.open(
        "/run/gow-full-x86-session.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        info = os.fstat(fd)
        validate_metadata_file(info)
        metadata: object = json.loads(os.read(fd, 8193))
    finally:
        os.close(fd)
    if not isinstance(metadata, dict):
        message = "invalid session metadata"
        raise TypeError(message)
    if (
        metadata["display"] != ":0"
        or metadata["puid"] != uid
        or metadata["pgid"] != gid
    ):
        error_message = "session identity does not match worker"
        raise RuntimeError(error_message)
    runtime_value = metadata.get("runtime")
    if not isinstance(runtime_value, str):
        message = "invalid session runtime"
        raise TypeError(message)
    runtime = Path(runtime_value)
    if (
        runtime.parent != Path("/tmp")  # noqa: S108 - fixed stock session root.
        or not re.fullmatch(r"gow-full-x86-[a-zA-Z0-9_-]+", runtime.name)
        or metadata["xauthority"] != str(runtime / "Xauthority")
    ):
        error_message = "unexpected session authority location"
        raise RuntimeError(error_message)
    return runtime


def validate_authority(info: os.stat_result, uid: int) -> None:
    """Require a finished private cookie inode belonging only to the app user."""
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != uid
        or stat.S_IMODE(info.st_mode) != AUTHORITY_MODE
        or info.st_nlink != 1
        or not 0 < info.st_size <= MAX_AUTHORITY_BYTES
    ):
        message = "unsafe or unfinished session authority"
        raise RuntimeError(message)


def open_authority(uid: int, gid: int) -> int:
    """Acquire the owned session cookie through no-follow directory descriptors."""
    runtime = session_runtime(uid, gid)
    temporary = os.open(
        "/tmp",  # noqa: S108 - fixed stock runtime; no-follow open below.
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        directory = os.open(
            runtime.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=temporary,
        )
    finally:
        os.close(temporary)
    try:
        info = os.fstat(directory)
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != PRIVATE_RUNTIME_MODE:
            error_message = "unsafe private session runtime"
            raise RuntimeError(error_message)
        auth = os.open(
            "Xauthority", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory
        )
        try:
            validate_authority(os.fstat(auth), uid)
        except BaseException:
            os.close(auth)
            raise
        else:
            return auth
    finally:
        os.close(directory)


class Worker:
    """Borrow broker connection; own received event FDs, input state and X sink."""

    def __init__(
        self,
        connection: socket.socket,
        sink_factory: Callable[[str, str], WorkerSink],
        authority_factory: Callable[[int, int], int],
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        """Borrow factories and socket; own only acquired resources."""
        self.sink_factory = sink_factory
        self.authority_factory = authority_factory
        self.monotonic = monotonic
        self.sleep = sleep
        self.connection = connection
        self.sources: dict[str, tuple[int, bytes]] = {}
        self.state: InputState | None = None
        self.sink: WorkerSink | None = None

    def input_state(self) -> InputState:
        """Return initialized state, refusing messages before authentication."""
        if self.state is None:
            message = "worker input state is not initialized"
            raise RuntimeError(message)
        return self.state

    def drain(self, source: str) -> bool:
        """Consume complete events, preserving partial records between reads."""
        fd, pending = self.sources[source]
        try:
            while True:
                data = os.read(fd, EVENT.size * 64)
                if not data:
                    return False
                pending += data
                while len(pending) >= EVENT.size:
                    _, _, kind, code, value = EVENT.unpack_from(pending)
                    pending = pending[EVENT.size :]
                    self.input_state().feed(source, kind, code, value)
                self.sources[source] = fd, pending
        except BlockingIOError:
            return True
        except OSError as error:
            if error.errno == errno.ENODEV:
                return False
            raise

    def remove(self, source: str) -> None:
        """Release a source's holds and always close its transferred descriptor."""
        if source in self.sources:
            fd, _ = self.sources.pop(source)
            try:
                self.input_state().remove_source(source)
            finally:
                os.close(fd)

    def message(self) -> bool:
        """Apply one broker control message and close all unaccepted descriptors."""
        data, ancillary, flags, _ = self.connection.recvmsg(
            MAX_MESSAGE_BYTES, socket.CMSG_SPACE(4), socket.MSG_CMSG_CLOEXEC
        )
        descriptors: list[int] = []
        try:
            for level, kind, body in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array("i")
                    values.frombytes(body[: len(body) - len(body) % values.itemsize])
                    descriptors.extend(values)
            if not data:
                return False
            if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                error_message = "truncated broker message"
                raise RuntimeError(error_message)
            message: object = json.loads(data)
            if not isinstance(message, dict):
                reason = "invalid broker message"
                raise TypeError(reason)
            operation = message.get("op")
            source = message.get("source")
            if not isinstance(operation, str):
                reason = "invalid broker operation"
                raise TypeError(reason)
            if operation in ("add", "remove") and not isinstance(source, str):
                reason = "invalid broker source identity"
                raise TypeError(reason)
            return self.apply_message(
                operation, source if isinstance(source, str) else None, descriptors
            )
        finally:
            for fd in descriptors:
                os.close(fd)

    def apply_message(
        self, operation: str, source: str | None, descriptors: list[int]
    ) -> bool:
        """Take ownership only of admitted add descriptors and apply control actions."""
        if operation == "add":
            if source is None or len(descriptors) != 1 or source in self.sources:
                error_message = "invalid source descriptor handoff"
                raise RuntimeError(error_message)
            fd = descriptors[-1]
            os.set_blocking(fd, False)
            self.sources[source] = fd, b""
            descriptors.pop()
            send_message(self.connection, {"op": "source_ready", "source": source})
        elif descriptors:
            error_message = "unexpected broker descriptor"
            raise RuntimeError(error_message)
        elif operation == "remove" and source is not None:
            self.remove(source)
        elif operation == "reset":
            self.reset_sources()
        elif operation == "close":
            return False
        else:
            error_message = "unknown broker operation"
            raise RuntimeError(error_message)
        return True

    def reset_sources(self) -> None:
        """Drain queued output before releasing only transport-owned held state."""
        for source in list(self.sources):
            if not self.drain(source):
                self.remove(source)
            else:
                self.input_state().remove_source(source)

    def run(self, uid: int, gid: int) -> None:
        """Own session resources until shutdown, including partial initialization."""
        authority: int | None = None
        deadline = self.monotonic() + 20
        try:
            while True:
                try:
                    if authority is None:
                        authority = self.authority_factory(uid, gid)
                    self.sink = self.sink_factory(
                        ":0", "/proc/self/fd/" + str(authority)
                    )
                    break
                except (
                    FileNotFoundError,
                    RuntimeError,
                    TypeError,
                    json.JSONDecodeError,
                ) as error:
                    if self.monotonic() >= deadline:
                        error_message = "authenticated worker readiness: " + str(error)
                        raise RuntimeError(error_message) from error
                    self.sleep(0.05)
            self.state = InputState(self.sink)
            send_message(self.connection, {"op": "ready"})
            self.process_events()
        finally:
            # ExitStack attempts every teardown even if releasing a hold fails.
            with ExitStack() as cleanup:
                if authority is not None:
                    cleanup.callback(os.close, authority)
                if self.sink is not None:
                    cleanup.callback(self.sink.close)
                for fd, _ in self.sources.values():
                    cleanup.callback(os.close, fd)
                self.sources.clear()
                if self.state is not None:
                    cleanup.callback(self.state.close)

    def process_events(self) -> None:
        """Consume broker controls and event descriptors until the broker closes."""
        while True:
            readers: list[socket.socket | int] = [
                self.connection,
                *(fd for fd, _ in self.sources.values()),
            ]
            ready = select.select(readers, [], [], 1)[0]
            if self.connection in ready and not self.message():
                break
            for source, (fd, _) in list(self.sources.items()):
                if fd in ready and not self.drain(source):
                    self.remove(source)


def main() -> int:
    """Drop privileges and run the capability-free worker on its inherited socket."""
    fd, uid, gid = map(int, sys.argv[1:])
    if uid <= 0 or gid <= 0:
        error_message = "non-root worker identity required"
        raise RuntimeError(error_message)
    connection = socket.socket(fileno=fd)
    try:
        no_new_privileges()
        os.setgroups([gid])
        os.setgid(gid)
        os.setuid(uid)
        check_credentials(uid, gid)
        Worker(connection, XTestSink, open_authority, time.monotonic, time.sleep).run(
            uid, gid
        )
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        send_message(connection, {"error": str(error)})
        sys.stderr.write("gow-input-worker: " + str(error) + "\n")
        sys.stderr.flush()
        return 1
    else:
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
