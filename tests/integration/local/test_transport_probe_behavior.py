"""Exercise probe decisions with owned files, sockets and display transcripts.

Injected event transcripts do not qualify stock evmapy, X11 or native devices.
"""

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from queue import Queue
from threading import Thread
from types import ModuleType

import pytest

from batocera_gow.runtime import transport_probe as transport


class Clock:
    """Advance polling deadlines without waiting on a native display."""

    def __init__(self) -> None:
        """Start the fixture clock at zero seconds."""
        self.seconds = 0.0

    def now(self) -> float:
        """Return monotonic fixture seconds."""
        return self.seconds

    def sleep(self, seconds: float) -> None:
        """Advance the deadline by the requested interval."""
        self.seconds += seconds


class TranscriptReceiver(transport.Receiver):
    """Supply external display observations to the real polling and case rules."""

    # Base initialization opens libX11 and a real display; transcripts own neither.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Keep event batches separate from held-state observations."""
        self.pending: list[transport.Event] = []
        self.held_names: list[str] = []
        self.unknown = 0
        self.origin = 0.0
        self.has_focus = True
        self.closed = False
        self.query_failure = False

    def read(self) -> list[transport.Event]:
        """Drain the current external display batch exactly once."""
        result, self.pending = self.pending, []
        return result

    def held(self) -> list[str]:
        """Return an independent display keymap sample or its I/O failure."""
        if self.query_failure:
            message = "display keymap unavailable"
            raise OSError(message)
        return self.held_names

    def focused(self) -> bool:
        """Report the external display's current focus decision."""
        return self.has_focus

    def reset_pointer(self) -> None:
        """Discard pending observations as an owned pointer reset would."""
        self.pending.clear()

    def close(self) -> None:
        """Record release of this external display handle."""
        self.closed = True


class TranscriptPad:
    """Record uinput frames and deliver independently specified display batches."""

    def __init__(self, receiver: TranscriptReceiver) -> None:
        """Borrow the transcript receiver without taking ownership."""
        self.fd = -1
        self.receiver = receiver
        self.frames: list[list[tuple[int, int, int]]] = []
        self.frame: list[tuple[int, int, int]] = []
        self.presses: list[transport.Event] = []
        self.releases: list[transport.Event] = []
        self.held: list[str] = []
        self.after_release: list[str] = []
        self.closed = False
        self.fail_close = False

    def write(self, event_type: int, code: int, value: int) -> None:
        """Retain the exact ordered events submitted to the device boundary."""
        self.frame.append((event_type, code, value))

    def syn(self) -> None:
        """Commit one frame and expose its configured external observations."""
        self.frames.append(self.frame)
        pressed = self.frame[-1][2] == 1
        self.frame = []
        self.receiver.pending.extend(self.presses if pressed else self.releases)
        self.receiver.held_names = self.held if pressed else self.after_release

    def close(self) -> None:
        """Record device destruction, optionally reporting a boundary failure."""
        self.closed = True
        if self.fail_close:
            message = "owned pad close failed"
            raise OSError(message)


class FixtureCodes:
    """Independent Linux event values exposed by the synthetic evdev boundary."""

    EV_KEY = 1
    BTN_MODE = 316
    BTN_START = 315
    BTN_SOUTH = 304
    BTN_EAST = 305
    BTN_NORTH = 307
    BTN_LEFT = 272
    BTN_MOUSE = 272
    KEY_LEFTCTRL = 29
    KEY_F9 = 67
    KEY_F12 = 88


class FixtureEvdev(ModuleType):
    """Expose only the event codes these nonnative probe cases consume."""

    def __init__(self) -> None:
        """Provide the stock-style module attribute without an untyped import."""
        super().__init__("fixture_evdev")
        self.ecodes = FixtureCodes()


@pytest.fixture
def receiver_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[transport.Probe, TranscriptReceiver, TranscriptPad]:
    """Assemble real probe rules with controlled display, input and clock I/O.

    Returns:
        The probe and independently configured device/display transcript handles.
    """
    clock = Clock()
    monkeypatch.setattr(time, "monotonic", clock.now)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr(transport, "input_permitted", lambda: None)
    monkeypatch.delenv("GOW_NATIVE_RESULTS", raising=False)
    module = FixtureEvdev()
    probe = transport.Probe()
    receiver = TranscriptReceiver()
    pad = TranscriptPad(receiver)
    probe.receiver, probe.pad, probe.evdev = receiver, pad, module
    return probe, receiver, pad


