"""Exercise probe decisions with owned files/processes, not native acceptance."""

import ctypes
import errno
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import select
import signal
import stat
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PosixPath
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from batocera_gow.runtime import emulator_probe as emulator
from batocera_gow.runtime import transport_probe
from batocera_gow.runtime.emulator_lifecycle import ProcessIdentity
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.media_catalog import emulator_case
from batocera_gow.runtime.mounted_media import MediaSelection
from batocera_gow.runtime.transport_probe import ProbeError, object_record

if TYPE_CHECKING:
    from ctypes import _Pointer


HELPERS = Path(__file__).with_name("emulator_probe_helpers")


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("small-width", False),
        ("small-height", False),
        ("blank", False),
        ("border-only", False),
        ("static-center", True),
        ("many-colors", True),
    ],
)
def test_render_evidence_requires_sufficient_nonblank_center_pixels(
    tmp_path: Path, scenario: str, *, expected: bool
) -> None:
    """A static image can qualify, but a border or undersized preview cannot."""
    size = {
        "small-width": (255, 224),
        "small-height": (256, 223),
    }.get(scenario, (256, 224))
    image = Image.new("RGB", size, "black")
    try:
        if scenario == "border-only":
            image.paste("white", (0, 0, size[0], 1))
            image.paste("white", (0, 0, 1, size[1]))
        elif scenario != "blank":
            image.paste("white", (100, 90, 120, 110))
        if scenario == "many-colors":
            for offset in range(24):
                image.putpixel((110 + offset, 100), (offset, 30, 60))
        path = tmp_path / "capture.png"
        image.save(path)
    finally:
        image.close()
    before = path.read_bytes()
    assert emulator.rendered_content(path) is expected
    assert emulator.rendered_content(path) is expected
    assert path.read_bytes() == before


@pytest.mark.parametrize("blank", [False, True])
def test_exit_checkpoint_publishes_only_nonblank_capture_and_caches_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, blank: bool
) -> None:
    """A failed pixel barrier is not cached or counted as successful evidence."""
    captures: list[Path] = []

    def capture(path: Path) -> dict[str, object]:
        captures.append(path)
        with Image.new("RGB", (256, 224), "black") as image:
            if not blank:
                image.paste("white", (100, 90, 120, 110))
            image.save(path)
        return {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    monkeypatch.setattr(emulator, "capture_checkpoint", capture)
    probe = emulator.EmulatorProbe(tmp_path)
    if blank:
        with pytest.raises(ProbeError, match="output became blank"):
            probe.checkpoint("emulator-before-exit")
        assert probe.captures == {}
        assert probe.result["status"] == "failed"
    else:
        observed = probe.checkpoint("emulator-before-exit")
        assert probe.checkpoint("emulator-before-exit") == observed
        assert len(captures) == 1
        assert observed["path"] == "emulator-before-exit.png"
        assert probe.captures == {"emulator-before-exit": observed}
        assert probe.result["status"] == "failed"


class MetadataChild(subprocess.Popen[bytes]):
    """Use a real local child while shortening only its external wait deadline."""

    def wait(self, timeout: float | None = None) -> int:
        """Exercise metadata timeout and escalation without a five-second sleep."""
        return super().wait(timeout=0.1 if timeout in (1, 5) else timeout)


@pytest.fixture
def metadata_children() -> Iterator[list[subprocess.Popen[bytes]]]:
    """Reap children even if metadata parsing or an ownership assertion fails."""
    children: list[subprocess.Popen[bytes]] = []
    try:
        yield children
    finally:
        for child in children:
            if child.stdin is not None:
                child.stdin.close()
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
            if child.stdout is not None:
                child.stdout.close()


@pytest.mark.parametrize("mode", ["success", "failed", "timeout", "ignore-term"])
def test_xemu_metadata_uses_disposable_config_and_always_reaps_its_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_children: list[subprocess.Popen[bytes]],
    mode: str,
) -> None:
    """Owned metadata failure cannot overwrite game state or retain private output."""
    game_config = tmp_path / "xemu.toml"
    game_config.write_text("operator game configuration", encoding="utf-8")
    executable = tmp_path / "inventoried-xemu"
    executable.write_bytes(b"local synthetic executable identity")
    configurations: list[Path] = []
    monkeypatch.setenv("DISPLAY", ":fixture")
    monkeypatch.setenv("XAUTHORITY", str(tmp_path / "private-cookie"))

    def local_path(value: str | os.PathLike[str]) -> Path:
        path = Path(value)
        return executable if path == Path("/usr/bin/xemu") else path

    def spawn(
        arguments: Sequence[str], *, stdout: int, stderr: int
    ) -> subprocess.Popen[bytes]:
        assert list(arguments[:2]) == ["/usr/bin/xemu", "-config_path"]
        assert list(arguments[3:]) == ["-version"]
        configuration = Path(arguments[2])
        configurations.append(configuration)
        assert configuration != game_config
        assert configuration.parent.parent == tmp_path
        assert configuration.parent.stat().st_mode & 0o777 == 0o700
        # This stdlib-only external producer can be forcibly killed. Do not let
        # interpreter site hooks create an unrelated, half-written coverage DB.
        child = MetadataChild(  # Fixed local metadata producer, no stock binary.
            [
                sys.executable,
                "-I",
                "-S",
                str(HELPERS / "xemu_metadata.py"),
                str(configuration),
                mode,
            ],
            stdout=stdout,
            stderr=stderr,
            bufsize=0,
        )
        metadata_children.append(child)
        assert child.stdout is not None
        assert select.select([child.stdout], [], [], 3)[0]
        assert child.stdout.readline() == b"ready\n"
        assert (
            configuration.read_text(encoding="utf-8") == "private helper configuration"
        )
        return child

    monkeypatch.setattr(emulator, "Path", local_path)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    if mode == "success":
        observed = emulator.xemu_identity(tmp_path)
        assert object_record(observed["reported_version"]) == {
            "argument": "-version",
            "exit_code": 0,
            "disposable_config": True,
            "version": "0.8.123",
            "revision": "a" * 40,
            "date": "Mon Jan 1 01:02:03 AM UTC 2024",
        }
        assert (
            observed["executable_sha256"]
            == hashlib.sha256(executable.read_bytes()).hexdigest()
        )
        assert "private" not in json.dumps(observed)
        assert str(tmp_path) not in json.dumps(observed)
    elif mode == "failed":
        with pytest.raises(ProbeError, match="metadata helper failed"):
            emulator.xemu_identity(tmp_path)
    else:
        with pytest.raises(subprocess.TimeoutExpired):
            emulator.xemu_identity(tmp_path)
    assert len(metadata_children) == 1
    assert (
        metadata_children[0].poll()
        == {
            "success": 0,
            "failed": 4,
            "timeout": -signal.SIGTERM,
            "ignore-term": -signal.SIGKILL,
        }[mode]
    )
    assert len(configurations) == 1
    assert not configurations[0].parent.exists()
    assert game_config.read_text(encoding="utf-8") == "operator game configuration"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "inventoried-xemu",
        "xemu.toml",
    ]


