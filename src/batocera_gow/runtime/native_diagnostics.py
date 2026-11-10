"""Authenticated owned-display capture and packaged native inspection.

The inspect command reads identities only. The frontend observer is launched as
an app-UID child of the ordinary frontend, never by Docker exec.
"""

import contextlib
import ctypes
import hashlib
import json
import math
import os
import select
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .resources import RUNTIME_ROOT

if TYPE_CHECKING:
    from collections.abc import Callable

    # ctypes exposes no public generic pointer annotation for its ABI pointers.
    from ctypes import _Pointer

    _XErrorCallback = Callable[[int, _Pointer["XErrorEvent"]], int]


_MAX_LEASE_BYTES = 4096
_MAX_DISPLAY_DIMENSION = 8192
_MAX_STRIDE_PADDING = 4096
_PROPERTY_LONG_BITS = 32
_PROPERTY_BYTE_BITS = 8
_BYTES_PER_LONG = 4
_MAX_PROPERTY_LONGS = 1024
_MAX_ATOM_LONGS = 16
_BAD_WINDOW = 3
_GET_PROPERTY = 20
_PROC_START_FIELD = 19
_SECCOMP_FILTER = 2
_FRONTEND_ALARM_GRACE = 15
_ANCESTRY_ERROR = "Capability-free non-root app ancestry not observed"
_APP_IDENTITY_ERROR = "App real/effective/saved identity differs"
_CREDENTIAL_KEYS = (
    "Uid",
    "Gid",
    "Groups",
    "CapInh",
    "CapEff",
    "CapPrm",
    "CapAmb",
    "NoNewPrivs",
)
_ID_SLOTS = 4
_OWNER_PERMISSION_SHIFT = 6
_GROUP_PERMISSION_SHIFT = 3
_READ_WRITE_PERMISSION = 0o6
_SESSION_ARGUMENTS = [b"/opt/gow-full-x86/runtime.py", b"session"]
_SESSION_ARGUMENT_COUNT = len(_SESSION_ARGUMENTS)
_ZPIXMAP = 2
_RGB_MASKS = (0xFF0000, 0xFF00, 0xFF)
_CAPTURE_ARGUMENT_COUNT = 2
# Stock ES publishes this fixed flag inside the disposable session's private /tmp.
# frontend_ready_flag requires an app-owned regular file before accepting it.
_FRONTEND_READY_NAME = "/tmp/emulationstation.ready"  # noqa: S108


class DiagnosticError(RuntimeError):
    """An actual runtime prerequisite or observation was not established."""


def object_value(value: object) -> dict[str, object]:
    """Require an object and retain its values without unchecked JSON typing.

    JSON keys are strings; non-JSON callers retain the existing string-key
    normalization. Values remain opaque until their consuming boundary checks them.
    """
    if not isinstance(value, dict):
        message = "Diagnostic object missing"
        raise DiagnosticError(message)
    return {str(key): item for key, item in value.items()}


