"""Exercise probe admission and owned cleanup without stock or native libraries."""

import errno
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from batocera_gow.runtime import emulator_probe as emulator
from batocera_gow.runtime.emulator_lifecycle import PrivateOutput, ProcessIdentity
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.native_diagnostics import Desktop
from batocera_gow.runtime.transport_probe import ProbeError, object_record


class DisplayHandle(Desktop):
    """Represent an owned external display handle, not X11 implementation behavior."""

    # This handle fixture must not open the base's real X11 connection.
    def __init__(self, *, fail_close: bool) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Track close attempts and optionally raise an external display error."""
        self.closed = False
        self.fail_close = fail_close

    def close(self) -> None:
        """Release the owned handle before exposing the configured I/O error."""
        self.closed = True
        if self.fail_close:
            message = "private display failure detail"
            raise OSError(message)


class PadHandle:
    """Record destruction of a device transferred to the probe."""

    def __init__(self, *, fail_close: bool) -> None:
        """Track only this handle's external write and close operations."""
        self.fd = -1
        self.closed = False
        self.fail_close = fail_close
        self.events: list[tuple[int, int, int]] = []

    def write(self, event_type: int, code: int, value: int) -> None:
        """Retain submitted kernel event fields without interpreting mappings."""
        self.events.append((event_type, code, value))

    def syn(self) -> None:
        """Retain the synchronization boundary as a device event."""
        self.events.append((0, 0, 0))

    def close(self) -> None:
        """Retire the owned handle or report a configured device-close error."""
        self.closed = True
        if self.fail_close:
            message = "private uinput failure detail"
            raise OSError(message)


@pytest.fixture
def local_children() -> Iterator[list[subprocess.Popen[bytes]]]:
    """Reap every disposable child even when a probe operation fails."""
    children: list[subprocess.Popen[bytes]] = []
    try:
        yield children
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
            if child.stdout is not None:
                child.stdout.close()


def start_child(children: list[subprocess.Popen[bytes]]) -> subprocess.Popen[bytes]:
    """Start a local private-output producer and transfer it to fixture ownership.

    Args:
        children: Fixture-owned processes guaranteed to be reaped after the test.

    Returns:
        A live process with an owned binary stdout pipe.
    """
    child = subprocess.Popen(  # Fixed local program and current interpreter.
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys,time; "
                "print('private game and environment bytes', flush=True); "
                "time.sleep(60)"
            ),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    children.append(child)
    return child


def test_forced_teardown_cannot_promote_an_apparently_passed_emulator(
    tmp_path: Path, local_children: list[subprocess.Popen[bytes]]
) -> None:
    """Stop only owned processes, clear private bytes and fail shortcut acceptance."""
    child = start_child(local_children)
    launcher = start_child(local_children)
    unrelated = start_child(local_children)
    probe = emulator.EmulatorProbe(tmp_path)
    probe.result["status"] = "passed"
    probe.emulator_identity = ProcessIdentity(child.pid, process_stat(child.pid)[1])
    probe.emulator_fd = os.pidfd_open(child.pid)
    descriptor = probe.emulator_fd
    probe.launcher = launcher
    assert launcher.stdout is not None
    probe.launcher_output = PrivateOutput(launcher.stdout)
    display = DisplayHandle(fail_close=False)
    probe.desktop = display
    try:
        failures = probe.close()
        assert failures == []
        assert child.wait(timeout=3) == -15
        assert launcher.poll() == -15
        assert unrelated.poll() is None
        assert display.closed
        assert probe.emulator_fd is None
        with pytest.raises(OSError, match=r"\[Errno 9\]") as closed:
            os.fstat(descriptor)
        assert closed.value.errno == errno.EBADF
        assert probe.launcher_output.observation()["retained_bytes"] == 0
        assert probe.result["status"] == "failed"
        assert probe.result["cleanup"] == {
            "status": "passed",
            "errors": [],
            "forced_emulator_teardown": True,
        }
        assert "private game" not in json.dumps(probe.result)
    finally:
        probe.close_process_observers([])


