"""Exercise local transport decisions without native devices or a real display.

C ABI fixtures model external responses only. They do not qualify stock X11,
Pillow, evdev, hotkeygen or physical controller forwarding.
"""

import array
import ctypes
import ctypes.util
import errno
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from collections import deque
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest
from PIL import Image

from batocera_gow.runtime import input_transport as broker
from batocera_gow.runtime import native_diagnostics as diagnostics
from batocera_gow.runtime import transport_probe as probe_module
from batocera_gow.runtime import x11_input

if TYPE_CHECKING:
    # ctypes has no public generic annotation for the pointers its callbacks use.
    from ctypes import _Pointer


class XTestLibrary(ctypes.CDLL):
    """Provide typed C callbacks with independently configurable server limits."""

    # CDLL initialization loads a library; this fixture supplies only local callbacks.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Expose no real shared library or desktop connection."""
        self.version: tuple[int, int] = (2, 1)
        self.bounds: tuple[int, int] = (8, 255)
        self.available = True
        self.opened = True
        self.accept = True
        self.authorities: list[str | None] = []
        self.events: list[tuple[str, int, int]] = []
        self.closes = 0
        self.XOpenDisplay = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(
            self.open
        )
        self.XCloseDisplay = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(self.close)
        integer_pointer = ctypes.POINTER(ctypes.c_int)
        self.XDisplayKeycodes = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, integer_pointer, integer_pointer
        )(self.keycodes)
        self.XFlush = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(self.flush)
        self.XTestQueryExtension = ctypes.CFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            integer_pointer,
            integer_pointer,
            integer_pointer,
            integer_pointer,
        )(self.query)
        self.XTestFakeKeyEvent = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        )(self.key)
        self.XTestFakeButtonEvent = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        )(self.button)
        self.XTestFakeRelativeMotionEvent = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
        )(self.motion)

    def open(self, display: bytes) -> int | None:
        """Sample the temporary authentication environment at connection time."""
        del display
        self.authorities.append(os.environ.get("XAUTHORITY"))
        return 123 if self.opened else None

    def close(self, display: int) -> int:
        """Count connection release without resetting desktop state."""
        del display
        self.closes += 1
        return 0

    def keycodes(
        self,
        display: int,
        minimum: "_Pointer[ctypes.c_int]",
        maximum: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Return external server limits through real C pointer arguments."""
        del display
        minimum[0], maximum[0] = self.bounds
        return 0

    def query(
        self,
        display: int,
        event: "_Pointer[ctypes.c_int]",
        error: "_Pointer[ctypes.c_int]",
        major: "_Pointer[ctypes.c_int]",
        minor: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Publish the configured extension version through its ABI."""
        del display, event, error
        major[0], minor[0] = self.version
        return int(self.available)

    def key(self, display: int, code: int, pressed: int, delay: int) -> int:
        """Retain the effective desktop keycode, not the Linux source code."""
        del display, delay
        self.events.append(("key", code, pressed))
        return int(self.accept)

    def button(self, display: int, code: int, pressed: int, delay: int) -> int:
        """Retain an X pointer-button edge."""
        del display, delay
        self.events.append(("button", code, pressed))
        return int(self.accept)

    def motion(self, display: int, dx: int, dy: int, delay: int) -> int:
        """Retain signed pointer movement after wire-boundary validation."""
        del display, delay
        self.events.append(("motion", dx, dy))
        return int(self.accept)

    def flush(self, display: int) -> int:
        """Return zero, which XFlush does not define as failure."""
        del display
        self.events.append(("flush", 0, 0))
        return 0


@pytest.fixture
def xtest_library(monkeypatch: pytest.MonkeyPatch) -> XTestLibrary:
    """Replace only native library loading with typed C ABI responses."""
    library = XTestLibrary()

    def load(name: str) -> ctypes.CDLL:
        del name
        return library

    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "fixture-" + name)
    monkeypatch.setattr(ctypes, "CDLL", load)
    return library


@pytest.mark.parametrize("previous", [None, "/caller/authority"])
def test_xtest_authentication_is_scoped_and_connection_ownership_is_local(
    xtest_library: XTestLibrary,
    monkeypatch: pytest.MonkeyPatch,
    previous: str | None,
) -> None:
    """Restore caller authentication and reject use after one owned close."""
    if previous is None:
        monkeypatch.delenv("XAUTHORITY", raising=False)
    else:
        monkeypatch.setenv("XAUTHORITY", previous)
    sink = x11_input.XTestSink(":fixture", "/owned/authority")
    try:
        assert xtest_library.authorities == ["/owned/authority"]
        assert os.environ.get("XAUTHORITY") == previous
        sink.key(30, pressed=True)
        sink.button(3, pressed=True)
        sink.motion(-32768, 32767)
        sink.flush()
        assert xtest_library.events == [
            ("key", 38, 1),
            ("button", 3, 1),
            ("motion", -32768, 32767),
            ("flush", 0, 0),
        ]
    finally:
        sink.close()
    sink.close()
    assert xtest_library.closes == 1
    with pytest.raises(RuntimeError, match="sink is closed"):
        sink.flush()