@pytest.mark.parametrize("missing", ["DISPLAY", "XAUTHORITY"])
def test_xemu_metadata_refuses_unauthenticated_session_before_allocating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """Require authenticated display context before allocating metadata files."""
    monkeypatch.setenv("DISPLAY", ":fixture")
    monkeypatch.setenv("XAUTHORITY", "private-cookie")
    monkeypatch.delenv(missing)
    with pytest.raises(ProbeError, match="Authenticated native X11 required"):
        emulator.xemu_identity(tmp_path)
    assert list(tmp_path.iterdir()) == []


class CoreLibrary:
    """Expose a local libretro information ABI without loading a stock core."""

    def __init__(self, name: bytes | None, version: bytes | None) -> None:
        """Keep the C callback and its backing byte strings alive during the query."""
        self.name, self.version = name, version

        def information(pointer: "_Pointer[emulator.CoreInfo]") -> None:
            pointer.contents.library_name = self.name
            pointer.contents.library_version = self.version

        self.retro_get_system_info = ctypes.CFUNCTYPE(
            None, ctypes.POINTER(emulator.CoreInfo)
        )(information)


@pytest.mark.parametrize(
    ("name", "version", "valid"),
    [
        (b"FCEUmm", b"1.2.3 abc+local", True),
        (b"other-core", b"1.2.3", False),
        (None, b"1.2.3", False),
        (b"FCEUmm", None, False),
        (b"FCEUmm", b"private\nfilename", False),
    ],
)
def test_backend_version_query_requires_expected_core_and_safe_complete_metadata(
    monkeypatch: pytest.MonkeyPatch,
    name: bytes | None,
    version: bytes | None,
    *,
    valid: bool,
) -> None:
    """Exercise metadata consumption through a local pointer ABI and process."""
    native_run = subprocess.run
    library = CoreLibrary(name, version)
    loaded: list[str] = []

    def load(path: str) -> CoreLibrary:
        loaded.append(path)
        return library

    def metadata(
        arguments: Sequence[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert list(arguments) == ["/usr/bin/retroarch", "--version"]
        assert capture_output
        assert text
        assert check
        return native_run(  # Fixed local metadata transcript producer.
            [
                sys.executable,
                "-I",
                str(HELPERS / "retroarch_metadata.py"),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )

    monkeypatch.setattr(ctypes, "CDLL", load)
    monkeypatch.setattr(subprocess, "run", metadata)
    if valid:
        observed = emulator.backend_versions(emulator_case("nes-fceumm"))
        assert observed == {
            "retroarch_version": "1.20.0",
            "core_library": "FCEUmm",
            "core_version": "1.2.3 abc+local",
        }
        assert "private" not in json.dumps(observed)
    else:
        with pytest.raises(
            ProbeError,
            match=r"core (library identity differs|version metadata missing)",
        ) as rejected:
            emulator.backend_versions(emulator_case("nes-fceumm"))
        assert "private" not in str(rejected.value)
    assert loaded == ["/usr/lib/libretro/fceumm_libretro.so"]


@pytest.mark.parametrize(
    "package", ["missing", "not-package", "ambiguous", "changed-launcher"]
)
def test_probe_run_refuses_untrusted_stock_package_before_selecting_media_or_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, package: str
) -> None:
    """Reject untrusted configgen before media selection or input allocation."""
    package_root = tmp_path / "configgen"
    package_root.mkdir()
    launcher = package_root / "emulatorlauncher.py"
    launcher.write_bytes(b"changed stock source with private path")
    specification = importlib.machinery.ModuleSpec(
        "configgen", loader=None, is_package=True
    )
    specification.submodule_search_locations = {
        "missing": [],
        "not-package": None,
        "ambiguous": [str(package_root), str(tmp_path / "other")],
        "changed-launcher": [str(package_root)],
    }[package]
    lease_observations: list[str] = []

    def permit() -> None:
        lease_observations.append("valid")

    def find(name: str) -> importlib.machinery.ModuleSpec | None:
        assert name == "configgen"
        return None if package == "missing" else specification

    monkeypatch.setattr(emulator, "input_permitted", permit)
    monkeypatch.setattr(importlib.util, "find_spec", find)
    probe = emulator.EmulatorProbe(
        tmp_path, catalog_path=tmp_path / "absent-private-catalog"
    )
    expected = {
        "missing": "Stock configgen package missing",
        "not-package": "Stock configgen package missing",
        "ambiguous": "Ambiguous stock configgen package",
        "changed-launcher": "Stock launcher differs from inspected source",
    }[package]
    with pytest.raises(ProbeError, match=expected) as rejected:
        probe.run()
    assert str(rejected.value) == expected
    assert lease_observations == ["valid"]
    assert probe.pad is None
    assert probe.launcher is None
    assert probe.desktop is None
    assert probe.result["native_device_consumption"] == {"status": "untested"}
    assert "media" not in probe.result
    assert not (tmp_path / "selection.json").exists()
    assert launcher.read_bytes() == b"changed stock source with private path"


@pytest.mark.parametrize(
    "fault",
    ["not-ready", "foreign-uid", "malformed-approval", "unapproved", "ordinary-file"],
)
def test_final_source_requires_owned_transport_approval_and_native_event_node(
    tmp_path: Path, fault: str
) -> None:
    """A real current PID or ordinary readable file does not grant native ownership."""
    ordinary = tmp_path / "private-file"
    ordinary.write_bytes(b"unrelated content")
    report: dict[str, object] = {
        "app_uid": os.getuid(),
        "approved_process_ids": [os.getpid()],
        "final": {
            "source_pid": os.getpid(),
            "node": str(ordinary),
            "sysname": "fixture",
        },
    }
    if fault == "foreign-uid":
        report["app_uid"] = os.getuid() + 1
    elif fault == "malformed-approval":
        report["approved_process_ids"] = "private approval text"
    elif fault == "unapproved":
        report["approved_process_ids"] = []
    probe = emulator.EmulatorProbe(tmp_path)
    with pytest.raises(ProbeError) as rejected:
        probe.pin_final(None if fault == "not-ready" else report)
    assert "private" not in str(rejected.value)
    assert probe.final_fd is None
    assert probe.final_identity is None
    assert ordinary.read_bytes() == b"unrelated content"


def test_changed_pinned_start_identity_records_numeric_failure_without_private_text(
    tmp_path: Path,
) -> None:
    """A live pidfd cannot excuse a different process-start identity."""
    probe = emulator.EmulatorProbe(tmp_path)
    start = process_stat(os.getpid())[1]
    probe.emulator_identity = ProcessIdentity(os.getpid(), start + 1)
    probe.emulator_fd = os.pidfd_open(os.getpid())
    descriptor = probe.emulator_fd
    try:
        with pytest.raises(ProbeError, match="start identity changed"):
            probe.observe_pinned_lifetime(probe.emulator_identity)
        failure = probe.process_observation_failure
        assert failure is not None
        assert failure["pid"] == os.getpid()
        assert failure["expected_start"] == start + 1
        assert failure["current_start"] == start
        assert failure["pidfd_live"] is True
        assert failure["errno"] is None
        assert set(failure) == {
            "role",
            "pid",
            "expected_start",
            "pidfd_live",
            "proc_state",
            "current_start",
            "errno",
        }
        assert "cmdline" not in failure
        assert "environment" not in failure
    finally:
        probe.close_process_observers([])
    with pytest.raises(OSError, match=r"\[Errno 9\] Bad file descriptor") as closed:
        os.fstat(descriptor)
    assert closed.value.errno == errno.EBADF


class ClassifiedDevice:
    """Supply only explicit external udev classifications to the consumer."""

    def __init__(self, properties: dict[str, str]) -> None:
        """Keep each observation independent of the synthetic event-node path."""
        self.properties: Mapping[str, str] = properties


class Classifier:
    """Model the read-only udev lookup, without native libraries or device access."""

    def __init__(self, final: int, pad: int, *, keyboard: bool) -> None:
        """Configure the independently expected final and gamepad classifications."""
        self.final, self.pad, self.keyboard = final, pad, keyboard

    def from_device_number(
        self, context: object, kind: str, number: int
    ) -> ClassifiedDevice:
        """Classify only the two declared synthetic event-device numbers."""
        assert context == "local-udev-context"
        assert kind == "char"
        if number == self.final:
            return ClassifiedDevice(
                {
                    "ID_INPUT_KEYBOARD": "1" if self.keyboard else "0",
                    "PRIVATE_SERIAL": "private classifier detail",
                }
            )
        assert number == self.pad
        return ClassifiedDevice({"ID_INPUT_JOYSTICK": "1"})


class UdevObserver:
    """Expose the typed external lookup expected by the probe."""

    def __init__(self, devices: Classifier) -> None:
        """Borrow the declared classification table."""
        self.Devices: emulator.UdevDevices = devices

    def Context(self) -> object:  # noqa: N802  # pyudev's external constructor name.
        """Return a distinct context token checked by the local lookup."""
        return "local-udev-context"


class ShortcutDeclaration:
    """Represent the external stock-generator shortcut declaration."""

    def getHotkeysContext(self) -> dict[str, object]:  # noqa: N802  # Stock API.
        """Declare an independently expected exit action, not observed JSON."""
        return {"name": "retroarch", "keys": {"exit": ["KEY_ESC"]}}


class LibretroDeclaration:
    """Expose only the external libretro-generator construction contract."""

    def LibretroGenerator(self) -> ShortcutDeclaration:  # noqa: N802  # Stock API.
        """Construct the immutable expected shortcut declaration."""
        return ShortcutDeclaration()


class StandaloneShortcutDeclaration:
    """Declare the unchanged standalone-emulator shortcut independently of JSON."""

    def getHotkeysContext(self) -> dict[str, object]:  # noqa: N802  # Stock API.
        """Require the ordinary standalone Alt+F4 exit context."""
        return {"name": "duckstation", "keys": {"exit": ["KEY_LEFTALT", "KEY_F4"]}}


class DuckstationDeclaration:
    """Represent stock firmware and shortcut declarations, not native behavior."""

    bios_lists: object = "fixture stock BIOS list"

    def find_bios(self, lists: object) -> Mapping[str, str]:
        """Declare recognized firmware without reading private BIOS files."""
        assert lists == self.bios_lists
        return {"Uni": "fixture-bios.bin"}

    def DuckstationGenerator(self) -> StandaloneShortcutDeclaration:  # noqa: N802  # Stock API.
        """Construct the independently expected standalone shortcut declaration."""
        return StandaloneShortcutDeclaration()


def local_input_view(
    routes: dict[str, Path], devices: dict[str, int], root_status: Path
) -> Callable[[str | os.PathLike[str]], PosixPath]:
    """Build an explicit synthetic procfs/device metadata view over real files.

    The child opens ordinary local files. Only their reported file kind/device
    and the status owner's UID are synthetic. These tests qualify consumer
    decisions, not kernel input, udev, stock configgen or native acceptance.
    """

    class LocalView(PosixPath):
        """Route selected external paths and model their declared metadata."""

        def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
            """Preserve real file metadata except declared synthetic event nodes."""
            info = super().stat(follow_symlinks=follow_symlinks)
            target = str(self)
            if str(self.parent).startswith("/proc/") and self.parent.name == "fd":
                target = str(self.readlink())
            if target not in devices:
                return info
            fields = list(info)
            fields[0] = stat.S_IFCHR | 0o600
            return os.stat_result(fields, {"st_rdev": devices[target]})

        def lstat(self) -> os.stat_result:
            """Supply root-controlled status metadata without requiring host chown."""
            info = super().lstat()
            if str(self) != str(root_status):
                return info
            fields = list(info)
            fields[4] = 0
            return os.stat_result(fields)

    def view(value: str | os.PathLike[str]) -> PosixPath:
        path = Path(value)
        return LocalView(routes.get(str(path), path))

    return view


@dataclass(frozen=True)
class ConsumptionFiles:
    """Own ordinary files standing in for generated settings and input nodes."""

    pad: Path
    final: Path
    status: Path
    profile: Path
    retroarch: Path
    duckstation: Path
    hotkeys: Path


def write_consumption_files(root: Path, backend: str, fault: str) -> ConsumptionFiles:
    """Write independent consumer inputs, corrupting only the selected contract."""
    files = ConsumptionFiles(
        root / "pad-event",
        root / "final-event",
        root / "transport.json",
        root / "es-input.cfg",
        root / "retroarch.cfg",
        root / "duckstation.ini",
        root / "hotkeygen.context",
    )
    files.pad.write_bytes(b"local synthetic pad")
    files.final.write_bytes(b"local synthetic keyboard")
    files.profile.write_text(
        "<inputList><inputConfig>"
        '<input name="b" type="button" id="0"/>'
        '<input name="a" type="button" id="1"/>'
        '<input name="start" type="button" id="7"/>'
        '<input name="select" type="button" id="6"/>'
        "</inputConfig></inputList>",
        encoding="utf-8",
    )
    write_retroarch_settings(files.retroarch, fault)
    write_duckstation_settings(files.duckstation, fault)
    exit_keys = ["KEY_ESC"] if backend == "libretro" else ["KEY_LEFTALT", "KEY_F4"]
    files.hotkeys.write_text(
        json.dumps(
            {
                "name": "retroarch" if backend == "libretro" else "duckstation",
                "keys": {"exit": ["KEY_Q"] if fault == "wrong-exit" else exit_keys},
            }
        ),
        encoding="utf-8",
    )
    return files


def write_retroarch_settings(path: Path, fault: str) -> None:
    """Materialize generated libretro bindings with one optional bad setting."""
    configuration = {
        "input_driver": "udev",
        "input_joypad_driver": "udev",
        "input_player1_b_btn": "0",
        "input_player1_a_btn": "1",
        "input_player1_start_btn": "7",
        "input_player1_select_btn": "6",
        "input_player1_up_btn": "h0up",
        "input_player1_l_x_minus_axis": "-0",
        "input_player1_joypad_index": "0",
    }
    changed = {
        "wrong-driver": ("input_driver", "sdl2"),
        "wrong-button": ("input_player1_start_btn", "6"),
        "wrong-hat": ("input_player1_up_btn", "4"),
        "wrong-axis": ("input_player1_l_x_minus_axis", "+0"),
        "wrong-player": ("input_player1_joypad_index", "1"),
    }.get(fault)
    if changed is not None:
        configuration[changed[0]] = changed[1]
    path.write_text(
        'private_unused_option = "private media filename"\n'
        + "\n".join(f'{key} = "{value}"' for key, value in configuration.items()),
        encoding="utf-8",
    )


def write_duckstation_settings(path: Path, fault: str) -> None:
    """Materialize standalone input and BIOS declarations for the consumer."""
    path.write_text(
        "[InputSources]\nSDL="
        + ("false" if fault == "wrong-driver" else "true")
        + "\nEvdev=false\nXInput=false\nRawInput=false\n"
        "[Pad1]\nType=DigitalController\nCross=SDL-0/A\nStart="
        + ("SDL-0/Back" if fault == "wrong-button" else "SDL-0/Start")
        + "\n[BIOS]\nSearchDirectory=/userdata/bios\nPathNTSCU="
        + ("wrong-bios.bin" if fault == "wrong-firmware" else "fixture-bios.bin")
        + "\nPathPAL=fixture-bios.bin\nPathNTSCJ=fixture-bios.bin\n",
        encoding="utf-8",
    )


def consumption_mapping(backend: str, fault: str) -> str:
    """Declare an SDL mapping independently of the probe's parsed evidence."""
    mapping = (
        "0123456789abcdef0123456789abcdef,Suite fixture,a:b0,b:b1,start:b7,"
        "back:b6,leftx:a0,lefty:a1,dpup:h0.1,"
    )
    if fault == "wrong-name":
        mapping = mapping.replace("Suite fixture", "private wrong name")
    elif backend == "duckstation" and fault == "wrong-hat":
        mapping = mapping.replace("dpup:h0.1", "dpup:h0.4")
    elif backend == "duckstation" and fault == "wrong-axis":
        mapping = mapping.replace("leftx:a0", "leftx:a2")
    if fault == "no-mapping":
        return ""
    if fault == "duplicate-mapping":
        return mapping + "\n" + mapping
    return mapping


def install_consumption_observers(
    monkeypatch: pytest.MonkeyPatch, files: ConsumptionFiles, fault: str
) -> None:
    """Install synthetic external metadata, leaving consumer decisions intact."""
    pad_device, final_device = os.makedev(13, 101), os.makedev(13, 102)
    view = local_input_view(
        {
            "/run/gow-full-x86-input-transport.json": files.status,
            "/userdata/system/configs/retroarch/retroarchcustom.cfg": files.retroarch,
            "/var/run/hotkeygen.context": files.hotkeys,
        },
        {str(files.pad): pad_device, str(files.final): final_device},
        files.status,
    )
    monkeypatch.setattr(emulator, "Path", view)
    monkeypatch.setattr(emulator, "PROFILE", files.profile)
    monkeypatch.setattr(emulator, "DUCKSTATION_SETTINGS", files.duckstation)
    monkeypatch.setattr(transport_probe, "STATUS", view(files.status))
    udev = UdevObserver(
        Classifier(final_device, pad_device, keyboard=fault != "not-keyboard")
    )

    def observe_udev() -> emulator.UdevAPI:
        return udev

    def observe_generator() -> emulator.LibretroGeneratorAPI:
        return LibretroDeclaration()

    def observe_duckstation_generator() -> emulator.DuckstationGeneratorAPI:
        return DuckstationDeclaration()

    monkeypatch.setattr(emulator, "_stock_udev", observe_udev)
    monkeypatch.setattr(emulator, "_stock_libretro_generator", observe_generator)
    monkeypatch.setattr(
        emulator, "_stock_duckstation_generator", observe_duckstation_generator
    )


def consumption_probe(
    root: Path, child: subprocess.Popen[bytes], backend: str, fault: str
) -> emulator.EmulatorProbe:
    """Supply the suite-owned pad and process identities to the real consumer."""
    cases = {
        "libretro": "nes-fceumm",
        "duckstation": "psx-duckstation",
        "xemu": "xbox-xemu",
    }
    probe = emulator.EmulatorProbe(root, case=cases[backend])
    probe.pad_device = os.makedev(13, 101)
    probe.pad_index = 1 if fault == "wrong-player" and backend == "duckstation" else 0
    # pragma: allowlist nextline secret
    probe.guid = "0123456789abcdef0123456789abcdef"
    probe.definition = {
        "name": "Suite fixture",
        "buttons": [304, 305, 314, 315, 316],
        "axes": [0, 1],
        "hat": [16, 17],
        "expected_sdl_counts": [5, 2, 1],
        "bus": 3,
        "vendor": 1,
        "product": 2,
        "version": 1,
        "guide_code": 316,
        "start_code": 315,
    }
    probe.bios_files = {"Uni": ("fixture-bios.bin", "fixture-firmware-identity")}
    probe.result["prerequisites"] = {"bios": {"stock_configured_route": False}}
    probe.result["pad_discovery"] = {
        "sdl": {"latest": {"joysticks": 2 if fault == "multiple-joysticks" else 1}},
    }
    probe.emulator_identity = ProcessIdentity(child.pid, process_stat(child.pid)[1])
    probe.result["profile"] = {"stock_configgen_consumed": False}
    return probe


@pytest.fixture
def consumption_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_children: list[subprocess.Popen[bytes]],
    backend: str,
    fault: str,
) -> Iterator[tuple[emulator.EmulatorProbe, ConsumptionFiles, subprocess.Popen[bytes]]]:
    """Own real child descriptors and files, with explicit synthetic metadata."""
    files = write_consumption_files(tmp_path, backend, fault)
    opened = [
        path
        for path in (files.pad, files.final)
        if fault != path.stem.split("-")[0] + "-unopened"
    ]
    # This descriptor-only child runs no application code and may be killed
    # immediately after stdin closes. Keep unrelated site/coverage hooks out.
    child = subprocess.Popen(  # noqa: S603  # Fixed local child, no native device.
        [
            sys.executable,
            "-I",
            "-S",
            str(HELPERS / "descriptor_consumer.py"),
            *(str(path) for path in opened),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            **os.environ,
            "SDL_GAMECONTROLLERCONFIG": consumption_mapping(backend, fault),
            "SDL_JOYSTICK_HIDAPI": "1" if fault == "wrong-environment" else "0",
            "XDG_CONFIG_HOME": "/userdata/system/configs",
            # pragma: allowlist nextline secret
            "PRIVATE_UNRELATED_SECRET": "private process environment detail",
        },
    )
    metadata_children.append(child)
    try:
        assert child.stdout is not None
        assert select.select([child.stdout], [], [], 3)[0]
        assert child.stdout.readline() == b"ready\n"
        files.status.write_text(
            json.dumps(
                {
                    "ready": True,
                    "worker_connected": True,
                    "app_uid": os.getuid(),
                    "approved_process_ids": [child.pid],
                    "sources": [
                        {
                            "name": "batocera hotkeys",
                            "role": "final",
                            "source_pid": child.pid,
                            "sysname": "input-final",
                            "node": str(files.final),
                        }
                    ]
                    + ([] if fault == "no-evmapy" else [{"name": "evmapy"}]),
                }
            ),
            encoding="utf-8",
        )
        files.status.chmod(0o600)
        install_consumption_observers(monkeypatch, files, fault)
        probe = consumption_probe(tmp_path, child, backend, fault)
        try:
            yield probe, files, child
        finally:
            descriptor = probe.final_fd
            failures: list[str] = []
            probe.close_process_observers(failures)
            assert failures == []
            assert probe.final_fd is None
            assert descriptor is not None
            with pytest.raises(
                OSError, match=r"\[Errno 9\] Bad file descriptor"
            ) as closed:
                os.fstat(descriptor)
            assert closed.value.errno == errno.EBADF
    finally:
        if child.stdin is not None:
            child.stdin.close()


def assert_consumption_evidence(
    probe: emulator.EmulatorProbe, child: subprocess.Popen[bytes], backend: str
) -> None:
    """Check independently expected mappings and live process ownership."""
    observed = object_record(probe.result["native_device_consumption"])
    assert observed["status"] == "passed"
    if backend == "libretro":
        assert observed["final_device"] == [13, 102]
        assert observed["generated_mapping"] == {
            "input_player1_b_btn": "0",
            "input_player1_a_btn": "1",
            "input_player1_start_btn": "7",
            "input_player1_select_btn": "6",
        }
        assert observed["final_source"] == {
            "pid": child.pid,
            "start": process_stat(child.pid)[1],
            "pinned_live": True,
        }
    else:
        assert observed["input_source"] == "SDL"
        assert observed["consumer_topology"] == {
            "discovered_joysticks": 1,
            "opened_joysticks": [[13, 101]],
            "configured_player_index": 0,
            "index_basis": "single-observed-suite-pad",
        }
        assert (
            object_record(observed["generated_mapping"])["Pad1.Start"] == "SDL-0/Start"
        )
        assert (
            object_record(object_record(probe.result["prerequisites"])["bios"])[
                "stock_configured_route"
            ]
            is True
        )
    assert observed["pad_device"] == [13, 101]
    assert observed["opened_devices"] in (
        [[13, 101], [13, 102]],
        [[13, 102], [13, 101]],
    )
    assert object_record(probe.result["profile"])["stock_configgen_consumed"] is True


@pytest.mark.parametrize(
    ("backend", "fault"),
    [
        ("libretro", fault)
        for fault in (
            "none",
            "pad-unopened",
            "final-unopened",
            "not-keyboard",
            "wrong-driver",
            "wrong-button",
            "wrong-hat",
            "wrong-axis",
            "wrong-player",
            "wrong-exit",
            "no-evmapy",
        )
    ]
    + [
        ("duckstation", fault)
        for fault in (
            "none",
            "pad-unopened",
            "wrong-driver",
            "wrong-button",
            "wrong-hat",
            "wrong-axis",
            "wrong-player",
            "wrong-exit",
            "no-evmapy",
            "wrong-firmware",
            "wrong-environment",
            "no-mapping",
            "duplicate-mapping",
            "wrong-name",
            "multiple-joysticks",
        )
    ],
)
def test_consumption_requires_opened_devices_generated_mapping_and_exit_context(
    consumption_scenario: tuple[
        emulator.EmulatorProbe, ConsumptionFiles, subprocess.Popen[bytes]
    ],
    backend: str,
    fault: str,
) -> None:
    """Require opened devices, generated bindings and matching stock shortcuts."""
    probe, files, child = consumption_scenario
    original_config = files.retroarch.read_bytes()
    if fault == "none":
        assert probe.native_consumption()
        assert_consumption_evidence(probe, child, backend)
    else:
        if fault in ("pad-unopened", "final-unopened"):
            assert probe.native_consumption() is False
        else:
            with pytest.raises(ProbeError):
                probe.native_consumption()
        assert probe.result["native_device_consumption"] == {"status": "untested"}
        assert (
            object_record(probe.result["profile"])["stock_configgen_consumed"] is False
        )
    assert probe.result["status"] == "failed"
    assert "private" not in json.dumps(probe.result)
    assert files.retroarch.read_bytes() == original_config
    assert child.poll() is None


class XboxShortcutDeclaration:
    """Declare the expected Xbox shortcut without consulting observed settings."""

    def getHotkeysContext(self) -> dict[str, object]:  # noqa: N802  # Stock API.
        """Require the standalone Alt+F4 exit action."""
        return {"name": "xemu", "keys": {"exit": ["KEY_LEFTALT", "KEY_F4"]}}


class XboxGeneratorDeclaration:
    """Expose external generator metadata, not an emulator implementation."""

    def XemuGenerator(self) -> XboxShortcutDeclaration:  # noqa: N802  # Stock API.
        """Construct the independent expected exit declaration."""
        return XboxShortcutDeclaration()


@dataclass(frozen=True)
class XboxConsumptionFiles:
    """Own a generated TOML, selected disc and mmap input beside shared files."""

    inputs: ConsumptionFiles
    config: Path
    disc: Path
    library: Path


def write_xbox_settings(path: Path, disc: Path, fault: str) -> None:
    """Declare ordinary stock routes, with one independently chosen fault."""
    routes = {
        "flashrom_path": "/userdata/bios/Complex_4627.bin",
        "bootrom_path": "/userdata/bios/mcpx_1.0.bin",
        "hdd_path": "/userdata/saves/xbox/xbox_hdd.qcow2",
        "eeprom_path": "/userdata/saves/xbox/xemu_eeprom.bin",
    }
    if fault in routes:
        routes[fault] = "/private/unapproved-state"
    port = (
        "11111111111111111111111111111111"
        if fault == "wrong-port"
        # pragma: allowlist nextline secret
        else "0123456789abcdef0123456789abcdef"
    )
    dvd: str | int = str(disc)
    if fault == "missing-disc":
        dvd = 42
    elif fault == "wrong-disc":
        dvd = str(disc.with_name("private-other.iso"))
    path.write_text(
        "[sys.files]\n"
        + "\n".join(f"{key} = {json.dumps(value)}" for key, value in routes.items())
        + f"\ndvd_path = {json.dumps(dvd)}\n[input.bindings]\n"
        + f"port1 = {json.dumps(port)}\n",
        encoding="utf-8",
    )


def xbox_mapping(fault: str) -> str:
    """Supply an effective mapping whose buttons remain independent of XML."""
    mapping = consumption_mapping("xemu", fault)
    if fault == "observed-guid":
        mapping += "\n" + mapping.replace(
            # pragma: allowlist nextline secret
            "0123456789abcdef0123456789abcdef",
            "11111111111111111111111111111111",
        )
    changed = {
        "wrong-button": ("start:b7", "start:b6"),
        "wrong-axis": ("lefty:a1", "lefty:a2"),
        "wrong-hat": ("dpup:h0.1", "dpup:h0.4"),
    }.get(fault)
    return mapping if changed is None else mapping.replace(*changed)


def xbox_consumer_child(
    files: XboxConsumptionFiles, fault: str
) -> subprocess.Popen[bytes]:
    """Start an owned child with real open files, memory mapping and environment."""
    opened = (
        [files.inputs.final]
        if fault == "pad-unopened"
        else [files.inputs.pad, files.inputs.final]
    )
    mapped = files.library
    if fault == "different-library":
        mapped = mapped.with_name("other-library")
        mapped.write_bytes(files.library.read_bytes())
    return subprocess.Popen(  # noqa: S603  # Fixed local child and owned files.
        [
            sys.executable,
            "-I",
            "-S",
            str(HELPERS / "xbox_consumer.py"),
            str(mapped),
            fault,
            *(str(path) for path in opened),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            **os.environ,
            "SDL_GAMECONTROLLERCONFIG": xbox_mapping(fault),
            "XDG_CONFIG_HOME": (
                "/private/wrong-config"
                if fault == "wrong-home"
                else "/userdata/system/configs"
            ),
            "LC_NUMERIC": "de_DE" if fault == "wrong-locale" else "C",
            # pragma: allowlist nextline secret
            "PRIVATE_UNRELATED_SECRET": "private process environment detail",
        },
    )


def install_xbox_metadata(
    monkeypatch: pytest.MonkeyPatch, files: XboxConsumptionFiles, fault: str
) -> None:
    """Model external node kinds and generator metadata, never a native SDL run."""
    install_consumption_observers(monkeypatch, files.inputs, fault)
    view = local_input_view(
        {
            "/run/gow-full-x86-input-transport.json": files.inputs.status,
            "/var/run/hotkeygen.context": files.inputs.hotkeys,
            "/userdata/roms": files.disc.parent,
        },
        {
            str(files.inputs.pad): os.makedev(13, 101),
            str(files.inputs.final): os.makedev(13, 102),
        },
        files.inputs.status,
    )
    monkeypatch.setattr(emulator, "Path", view)
    monkeypatch.setattr(emulator, "XEMU_CONFIG", files.config)
    monkeypatch.setattr(emulator, "XEMU_SDL", str(files.library))

    def generator() -> emulator.XemuGeneratorAPI:
        return XboxGeneratorDeclaration()

    monkeypatch.setattr(emulator, "_stock_xemu_generator", generator)


@pytest.fixture
def xbox_consumption_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_children: list[subprocess.Popen[bytes]],
    fault: str,
) -> Iterator[
    tuple[emulator.EmulatorProbe, XboxConsumptionFiles, subprocess.Popen[bytes]]
]:
    """Use real procfs observations with explicitly synthetic input classification."""
    inputs = write_consumption_files(tmp_path, "xemu", fault)
    files = XboxConsumptionFiles(
        inputs,
        tmp_path / "xemu.toml",
        tmp_path / "private-disc.iso",
        tmp_path / "sdl-object",
    )
    files.library.write_bytes(b"owned mmap input, not a shared library\n" * 256)
    files.disc.write_bytes(b"private selected disc bytes")
    write_xbox_settings(files.config, files.disc, fault)
    inputs.hotkeys.write_text(
        json.dumps(
            {
                "name": "wrong-emulator" if fault == "wrong-context" else "xemu",
                "keys": {
                    "exit": ["KEY_Q"]
                    if fault == "wrong-exit"
                    else ["KEY_LEFTALT", "KEY_F4"]
                },
            }
        ),
        encoding="utf-8",
    )
    child = xbox_consumer_child(files, fault)
    metadata_children.append(child)
    probe = consumption_probe(tmp_path, child, "xemu", fault)
    probe.selection = MediaSelection(
        "xbox", files.disc.name, (), "selected-disc-identity"
    )
    probe.xemu_topology = {
        # pragma: allowlist nextline secret
        "guid": "0123456789abcdef0123456789abcdef",
        "discovered_gamepads": 1,
        "matching_guid_gamepads": 1,
        "suite_device_matched": True,
    }
    try:
        assert child.stdout is not None
        assert select.select([child.stdout], [], [], 3)[0]
        assert child.stdout.readline() == b"ready\n"
        inputs.status.write_text(
            json.dumps(
                {
                    "sources": [] if fault == "no-evmapy" else [{"name": "evmapy"}],
                }
            ),
            encoding="utf-8",
        )
        inputs.status.chmod(0o600)
        install_xbox_metadata(monkeypatch, files, fault)
        yield probe, files, child
    finally:
        failures: list[str] = []
        probe.close_process_observers(failures)
        assert failures == []
        if child.stdin is not None:
            child.stdin.close()


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "pad-unopened",
        "nonexecutable-map",
        "different-library",
        "wrong-home",
        "wrong-locale",
        "no-mapping",
        "duplicate-mapping",
        "wrong-button",
        "wrong-axis",
        "wrong-hat",
        "flashrom_path",
        "bootrom_path",
        "hdd_path",
        "eeprom_path",
        "missing-disc",
        "wrong-disc",
        "wrong-port",
        "wrong-context",
        "wrong-exit",
        "no-evmapy",
    ],
)
def test_xbox_consumption_binds_real_process_to_selected_disc_and_generated_routes(
    xbox_consumption_scenario: tuple[
        emulator.EmulatorProbe, XboxConsumptionFiles, subprocess.Popen[bytes]
    ],
    fault: str,
) -> None:
    """Reject incomplete consumption without changing disc, settings or pass state."""
    probe, files, child = xbox_consumption_scenario
    before = (files.config.read_bytes(), files.disc.read_bytes())
    if fault == "none":
        assert probe.xemu_consumption()
        observed = object_record(probe.result["native_device_consumption"])
        assert observed["status"] == "passed"
        assert observed["input_source"] == "SDL3"
        assert observed["pad_device"] == [13, 101]
        assert observed["opened_devices"] == [[13, 101], [13, 102]]
        assert observed["generated_mapping"] == {
            # pragma: allowlist nextline secret
            "input.bindings.port1": "0123456789abcdef0123456789abcdef"
        }
        assert observed["environment"] == {
            # pragma: allowlist nextline secret
            "sdl_mapping_guid": "0123456789abcdef0123456789abcdef",
            "suite_mapping_consumed": True,
            "XDG_CONFIG_HOME": "/userdata/system/configs",
            "LC_NUMERIC": "C",
        }
        configured = object_record(observed["configured_files"])
        assert configured["dvd_identity"] == "selected-disc-identity"
        assert "dvd_path" not in configured
        assert (
            object_record(observed["sdl_object"])["sha256"]
            == hashlib.sha256(files.library.read_bytes()).hexdigest()
        )
        assert (
            object_record(probe.result["profile"])["stock_configgen_consumed"] is True
        )
    else:
        if fault == "pad-unopened":
            assert probe.xemu_consumption() is False
        else:
            with pytest.raises(ProbeError):
                probe.xemu_consumption()
        assert probe.result["native_device_consumption"] == {"status": "untested"}
        assert (
            object_record(probe.result["profile"])["stock_configgen_consumed"] is False
        )
    assert "private" not in json.dumps(probe.result)
    assert probe.result["status"] == "failed"
    assert (files.config.read_bytes(), files.disc.read_bytes()) == before
    assert child.poll() is None


