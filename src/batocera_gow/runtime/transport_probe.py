r"""Disposable stock evmapy -> hotkeygen -> X11 diagnostic frontend.

Invoke through the input-transport supervisor and unchanged entrypoint, never
through docker exec. GOW_INPUT_TRIAL_RESULTS must name a writable results
mount. This command writes transport-probe.json there and exits 1 if any case
fails. It needs the packaged evdev, evmapy, hotkeygen and libX11, app-UID
/dev/uinput access, the supervisor's ready status, and an authenticated :0.
It does not patch stock code, install mappings, or claim Moonlight acceptance.

Set GOW_INPUT_TRIAL_RESULTS and an absolute GOW_INPUT_TRIAL_GATE path in that
directory. The operator creates the gate only after inspecting container
isolation, capabilities, image and mounts. Launch with:
    python3 /opt/gow-full-x86/input_transport.py -- \
        /opt/gow-full-x86/entrypoint.sh python3 \
        /opt/gow-full-x86/transport_probe.py

Set GOW_INPUT_TRIAL_CASE to one name in RECEIVER_CASES to run that assertion
alone. Unselected assertions are reported in not_run_cases, never as passes.
"""

import ctypes
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from types import FrameType, ModuleType
from typing import Literal, Protocol, TypedDict, runtime_checkable

from .native_diagnostics import (
    DiagnosticError,
    capture_checkpoint,
    input_permitted,
    publish_json,
    publish_selected_log,
)

ASSET_ROOT = Path("/opt/gow-full-x86")
STATUS = Path("/run/gow-full-x86-input-transport.json")
CONTEXT = Path("/var/run/hotkeygen.context")
EVMAPY = Path("/var/run/evmapy")
HOLD = 0.25
TIMEOUT = 12.0
RECEIVER_CASES = (
    "stock_combo_exit_held_and_pointer_reset",
    "stock_context_pointer_button",
    "context_switch_without_semantic_leakage",
    "held_graceful_source_removal_and_recreation",
    "stock_command_once_per_stock_release",
)
KEY_PRESS = 2
KEY_RELEASE = 3
BUTTON_PRESS = 4
BUTTON_RELEASE = 5
POINTER_MOTION = 6
CHORD_LENGTH = 2
FULL_CHORD_LENGTH = 4
COMMAND_RELEASES = 2


type FileIdentity = tuple[int, int, int, int]
type KeySequence = list[list[str]]
type ButtonSequence = list[list[int | str]]


class EventTiming(TypedDict):
    """Receiver timestamps use relative microseconds and X11 milliseconds."""

    at_us: int
    server_time_ms: int


class KeyEvent(EventTiming):
    """One allowlisted key transition addressed to the owned window."""

    kind: Literal["key"]
    key: str
    action: Literal["press", "release"]


class ButtonEvent(EventTiming):
    """One allowlisted pointer-button transition."""

    kind: Literal["button"]
    button: int
    action: Literal["press", "release"]


class MotionEvent(EventTiming):
    """One pointer position in root-window coordinates."""

    kind: Literal["motion"]
    x: int
    y: int


type Event = KeyEvent | ButtonEvent | MotionEvent


class CollectedEvents(TypedDict):
    """Ordered receiver events shared by collectors and scenario evidence."""

    events: list[Event]


class ScenarioEvidence(CollectedEvents, total=False):
    """Conditional observations recorded only after their scenario steps run."""

    capture: dict[str, object]
    error: str
    held_keys_during_hold: list[str]
    held_duration_ms: int
    source_removal_mode: str
    disconnect_error: str
    held_after_disconnect: list[str]
    disconnect_sequence: KeySequence
    disconnect_passed: bool
    recreated_first_use_passed: bool
    recreated_first_use_error: str
    recreated_events: list[Event]
    recreated_held_duration_ms: int | None
    held_after_recreated_first_use: list[str]
    command_count_observations: list[int]
    command_count_before_release: int
    command_count_after_release: int
    command_count_while_held_again: int
    command_count_after_source_removal: int


class CaseRow(ScenarioEvidence):
    """A selected case always records its identity, expectation and status."""

    name: str
    status: Literal["passed", "failed"]
    expected: Mapping[str, object]


@runtime_checkable
class Gamepad(Protocol):
    """The owned stock evdev device operations needed by either probe."""

    fd: int

    def write(self, event_type: int, code: int, value: int) -> None:
        """Send one event to this device."""
        ...

    def syn(self) -> None:
        """Commit queued events in their existing order."""
        ...

    def close(self) -> None:
        """Destroy this owned device and close its descriptor."""
        ...


class ProbeError(RuntimeError):
    """A required stock receiver observation or ownership check failed."""


def require(condition: object, message: str) -> None:
    """Reject an unmet diagnostic condition even under optimized Python."""
    if not condition:
        raise ProbeError(message)


def wait_for[T](
    description: str,
    predicate: Callable[[], T | None],
    timeout: float = TIMEOUT,
    *,
    check_permission: bool = True,
) -> T:
    """Poll for a truthy observation while preserving the native input lease.

    The predicate's successful value is returned unchanged. Timeouts are in
    seconds; only the pre-input inspection gate may disable lease checking.
    """
    if not math.isfinite(timeout) or timeout < 0:
        message = "diagnostic timeout must be finite and nonnegative"
        raise ProbeError(message)
    deadline = time.monotonic() + timeout
    while True:
        if check_permission:
            input_permitted()
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            message = "timeout waiting for " + description
            raise ProbeError(message)
        time.sleep(0.025)


def file_identity(path: Path) -> FileIdentity:
    """Identify a directory entry without following a replacement symlink."""
    info = path.lstat()
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_rdev


def remove_owned(path: Path, identity: FileIdentity) -> None:
    """Unlink only a still-matching owned entry; absence is already clean."""
    try:
        require(
            file_identity(path) == identity, "cleanup identity changed: " + str(path)
        )
        path.unlink()
    except FileNotFoundError:
        return


