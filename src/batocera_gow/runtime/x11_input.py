"""XTEST output for the disposable input trial, without hotkey translation."""

import ctypes
import ctypes.util
import os
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Protocol

MAX_LINUX_KEY = 247
MAX_X_KEYCODE = 255
MIN_X_KEYCODE = 8
MAX_X_BUTTON = 255
KEY_REPEAT = 2


class InputSink(Protocol):
    """Borrowed desktop operations used by ordered input state."""

    def key(self, linux_code: int, /, *, pressed: bool) -> None:
        """Set one key without changing other desktop holds."""
        ...

    def button(self, x_button: int, /, *, pressed: bool) -> None:
        """Set one pointer button."""
        ...

    def motion(self, dx: int, dy: int, /) -> None:
        """Move the pointer by bounded relative coordinates."""
        ...

    def flush(self) -> None:
        """Submit queued desktop operations."""
        ...


@dataclass
class _RelativeSegment:
    """One ordered motion segment or same-direction wheel run."""

    kind: str | int
    x: int
    y: int


EV_SYN = 0
EV_KEY = 1
EV_REL = 2
EV_MSC = 4
SYN_REPORT = 0
SYN_DROPPED = 3
REL_X = 0
REL_Y = 1
REL_HWHEEL = 6
REL_WHEEL = 8

# evdev mouse button order differs from X11's left, middle, right order.
_MOUSE_BUTTONS = {
    0x110: 1,
    0x111: 3,
    0x112: 2,
    0x113: 8,
    0x114: 9,
    0x115: 10,
    0x116: 11,
    0x117: 12,
}


def _integer(value: object, minimum: int, maximum: int, label: str) -> int:
    """Validate untrusted event integers without accepting bool as an event value."""
    if type(value) is not int or not minimum <= value <= maximum:
        error_message = f"{label} must be an integer in {minimum}..{maximum}: {value!r}"
        raise ValueError(error_message)
    return value