@pytest.mark.parametrize(
    ("fault", "reason", "closes"),
    [
        ("open", "cannot open authenticated", 0),
        ("missing-extension", "does not support XTEST", 1),
        ("old-version", "2.1 or newer", 1),
        ("invalid-bounds", "invalid keycode bounds", 1),
    ],
)
def test_xtest_partial_setup_releases_only_an_acquired_connection(
    xtest_library: XTestLibrary,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    reason: str,
    closes: int,
) -> None:
    """An unusable external server cannot leak a connection or authentication."""
    monkeypatch.setenv("XAUTHORITY", "/caller/cookie")
    if fault == "open":
        xtest_library.opened = False
    elif fault == "missing-extension":
        xtest_library.available = False
    elif fault == "old-version":
        xtest_library.version = (2, 0)
    else:
        xtest_library.bounds = (7, 256)
    with pytest.raises(RuntimeError, match=reason):
        x11_input.XTestSink(":fixture", "/owned/cookie")
    assert xtest_library.closes == closes
    assert os.environ["XAUTHORITY"] == "/caller/cookie"
    assert xtest_library.events == []


@pytest.mark.parametrize(
    "operation", ["key-range", "key-bool", "button-bool", "motion-range"]
)
def test_xtest_invalid_input_never_reaches_the_desktop(
    xtest_library: XTestLibrary, operation: str
) -> None:
    """Validate server bounds and event integers before emitting any edge."""
    xtest_library.bounds = (20, 100)
    sink = x11_input.XTestSink(":fixture", "/owned/cookie")
    try:
        actions = {
            "key-range": (
                partial(sink.key, linux_code=1, pressed=True),
                "Linux key 1 is outside this X display's keycode bounds",
            ),
            "key-bool": (
                partial(sink.key, linux_code=True, pressed=True),
                r"Linux key code must be an integer in 1\.\.247: True",
            ),
            "button-bool": (
                partial(sink.button, x_button=True, pressed=True),
                r"X button must be an integer in 1\.\.255: True",
            ),
            "motion-range": (
                partial(sink.motion, 32768, 0),
                r"relative X motion must be an integer in -32768\.\.32767: 32768",
            ),
        }
        action, reason = actions[operation]
        with pytest.raises(ValueError, match=reason):
            action()
        assert xtest_library.events == []
    finally:
        sink.close()


@pytest.mark.parametrize("operation", ["key", "button", "motion"])
def test_xtest_server_rejection_is_actionable_without_closing_borrowed_state(
    xtest_library: XTestLibrary, operation: str
) -> None:
    """Report failed injection rather than silently accepting a dropped event."""
    sink = x11_input.XTestSink(":fixture", "/owned/cookie")
    xtest_library.accept = False
    try:
        actions = {
            "key": partial(sink.key, 30, pressed=True),
            "button": partial(sink.button, 1, pressed=True),
            "motion": partial(sink.motion, 1, -1),
        }
        action = actions[operation]
        with pytest.raises(RuntimeError, match="XTEST rejected"):
            action()
        assert xtest_library.closes == 0
    finally:
        sink.close()


class PixelLibrary(ctypes.CDLL):
    """Own a small padded BGRX allocation supplied at the external XImage seam."""

    # CDLL initialization loads a library; this fixture owns only its pixel buffer.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Use two known colors and poisoned stride padding, not derived pixels."""
        self.pixels = ctypes.create_string_buffer(
            b"\x00\x00\xff\x00\x00\xff\x00\x00PAD!"
        )
        self.image = diagnostics.XImage()
        self.image.data = ctypes.addressof(self.pixels)
        self.image.bits_per_pixel = 32
        self.image.byte_order = 0
        self.image.bytes_per_line = 12
        self.image.red_mask = 0xFF0000
        self.image.green_mask = 0xFF00
        self.image.blue_mask = 0xFF
        self.dimensions: tuple[int, int] = (2, 1)
        self.destroyed = 0
        self.closed = 0
        self.XDisplayWidth = self.width
        self.XDisplayHeight = self.height
        self.XGetImage = self.get_image
        self.XDestroyImage = self.destroy_image
        self.XCloseDisplay = self.close_display

    def width(self, display: int, screen: int) -> int:
        """Return the externally reported display width."""
        del display, screen
        return self.dimensions[0]

    def height(self, display: int, screen: int) -> int:
        """Return the externally reported display height."""
        del display, screen
        return self.dimensions[1]

    # XGetImage's C ABI fixes all eight arguments; retain their explicit types.
    def get_image(  # noqa: PLR0913, PLR0917
        self,
        display: int,
        root: int,
        x: int,
        y: int,
        width: int,
        height: int,
        mask: int,
        image_format: int,
    ) -> "_Pointer[diagnostics.XImage]":
        """Borrow the allocated image until the caller destroys it."""
        del display, root, x, y, width, height, mask, image_format
        return ctypes.pointer(self.image)

    def destroy_image(self, image: "_Pointer[diagnostics.XImage]") -> int:
        """Record release even on format or publication failure."""
        del image
        self.destroyed += 1
        return 0

    def close_display(self, display: int) -> int:
        """Record the separate connection lifetime."""
        del display
        self.closed += 1
        return 0