def object_record(value: object) -> dict[str, object]:
    """Validate external JSON objects without accepting non-string keys."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        message = "expected a diagnostic JSON object"
        raise ProbeError(message)
    return {str(key): item for key, item in value.items()}


def object_rows(value: object) -> list[dict[str, object]]:
    """Validate a JSON array of records at its file or socket boundary."""
    if not isinstance(value, list):
        message = "expected a diagnostic JSON record array"
        raise ProbeError(message)
    return [object_record(item) for item in value]


def sources(status: Mapping[str, object]) -> list[dict[str, object]]:
    """Read validated supervisor sources, treating an absent status as empty."""
    return object_rows(status.get("sources", []))


class XKeyEvent(ctypes.Structure):
    """Native-width XKeyEvent ABI also used by pointer event prefixes."""

    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class XEvent(ctypes.Union):
    """Full Xlib event union storage, including its platform-sized padding."""

    _fields_ = [("type", ctypes.c_int), ("key", XKeyEvent), ("pad", ctypes.c_long * 24)]


class XAttributes(ctypes.Structure):
    """XSetWindowAttributes ABI used to create a private override window."""

    _fields_ = [
        ("background_pixmap", ctypes.c_ulong),
        ("background_pixel", ctypes.c_ulong),
        ("border_pixmap", ctypes.c_ulong),
        ("border_pixel", ctypes.c_ulong),
        ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int),
        ("event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int),
        ("colormap", ctypes.c_ulong),
        ("cursor", ctypes.c_ulong),
    ]


class Receiver:
    """Read only events addressed to this frontend's own X11 window."""

    KEY_NAMES = ("Control_L", "Shift_L", "F9", "F10", "F11", "F12")

    def __init__(self) -> None:
        """Own a fresh authenticated display and clean partial window setup."""
        self.x = ctypes.CDLL("libX11.so.6")
        signatures = {
            "XOpenDisplay": (ctypes.c_void_p, [ctypes.c_char_p]),
            "XDefaultScreen": (ctypes.c_int, [ctypes.c_void_p]),
            "XRootWindow": (ctypes.c_ulong, [ctypes.c_void_p, ctypes.c_int]),
            "XDisplayWidth": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
            "XDisplayHeight": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
            "XCreateSimpleWindow": (
                ctypes.c_ulong,
                [
                    ctypes.c_void_p,
                    ctypes.c_ulong,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.c_ulong,
                    ctypes.c_ulong,
                ],
            ),
            "XChangeWindowAttributes": (
                ctypes.c_int,
                [
                    ctypes.c_void_p,
                    ctypes.c_ulong,
                    ctypes.c_ulong,
                    ctypes.POINTER(XAttributes),
                ],
            ),
            "XSelectInput": (
                ctypes.c_int,
                [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long],
            ),
            "XStoreName": (
                ctypes.c_int,
                [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p],
            ),
            "XMapRaised": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_ulong]),
            "XSetInputFocus": (
                ctypes.c_int,
                [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong],
            ),
            "XGetInputFocus": (
                ctypes.c_int,
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_ulong),
                    ctypes.POINTER(ctypes.c_int),
                ],
            ),
            "XSync": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
            "XPending": (ctypes.c_int, [ctypes.c_void_p]),
            "XNextEvent": (ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(XEvent)]),
            "XStringToKeysym": (ctypes.c_ulong, [ctypes.c_char_p]),
            "XKeysymToKeycode": (ctypes.c_ubyte, [ctypes.c_void_p, ctypes.c_ulong]),
            "XQueryKeymap": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p]),
            "XWarpPointer": (
                ctypes.c_int,
                [
                    ctypes.c_void_p,
                    ctypes.c_ulong,
                    ctypes.c_ulong,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.c_int,
                    ctypes.c_int,
                ],
            ),
            "XDestroyWindow": (ctypes.c_int, [ctypes.c_void_p, ctypes.c_ulong]),
            "XCloseDisplay": (ctypes.c_int, [ctypes.c_void_p]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.x, name)
            function.restype, function.argtypes = result, args
        opened: object = self.x.XOpenDisplay(None)
        if not isinstance(opened, int) or not opened:
            message = "authenticated XOpenDisplay failed"
            raise ProbeError(message)
        self.display: int | None = opened
        self.window = 0
        self.origin = time.monotonic()
        self.unknown = 0
        self.names: dict[int, str] = {}
        try:
            for name in self.KEY_NAMES:
                code = int(
                    self.x.XKeysymToKeycode(
                        self.display, self.x.XStringToKeysym(name.encode("ascii"))
                    )
                )
                require(
                    code and code not in self.names, "X keymap lacks distinct " + name
                )
                self.names[code] = name
            screen = self.x.XDefaultScreen(self.display)
            root = self.x.XRootWindow(self.display, screen)
            self.window = int(
                self.x.XCreateSimpleWindow(
                    self.display,
                    root,
                    0,
                    0,
                    self.x.XDisplayWidth(self.display, screen),
                    self.x.XDisplayHeight(self.display, screen),
                    0,
                    0,
                    0,
                )
            )
            require(self.window, "X11 receiver window creation failed")
            attributes = XAttributes()
            attributes.override_redirect = 1
            self.x.XChangeWindowAttributes(
                self.display, self.window, 1 << 9, ctypes.byref(attributes)
            )
            self.x.XStoreName(
                self.display, self.window, b"GoW stock input transport diagnostic"
            )
            self.x.XSelectInput(self.display, self.window, 1 | 2 | 4 | 8 | 64)
            self.x.XMapRaised(self.display, self.window)
            self.x.XSync(self.display, 0)
            self.x.XSetInputFocus(self.display, self.window, 1, 0)
            self.x.XSync(self.display, 0)
            wait_for("receiver focus", self.focused, 3)
        except BaseException:
            self.close()
            raise

    def focused(self) -> bool:
        """Check that the actual input focus still belongs to this window."""
        window, revert = ctypes.c_ulong(), ctypes.c_int()
        self.x.XGetInputFocus(self.display, ctypes.byref(window), ctypes.byref(revert))
        return window.value == self.window

    def read(self) -> list[Event]:
        """Drain ordered events, retaining only the diagnostic allowlist."""
        events: list[Event] = []
        while self.x.XPending(self.display):
            event = XEvent()
            self.x.XNextEvent(self.display, ctypes.byref(event))
            if event.type not in (
                KEY_PRESS,
                KEY_RELEASE,
                BUTTON_PRESS,
                BUTTON_RELEASE,
                POINTER_MOTION,
            ):
                continue
            key = event.key
            require(
                key.window == self.window and not key.send_event,
                "receiver got an event outside its owned authenticated window",
            )
            at_us = round((time.monotonic() - self.origin) * 1000000)
            server_time_ms = int(key.time)
            row: Event
            if event.type in (KEY_PRESS, KEY_RELEASE):
                if key.keycode not in self.names:
                    # Do not retain unrelated session keys or their identities.
                    self.unknown += 1
                    continue
                row = {
                    "at_us": at_us,
                    "server_time_ms": server_time_ms,
                    "kind": "key",
                    "key": self.names[key.keycode],
                    "action": "press" if event.type == KEY_PRESS else "release",
                }
            elif event.type in (BUTTON_PRESS, BUTTON_RELEASE):
                if key.keycode != 1:
                    self.unknown += 1
                    continue
                row = {
                    "at_us": at_us,
                    "server_time_ms": server_time_ms,
                    "kind": "button",
                    "button": 1,
                    "action": "press" if event.type == BUTTON_PRESS else "release",
                }
            else:
                row = {
                    "at_us": at_us,
                    "server_time_ms": server_time_ms,
                    "kind": "motion",
                    "x": int(key.x_root),
                    "y": int(key.y_root),
                }
            events.append(row)
        return events

    def collect(self, seconds: float) -> list[Event]:
        """Collect for a bounded interval while checking permission each poll."""
        deadline = time.monotonic() + seconds
        events: list[Event] = []
        while True:
            input_permitted()
            events.extend(self.read())
            if time.monotonic() >= deadline:
                return events
            time.sleep(0.005)

    def until(
        self,
        row: CollectedEvents,
        predicate: Callable[[list[Event]], bool],
        description: str,
        timeout: float = 3,
    ) -> None:
        """Append events until an observable scenario condition is satisfied."""
        deadline = time.monotonic() + timeout
        while True:
            input_permitted()
            row["events"].extend(self.read())
            if predicate(row["events"]):
                return
            if time.monotonic() >= deadline:
                message = "timeout waiting for receiver " + description
                raise ProbeError(message)
            time.sleep(0.005)

    def reset_pointer(self) -> None:
        """Warp inside the owned window and discard only the settling events."""
        self.x.XWarpPointer(self.display, 0, self.window, 0, 0, 0, 0, 200, 200)
        self.x.XSync(self.display, 0)
        self.collect(0.05)

    def held(self) -> list[str]:
        """Read current held state only for the diagnostic key allowlist."""
        bits = ctypes.create_string_buffer(32)
        self.x.XQueryKeymap(self.display, bits)
        return sorted(
            name
            for code, name in self.names.items()
            if bits.raw[code // 8] & (1 << (code % 8))
        )

    def close(self) -> None:
        """Destroy this window and close its display even if destruction fails."""
        display = self.display
        if display is None:
            return
        try:
            if self.window:
                self.x.XDestroyWindow(display, self.window)
        finally:
            self.x.XCloseDisplay(display)
            self.display = None


def keys(events: Iterable[Event]) -> KeySequence:
    """Extract key transitions without changing their receiver order."""
    return [
        [event["key"], event["action"]] for event in events if event["kind"] == "key"
    ]


def buttons(events: Iterable[Event]) -> ButtonSequence:
    """Extract pointer-button transitions in their receiver order."""
    return [
        [event["button"], event["action"]]
        for event in events
        if event["kind"] == "button"
    ]


def chord_events(names: Iterable[str], action: str) -> KeySequence:
    """Build the exact ordered key transitions expected for a stock chord."""
    return [[name, action] for name in names]


class Probe:
    """Own a disposable receiver, stock evmapy child and synthetic gamepad."""

    def __init__(self) -> None:
        """Initialize evidence without creating input, processes or files."""
        self.cases: list[CaseRow] = []
        self.errors: list[str] = []
        self.source_records: list[dict[str, object]] = []
        self.process_records: list[dict[str, object]] = []
        self.context_barriers: list[dict[str, object]] = []
        self.hash_evidence: dict[str, object] | None = None
        self.result: dict[str, object] = {
            "schema": 1,
            "status": "failed",
            "cases": self.cases,
            "errors": self.errors,
            "invocation": {
                "argv": sys.argv,
                "uid": os.getuid(),
                "gid": os.getgid(),
                "wrapper": [
                    "python3",
                    str(ASSET_ROOT / "input_transport.py"),
                    "--",
                    str(ASSET_ROOT / "entrypoint.sh"),
                    "python3",
                    str(ASSET_ROOT / "transport_probe.py"),
                ],
                "environment": {
                    key: os.environ.get(key)
                    for key in (
                        "DISPLAY",
                        "XAUTHORITY",
                        "XDG_SESSION_TYPE",
                        "GOW_INPUT_TRIAL_RESULTS",
                        "GOW_INPUT_TRIAL_GATE",
                    )
                },
            },
            "requirements": [
                "Unchanged stock Batocera evdev, evmapy, hotkeygen and libX11",
                (
                    "Owned supervisor descendant, app UID, accessible /dev/uinput "
                    "and input device cgroup permission"
                ),
                (
                    "Diagnostic supervisor ready status with pinned final batocera "
                    "hotkeys source and connected XTEST worker"
                ),
                (
                    "Fresh private trial session with no evmapy daemon or "
                    "controller JSON configurations"
                ),
                (
                    "Authenticated DISPLAY=:0, app Xauthority and writable "
                    "GOW_INPUT_TRIAL_RESULTS directory"
                ),
                (
                    "Operator-created GOW_INPUT_TRIAL_GATE file after native "
                    "container isolation inspection"
                ),
            ],
            "limits": [
                (
                    "Synthetic session-owned controller, not physical Moonlight "
                    "controller acceptance"
                ),
                (
                    "Only this frontend window is selected, never root input "
                    "or another application window"
                ),
                (
                    "Core X11 does not identify the original input device; "
                    "an isolated idle trial session is required"
                ),
                (
                    "Pointer motion uses stock hotkeygen exit reset; stock semantic "
                    "contexts have no general pointer-motion action"
                ),
                (
                    "Source loss tests graceful SIGTERM shutdown of probe-owned stock "
                    "evmapy, not crash recovery or runtime hotkeygen termination"
                ),
            ],
            "sources": self.source_records,
            "evmapy_processes": self.process_records,
            "context_barriers": self.context_barriers,
        }
        self.work: Path | None = None
        self.work_identity: FileIdentity | None = None
        self.receiver: Receiver | None = None
        self.pad: Gamepad | None = None
        self.evmapy: subprocess.Popen[bytes] | None = None
        self.owned_files: dict[Path, FileIdentity] = {}
        self.original_context: dict[str, object] | None = None
        self.context_saved = False
        self.context_changed = False
        self.context_identity: FileIdentity | None = None
        self.context_bytes: bytes | None = None
        self.canary = 0
        self.evdev: ModuleType | None = None
        self.output: Path | None = None
        self.hash_paths: list[Path] = []
        self.pad_config: Path | None = None
        self.pad_node = ""
        self.semantic_sysname = ""
        self.selected_case: str | None = None

    def active_receiver(self) -> Receiver:
        """Borrow the receiver only after successful initialization."""
        if self.receiver is None:
            message = "receiver is not initialized"
            raise ProbeError(message)
        return self.receiver

    def active_pad(self) -> Gamepad:
        """Borrow the currently owned pad without transferring its lifetime."""
        if self.pad is None:
            message = "gamepad is not initialized"
            raise ProbeError(message)
        return self.pad

    def work_directory(self) -> Path:
        """Require the private scratch directory before issuing stock commands."""
        if self.work is None:
            message = "private probe directory is not initialized"
            raise ProbeError(message)
        require(
            file_identity(self.work) == self.work_identity, "scratch identity changed"
        )
        return self.work

    def code(self, name: str) -> int:
        """Validate a named event constant from the actual stock evdev package."""
        if self.evdev is None:
            message = "stock evdev is not initialized"
            raise ProbeError(message)
        value: object = getattr(self.evdev.ecodes, name, None)
        if not isinstance(value, int):
            message = "stock evdev event code is not an integer"
            raise ProbeError(message)
        return value

    def record_evidence(self, extra_paths: Iterable[Path] = ()) -> None:
        """Record app credentials and hashes of stock inputs used by the case.

        Args:
            extra_paths: Additional stock files used by the selected native case.
        """
        fields = {"Uid", "Gid", "CapEff", "CapPrm", "CapAmb", "NoNewPrivs"}
        credentials = {}
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key in fields:
                credentials[key] = value.strip()
        self.result["app_credentials"] = credentials
        require(
            set(credentials) == fields, "application credential evidence is incomplete"
        )
        paths = [Path("/usr/bin/hotkeygen"), Path("/usr/bin/evmapy"), *extra_paths]
        paths.extend(
            Path("/etc/hotkeygen") / (name + ".conf")
            for name in ("default_mapping", "default_context", "common_context")
        )
        specification = importlib.util.find_spec("evmapy")
        if specification is None or not specification.submodule_search_locations:
            message = "packaged evmapy Python modules are unavailable"
            raise ProbeError(message)
        for directory in specification.submodule_search_locations:
            paths.extend(sorted(Path(directory).glob("*.py")))
        self.hash_paths = sorted(set(paths))
        self.hash_evidence = {"before": self.stock_hashes()}
        self.result["stock_hashes"] = self.hash_evidence

    def stock_hashes(self) -> dict[str, str]:
        """Hash only the selected stock inputs used by this diagnostic."""
        hashes = {}
        for path in self.hash_paths:
            with path.open("rb") as stream:
                hashes[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
        return hashes

    def record_final_hashes(self) -> None:
        """Fail cleanup if a selected stock file changed during observation."""
        evidence = self.hash_evidence
        if evidence is None:
            return
        evidence["after"] = self.stock_hashes()
        evidence["unchanged"] = evidence["before"] == evidence["after"]
        require(
            evidence["unchanged"],
            "packaged stock input files changed during diagnostic",
        )

    def status(self) -> dict[str, object]:
        """Read a safe supervisor status and validate its record-array boundary."""
        try:
            info = STATUS.lstat()
            require(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == 0
                and not info.st_mode & 0o022,
                "unsafe supervisor status file",
            )
            data = object_record(json.loads(STATUS.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return {}
        require(
            not data.get("error"),
            "supervisor reported failure: " + str(data.get("error")),
        )
        sources(data)
        return data

    def command(self, args: Sequence[str]) -> None:
        """Run one bounded stock hotkeygen command without retaining its output."""
        require(
            bool(args) and args[0] == "/usr/bin/hotkeygen",
            "only the stock hotkeygen executable is permitted",
        )
        # The executable is fixed above; context data remains separate argv.
        completed = subprocess.run(  # noqa: S603
            args, capture_output=True, text=True, timeout=5, check=False
        )
        require(
            completed.returncode == 0,
            "stock command failed: "
            + args[0]
            + " returned "
            + str(completed.returncode),
        )

    def remember(self, path: Path) -> None:
        """Pin an entry allocated by this probe before later cleanup."""
        self.owned_files[path] = file_identity(path)

    def setup(self) -> None:
        """Validate isolation and the operator gate before allocating input."""
        destination = os.environ.get("GOW_INPUT_TRIAL_RESULTS")
        if not destination or not Path(destination).is_absolute():
            message = "GOW_INPUT_TRIAL_RESULTS must be an absolute results directory"
            raise ProbeError(message)
        directory = Path(destination)
        require(directory.is_dir(), "results directory does not exist")
        self.output = directory / "transport-probe.json"
        require(
            not self.output.exists() and not self.output.is_symlink(),
            "refusing to overwrite an existing transport-probe.json",
        )
        require(os.getuid() != 0, "probe must run as the non-root application UID")
        require(
            Path("/.dockerenv").exists() and Path("/usr/bin/hotkeygen").is_file(),
            "probe requires the actual stock container",
        )
        require(
            os.environ.get("DISPLAY") == ":0" and os.environ.get("XAUTHORITY"),
            "missing authenticated stock X11 app environment",
        )
        require(
            not any(key in os.environ for key in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET")),
            "application Wayland environment is forbidden",
        )
        self.record_evidence()
        if os.environ.get("GOW_NATIVE_RESULTS"):
            publish_json(
                directory / "startup.json",
                {"uid": os.getuid(), "gid": os.getgid(), "mode": "stock-receivers"},
            )
        self.wait_operator_gate(directory)

        def final_ready() -> dict[str, object] | None:
            data = self.status()
            finals = [
                source
                for source in sources(data)
                if source.get("name") == "batocera hotkeys"
            ]
            if not data.get("ready") or not data.get("worker_connected") or not finals:
                return None
            require(len(finals) == 1, "expected exactly one pinned stock final device")
            return finals[0]

        final = wait_for(
            "connected XTEST worker and pinned final source", final_ready, 25
        )
        self.source_records.append(
            {
                key: final.get(key)
                for key in ("role", "name", "sysname", "node", "source_pid")
            }
        )
        # Stock evdev is deliberately loaded only after native permission.
        self.evdev = importlib.import_module("evdev")
        require(
            EVMAPY.is_dir() and not EVMAPY.is_symlink(),
            "stock evmapy runtime directory missing",
        )
        require(
            not list(EVMAPY.glob("*.json")),
            "existing controller configurations would exceed trial scope",
        )
        require(
            not any(
                path.exists() or path.is_symlink()
                for path in (EVMAPY / "evmapy.socket", EVMAPY / "ready")
            ),
            "existing evmapy state is not owned by this trial",
        )
        if CONTEXT.exists() or CONTEXT.is_symlink():
            require(stat.S_ISREG(CONTEXT.lstat().st_mode), "unsafe hotkeygen context")
            self.context_identity = file_identity(CONTEXT)
            self.context_bytes = CONTEXT.read_bytes()
            self.original_context = object_record(json.loads(self.context_bytes))
            if not isinstance(self.original_context.get("name"), str):
                message = "stock context name is not a string"
                raise ProbeError(message)
            object_record(self.original_context.get("keys"))
        self.context_saved = True
        self.work = Path(tempfile.mkdtemp(prefix="gow-input-trial-", dir="/var/run"))
        self.work_identity = file_identity(self.work)
        self.receiver = Receiver()
        self.new_pad()
        self.start_evmapy()

    def wait_operator_gate(self, directory: Path) -> None:
        """Require the owned inspection gate before allowing any synthetic input."""
        gate_value = os.environ.get("GOW_INPUT_TRIAL_GATE")
        if not gate_value or not Path(gate_value).is_absolute():
            message = "GOW_INPUT_TRIAL_GATE must name an absolute inspection gate file"
            raise ProbeError(message)
        gate = Path(gate_value)
        require(
            gate.parent.resolve() == directory.resolve()
            or (
                os.environ.get("GOW_NATIVE_LEASE") == str(gate)
                and gate.parent.name == ".native-control"
                and gate.parent.parent.resolve() == directory.parent.resolve()
            ),
            "operator gate must be inside the owned results/control directory",
        )

        def gate_open() -> bool:
            try:
                info = gate.lstat()
            except FileNotFoundError:
                return False
            require(
                stat.S_ISREG(info.st_mode),
                "operator gate is not a regular non-symlink file",
            )
            return True

        wait_for(
            "operator container-inspection gate before creating input",
            gate_open,
            90,
            check_permission=False,
        )
        input_permitted()
        self.result["operator_gate_observed"] = True

    def new_pad(self) -> None:
        """Create and pin only this session's stock-compatible synthetic pad."""
        if self.evdev is None:
            message = "stock evdev is not initialized"
            raise ProbeError(message)
        require(self.pad is None, "refusing to replace a live owned gamepad")
        # These are the Guide/start and face-button names used in stock hotkeys.keys.
        pad: object = self.evdev.UInput(
            name="gow input trial gamepad",
            vendor=0x1209,
            product=0x4301,
            phys="gow-input-trial",
            events={
                self.code("EV_KEY"): [
                    self.code("BTN_MODE"),
                    self.code("BTN_START"),
                    self.code("BTN_SOUTH"),
                    self.code("BTN_EAST"),
                    self.code("BTN_NORTH"),
                ]
            },
        )
        if not isinstance(pad, Gamepad):
            message = "stock UInput does not provide the gamepad ownership API"
            raise ProbeError(message)
        self.pad = pad
        uinput = importlib.import_module("evdev._uinput")
        sysname: object = uinput.get_sysname(pad.fd)
        if not isinstance(sysname, str) or not re.fullmatch(r"input[0-9]+", sysname):
            message = "unexpected UI_GET_SYSNAME result"
            raise ProbeError(message)
        syspath = Path("/sys/devices/virtual/input") / sysname
        entries = [
            path
            for path in syspath.iterdir()
            if re.fullmatch(r"event[0-9]+", path.name)
        ]
        require(len(entries) == 1, "owned gamepad has no unique sysfs event identity")
        entry = entries[0]
        node = Path("/dev/input") / entry.name
        major, minor = map(
            int, (entry / "dev").read_text(encoding="utf-8").strip().split(":")
        )
        expected_devt = os.makedev(major, minor)

        def exposed() -> dict[str, object] | None:
            source = next(
                (
                    source
                    for source in sources(self.status())
                    if source.get("sysname") == sysname
                    and source.get("source_pid") == os.getpid()
                ),
                None,
            )
            if source is None or not node.exists():
                return None
            info = node.stat()
            require(
                stat.S_ISCHR(info.st_mode) and info.st_rdev == expected_devt,
                "forwarded gamepad dev_t differs from owned sysfs identity",
            )
            return source

        record = wait_for("owned gamepad forwarding", exposed)
        self.source_records.append(
            {
                key: record.get(key)
                for key in ("role", "name", "sysname", "node", "source_pid")
            }
        )
        self.pad_node = str(node)
        self.write_pad_configuration(entry.name)

    def write_pad_configuration(self, event_name: str) -> None:
        """Publish one exclusive controller mapping derived from stock actions."""
        require(
            re.fullmatch(r"event[0-9]+", event_name),
            "gamepad configuration requires a pinned event name",
        )
        config = EVMAPY / (event_name + ".json")
        stock_actions = object_record(
            json.loads(
                Path("/usr/share/evmapy/hotkeys.keys").read_text(encoding="utf-8")
            )
        )
        actions = object_rows(stock_actions.get("actions_player1"))
        wanted = [["hotkey", "start"], ["hotkey", "b"], ["hotkey", "y"]]
        selected: list[dict[str, object]] = []
        for trigger in wanted:
            matches = [action for action in actions if action.get("trigger") == trigger]
            require(
                len(matches) == 1 and matches[0].get("type") == "key",
                "packaged hotkeys.keys lacks required stock action " + repr(trigger),
            )
            selected.append(
                {
                    key: value
                    for key, value in matches[0].items()
                    if key != "description"
                }
            )
        mapping = object_record(
            json.loads(
                Path("/etc/hotkeygen/default_mapping.conf").read_text(encoding="utf-8")
            )
        )
        require(
            mapping.get("KEY_EXIT") == "exit"
            and mapping.get("KEY_MENU") == "menu"
            and mapping.get("KEY_SAVE") == "save_state",
            "stock semantic mapping prerequisite differs",
        )
        self.result["stock_controller_actions"] = selected
        with config.open("x", encoding="utf-8") as stream:
            self.remember(config)
            self.pad_config = config
            json.dump(
                {
                    "grab": False,
                    "axes": [],
                    "buttons": [
                        {"name": "hotkey", "code": self.code("BTN_MODE")},
                        {"name": "start", "code": self.code("BTN_START")},
                        {"name": "b", "code": self.code("BTN_SOUTH")},
                        {"name": "a", "code": self.code("BTN_EAST")},
                        {"name": "y", "code": self.code("BTN_NORTH")},
                    ],
                    "actions": selected,
                },
                stream,
                sort_keys=True,
            )

    def control_list(self) -> list[dict[str, object]] | None:
        """Query only the trial's stock evmapy through a private reply socket."""
        client = self.work_directory() / "control.socket"
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
            connection.settimeout(0.25)
            connection.bind(str(client))
            self.remember(client)
            identity = file_identity(client)
            try:
                connection.sendto(
                    b'{"command":"list","wait":true}', str(EVMAPY / "evmapy.socket")
                )
                devices = object_rows(json.loads(connection.recv(65536)))
            except (TimeoutError, FileNotFoundError, ConnectionRefusedError):
                return None
            else:
                return devices
            finally:
                remove_owned(client, identity)
                del self.owned_files[client]

    def start_evmapy(self) -> None:
        """Own one stock daemon and qualify its actual controller subscription."""
        require(self.evmapy is None, "refusing to replace a live evmapy child")
        require(
            not any(
                path.exists() or path.is_symlink()
                for path in (EVMAPY / "evmapy.socket", EVMAPY / "ready")
            ),
            "refusing to replace existing evmapy runtime state",
        )
        # This is a fixed stock executable; the probe owns and reaps the child.
        self.evmapy = subprocess.Popen(
            ["/usr/bin/evmapy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        process = self.evmapy

        def ready() -> list[dict[str, object]] | None:
            self.remember_evmapy_entries()
            require(
                process.poll() is None,
                "probe-owned stock evmapy exited before readiness",
            )
            if (
                not (EVMAPY / "ready").exists()
                or not (EVMAPY / "evmapy.socket").exists()
            ):
                return None
            devices = self.control_list()
            if devices is None:
                return None
            require(
                len(devices) == 1 and devices[0].get("path") == self.pad_node,
                "stock evmapy subscribed outside the owned controller "
                "or failed to load its configuration",
            )
            return devices

        wait_for("stock evmapy ready and subscribed to owned gamepad", ready)
        semantic = wait_for(
            "owned evmapy semantic device forwarding",
            lambda: next(
                (
                    source
                    for source in sources(self.status())
                    if source.get("name") == "evmapy"
                    and source.get("source_pid") == process.pid
                ),
                None,
            ),
        )
        self.source_records.append(
            {
                key: semantic.get(key)
                for key in ("role", "name", "sysname", "node", "source_pid")
            }
        )
        sysname = semantic.get("sysname")
        if not isinstance(sysname, str):
            message = "forwarded semantic source lacks its sysfs name"
            raise ProbeError(message)
        self.semantic_sysname = sysname
        # Public context changes signal the already-running stock daemon. The
        # receiver canary below confirms both its reload and semantic subscription.

    def remember_evmapy_entries(self) -> None:
        """Pin residual child allocations, including after partial startup failure.

        Startup has already refused all existing entries. Only app-owned regular
        readiness files and Unix sockets are eligible, never symlinks or foreign
        replacements of an entry that was already recorded.
        """
        for name in ("ready", "evmapy.socket"):
            path = EVMAPY / name
            if path in self.owned_files:
                continue
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            expected_type = stat.S_ISREG if name == "ready" else stat.S_ISSOCK
            require(
                expected_type(info.st_mode) and info.st_uid == os.getuid(),
                "evmapy left an unsafe or foreign runtime entry",
            )
            self.owned_files[path] = (
                info.st_dev,
                info.st_ino,
                stat.S_IFMT(info.st_mode),
                info.st_rdev,
            )

    def stop_evmapy(self, *, graceful: bool = False) -> None:
        """Reap only the owned child and remove its still-matching runtime entries."""
        forced_kill = False
        returncode = None
        if self.evmapy is not None:
            process = self.evmapy
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    forced_kill = True
                    process.kill()
                    process.wait(timeout=3)
            returncode = process.returncode
            self.process_records.append(
                {
                    "pid": process.pid,
                    "returncode": returncode,
                    "forced_kill": forced_kill,
                }
            )
            self.evmapy = None
            self.remember_evmapy_entries()
        for name in ("evmapy.socket", "ready"):
            path = EVMAPY / name
            identity = self.owned_files.get(path)
            if identity is not None:
                remove_owned(path, identity)
                del self.owned_files[path]
        if graceful:
            require(
                not forced_kill and returncode == 0,
                "stock evmapy did not complete graceful SIGTERM cleanup",
            )

    def combo(self, button: int, *, pressed: bool) -> None:
        """Press Guide first, release it last, and commit one ordered frame."""
        event_type = self.code("EV_KEY")
        guide = self.code("BTN_MODE")
        if pressed:
            input_permitted()
            self.active_pad().write(event_type, guide, 1)
            self.active_pad().write(event_type, button, 1)
        else:
            self.active_pad().write(event_type, button, 0)
            self.active_pad().write(event_type, guide, 0)
        self.active_pad().syn()

    def context(self, name: str, mappings: Mapping[str, str | list[str]]) -> None:
        """Change only the trial's context and observe stock reload via a canary."""
        self.require_context_ownership()
        self.canary += 1
        marker = "F9" if self.canary % 2 else "F10"
        updated = dict(mappings, save_state="KEY_" + marker)
        self.context_changed = True
        try:
            self.command(
                [
                    "/usr/bin/hotkeygen",
                    "--disable-common",
                    "--new-context",
                    name,
                    json.dumps(updated, sort_keys=True),
                ]
            )
        finally:
            # A failed command can still have written the owned context.
            # Never claim a different context merely because the command ran.
            self.remember_context(name, updated)
        deadline = time.monotonic() + TIMEOUT
        attempts: list[KeySequence] = []
        while time.monotonic() < deadline:
            self.active_receiver().collect(0.05)
            self.combo(self.code("BTN_NORTH"), pressed=True)
            # Wait for actual keydown before releasing, not a launch-time sleep.
            trial: CollectedEvents = {"events": []}
            try:
                self.active_receiver().until(
                    trial,
                    lambda events: any(
                        event["kind"] == "key" and event["action"] == "press"
                        for event in events
                    ),
                    "context canary",
                    1.2,
                )
            except ProbeError:
                pass
            finally:
                self.combo(self.code("BTN_NORTH"), pressed=False)
            trial["events"].extend(self.active_receiver().collect(0.15))
            sequence = keys(trial["events"])
            attempts.append(sequence)
            if sequence == [[marker, "press"], [marker, "release"]]:
                self.context_barriers.append(
                    {"name": name, "marker": marker, "attempt_sequences": attempts}
                )
                require(
                    not self.active_receiver().held(),
                    "key held after context readiness canary",
                )
                return
        message = (
            "timeout waiting for observed stock context reload "
            "and semantic forwarding: " + name
        )
        raise ProbeError(message)

    def case(
        self,
        name: str,
        expected: Mapping[str, object],
        function: Callable[[CaseRow], None],
    ) -> CaseRow | None:
        """Run a selected scenario; unselected cases allocate no case resources."""
        if self.selected_case is not None and name != self.selected_case:
            return None
        row: CaseRow = {
            "name": name,
            "status": "failed",
            "expected": expected,
            "events": [],
        }
        self.cases.append(row)
        try:
            require(self.active_receiver().focused(), "receiver lost focus")
            self.active_receiver().collect(0.05)
            self.active_receiver().origin = time.monotonic()
            function(row)
            require(
                not self.active_receiver().unknown,
                "unexpected receiver input; identities were not recorded",
            )
            if os.environ.get("GOW_NATIVE_RESULTS"):
                row["capture"] = self.capture_case(name)
            row["status"] = "passed"
        except InterruptedError:
            raise
        except (
            ProbeError,
            DiagnosticError,
            OSError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            row["error"] = str(error)
        return row

    def capture_case(self, name: str) -> dict[str, object]:
        """Capture only a named scenario into the initialized output directory."""
        if self.output is None:
            message = "probe output directory is not initialized"
            raise ProbeError(message)
        return capture_checkpoint(self.output.parent / (name + ".png"))

    def held_chord(
        self,
        row: ScenarioEvidence,
        chord: Sequence[str],
        *,
        button: int | None = None,
        pointer: bool = False,
    ) -> None:
        """Require exact key ordering and held duration, then prove full release."""
        button = self.code("BTN_START") if button is None else button
        down, up = chord_events(chord, "press"), chord_events(chord, "release")
        self.active_receiver().reset_pointer()
        self.combo(button, pressed=True)
        try:
            self.active_receiver().until(
                row, lambda events: len(keys(events)) >= len(down), "chord press"
            )
            require(keys(row["events"]) == down, "unexpected chord press sequence")
            row["events"].extend(self.active_receiver().collect(HOLD))
            require(
                keys(row["events"]) == down,
                "held action released or repeated before controller release",
            )
            row["held_keys_during_hold"] = self.active_receiver().held()
            require(
                row["held_keys_during_hold"] == sorted(chord),
                "X11 held key state differs",
            )
        finally:
            self.combo(button, pressed=False)
        self.active_receiver().until(
            row,
            lambda events: len(keys(events)) >= len(down) + len(up),
            "chord release",
        )
        row["events"].extend(self.active_receiver().collect(0.08))
        require(
            keys(row["events"]) == down + up, "unexpected full chord event sequence"
        )
        require(
            not buttons(row["events"]),
            "semantic key leaked as an unexpected pointer button",
        )
        require(
            not self.active_receiver().held(), "X11 key remained held after release"
        )
        key_rows = [event for event in row["events"] if event["kind"] == "key"]
        row["held_duration_ms"] = (
            key_rows[len(chord)]["server_time_ms"] - key_rows[0]["server_time_ms"]
        ) & 0xFFFFFFFF
        require(
            row["held_duration_ms"] >= HOLD * 1000 - 20,
            "held action duration was shortened",
        )
        if pointer:
            first_key = next(
                index
                for index, event in enumerate(row["events"])
                if event["kind"] == "key"
            )
            require(
                any(
                    event["kind"] == "motion" and event["x"] == 0 and event["y"] == 0
                    for event in row["events"][:first_key]
                ),
                "stock exit pointer reset did not precede chord",
            )

    def pointer_button(self, row: CaseRow) -> None:
        """Require a single held BTN_LEFT click with no semantic-key leakage."""
        self.active_receiver().reset_pointer()
        self.combo(self.code("BTN_SOUTH"), pressed=True)
        try:
            self.active_receiver().until(
                row, lambda events: bool(buttons(events)), "stock context button press"
            )
            row["events"].extend(self.active_receiver().collect(HOLD))
            require(
                buttons(row["events"]) == [[1, "press"]], "button hold sequence differs"
            )
        finally:
            self.combo(self.code("BTN_SOUTH"), pressed=False)
        self.active_receiver().until(
            row,
            lambda events: len(buttons(events)) >= COMMAND_RELEASES,
            "stock context button release",
        )
        row["events"].extend(self.active_receiver().collect(0.08))
        require(
            buttons(row["events"]) == [[1, "press"], [1, "release"]]
            and not keys(row["events"]),
            "stock BTN_LEFT context did not produce exactly one click "
            "without semantic leakage",
        )
        button_rows = [event for event in row["events"] if event["kind"] == "button"]
        row["held_duration_ms"] = (
            button_rows[1]["server_time_ms"] - button_rows[0]["server_time_ms"]
        ) & 0xFFFFFFFF
        require(
            row["held_duration_ms"] >= HOLD * 1000 - 20, "button hold was shortened"
        )

    def loss_and_recreation(self, row: CaseRow) -> None:
        """Prove graceful source loss releases held keys and first reuse works."""
        chord = ["Control_L", "F12"]
        row["source_removal_mode"] = "graceful_SIGTERM"
        self.combo(self.code("BTN_START"), pressed=True)
        try:
            self.active_receiver().until(
                row,
                lambda events: len(keys(events)) >= CHORD_LENGTH,
                "pre-disconnect held chord",
            )
            require(
                keys(row["events"]) == chord_events(chord, "press"),
                "pre-disconnect sequence differs",
            )
            row["events"].extend(self.active_receiver().collect(HOLD))
            self.stop_evmapy(graceful=True)
            wait_for(
                "semantic source revoked after owned evmapy exit",
                lambda: (
                    not any(
                        source.get("sysname") == self.semantic_sysname
                        for source in sources(self.status())
                    )
                ),
                4,
            )
            try:
                self.active_receiver().until(
                    row,
                    lambda events: len(keys(events)) >= FULL_CHORD_LENGTH,
                    "disconnect releases",
                    2,
                )
            except ProbeError:
                row["disconnect_error"] = (
                    "no complete X11 release after owned semantic source removal"
                )
            row["events"].extend(self.active_receiver().collect(0.1))
            row["held_after_disconnect"] = self.active_receiver().held()
            row["disconnect_sequence"] = keys(row["events"])
            # Graceful stock uinput destruction and transport source revocation
            # can release in different orders. Require each held key exactly
            # once, with no extra key or button events and no stuck state.
            sequence = keys(row["events"])
            row["disconnect_passed"] = (
                sequence[:2] == chord_events(chord, "press")
                and sorted(sequence[2:]) == sorted(chord_events(chord, "release"))
                and not buttons(row["events"])
                and not row["held_after_disconnect"]
            )
        finally:
            self.combo(self.code("BTN_START"), pressed=False)
        self.active_pad().close()
        self.pad = None
        if self.pad_config is None:
            message = "owned gamepad configuration is missing"
            raise ProbeError(message)
        remove_owned(self.pad_config, self.owned_files[self.pad_config])
        del self.owned_files[self.pad_config]
        self.pad_config = None
        self.new_pad()
        self.start_evmapy()
        self.context("trial-recreated", {"exit": ["KEY_LEFTCTRL", "KEY_F12"]})
        # The first combo must work without a clearing cycle. A worker-only
        # release can leave the stock final uinput kernel state held, suppressing
        # this first new press. Keep that failure visible.
        recreated: ScenarioEvidence = {"events": []}
        try:
            self.held_chord(recreated, chord)
        except ProbeError as error:
            row["recreated_first_use_passed"] = False
            row["recreated_first_use_error"] = str(error)
            recreated["events"].extend(self.active_receiver().collect(0.2))
        else:
            row["recreated_first_use_passed"] = True
        finally:
            row["recreated_events"] = recreated["events"]
            row["recreated_held_duration_ms"] = recreated.get("held_duration_ms")
            row["held_after_recreated_first_use"] = self.active_receiver().held()
        require(
            row.get("recreated_first_use_passed") is True,
            "first combo after source recreation failed",
        )
        require(
            row["disconnect_passed"],
            "source removal left held state or changed disconnect event sequence",
        )

    def command_release(self, row: CaseRow, counter: Path) -> None:
        """Observe command-on-release twice, including graceful semantic loss."""

        def count() -> int:
            require(
                file_identity(counter) == self.owned_files[counter],
                "command counter identity changed",
            )
            data = counter.read_bytes() if counter.exists() else b""
            value = data.count(b"command\n")
            observations = row.setdefault("command_count_observations", [])
            if not observations or observations[-1] != value:
                observations.append(value)
            require(data == b"command\n" * value, "stock command wrote unexpected data")
            require(
                value <= COMMAND_RELEASES,
                "stock command executed "
                + str(value)
                + " times for two release actions",
            )
            return value

        self.combo(self.code("BTN_START"), pressed=True)
        try:
            row["events"].extend(self.active_receiver().collect(0.4))
            row["command_count_before_release"] = count()
            require(count() == 0, "stock command ran on press rather than release")
        finally:
            self.combo(self.code("BTN_START"), pressed=False)
        wait_for("stock command action on controller release", lambda: count() == 1, 3)
        row["events"].extend(self.active_receiver().collect(0.35))
        row["command_count_after_release"] = count()
        require(
            count() == 1 and not keys(row["events"]) and not buttons(row["events"]),
            "command count differs or semantic command key leaked into X11",
        )
        # Graceful stock evmapy shutdown destroys its held semantic keyboard.
        # Its real release is another stock hotkeygen command action, not a
        # helper-generated semantic event. Expect exactly one execution for it.
        row["source_removal_mode"] = "graceful_SIGTERM"
        self.combo(self.code("BTN_START"), pressed=True)
        try:
            row["events"].extend(self.active_receiver().collect(0.3))
            row["command_count_while_held_again"] = count()
            require(count() == 1, "second command press executed before release")
            self.stop_evmapy(graceful=True)
            wait_for(
                "command semantic source revocation",
                lambda: (
                    not any(
                        source.get("sysname") == self.semantic_sysname
                        for source in sources(self.status())
                    )
                ),
                4,
            )
            wait_for(
                "one stock command for graceful semantic-device release",
                lambda: count() == COMMAND_RELEASES,
                3,
            )
            row["events"].extend(self.active_receiver().collect(0.35))
            row["command_count_after_source_removal"] = count()
            require(
                count() == COMMAND_RELEASES,
                "graceful source removal did not execute exactly one "
                "additional stock command",
            )
            require(
                not keys(row["events"]) and not buttons(row["events"]),
                "command-source removal leaked a semantic key or button",
            )
        finally:
            self.combo(self.code("BTN_START"), pressed=False)

    def run(self) -> None:
        """Execute all five stock receiver scenarios without changing stock policy."""
        selected = os.environ.get("GOW_INPUT_TRIAL_CASE")
        if selected is not None and selected not in RECEIVER_CASES:
            message = "GOW_INPUT_TRIAL_CASE must name a supported receiver scenario"
            raise ProbeError(message)
        self.selected_case = selected
        self.result["selected_case"] = selected
        self.setup()
        first = ["Control_L", "F12"]
        self.context(
            "trial-chord-one",
            {"exit": ["KEY_LEFTCTRL", "KEY_F12"], "menu": ["BTN_LEFT"]},
        )
        self.case(
            "stock_combo_exit_held_and_pointer_reset",
            {
                "keys": chord_events(first, "press") + chord_events(first, "release"),
                "held_ms_minimum": HOLD * 1000 - 20,
                "pointer_reset_before_keys": [0, 0],
            },
            lambda row: self.held_chord(row, first, pointer=True),
        )
        self.case(
            "stock_context_pointer_button",
            {"buttons": [[1, "press"], [1, "release"]], "keys": []},
            self.pointer_button,
        )
        second = ["Shift_L", "F11"]
        self.context("trial-chord-two", {"exit": ["KEY_LEFTSHIFT", "KEY_F11"]})
        self.case(
            "context_switch_without_semantic_leakage",
            {"keys": chord_events(second, "press") + chord_events(second, "release")},
            lambda row: self.held_chord(row, second),
        )
        self.context("trial-disconnect", {"exit": ["KEY_LEFTCTRL", "KEY_F12"]})
        self.case(
            "held_graceful_source_removal_and_recreation",
            {
                "press": chord_events(first, "press"),
                "release_each_once_any_order": first,
                "source_removal_mode": "graceful_SIGTERM",
                "disconnect_release_timeout_seconds": 2,
                "held_after_disconnect": [],
                "recreated_keys": chord_events(first, "press")
                + chord_events(first, "release"),
            },
            self.loss_and_recreation,
        )
        counter = self.work_directory() / "command-count"
        with counter.open("xb"):
            self.remember(counter)
        # The command itself is handled only by stock hotkeygen's release path.
        # A path created by mkdtemp under /var/run contains no shell metacharacters.
        command = "printf 'command\\n' >> " + str(counter)
        self.context("trial-command", {"exit": command})
        self.case(
            "stock_command_once_per_stock_release",
            {
                "keys": [],
                "buttons": [],
                "command_count_before_release": 0,
                "command_count_after_release": 1,
                "command_count_while_held_again": 1,
                "command_count_after_source_removal": 2,
                "source_removal_mode": "graceful_SIGTERM",
            },
            lambda row: self.command_release(row, counter),
        )
        require(
            not self.active_receiver().held(),
            "receiver still has a diagnostic key held at completion",
        )
        self.result["unexpected_receiver_event_count"] = self.active_receiver().unknown
        require(
            not self.active_receiver().unknown,
            "unexpected receiver input was discarded without recording identities",
        )
        self.result["status"] = (
            "passed"
            if all(row["status"] == "passed" for row in self.cases)
            else "failed"
        )

    def close(self) -> None:
        """Attempt every owned teardown even if a preceding cleanup step fails."""
        failures: list[str] = []
        for action in (
            self.stop_evmapy,
            self.close_pad,
            self.restore_context,
            self.record_final_hashes,
        ):
            try:
                action()
            except (
                ProbeError,
                OSError,
                ValueError,
                subprocess.SubprocessError,
            ) as error:
                failures.append(str(error))
        for path, identity in list(self.owned_files.items()):
            try:
                remove_owned(path, identity)
                del self.owned_files[path]
            except (ProbeError, OSError) as error:
                failures.append(str(error))
        failures.extend(self.close_receiver())
        if self.work is not None:
            try:
                self.remove_work_directory()
            except (ProbeError, OSError) as error:
                failures.append(str(error))
        self.result["cleanup"] = {
            "status": "failed" if failures else "passed",
            "errors": failures,
        }
        if failures:
            self.result["status"] = "failed"

    def close_receiver(self) -> list[str]:
        """Always close the owned display, including after held-state query failure."""
        receiver = self.receiver
        if receiver is None:
            return []
        failures: list[str] = []
        try:
            held = receiver.held()
            self.result["held_keys_at_cleanup"] = held
            if held:
                failures.append("diagnostic keys still held at receiver cleanup")
        except (ProbeError, OSError) as error:
            failures.append(str(error))
        finally:
            try:
                receiver.close()
                self.receiver = None
            except (ProbeError, OSError) as error:
                failures.append(str(error))
        return failures

    def remove_work_directory(self) -> None:
        """Remove only an unchanged empty scratch directory, never unknown contents."""
        if self.work is None:
            return
        require(
            file_identity(self.work) == self.work_identity,
            "refusing cleanup of replaced scratch directory",
        )
        self.work.rmdir()
        self.work = None

    def close_pad(self) -> None:
        """Destroy only the currently owned synthetic device, if allocated."""
        if self.pad is not None:
            self.active_pad().close()
            self.pad = None

    def context_actions(
        self, mappings: Mapping[str, object]
    ) -> dict[str, str | int | list[int]]:
        """Resolve aliases through the same stock evdev codes as hotkeygen.

        Stock treats lists as ordered event codes and KEY_ scalar strings as
        single codes. Every other scalar string is an unchanged shell command.
        """
        actions: dict[str, str | int | list[int]] = {}
        for action, value in mappings.items():
            if isinstance(value, str):
                actions[action] = (
                    self.code(value) if value.startswith("KEY_") else value
                )
            elif isinstance(value, list):
                codes = []
                for name in value:
                    if not isinstance(name, str):
                        message = "stock context event name is not a string"
                        raise ProbeError(message)
                    codes.append(self.code(name))
                actions[action] = codes
            else:
                message = "stock context action is not a string or event list"
                raise ProbeError(message)
        return actions

    def remember_context(
        self, name: str, mappings: Mapping[str, str | list[str]]
    ) -> None:
        """Pin the requested stock semantics, retaining exact written bytes/inode."""
        identity = file_identity(CONTEXT)
        require(stat.S_ISREG(CONTEXT.lstat().st_mode), "unsafe hotkeygen context")
        content = CONTEXT.read_bytes()
        context = object_record(json.loads(content))
        require(
            context.get("name") == name
            and self.context_actions(object_record(context.get("keys")))
            == self.context_actions(mappings),
            "stock command did not leave the requested owned context",
        )
        require(file_identity(CONTEXT) == identity, "context changed while pinning")
        self.context_identity = identity
        self.context_bytes = content

    def require_context_ownership(self) -> None:
        """Refuse foreign replacement or in-place edits of the saved context."""
        try:
            current = file_identity(CONTEXT)
            content = CONTEXT.read_bytes()
        except FileNotFoundError:
            current = None
            content = None
        require(
            current == self.context_identity and content == self.context_bytes,
            "hotkeygen context changed outside the owned probe",
        )

    def restore_context(self) -> None:
        """Restore saved stock semantics only while the context is still owned."""
        if not self.context_saved or not self.context_changed:
            return
        self.require_context_ownership()
        if self.original_context is None:
            self.command(["/usr/bin/hotkeygen", "--default-context"])
        else:
            name = self.original_context.get("name")
            if not isinstance(name, str):
                message = "saved stock context name is not a string"
                raise ProbeError(message)
            self.command(
                [
                    "/usr/bin/hotkeygen",
                    "--disable-common",
                    "--new-context",
                    name,
                    json.dumps(self.original_context["keys"], sort_keys=True),
                ]
            )
        self.context_changed = False

    def publish(self) -> bool:
        """Publish one private report without replacing existing evidence."""
        if self.output is None:
            destination = os.environ.get("GOW_INPUT_TRIAL_RESULTS")
            if (
                destination
                and Path(destination).is_absolute()
                and Path(destination).is_dir()
            ):
                self.output = Path(destination) / "transport-probe.json"
        if self.output is None:
            sys.stderr.write(json.dumps(self.result, sort_keys=True) + "\n")
            return False
        try:
            if os.environ.get("GOW_NATIVE_RESULTS"):
                publish_selected_log(
                    self.output.parent,
                    [row["name"] + ": " + row["status"] for row in self.cases]
                    + self.errors,
                )
            publish_json(self.output, self.result)
        except OSError as error:
            sys.stderr.write(
                "cannot publish transport diagnostic: " + str(error) + "\n"
            )
            return False
        else:
            return True


def main() -> int:
    """Bound the native run, release input, and publish complete cleanup evidence."""
    probe = Probe()

    def interrupted(signum: int, _frame: FrameType | None) -> None:
        message = "probe interrupted by signal " + str(signum)
        raise InterruptedError(message)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    signal.alarm(240)
    try:
        probe.run()
    except (
        ProbeError,
        DiagnosticError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        probe.errors.append(str(error))
        probe.result["status"] = "failed"
    finally:
        signal.alarm(0)
        for release in (probe.close_pad, probe.stop_evmapy):
            try:
                release()
            except (ProbeError, OSError, subprocess.SubprocessError) as error:
                probe.errors.append("Input release: " + str(error))
                probe.result["status"] = "failed"
        if (
            probe.result["status"] != "passed"
            and os.environ.get("GOW_NATIVE_RESULTS")
            and probe.output is not None
        ):
            try:
                probe.result["failure_capture"] = capture_checkpoint(
                    probe.output.parent / "receiver-failure.png"
                )
            except (DiagnosticError, OSError, ValueError) as error:
                probe.result["failure_capture"] = {
                    "status": "unavailable",
                    "error": str(error),
                }
        # Cleanup remains bounded by each tracked child's wait timeout.
        probe.close()
        expected_cases = RECEIVER_CASES
        completed = {row["name"] for row in probe.cases}
        probe.result["not_run_cases"] = [
            name for name in expected_cases if name not in completed
        ]
    published = probe.publish()
    return 0 if published and probe.result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