def _require_lease(path: Path) -> None:
    """Validate one bounded root-controlled lease without following a symlink."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_size > _MAX_LEASE_BYTES
        ):
            message = "Unsafe native lease file"
            raise DiagnosticError(message)
        value = object_value(json.loads(stream.read(_MAX_LEASE_BYTES + 1)))
    expiry = value.get("expires")
    if (
        isinstance(expiry, bool)
        or not isinstance(expiry, (int, float))
        or not math.isfinite(expiry)
        or time.monotonic() >= expiry
    ):
        message = "Native input permission expired or was revoked"
        raise InterruptedError(message)


def input_permitted() -> None:
    """Refuse further input when the coordinator's renewable lease is lost.

    A legacy probe without GOW_NATIVE_LEASE retains its existing operator gate.
    Release and cleanup operations must not call this guard.
    """
    name = os.environ.get("GOW_NATIVE_LEASE")
    if name is None:
        return
    try:
        _require_lease(Path(name))
    except (OSError, ValueError, DiagnosticError) as error:
        message = "Native input permission unavailable"
        raise InterruptedError(message) from error


def publish_bytes(path: Path, value: bytes) -> None:
    """Publish a complete private regular file atomically without replacement.

    The caller owns the parent directory. A mode0600 exclusive temporary file
    is synced before linking the final name; existing final or partial names
    are never overwritten. Only the temporary file created here is removed.

    Raises:
        OSError: If creation, writing, publication or temporary cleanup fails.
    """
    temporary = path.with_name(path.name + ".partial")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink()


def publish_json(path: Path, value: dict[str, object]) -> None:
    """Serialize a private observation before creating any evidence file.

    Serialization failure leaves the directory untouched. Publication uses
    ``publish_bytes`` and therefore never replaces existing evidence.
    """
    publish_bytes(
        path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    )


def publish_selected_log(directory: Path, lines: list[str]) -> None:
    """Publish caller-selected observations, never raw environment/config dumps.

    The caller must select nonsecret diagnostic lines. This function does not
    redact arbitrary input and never reads application logs itself.
    """
    publish_bytes(directory / "selected.log", ("\n".join(lines) + "\n").encode("utf-8"))


class XImage(ctypes.Structure):
    """The stable libX11 image prefix needed for explicit pixel validation."""

    # ctypes' metaclass creates and initializes these native field descriptors.
    width: int  # pyright: ignore[reportUninitializedInstanceVariable]
    height: int  # pyright: ignore[reportUninitializedInstanceVariable]
    xoffset: int  # pyright: ignore[reportUninitializedInstanceVariable]
    image_format: int  # pyright: ignore[reportUninitializedInstanceVariable]
    data: int | None  # pyright: ignore[reportUninitializedInstanceVariable]
    byte_order: int  # pyright: ignore[reportUninitializedInstanceVariable]
    bitmap_unit: int  # pyright: ignore[reportUninitializedInstanceVariable]
    bitmap_bit_order: int  # pyright: ignore[reportUninitializedInstanceVariable]
    bitmap_pad: int  # pyright: ignore[reportUninitializedInstanceVariable]
    depth: int  # pyright: ignore[reportUninitializedInstanceVariable]
    bytes_per_line: int  # pyright: ignore[reportUninitializedInstanceVariable]
    bits_per_pixel: int  # pyright: ignore[reportUninitializedInstanceVariable]
    red_mask: int  # pyright: ignore[reportUninitializedInstanceVariable]
    green_mask: int  # pyright: ignore[reportUninitializedInstanceVariable]
    blue_mask: int  # pyright: ignore[reportUninitializedInstanceVariable]

    _fields_ = (
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("xoffset", ctypes.c_int),
        ("image_format", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("byte_order", ctypes.c_int),
        ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int),
        ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int),
        ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong),
        ("blue_mask", ctypes.c_ulong),
    )


class XErrorEvent(ctypes.Structure):
    """Public Xlib error-event ABI, including native-width resource and serial."""

    # ctypes' metaclass creates and initializes these native field descriptors.
    event_type: int  # pyright: ignore[reportUninitializedInstanceVariable]
    display: int | None  # pyright: ignore[reportUninitializedInstanceVariable]
    resourceid: int  # pyright: ignore[reportUninitializedInstanceVariable]
    serial: int  # pyright: ignore[reportUninitializedInstanceVariable]
    error_code: int  # pyright: ignore[reportUninitializedInstanceVariable]
    request_code: int  # pyright: ignore[reportUninitializedInstanceVariable]
    minor_code: int  # pyright: ignore[reportUninitializedInstanceVariable]

    _fields_ = (
        ("event_type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    )


_X_ERROR_HANDLER = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(XErrorEvent)
)
# XSetErrorHandler is process-global, not per Desktop or Display. Serialize our
# temporary scopes; unrelated Xlib users still receive their previous handler.
_X11_ERROR_LOCK = threading.Lock()


class _PropertyRequest:
    """Keep the exact request and previous handler alive during native dispatch."""

    # XSetErrorHandler supplies this after installing our callback; ready gates reads.
    previous: "_XErrorCallback"  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, display: int, window: int, serial: int) -> None:
        """Pin one connection/window/request triple until handler restoration."""
        self.display = display
        self.window = window
        self.serial = serial
        self.ready = threading.Event()


_x11_property_request: _PropertyRequest


def _property_error(display: int, event: "_Pointer[XErrorEvent]") -> int:
    """Ignore only this request's BadWindow and delegate every other error."""
    request = _x11_property_request
    # XSetErrorHandler installs before it returns the old pointer. A foreign
    # thread entering in that interval must wait for the original policy.
    request.ready.wait()
    error = event.contents
    if (
        display == request.display
        and error.display == request.display
        and error.serial == request.serial
        and error.resourceid == request.window
        and error.error_code == _BAD_WINDOW
        and error.request_code == _GET_PROPERTY
        and error.minor_code == 0
    ):
        return 0
    return int(request.previous(display, event))


# The C callback must outlive a temporary scope: another native thread can
# already hold its address when restoration removes it from Xlib.
_X11_PROPERTY_ERROR = _X_ERROR_HANDLER(_property_error)