class PixelDesktop(diagnostics.Desktop):
    """Use real screenshot/publication rules on a typed external pixel buffer."""

    # Desktop initialization connects to X11; this fixture borrows local pixels.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, library: PixelLibrary
    ) -> None:
        """Borrow fixture pixels while owning the synthetic connection handle."""
        self.x = library
        self.display = 123
        self.screen = 0
        self.root = 456


def test_screenshot_decodes_stride_and_publishes_private_exclusive_png(
    tmp_path: Path,
) -> None:
    """Capture actual PNG bytes and exclude poisoned padding from image content."""
    library = PixelLibrary()
    desktop = PixelDesktop(library)
    path = tmp_path / "capture.png"
    try:
        metadata = desktop.screenshot(path)
        with Image.open(path) as image:
            assert image.size == (2, 1)
            assert image.getpixel((0, 0)) == (255, 0, 0)
            assert image.getpixel((1, 0)) == (0, 255, 0)
        assert metadata["path"] == "capture.png"
        assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert path.stat().st_mode & 0o777 == 0o600
        original = path.read_bytes()
        with pytest.raises(FileExistsError):
            desktop.screenshot(path)
        assert path.read_bytes() == original
        assert not path.with_name("capture.png.partial").exists()
        assert library.destroyed == 2
        assert library.closed == 0
    finally:
        desktop.close()
    desktop.close()
    assert library.closed == 1


@pytest.mark.parametrize(
    "fault", ["dimensions", "depth", "byte-order", "mask", "stride", "data"]
)
def test_screenshot_rejects_untrusted_pixel_layout_and_releases_image(
    tmp_path: Path, fault: str
) -> None:
    """Unsafe pixel memory cannot become apparently valid capture evidence."""
    library = PixelLibrary()
    if fault == "dimensions":
        library.dimensions = (8193, 1)
    elif fault == "depth":
        library.image.bits_per_pixel = 24
    elif fault == "byte-order":
        library.image.byte_order = 1
    elif fault == "mask":
        library.image.red_mask = 0xFF
    elif fault == "stride":
        library.image.bytes_per_line = 7
    else:
        library.image.data = None
    desktop = PixelDesktop(library)
    try:
        with pytest.raises(diagnostics.DiagnosticError):
            desktop.screenshot(tmp_path / "rejected.png")
        assert list(tmp_path.iterdir()) == []
        assert library.destroyed == (0 if fault == "dimensions" else 1)
        assert library.closed == 0
    finally:
        desktop.close()


@pytest.fixture
def capture_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a local child program at the configured diagnostic launcher seam."""
    launcher = tmp_path / "launcher"
    launcher.mkdir()
    (launcher / "native_diagnostics.py").write_text(
        "import json,os,sys,time\n"
        "mode = os.environ['FIXTURE_CAPTURE_MODE']\n"
        "if mode == 'timeout': time.sleep(60)\n"
        "if mode == 'failure':\n"
        "    sys.stderr.write('private-native-detail')\n"
        "    raise SystemExit(7)\n"
        "if mode == 'malformed': print('not json')\n"
        "elif mode == 'array': print('[]')\n"
        "else: print(json.dumps({'path':'fixture.png','width':2,'height':1}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(diagnostics, "RUNTIME_ROOT", launcher)
    return launcher


@pytest.mark.parametrize(
    "mode", ["success", "failure", "malformed", "array", "timeout", "missing"]
)
def test_checkpoint_bounds_real_child_failures_without_disclosing_output(
    capture_launcher: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Parse only successful structured child output; never echo private stderr."""
    monkeypatch.setenv("FIXTURE_CAPTURE_MODE", mode)
    if mode == "missing":
        (capture_launcher / "native_diagnostics.py").unlink()
    if mode == "success":
        assert diagnostics.capture_checkpoint(tmp_path / "destination.png") == {
            "path": "fixture.png",
            "width": 2,
            "height": 1,
        }
    else:
        with pytest.raises((diagnostics.DiagnosticError, ValueError)) as error:
            diagnostics.capture_checkpoint(
                tmp_path / "destination.png", timeout=0.05 if mode == "timeout" else 3
            )
        assert "private-native-detail" not in str(error.value)
        assert "not json" not in str(error.value)
    assert not (tmp_path / "destination.png").exists()