@pytest.mark.parametrize("fault", ["observed-guid"])
@pytest.mark.parametrize("port_matches", [False, True])
def test_xbox_port_must_match_observed_sdl_guid_not_only_environment_mapping(
    xbox_consumption_scenario: tuple[
        emulator.EmulatorProbe, XboxConsumptionFiles, subprocess.Popen[bytes]
    ],
    monkeypatch: pytest.MonkeyPatch,
    *,
    port_matches: bool,
) -> None:
    """Consume synthetic SDL metadata and cache it without claiming library proof."""
    probe, files, _child = xbox_consumption_scenario
    actual_guid = "11111111111111111111111111111111"
    if port_matches:
        write_xbox_settings(files.config, files.disc, "wrong-port")
    observations: list[int] = []

    def observe_gamepad(device: int, mapping: str, name: str) -> dict[str, object]:
        assert device == os.makedev(13, 101)
        assert "start:b7" in mapping
        assert name == "Suite fixture"
        observations.append(device)
        return {
            "guid": actual_guid,
            "discovered_gamepads": 2,
            "matching_guid_gamepads": 1,
            "suite_device_matched": True,
        }

    monkeypatch.setattr(emulator, "sdl3_gamepad", observe_gamepad)
    probe.xemu_topology = None
    if port_matches:
        assert probe.xemu_consumption()
        assert probe.xemu_consumption()
        evidence = object_record(probe.result["native_device_consumption"])
        assert evidence["generated_mapping"] == {"input.bindings.port1": actual_guid}
        assert object_record(evidence["consumer_topology"])["discovered_gamepads"] == 2
    else:
        with pytest.raises(ProbeError):
            probe.xemu_consumption()
        assert probe.result["native_device_consumption"] == {"status": "untested"}
        assert (
            object_record(probe.result["profile"])["stock_configgen_consumed"] is False
        )
    assert observations == [os.makedev(13, 101)]
    assert "private" not in json.dumps(probe.result)


