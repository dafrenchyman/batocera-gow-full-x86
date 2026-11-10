"""Exercise descriptor transport and worker lifecycle without evdev or X11."""

import errno
import json
import os
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest

from batocera_gow.runtime import input_transport as transport
from batocera_gow.runtime import input_worker
from batocera_gow.runtime.x11_input import InputState


class Desktop:
    """Observe desktop operations without opening a display or claiming XTEST proof."""

    def __init__(self) -> None:
        """Begin with no recorded connection operations."""
        self.events: list[tuple[str, int, int]] = []
        self.closes = 0

    def key(self, code: int, *, pressed: bool) -> None:
        """Record the consumer-visible key transition."""
        self.events.append(("key", code, int(pressed)))

    def button(self, code: int, *, pressed: bool) -> None:
        """Record the consumer-visible pointer button transition."""
        self.events.append(("button", code, int(pressed)))

    def motion(self, dx: int, dy: int) -> None:
        """Record relative pointer displacement in desktop coordinates."""
        self.events.append(("motion", dx, dy))

    def flush(self) -> None:
        """Record the frame boundary after queued desktop output."""
        self.events.append(("flush", 0, 0))

    def close(self) -> None:
        """Record owned connection teardown."""
        self.closes += 1


class Clock:
    """Advance only when the worker requests a readiness delay."""

    def __init__(self) -> None:
        """Start the deterministic clock at zero seconds."""
        self.now = 0.0
        self.delays: list[float] = []

    def monotonic(self) -> float:
        """Return elapsed fixture seconds."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance readiness time without delaying the host."""
        self.delays.append(seconds)
        self.now += 10


def assert_closed(descriptor: int) -> None:
    """Require EBADF rather than relying on platform-specific exception wording."""
    with pytest.raises(OSError, match=r"\[Errno 9\]") as error:
        os.fstat(descriptor)
    assert error.value.errno == errno.EBADF


def event(kind: int, code: int, value: int) -> bytes:
    """Encode a local Linux input record independently of the worker's decoder."""
    return struct.pack("llHHi", 0, 0, kind, code, value)


@pytest.fixture
def worker_pair() -> Iterator[tuple[input_worker.Worker, socket.socket, Desktop]]:
    """Supply borrowed socket endpoints and release every admitted worker source."""
    parent, connection = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    desktop = Desktop()

    def unavailable_authority(uid: int, gid: int) -> int:
        del uid, gid
        message = "this message-only fixture must not authenticate"
        raise AssertionError(message)

    def open_desktop(display: str, authority: str) -> Desktop:
        del display, authority
        return desktop

    worker = input_worker.Worker(
        connection, open_desktop, unavailable_authority, time.monotonic, time.sleep
    )
    worker.state = InputState(desktop)
    try:
        with parent, connection:
            yield worker, parent, desktop
    finally:
        for source in list(worker.sources):
            worker.remove(source)
        worker.input_state().close()


def admit(worker: input_worker.Worker, parent: socket.socket, descriptor: int) -> int:
    """Transfer a duplicate reader and require the worker's public acknowledgement.

    Args:
        worker: Authenticated fixture worker receiving a real control packet.
        parent: Broker endpoint borrowed for the descriptor transfer.
        descriptor: Caller-owned pipe reader, which must remain open.

    Returns:
        The worker-owned duplicate used to observe lifetime cleanup.
    """
    transport.send_message(parent, {"op": "add", "source": "keyboard"}, descriptor)
    assert worker.message()
    assert json.loads(parent.recv(8192)) == {"op": "source_ready", "source": "keyboard"}
    return worker.sources["keyboard"][0]


def test_partial_records_reset_and_disconnect_preserve_order_and_fd_ownership(
    worker_pair: tuple[input_worker.Worker, socket.socket, Desktop],
) -> None:
    """Buffer split records, drain queued output before reset and release holds."""
    worker, parent, desktop = worker_pair
    with ExitStack() as cleanup:
        reader, writer = os.pipe()
        cleanup.callback(os.close, reader)
        cleanup.callback(os.close, writer)
        owned = admit(worker, parent, reader)
        assert owned != reader
        assert not os.get_inheritable(owned)
        press = event(1, 30, 1)
        os.write(writer, press[:7])
        assert worker.drain("keyboard")
        assert desktop.events == []
        os.write(writer, press[7:] + event(2, 0, 12) + event(2, 1, -4) + event(0, 0, 0))
        assert worker.drain("keyboard")
        assert desktop.events == [("key", 30, 1), ("motion", 12, -4), ("flush", 0, 0)]
        os.write(writer, event(1, 31, 1))
        transport.send_message(parent, {"op": "reset"})
        assert worker.message()
        transitions = [item for item in desktop.events if item[0] == "key"]
        assert transitions[:2] == [("key", 30, 1), ("key", 31, 1)]
        assert set(transitions[2:]) == {("key", 30, 0), ("key", 31, 0)}
        assert len(transitions) == 4
        os.fstat(owned)
        os.write(writer, event(1, 32, 1))
        assert worker.drain("keyboard")
        transport.send_message(parent, {"op": "remove", "source": "keyboard"})
        assert worker.message()
        assert desktop.events[-2:] == [("key", 32, 0), ("flush", 0, 0)]
        assert_closed(owned)
        assert stat.S_ISFIFO(os.fstat(reader).st_mode)
        assert worker.sources == {}
        assert desktop.closes == 0