class ObservationDesktop(diagnostics.Desktop):
    """Expose absent frontend readiness or an external observation failure."""

    # Desktop initialization would connect to the host display.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, failure: OSError | ValueError | diagnostics.DiagnosticError | None
    ) -> None:
        """Avoid connecting to the host display."""
        self.failure = failure
        self.closed = False

    def active_pid(self) -> int | None:
        """Return no active owned window, or the configured external failure."""
        if self.failure is not None:
            raise self.failure
        return None

    def close(self) -> None:
        """Record deterministic observer connection cleanup."""
        self.closed = True


@pytest.mark.parametrize(
    "failure", ["timeout", "os", "parser", "diagnostic", "revoked"]
)
def test_frontend_failure_report_is_private_sanitized_and_closes_display(
    capture_launcher: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """No frontend, malformed observation or lease loss can yield passing evidence."""
    del capture_launcher
    errors: dict[str, OSError | ValueError | diagnostics.DiagnosticError | None] = {
        "timeout": None,
        "os": OSError(errno.EIO, "private-window-title"),
        "parser": ValueError("private-content-path"),
        "diagnostic": diagnostics.DiagnosticError("approved descendant unavailable"),
        "revoked": InterruptedError("native permission revoked"),
    }
    expected = {
        "timeout": "Normal frontend/ready worker/final source deadline expired",
        "os": "Frontend runtime observation unavailable",
        "parser": "Frontend runtime observation malformed",
        "diagnostic": "approved descendant unavailable",
        "revoked": "native permission revoked",
    }
    desktop = ObservationDesktop(errors[failure])
    elapsed = 0.0

    def now() -> float:
        return elapsed

    def sleep(seconds: float) -> None:
        nonlocal elapsed
        elapsed += seconds

    monkeypatch.setenv("FIXTURE_CAPTURE_MODE", "failure")
    monkeypatch.delenv("GOW_NATIVE_LEASE", raising=False)
    monkeypatch.setattr(os, "getuid", lambda: 1234)
    monkeypatch.setattr(diagnostics, "Desktop", lambda: desktop)
    monkeypatch.setattr(time, "monotonic", now)
    monkeypatch.setattr(time, "sleep", sleep)
    # Readiness is absent at this external file boundary, not a fabricated ES pass.
    monkeypatch.setattr(diagnostics, "transport_ready", lambda _path: None)
    assert diagnostics.observe_frontend(tmp_path, 0.1) == 1
    assert desktop.closed
    report = json.loads((tmp_path / "frontend-probe.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["errors"] == [expected[failure]]
    assert report["captures"] == [
        {"status": "unavailable", "checkpoint": "frontend-failure"}
    ]
    assert "private-" not in json.dumps(report)
    assert (tmp_path / "selected.log").read_text(encoding="utf-8") == (
        "normal frontend observation: failed\n" + expected[failure] + "\n"
    )
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in tmp_path.glob("*.json"))


class PipeSource(broker.Source):
    """Own real pipe descriptors at the broker's explicit device boundary."""

    # Source initialization acquires a device; these descriptors are already owned.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, name: str, reader: int, creator: int, *, final: bool = True
    ) -> None:
        """Transfer only fixture pipe handles, without touching devices or sysfs."""
        self.sysname = name
        self.reader = reader
        self.creator = creator
        self.node = None
        self.udev = None
        self.final = final
        self.sent = False
        self.alive = True
        self.closed = False
        self.close_failure = False

    def valid(self) -> bool:
        """Expose an independently controlled creator-lifetime observation."""
        return self.alive

    def close(self) -> None:
        """Release actual owned descriptors before reporting a teardown failure."""
        was_closed = self.closed
        super().close()
        self.closed = True
        if self.close_failure and not was_closed:
            message = "source withdrawal failed"
            raise OSError(message)

    def summary(self) -> dict[str, object]:
        """Publish only consumer-facing identity, never descriptor numbers."""
        return {"sysname": self.sysname, "role": "final" if self.final else "semantic"}


@pytest.fixture
def local_broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> broker.Broker:
    """Configure a broker whose status writes stay in an owned temporary directory."""
    monkeypatch.setattr(broker, "STATUS", tmp_path / "status.json")
    return broker.Broker(
        ["fixture"], (1234, 2345), broker.start_process, time.monotonic, time.sleep
    )


def test_broker_handoff_waits_for_live_final_then_revocation_closes_its_pins(
    local_broker: broker.Broker,
) -> None:
    """Transfer usable descriptors only after authentication and revoke once."""
    with ExitStack() as cleanup:
        parent, worker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        cleanup.enter_context(parent)
        cleanup.enter_context(worker)
        reader, writer = os.pipe()
        cleanup.callback(os.close, writer)
        source = PipeSource("input7", reader, os.dup(reader))
        cleanup.callback(source.close)
        local_broker.sources["input7"] = source
        local_broker.connection = parent
        local_broker.handoff_sources(parent)
        worker.settimeout(0)
        with pytest.raises(BlockingIOError):
            worker.recv(8192)
        broker.send_message(worker, {"op": "ready"})
        local_broker.receive_worker_messages(parent)
        source.alive = False
        local_broker.handoff_sources(parent)
        with pytest.raises(BlockingIOError):
            worker.recv(8192)
        source.alive = True
        local_broker.handoff_sources(parent)
        payload, ancillary, _, _ = worker.recvmsg(
            8192, socket.CMSG_SPACE(array.array("i").itemsize)
        )
        assert json.loads(payload) == {"op": "add", "source": "input7"}
        transferred = array.array("i")
        transferred.frombytes(ancillary[0][2])
        assert len(transferred) == 1
        duplicate = transferred[0]
        cleanup.callback(os.close, duplicate)
        os.write(writer, b"independent input bytes")
        assert os.read(duplicate, 64) == b"independent input bytes"
        local_broker.handoff_sources(parent)
        with pytest.raises(BlockingIOError):
            worker.recv(8192)
        broker.send_message(worker, {"op": "source_ready", "source": "input7"})
        local_broker.receive_worker_messages(parent)
        local_broker.publish()
        assert json.loads(broker.STATUS.read_text(encoding="utf-8"))["ready"] is True
        local_broker.revoke("input7")
        assert json.loads(worker.recv(8192)) == {"op": "remove", "source": "input7"}
        assert source.closed
        assert local_broker.acknowledged == set()
        assert local_broker.sources == {}
        with pytest.raises(
            OSError, match=r"^\[Errno 9\] Bad file descriptor$"
        ) as error:
            os.fstat(reader)
        assert error.value.errno == errno.EBADF
        os.fstat(duplicate)


def test_broker_socket_failure_does_not_prevent_semantic_source_revocation(
    local_broker: broker.Broker,
) -> None:
    """A dead worker cannot retain source ownership or a stale readiness claim."""
    reader, writer = os.pipe()
    source = PipeSource("semantic", reader, os.dup(reader), final=False)
    parent, worker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent:
        worker.close()
        local_broker.connection = parent
        local_broker.worker_ready = True
        local_broker.sources["semantic"] = source
        local_broker.acknowledged.add("semantic")
        try:
            with pytest.raises(BrokenPipeError):
                local_broker.revoke("semantic")
            assert source.closed
            assert local_broker.sources == {}
            assert local_broker.acknowledged == set()
            with pytest.raises(
                OSError, match=r"^\[Errno 9\] Bad file descriptor$"
            ) as error:
                os.fstat(reader)
            assert error.value.errno == errno.EBADF
        finally:
            source.close()
            os.close(writer)


def test_broker_cleanup_attempts_every_source_and_publishes_failure(
    local_broker: broker.Broker,
) -> None:
    """One withdrawal failure cannot leak later sources or leave ready status."""
    with ExitStack() as cleanup:
        sources: list[PipeSource] = []
        descriptors: list[int] = []
        for name in ("first", "second"):
            reader, writer = os.pipe()
            cleanup.callback(os.close, writer)
            source = PipeSource(name, reader, os.dup(reader))
            sources.append(source)
            cleanup.callback(source.close)
            descriptors.extend(
                [reader, source.creator if source.creator is not None else -1]
            )
            local_broker.sources[name] = source
            local_broker.acknowledged.add(name)
        sources[0].close_failure = True
        with pytest.raises(OSError, match="source withdrawal failed"):
            local_broker.finish_sources()
        assert all(source.closed for source in sources)
        assert local_broker.sources == {}
        assert local_broker.acknowledged == set()
        report = json.loads(broker.STATUS.read_text(encoding="utf-8"))
        assert report["ready"] is False
        assert report["error"] == "source withdrawal failed"
        for descriptor in descriptors:
            with pytest.raises(
                OSError, match=r"^\[Errno 9\] Bad file descriptor$"
            ) as error:
                os.fstat(descriptor)
            assert error.value.errno == errno.EBADF


@pytest.mark.parametrize("packet", [b"[]", b'{"error":"worker rejected source"}'])
def test_broker_rejects_worker_failure_before_publishing_readiness(
    local_broker: broker.Broker, packet: bytes
) -> None:
    """Malformed or failed worker messages cannot silently establish readiness."""
    parent, worker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent, worker:
        worker.send(packet)
        with pytest.raises((TypeError, RuntimeError)):
            local_broker.receive_worker_messages(parent)
        assert not local_broker.worker_ready
        assert local_broker.acknowledged == set()


class EventLibrary(ctypes.CDLL):
    """Deliver typed XEvent buffers at the receiver's external queue boundary."""

    # CDLL initialization loads a library; this fixture supplies local event callbacks.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, events: list[probe_module.XEvent]
    ) -> None:
        """Retain a finite independent sequence of server observations."""
        self.events = deque(events)
        self.closes = 0
        self.destroy_failure = False
        self.XPending = self.pending
        self.XNextEvent = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(probe_module.XEvent)
        )(self.next_event)
        self.XDestroyWindow = self.destroy
        self.XCloseDisplay = self.close_display

    def pending(self, display: int) -> int:
        """Report whether another external event is queued."""
        del display
        return len(self.events)

    def next_event(
        self, display: int, destination: "_Pointer[probe_module.XEvent]"
    ) -> int:
        """Copy one external event into the consumer's actual native buffer."""
        del display
        destination[0] = self.events.popleft()
        return 0

    def destroy(self, display: int, window: int) -> int:
        """Optionally fail window release before display cleanup."""
        del display, window
        if self.destroy_failure:
            message = "window teardown failed"
            raise OSError(message)
        return 0

    def close_display(self, display: int) -> int:
        """Count owned display releases."""
        del display
        self.closes += 1
        return 0