def owned_xbox_disc_probe(root: Path, entry: str) -> emulator.EmulatorProbe:
    """Configure a selected owned file without allocating native resources."""
    probe = emulator.EmulatorProbe(root, case="xbox-xemu")
    probe.selection = MediaSelection("xbox", entry, (), "selected-disc-identity")
    return probe


@pytest.mark.parametrize(
    "settings",
    ["bounded", "oversized", "symlink", "directory", "malformed", "invalid-utf8"],
)
def test_xbox_disc_requires_bounded_nofollow_generated_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: str
) -> None:
    """Consume the selected ISO without rewriting or following generated TOML."""
    disc, config = tmp_path / "private-disc.iso", tmp_path / "xemu.toml"
    target = tmp_path / "private-config"
    disc.write_bytes(b"private immutable ISO fixture")
    write_xbox_settings(config, disc, "none")
    original = config.read_bytes()
    if settings in ("bounded", "oversized"):
        size = 65536 if settings == "bounded" else 65537
        config.write_bytes(original + b"#" + b"x" * (size - len(original) - 1))
    elif settings == "symlink":
        config.rename(target)
        config.symlink_to(target)
    elif settings == "directory":
        config.unlink()
        config.mkdir()
    elif settings == "malformed":
        config.write_text("private invalid TOML [[[", encoding="utf-8")
    else:
        config.write_bytes(b"\xffprivate invalid encoding")
    monkeypatch.setattr(emulator, "XEMU_CONFIG", config)
    monkeypatch.setattr(
        emulator,
        "Path",
        local_input_view({"/userdata/roms": tmp_path}, {}, tmp_path / "unused-status"),
    )
    probe = owned_xbox_disc_probe(tmp_path, disc.name)
    if settings == "bounded":
        assert probe.xemu_disc() == disc
        assert config.stat().st_size == 65536
    elif settings == "symlink":
        with pytest.raises(OSError, match=r"\[Errno 40\]") as refused:
            probe.xemu_disc()
        assert refused.value.errno == errno.ELOOP
        assert target.read_bytes() == original
        assert config.is_symlink()
    elif settings == "directory":
        with pytest.raises(IsADirectoryError):
            probe.xemu_disc()
    elif settings == "malformed":
        with pytest.raises(tomllib.TOMLDecodeError):
            probe.xemu_disc()
    elif settings == "invalid-utf8":
        with pytest.raises(UnicodeDecodeError):
            probe.xemu_disc()
    else:
        with pytest.raises(ProbeError):
            probe.xemu_disc()
    assert disc.read_bytes() == b"private immutable ISO fixture"
    assert "private" not in json.dumps(probe.result)
    assert probe.result["native_device_consumption"] == {"status": "untested"}