@pytest.mark.parametrize("profile_state", ["unchanged", "changed", "missing"])
def test_cleanup_closes_all_observers_and_checks_profile_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile_state: str,
) -> None:
    """A completed process needs no forced signal, but changed owned input fails."""
    profile = tmp_path / "suite-es-input.cfg"
    profile.write_bytes(b"owned fixture profile")
    monkeypatch.setattr(emulator, "PROFILE", profile)
    probe = emulator.EmulatorProbe(tmp_path)
    probe.result["status"] = "passed"
    probe.profile_seeded = True
    probe.profile_hash = hashlib.sha256(b"owned fixture profile").hexdigest()
    descriptors = [os.open(profile, os.O_RDONLY) for _ in range(3)]
    probe.emulator_fd, probe.final_fd, probe.duckstation_log_fd = descriptors
    # Use a terminated child's pidfd rather than pretending a file is a process.
    os.close(descriptors[0])
    with subprocess.Popen(  # Fixed no-op local child.
        [sys.executable, "-I", "-c", "pass"],
    ) as child:
        probe.emulator_fd = os.pidfd_open(child.pid)
        descriptors[0] = probe.emulator_fd
        child.wait(timeout=3)
        if profile_state == "changed":
            profile.write_bytes(b"changed fixture profile")
        elif profile_state == "missing":
            profile.unlink()
        failures = probe.close()
    assert probe.emulator_fd is None
    assert probe.final_fd is None
    assert probe.duckstation_log_fd is None
    for descriptor in descriptors:
        with pytest.raises(OSError, match=r"\[Errno 9\]") as closed:
            os.fstat(descriptor)
        assert closed.value.errno == errno.EBADF
    assert probe.forced is False
    if profile_state == "unchanged":
        assert failures == []
        assert probe.result["status"] == "passed"
    else:
        assert len(failures) == 1
        assert "Suite ES profile" in failures[0]
        assert probe.result["status"] == "failed"