class EventReceiver(probe_module.Receiver):
    """Retain production event filtering and lifetime with no native connection."""

    # Receiver initialization opens X11 and creates a real window.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, library: EventLibrary
    ) -> None:
        """Own a synthetic window and diagnostic key allowlist."""
        self.x = library
        self.display = 123
        self.window = 456
        self.names = {38: "Control_L", 96: "F12"}
        self.origin = time.monotonic()
        self.unknown = 0


def server_event(
    kind: int, code: int = 0, *, window: int = 456, synthetic: bool = False
) -> probe_module.XEvent:
    """Build external server data independently of receiver output dictionaries."""
    event = probe_module.XEvent()
    event.type = kind
    event.key.window = window
    event.key.send_event = int(synthetic)
    event.key.keycode = code
    event.key.time = 1234
    event.key.x_root = -12
    event.key.y_root = 34
    return event


def test_receiver_discards_private_keys_but_counts_unexpected_semantic_events() -> None:
    """Keep ordered allowlisted output while retaining no unrelated key identity."""
    library = EventLibrary(
        [
            server_event(12),
            server_event(2, 38),
            server_event(2, 65),
            server_event(4, 2),
            server_event(4, 1),
            server_event(6),
            server_event(3, 38),
            server_event(5, 1),
        ]
    )
    receiver = EventReceiver(library)
    try:
        rows = receiver.read()
        assert probe_module.keys(rows) == [
            ["Control_L", "press"],
            ["Control_L", "release"],
        ]
        assert probe_module.buttons(rows) == [[1, "press"], [1, "release"]]
        assert [(row["x"], row["y"]) for row in rows if row["kind"] == "motion"] == [
            (-12, 34)
        ]
        assert receiver.unknown == 2
        assert len(rows) == 5
        assert all(row["server_time_ms"] == 1234 for row in rows)
        assert receiver.read() == []
        assert all("keycode" not in row for row in rows)
    finally:
        receiver.close()
    receiver.close()
    assert library.closes == 1