@dataclass(frozen=True)
class XboxSquashfsFiles:
    """Own archive, extracted stand-in and observations, with no actual mounts."""

    archive: Path
    disc: Path
    mount: Path
    backing: Path
    mountinfo: Path
    config: Path


def write_xbox_squashfs_files(root: Path, fault: str) -> XboxSquashfsFiles:
    """Materialize a synthetic mount boundary over real independently owned files."""
    roms = root / "roms"
    roms.mkdir()
    mount = root / "mounted images" / "private-archive"
    mount.mkdir(parents=True)
    archive = roms / (
        "private-archive.zip" if fault == "unsupported" else "private-archive.squashfs"
    )
    archive.write_bytes(b"private selected archive")
    disc = mount / "private-disc.iso"
    disc.write_bytes(b"private disc in modeled mount")
    if fault == "escape":
        outside = root / "private-outside.iso"
        disc.rename(outside)
        disc.symlink_to(outside)
    elif fault == "not-regular":
        disc.unlink()
        disc.mkdir()
    alias = root / "private-backing-alias"
    if fault == "different-backing":
        alias.write_bytes(archive.read_bytes())
    else:
        alias.hardlink_to(archive)
    backing = root / "sys" / "loop7" / "loop" / "backing_file"
    backing.parent.mkdir(parents=True)
    backing.write_text(str(alias).lstrip("/") + "\n", encoding="utf-8")
    escaped_mount = str(mount).replace(" ", r"\040")
    device = "/dev/sda" if fault == "non-loop" else "/dev/loop7"
    filesystem = "ext4" if fault == "wrong-filesystem" else "squashfs"
    row = f"30 20 7:7 / {escaped_mount} ro - {filesystem} {device} ro\n"
    mountinfo = root / "mountinfo"
    mountinfo.write_text(
        row * (2 if fault == "ambiguous-mount" else 1), encoding="utf-8"
    )
    config = root / "xemu.toml"
    write_xbox_settings(config, disc, "none")
    return XboxSquashfsFiles(archive, disc, mount, backing, mountinfo, config)