def test_failed_capture_and_display_close_do_not_prevent_descriptor_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserve cleanup failures as fixed categories without private exception text."""
    probe = emulator.EmulatorProbe(tmp_path)
    path = tmp_path / "log"
    path.write_bytes(b"private log bytes")
    descriptor = os.open(path, os.O_RDONLY)
    probe.duckstation_log_fd = descriptor
    display = DisplayHandle(fail_close=True)
    probe.desktop = display

    def unavailable_capture(path: Path) -> dict[str, object]:
        del path
        message = "private screenshot failure detail"
        raise OSError(message)

    monkeypatch.setattr(emulator, "capture_checkpoint", unavailable_capture)
    failures = probe.close()
    assert failures == ["Owned authenticated display close failed"]
    assert display.closed
    assert probe.duckstation_log_fd is None
    with pytest.raises(OSError, match=r"\[Errno 9\]") as closed:
        os.fstat(descriptor)
    assert closed.value.errno == errno.EBADF
    assert probe.result["failure_capture"] == {
        "status": "unavailable",
        "checkpoint": "emulator-failure",
    }
    serialized = json.dumps(probe.result)
    assert "private screenshot" not in serialized
    assert "private display" not in serialized
    assert "private log" not in serialized
    assert object_record(probe.result["cleanup"])["status"] == "failed"


@pytest.mark.parametrize("fail_close", [False, True])
def test_device_close_failure_is_reported_without_disclosing_native_error(
    tmp_path: Path, *, fail_close: bool
) -> None:
    """Retire an allocated pad after partial startup without needing stock imports."""
    probe = emulator.EmulatorProbe(tmp_path)
    pad = PadHandle(fail_close=fail_close)
    probe.pad = pad
    failures: list[str] = []
    probe.close_native_input(failures)
    assert pad.closed
    assert failures == (["Owned native gamepad close failed"] if fail_close else [])
    assert "private uinput" not in str(failures)


@pytest.mark.parametrize(
    ("case", "arguments", "visual"),
    [
        (
            "nes-fceumm",
            ["retroarch", "-L", "/usr/lib/libretro/fceumm_libretro.so"],
            None,
        ),
        (
            "xbox-xemu",
            ["xemu", "-config_path", "/userdata/system/configs/xemu/xemu.toml"],
            None,
        ),
        (
            "psx-duckstation",
            [
                "duckstation-qt",
                "-visual",
                "0x21",
                "-batch",
                "-nogui",
                "--",
                "private-disc.chd",
            ],
            "0x21",
        ),
        (
            "psx-duckstation-vulkan",
            ["duckstation-qt", "-batch", "-nogui", "--", "private-disc.chd"],
            None,
        ),
    ],
)
def test_backend_command_admission_preserves_variant_and_hides_private_content(
    tmp_path: Path, case: str, arguments: list[str], visual: str | None
) -> None:
    """Inspect actual NUL-separated argv without claiming a native launch occurred."""
    process_view = tmp_path / "proc"
    process_view.mkdir()
    (process_view / "cmdline").write_bytes(
        b"\0".join(os.fsencode(arg) for arg in arguments) + b"\0"
    )
    probe = emulator.EmulatorProbe(tmp_path, case=case)
    probe.validate_emulator_command(process_view)
    if probe.case.backend == "duckstation":
        assert probe.result["qt_visual"] == visual
    assert probe.result["status"] == "failed"
    assert "private-disc" not in json.dumps(probe.result)


@pytest.mark.parametrize(
    ("case", "arguments"),
    [
        ("nes-fceumm", ["retroarch", "-L", "/foreign/core.so"]),
        (
            "nes-fceumm",
            [
                "retroarch",
                "-L",
                "/usr/lib/libretro/fceumm_libretro.so",
                "-L",
                "/foreign/core.so",
            ],
        ),
        ("xbox-xemu", ["xemu", "-config_path", "/foreign/state.toml"]),
        (
            "xbox-xemu",
            [
                "xemu",
                "-config_path",
                "/userdata/system/configs/xemu/xemu.toml",
                "-dvd_path",
                "private-disc.iso",
            ],
        ),
        (
            "psx-duckstation",
            ["duckstation-qt", "-batch", "-nogui", "--", "private-disc.chd"],
        ),
        (
            "psx-duckstation",
            [
                "duckstation-qt",
                "-visual",
                "0x0",
                "-batch",
                "-nogui",
                "--",
                "private-disc.chd",
            ],
        ),
        (
            "psx-duckstation",
            [
                "duckstation-qt",
                "-visual",
                "0x100000000",
                "-batch",
                "-nogui",
                "--",
                "private-disc.chd",
            ],
        ),
        (
            "psx-duckstation-vulkan",
            [
                "duckstation-qt",
                "-visual",
                "0x21",
                "-batch",
                "-nogui",
                "--",
                "private-disc.chd",
            ],
        ),
        (
            "psx-duckstation-vulkan",
            ["duckstation-qt", "-batch", "-nogui", "private-disc.chd"],
        ),
    ],
)
def test_backend_command_admission_refuses_changed_core_state_and_visual_routes(
    tmp_path: Path, case: str, arguments: list[str]
) -> None:
    """Do not pin a plausible backend with unapproved arguments or renderer route."""
    process_view = tmp_path / "proc"
    process_view.mkdir()
    (process_view / "cmdline").write_bytes(
        b"\0".join(os.fsencode(arg) for arg in arguments) + b"\0"
    )
    probe = emulator.EmulatorProbe(tmp_path, case=case)
    with pytest.raises(ProbeError, match="Actual") as refused:
        probe.validate_emulator_command(process_view)
    assert "private-disc" not in str(refused.value)
    assert probe.emulator_identity is None
    assert probe.emulator_fd is None


def test_settings_preserve_case_and_percent_values_but_refuse_symlinked_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read only disposable generated settings without interpolation or adoption."""
    settings = tmp_path / "settings.ini"
    original = b"[GPU]\nRenderer=Vulkan\n[Logging]\nLogFilter=50% private fixture\n"
    settings.write_bytes(original)
    monkeypatch.setattr(emulator, "DUCKSTATION_SETTINGS", settings)
    probe = emulator.EmulatorProbe(tmp_path, case="psx-duckstation-vulkan")
    parsed = probe.duckstation_settings()
    assert dict(parsed["GPU"]) == {"Renderer": "Vulkan"}
    assert parsed["Logging"]["LogFilter"] == "50% private fixture"
    assert settings.read_bytes() == original
    target = tmp_path / "foreign.ini"
    settings.rename(target)
    settings.symlink_to(target)
    with pytest.raises(ProbeError, match="symlink"):
        probe.duckstation_settings()
    assert target.read_bytes() == original