@pytest.mark.parametrize("fault", ["foreign-window", "synthetic"])
def test_receiver_refuses_events_not_from_its_authenticated_owned_window(
    fault: str,
) -> None:
    """Neither SendEvent spoofing nor a foreign window qualifies as input."""
    library = EventLibrary(
        [
            server_event(
                2,
                38,
                window=999 if fault == "foreign-window" else 456,
                synthetic=fault == "synthetic",
            )
        ]
    )
    receiver = EventReceiver(library)
    try:
        with pytest.raises(probe_module.ProbeError, match="owned authenticated window"):
            receiver.read()
    finally:
        receiver.close()
    assert library.closes == 1


def test_receiver_destroy_failure_still_closes_connection_once() -> None:
    """Release display ownership even when its window cannot be destroyed."""
    library = EventLibrary([])
    library.destroy_failure = True
    receiver = EventReceiver(library)
    with pytest.raises(OSError, match="window teardown failed"):
        receiver.close()
    receiver.close()
    assert library.closes == 1
    assert receiver.display is None


class AtomLibrary(ctypes.CDLL):
    """Supply known atom identities without loading an X11 shared library."""

    # CDLL initialization loads a library; atom identities here are local constants.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Keep distinct normal, fullscreen and modal atoms."""
        self.XInternAtom = self.atom

    def atom(self, display: int, name: bytes, only_existing: int) -> int:
        """Resolve fixture properties using independently chosen server identities."""
        del display, only_existing
        return {
            b"_NET_WM_WINDOW_TYPE_NORMAL": 11,
            b"_NET_WM_STATE_FULLSCREEN": 12,
            b"_NET_WM_STATE_MODAL": 13,
        }[name]


