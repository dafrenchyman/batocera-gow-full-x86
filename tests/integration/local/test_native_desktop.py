"""Exercise Desktop against an authenticated, exclusively owned Xvfb server."""

import ctypes
import ctypes.util
import os
import secrets
import select
import shutil
import struct
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PROGRAM = """
import ctypes as c
import os
import sys
from unittest.mock import patch
from batocera_gow.runtime import native_diagnostics as native

x = c.CDLL(sys.argv[1])
owned_display = sys.argv[2].encode('ascii')
mode = sys.argv[3]
x.XOpenDisplay.argtypes = [c.c_char_p]
x.XOpenDisplay.restype = c.c_void_p
if mode == 'unauthenticated':
    connection = x.XOpenDisplay(owned_display)
    if connection:
        x.XCloseDisplay.argtypes = [c.c_void_p]
        x.XCloseDisplay(connection)
        raise SystemExit(2)
    raise SystemExit(0)

class Connection:
    # Only redirect library selection and the constructor's connection target.
    # Every request, reply, allocation and error still belongs to actual Xlib.
    def __init__(self):
        self.XOpenDisplay = lambda ignored: x.XOpenDisplay(owned_display)
    def __getattr__(self, name):
        return getattr(x, name)

with patch.object(native.ctypes, 'CDLL', return_value=Connection()):
    desktop = native.Desktop()
d = desktop.display
other = x.XOpenDisplay(owned_display)
assert other
x.XCreateSimpleWindow.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int,
                                  c.c_uint, c.c_uint, c.c_uint, c.c_ulong, c.c_ulong]
x.XCreateSimpleWindow.restype = c.c_ulong
x.XChangeProperty.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong,
                             c.c_int, c.c_int, c.c_void_p, c.c_int]
x.XDeleteProperty.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong]
x.XDestroyWindow.argtypes = [c.c_void_p, c.c_ulong]
x.XSync.argtypes = [c.c_void_p, c.c_int]
x.XNextRequest.argtypes = [c.c_void_p]
x.XNextRequest.restype = c.c_ulong
x.XNoOp.argtypes = [c.c_void_p]
x.XSetErrorHandler.argtypes = [c.c_void_p]
x.XSetErrorHandler.restype = c.c_void_p
x.XSetAfterFunction.argtypes = [c.c_void_p, c.c_void_p]
x.XSetAfterFunction.restype = c.c_void_p

# Independent public Xlib ABI, not the implementation's error-event definition.
class Error(c.Structure):
    _fields_ = [('type', c.c_int), ('display', c.c_void_p),
                ('resourceid', c.c_ulong), ('serial', c.c_ulong),
                ('error_code', c.c_ubyte), ('request_code', c.c_ubyte),
                ('minor_code', c.c_ubyte)]
Handler = c.CFUNCTYPE(c.c_int, c.c_void_p, c.POINTER(Error))
After = c.CFUNCTYPE(c.c_int, c.c_void_p)
active = x.XInternAtom(d, b'_NET_ACTIVE_WINDOW', 0)
pid_atom = x.XInternAtom(d, b'_NET_WM_PID', 0)
window = x.XCreateSimpleWindow(d, desktop.root, 0, 0, 20, 20, 0, 0, 0)
second = x.XCreateSimpleWindow(d, desktop.root, 0, 0, 20, 20, 0, 0, 0)

def property(window_id, atom, type_id, values, format_=32):
    data = (c.c_ulong * len(values))(*values)
    x.XChangeProperty(d, window_id, atom, type_id, format_, 0, data, len(values))
    x.XSync(d, 0)

def get(connection, window_id, atom):
    actual, count, remaining = c.c_ulong(), c.c_ulong(), c.c_ulong()
    format_ = c.c_int()
    data = c.POINTER(c.c_ubyte)()
    try:
        return x.XGetWindowProperty(connection, window_id, atom, 0, 1, 0, 0,
            c.byref(actual), c.byref(format_), c.byref(count),
            c.byref(remaining), c.byref(data))
    finally:
        if data:
            x.XFree(data)

property(desktop.root, active, 33, [window])
property(window, pid_atom, 6, [os.getpid()])
assert desktop.active_pid() == os.getpid()

try:
    if mode == 'destroyed':
        x.XDestroyWindow(d, window)
        x.XSync(d, 0)
        window = 0
        # XGetWindowProperty delivers BadWindow synchronously, not only at XSync.
        assert desktop.active_pid() is None
        assert desktop.active_pid() is None
        property(second, pid_atom, 6, [os.getpid()])
        property(desktop.root, active, 33, [second])
        assert desktop.active_pid() == os.getpid()
    elif mode == 'malformed':
        x.XDeleteProperty(d, window, pid_atom)
        assert desktop.active_pid() is None
        property(window, pid_atom, 6, [7], 8)
        assert desktop.active_pid() is None
        property(window, pid_atom, 6, [])
        assert desktop.active_pid() is None
        property(window, pid_atom, 6, [7, 8])
        assert desktop.active_pid() is None
        property(window, pid_atom, 6, [os.getpid()])
        x.XDeleteProperty(d, desktop.root, active)
        assert desktop.active_pid() is None
    elif mode == 'render':
        normal = x.XInternAtom(d, b'_NET_WM_WINDOW_TYPE_NORMAL', 0)
        dialog = x.XInternAtom(d, b'_NET_WM_WINDOW_TYPE_DIALOG', 0)
        fullscreen = x.XInternAtom(d, b'_NET_WM_STATE_FULLSCREEN', 0)
        modal = x.XInternAtom(d, b'_NET_WM_STATE_MODAL', 0)
        type_atom = x.XInternAtom(d, b'_NET_WM_WINDOW_TYPE', 0)
        state_atom = x.XInternAtom(d, b'_NET_WM_STATE', 0)
        title_atom = x.XInternAtom(d, b'_NET_WM_NAME', 0)
        utf8 = x.XInternAtom(d, b'UTF8_STRING', 0)
        transient = x.XInternAtom(d, b'WM_TRANSIENT_FOR', 0)
        def title(value):
            text = c.create_string_buffer(value)
            x.XChangeProperty(d, window, title_atom, utf8, 8, 0, text, len(value))
            x.XSync(d, 0)
        property(window, type_atom, 4, [normal])
        property(window, state_atom, 4, [fullscreen])
        title(b'Synthetic private game')
        assert desktop.render_window(os.getpid())
        assert not desktop.render_window(os.getpid() + 1)
        title(b'DuckStation ')
        assert not desktop.render_window(os.getpid())
        title(b'Synthetic private game')
        property(window, type_atom, 4, [dialog])
        assert not desktop.render_window(os.getpid())
        property(window, type_atom, 4, [normal])
        property(window, state_atom, 4, [fullscreen, modal])
        assert not desktop.render_window(os.getpid())
        property(window, state_atom, 4, [])
        assert not desktop.render_window(os.getpid())
        property(window, state_atom, 4, [fullscreen])
        property(window, transient, 33, [second])
        assert not desktop.render_window(os.getpid())
        x.XDeleteProperty(d, window, transient)
        assert desktop.render_window(os.getpid())
        title(b'xemu | v0.8.134')
        assert desktop.render_window(os.getpid(), application='xemu')
        assert not desktop.render_window(os.getpid() + 1, application='xemu')
        title(b'Failed to load xemu config file')
        assert not desktop.render_window(os.getpid(), application='xemu')
        title(b'xemu | v0.8.134')
        property(window, type_atom, 4, [dialog])
        assert not desktop.render_window(os.getpid(), application='xemu')
        property(window, type_atom, 4, [normal])
        property(window, state_atom, 4, [fullscreen, modal])
        assert not desktop.render_window(os.getpid(), application='xemu')
        property(window, state_atom, 4, [fullscreen])
        # Bounded text reads reject incomplete titles, not their private prefix.
        title(b'x' * 4097)
        assert not desktop.render_window(os.getpid())
        x.XDestroyWindow(d, window)
        x.XSync(d, 0)
        window = 0
        assert not desktop.render_window(os.getpid())
    elif mode == 'pending-default':
        # A preceding unrelated error must retain Xlib's fatal default policy.
        x.XDestroyWindow(d, second)
        x.XSync(d, 0)
        stale = second
        second = 0
        x.XDestroyWindow(d, stale)
        desktop.active_pid()
        raise SystemExit(3)
    elif mode == 'restored-default':
        x.XDestroyWindow(d, window)
        x.XSync(d, 0)
        stale = window
        window = 0
        assert desktop.active_pid() is None
        get(d, stale, pid_atom)
        raise SystemExit(3)
    elif mode == 'foreign-default':
        default = x.XSetErrorHandler(None)
        x.XSetErrorHandler(default)
        fired = False
        @After
        def foreign_request(display):
            global fired
            installed = x.XSetErrorHandler(None)
            x.XSetErrorHandler(installed)
            if not fired and installed != default:
                fired = True
                get(other, stale, pid_atom)
            return 0
        x.XDestroyWindow(d, second)
        x.XSync(d, 0)
        stale = second
        second = 0
        x.XSetAfterFunction(d, c.cast(foreign_request, c.c_void_p))
        desktop.cardinal(stale, '_NET_WM_PID')
        raise SystemExit(3)
    elif mode == 'foreign-errors':
        events = []
        @Handler
        def previous(display, event):
            e = event.contents
            events.append((display, e.resourceid, e.serial,
                           e.error_code, e.request_code, e.minor_code))
            return 0
        old = x.XSetErrorHandler(c.cast(previous, c.c_void_p))
        fired = False
        @After
        def during_request(display):
            global fired
            # Inject only while a temporary handler is installed. No fake errors.
            installed = x.XSetErrorHandler(c.cast(previous, c.c_void_p))
            x.XSetErrorHandler(installed)
            if not fired and installed != c.cast(previous, c.c_void_p).value:
                fired = True
                serial = x.XNextRequest(d) - 1
                # Match serial/resource/opcode on a different Display connection.
                while x.XNextRequest(other) < serial:
                    x.XNoOp(other)
                assert x.XNextRequest(other) == serial
                get(other, second, pid_atom)
                # Same display/resource/opcode, different request serial.
                get(d, second, pid_atom)
                # BadAtom and a different request opcode must also be delegated.
                get(d, desktop.root, 0x7fffffff)
                x.XDestroyWindow(d, second)
                x.XSync(d, 0)
            return 0
        x.XDestroyWindow(d, second)
        x.XSync(d, 0)
        old_after = x.XSetAfterFunction(d, c.cast(during_request, c.c_void_p))
        try:
            assert desktop.cardinal(second, '_NET_WM_PID') is None
            assert fired
            assert [(e[3], e[4], e[5]) for e in events] == [
                (3, 20, 0), (3, 20, 0), (5, 20, 0), (3, 4, 0)]
            assert events[0][0] == other and events[1][0] == d
            assert events[0][2] != events[1][2]
            assert events[0][1] == events[1][1] == second
            # A subsequent real error reaches exactly the previous handler.
            get(d, second, pid_atom)
            assert len(events) == 5
            assert desktop.active_pid() == os.getpid()
        finally:
            x.XSetAfterFunction(d, old_after)
            restored = x.XSetErrorHandler(old)
            assert restored == c.cast(previous, c.c_void_p).value
            second = 0
    else:
        raise SystemExit(4)
finally:
    if window:
        x.XDestroyWindow(d, window)
    if second:
        x.XDestroyWindow(d, second)
    x.XCloseDisplay(other)
    desktop.close()
"""