def configure_chord(pad: TranscriptPad) -> None:
    """Supply one known Ctrl/F12 display trace across the X11 timestamp wrap."""
    pad.presses = [
        {"at_us": 0, "server_time_ms": 4294967199, "kind": "motion", "x": 0, "y": 0},
        {
            "at_us": 0,
            "kind": "key",
            "key": "Control_L",
            "action": "press",
            "server_time_ms": 4294967200,
        },
        {
            "at_us": 0,
            "kind": "key",
            "key": "F12",
            "action": "press",
            "server_time_ms": 4294967201,
        },
    ]
    pad.releases = [
        {
            "at_us": 250000,
            "kind": "key",
            "key": "Control_L",
            "action": "release",
            "server_time_ms": 154,
        },
        {
            "at_us": 250000,
            "kind": "key",
            "key": "F12",
            "action": "release",
            "server_time_ms": 155,
        },
    ]
    pad.held = ["Control_L", "F12"]


def test_chord_requires_order_duration_pointer_reset_and_complete_release(
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
) -> None:
    """Accept a complete transcript and retain independent ordered input frames."""
    probe, _, pad = receiver_probe
    configure_chord(pad)
    row = probe.case(
        "fixture-chord",
        {"held_ms_minimum": 230},
        lambda value: probe.held_chord(value, ["Control_L", "F12"], pointer=True),
    )
    assert row is not None
    assert row["status"] == "passed"
    assert "held_duration_ms" in row
    assert "held_keys_during_hold" in row
    assert row["held_duration_ms"] == 250
    assert row["held_keys_during_hold"] == ["Control_L", "F12"]
    assert pad.frames == [
        [(1, 316, 1), (1, 315, 1)],
        [(1, 315, 0), (1, 316, 0)],
    ]


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("wrong-order", "unexpected chord press sequence"),
        ("missing-held", "X11 held key state differs"),
        ("leaked-button", "semantic key leaked"),
        ("stuck-key", "X11 key remained held"),
        ("short-hold", "held action duration was shortened"),
        ("missing-reset", "pointer reset did not precede chord"),
        ("missing-release", "timeout waiting for receiver chord release"),
    ],
)
def test_incomplete_chord_fails_and_still_releases_owned_controls(
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
    fault: str,
    message: str,
) -> None:
    """Reject plausible incomplete display evidence without leaving input held."""
    probe, _, pad = receiver_probe
    configure_chord(pad)
    if fault == "wrong-order":
        pad.presses[1], pad.presses[2] = pad.presses[2], pad.presses[1]
    elif fault == "missing-held":
        pad.held = ["Control_L"]
    elif fault == "leaked-button":
        pad.releases.append(
            {
                "at_us": 250000,
                "server_time_ms": 155,
                "kind": "button",
                "button": 1,
                "action": "press",
            }
        )
    elif fault == "stuck-key":
        pad.after_release = ["F12"]
    elif fault == "short-hold":
        pad.releases[0]["server_time_ms"] = 0
    elif fault == "missing-reset":
        pad.presses.pop(0)
    else:
        pad.releases.clear()
    row = probe.case(
        "fixture-chord",
        {},
        lambda value: probe.held_chord(value, ["Control_L", "F12"], pointer=True),
    )
    assert row is not None
    assert row["status"] == "failed"
    assert "error" in row
    assert message in row["error"]
    assert pad.frames[-1] == [(1, 315, 0), (1, 316, 0)]