class PropertyDesktop(diagnostics.Desktop):
    """Retain production render qualification over explicit external properties."""

    # Desktop initialization connects to X11; this fixture supplies local properties.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Start with a nonmodal fullscreen game window owned by PID 1234."""
        self.x = AtomLibrary()
        self.display = 123
        self.root = 1
        self.properties: dict[tuple[int, str], bytes | tuple[int, ...] | None] = {
            (1, "_NET_ACTIVE_WINDOW"): (2,),
            (2, "_NET_WM_PID"): (1234,),
            (2, "_NET_WM_WINDOW_TYPE"): (11,),
            (2, "_NET_WM_STATE"): (12,),
            (2, "_NET_WM_NAME"): b"private selected game title",
        }
        self.lose_focus = False
        self.active_reads = 0

    def property_value(
        self, window: int, name: str, *, length: int = 1
    ) -> bytes | tuple[int, ...] | None:
        """Sample external properties, including a focus change during inspection."""
        del length
        if name == "_NET_ACTIVE_WINDOW":
            self.active_reads += 1
            if self.lose_focus and self.active_reads > 1:
                return (99,)
        return self.properties.get((window, name))


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "pid",
        "type",
        "windowed",
        "modal",
        "transient",
        "startup-title",
        "empty-title",
        "focus",
    ],
)
def test_render_qualification_requires_stable_owned_fullscreen_game_window(
    fault: str,
) -> None:
    """A title, active process or fullscreen property alone cannot qualify output."""
    desktop = PropertyDesktop()
    changes: dict[str, tuple[str, bytes | tuple[int, ...] | None]] = {
        "pid": ("_NET_WM_PID", (999,)),
        "type": ("_NET_WM_WINDOW_TYPE", (11, 14)),
        "windowed": ("_NET_WM_STATE", ()),
        "modal": ("_NET_WM_STATE", (12, 13)),
        "transient": ("WM_TRANSIENT_FOR", (99,)),
        "startup-title": ("_NET_WM_NAME", b"DuckStation setup"),
        "empty-title": ("_NET_WM_NAME", b"  "),
    }
    if fault in changes:
        name, value = changes[fault]
        desktop.properties[(2, name)] = value
    desktop.lose_focus = fault == "focus"
    assert desktop.render_window(1234) is (fault == "none")


@pytest.mark.parametrize("title", [b"xemu | v0.8.134", b"xemu", b"private game title"])
def test_xemu_window_requires_the_pinned_backend_title(title: bytes) -> None:
    """Do not accept an arbitrary normal fullscreen window as the pinned SDL backend."""
    desktop = PropertyDesktop()
    desktop.properties[(2, "_NET_WM_NAME")] = title
    assert desktop.active_pid() == 1234
    assert desktop.render_window(1234, application="xemu") is (
        title == b"xemu | v0.8.134"
    )


class FileNode(broker.EventNode):
    """Own a regular fixture inode solely for acquisition-failure cleanup."""

    # EventNode initialization creates a character device, not this regular file.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, path: Path
    ) -> None:
        """Create and pin a file without allocating a character device."""
        path.write_bytes(b"owned-event-placeholder")
        self.path = path
        self.created = True
        self.identity = broker.node_identity(path.lstat())


class IncompleteSource(broker.Source):
    """Fail after a real reader is acquired at the external device boundary."""

    allocated: ClassVar[list[int]]
    path: ClassVar[Path]

    def acquire(self, gid: int, *, suite: bool) -> None:
        """Leave partial resources for the Source constructor to unwind."""
        del gid, suite
        self.node = FileNode(self.path)
        self.reader = self.node.open()
        self.allocated.append(self.reader)
        message = "external device changed after opening"
        raise OSError(message)


def test_source_acquisition_failure_closes_transferred_fds_but_borrows_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partially acquired reader cannot leak its creator pin or filesystem node."""
    allocated: list[int] = []
    path = tmp_path / "owned-node"
    monkeypatch.setattr(IncompleteSource, "path", path, raising=False)
    monkeypatch.setattr(IncompleteSource, "allocated", allocated, raising=False)
    process = broker.OwnedProcess(os.getpid())
    reader, writer = os.pipe()
    try:
        with pytest.raises(OSError, match="external device changed"):
            IncompleteSource(process, (17, reader), "input7", os.getgid())
        assert len(allocated) == 1
        assert not path.exists()
        for descriptor in [reader, *allocated]:
            with pytest.raises(
                OSError, match=r"^\[Errno 9\] Bad file descriptor$"
            ) as error:
                os.fstat(descriptor)
            assert error.value.errno == errno.EBADF
        assert process.valid()
        os.fstat(process.fd)
        os.fstat(writer)
    finally:
        process.close()
        os.close(writer)


@pytest.mark.parametrize(
    "failure", ["selection", "existing-report", "relative-results", "absent-results"]
)
def test_probe_entrypoint_refuses_before_native_allocation_and_retains_failure(
    tmp_path: Path, failure: str
) -> None:
    """Exercise real installed CLI refusal, cleanup reporting and exclusive output."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GOW_INPUT_TRIAL_", "GOW_NATIVE_"))
    }
    environment["GOW_INPUT_TRIAL_RESULTS"] = str(tmp_path)
    report = tmp_path / "transport-probe.json"
    if failure == "selection":
        environment["GOW_INPUT_TRIAL_CASE"] = "not-a-supported-scenario"
        reason = "must name a supported receiver scenario"
    elif failure == "existing-report":
        report.write_bytes(b"operator evidence must survive")
        reason = "refusing to overwrite"
    elif failure == "relative-results":
        environment["GOW_INPUT_TRIAL_RESULTS"] = "relative-results"
        reason = "must be an absolute results directory"
    else:
        del environment["GOW_INPUT_TRIAL_RESULTS"]
        reason = "must be an absolute results directory"
    completed = subprocess.run(
        [sys.executable, "-m", "batocera_gow.runtime.transport_probe"],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        check=False,
    )
    assert completed.returncode == 1
    if failure == "existing-report":
        assert report.read_bytes() == b"operator evidence must survive"
        assert "cannot publish transport diagnostic" in completed.stderr
        assert not report.with_name("transport-probe.json.partial").exists()
        return
    document = json.loads(
        report.read_text(encoding="utf-8") if report.exists() else completed.stderr
    )
    assert document["status"] == "failed"
    assert any(reason in error for error in document["errors"])
    assert document["cases"] == []
    assert document["cleanup"] == {"status": "passed", "errors": []}
    assert document["not_run_cases"] == [
        "stock_combo_exit_held_and_pointer_reset",
        "stock_context_pointer_button",
        "context_switch_without_semantic_leakage",
        "held_graceful_source_removal_and_recreation",
        "stock_command_once_per_stock_release",
    ]