def authority_record(number: bytes, cookie: bytes) -> bytes:
    """Encode one MIT cookie for only the fixture's private authority file."""
    fields = [b"", number, b"MIT-MAGIC-COOKIE-1", cookie]
    return struct.pack("!H", 65535) + b"".join(
        struct.pack("!H", len(field)) + field for field in fields
    )


@pytest.fixture
def owned_x11(tmp_path: Path) -> Iterator[tuple[str, str, Path]]:
    """Start only an authenticated dynamic display and reap its exact process."""
    if os.getuid() == 0:
        pytest.skip("Desktop requires non-root execution")
    executable = shutil.which("Xvfb")
    if executable is None:
        pytest.skip("Xvfb is unavailable")
    library = os.environ.get("GOW_TEST_LIBX11") or ctypes.util.find_library("X11")
    if not library:
        pytest.skip("Host libX11 is unavailable; supply GOW_TEST_LIBX11")
    try:
        ctypes.CDLL(library)
    except OSError:
        if "GOW_TEST_LIBX11" in os.environ:
            raise
        pytest.skip("Host libX11 cannot load; supply GOW_TEST_LIBX11")
    authority = tmp_path / "authority"
    cookie = secrets.token_bytes(16)
    authority.write_bytes(authority_record(b"", cookie))
    authority.chmod(0o600)
    reader, writer = os.pipe()
    try:
        server = subprocess.Popen(  # noqa: S603 - Xvfb is resolved explicitly and owns only fixture state.
            [
                executable,
                "-displayfd",
                str(writer),
                "-screen",
                "0",
                "64x64x24",
                "-screen",
                "1",
                "64x64x24",
                "-nolisten",
                "tcp",
                "-auth",
                str(authority),
            ],
            pass_fds=(writer,),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        os.close(reader)
        authority.unlink()
        raise
    finally:
        os.close(writer)
    try:
        if not select.select([reader], [], [], 5)[0]:
            pytest.fail("Owned Xvfb did not publish its display within five seconds")
        number = os.read(reader, 64).strip()
        assert number.isdigit(), "Owned Xvfb did not publish a numeric display"
        authority.write_bytes(authority_record(number, cookie))
        yield library, ":" + number.decode("ascii"), authority
    finally:
        os.close(reader)
        try:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        finally:
            authority.unlink()


def run_desktop(
    fixture: tuple[str, str, Path], mode: str, authority: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Contain Xlib default-handler exits and enforce a finite child lifetime."""
    library, display, auth = fixture
    return subprocess.run(  # noqa: S603 - Execute only the controlled Xlib fixture program.
        [sys.executable, "-c", PROGRAM, library, display, mode],
        env={
            **os.environ,
            "DISPLAY": ":0",
            "XAUTHORITY": str(authority or auth),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("mode", ["destroyed", "malformed", "foreign-errors", "render"])
def test_actual_x11_observation_survives_only_expected_window_loss(
    owned_x11: tuple[str, str, Path], mode: str
) -> None:
    """Keep real Xlib observations usable after expected resource loss."""
    completed = run_desktop(owned_x11, mode)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "mode", ["pending-default", "restored-default", "foreign-default"]
)
def test_unrelated_x11_errors_keep_fatal_default_policy(
    owned_x11: tuple[str, str, Path], mode: str
) -> None:
    """Preserve Xlib's fatal policy for errors outside the scoped request."""
    completed = run_desktop(owned_x11, mode)
    assert completed.returncode == 1, completed.stderr
    assert "BadWindow" in completed.stderr


def test_owned_server_refuses_a_different_cookie(
    owned_x11: tuple[str, str, Path], tmp_path: Path
) -> None:
    """Refuse a genuine X11 connection using a different authentication cookie."""
    wrong = tmp_path / "wrong-authority"
    cookie = owned_x11[2].read_bytes()[-16:]
    different_cookie = bytes([cookie[0] ^ 1]) + cookie[1:]
    wrong.write_bytes(
        authority_record(owned_x11[1][1:].encode("ascii"), different_cookie)
    )
    wrong.chmod(0o600)
    try:
        completed = run_desktop(owned_x11, "unauthenticated", wrong)
        assert completed.returncode == 0, completed.stderr
    finally:
        wrong.unlink()


def test_visual_validation_uses_the_actual_connection_screen(
    owned_x11: tuple[str, str, Path],
) -> None:
    """Real two-screen Xlib rejects a valid visual belonging to another screen."""
    library, display, authority = owned_x11
    program = """
import ctypes as c
import sys
from batocera_gow.runtime.duckstation_visual import LiveVisual, VisualError, VisualInfo
# Only bypass EGL initialization, which this X11-only control does not qualify.
session = object.__new__(LiveVisual)
session.x = x = c.CDLL(sys.argv[1])
x.XOpenDisplay.argtypes = [c.c_char_p]
x.XOpenDisplay.restype = c.c_void_p
x.XDefaultScreen.argtypes = [c.c_void_p]
x.XDefaultScreen.restype = c.c_int
x.XDefaultVisual.argtypes = [c.c_void_p, c.c_int]
x.XDefaultVisual.restype = c.c_void_p
x.XVisualIDFromVisual.argtypes = [c.c_void_p]
x.XVisualIDFromVisual.restype = c.c_ulong
x.XGetVisualInfo.argtypes = [
    c.c_void_p, c.c_long, c.POINTER(VisualInfo), c.POINTER(c.c_int),
]
x.XGetVisualInfo.restype = c.POINTER(VisualInfo)
x.XFree.argtypes = [c.c_void_p]
x.XCloseDisplay.argtypes = [c.c_void_p]
session.connection = x.XOpenDisplay((sys.argv[2] + '.1').encode())
assert session.connection and x.XDefaultScreen(session.connection) == 1
try:
    current = x.XVisualIDFromVisual(x.XDefaultVisual(session.connection, 1))
    foreign = x.XVisualIDFromVisual(x.XDefaultVisual(session.connection, 0))
    assert current != foreign
    session.validate(current)
    for visual in (foreign, 0, 0xffffffff):
        try:
            session.validate(visual)
        except VisualError:
            pass
        else:
            raise RuntimeError('Foreign or nonexistent screen visual accepted')
finally:
    x.XCloseDisplay(session.connection)
"""
    completed = subprocess.run(  # noqa: S603 - Execute the controlled two-screen Xlib program.
        [sys.executable, "-c", program, library, display],
        env={
            **os.environ,
            "XAUTHORITY": str(authority),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