class Desktop:
    """Open only the authenticated display inherited from the owned app."""

    def __init__(self) -> None:
        """Own one connection; refuse root or an unauthenticated session.

        Raises:
            DiagnosticError: If the inherited environment or X11 authentication
                does not identify the ordinary application display.
        """
        if (
            os.getuid() == 0
            or os.environ.get("DISPLAY") != ":0"
            or not os.environ.get("XAUTHORITY")
        ):
            message = "Expected non-root authenticated owned X11 environment"
            raise DiagnosticError(message)
        self.x = ctypes.CDLL("libX11.so.6")
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XDefaultScreen.argtypes = [ctypes.c_void_p]
        self.x.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XRootWindow.restype = ctypes.c_ulong
        self.x.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.x.XInternAtom.restype = ctypes.c_ulong
        self.x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        self.x.XGetWindowProperty.restype = ctypes.c_int
        self.x.XNextRequest.argtypes = [ctypes.c_void_p]
        self.x.XNextRequest.restype = ctypes.c_ulong
        self.x.XLockDisplay.argtypes = [ctypes.c_void_p]
        self.x.XLockDisplay.restype = None
        self.x.XUnlockDisplay.argtypes = [ctypes.c_void_p]
        self.x.XUnlockDisplay.restype = None
        self.x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XSync.restype = ctypes.c_int
        self.x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        self.x.XSetErrorHandler.restype = ctypes.c_void_p
        self.x.XFree.argtypes = [ctypes.c_void_p]
        self.x.XGetImage.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_int,
        ]
        self.x.XGetImage.restype = ctypes.POINTER(XImage)
        self.x.XDestroyImage.argtypes = [ctypes.POINTER(XImage)]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        connection: object = self.x.XOpenDisplay(None)
        if not isinstance(connection, int) or not connection:
            message = "Cannot authenticate to owned X11 display"
            raise DiagnosticError(message)
        self.display: int | None = connection
        self.screen = int(self.x.XDefaultScreen(self.display))
        self.root = int(self.x.XRootWindow(self.display, self.screen))

    def property_value(
        self, window: int, name: str, *, length: int = 1
    ) -> bytes | tuple[int, ...] | None:
        """Read a bounded complete property under the exact BadWindow scope.

        Text and atom arrays use the same authenticated connection and request
        ownership as scalar EWMH identities. Destroyed windows stay unavailable.
        """
        global _x11_property_request  # noqa: PLW0603

        # XSetErrorHandler requires a process-global callback and native callers
        # must observe the same pinned request throughout this serialized scope.
        if self.display is None:
            message = "Owned X11 display connection is closed"
            raise DiagnosticError(message)
        if not 0 < length <= _MAX_PROPERTY_LONGS:
            message = "Invalid owned X11 property read bound"
            raise DiagnosticError(message)

        actual, count, remaining = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        format_ = ctypes.c_int()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        atom = int(self.x.XInternAtom(self.display, name.encode(), 1))
        if not atom:
            return None
        with _X11_ERROR_LOCK:
            self.x.XLockDisplay(self.display)
            try:
                # Deliver earlier queued errors under the unchanged policy.
                self.x.XSync(self.display, 0)
                request = _PropertyRequest(
                    self.display, window, int(self.x.XNextRequest(self.display))
                )
                _x11_property_request = request
                previous_address = self.x.XSetErrorHandler(
                    ctypes.cast(_X11_PROPERTY_ERROR, ctypes.c_void_p)
                )
                # Xlib returns its actual default handler, never a NULL fallback.
                request.previous = _X_ERROR_HANDLER(previous_address)
                request.ready.set()
                try:
                    status = int(
                        self.x.XGetWindowProperty(
                            self.display,
                            window,
                            atom,
                            0,
                            length,
                            0,
                            0,
                            ctypes.byref(actual),
                            ctypes.byref(format_),
                            ctypes.byref(count),
                            ctypes.byref(remaining),
                            ctypes.byref(data),
                        )
                    )
                finally:
                    self.x.XSetErrorHandler(previous_address)
            finally:
                self.x.XUnlockDisplay(self.display)
        try:
            if status == 0 and remaining.value == 0 and data:
                if format_.value == _PROPERTY_LONG_BITS and count.value <= length:
                    values = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))
                    return tuple(int(values[index]) for index in range(count.value))
                if (
                    format_.value == _PROPERTY_BYTE_BITS
                    and count.value <= length * _BYTES_PER_LONG
                ):
                    return ctypes.string_at(data, count.value)
            return None
        finally:
            if data:
                self.x.XFree(data)

    def cardinal(self, window: int, name: str) -> int | None:
        """Read one complete scalar, retaining the destroyed-window policy."""
        value = self.property_value(window, name)
        return value[0] if isinstance(value, tuple) and len(value) == 1 else None

    def render_window(self, pid: int, *, application: str = "duckstation") -> bool:
        """Require an active fullscreen nonmodal render window for the backend.

        DuckStation changes its title after OnSystemStarted. Stock xemu uses
        its fixed SDL window title instead. Neither title alone proves output;
        callers must also observe the selected disc and authenticated pixels.
        Private titles stay in memory.
        """
        window = self.cardinal(self.root, "_NET_ACTIVE_WINDOW")
        if not window or self.cardinal(window, "_NET_WM_PID") != pid:
            return False
        type_ = self.property_value(
            window, "_NET_WM_WINDOW_TYPE", length=_MAX_ATOM_LONGS
        )
        state = self.property_value(window, "_NET_WM_STATE", length=_MAX_ATOM_LONGS)
        title = self.property_value(window, "_NET_WM_NAME", length=_MAX_PROPERTY_LONGS)
        normal = int(self.x.XInternAtom(self.display, b"_NET_WM_WINDOW_TYPE_NORMAL", 1))
        fullscreen = int(
            self.x.XInternAtom(self.display, b"_NET_WM_STATE_FULLSCREEN", 1)
        )
        modal = int(self.x.XInternAtom(self.display, b"_NET_WM_STATE_MODAL", 1))
        return (
            isinstance(type_, tuple)
            and type_ == (normal,)
            and isinstance(state, tuple)
            and fullscreen != 0
            and fullscreen in state
            and modal not in state
            and self.cardinal(window, "WM_TRANSIENT_FOR") is None
            and isinstance(title, bytes)
            and bool(title.strip())
            and (
                (application == "duckstation" and not title.startswith(b"DuckStation"))
                or (application == "xemu" and title == b"xemu | v0.8.134")
            )
            and self.cardinal(self.root, "_NET_ACTIVE_WINDOW") == window
        )

    def active_pid(self) -> int | None:
        """Return the active owned-window PID, not a process-name heuristic."""
        window = self.cardinal(self.root, "_NET_ACTIVE_WINDOW")
        return self.cardinal(window, "_NET_WM_PID") if window else None

    def screenshot(self, path: Path) -> dict[str, object]:
        """Publish authenticated root pixels using the unchanged stock Pillow.

        Only bounded little-endian 32-bit BGRX images with the expected masks
        are accepted. Xlib pixels, the Pillow image and the exclusive temporary
        file are released on every path. The authenticated display stays open.

        Args:
            path: Absent PNG destination in a caller-owned private directory.

        Returns:
            Basename, dimensions, SHA-256 and the actual capture mechanism.

        Raises:
            DiagnosticError: If dimensions, pixels or their format are unavailable.
            OSError: If exclusive PNG publication or cleanup fails.
        """
        # Only capture needs Pillow. Inspection/imports remain usable with stdlib,
        # while actual captures use Batocera's unchanged stock installation.
        from PIL import Image  # noqa: PLC0415

        width = int(self.x.XDisplayWidth(self.display, self.screen))
        height = int(self.x.XDisplayHeight(self.display, self.screen))
        if (
            not 0 < width <= _MAX_DISPLAY_DIMENSION
            or not 0 < height <= _MAX_DISPLAY_DIMENSION
        ):
            message = "Invalid owned display dimensions"
            raise DiagnosticError(message)
        image: _Pointer[XImage] = self.x.XGetImage(
            self.display,
            self.root,
            0,
            0,
            width,
            height,
            ctypes.c_ulong(-1).value,
            _ZPIXMAP,
        )
        if not image:
            message = "Authenticated XGetImage failed"
            raise DiagnosticError(message)
        try:
            info = image.contents
            stride = int(info.bytes_per_line)
            if (
                int(info.bits_per_pixel) != _PROPERTY_LONG_BITS
                or int(info.byte_order) != 0
                or (int(info.red_mask), int(info.green_mask), int(info.blue_mask))
                != _RGB_MASKS
                or not width * _BYTES_PER_LONG
                <= stride
                <= width * _BYTES_PER_LONG + _MAX_STRIDE_PADDING
            ):
                message = "Unsupported XGetImage pixel format"
                raise DiagnosticError(message)
            pixel_address = info.data
            if not pixel_address:
                message = "Authenticated XGetImage returned no pixel data"
                raise DiagnosticError(message)
            pixels = ctypes.string_at(pixel_address, stride * height)
            temporary = path.with_name(path.name + ".partial")
            descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    with Image.frombytes(
                        "RGB", (width, height), pixels, "raw", "BGRX", stride
                    ) as captured:
                        captured.save(stream, format="PNG")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.link(temporary, path, follow_symlinks=False)
            finally:
                temporary.unlink()
            return {
                "path": path.name,
                "width": width,
                "height": height,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mechanism": "authenticated-libX11-XGetImage-stock-Pillow",
            }
        finally:
            self.x.XDestroyImage(image)

    def close(self) -> None:
        """Close this borrowed-session connection without affecting the display."""
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None