@pytest.mark.parametrize(
    ("packet", "reason"),
    [
        (b"[]", "invalid broker message"),
        (b'{"op":12}', "invalid broker operation"),
        (b'{"op":"add","source":12}', "invalid broker source identity"),
        (b'{"op":"reset"}', "unexpected broker descriptor"),
    ],
)
def test_rejected_control_packets_close_transferred_descriptors_only(
    packet: bytes,
    reason: str,
    worker_pair: tuple[input_worker.Worker, socket.socket, Desktop],
) -> None:
    """Reject malformed handoffs without leaking received FDs or closing the sender."""
    worker, parent, desktop = worker_pair
    with ExitStack() as cleanup:
        reader, writer = os.pipe()
        cleanup.callback(os.close, reader)
        cleanup.callback(os.close, writer)
        before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
        parent.sendmsg(
            [packet], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", reader))]
        )
        with pytest.raises((RuntimeError, TypeError), match=reason):
            worker.message()
        assert {entry.name for entry in Path("/proc/self/fd").iterdir()} == before
        os.fstat(reader)
        assert worker.sources == {}
        assert desktop.events == []


def test_unknown_control_without_descriptor_is_refused(
    worker_pair: tuple[input_worker.Worker, socket.socket, Desktop],
) -> None:
    """Unknown operations cannot create state even without a descriptor handoff."""
    worker, parent, desktop = worker_pair
    parent.send(b'{"op":"unknown"}')
    with pytest.raises(RuntimeError, match="unknown broker operation"):
        worker.message()
    assert worker.sources == {}
    assert desktop.events == []


def test_duplicate_and_truncated_handoffs_cannot_replace_admitted_source(
    worker_pair: tuple[input_worker.Worker, socket.socket, Desktop],
) -> None:
    """Keep the original source intact when a duplicate or oversized packet arrives."""
    worker, parent, _ = worker_pair
    with ExitStack() as cleanup:
        reader, writer = os.pipe()
        cleanup.callback(os.close, reader)
        cleanup.callback(os.close, writer)
        owned = admit(worker, parent, reader)
        transport.send_message(parent, {"op": "add", "source": "keyboard"}, reader)
        with pytest.raises(RuntimeError, match="invalid source descriptor handoff"):
            worker.message()
        parent.send(b" " * 8193)
        with pytest.raises(RuntimeError, match="truncated broker message"):
            worker.message()
        assert worker.sources == {"keyboard": (owned, b"")}
        os.fstat(owned)


def test_worker_authentication_retries_and_full_loop_releases_owned_resources(
    tmp_path: Path,
) -> None:
    """Retry unfinished startup, retain one acquired cookie and close after controls."""
    authority_file = tmp_path / "cookie"
    authority_file.write_bytes(b"fixture-cookie")
    desktop, clock = Desktop(), Clock()
    authorities: list[int] = []
    attempts: list[str] = []

    def authority_factory(uid: int, gid: int) -> int:
        assert (uid, gid) == (1234, 2345)
        attempts.append("authority")
        if len(attempts) == 1:
            raise FileNotFoundError(authority_file)
        descriptor = os.open(authority_file, os.O_RDONLY)
        authorities.append(descriptor)
        return descriptor

    def sink_factory(display: str, authority: str) -> Desktop:
        assert display == ":0"
        assert Path(authority).read_bytes() == b"fixture-cookie"
        attempts.append("display")
        if attempts.count("display") == 1:
            message = "display not ready"
            raise RuntimeError(message)
        return desktop

    parent, connection = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent, connection, ExitStack() as cleanup:
        reader, writer = os.pipe()
        cleanup.callback(os.close, reader)
        cleanup.callback(os.close, writer)
        os.write(writer, event(1, 30, 1))
        transport.send_message(parent, {"op": "add", "source": "keyboard"}, reader)
        for operation in ("reset", "remove", "close"):
            transport.send_message(parent, {"op": operation, "source": "keyboard"})
        worker = input_worker.Worker(
            connection, sink_factory, authority_factory, clock.monotonic, clock.sleep
        )
        worker.run(1234, 2345)
        assert attempts == ["authority", "authority", "display", "display"]
        assert clock.delays == [0.05, 0.05]
        assert json.loads(parent.recv(8192)) == {"op": "ready"}
        assert json.loads(parent.recv(8192)) == {
            "op": "source_ready",
            "source": "keyboard",
        }
        assert [item for item in desktop.events if item[0] == "key"] == [
            ("key", 30, 1),
            ("key", 30, 0),
        ]
        assert desktop.closes == 1
        assert worker.sources == {}
        assert len(authorities) == 1
        assert_closed(authorities[0])
        connection.send(b"borrowed connection survives")
        assert parent.recv(8192) == b"borrowed connection survives"
        os.fstat(reader)