def install_xbox_mount_observations(
    monkeypatch: pytest.MonkeyPatch, files: XboxSquashfsFiles, fault: str
) -> None:
    """Supply synthetic mountinfo/statvfs, not privileged or stock mount acceptance."""
    monkeypatch.setattr(emulator, "XEMU_CONFIG", files.config)
    monkeypatch.setattr(
        emulator,
        "Path",
        local_input_view(
            {
                "/userdata/roms": files.archive.parent,
                "/var/run/squashfs": files.mount.parent,
                "/proc/self/mountinfo": files.mountinfo,
                "/sys/class/block": files.backing.parents[2],
            },
            {},
            files.archive.parent / "unused-status",
        ),
    )
    original = os.statvfs

    def observed_statvfs(path: str | os.PathLike[str]) -> os.statvfs_result:
        if os.fspath(path) == str(files.disc):
            flags = 0 if fault == "writable" else os.ST_RDONLY
            return os.statvfs_result((4096, 4096, 1, 1, 1, 1, 1, 1, flags, 255))
        return original(path)

    monkeypatch.setattr(os, "statvfs", observed_statvfs)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "writable",
        "escape",
        "different-backing",
        "non-loop",
        "wrong-filesystem",
        "ambiguous-mount",
        "unsupported",
        "not-regular",
    ],
)
def test_xbox_squashfs_disc_requires_unique_readonly_selected_archive_backing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Bind the disc to the selected inode, rejecting writable or unrelated views."""
    files = write_xbox_squashfs_files(tmp_path, fault)
    before = (files.archive.read_bytes(), files.config.read_bytes())
    install_xbox_mount_observations(monkeypatch, files, fault)
    probe = owned_xbox_disc_probe(tmp_path, files.archive.name)
    if fault == "none":
        assert probe.xemu_disc() == files.disc
        assert files.disc.read_bytes() == b"private disc in modeled mount"
    else:
        with pytest.raises(ProbeError):
            probe.xemu_disc()
    assert (files.archive.read_bytes(), files.config.read_bytes()) == before
    assert "private" not in json.dumps(probe.result)
    assert probe.result["native_device_consumption"] == {"status": "untested"}