class DaemonProbe(probe_module.Probe):
    """Read an owned child's identity at the external supervisor status boundary."""

    def status(self) -> dict[str, object]:
        """Expose semantic identity only while the allocated child is alive."""
        process = self.evmapy
        return {
            "sources": []
            if process is None or process.poll() is not None
            else [
                {
                    "name": "evmapy",
                    "source_pid": process.pid,
                    "sysname": "input42",
                    "node": "/fixture/event42",
                    "role": "semantic",
                },
            ],
        }


@pytest.mark.parametrize("subscription", ["owned", "foreign", "multiple", "early-exit"])
def test_daemon_startup_requires_unique_owned_subscription_and_reaps_partial_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subscription: str,
) -> None:
    """Require a unique owned controller subscription on a real local socket."""
    runtime = tmp_path / "evmapy"
    runtime.mkdir()
    work = tmp_path / "scratch"
    work.mkdir()
    owner = DaemonProbe()
    owner.work = work
    owner.work_identity = probe_module.file_identity(work)
    owner.pad_node = "/fixture/event7"
    monkeypatch.setattr(probe_module, "EVMAPY", runtime)
    monkeypatch.delenv("GOW_NATIVE_LEASE", raising=False)
    monkeypatch.delenv("GOW_NATIVE_RESULTS", raising=False)
    children: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    program = (
        "import json,pathlib,signal,socket,sys\n"
        "directory=pathlib.Path(sys.argv[1])\n"
        "mode=sys.argv[2]\n"
        "if mode == 'early-exit': raise SystemExit(7)\n"
        "connection=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)\n"
        "connection.bind(str(directory/'evmapy.socket'))\n"
        "(directory/'ready').write_bytes(b'ready')\n"
        "signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))\n"
        "while True:\n"
        "    _,address=connection.recvfrom(65536)\n"
        "    paths=['/fixture/event7'] if mode == 'owned' else ['/foreign/event']\n"
        "    if mode == 'multiple': paths.append('/fixture/event7')\n"
        "    payload=json.dumps([{'path':p} for p in paths]).encode()\n"
        "    connection.sendto(payload,address)\n"
    )

    def start(
        command: list[str], *, stdout: int, stderr: int
    ) -> subprocess.Popen[bytes]:
        assert command == ["/usr/bin/evmapy"]
        child = original_popen(
            [sys.executable, "-c", program, str(runtime), subscription],
            stdout=stdout,
            stderr=stderr,
        )
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", start)
    try:
        if subscription == "owned":
            owner.start_evmapy()
            assert owner.semantic_sysname == "input42"
            assert owner.source_records == [
                {
                    "role": "semantic",
                    "name": "evmapy",
                    "sysname": "input42",
                    "node": "/fixture/event42",
                    "source_pid": children[0].pid,
                }
            ]
            assert children[0].poll() is None
            owner.stop_evmapy(graceful=True)
            assert owner.process_records == [
                {
                    "pid": children[0].pid,
                    "returncode": 0,
                    "forced_kill": False,
                }
            ]
        else:
            with pytest.raises(
                probe_module.ProbeError,
                match=r"exited before readiness|subscribed outside",
            ):
                owner.start_evmapy()
            assert owner.source_records == []
    finally:
        try:
            owner.close()
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
    assert len(children) == 1
    assert children[0].poll() is not None
    assert list(runtime.iterdir()) == []
    assert not work.exists()