def test_worker_display_timeout_closes_cookie_and_preserves_original_failure(
    tmp_path: Path,
) -> None:
    """Bound authentication retries and revoke the acquired cookie on final failure."""
    path = tmp_path / "cookie"
    path.write_bytes(b"fixture")
    authority = os.open(path, os.O_RDONLY)
    clock = Clock()

    def open_authority(uid: int, gid: int) -> int:
        del uid, gid
        return authority

    def unavailable_display(display: str, cookie: str) -> Desktop:
        del display, cookie
        message = "fixture display refused authentication"
        raise RuntimeError(message)

    parent, connection = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent, connection:
        worker = input_worker.Worker(
            connection,
            unavailable_display,
            open_authority,
            clock.monotonic,
            clock.sleep,
        )
        with pytest.raises(
            RuntimeError, match="authenticated worker readiness"
        ) as error:
            worker.run(1234, 2345)
        assert isinstance(error.value.__cause__, RuntimeError)
        assert str(error.value.__cause__) == "fixture display refused authentication"
        assert clock.delays == [0.05, 0.05]
        assert_closed(authority)
        assert connection.fileno() >= 0


@pytest.mark.parametrize(
    "damage", ["mode", "hardlink", "empty", "oversized", "directory"]
)
def test_cookie_validation_refuses_unfinished_or_shared_inodes(
    damage: str, tmp_path: Path
) -> None:
    """Accept a private finished cookie, then refuse each unsafe filesystem state."""
    path = tmp_path / "cookie"
    path.write_bytes(b"cookie")
    path.chmod(0o600)
    input_worker.validate_authority(path.stat(), os.getuid())
    if damage == "mode":
        path.chmod(0o640)
    elif damage == "hardlink":
        os.link(path, tmp_path / "alias")
    elif damage == "empty":
        path.write_bytes(b"")
    elif damage == "oversized":
        path.write_bytes(b"x" * 65537)
    else:
        path.unlink()
        path.mkdir(mode=0o600)
    with pytest.raises(RuntimeError, match="unsafe or unfinished session authority"):
        input_worker.validate_authority(path.stat(), os.getuid())


class BrokerProcesses:
    """Run harmless children in place of the stock worker and application."""

    def __init__(self) -> None:
        """Retain children for independent post-cleanup lifetime observations."""
        self.children: list[subprocess.Popen[bytes]] = []

    def __call__(
        self,
        command: list[str],
        *,
        pass_fds: tuple[int, ...] = (),
        preexec_fn: Callable[[], None] | None = None,
    ) -> subprocess.Popen[bytes]:
        """Launch only fixed Python sleepers, never the appliance command supplied."""
        del command
        child = transport.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            pass_fds=pass_fds,
            preexec_fn=preexec_fn,
        )
        self.children.append(child)
        return child