@pytest.mark.parametrize("fault", ["none", "key-leak", "short-hold"])
def test_pointer_scenario_requires_one_click_without_key_leakage(
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
    fault: str,
) -> None:
    """Keep pointer consumer evidence distinct from the semantic controller key."""
    probe, _, pad = receiver_probe
    pad.presses = [
        {
            "at_us": 0,
            "kind": "button",
            "button": 1,
            "action": "press",
            "server_time_ms": 1000,
        },
    ]
    pad.releases = [
        {
            "at_us": 250000,
            "kind": "button",
            "button": 1,
            "action": "release",
            "server_time_ms": 1250,
        },
    ]
    if fault == "key-leak":
        pad.releases.append(
            {
                "at_us": 250000,
                "server_time_ms": 1250,
                "kind": "key",
                "key": "F12",
                "action": "press",
            }
        )
    elif fault == "short-hold":
        pad.releases[0]["server_time_ms"] = 1100
    row = probe.case("fixture-pointer", {}, probe.pointer_button)
    assert row is not None
    assert row["status"] == ("passed" if fault == "none" else "failed")
    assert pad.frames == [
        [(1, 316, 1), (1, 304, 1)],
        [(1, 304, 0), (1, 316, 0)],
    ]


def test_lost_focus_and_unselected_case_do_not_inject(
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
) -> None:
    """Refuse input before a scenario when its consumer no longer owns focus."""
    probe, receiver, pad = receiver_probe
    probe.selected_case = "chosen"
    assert probe.case("other", {}, probe.pointer_button) is None
    assert probe.cases == []
    receiver.has_focus = False
    row = probe.case("chosen", {}, probe.pointer_button)
    assert row is not None
    assert row["status"] == "failed"
    assert "error" in row
    assert row["error"] == "receiver lost focus"
    assert pad.frames == []