def _validate_timeout(timeout: float) -> None:
    """Reject nonfinite or nonpositive observation deadlines before side effects."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        message = "Expected a finite positive diagnostic timeout"
        raise DiagnosticError(message)


def capture_checkpoint(path: Path, timeout: float = 10) -> dict[str, object]:
    """Bound a fresh authenticated X11 capture in an owned app-UID child.

    Use the stable image launcher, not the installed module's source directory.
    The child inherits the application credentials and authenticated environment.
    Captured output is consumed only as structured screenshot metadata.

    Raises:
        DiagnosticError: If the child cannot run, times out or rejects capture.
        ValueError: If successful child output is not valid JSON.
    """
    _validate_timeout(timeout)
    try:
        # The interpreter and absolute installed launcher are owned, not request data.
        completed = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(RUNTIME_ROOT / "native_diagnostics.py"),
                "capture",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = "Owned screenshot capture unavailable or timed out"
        raise DiagnosticError(message) from error
    if completed.returncode:
        message = "Owned screenshot capture failed"
        raise DiagnosticError(message)
    return object_value(json.loads(completed.stdout))


def transport_ready(path: Path) -> dict[str, object] | None:
    """Require a ready worker and exactly one pinned final stock source.

    Missing status or incomplete readiness returns None. Unsafe ownership,
    writable/nonregular status, failed transport or inconsistent final-source
    identities raise DiagnosticError. This reads evidence only; it neither
    authorizes input nor proves a process is still alive.
    """
    try:
        info = path.lstat()
        status = object_value(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or info.st_mode & 0o022
        or status.get("error")
    ):
        message = "Unsafe or failed transport status"
        raise DiagnosticError(message)
    sources = status.get("sources")
    if not isinstance(sources, list):
        message = "Transport sources missing"
        raise DiagnosticError(message)
    finals: list[dict[str, object]] = []
    for source in sources:
        record = object_value(source)
        if record.get("name") == "batocera hotkeys":
            finals.append(record)
    if (
        status.get("ready") is not True
        or status.get("worker_connected") is not True
        or not finals
    ):
        return None
    approved = status.get("approved_process_ids")
    if (
        len(finals) != 1
        or finals[0].get("role") != "final"
        or not all(
            finals[0].get(k) is not None for k in ("source_pid", "sysname", "node")
        )
        or not isinstance(approved, list)
    ):
        message = "Final source identity/approved process ancestry is not pinned"
        raise DiagnosticError(message)
    return {
        "ready": True,
        "worker_connected": True,
        "final": finals[0],
        "app_uid": status.get("app_uid"),
        "approved_process_ids": approved,
    }


def process_identity(pid: int) -> tuple[int, int]:
    """Read the live parent and start ticks used by the transport ProcessTree.

    Raises:
        DiagnosticError: If proc does not describe a live process.
    """
    if pid <= 0:
        raise DiagnosticError(_ANCESTRY_ERROR)
    value = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    try:
        fields = value[value.rindex(")") + 2 :].split()
        if fields[0] in ("Z", "X", "x"):
            raise DiagnosticError(_ANCESTRY_ERROR)
        identity = int(fields[1]), int(fields[_PROC_START_FIELD])
    except (IndexError, ValueError) as error:
        raise DiagnosticError(_ANCESTRY_ERROR) from error
    return identity


def _proc_fields(path: Path) -> dict[str, str]:
    """Read proc status fields without retaining command lines or environments."""
    return dict(
        line.split(":", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if ":" in line
    )


def _confined_credentials(fields: dict[str, str], uid: int, gid: int) -> None:
    """Require all four identities, zero inheritable/effective grants and NNP."""
    if (
        fields.get("Uid", "").split() != [str(uid)] * _ID_SLOTS
        or fields.get("Gid", "").split() != [str(gid)] * _ID_SLOTS
    ):
        raise DiagnosticError(_APP_IDENTITY_ERROR)
    if (
        any(
            fields.get(key, "").strip() != "0000000000000000"
            for key in ("CapInh", "CapEff", "CapPrm", "CapAmb")
        )
        or fields.get("NoNewPrivs", "").strip() != "1"
    ):
        raise DiagnosticError(_ANCESTRY_ERROR)


def _approved_process_ids(status: dict[str, object]) -> set[int]:
    """Reject absent, duplicate, boolean or non-live-range approval identities."""
    approved = status.get("approved_process_ids")
    if not isinstance(approved, list) or not approved:
        raise DiagnosticError(_ANCESTRY_ERROR)
    approved_ids: set[int] = set()
    for pid in approved:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1:
            raise DiagnosticError(_ANCESTRY_ERROR)
        approved_ids.add(pid)
    if len(approved_ids) != len(approved):
        raise DiagnosticError(_ANCESTRY_ERROR)
    return approved_ids


def _session_command(command: list[bytes]) -> bool:
    """Match the stable installed session launcher, never a process-name guess."""
    return command[1 : 1 + _SESSION_ARGUMENT_COUNT] == _SESSION_ARGUMENTS


def _is_application_process(
    pid: int,
    uid: int,
    approved_ids: set[int],
    fields: dict[str, str],
    command: list[bytes],
) -> bool:
    """Include every app-UID, approved or non-inspector packaged process."""
    return (
        pid in approved_ids
        or str(uid) in fields.get("Uid", "").split()
        or (
            pid not in (1, os.getpid())
            and any(argument.startswith(b"/opt/gow-full-x86/") for argument in command)
        )
    )


def _uinput_actor(
    credential: dict[str, object],
    identities: dict[int, tuple[int, int, int]],
    root: int,
    identity: tuple[int, int],
    uinput: os.stat_result,
) -> dict[str, object]:
    """Revalidate a pinned actor's ancestry, credentials and uinput permissions."""
    uid, gid = identity
    pid = credential["pid"]
    if not isinstance(pid, int):
        raise DiagnosticError(_ANCESTRY_ERROR)
    ancestor = pid
    visited: set[int] = set()
    while ancestor != root:
        if ancestor in visited or ancestor not in identities:
            raise DiagnosticError(_ANCESTRY_ERROR)
        visited.add(ancestor)
        ancestor = identities[ancestor][0]
    current = _proc_fields(Path(f"/proc/{pid}/status"))
    if any(
        current.get(key, "").strip() != value
        for key, value in credential.items()
        if key != "pid"
    ):
        raise DiagnosticError(_ANCESTRY_ERROR)
    groups = [*str(credential["Groups"]).split(), str(gid)]
    if uinput.st_uid == uid:
        shift = _OWNER_PERMISSION_SHIFT
    elif str(uinput.st_gid) in groups:
        shift = _GROUP_PERMISSION_SHIFT
    else:
        shift = 0
    if (uinput.st_mode >> shift) & _READ_WRITE_PERMISSION != _READ_WRITE_PERMISSION:
        message = "Native app cannot read/write uinput"
        raise DiagnosticError(message)
    parent, start, _ = identities[pid]
    return {
        "pid": pid,
        "parent_pid": parent,
        "start_time_ticks": start,
        "application_root_pid": root,
        "read_write": True,
    }