class XTestSink:
    """One worker's authenticated X connection. No global keyboard reset is used."""

    def __init__(self, display: str, authority: str) -> None:
        """Own an authenticated X connection, including partial-setup cleanup."""
        # Importing this module never loads either X shared library.

        if not isinstance(display, str) or not display or "\0" in display:
            error_message = "an explicit X display is required"
            raise ValueError(error_message)
        if not isinstance(authority, str) or not authority or "\0" in authority:
            error_message = "an explicit X authority file is required"
            raise ValueError(error_message)
        self._display: int | None = None
        self._configure_libraries()

        previous = os.environ.get("XAUTHORITY")
        os.environ["XAUTHORITY"] = authority
        try:
            opened: int | None = self._x11.XOpenDisplay(os.fsencode(display))
            self._display = opened
        finally:
            if previous is None:
                os.environ.pop("XAUTHORITY", None)
            else:
                os.environ["XAUTHORITY"] = previous
        if not self._display:
            error_message = f"cannot open authenticated X display {display!r}"
            raise RuntimeError(error_message)
        try:
            self._minimum, self._maximum = self._validate_extension()
        except BaseException:
            self.close()
            raise

    def _validate_extension(self) -> tuple[int, int]:
        """Require XTEST 2.1 and return the server's valid keycode bounds."""
        integer = ctypes.c_int
        event, error, major, minor = (integer() for _ in range(4))
        if not self._xtst.XTestQueryExtension(
            self._display,
            ctypes.byref(event),
            ctypes.byref(error),
            ctypes.byref(major),
            ctypes.byref(minor),
        ):
            error_message = "the X display does not support XTEST"
            raise RuntimeError(error_message)
        # Relative motion requires XTEST 2.1 or newer.
        if (major.value, minor.value) < (2, 1):
            error_message = "the input worker requires XTEST 2.1 or newer"
            raise RuntimeError(error_message)
        minimum, maximum = integer(), integer()
        self._x11.XDisplayKeycodes(
            self._display, ctypes.byref(minimum), ctypes.byref(maximum)
        )
        if not MIN_X_KEYCODE <= minimum.value <= maximum.value <= MAX_X_KEYCODE:
            error_message = "the X display returned invalid keycode bounds"
            raise RuntimeError(error_message)
        return minimum.value, maximum.value

    def _configure_libraries(self) -> None:
        """Load only the X11/XTEST libraries and declare their C call boundaries."""
        x11_name = ctypes.util.find_library("X11")
        xtst_name = ctypes.util.find_library("Xtst")
        if not x11_name or not xtst_name:
            error_message = "the input worker requires libX11 and libXtst"
            raise RuntimeError(error_message)
        self._x11 = ctypes.CDLL(x11_name)
        self._xtst = ctypes.CDLL(xtst_name)
        pointer = ctypes.c_void_p
        integer = ctypes.c_int
        uint = ctypes.c_uint
        ulong = ctypes.c_ulong
        int_pointer = ctypes.POINTER(integer)
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = pointer
        self._x11.XCloseDisplay.argtypes = [pointer]
        self._x11.XCloseDisplay.restype = integer
        self._x11.XDisplayKeycodes.argtypes = [pointer, int_pointer, int_pointer]
        self._x11.XDisplayKeycodes.restype = integer
        self._x11.XFlush.argtypes = [pointer]
        self._x11.XFlush.restype = integer
        self._xtst.XTestQueryExtension.argtypes = [
            pointer,
            int_pointer,
            int_pointer,
            int_pointer,
            int_pointer,
        ]
        self._xtst.XTestQueryExtension.restype = integer
        self._xtst.XTestFakeKeyEvent.argtypes = [pointer, uint, integer, ulong]
        self._xtst.XTestFakeKeyEvent.restype = integer
        self._xtst.XTestFakeButtonEvent.argtypes = [pointer, uint, integer, ulong]
        self._xtst.XTestFakeButtonEvent.restype = integer
        self._xtst.XTestFakeRelativeMotionEvent.argtypes = [
            pointer,
            integer,
            integer,
            ulong,
        ]
        self._xtst.XTestFakeRelativeMotionEvent.restype = integer

    def _connection(self) -> int:
        if not self._display:
            error_message = "the XTEST sink is closed"
            raise RuntimeError(error_message)
        return self._display

    def key(self, linux_code: int, *, pressed: bool) -> None:
        """Inject one Linux key transition into this connection's supported range."""
        code = _integer(linux_code, 1, MAX_LINUX_KEY, "Linux key code") + MIN_X_KEYCODE
        if not self._minimum <= code <= self._maximum:
            error_message = (
                f"Linux key {linux_code} is outside this X display's keycode bounds"
            )
            raise ValueError(error_message)
        if type(pressed) is not bool:
            error_message = "key pressed must be a bool"
            raise ValueError(error_message)
        if not self._xtst.XTestFakeKeyEvent(self._connection(), code, pressed, 0):
            error_message = f"XTEST rejected Linux key {linux_code}"
            raise RuntimeError(error_message)

    def button(self, x_button: int, *, pressed: bool) -> None:
        """Inject one X pointer-button transition without resetting other buttons."""
        _integer(x_button, 1, MAX_X_BUTTON, "X button")
        if type(pressed) is not bool:
            error_message = "button pressed must be a bool"
            raise ValueError(error_message)
        if not self._xtst.XTestFakeButtonEvent(
            self._connection(), x_button, pressed, 0
        ):
            error_message = f"XTEST rejected button {x_button}"
            raise RuntimeError(error_message)

    def motion(self, dx: int, dy: int) -> None:
        """Inject bounded signed relative motion without truncating coordinates."""
        # XTEST's wire coordinates are signed 16-bit, despite its C int arguments.
        _integer(dx, -32768, 32767, "relative X motion")
        _integer(dy, -32768, 32767, "relative Y motion")
        if not self._xtst.XTestFakeRelativeMotionEvent(self._connection(), dx, dy, 0):
            error_message = "XTEST rejected relative pointer motion"
            raise RuntimeError(error_message)

    def flush(self) -> None:
        """Submit pending X operations; XFlush has no success-status return contract."""
        # XFlush's int return is not a success/failure status.
        self._x11.XFlush(self._connection())

    def close(self) -> None:
        """Close this sink's connection once without resetting global desktop state."""
        if self._display:
            connection, self._display = self._display, None
            self._x11.XCloseDisplay(connection)