def test_lease_revocation_during_hold_releases_input_and_propagates(
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation cannot become a passing row or block the release frame."""
    probe, _, pad = receiver_probe
    configure_chord(pad)

    def permission() -> None:
        if pad.frames and len(pad.frames) == 1:
            message = "fixture lease revoked"
            raise InterruptedError(message)

    monkeypatch.setattr(transport, "input_permitted", permission)
    with pytest.raises(InterruptedError, match="lease revoked"):
        probe.case(
            "cancelled", {}, lambda row: probe.held_chord(row, ["Control_L", "F12"])
        )
    assert probe.cases[0]["status"] == "failed"
    assert pad.frames[-1] == [(1, 315, 0), (1, 316, 0)]


@pytest.mark.parametrize("payload", ["[]", '{"sources":{}}', '{"sources":[1]}'])
def test_status_rejects_malformed_record_arrays_without_allocating_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    """Malformed supervisor JSON must fail before any device or child allocation."""
    status = tmp_path / "status.json"
    status.write_text(payload, encoding="utf-8")
    status.chmod(0o600)
    monkeypatch.setattr(transport, "STATUS", status)
    # The file owner is the only simulated credential; JSON and mode checks are real.
    original_lstat = Path.lstat

    def owned_stat(path: Path) -> os.stat_result:
        info = original_lstat(path)
        if path == status:
            values = list(info)
            values[4] = 0
            return type(info)(values)
        return info

    monkeypatch.setattr(Path, "lstat", owned_stat)
    probe = transport.Probe()
    with pytest.raises(transport.ProbeError, match="diagnostic JSON"):
        probe.status()
    assert probe.pad is None
    assert probe.evmapy is None


@pytest.fixture
def scratch_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> transport.Probe:
    """Prepare only owned filesystem locations, without stock setup or imports."""
    runtime = tmp_path / "evmapy"
    runtime.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(transport, "EVMAPY", runtime)
    monkeypatch.setattr(transport, "CONTEXT", tmp_path / "context.json")
    probe = transport.Probe()
    probe.work = work
    probe.evdev = FixtureEvdev()
    probe.work_identity = transport.file_identity(work)
    return probe


@pytest.mark.parametrize(
    "payload", [b'[{"path":"/fixture/event7"}]', b"{}", b"[false]"]
)
def test_control_socket_validates_reply_and_removes_private_client(
    scratch_probe: transport.Probe, payload: bytes
) -> None:
    """Use a real local datagram exchange and retire the reply socket on failure."""
    requests: Queue[bytes] = Queue()
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(transport.EVMAPY / "evmapy.socket"))
        server.settimeout(2)

        def respond() -> None:
            request, address = server.recvfrom(65536)
            requests.put(request)
            server.sendto(payload, address)

        thread = Thread(target=respond)
        thread.start()
        try:
            if payload.startswith(b'[{"'):
                assert scratch_probe.control_list() == [{"path": "/fixture/event7"}]
            else:
                with pytest.raises(transport.ProbeError, match="diagnostic JSON"):
                    scratch_probe.control_list()
        finally:
            thread.join(timeout=3)
        assert not thread.is_alive()
        assert requests.get(timeout=1) == b'{"command":"list","wait":true}'
    assert not (scratch_probe.work_directory() / "control.socket").exists()
    assert scratch_probe.owned_files == {}


def test_missing_control_server_leaves_no_private_socket(
    scratch_probe: transport.Probe,
) -> None:
    """Unavailable stock control remains pending, not fabricated readiness."""
    assert scratch_probe.control_list() is None
    assert scratch_probe.owned_files == {}
    assert not (scratch_probe.work_directory() / "control.socket").exists()


def test_cleanup_preserves_replaced_entries_and_attempts_other_resources(
    scratch_probe: transport.Probe,
) -> None:
    """A foreign inode cannot be deleted even when another owned cleanup succeeds."""
    work = scratch_probe.work_directory()
    replaced = work / "replaced"
    replaced.write_bytes(b"owned")
    scratch_probe.remember(replaced)
    displaced = work.parent / "original"
    replaced.rename(displaced)
    replaced.write_bytes(b"foreign replacement")
    other = work / "other"
    other.write_bytes(b"owned")
    scratch_probe.remember(other)
    scratch_probe.result["status"] = "passed"
    scratch_probe.close()
    assert replaced.read_bytes() == b"foreign replacement"
    assert displaced.read_bytes() == b"owned"
    assert not other.exists()
    assert work.is_dir()
    assert scratch_probe.result["status"] == "failed"
    cleanup = transport.object_record(scratch_probe.result["cleanup"])
    assert cleanup["status"] == "failed"
    assert "cleanup identity changed" in str(cleanup["errors"])


@pytest.mark.parametrize("state", ["same", "edited", "replaced"])
def test_context_ownership_checks_bytes_and_inode_before_restoration(
    scratch_probe: transport.Probe, state: str
) -> None:
    """Reject foreign context changes without invoking stock commands."""
    context = transport.CONTEXT
    original = b'{"name":"trial","keys":{"exit":"KEY_F12"}}'
    context.write_bytes(original)
    scratch_probe.remember_context("trial", {"exit": "KEY_F12"})
    if state == "edited":
        context.write_bytes(b'{"name":"foreign","keys":{}}')
    elif state == "replaced":
        context.rename(context.with_suffix(".old"))
        context.write_bytes(original)
    if state == "same":
        scratch_probe.require_context_ownership()
        assert context.read_bytes() == original
    else:
        with pytest.raises(transport.ProbeError, match="changed outside"):
            scratch_probe.require_context_ownership()


@pytest.mark.parametrize(
    "keys",
    [
        {"menu": ["BTN_MOUSE"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]},
        {"menu": ["BTN_LEFT"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]},
    ],
)
def test_stock_key_aliases_preserve_order_and_pin_exact_file_bytes(
    scratch_probe: transport.Probe, keys: dict[str, str | list[str]]
) -> None:
    """Accept equivalent event codes without rewriting the stock-owned spelling."""
    context = transport.CONTEXT
    saved = json.dumps({"name": "trial", "keys": keys}).encode()
    context.write_bytes(saved)
    identity = transport.file_identity(context)
    scratch_probe.remember_context(
        "trial", {"menu": ["BTN_LEFT"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]}
    )
    scratch_probe.require_context_ownership()
    assert context.read_bytes() == saved
    assert transport.file_identity(context) == identity
    context.write_bytes(saved + b"\n")
    with pytest.raises(transport.ProbeError, match="changed outside"):
        scratch_probe.require_context_ownership()


@pytest.mark.parametrize(
    ("name", "keys"),
    [
        ("foreign", {"menu": ["BTN_MOUSE"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]}),
        ("trial", {"menu": ["BTN_MOUSE"], "exit": ["KEY_F12", "KEY_LEFTCTRL"]}),
        ("trial", {"menu": ["BTN_MOUSE"], "exit": ["KEY_LEFTCTRL", "KEY_F9"]}),
        ("trial", {"menu": "BTN_MOUSE", "exit": ["KEY_LEFTCTRL", "KEY_F12"]}),
        ("trial", {"menu": ["BTN_MOUSE"]}),
        (
            "trial",
            {
                "menu": ["BTN_MOUSE"],
                "exit": ["KEY_LEFTCTRL", "KEY_F12"],
                "command": "printf foreign",
            },
        ),
        ("trial", {"menu": ["UNKNOWN_EVENT"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]}),
        ("trial", {"menu": [272], "exit": ["KEY_LEFTCTRL", "KEY_F12"]}),
    ],
)
def test_different_stock_context_semantics_are_never_claimed(
    scratch_probe: transport.Probe, name: str, keys: dict[str, object]
) -> None:
    """Alias handling must not admit changed actions, order, types or commands."""
    context = transport.CONTEXT
    saved = json.dumps({"name": name, "keys": keys}).encode()
    context.write_bytes(saved)
    with pytest.raises(transport.ProbeError):
        scratch_probe.remember_context(
            "trial", {"menu": ["BTN_LEFT"], "exit": ["KEY_LEFTCTRL", "KEY_F12"]}
        )
    assert scratch_probe.context_identity is None
    assert scratch_probe.context_bytes is None
    assert context.read_bytes() == saved


@pytest.mark.parametrize(
    ("requested", "saved", "accepted"),
    [
        ("BTN_LEFT", "BTN_LEFT", True),
        ("BTN_LEFT", "BTN_MOUSE", False),
        ("KEY_F12", "KEY_F12", True),
        ("KEY_F12", ["KEY_F12"], False),
        (["KEY_F12"], "KEY_F12", False),
    ],
)
def test_scalar_commands_and_event_sequences_keep_stock_distinctions(
    scratch_probe: transport.Probe,
    requested: str | list[str],
    saved: str | list[str],
    *,
    accepted: bool,
) -> None:
    """Only KEY_ scalar names are events; other strings are exact commands."""
    transport.CONTEXT.write_text(
        json.dumps({"name": "trial", "keys": {"exit": saved}}), encoding="utf-8"
    )
    if accepted:
        scratch_probe.remember_context("trial", {"exit": requested})
        scratch_probe.require_context_ownership()
    else:
        with pytest.raises(transport.ProbeError):
            scratch_probe.remember_context("trial", {"exit": requested})


def test_integrity_failure_still_closes_pad_receiver_and_private_directory(
    scratch_probe: transport.Probe,
) -> None:
    """Changed stock-input bytes veto success without preventing later cleanup."""
    fixture = scratch_probe.work_directory().parent / "stock-input"
    fixture.write_bytes(b"before")
    scratch_probe.hash_paths = [fixture]
    scratch_probe.hash_evidence = {"before": scratch_probe.stock_hashes()}
    fixture.write_bytes(b"after")
    receiver = TranscriptReceiver()
    receiver.query_failure = True
    pad = TranscriptPad(receiver)
    pad.fail_close = True
    scratch_probe.receiver, scratch_probe.pad = receiver, pad
    scratch_probe.result["status"] = "passed"
    work = scratch_probe.work_directory()
    scratch_probe.close()
    assert receiver.closed
    assert pad.closed
    assert not work.exists()
    assert scratch_probe.result["status"] == "failed"
    cleanup = transport.object_record(scratch_probe.result["cleanup"])
    assert cleanup["status"] == "failed"
    assert "packaged stock input files changed" in str(cleanup["errors"])
    assert "display keymap unavailable" in str(cleanup["errors"])
    assert "owned pad close failed" in str(cleanup["errors"])


@pytest.fixture
def owned_child() -> Iterator[subprocess.Popen[bytes]]:
    """Own a local sleeping child and reap it even if the test fails."""
    child = subprocess.Popen(  # Current interpreter and fixed local program.
        [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield child
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)


def test_owned_daemon_stop_reaps_child_and_only_its_matching_runtime_entries(
    scratch_probe: transport.Probe, owned_child: subprocess.Popen[bytes]
) -> None:
    """Real process shutdown records identity and removes pinned socket/readiness."""
    ready = transport.EVMAPY / "ready"
    ready.write_bytes(b"ready")
    unrelated = transport.EVMAPY / "operator.json"
    unrelated.write_bytes(b"foreign")
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(transport.EVMAPY / "evmapy.socket"))
        scratch_probe.evmapy = owned_child
        scratch_probe.stop_evmapy()
    assert owned_child.poll() is not None
    assert scratch_probe.evmapy is None
    assert scratch_probe.process_records == [
        {"pid": owned_child.pid, "returncode": -15, "forced_kill": False},
    ]
    assert not ready.exists()
    assert not (transport.EVMAPY / "evmapy.socket").exists()
    assert unrelated.read_bytes() == b"foreign"


def test_report_publication_is_private_exclusive_and_contains_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Never replace an earlier report or symlink target during publication."""
    monkeypatch.delenv("GOW_NATIVE_RESULTS", raising=False)
    probe = transport.Probe()
    probe.output = tmp_path / "report.json"
    probe.close()
    assert probe.publish()
    original = probe.output.read_bytes()
    assert transport.object_record(json.loads(original))["cleanup"] == {
        "status": "passed",
        "errors": [],
    }
    assert probe.output.stat().st_mode & 0o777 == 0o600
    assert not probe.publish()
    assert probe.output.read_bytes() == original
    probe.output.unlink()
    target = tmp_path / "foreign"
    target.write_bytes(b"do not replace")
    probe.output.symlink_to(target)
    assert not probe.publish()
    assert target.read_bytes() == b"do not replace"
    assert "cannot publish transport diagnostic" in capsys.readouterr().err


@pytest.fixture
def stock_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Redirect only stock configuration reads to independent disposable files.

    Returns:
        Action and semantic-mapping files consumed by real configuration rules.
    """
    actions = tmp_path / "hotkeys.keys"
    actions.write_text(
        json.dumps(
            {
                "actions_player1": [
                    {
                        "trigger": ["hotkey", "start"],
                        "type": "key",
                        "target": "KEY_EXIT",
                        "description": "private fixture description",
                    },
                    {"trigger": ["hotkey", "b"], "type": "key", "target": "KEY_MENU"},
                    {"trigger": ["hotkey", "y"], "type": "key", "target": "KEY_SAVE"},
                    {"trigger": ["hotkey", "a"], "type": "key", "target": "KEY_OTHER"},
                ],
            },
        ),
        encoding="utf-8",
    )
    mappings = tmp_path / "default_mapping.conf"
    mappings.write_text(
        '{"KEY_EXIT":"exit","KEY_MENU":"menu","KEY_SAVE":"save_state"}',
        encoding="utf-8",
    )
    redirects = {
        Path("/usr/share/evmapy/hotkeys.keys"): actions,
        Path("/etc/hotkeygen/default_mapping.conf"): mappings,
    }
    original_read = Path.read_text

    def read_stock(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        return original_read(
            redirects.get(path, path), encoding=encoding, errors=errors
        )

    monkeypatch.setattr(Path, "read_text", read_stock)
    return actions, mappings


def test_controller_configuration_selects_only_stock_actions_and_refuses_overwrite(
    scratch_probe: transport.Probe,
    receiver_probe: tuple[transport.Probe, TranscriptReceiver, TranscriptPad],
    stock_inputs: tuple[Path, Path],
) -> None:
    """Publish a pinned mapping without descriptions or unrelated stock actions."""
    del stock_inputs
    evdev = receiver_probe[0].evdev
    assert evdev is not None
    scratch_probe.evdev = evdev
    scratch_probe.write_pad_configuration("event7")
    config = transport.EVMAPY / "event7.json"
    value = transport.object_record(json.loads(config.read_text(encoding="utf-8")))
    assert value == {
        "grab": False,
        "axes": [],
        "buttons": [
            {"name": "hotkey", "code": 316},
            {"name": "start", "code": 315},
            {"name": "b", "code": 304},
            {"name": "a", "code": 305},
            {"name": "y", "code": 307},
        ],
        "actions": [
            {"trigger": ["hotkey", "start"], "type": "key", "target": "KEY_EXIT"},
            {"trigger": ["hotkey", "b"], "type": "key", "target": "KEY_MENU"},
            {"trigger": ["hotkey", "y"], "type": "key", "target": "KEY_SAVE"},
        ],
    }
    original = config.read_bytes()
    with pytest.raises(FileExistsError):
        scratch_probe.write_pad_configuration("event7")
    assert config.read_bytes() == original
    scratch_probe.close()
    assert not config.exists()


@pytest.mark.parametrize(
    "fault", ["duplicate-action", "wrong-action-type", "wrong-semantics"]
)
def test_configuration_refuses_ambiguous_or_changed_stock_rules_before_write(
    scratch_probe: transport.Probe,
    stock_inputs: tuple[Path, Path],
    fault: str,
) -> None:
    """Reject changed upstream prerequisites rather than invent replacement policy."""
    actions, mappings = stock_inputs
    if fault == "wrong-semantics":
        mappings.write_text('{"KEY_EXIT":"menu"}', encoding="utf-8")
    else:
        action: dict[str, object] = {
            "trigger": ["hotkey", "start"],
            "type": "key",
            "target": "KEY_EXIT",
        }
        rows = [
            action,
            {"trigger": ["hotkey", "b"], "type": "key"},
            {"trigger": ["hotkey", "y"], "type": "key"},
        ]
        if fault == "duplicate-action":
            rows.append(dict(action))
        else:
            action["type"] = "command"
        actions.write_text(json.dumps({"actions_player1": rows}), encoding="utf-8")
    with pytest.raises(transport.ProbeError, match="stock"):
        scratch_probe.write_pad_configuration("event7")
    assert not (transport.EVMAPY / "event7.json").exists()
    assert scratch_probe.owned_files == {}


@pytest.mark.parametrize("gate_kind", ["regular", "symlink", "directory", "outside"])
def test_operator_gate_requires_owned_non_symlink_location_before_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate_kind: str,
) -> None:
    """Filesystem presence cannot authorize an escaped or symlinked native gate."""
    directory = tmp_path / "results"
    directory.mkdir()
    gate = directory / "allow-input"
    if gate_kind == "directory":
        gate.mkdir()
    elif gate_kind == "symlink":
        target = tmp_path / "target"
        target.write_bytes(b"operator")
        gate.symlink_to(target)
    elif gate_kind == "outside":
        gate = tmp_path / "outside"
        gate.write_bytes(b"operator")
    else:
        gate.write_bytes(b"operator")
    calls: list[str] = []
    monkeypatch.setenv("GOW_INPUT_TRIAL_GATE", str(gate))
    monkeypatch.delenv("GOW_NATIVE_LEASE", raising=False)
    monkeypatch.setattr(transport, "input_permitted", lambda: calls.append("lease"))
    probe = transport.Probe()
    if gate_kind == "regular":
        probe.wait_operator_gate(directory)
        assert calls == ["lease"]
        assert probe.result["operator_gate_observed"] is True
    else:
        with pytest.raises(transport.ProbeError, match="operator gate"):
            probe.wait_operator_gate(directory)
        assert calls == []
        assert "operator_gate_observed" not in probe.result


@pytest.mark.parametrize("kind", ["missing", "symlink", "writable"])
def test_supervisor_status_refuses_unsafe_file_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Do not adopt status from a symlink or a group-writable directory entry."""
    status = tmp_path / "status.json"
    monkeypatch.setattr(transport, "STATUS", status)
    if kind == "symlink":
        target = tmp_path / "foreign-status"
        target.write_text('{"sources":[]}', encoding="utf-8")
        status.symlink_to(target)
    elif kind == "writable":
        status.write_text('{"sources":[]}', encoding="utf-8")
        status.chmod(0o666)
    probe = transport.Probe()
    if kind == "missing":
        assert probe.status() == {}
    else:
        with pytest.raises(transport.ProbeError, match="unsafe supervisor status"):
            probe.status()
    assert probe.pad is None
    assert probe.work is None


@pytest.mark.parametrize("timeout", [-1, float("inf"), float("nan")])
def test_unbounded_polling_is_refused_before_observation_or_lease(
    monkeypatch: pytest.MonkeyPatch, timeout: float
) -> None:
    """Bad timing configuration cannot create an unbounded native observation."""
    calls: list[str] = []
    monkeypatch.setattr(transport, "input_permitted", lambda: calls.append("lease"))

    def observe() -> bool:
        calls.append("observe")
        return True

    with pytest.raises(transport.ProbeError, match="finite and nonnegative"):
        transport.wait_for("fixture", observe, timeout)
    assert calls == []