def _application_snapshot(
    approved_ids: set[int], uid: int, gid: int, handles: contextlib.ExitStack
) -> tuple[list[dict[str, object]], dict[int, tuple[int, int, int]], list[int]]:
    """Collect confined credentials and pin each live approved actor.

    Every acquired pidfd transfers immediately to the borrowed cleanup stack.
    Missing processes retain historical approval only and cannot become roots.
    """
    credentials: list[dict[str, object]] = []
    identities: dict[int, tuple[int, int, int]] = {}
    roots: list[int] = []
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        pid = int(path.name)
        try:
            fields = _proc_fields(path / "status")
            command = (path / "cmdline").read_bytes().split(b"\0")
            if not _is_application_process(pid, uid, approved_ids, fields, command):
                continue
            _confined_credentials(fields, uid, gid)
            credential: dict[str, object] = {
                "pid": pid,
                **{key: fields.get(key, "").strip() for key in _CREDENTIAL_KEYS},
            }
            credentials.append(credential)
            if pid not in approved_ids:
                continue
            descriptor = os.pidfd_open(pid)
            handles.callback(os.close, descriptor)
            if select.select([descriptor], [], [], 0)[0]:
                continue
            parent, start = process_identity(pid)
            identities[pid] = parent, start, descriptor
            if parent == 1 and _session_command(command):
                roots.append(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
    return credentials, identities, roots


def application_credentials(
    status: dict[str, object], uid: int, gid: int, uinput: os.stat_result
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Qualify live approved actors, never authority from names or shared UID.

    The root-controlled status supplies ProcessTree approval. Every observed
    app-UID process must be confined, including the separate XTEST worker, but
    only approved live descendants of the single PID1 session may be actors.
    Borrowed proc observations and uinput metadata are never modified. All
    pidfds opened here close before return, including after partial failure.

    Returns:
        All app credentials and approved actors' numeric uinput evidence.

    Raises:
        DiagnosticError: If approval, live ancestry, credentials or actor device
            permission is missing or inconsistent.
    """
    approved_ids = _approved_process_ids(status)
    with contextlib.ExitStack() as handles:
        credentials, identities, roots = _application_snapshot(
            approved_ids, uid, gid, handles
        )
        if len(roots) != 1:
            raise DiagnosticError(_ANCESTRY_ERROR)
        root = roots[0]
        actors = [
            _uinput_actor(credential, identities, root, (uid, gid), uinput)
            for credential in credentials
            if credential["pid"] in identities
        ]
        for pid, (parent, start, descriptor) in identities.items():
            if select.select([descriptor], [], [], 0)[0] or process_identity(pid) != (
                parent,
                start,
            ):
                raise DiagnosticError(_ANCESTRY_ERROR)
        if not _session_command(
            Path(f"/proc/{root}/cmdline").read_bytes().split(b"\0")
        ):
            raise DiagnosticError(_ANCESTRY_ERROR)
        return credentials, actors


def _integrity_hashes(value: object) -> dict[str, object]:
    """Hash only declared stock/additive paths, refusing lexical traversal."""
    hashes = object_value(value)
    observed: dict[str, object] = {}
    for name, digest in hashes.items():
        if (
            name != "/lib/libudev.so.1.6.3"
            and not name.startswith(("/opt/gow-full-x86/", "/usr/", "/etc/hotkeygen/"))
        ) or ".." in name.split("/"):
            message = "Invalid integrity inspection path"
            raise DiagnosticError(message)
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            message = "Packaged source/stock integrity mismatch"
            raise DiagnosticError(message)
        observed[name] = digest
    return observed


def _package_permissions() -> None:
    """Inspect root, additive ancestors and every staged child without mutation."""
    for path in (
        Path("/"),
        Path("/opt"),
        Path("/opt/gow-full-x86"),
        *Path("/opt/gow-full-x86").rglob("*"),
    ):
        info = path.lstat()
        if (
            info.st_uid != 0
            or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022)
            or any(
                key in os.listxattr(path, follow_symlinks=False)
                for key in ("system.posix_acl_access", "system.posix_acl_default")
            )
        ):
            message = "Additive package is writable or has ACLs"
            raise DiagnosticError(message)


def inspect_runtime(request: dict[str, object]) -> dict[str, object]:
    """Read package integrity and app credentials without launching a probe.

    The request supplies expected hashes and the positive application UID/GID.
    Only allowlisted stock/additive paths are hashed. Package ancestry, ACLs,
    confined userdata, supervisor status, seccomp and pinned live actors must
    all agree before numeric observations are returned. Nothing is written.

    Raises:
        DiagnosticError: If an integrity, containment or security check fails.
        OSError: If required runtime files or kernel observations are unavailable.
    """
    observed = _integrity_hashes(request.get("hashes"))
    _package_permissions()
    userdata = Path("/userdata")
    home_userdata = Path("/home/retro/userdata")
    # Match the raw stock target exactly. Path.readlink normalizes spelling and
    # would admit differently spelled targets that this containment gate rejects.
    if (
        not userdata.is_symlink()
        or os.readlink(userdata) != "/home/retro/userdata"  # noqa: PTH115
        or home_userdata.is_symlink()
        or not home_userdata.is_dir()
    ):
        message = "Userdata is not confined to the native disposable home"
        raise DiagnosticError(message)
    userdata_info = home_userdata.stat()
    status_path = Path("/run/gow-full-x86-input-transport.json")
    status_info = status_path.lstat()
    if (
        not stat.S_ISREG(status_info.st_mode)
        or status_info.st_uid != 0
        or status_info.st_mode & 0o022
    ):
        message = "Supervisor PID/app identity is not established"
        raise DiagnosticError(message)
    status = object_value(json.loads(status_path.read_text(encoding="utf-8")))
    uid, gid = request.get("uid"), request.get("gid")
    if type(uid) is not int or type(gid) is not int or uid <= 0 or gid <= 0:
        raise DiagnosticError(_APP_IDENTITY_ERROR)
    if status.get("pid") != 1 or status.get("app_uid") != uid or status.get("error"):
        message = "Supervisor PID/app identity is not established"
        raise DiagnosticError(message)
    own_status = _proc_fields(Path("/proc/self/status"))
    if own_status.get("Seccomp", "").strip() != str(_SECCOMP_FILTER):
        message = "Effective container seccomp filter missing"
        raise DiagnosticError(message)
    uinput = Path("/dev/uinput").stat()
    if not stat.S_ISCHR(uinput.st_mode):
        message = "Native uinput device missing"
        raise DiagnosticError(message)
    credentials, actors = application_credentials(status, uid, gid, uinput)
    return {
        "hashes": observed,
        "credentials": credentials,
        "supervisor_pid": status.get("pid"),
        "effective_seccomp": _SECCOMP_FILTER,
        "uinput": [os.major(uinput.st_rdev), os.minor(uinput.st_rdev)],
        "uinput_actors": actors,
        "approved_process_ids": status.get("approved_process_ids"),
        "userdata": {
            "link": "/home/retro/userdata",
            "identity": [
                userdata_info.st_dev,
                userdata_info.st_ino,
                userdata_info.st_uid,
            ],
        },
    }


def frontend_ready_flag(path: Path, uid: int) -> list[int] | None:
    """Read ES's stock post-splash readiness flag in the private container.

    Batocera ES 2c29a330e487210a7d51ad2650bb7b280ea44c86 sets this
    after closeSplashScreen, preload, input initialization and goToStart.
    """
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != uid:
        message = "Stock ES ready flag is not an app-owned regular file"
        raise DiagnosticError(message)
    return [info.st_dev, info.st_ino, info.st_uid]


def _frontend_observation(
    desktop: Desktop, directory: Path, handles: contextlib.ExitStack
) -> dict[str, object] | None:
    """Capture only a ready, confined ES window while pinning both live actors.

    Newly opened pidfds transfer to the observer's cleanup stack, including when
    later qualification fails. The display and cleanup stack remain borrowed.
    """
    ready = transport_ready(Path("/run/gow-full-x86-input-transport.json"))
    pid = desktop.active_pid()
    if ready is None or pid is None:
        return None
    approved = ready["approved_process_ids"]
    if not isinstance(approved, list) or pid not in approved:
        message = "Active ES window is not an approved app descendant"
        raise DiagnosticError(message)
    executable = Path(f"/proc/{pid}/exe").resolve().name
    flag = frontend_ready_flag(Path(_FRONTEND_READY_NAME), os.getuid())
    if executable != "emulationstation" or flag is None:
        return None
    try:
        _confined_credentials(
            _proc_fields(Path(f"/proc/{pid}/status")), os.getuid(), os.getgid()
        )
    except DiagnosticError as error:
        message = "Active frontend lost non-root capability-free identity"
        raise DiagnosticError(message) from error
    descriptor = os.pidfd_open(pid)
    handles.callback(os.close, descriptor)
    final = object_value(ready.get("final"))
    final_pid = final.get("source_pid")
    if type(final_pid) is not int or final_pid not in approved:
        message = "Final source process is not an approved app descendant"
        raise DiagnosticError(message)
    final_descriptor = os.pidfd_open(final_pid)
    handles.callback(os.close, final_descriptor)
    if select.select([descriptor, final_descriptor], [], [], 0)[0]:
        message = "Frontend died before readiness capture"
        raise DiagnosticError(message)
    capture = capture_checkpoint(directory / "frontend-ready.png")
    after = transport_ready(Path("/run/gow-full-x86-input-transport.json"))
    if (
        select.select([descriptor, final_descriptor], [], [], 0)[0]
        or desktop.active_pid() != pid
        or frontend_ready_flag(Path(_FRONTEND_READY_NAME), os.getuid()) != flag
        or after is None
        or after.get("final") != ready.get("final")
    ):
        message = "Pinned frontend/transport identity changed during capture"
        raise DiagnosticError(message)
    return {
        "status": "passed",
        "frontend": {
            "pid": pid,
            "executable": executable,
            "active_window": True,
            "completed_initialization": True,
            "ready_flag_identity": flag,
            "pinned_final_source_live": True,
        },
        "transport": ready,
        "captures": [capture],
    }


def _wait_frontend(
    desktop: Desktop,
    directory: Path,
    deadline: float,
    handles: contextlib.ExitStack,
) -> dict[str, object]:
    """Wait for the first lease, then require uninterrupted permission/readiness."""
    armed = False
    while time.monotonic() < deadline:
        try:
            input_permitted()
            armed = True
        except InterruptedError:
            if armed:
                raise
            # Before the first inspection lease this observer remains read-only.
            time.sleep(0.05)
            continue
        observation = _frontend_observation(desktop, directory, handles)
        if observation is not None:
            return observation
        time.sleep(0.05)
    message = "Normal frontend/ready worker/final source deadline expired"
    raise DiagnosticError(message)


def _failure_capture(directory: Path) -> list[dict[str, object]]:
    """Retain one actual failed-checkpoint capture or an explicit unavailability."""
    try:
        capture = capture_checkpoint(directory / "frontend-failure.png")
    except (OSError, DiagnosticError):
        return [{"status": "unavailable", "checkpoint": "frontend-failure"}]
    return [capture]


def _frontend_startup(directory: Path, timeout: float) -> tuple[Desktop, float]:
    """Validate the app observer, publish startup and transfer its open display."""
    if os.getuid() == 0:
        message = "Frontend observer must use app UID"
        raise DiagnosticError(message)
    _validate_timeout(timeout)
    deadline = time.monotonic() + timeout
    publish_json(
        directory / "startup.json",
        {
            "uid": os.getuid(),
            "gid": os.getgid(),
            "mode": "normal-frontend-observer",
        },
    )
    return Desktop(), deadline


def _observation_error(error: OSError | ValueError | DiagnosticError) -> str:
    """Keep explicit refusal reasons but discard arbitrary private OS/parser text."""
    if isinstance(error, DiagnosticError) or (
        isinstance(error, InterruptedError) and error.errno is None
    ):
        return str(error)
    if isinstance(error, OSError):
        return "Frontend runtime observation unavailable"
    return "Frontend runtime observation malformed"


def observe_frontend(directory: Path, timeout: float) -> int:
    """Observe the ordinary frontend's active ES window and stock ready flag.

    Both the stock post-splash flag and active pinned ES window are required.
    A splash, a process alone or arbitrary pixels cannot pass. The supplied
    directory must already be test-owned. Evidence is published exclusively,
    without replacing prior files. All opened displays/pidfds close on failure.

    Returns:
        Zero only after a qualified capture, otherwise one with failure evidence.

    Raises:
        OSError: If evidence publication or resource cleanup fails.
    """
    result: dict[str, object] = {
        "schema": 1,
        "status": "failed",
        "captures": [],
        "errors": [],
    }
    desktop: Desktop | None = None
    try:
        with contextlib.ExitStack() as handles:
            try:
                desktop, deadline = _frontend_startup(directory, timeout)
                handles.callback(desktop.close)
                result.update(_wait_frontend(desktop, directory, deadline, handles))
            except (OSError, ValueError, DiagnosticError) as error:
                result["errors"] = [_observation_error(error)]
                if desktop is not None:
                    result["captures"] = _failure_capture(directory)
    finally:
        selected_errors = result["errors"]
        lines = (
            [str(value) for value in selected_errors]
            if isinstance(selected_errors, list)
            else []
        )
        publish_selected_log(
            directory, ["normal frontend observation: " + str(result["status"]), *lines]
        )
        publish_json(directory / "frontend-probe.json", result)
    return 0 if result["status"] == "passed" else 1


def main() -> int:
    """Expose bounded inspection or the normal frontend's child observer."""
    arguments = sys.argv[1:]
    if len(arguments) == _CAPTURE_ARGUMENT_COUNT and arguments[0] == "capture":
        desktop = Desktop()
        try:
            json.dump(desktop.screenshot(Path(arguments[1])), sys.stdout)
        finally:
            desktop.close()
        return 0
    if arguments == ["inspect"]:
        json.dump(inspect_runtime(object_value(json.load(sys.stdin))), sys.stdout)
        return 0
    if arguments == ["frontend"]:

        def interrupted(signum: int, _frame: object) -> None:
            """Abort observation but retain evidence and owned-resource cleanup."""
            message = "Frontend observer interrupted: " + str(signum)
            raise InterruptedError(message)

        for signum in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, interrupted)
        try:
            timeout = float(os.environ["GOW_NATIVE_FRONTEND_TIMEOUT"])
            _validate_timeout(timeout)
        except (KeyError, ValueError, DiagnosticError) as error:
            message = "Expected a finite positive frontend diagnostic timeout"
            raise DiagnosticError(message) from error
        signal.alarm(int(timeout) + _FRONTEND_ALARM_GRACE)
        return observe_frontend(Path(os.environ["GOW_NATIVE_RESULTS"]), timeout)
    message = "Expected inspect or frontend diagnostic mode"
    raise DiagnosticError(message)


if __name__ == "__main__":
    raise SystemExit(main())