class _Source:
    """Retain one producer's insertion-ordered holds and framed relative events."""

    def __init__(self) -> None:
        """Start with no acquired holds or pending frame segments."""
        self.held: dict[tuple[str, int], None] = {}
        self.pending: deque[_RelativeSegment] = deque()


class InputState:
    """Own only injected holds; preserve producer ordering and share holds by source."""

    def __init__(self, sink: InputSink) -> None:
        """Borrow a sink; closing state releases holds but never closes the sink."""
        self._sink = sink
        self._sources: dict[str, _Source] = {}
        self._counts: dict[tuple[str, int], int] = {}
        self._dropped: set[str] = set()
        self._closed = False

    def _emit(self, token: tuple[str, int], *, pressed: bool) -> None:
        kind, code = token
        if kind == "key":
            self._sink.key(code, pressed=pressed)
        else:
            self._sink.button(code, pressed=pressed)

    def _hold(self, source: str, token: tuple[str, int], value: int) -> None:
        state = self._sources.get(source)
        # A repeat without its original press is not a new transport-owned hold.
        if value == KEY_REPEAT:
            return
        if value == 1:
            if state is None:
                state = _Source()
                self._sources[source] = state
            if token in state.held:
                return
            self._drain_relative(state)
            count = self._counts.get(token, 0)
            if not count:
                self._emit(token, pressed=True)
            self._counts[token] = count + 1
            state.held[token] = None
        elif state is not None and token in state.held:
            self._drain_relative(state)
            count = self._counts[token]
            if count == 1:
                self._emit(token, pressed=False)
                del self._counts[token]
            else:
                self._counts[token] = count - 1
            del state.held[token]

    def _queue_relative(self, state: _Source, code: int, value: int) -> None:
        if not value:
            return
        kind = "motion" if code in (REL_X, REL_Y) else code
        if kind == "motion":
            if not state.pending or state.pending[-1].kind != kind:
                state.pending.append(_RelativeSegment(kind, 0, 0))
            if code == REL_X:
                state.pending[-1].x += value
            else:
                state.pending[-1].y += value
        elif (
            state.pending
            and state.pending[-1].kind == kind
            and state.pending[-1].x * value > 0
        ):
            state.pending[-1].x += value
        else:
            # Opposite wheel directions are separate clicks, not cancellation.
            state.pending.append(_RelativeSegment(kind, value, 0))

    def _drain_relative(self, state: _Source) -> None:
        while state.pending:
            segment = state.pending[0]
            if segment.kind == "motion":
                # Split long frames without truncating XTEST wire coordinates.
                while segment.x or segment.y:
                    dx = max(-32768, min(32767, segment.x))
                    dy = max(-32768, min(32767, segment.y))
                    self._sink.motion(dx, dy)
                    segment.x -= dx
                    segment.y -= dy
            else:
                positive, negative = (4, 5) if segment.kind == REL_WHEEL else (7, 6)
                direction = 1 if segment.x > 0 else -1
                button = positive if direction == 1 else negative
                while segment.x:
                    token = ("button", button)
                    # Keep a failed wheel release owned so close can retry it.
                    self._emit(token, pressed=True)
                    self._counts[token] = 1
                    self._emit(token, pressed=False)
                    del self._counts[token]
                    segment.x -= direction
            state.pending.popleft()

    def _frame(self, source: str) -> None:
        state = self._sources.get(source)
        if state is not None:
            self._drain_relative(state)
        self._sink.flush()

    def feed(
        self, source: str, event_type: object, code: object, value: object
    ) -> None:
        """Apply one evdev event, retaining producer order and shared hold ownership.

        Invalid events raise ValueError without changing existing holds. A dropped
        frame releases this source and raises RuntimeError; events remain ignored
        through its next synchronization report.
        """
        if self._closed:
            error_message = "the input state is closed"
            raise RuntimeError(error_message)
        event_type = _integer(event_type, 0, 65535, "event type")
        code = _integer(code, 0, 65535, "event code")
        value = _integer(value, -(2**31), 2**31 - 1, "event value")
        if source in self._dropped:
            # Kernel evdev requires discarding everything through the next report.
            if event_type == EV_SYN and code == SYN_REPORT:
                self._dropped.remove(source)
            return
        if event_type == EV_SYN:
            self._synchronize(source, code, value)
        elif event_type == EV_KEY:
            self._key_event(source, code, value)
        elif event_type == EV_REL:
            self._relative_event(source, code, value)
        elif event_type == EV_MSC and code in (0, 1, 2, 3, 4, 5):
            return
        else:
            error_message = f"unsupported input event {event_type}:{code}"
            raise ValueError(error_message)

    def _synchronize(self, source: str, code: int, value: int) -> None:
        """Finish a frame or revoke a dropped source before accepting further input."""
        if code not in (SYN_REPORT, SYN_DROPPED) or value != 0:
            error_message = f"unsupported synchronization event {code}:{value}"
            raise ValueError(error_message)
        if code == SYN_DROPPED:
            self._dropped.add(source)
            failure = RuntimeError(f"input events dropped for source {source!r}")
            try:
                self._release_source(source)
            except Exception as exc:
                raise failure from exc
            raise failure
        self._frame(source)

    def _key_event(self, source: str, code: int, value: int) -> None:
        """Apply one supported Linux key or pointer-button transition."""
        if value not in (0, 1, 2):
            error_message = f"invalid key value {value}"
            raise ValueError(error_message)
        if code in _MOUSE_BUTTONS:
            token = ("button", _MOUSE_BUTTONS[code])
        elif 1 <= code <= MAX_LINUX_KEY:
            token = ("key", code)
        else:
            error_message = f"unsupported Linux key or button {code}"
            raise ValueError(error_message)
        self._hold(source, token, value)

    def _relative_event(self, source: str, code: int, value: int) -> None:
        """Queue one supported relative axis while preserving producer order."""
        if code not in (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL):
            error_message = f"unsupported relative axis {code}"
            raise ValueError(error_message)
        state = self._sources.get(source)
        if state is None:
            state = _Source()
            self._sources[source] = state
        self._queue_relative(state, code, value)

    def _release_token(self, token: tuple[str, int]) -> None:
        """Release the last shared hold or reduce its source ownership count."""
        count = self._counts[token]
        if count > 1:
            self._counts[token] = count - 1
        else:
            self._emit(token, pressed=False)
            del self._counts[token]

    def _release_source(self, source: str) -> None:
        """Release all this source's holds, retaining failed releases for close."""
        state = self._sources.pop(source, None)
        with ExitStack() as cleanup:
            cleanup.callback(self._sink.flush)
            if state is not None:
                # ExitStack releases later acquisitions first, even after failure.
                for token in state.held:
                    cleanup.callback(self._release_token, token)

    def remove_source(self, source: str) -> None:
        """Release only this source's holds and discard its pending pointer motion."""
        if not self._closed:
            self._dropped.discard(source)
            self._release_source(source)

    def close(self) -> None:
        """Release every owned hold once; leave the borrowed sink open."""
        if self._closed:
            return
        self._closed = True
        try:
            with ExitStack() as cleanup:
                cleanup.callback(self._sink.flush)
                for token in self._counts:
                    cleanup.callback(self._emit, token, pressed=False)
        finally:
            self._sources.clear()
            self._counts.clear()
            self._dropped.clear()