@pytest.mark.skipif(not hasattr(os, "pidfd_open"), reason="Linux pidfds are required")
def test_broker_readiness_failure_publishes_status_and_reaps_both_owned_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Time out an unauthenticated worker and retain failure through owned cleanup."""
    status = tmp_path / "transport.json"
    uinput = tmp_path / "inert-uinput"
    uinput.write_bytes(b"not a device")
    monkeypatch.setattr(transport, "STATUS", status)

    def paths(value: str | Path) -> Path:
        return uinput if str(value) == "/dev/uinput" else Path(value)

    monkeypatch.setattr(transport, "Path", paths)
    processes = BrokerProcesses()
    elapsed = 0.0

    def monotonic() -> float:
        nonlocal elapsed
        elapsed += 10
        return elapsed

    owner = transport.Broker(
        ["fixture-application"],
        (os.getuid(), os.getgid()),
        processes,
        monotonic,
        time.sleep,
    )
    handlers = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with pytest.raises(RuntimeError, match="input transport readiness timed out"):
            owner.run()
        report = json.loads(status.read_text(encoding="utf-8"))
        assert report["ready"] is False
        assert report["worker_connected"] is False
        assert report["sources"] == []
        assert report["error"] == "input transport readiness timed out"
        assert report["strict_device_lifetime_isolation"] is False
        assert len(processes.children) == 2
        assert all(child.poll() is not None for child in processes.children)
        assert owner.connection is None
        assert not status.with_suffix(".partial").exists()
        assert all(
            signal.getsignal(number) == handler for number, handler in handlers.items()
        )
    finally:
        for child in processes.children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


def test_broker_worker_messages_and_closing_deadline_are_observable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publish authenticated connection state and bound orderly worker disconnect."""
    status = tmp_path / "status.json"
    monkeypatch.setattr(transport, "STATUS", status)
    clock = Clock()
    broker = transport.Broker(
        ["fixture"], (1234, 2345), BrokerProcesses(), clock.monotonic, clock.sleep
    )
    parent, worker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent, worker:
        transport.send_message(worker, {"op": "ready"})
        transport.send_message(worker, {"op": "source_ready", "source": "unknown"})
        broker.receive_worker_messages(parent)
        broker.publish()
        report = json.loads(status.read_text(encoding="utf-8"))
        assert report["worker_connected"] is True
        assert report["ready"] is False
        assert broker.acknowledged == set()
        broker.check_deadlines(30)
        worker.shutdown(socket.SHUT_WR)
        broker.receive_worker_messages(parent)
        broker.publish()
        assert (
            json.loads(status.read_text(encoding="utf-8"))["worker_connected"] is False
        )
        broker.check_deadlines(30)
        clock.now = 4
        with pytest.raises(
            RuntimeError, match="worker closed while application remained running"
        ):
            broker.check_deadlines(30)


def test_worker_eof_releases_source_holds_but_not_the_borrowed_socket(
    worker_pair: tuple[input_worker.Worker, socket.socket, Desktop],
) -> None:
    """Treat a pipe's completed final event and EOF as a source disconnect."""
    worker, parent, desktop = worker_pair
    reader, writer = os.pipe()
    try:
        owned = admit(worker, parent, reader)
        os.write(writer, event(1, 30, 1))
    finally:
        os.close(writer)
        os.close(reader)
    assert not worker.drain("keyboard")
    worker.remove("keyboard")
    assert desktop.events == [("key", 30, 1), ("key", 30, 0), ("flush", 0, 0)]
    assert_closed(owned)
    transport.send_message(parent, {"op": "close"})
    assert not worker.message()


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("valid", ""),
        ("not-object", "invalid session metadata"),
        ("identity", "session identity does not match worker"),
        ("display", "session identity does not match worker"),
        ("runtime-type", "invalid session runtime"),
        ("outside-tmp", "unexpected session authority location"),
        ("foreign-name", "unexpected session authority location"),
        ("authority", "unexpected session authority location"),
    ],
)
def test_session_metadata_selects_only_the_matching_private_authority(
    damage: str, reason: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read a bounded local metadata file, never the host's session metadata."""
    path = tmp_path / "metadata.json"
    runtime_directory = "/tmp/gow-full-x86-fixture"  # noqa: S108 - validate only; never allocate this path.
    document: dict[str, object] = {
        "display": ":0",
        "puid": 1234,
        "pgid": 2345,
        "runtime": runtime_directory,
        "xauthority": runtime_directory + "/Xauthority",
    }
    replacements: dict[str, tuple[str, object]] = {
        "identity": ("puid", 99),
        "display": ("display", ":1"),
        "runtime-type": ("runtime", 123),
        "outside-tmp": ("runtime", "/home/retro/gow-full-x86-fixture"),
        "foreign-name": ("runtime", "/tmp/foreign-session"),  # noqa: S108 - validation input only.
        "authority": ("xauthority", "/foreign-cookie"),
    }
    if damage in replacements:
        key, value = replacements[damage]
        document[key] = value
    path.write_text(
        "[]" if damage == "not-object" else json.dumps(document), encoding="utf-8"
    )
    path.chmod(0o644)
    original_open, original_fstat = os.open, os.fstat
    opened: list[int] = []

    def open_metadata(
        name: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        """Redirect only the fixed metadata pathname to the owned fixture."""
        assert name == "/run/gow-full-x86-session.json"
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        opened.append(descriptor)
        return descriptor

    def root_metadata(descriptor: int) -> os.stat_result:
        """Model root ownership at the trusted filesystem metadata boundary."""
        fields = list(original_fstat(descriptor))
        fields[4] = 0
        return os.stat_result(fields)

    monkeypatch.setattr(os, "open", open_metadata)
    monkeypatch.setattr(os, "fstat", root_metadata)
    if damage == "valid":
        assert input_worker.session_runtime(1234, 2345) == Path(runtime_directory)
    else:
        with pytest.raises((RuntimeError, TypeError), match=reason):
            input_worker.session_runtime(1234, 2345)
    assert len(opened) == 1
    with pytest.raises(OSError, match=r"\[Errno 9\]") as error:
        original_fstat(opened[0])
    assert error.value.errno == errno.EBADF
