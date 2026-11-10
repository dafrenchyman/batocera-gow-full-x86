"""Owned stock emulator native launch and Guide+Start exit diagnostic.

Run only as native Cmd through the packaged supervisor and entrypoint. The
coordinator validates effective mounts and isolation before renewing the lease.
Private media selection reuses the maintained mounted-media implementation.
"""

import configparser
import contextlib
import ctypes
import hashlib
import importlib
import importlib.util
import json
import os
import re
import secrets
import select
import signal
import stat
import subprocess
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET
from _ctypes import CFuncPtr
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from functools import partial
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, ClassVar, Protocol, TypedDict, runtime_checkable

from .duckstation_backend import active_backend
from .duckstation_install import OVERRIDE_NAME, launcher_environment
from .duckstation_wrapper import CasePreservingConfigParser
from .emulator_lifecycle import (
    STOCK_LAUNCHER_SHA256,
    EmulatorLifecycle,
    ExitBudgets,
    Observation,
    PrivateOutput,
    ProcessIdentity,
    TransitionError,
    stock_termination,
)
from .input_transport import live, process_stat
from .media_catalog import (
    DUCKSTATION_PACKAGE_SOURCE,
    XEMU_HDD,
    XEMU_HDD_SHA256,
    XEMU_HDD_USE,
    XEMU_PACKAGE_SOURCE,
    XEMU_SDL,
    EmulatorCase,
    emulator_case,
    load_catalog,
    object_record,
)
from .mounted_media import (
    MediaSelection,
    inspect_media,
    inspect_xiso,
    read_selection,
    select_media,
    write_selection,
)
from .native_diagnostics import (
    Desktop,
    DiagnosticError,
    capture_checkpoint,
    input_permitted,
    publish_json,
    publish_selected_log,
    transport_ready,
)
from .resources import RUNTIME_ROOT
from .transport_probe import Probe, ProbeError, require, wait_for

if TYPE_CHECKING:
    # Match Structure._fields_ without a private ctypes import at runtime.
    from _ctypes import _CDataType

    _StructureFields = Sequence[
        tuple[str, type[_CDataType]] | tuple[str, type[_CDataType], int]
    ]

CATALOG = Path("/usr/share/emulationstation/es_systems.cfg")
ROMS = Path("/home/retro/userdata/roms")
PROFILE = Path("/userdata/system/configs/emulationstation/es_input.cfg")
DUCKSTATION_SETTINGS = Path("/userdata/system/configs/duckstation/settings.ini")
XEMU_CONFIG = Path("/userdata/system/configs/xemu/xemu.toml")
XEMU_FILES = {
    "flashrom_path": "/userdata/bios/Complex_4627.bin",
    "bootrom_path": "/userdata/bios/mcpx_1.0.bin",
    "hdd_path": "/userdata/saves/xbox/xbox_hdd.qcow2",
    "eeprom_path": "/userdata/saves/xbox/xemu_eeprom.bin",
}
ASSERTIONS = "stock-native-observed-exit-v3"
CONTROLS = (
    "none",
    "withhold-readiness",
    "withhold-chord",
    "wrong-window",
    "pre-chord-death",
    "launcher-error",
    "early-native-exit",
)

# Bounds belong to the pinned stock schemas and private diagnostic contract.
SDL_CONTROL_COUNTS = 3
SDL_GUID_LENGTH = 32
SDL_MAPPING_PREFIX_FIELDS = 2
SDL_MAX_GAMEPADS = 64
SDL_LOG_INPUT_CATEGORY = 7
SDL_LOG_DEBUG_PRIORITY = 2
MAX_EVENT_CODE = 0xFFFF
MAX_ENVIRONMENT_BYTES = 262144
MAX_METADATA_BYTES = 65536
MAX_PROCFS_BYTES = 1024 * 1024
MAX_UDEV_RECORD_BYTES = 4096
MAX_LEADER_STAT_BYTES = 4096
PROC_MAP_REQUIRED_FIELDS = 5
PROC_STAT_REQUIRED_FIELDS = 20
STOCK_XBOX_HDD_BYTES = 4521984
MIN_RENDER_WIDTH = 256
MIN_RENDER_HEIGHT = 224
MIN_RENDER_COLORS = 2
MAX_EXCEPTION_BYTES = 8192
MAX_EXCEPTION_LINES = 128
MAX_EXCEPTION_FRAMES = 8
MAX_ERRNO = 4095
MAX_STARTUP_LINES = 256
LINUX_INPUT_MAJOR = 13
MAX_X11_VISUAL = 0xFFFFFFFF
DUCKSTATION_VISUAL_ARGUMENT_FIELDS = 7
DUCKSTATION_ARGUMENT_FIELDS = 5
NEWLINE_BYTE = 10
SDL_AXIS_QUALIFICATION_THRESHOLD = -16000


def _record(value: object) -> dict[str, object]:
    """Borrow a mutable report object, rejecting malformed external records."""
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        message = "Native observation object malformed"
        raise ProbeError(message)
    return value


def _records(value: object) -> list[dict[str, object]]:
    """Validate a transport source list without assuming JSON field types."""
    if not isinstance(value, list):
        message = "Native observation list malformed"
        raise ProbeError(message)
    return [_record(item) for item in value]


def _text(value: object) -> str:
    """Require a string without disclosing a rejected private value."""
    if not isinstance(value, str):
        message = "Native observation text malformed"
        raise ProbeError(message)
    return value


def _integer(value: object) -> int:
    """Require an integer rather than accepting JSON booleans as device IDs."""
    if isinstance(value, bool) or not isinstance(value, int):
        message = "Native observation integer malformed"
        raise ProbeError(message)
    return value


def _strings(value: object) -> list[str]:
    """Borrow an error list only after validating its public text entries."""
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        message = "Native observation text list malformed"
        raise ProbeError(message)
    return value


class GamepadDefinition(TypedDict):
    """Validated owned controller asset consumed by uinput and stock SDL."""

    name: str
    buttons: list[int]
    axes: list[int]
    hat: list[int]
    expected_sdl_counts: list[int]
    bus: int
    vendor: int
    product: int
    version: int
    guide_code: int
    start_code: int


def _integer_list(value: object) -> list[int]:
    """Validate controller event codes before granting them to uinput."""
    if not isinstance(value, list):
        message = "Suite gamepad event list malformed"
        raise ProbeError(message)
    return [_integer(item) for item in value]


def _gamepad_definition(path: Path) -> GamepadDefinition:
    """Read the staged suite asset, never a file adjacent to installed source."""
    value = _record(json.loads(path.read_text(encoding="utf-8")))
    definition: GamepadDefinition = {
        "name": _text(value["name"]),
        "buttons": _integer_list(value["buttons"]),
        "axes": _integer_list(value["axes"]),
        "hat": _integer_list(value["hat"]),
        "expected_sdl_counts": _integer_list(value["expected_sdl_counts"]),
        "bus": _integer(value["bus"]),
        "vendor": _integer(value["vendor"]),
        "product": _integer(value["product"]),
        "version": _integer(value["version"]),
        "guide_code": _integer(value["guide_code"]),
        "start_code": _integer(value["start_code"]),
    }
    require(
        definition["name"]
        and len(definition["expected_sdl_counts"]) == SDL_CONTROL_COUNTS
        and definition["guide_code"] in definition["buttons"]
        and definition["start_code"] in definition["buttons"]
        and all(
            0 <= code <= MAX_EVENT_CODE
            for codes in (definition["buttons"], definition["axes"], definition["hat"])
            for code in codes
        ),
        "Suite gamepad definition invalid",
    )
    return definition


@runtime_checkable
class NativePad(Protocol):
    """Owned uinput device; its creator releases all holds before closing."""

    fd: int

    def write(self, event_type: int, code: int, value: int) -> None:
        """Write one event without synchronizing the frame."""
        ...

    def syn(self) -> None:
        """Publish a complete event frame."""
        ...

    def close(self) -> None:
        """Release the owned device descriptor."""
        ...


@runtime_checkable
class EventCodes(Protocol):
    """Stock evdev event classes used by this controller."""

    EV_KEY: int
    EV_ABS: int


@runtime_checkable
class UInputBackend(Protocol):
    """Stock evdev native helper used to identify the created device."""

    def get_sysname(self, descriptor: int) -> str:
        """Return the kernel sysname for an owned uinput descriptor."""
        ...


@runtime_checkable
class EvdevAPI(Protocol):
    """Small stock evdev contract, imported only for native device creation."""

    ecodes: EventCodes
    _uinput: UInputBackend

    def AbsInfo(  # noqa: N802, PLR0913, PLR0917  # Stock evdev's six-field native ABI.
        self,
        value: int,
        minimum: int,
        maximum: int,
        fuzz: int,
        flat: int,
        resolution: int,
    ) -> object:  # Exact stock library API.
        """Construct the stock absolute-axis information record."""
        ...

    def UInput(  # noqa: N802, PLR0913  # Stock evdev constructor keywords.
        self,
        *,
        events: object,
        name: str,
        bustype: int,
        vendor: int,
        product: int,
        version: int,
    ) -> NativePad:  # Exact stock library API.
        """Create a suite-owned device with only declared capabilities."""
        ...


@runtime_checkable
class SDLAPI(Protocol):
    """Stock PySDL2 calls used to qualify the suite pad before configgen."""

    SDL_INIT_JOYSTICK: int
    SDL_InitSubSystem: CFuncPtr

    def SDL_version(self) -> "SDLVersion":  # noqa: N802  # Exact stock library API.
        """Construct the actual PySDL2 structure accepted by its pointer ABI."""
        ...

    def SDL_GetVersion(self, version: object) -> None:  # noqa: N802  # Exact stock library API.
        """Write the stock SDL version ABI."""
        ...

    def SDL_JoystickUpdate(self) -> None:  # noqa: N802  # Exact stock library API.
        """Refresh the current joystick state."""
        ...

    def SDL_NumJoysticks(self) -> int:  # noqa: N802  # Exact stock library API.
        """Return the current joystick count."""
        ...

    def SDL_JoystickPathForIndex(self, index: int) -> bytes | None:  # noqa: N802  # Exact stock library API.
        """Return the native event node for an SDL index."""
        ...

    def SDL_GetError(self) -> bytes | None:  # noqa: N802  # Exact stock library API.
        """Return ephemeral diagnostic bytes that must not be retained."""
        ...

    def SDL_JoystickOpen(self, index: int) -> object:  # noqa: N802  # Exact stock library API.
        """Open the suite pad for state qualification."""
        ...

    def SDL_JoystickClose(self, joystick: object) -> None:  # noqa: N802  # Exact stock library API.
        """Close this observer's reader without destroying uinput."""
        ...

    def SDL_JoystickName(self, joystick: object) -> bytes:  # noqa: N802  # Exact stock library API.
        """Return the discovered pad name."""
        ...

    def SDL_JoystickNumButtons(self, joystick: object) -> int:  # noqa: N802  # Exact stock library API.
        """Return the discovered button count."""
        ...

    def SDL_JoystickNumAxes(self, joystick: object) -> int:  # noqa: N802  # Exact stock library API.
        """Return the discovered axis count."""
        ...

    def SDL_JoystickNumHats(self, joystick: object) -> int:  # noqa: N802  # Exact stock library API.
        """Return the discovered hat count."""
        ...

    def SDL_JoystickGetGUID(self, joystick: object) -> object:  # noqa: N802  # Exact stock library API.
        """Return the stock value-type GUID."""
        ...

    def SDL_JoystickGetGUIDString(  # noqa: N802  # Exact stock library API.
        self, guid: object, buffer: object, size: int
    ) -> None:
        """Write the GUID's hexadecimal representation."""
        ...

    def SDL_JoystickGetButton(self, joystick: object, index: int) -> int:  # noqa: N802  # Exact stock library API.
        """Read one qualified button."""
        ...

    def SDL_JoystickGetAxis(self, joystick: object, index: int) -> int:  # noqa: N802  # Exact stock library API.
        """Read one qualified axis."""
        ...

    def SDL_JoystickGetHat(self, joystick: object, index: int) -> int:  # noqa: N802  # Exact stock library API.
        """Read one qualified hat."""
        ...

    def SDL_QuitSubSystem(self, flags: int) -> None:  # noqa: N802  # Exact stock library API.
        """Close only the observer's initialized subsystem."""
        ...


class SDLVersion(ctypes.Structure):
    """SDL2's three-byte public version ABI."""

    _fields_: ClassVar["_StructureFields"] = [
        ("major", ctypes.c_uint8),
        ("minor", ctypes.c_uint8),
        ("patch", ctypes.c_uint8),
    ]
    # ctypes' metaclass creates and initializes these native field descriptors.
    major: int  # pyright: ignore[reportUninitializedInstanceVariable]
    minor: int  # pyright: ignore[reportUninitializedInstanceVariable]
    patch: int  # pyright: ignore[reportUninitializedInstanceVariable]


class UdevDevice(Protocol):
    """Read-only stock classification properties for a device number."""

    properties: Mapping[str, str]


class UdevDevices(Protocol):
    """Stock pyudev device-number lookup used instead of trusting node names."""

    def from_device_number(self, context: object, kind: str, number: int) -> UdevDevice:
        """Resolve properties for the exact kernel character-device number."""
        ...


@runtime_checkable
class UdevAPI(Protocol):
    """Optional stock pyudev calls needed by native consumption checks."""

    Devices: UdevDevices

    def Context(self) -> object:  # noqa: N802  # Exact stock library API.
        """Create an observer context without publishing metadata."""
        ...


class HotkeysGenerator(Protocol):
    """Stock configgen's authoritative shortcut declaration."""

    def getHotkeysContext(self) -> dict[str, object]:  # noqa: N802  # Exact stock library API.
        """Return the stock shortcut context, never a project replacement."""
        ...


@runtime_checkable
class DuckstationGeneratorAPI(Protocol):
    """Stock firmware lookup and shortcut generator used by the Qt backend."""

    bios_lists: object

    def find_bios(self, lists: object) -> Mapping[str, str]:
        """Return stock-recognized firmware names without copying content."""
        ...

    def DuckstationGenerator(self) -> HotkeysGenerator:  # noqa: N802  # Exact stock library API.
        """Construct the unchanged stock shortcut generator."""
        ...


@runtime_checkable
class XemuGeneratorAPI(Protocol):
    """Stock xemu shortcut declaration."""

    def XemuGenerator(self) -> HotkeysGenerator:  # noqa: N802  # Exact stock library API.
        """Construct the unchanged stock generator."""
        ...


@runtime_checkable
class LibretroGeneratorAPI(Protocol):
    """Stock RetroArch shortcut declaration."""

    def LibretroGenerator(self) -> HotkeysGenerator:  # noqa: N802  # Exact stock library API.
        """Construct the unchanged stock generator."""
        ...


def _hotkeys(path: Path) -> dict[str, object]:
    """Read a stock context as typed JSON without preserving private text."""
    return _record(json.loads(path.read_text(encoding="utf-8")))


def _stock_sources(probe: Probe) -> list[dict[str, object]]:
    """Validate transport sources before reading producer identities."""
    return _records(probe.status().get("sources", []))


def _exit_binding(context: dict[str, object]) -> object:
    """Read the stock exit action only after validating its keys object."""
    return _record(context["keys"]).get("exit")


def _validate_exit_context(
    observed: dict[str, object], expected: dict[str, object], backend: str
) -> None:
    """Keep all backends on the unchanged stock generator's exit action."""
    require(
        observed["name"] == expected["name"]
        and _exit_binding(observed) == _exit_binding(expected),
        "Unchanged stock generator exit context missing",
    )
    if backend in ("duckstation", "xemu"):
        require(
            _exit_binding(observed) == ["KEY_LEFTALT", "KEY_F4"],
            "Unchanged stock standalone exit binding missing",
        )
    if backend == "xemu":
        require(observed["name"] == "xemu", "Unchanged stock xemu exit context missing")


def _optional_record(value: object) -> dict[str, object] | None:
    """Keep absent optional diagnostics absent instead of inventing evidence."""
    return None if value is None else _record(value)


def _opened_input_devices(pid: int) -> set[tuple[int, int]]:
    """Observe exact opened Linux input device numbers for a pinned process."""
    opened: set[tuple[int, int]] = set()
    for path in Path(f"/proc/{pid}/fd").iterdir():
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        if stat.S_ISCHR(info.st_mode) and os.major(info.st_rdev) == LINUX_INPUT_MAJOR:
            opened.add((os.major(info.st_rdev), os.minor(info.st_rdev)))
    return opened


def _process_environment(pid: int, selected: Sequence[bytes]) -> dict[bytes, bytes]:
    """Read bounded selected stock fields; never retain other environment bytes."""
    with Path(f"/proc/{pid}/environ").open("rb") as stream:
        raw = stream.read(262145)
    require(
        len(raw) <= MAX_ENVIRONMENT_BYTES, "Native process environment exceeds limit"
    )
    environment: dict[bytes, bytes] = {}
    for entry in raw.split(b"\0"):
        key, separator, value = entry.partition(b"=")
        if separator and key in selected:
            require(key not in environment, "Duplicate native stock environment")
            environment[key] = value
    return environment


def _stock_evdev() -> EvdevAPI:
    """Load stock evdev only when creating a native controller."""
    module = importlib.import_module("evdev")
    if not isinstance(module, EvdevAPI):
        message = "Stock evdev contract unavailable"
        raise ProbeError(message)
    return module


def _stock_sdl() -> SDLAPI:
    """Load stock SDL2 bindings without borrowing host libraries."""
    module = importlib.import_module("sdl2")
    if not isinstance(module, SDLAPI):
        message = "Stock SDL contract unavailable"
        raise ProbeError(message)
    return module


def _stock_udev() -> UdevAPI:
    """Load the stock read-only device classification observer."""
    module = importlib.import_module("pyudev")
    if not isinstance(module, UdevAPI):
        message = "Stock udev contract unavailable"
        raise ProbeError(message)
    return module


def _stock_duckstation_generator() -> DuckstationGeneratorAPI:
    """Load stock PS1 firmware and shortcut declarations without replacing them."""
    module = importlib.import_module(
        "configgen.generators.duckstation.duckstationGenerator"
    )
    if not isinstance(module, DuckstationGeneratorAPI):
        message = "Stock DuckStation generator contract unavailable"
        raise ProbeError(message)
    return module


def _stock_xemu_generator() -> XemuGeneratorAPI:
    """Load the stock Xbox shortcut declaration."""
    module = importlib.import_module("configgen.generators.xemu.xemuGenerator")
    if not isinstance(module, XemuGeneratorAPI):
        message = "Stock xemu generator contract unavailable"
        raise ProbeError(message)
    return module


def _stock_libretro_generator() -> LibretroGeneratorAPI:
    """Load the stock RetroArch shortcut declaration."""
    module = importlib.import_module("configgen.generators.libretro.libretroGenerator")
    if not isinstance(module, LibretroGeneratorAPI):
        message = "Stock libretro generator contract unavailable"
        raise ProbeError(message)
    return module


def _suite_profile() -> ET.Element | None:
    """Read only the suite-generated controller XML in the disposable home."""
    root = ET.parse(PROFILE)  # noqa: S314  # Fixed suite-owned generated XML, not media.
    return root.getroot().find("inputConfig")


def _profile_button(profile: ET.Element | None, name: str) -> str:
    """Read a required stock-generated button binding with explicit failure."""
    if profile is None:
        message = "Stock controller profile missing"
        raise ProbeError(message)
    item = profile.find(f"input[@name='{name}']")
    if item is None:
        message = "Stock controller button missing"
        raise ProbeError(message)
    return _text(item.get("id"))


class CoreInfo(ctypes.Structure):
    """The stable libretro retro_system_info ABI, queried without retro_init."""

    _fields_: ClassVar["_StructureFields"] = [
        ("library_name", ctypes.c_char_p),
        ("library_version", ctypes.c_char_p),
        ("valid_extensions", ctypes.c_char_p),
        ("need_fullpath", ctypes.c_bool),
        ("block_extract", ctypes.c_bool),
    ]
    # ctypes' metaclass creates and initializes these native field descriptors.
    library_name: bytes | None  # pyright: ignore[reportUninitializedInstanceVariable]
    library_version: bytes | None  # pyright: ignore[reportUninitializedInstanceVariable]


def parse_retroarch_version(metadata: str) -> str:
    """Extract one stock ``Version:`` record, never compiler or build-date numbers.

    Args:
        metadata: Captured output from the packaged RetroArch ``--version``.

    Returns:
        The numeric RetroArch version without its build date.

    Raises:
        ProbeError: If the version record is missing, malformed or duplicated.
    """
    records = [line for line in metadata.splitlines() if line.startswith("Version:")]
    require(len(records) == 1, "Actual RetroArch version metadata missing or ambiguous")
    version = re.fullmatch(
        r"Version: ([0-9]+\.[0-9]+\.[0-9]+) "
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"(?:[1-9]|[12][0-9]|3[01]) [0-9]{4}",
        records[0],
    )
    if version is None:
        message = "Actual RetroArch version metadata malformed"
        raise ProbeError(message)
    return version.group(1)


def backend_versions(case: EmulatorCase) -> dict[str, str]:
    """Read stock metadata only; this never launches content or supplies exit proof."""
    metadata = subprocess.run(
        ["/usr/bin/retroarch", "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    version = parse_retroarch_version(metadata.stdout + "\n" + metadata.stderr)
    core = ctypes.CDLL(case.core_path)
    core.retro_get_system_info.argtypes = [ctypes.POINTER(CoreInfo)]
    core.retro_get_system_info.restype = None
    info = CoreInfo()
    core.retro_get_system_info(ctypes.byref(info))
    name = info.library_name.decode("ascii") if info.library_name else ""
    core_version = info.library_version.decode("ascii") if info.library_version else ""
    require(name == case.library, "Actual core library identity differs")
    require(
        re.fullmatch(r"[A-Za-z0-9 ._+()/-]{1,80}", core_version),
        "Actual core version metadata missing",
    )
    return {
        "retroarch_version": version,
        "core_library": name,
        "core_version": core_version,
    }


def parse_duckstation_version(output: str, exit_code: int) -> dict[str, object]:
    """Select one complete version record without retaining surrounding diagnostics.

    The pinned Qt parser returns EXIT_FAILURE for informational mode.
    Package-source provenance never fills missing runtime observations.

    Args:
        output: Captured streams separated by a newline at their boundary.
        exit_code: Observed informational command status, which must be one.

    Returns:
        The safe version record and its tag/branch, including blank SCM fields.

    Raises:
        ProbeError: If the status differs or version records are absent,
            malformed or duplicated.
    """
    records = [
        line
        for line in output.splitlines()
        if line.lstrip().startswith("DuckStation Version")
    ]
    require(len(records) == 1, "Actual DuckStation metadata missing or ambiguous")
    match = re.fullmatch(
        r"DuckStation Version ([A-Za-z0-9._+-]{0,80}) \(([A-Za-z0-9._+-]{0,80})\)",
        records[0],
    )
    if exit_code != 1 or match is None:
        message = "Actual DuckStation metadata malformed"
        raise ProbeError(message)
    return {
        "argument": "-version",
        "exit_code": exit_code,
        "output": records[0],
        "tag": match[1],
        "branch": match[2],
    }


def duckstation_identity() -> dict[str, object]:
    """Observe installed Qt metadata without content, a display or firmware."""
    metadata = subprocess.run(
        ["/usr/bin/duckstation-qt", "-version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    return {
        "variant": "duckstation-qt",
        "executable": "/usr/bin/duckstation-qt",
        "executable_sha256": digest(Path("/usr/bin/duckstation-qt")),
        "reported_version": parse_duckstation_version(
            metadata.stdout + "\n" + metadata.stderr, metadata.returncode
        ),
        "package_source": dict(DUCKSTATION_PACKAGE_SOURCE),
    }


def parse_xemu_version(output: str, exit_code: int) -> dict[str, object]:
    """Select unique early xemu records, ignoring unrelated bounded diagnostics.

    A failed SDL startup can print these records too. Only successful completion
    of the separate informational helper supplies this metadata observation.
    """
    require(exit_code == 0, "Actual xemu metadata helper failed")
    require(len(output) <= MAX_METADATA_BYTES, "Actual xemu metadata exceeds limit")
    fields = {}
    patterns = {
        "xemu_version": r"[0-9]+\.[0-9]+\.[0-9]+",
        "xemu_commit": r"[a-f0-9]{40}",
        "xemu_date": r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"(?:[1-9]|[12][0-9]|3[01]) [0-9]{2}:[0-9]{2}:[0-9]{2} "
        r"(?:AM|PM) UTC [0-9]{4}",
    }
    for key, pattern in patterns.items():
        records = [
            line for line in output.splitlines() if line.lstrip().startswith(key)
        ]
        require(len(records) == 1, "Actual xemu metadata missing or ambiguous")
        match = re.fullmatch(key + ": (" + pattern + ")", records[0])
        if match is None:
            message = "Actual xemu metadata malformed"
            raise ProbeError(message)
        fields[key] = match[1]
    return {
        "argument": "-version",
        "exit_code": exit_code,
        "disposable_config": True,
        "version": fields["xemu_version"],
        "revision": fields["xemu_commit"],
        "date": fields["xemu_date"],
    }


def xemu_identity(directory: Path) -> dict[str, object]:
    """Run metadata before the game on this authenticated display and owned config.

    Startup saves settings even in informational mode. The private temporary
    directory prevents the helper from reading or overwriting the game config.
    Bounded private draining retains no raw diagnostics in collected evidence.
    """
    require(
        os.environ.get("DISPLAY") and os.environ.get("XAUTHORITY"),
        "Authenticated native X11 required for xemu metadata",
    )
    with tempfile.TemporaryDirectory(
        prefix="xemu-metadata-", dir=directory
    ) as temporary:
        child = subprocess.Popen(  # noqa: S603  # Fixed stock executable, owned config argv.
            [
                "/usr/bin/xemu",
                "-config_path",
                str(Path(temporary) / "xemu.toml"),
                "-version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if child.stdout is None:
            message = "Private xemu metadata pipe missing"
            raise ProbeError(message)
        output = PrivateOutput(child.stdout)
        try:
            code = child.wait(timeout=5)
            raw = output.read_complete(timeout=0.25)
            if raw is None:
                message = "Actual xemu metadata output incomplete"
                raise ProbeError(message)
            version = parse_xemu_version(raw.decode("utf-8", errors="replace"), code)
        finally:
            try:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=1)
            finally:
                output.close()
    return {
        "variant": "xemu",
        "executable": "/usr/bin/xemu",
        "executable_sha256": digest(Path("/usr/bin/xemu")),
        "reported_version": version,
        "package_source": dict(XEMU_PACKAGE_SOURCE),
    }


class SDL3GUID(ctypes.Structure):
    """SDL3 SDL_GUID, returned by value, not an SDL2 wrapper's guessed ABI."""

    _fields_: ClassVar["_StructureFields"] = [("data", ctypes.c_uint8 * 16)]


def _sdl3_library() -> ctypes.CDLL:
    """Declare the actual stock consumer's SDL3 ABI, including by-value GUIDs."""
    library = ctypes.CDLL(XEMU_SDL)
    library.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    library.SDL_InitSubSystem.restype = ctypes.c_bool
    library.SDL_Quit.argtypes = []
    library.SDL_Quit.restype = None
    library.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    library.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    library.SDL_GetGamepadPathForID.argtypes = [ctypes.c_uint32]
    library.SDL_GetGamepadPathForID.restype = ctypes.c_char_p
    library.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    library.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    library.SDL_GetJoystickGUIDForID.argtypes = [ctypes.c_uint32]
    library.SDL_GetJoystickGUIDForID.restype = SDL3GUID
    library.SDL_GUIDToString.argtypes = [SDL3GUID, ctypes.c_char_p, ctypes.c_int]
    library.SDL_GUIDToString.restype = None
    library.SDL_free.argtypes = [ctypes.c_void_p]
    library.SDL_free.restype = None
    return library


def sdl3_gamepad(device: int, mapping: str, name: str) -> dict[str, object]:
    """Observe SDL3's suite device and unambiguous GUID for stock port binding.

    The observer uses the consumer's effective mapping. The emulator's own
    mapped library and open pad FD are checked separately. This is not guest
    input evidence and does not inspect emulator private memory.
    """
    library = _sdl3_library()
    ids = None
    previous = os.environ.get("SDL_GAMECONTROLLERCONFIG")
    os.environ["SDL_GAMECONTROLLERCONFIG"] = mapping
    try:
        require(library.SDL_InitSubSystem(0x2000), "SDL3 gamepad initialization failed")
        count = ctypes.c_int()
        ids = library.SDL_GetGamepads(ctypes.byref(count))
        require(
            bool(ids) and 1 <= count.value <= SDL_MAX_GAMEPADS,
            "SDL3 gamepad topology unavailable",
        )
        matches = []
        guids = []
        for index in range(count.value):
            instance = ids[index]
            guid_buffer = ctypes.create_string_buffer(33)
            library.SDL_GUIDToString(
                library.SDL_GetJoystickGUIDForID(instance), guid_buffer, 33
            )
            guid = guid_buffer.value.decode("ascii")
            guids.append(guid)
            path = library.SDL_GetGamepadPathForID(instance)
            if path is None:
                continue
            info = Path(os.fsdecode(path)).stat()
            if stat.S_ISCHR(info.st_mode) and info.st_rdev == device:
                require(
                    library.SDL_GetGamepadNameForID(instance) == name.encode("utf-8"),
                    "SDL3 suite gamepad name differs",
                )
                matches.append(guid)
        require(len(matches) == 1, "SDL3 did not uniquely discover the suite pad")
        guid = matches[0]
        require(
            re.fullmatch(r"[a-f0-9]{32}", guid)
            and guid != "0" * 32
            and guids.count(guid) == 1,
            "SDL3 suite GUID is ambiguous",
        )
        expected_rows = [
            row for row in mapping.splitlines() if row.startswith(guid + ",")
        ]
        require(len(expected_rows) == 1, "Stock mapping does not select SDL3 GUID")
        return {
            "guid": guid,
            "discovered_gamepads": count.value,
            "matching_guid_gamepads": guids.count(guid),
            "suite_device_matched": True,
        }
    finally:
        if ids:
            library.SDL_free(ids)
        library.SDL_Quit()
        if previous is None:
            os.environ.pop("SDL_GAMECONTROLLERCONFIG", None)
        else:
            os.environ["SDL_GAMECONTROLLERCONFIG"] = previous


def sdl_mapping_bindings(mapping: str) -> dict[str, str]:
    """Extract unambiguous mapping fields without treating a GUID as SDL proof."""
    fields = mapping.split(",")
    require(len(fields) > SDL_MAPPING_PREFIX_FIELDS, "Stock SDL mapping malformed")
    bindings = {}
    for field in fields[2:]:
        key, separator, value = field.partition(":")
        if separator:
            require(key not in bindings, "Duplicate stock SDL mapping field")
            bindings[key] = value
    return bindings


def seed_xemu_hdd(userdata: Path, seed: Path) -> dict[str, object]:
    """Copy only the fingerprinted stock seed into fresh owned Xbox state.

    Writable directories must belong to the app on the userdata filesystem.
    Existing HDD/EEPROM/config files are refused, never adopted from a home.
    """
    require(userdata.resolve() == userdata, "Disposable userdata is symlinked")
    root = os.open(userdata, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directories: list[int] = []
    try:
        root_info = os.fstat(root)
        require(root_info.st_uid == os.getuid(), "Disposable userdata owner differs")
        for relative in ("saves/xbox", "system/configs/xemu", "system/cache"):
            parent = os.dup(root)
            try:
                for part in relative.split("/"):
                    with contextlib.suppress(FileExistsError):
                        os.mkdir(part, mode=0o700, dir_fd=parent)
                    child = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=parent,
                    )
                    os.close(parent)
                    parent = child
                    info = os.fstat(child)
                    require(
                        info.st_uid == os.getuid() and info.st_dev == root_info.st_dev,
                        "Xbox writable directory escaped owned userdata",
                    )
                directories.append(parent)
            finally:
                if parent not in directories:
                    os.close(parent)
        saves, configs, _ = directories
        for directory, name in (
            (saves, "xbox_hdd.qcow2"),
            (saves, "xemu_eeprom.bin"),
            (configs, "xemu.toml"),
        ):
            try:
                os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            message = "Xbox disposable state is not fresh"
            raise ProbeError(message)
        descriptor = os.open(seed, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            require(
                stat.S_ISREG(info.st_mode)
                and info.st_size == STOCK_XBOX_HDD_BYTES
                and info.st_uid == 0
                and not info.st_mode & 0o022
                and not os.access(seed, os.W_OK),
                "Stock Xbox HDD source is not protected",
            )
            require(
                hashlib.file_digest(source, "sha256").hexdigest() == XEMU_HDD_SHA256,
                "Stock Xbox HDD seed is not qualified",
            )
            source.seek(0)
            destination = os.open(
                "xbox_hdd.qcow2",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=saves,
            )
            with os.fdopen(destination, "wb") as target:
                copied = hashlib.sha256()
                while chunk := source.read(65536):
                    target.write(chunk)
                    copied.update(chunk)
                require(
                    copied.hexdigest() == XEMU_HDD_SHA256,
                    "Stock Xbox HDD changed while copying",
                )
                target_info = os.fstat(target.fileno())
            require(
                os.stat("xbox_hdd.qcow2", dir_fd=saves, follow_symlinks=False).st_ino
                == target_info.st_ino
                and target_info.st_uid == os.getuid(),
                "Disposable Xbox HDD identity changed",
            )
        require(
            userdata.stat().st_ino == root_info.st_ino,
            "Disposable userdata identity changed",
        )
        return {
            "status": "available",
            "route": "stock",
            "source_identity": XEMU_HDD_SHA256,
            "source_readonly": True,
            "use_disposition": XEMU_HDD_USE,
            "owned_copy": True,
        }
    finally:
        for directory in directories:
            os.close(directory)
        os.close(root)


class Clock:
    """Production monotonic clock assembled by the native diagnostic entry point."""

    def now(self) -> float:
        """Return monotonic seconds for shared exit deadlines."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Sleep for a bounded observation interval in seconds."""
        time.sleep(seconds)


def digest(path: Path) -> str:
    """Hash a required file without changing its content."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rendered_content(path: Path) -> bool:
    """Reject blank/uninitialized output, never use pixel changes as an oracle.

    This predicate is used only with a live active emulator and loaded exact
    core. It does not identify gameplay, title screens or client video.
    """
    # Pillow is a stock runtime dependency, not required by media-only consumers.
    from PIL import Image  # noqa: PLC0415

    with Image.open(path) as image:
        image.load()
        width, height = image.size
        if width < MIN_RENDER_WIDTH or height < MIN_RENDER_HEIGHT:
            return False
        # Ignore window borders and peripheral bezels. Content need not animate.
        center = image.crop((width // 4, height // 4, width * 3 // 4, height * 3 // 4))
        colors = center.convert("RGB").getcolors(maxcolors=16)
        return colors is None or len(colors) >= MIN_RENDER_COLORS


def loaded_object_observation(
    symbol: CFuncPtr,
    inventory_path: Path,  # Native symbol ABI.
) -> dict[str, object]:
    """Bind an actual function address to the inventoried file's mapped inode.

    Unexpected mapping names never leave the process. A version string or a
    library found on disk cannot establish loaded-object provenance.
    """
    address = ctypes.cast(symbol, ctypes.c_void_p).value
    if address is None:
        return {"status": "unavailable"}
    try:
        descriptor = os.open(inventory_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                return {"status": "unsafe"}
            with Path("/proc/self/maps").open("rb") as maps:
                raw = maps.read(1024 * 1024 + 1)
            if len(raw) > MAX_PROCFS_BYTES:
                return {"status": "oversize"}
            for line in raw.splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) < PROC_MAP_REQUIRED_FIELDS:
                    continue
                start, end = (int(value, 16) for value in fields[0].split(b"-"))
                major, minor = (int(value, 16) for value in fields[3].split(b":"))
                if (
                    start <= address < end
                    and b"x" in fields[1]
                    and os.makedev(major, minor) == info.st_dev
                    and int(fields[4]) == info.st_ino
                ):
                    return {
                        "status": "mapped",
                        "inventory_path": str(inventory_path),
                        "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                    }
    except OSError as error:
        return {"status": "unavailable", "errno": error.errno}
    return {"status": "different-object"}


class SDLDiscoveryMode:
    """Observe the stock discovery branch without changing hints or discovery.

    Only fixed SDL input-log categories survive. Restore the borrowed logger
    and its priority even when initialization fails; do not retain log bytes.
    """

    CALLBACK = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
    )
    MESSAGES: ClassVar[dict[bytes, str]] = {
        b"Using udev for joystick device discovery": "udev_selected",
        b"udev disabled by SDL_JOYSTICK_DISABLE_UDEV": "fallback_disabled",
        b"Container detected, disabling udev integration": "fallback_sandbox",
        b"udev init failed, disabling udev integration": "fallback_init_failed",
    }

    def __init__(self, library: ctypes.CDLL) -> None:
        """Borrow the current SDL logger and replace it until explicit close."""
        self.library = library
        self.observed: dict[str, bool] = {}
        self.original = self.CALLBACK()
        self.userdata = ctypes.c_void_p()
        library.SDL_LogGetOutputFunction.argtypes = [
            ctypes.POINTER(self.CALLBACK),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.SDL_LogGetOutputFunction.restype = None
        library.SDL_LogSetOutputFunction.argtypes = [self.CALLBACK, ctypes.c_void_p]
        library.SDL_LogSetOutputFunction.restype = None
        library.SDL_LogGetPriority.argtypes = [ctypes.c_int]
        library.SDL_LogGetPriority.restype = ctypes.c_int
        library.SDL_LogSetPriority.argtypes = [ctypes.c_int, ctypes.c_int]
        library.SDL_LogSetPriority.restype = None
        library.SDL_LogGetOutputFunction(
            ctypes.byref(self.original), ctypes.byref(self.userdata)
        )
        self.priority = int(library.SDL_LogGetPriority(7))
        self.callback = self.CALLBACK(self.observe)
        library.SDL_LogSetOutputFunction(self.callback, None)
        library.SDL_LogSetPriority(7, min(self.priority, 2))

    def observe(
        self, _userdata: int | None, category: int, priority: int, message: bytes | None
    ) -> None:
        """Classify only exact upstream messages, forwarding prior log behavior."""
        if (
            category == SDL_LOG_INPUT_CATEGORY
            and priority == SDL_LOG_DEBUG_PRIORITY
            and message is not None
            and message in self.MESSAGES
        ):
            self.observed[self.MESSAGES[message]] = True
        if self.original and (
            category != SDL_LOG_INPUT_CATEGORY or priority >= self.priority
        ):
            self.original(self.userdata, category, priority, message)

    def close(self) -> None:
        """Restore the borrowed SDL logger before dropping callback references."""
        self.library.SDL_LogSetPriority(7, self.priority)
        self.library.SDL_LogSetOutputFunction(self.original, self.userdata)


class JoystickDiscoveryAPI(Protocol):
    """Borrowed stock SDL discovery calls, without controller overrides."""

    def SDL_JoystickUpdate(self) -> None:  # noqa: N802  # Exact stock library API.
        """Refresh joystick discovery through the stock SDL implementation."""
        ...

    def SDL_NumJoysticks(self) -> int:  # noqa: N802  # Exact stock library API.
        """Return the current number of stock-discovered joysticks."""
        ...

    def SDL_JoystickPathForIndex(self, index: int) -> bytes | None:  # noqa: N802  # Exact stock library API.
        """Return an ephemeral event-node path, or no path."""
        ...

    def SDL_GetError(self) -> bytes | None:  # noqa: N802  # Exact stock library API.
        """Return ephemeral error bytes without retaining their contents."""
        ...


class SDLGamepadDiscovery:
    """Match the actual SDL device while retaining only first/latest counters.

    Paths, names and SDL error bytes are never retained. Evidence is diagnostic,
    not a substitute for opening and qualifying the discovered controller.
    """

    def __init__(self, sdl: JoystickDiscoveryAPI, device: int) -> None:
        """Borrow discovery calls and bind only the suite's kernel device number."""
        self.sdl, self.device = sdl, device
        self.evidence: dict[str, object] = {
            "polls": 0,
            "first": None,
            "latest": None,
        }
        self.polls = 0

    def poll(self) -> int | None:
        """Return SDL index plus one only on an exact character-device match.

        Existing filesystem failures still raise after recording numeric errno;
        a diagnostic must not turn an inaccessible candidate into success.
        """
        self.polls += 1
        observation: dict[str, object] = {
            "joysticks": None,
            "checked": 0,
            "pathless": 0,
            "matching_index": None,
            "path_stat_errno": None,
        }
        checked, pathless = 0, 0
        try:
            self.sdl.SDL_JoystickUpdate()
            count = self.sdl.SDL_NumJoysticks()
            observation["joysticks"] = count
            for index in range(count):
                node = self.sdl.SDL_JoystickPathForIndex(index)
                checked += 1
                if not node:
                    pathless += 1
                    continue
                info = Path(os.fsdecode(node)).stat()
                if stat.S_ISCHR(info.st_mode) and info.st_rdev == self.device:
                    observation["matching_index"] = index
                    return index + 1
        except OSError as error:
            observation["path_stat_errno"] = error.errno
            raise
        else:
            return None
        finally:
            observation.update(
                checked=checked,
                pathless=pathless,
                sdl_error_present=bool(self.sdl.SDL_GetError()),
            )
            self.evidence["polls"] = self.polls
            if self.evidence["first"] is None:
                self.evidence["first"] = observation
            self.evidence["latest"] = observation


def gamepad_device_observation(
    node: Path, device: int, udev_data: Path = Path("/run/udev/data")
) -> dict[str, object]:
    """Read only the suite node and its bounded, no-follow udev record.

    Classification values are reduced to fixed categories. Missing, unsafe or
    unreadable metadata remains an observation, never publication authority.
    """
    result: dict[str, object] = {}
    try:
        descriptor = os.open(
            node, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            info = os.fstat(descriptor)
            result["node"] = {
                "status": "opened",
                "identity_matches": stat.S_ISCHR(info.st_mode)
                and info.st_rdev == device,
            }
        finally:
            os.close(descriptor)
    except OSError as error:
        result["node"] = {"status": "unavailable", "errno": error.errno}
    record = udev_data / f"c{os.major(device)}:{os.minor(device)}"
    try:
        descriptor = os.open(
            record, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                result["udev"] = {"status": "unsafe"}
                return result
            raw = os.read(descriptor, 4097)
        finally:
            os.close(descriptor)
    except FileNotFoundError:
        result["udev"] = {"status": "missing"}
        return result
    except OSError as error:
        result["udev"] = {"status": "unavailable", "errno": error.errno}
        return result
    if len(raw) > MAX_UDEV_RECORD_BYTES:
        result["udev"] = {"status": "oversize"}
        return result
    properties = {}
    for key in (
        "ID_INPUT",
        "ID_INPUT_JOYSTICK",
        "ID_INPUT_KEY",
        "ID_INPUT_KEYBOARD",
        "ID_INPUT_MOUSE",
        "ID_INPUT_ACCELEROMETER",
        "ID_INPUT_TOUCHSCREEN",
        "ID_CLASS",
    ):
        prefix = b"E:" + key.encode("ascii") + b"="
        values = [
            line[len(prefix) :] for line in raw.splitlines() if line.startswith(prefix)
        ]
        if not values:
            value = "absent"
        elif len(values) != 1:
            value = "ambiguous"
        elif key == "ID_CLASS" and values[0] == b"joystick":
            value = "joystick"
        else:
            value = "1" if values[0] == b"1" else "other"
        properties[key] = value
    result["udev"] = {"status": "read", "properties": properties}
    return result


def _process_leader_stat(pid: int) -> tuple[str, int]:
    """Read bounded leader state/start ticks without treating Z as group death.

    This is only a post-chord fallback for a still-live pinned pidfd. The normal
    process_stat contract, including zombie rejection, remains unchanged.

    Args:
        pid: Exact PID already bound to the emulator's borrowed pidfd.

    Returns:
        The actual leader state and its procfs start ticks.

    Raises:
        OSError: If procfs metadata cannot be read.
        ProbeError: If metadata is oversized, malformed or names another PID.
    """
    with Path(f"/proc/{pid}/stat").open("rb") as stream:
        raw = stream.read(4097)
    require(
        len(raw) <= MAX_LEADER_STAT_BYTES, "Pinned emulator leader metadata oversized"
    )
    leader, separator, tail = raw.rpartition(b") ")
    fields = tail.split()
    require(
        separator
        and leader.startswith(f"{pid} (".encode("ascii"))
        and len(fields) >= PROC_STAT_REQUIRED_FIELDS
        and len(fields[0]) == 1
        and fields[0] in b"RSDZTtXxKWPI"
        and fields[1].isdigit()
        and fields[17].isdigit()
        and fields[19].isdigit(),
        "Pinned emulator leader metadata malformed or PID changed",
    )
    start = int(fields[19])
    require(
        start > 0 and int(fields[17]) > 0,
        "Pinned emulator leader start/thread metadata invalid",
    )
    return fields[0].decode("ascii"), start


def _launch_exception_observation(status: str) -> dict[str, object]:
    """Return a text-free startup diagnostic with no selected exception."""
    return {
        "status": status,
        "reason": None,
        "exception": None,
        "errno": None,
        "frames": [],
        "unknown_frames": False,
        "frames_truncated": False,
        "additional_exceptions": False,
    }


_STOCK_TRACEBACK_FRAMES: dict[bytes, tuple[str, int]] = {
    (
        b'  File "/usr/lib/python3.12/site-packages/configgen/emulatorlauncher.py", '
        b"line 660, in launch"
    ): ("stock-launch-main", 660),
    (
        b'  File "/usr/lib/python3.12/site-packages/configgen/generators/'
        b'duckstation/duckstationGenerator.py", line 436, in generate'
    ): ("stock-duckstation-controller-db", 436),
}
_STOCK_EXCEPTION_CATEGORIES = {
    name.encode("ascii"): name
    for name in (
        "PermissionError",
        "FileNotFoundError",
        "OSError",
        "ValueError",
        "RuntimeError",
        "TypeError",
        "KeyError",
    )
}


class _LaunchTraceback:
    """Reduce the traceback grammar without retaining private source or messages."""

    def __init__(self) -> None:
        """Initialize one isolated exception envelope's bounded public evidence."""
        self.frames: list[list[str | int]] = []
        self.unknown_frames = False
        self.frames_truncated = False
        self.saw_frame = False
        self.category: str | None = None
        self.number: int | None = None

    def consume(self, line: bytes) -> str | None:
        """Return a fixed rejection reason, retaining only allowlisted metadata."""
        if self.category is not None:
            return "malformed-envelope" if line else None
        if re.fullmatch(rb'  File "[^"\r\n]+", line [1-9][0-9]*, in [^\r\n]+', line):
            self.saw_frame = True
            public = _STOCK_TRACEBACK_FRAMES.get(line)
            if public is None:
                self.unknown_frames = True
            elif len(self.frames) < MAX_EXCEPTION_FRAMES:
                self.frames.append(list(public))
            else:
                self.frames_truncated = True
            return None
        if line.startswith(b"    ") and self.saw_frame:
            # Python's source echoes and caret annotations are never retained.
            return None
        terminal = re.fullmatch(rb"([A-Za-z_][A-Za-z_0-9]*):[^\r\n]*", line)
        if terminal is None or not self.saw_frame:
            return "malformed-envelope"
        self.category = _STOCK_EXCEPTION_CATEGORIES.get(terminal[1])
        if self.category is None:
            return "unknown-exception"
        errno = re.match(rb"[A-Za-z_][A-Za-z_0-9]*: \[Errno (-?[0-9]{1,5})\] ", line)
        if errno is not None:
            candidate = int(errno[1])
            if 1 <= candidate <= MAX_ERRNO:
                self.number = candidate
        return None


def _reduce_launch_traceback(
    envelope: bytes, result: dict[str, object]
) -> dict[str, object]:
    """Validate one complete bounded traceback before publishing its metadata."""
    lines = envelope.split(b"\n")
    if len(lines) > MAX_EXCEPTION_LINES:
        result["reason"] = "oversized-envelope"
        return result
    if (
        any(
            line
            in (
                b"During handling of the above exception, another exception occurred:",
                b"The above exception was the direct cause of the following exception:",
            )
            for line in lines
        )
        or lines.count(b"Traceback (most recent call last):") > 1
    ):
        result.update(reason="additional-exceptions", additional_exceptions=True)
        return result
    result["reason"] = "malformed-envelope"
    if (
        not envelope.endswith(b"\n")
        or lines[0] != b"Traceback (most recent call last):"
    ):
        return result
    traceback = _LaunchTraceback()
    for line in lines[1:]:
        reason = traceback.consume(line)
        if reason is not None:
            result["reason"] = reason
            return result
    if traceback.category is not None:
        result.update(
            status="recognized",
            reason=None,
            exception=traceback.category,
            errno=traceback.number,
            frames=traceback.frames,
            unknown_frames=traceback.unknown_frames,
            frames_truncated=traceback.frames_truncated,
        )
    return result


def stock_launch_failure(output: bytes) -> dict[str, object]:
    """Reduce the first exact stock configgen exception logger envelope.

    Args:
        output: Complete bytes from the existing bounded private launcher reader.

    Returns:
        Fixed diagnostic fields only, never messages, source echoes or paths.
        Public frame roles match the pinned stock locations documented by the
        startup fixtures. Even exact log matches are untrusted observations,
        not authenticated provenance or launch/exit acceptance evidence.
    """
    timestamp = rb"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}"
    header = re.compile(
        rb"^" + timestamp + rb" ERROR \(emulatorlauncher\.py:(?:662|668)\):"
        rb"launch configgen exception: \n",
        re.MULTILINE,
    )
    result = _launch_exception_observation("not-found")
    first = header.search(output)
    if first is None:
        return result
    result["status"] = "rejected"
    if header.search(output, first.end()) is not None:
        result.update(reason="additional-exceptions", additional_exceptions=True)
        return result
    # Only the selected logger record is bounded, not preceding unrelated output.
    next_record = re.compile(
        rb"^"
        + timestamp
        + rb" (?:DEBUG|INFO|WARNING|ERROR|CRITICAL) \([^\r\n]+\):[^\r\n ]+ ",
        re.MULTILINE,
    ).search(output, first.end())
    end = next_record.start() if next_record else len(output)
    if end - first.start() > MAX_EXCEPTION_BYTES:
        result["reason"] = "oversized-envelope"
        return result
    return _reduce_launch_traceback(output[first.end() : end], result)


def _startup_window(output: bytes, result: dict[str, object]) -> bytes:
    """Bound stderr scanning and discard any prefix cut through a private line."""
    start = max(0, len(output) - 65536)
    window = output[start:]
    cut_line = start > 0 and output[start - 1] != NEWLINE_BYTE
    result.update(
        bytes_scanned=len(window),
        truncated=start > 0,
        partial_line=cut_line or not window.endswith(b"\n"),
    )
    if cut_line:
        newline = window.find(b"\n")
        window = window[newline + 1 :] if newline != -1 else b""
    return window


def _reduce_startup_roles(
    window: bytes,
    patterns: Sequence[tuple[bytes, str]],
    result: dict[str, object],
) -> dict[str, object]:
    """Select one stock stderr record and retain ordered allowlisted roles only."""
    timestamp = rb"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}"
    stderr_header = re.compile(
        timestamp + rb" ERROR \(emulatorlauncher\.py:596\):runCommand "
    )
    # Stock source filenames contain no closing parenthesis. Excluding it keeps
    # one envelope delimiter candidate, even in malformed private payload lines.
    logger_header = re.compile(
        timestamp + rb" (?:DEBUG|INFO|WARNING|ERROR|CRITICAL) \([^\r\n)]+\):[^\r\n ]+ "
    )
    roles: list[str] = []
    lines_scanned = 0
    in_stderr = False
    position = 0
    while position < len(window):
        newline = window.find(b"\n", position)
        if newline == -1:
            break
        line = window[position:newline]
        position = newline + 1
        if in_stderr:
            if logger_header.match(line) is not None:
                break
        else:
            header = stderr_header.match(line)
            if header is None:
                continue
            in_stderr = True
            line = line[header.end() :]
        if lines_scanned == MAX_STARTUP_LINES:
            result["truncated"] = True
            break
        lines_scanned += 1
        for pattern, role in patterns:
            if re.fullmatch(pattern, line) is not None:
                if role not in roles:
                    roles.append(role)
                break
    result.update(
        status="matched" if roles else "unmatched",
        roles=roles,
        lines_scanned=lines_scanned,
    )
    return result


def duckstation_startup_failure(output: bytes | None) -> dict[str, object]:
    """Reduce one bounded stock stderr record to fixed public failure roles.

    Args:
        output: Ephemeral bytes from the owned launcher reader, or None when
            unavailable. Only the latest 64 KiB and 256 complete selected
            payload lines are examined. A cut first line is discarded.

    Returns:
        Fixed roles, counts and availability/completeness flags, never captured
        values, text or hashes. Exact source-shaped matches remain untrusted
        observations, not authenticated causes or lifecycle acceptance. In
        particular, the required-SBI warning does not prove that boot stopped.
    """
    result: dict[str, object] = {
        "status": "unavailable" if output is None else "unmatched",
        "roles": [],
        "bytes_scanned": 0,
        "lines_scanned": 0,
        "truncated": False,
        "partial_line": False,
    }
    if output is None or not output:
        return result
    window = _startup_window(output, result)
    # fmt's {:10.4f} pads nonnegative seconds to a minimum width of ten.
    console_time = (
        rb"(?:\[(?:    [0-9]|   [1-9][0-9]|  [1-9][0-9]{2}| "
        rb"[1-9][0-9]{3}|[1-9][0-9]{4,})\.[0-9]{4}\] )?"
    )
    # These Error contents reach stderr only inside Host::CreateGPUDevice's
    # ERROR_LOG. More specific nested failures precede its generic envelope.
    graphics_errors = (
        (
            (
                rb"CreateGPUDevice\): Failed to create GPU device: "
                rb"eglInitialize\(\) failed: [0-9]+ \(0x[0-9A-F]+\)"
            ),
            "duckstation-egl-initialize-failed",
        ),
        (
            (
                rb"CreateGPUDevice\): Failed to create GPU device: "
                rb"eglGetDisplay\(\) failed: [0-9]+ \(0x[0-9A-F]+\)"
            ),
            "duckstation-egl-display-failed",
        ),
        (
            (
                rb"CreateGPUDevice\): Failed to create GPU device: "
                rb"Loading GLAD EGL functions failed"
            ),
            "duckstation-glad-egl-load-failed",
        ),
        (
            (
                rb"CreateGPUDevice\): Failed to create GPU device: "
                rb"Failed to load (?:GL|GLES) functions for GLAD"
            ),
            "duckstation-glad-gl-load-failed",
        ),
        (
            (
                rb"CreateGPUDevice\): Failed to create GPU device: "
                rb"Failed to create any context versions"
            ),
            "duckstation-gl-context-versions-exhausted",
        ),
        (
            rb"CreateGPUDevice\): Failed to create GPU device: [^\r\n]*",
            "duckstation-gpu-device-create-failed",
        ),
        (
            rb"LoadEGL\): Failed to load EGL: [^\r\n]*",
            "duckstation-egl-load-failed",
        ),
        (
            rb"CreateDevice\): Failed to create any GL context",
            "duckstation-gl-context-create-failed",
        ),
        (
            (
                rb"CreateContext\): (?:eglChooseConfig\(\) failed: 0x[0-9a-f]+|"
                rb"eglBindAPI\(EGL_OPENGL(?:_ES)?_API\) failed|"
                rb"eglCreateContext\(\) failed: 0x[0-9a-f]+)"
            ),
            "duckstation-egl-context-attempt-failed",
        ),
        (
            rb"CreateContextAndSurface\): eglMakeCurrent\(\) failed: 0x[0-9A-F]+",
            "duckstation-egl-make-current-failed",
        ),
        (
            (
                rb"TryGetPlatformDisplay\): "
                rb"eglGetPlatformDisplayEXT\(\) failed: [0-9]+ \(0x[0-9A-F]+\)"
            ),
            "duckstation-egl-platform-display-failed",
        ),
    )
    # Our post-configgen wrapper can refuse before the stock binary executes.
    # Admit only its fixed public messages, never arbitrary VisualError text.
    # These observations diagnose refusal; they do not establish its native cause.
    wrapper_errors = (
        (
            b"Cannot authenticate to the current X11 display",
            "duckstation-wrapper-x11-authentication-failed",
        ),
        (
            b"Cannot initialize EGL on the current X11 display",
            "duckstation-wrapper-egl-initialize-failed",
        ),
        (
            b"EGL config enumeration failed",
            "duckstation-wrapper-egl-enumeration-failed",
        ),
        (
            b"EGL config count exceeds discovery bound",
            "duckstation-wrapper-egl-count-exceeded",
        ),
        (
            b"EGL config enumeration changed beyond its bound",
            "duckstation-wrapper-egl-enumeration-changed",
        ),
        (
            b"EGL config attribute unavailable",
            "duckstation-wrapper-egl-attribute-missing",
        ),
        (
            b"Cannot release the discovery EGL context",
            "duckstation-wrapper-egl-context-release-failed",
        ),
        (
            b"Chosen EGL config has no native X11 visual",
            "duckstation-wrapper-egl-visual-missing",
        ),
        (
            b"Chosen EGL visual is not valid on the current X11 screen",
            "duckstation-wrapper-x11-visual-invalid",
        ),
        (
            b"No supported DuckStation EGL context/config for this X11 session",
            "duckstation-wrapper-egl-context-unavailable",
        ),
        (
            b"Cannot load or query live EGL/X11 for automatic visual discovery",
            "duckstation-wrapper-discovery-unavailable",
        ),
        (
            b"Discovery returned an invalid native X11 visual",
            "duckstation-wrapper-discovery-result-invalid",
        ),
    )
    patterns = (
        (
            rb"qt\.qpa\.xcb: could not connect to display [^\r\n]*",
            "qt-xcb-display-connect-failed",
        ),
        (
            (
                rb'qt\.qpa\.plugin: Could not load the Qt platform plugin "[^"\r\n]*" '
                rb'in "[^"\r\n]*" even though it was found\.'
            ),
            "qt-platform-plugin-load-failed",
        ),
        (
            (
                rb"This application failed to start because no Qt platform plugin "
                rb"could be initialized\. Reinstalling the application "
                rb"may fix this problem\."
            ),
            "qt-platform-initialization-failed",
        ),
        (
            console_time
            + (
                rb"(\x1b\[1;31m)?E\(CreateGPU\): "
                rb"Failed to create fallback software renderer\.(?(1)\x1b\[0m)"
            ),
            "duckstation-software-renderer-create-failed",
        ),
        (
            console_time
            + (
                rb"(\x1b\[1;33m)?W\(CheckForSBIFile\): "
                # Check the delimiter separately to avoid quadratic backtracking
                # through private fields containing many opening parentheses.
                rb"SBI file missing but required for (?=[^\r\n]+ \()"
                rb"[^\r\n]+\)(?(1)\x1b\[0m)"
            ),
            "duckstation-required-sbi-missing",
        ),
        *(
            (
                console_time + rb"(\x1b\[1;31m)?E\(" + message + rb"(?(1)\x1b\[0m)",
                role,
            )
            for message, role in graphics_errors
        ),
        (
            rb"\*{15} Unhandled SIGSEGV at (?:0x[0-9a-f]+|\(nil\)) \*{15}",
            "duckstation-crash-handler-sigsegv",
        ),
        (
            rb"\*{15} Unhandled SIGBUS at (?:0x[0-9a-f]+|\(nil\)) \*{15}",
            "duckstation-crash-handler-sigbus",
        ),
        (
            rb"Aborting application\.",
            "duckstation-crash-handler-aborting",
        ),
        *(
            (
                rb"DuckStation compatibility wrapper: OpenGL launch refused: "
                + re.escape(message)
                + rb"\. No uncorrected or renderer fallback was attempted\.",
                role,
            )
            for message, role in wrapper_errors
        ),
        (
            (
                rb"DuckStation compatibility wrapper: launch refused\. "
                rb"Cannot read final generated GPU/Renderer or exec the absolute "
                rb"stock emulator\. No fallback was attempted\."
            ),
            "duckstation-wrapper-launch-refused",
        ),
    )
    return _reduce_startup_roles(window, patterns, result)


class EmulatorProbe:
    """Own one stock launch, its synthetic pad and its pinned evidence lifecycle.

    Media roots and selection inputs are supplied by the inspected coordinator.
    Construction has no native side effects; ``close`` releases only resources
    this instance created, including after partial startup.
    """

    def __init__(  # noqa: PLR0913  # Preserve independently configured native fixture inputs.
        self,
        directory: Path,
        control: str = "none",
        *,
        roms_view: Path = ROMS,
        catalog_path: Path = CATALOG,
        reproduction: Path = Path("/home/retro/.native-control/selection.json"),
        reproduce_required: bool = False,
        case: str = "nes-fceumm",
    ) -> None:
        """Configure an owned attempt without importing stock native libraries."""
        require(control in CONTROLS, "Unknown emulator negative control")
        self.directory, self.control = directory, control
        self.case = emulator_case(case)
        if self.case.backend == "libretro":
            self.core_path = Path(self.case.core_path)
            self.info_path = Path(self.case.info_path)
        self.roms_view, self.catalog_path, self.reproduction = (
            roms_view,
            catalog_path,
            reproduction,
        )
        self.reproduce_required = reproduce_required
        self.pad: NativePad | None = None
        self.sdl: SDLAPI | None = None
        self.evdev: EvdevAPI
        self.definition: GamepadDefinition
        self.joystick: object | None = None
        self.pad_node: str
        self.pad_device: int
        self.pad_index: int
        self.pad_source: dict[str, object]
        self.guid: str
        self.bios_files: dict[str, tuple[str, str]]
        self.xemu_topology: dict[str, object] | None = None
        self.launcher: subprocess.Popen[bytes] | None = None
        self.launcher_output: PrivateOutput | None = None
        self.launcher_start: int | None = None
        self.emulator_termination: str | None = None
        self.termination_observed = False
        self.emulator_fd: int | None = None
        self.duckstation_log_fd: int | None = None
        self.emulator_identity: ProcessIdentity | None = None
        self.final_fd: int | None = None
        self.final_identity: tuple[int, int, str, str, int] | None = None
        self.desktop: Desktop | None = None
        self.selection: MediaSelection
        self.profile_hash: str | None = None
        self.profile_seeded = False
        self.forced = False
        self.captures: dict[str, dict[str, object]] = {}
        self.integrity = Probe()
        self.process_observation_failure: dict[str, object] | None = None
        self.boundary = "startup"
        self.result: dict[str, object] = {
            "schema": 1,
            "status": "failed",
            "case": self.case.identifier,
            "system": self.case.system,
            "backend": self.case.backend,
            "core": self.case.core,
            "assertions": ASSERTIONS,
            "negative_control": control,
            "renderer_requested": self.case.renderer or None,
            "native_device_consumption": {"status": "untested"},
            "errors": [],
            "captures": [],
        }

    def pinned_emulator(self) -> ProcessIdentity:
        """Require a process identity previously bound to the owned pidfd."""
        if self.emulator_identity is None:
            message = "Pinned emulator identity missing"
            raise ProbeError(message)
        return self.emulator_identity

    def emulator_descriptor(self) -> int:
        """Borrow the owned pidfd, refusing an unpinned process."""
        if self.emulator_fd is None:
            message = "Pinned emulator descriptor missing"
            raise ProbeError(message)
        return self.emulator_fd

    def active_launcher(self) -> subprocess.Popen[bytes]:
        """Borrow the launcher created by this attempt, never find one by name."""
        if self.launcher is None:
            message = "Owned launcher missing"
            raise ProbeError(message)
        return self.launcher

    def active_sdl(self) -> SDLAPI:
        """Require stock SDL initialization before observing controller state."""
        if self.sdl is None:
            message = "Stock SDL observer missing"
            raise ProbeError(message)
        return self.sdl

    def active_pad(self) -> NativePad:
        """Require the suite-owned uinput handle before writing events."""
        if self.pad is None:
            message = "Owned native gamepad missing"
            raise ProbeError(message)
        return self.pad

    def active_desktop(self) -> Desktop:
        """Borrow the authenticated display opened for this launch."""
        if self.desktop is None:
            message = "Owned authenticated display missing"
            raise ProbeError(message)
        return self.desktop

    def retain_boundary(self, name: str) -> None:
        """Publish one private incomplete observation before final-report cleanup.

        Fixed exclusive names bound retention even if native code exits without
        unwinding Python. These snapshots cannot satisfy the final assertion.
        """
        if name not in (
            "before-chord",
            "chord-pressed",
            "chord-released",
            "launcher-exit",
            "failure",
            "cleanup-start",
            "cleanup-returned",
        ):
            message = "Unknown emulator evidence boundary"
            raise ValueError(message)
        previous = self.boundary
        if name in ("failure", "cleanup-start") and self.launcher is not None:
            self.observe_launch_failure(self.active_launcher().poll())
            self.observe_startup_failure()
        self.boundary = name
        value: dict[str, object] = {
            "schema": 1,
            "status": "incomplete",
            "boundary": name,
            "case": self.case.identifier,
            "system": self.case.system,
            "backend": self.case.backend,
            "core": self.case.core,
            "assertions": ASSERTIONS,
            "previous_boundary": previous,
            "observed": time.monotonic(),
            "probe": {"pid": os.getpid(), "start": process_stat(os.getpid())[1]},
            "launcher": (
                {
                    "pid": self.active_launcher().pid,
                    "start": self.launcher_start,
                    "code": self.active_launcher().poll(),
                }
                if self.launcher is not None
                else None
            ),
            "emulator": (
                {
                    "pid": self.pinned_emulator().pid,
                    "start": self.pinned_emulator().start,
                    "live": (
                        live(self.emulator_descriptor())
                        if self.emulator_fd is not None
                        else None
                    ),
                }
                if self.emulator_identity is not None
                else None
            ),
            "private_output": (
                self.launcher_output.observation()
                if self.launcher_output is not None
                else None
            ),
            "observations": {
                key: self.result[key]
                for key in (
                    "media",
                    "profile",
                    "backend_identity",
                    "native_device_consumption",
                    "chord",
                    "termination_observation",
                    "launch_failure_diagnostic",
                    "startup_failure_diagnostic",
                    "failure_observation",
                    "cleanup",
                )
                if key in self.result
            },
            "captures": list(self.captures.values()),
        }
        publish_json(self.directory / ("emulator-" + name + ".json"), value)

    def permission(self) -> None:
        """Require the coordinator lease before generating input."""
        input_permitted()

    def wait_permission(self) -> None:
        """Wait at most 120 seconds for native authorization."""
        deadline = time.monotonic() + 120
        while True:
            try:
                self.permission()
            except InterruptedError as error:
                if time.monotonic() >= deadline:
                    message = "Native inspection permission deadline expired"
                    raise DiagnosticError(message) from error
                time.sleep(0.05)
            else:
                return

    def select(self) -> bool:
        """Select only after host effective-mount validation has opened the lease."""
        stock = load_catalog(self.catalog_path)
        system = stock.system(self.case.system)
        require(
            (self.case.backend, self.case.core) in system.backends,
            "Stock system/core declaration missing",
        )
        reproduction = self.reproduction
        if self.reproduce_required or reproduction.exists():
            self.selection = read_selection(
                reproduction, self.roms_view, catalog_path=self.catalog_path
            )
            require(
                self.selection.system == self.case.system,
                "Reproduction system does not match case",
            )
        else:
            eligible = inspect_media(system, self.roms_view)
            if not eligible.candidates:
                self.result.update(
                    status="skipped-no-media",
                    reason="Skipped: no compatible mounted media",
                    native_device_consumption={
                        "status": "untested",
                        "reason": "Skipped: no compatible mounted media",
                    },
                )
                return False
            self.selection = select_media(eligible, secrets.randbelow)
        write_selection(self.directory / "selection.json", self.selection)
        self.result["media"] = {
            "identity": self.selection.digest,
            "route": "existing-readonly-mounted-private-media",
            "catalog_sha256": stock.sha256,
            "private_record": "selection.json",
        }
        return True

    def create_pad(self) -> list[str]:
        """Discover actual SDL identity and qualify each suite control before launch."""
        evdev = _stock_evdev()
        definition = _gamepad_definition(RUNTIME_ROOT / "suite-gamepad.json")
        self.definition = definition
        events = {
            evdev.ecodes.EV_KEY: definition["buttons"],
            evdev.ecodes.EV_ABS: [
                (code, evdev.AbsInfo(0, -32768, 32767, 0, 0, 0))
                for code in definition["axes"]
            ]
            + [(code, evdev.AbsInfo(0, -1, 1, 0, 0, 0)) for code in definition["hat"]],
        }
        self.pad = evdev.UInput(
            events=events,
            name=definition["name"],
            bustype=definition["bus"],
            vendor=definition["vendor"],
            product=definition["product"],
            version=definition["version"],
        )
        self.evdev = evdev
        sysname = evdev._uinput.get_sysname(self.pad.fd)  # noqa: SLF001  # Stock descriptor identity.
        source = wait_for(
            "suite native gamepad forwarding",
            lambda: next(
                (
                    source
                    for source in _records(self.integrity.status().get("sources", []))
                    if source["sysname"] == sysname
                    and source["source_pid"] == os.getpid()
                ),
                None,
            ),
        )
        if source is None:
            message = "Suite native gamepad forwarding missing"
            raise ProbeError(message)
        self.pad_source = source
        self.pad_node = _text(source["node"])
        self.pad_device = Path(self.pad_node).stat().st_rdev
        observation: dict[str, object] = {
            "source_pid": os.getpid(),
            "source_sysname": sysname,
            "event_device": [os.major(self.pad_device), os.minor(self.pad_device)],
            "before": gamepad_device_observation(Path(self.pad_node), self.pad_device),
            "initialization": "not-run",
            "publication": {
                "properties": source.get("udev_properties"),
                "classifier_sha256": source.get("udev_classifier_sha256"),
            },
        }
        self.result["pad_discovery"] = observation
        require(
            _record(source.get("udev_properties", {})).get("ID_INPUT_JOYSTICK") == "1",
            "Suite gamepad lacks stock classifier publication",
        )
        guid, actual_name, counts = self.discover_sdl_pad(definition, observation)
        sdl = self.active_sdl()
        qualified = self.qualify_controls()
        # Only suite data enters this disposable home. Never read a production profile.
        mapping = (
            (RUNTIME_ROOT / "suite-es-input.cfg")
            .read_text(encoding="utf-8")
            .replace("{guid}", guid)
        )
        require(not PROFILE.is_symlink(), "Disposable ES profile is a symlink")
        PROFILE.parent.mkdir(parents=True, exist_ok=True)
        PROFILE.write_text(mapping, encoding="utf-8")
        self.profile_seeded = True
        self.profile_hash = digest(PROFILE)
        self.result["profile"] = {
            "sha256": self.profile_hash,
            "definition_sha256": digest(RUNTIME_ROOT / "suite-gamepad.json"),
            "template_sha256": digest(RUNTIME_ROOT / "suite-es-input.cfg"),
            "guid": guid,
            "name": actual_name,
            "sdl_index": self.pad_index,
            "counts": counts,
            "qualified_controls": qualified,
            "source": source,
            "event_device": [os.major(self.pad_device), os.minor(self.pad_device)],
            "stock_configgen_consumed": False,
        }
        # Close only SDL's reader, leaving the suite-owned UInput alive for configgen.
        sdl.SDL_JoystickClose(self.joystick)
        self.joystick = None
        sdl.SDL_QuitSubSystem(sdl.SDL_INIT_JOYSTICK)
        return [
            "-p1index",
            str(self.pad_index),
            "-p1guid",
            guid,
            "-p1name",
            actual_name,
            "-p1devicepath",
            self.pad_node,
            "-p1nbbuttons",
            str(counts[0]),
            "-p1nbaxes",
            str(counts[1]),
            "-p1nbhats",
            str(counts[2]),
        ]

    def discover_sdl_pad(
        self, definition: GamepadDefinition, observation: dict[str, object]
    ) -> tuple[str, str, list[int]]:
        """Pin native library provenance and the owned pad's actual SDL identity."""
        self.sdl = _stock_sdl()
        sdl = self.sdl
        version = sdl.SDL_version()
        sdl.SDL_GetVersion(ctypes.byref(version))
        observation["sdl_version"] = [version.major, version.minor, version.patch]
        observation["sdl_object"] = loaded_object_observation(
            sdl.SDL_InitSubSystem, Path("/usr/lib/libSDL2-2.0.so.0.3200.8")
        )
        require(
            _record(observation["sdl_object"])["status"] == "mapped",
            "Loaded SDL does not match the stock inventory path",
        )
        library = ctypes.CDLL(
            "/usr/lib/libSDL2-2.0.so.0.3200.8", mode=os.RTLD_NOLOAD | os.RTLD_NOW
        )
        mode = SDLDiscoveryMode(library)
        observation["discovery_mode"] = mode.observed
        discovery = SDLGamepadDiscovery(sdl, self.pad_device)
        observation["sdl"] = discovery.evidence
        try:
            initialized = sdl.SDL_InitSubSystem(sdl.SDL_INIT_JOYSTICK) == 0
            observation["initialization"] = "passed" if initialized else "failed"
            observation["initialization_error_present"] = bool(sdl.SDL_GetError())
            try:
                udev = ctypes.CDLL("libudev.so.1", mode=os.RTLD_NOLOAD | os.RTLD_NOW)
                observation["udev_object"] = loaded_object_observation(
                    udev.udev_new, Path("/lib/libudev.so.1.6.3")
                )
            except OSError:
                observation["udev_object"] = {"status": "not-loaded"}
            require(initialized, "Stock SDL joystick initialization failed")
            require(
                mode.observed == {"udev_selected": True},
                "Actual SDL libudev discovery mode not established",
            )
            require(
                _record(observation["udev_object"])["status"] == "mapped",
                "Loaded libudev does not match the stock inventory path",
            )
            self.pad_index = (
                _integer(wait_for("actual stock SDL gamepad discovery", discovery.poll))
                - 1
            )
        finally:
            mode.close()
            observation["after"] = gamepad_device_observation(
                Path(self.pad_node), self.pad_device
            )
        self.joystick = sdl.SDL_JoystickOpen(self.pad_index)
        require(self.joystick, "Stock SDL cannot open suite gamepad")
        actual_name = os.fsdecode(sdl.SDL_JoystickName(self.joystick))
        require(
            actual_name == definition["name"], "Discovered SDL gamepad name differs"
        )
        counts = [
            sdl.SDL_JoystickNumButtons(self.joystick),
            sdl.SDL_JoystickNumAxes(self.joystick),
            sdl.SDL_JoystickNumHats(self.joystick),
        ]
        require(
            counts == definition["expected_sdl_counts"],
            "Discovered SDL control counts differ",
        )
        buffer = ctypes.create_string_buffer(33)
        sdl.SDL_JoystickGetGUIDString(
            sdl.SDL_JoystickGetGUID(self.joystick), buffer, 33
        )
        guid = buffer.value.decode("ascii")
        require(
            len(guid) == SDL_GUID_LENGTH and int(guid, 16) != 0,
            "Actual SDL GUID is unavailable",
        )
        self.guid = guid
        return guid, actual_name, counts

    def qualify_controls(self) -> list[list[str | int]]:
        """Prove each owned uinput control reaches SDL and returns to neutral.

        Each press has a finally-release independent of lease validity. These
        observations qualify the suite device, not physical client forwarding.
        """
        definition, evdev = self.definition, self.evdev
        qualified: list[list[str | int]] = []
        for index, code in enumerate(definition["buttons"]):
            self.permission()
            self.active_pad().write(evdev.ecodes.EV_KEY, code, 1)
            self.active_pad().syn()
            try:
                wait_for(
                    "actual SDL button identity", partial(self.sdl_button, index, 1), 3
                )
                qualified.append(["button", code, index])
            finally:
                self.active_pad().write(evdev.ecodes.EV_KEY, code, 0)
                self.active_pad().syn()
            wait_for("SDL neutral release", partial(self.sdl_button, index, 0), 3)
        for index, code in enumerate(definition["axes"]):
            self.permission()
            self.active_pad().write(evdev.ecodes.EV_ABS, code, -24000)
            self.active_pad().syn()
            try:
                wait_for("actual SDL axis identity", partial(self.sdl_axis, index), 3)
                qualified.append(["axis", code, index])
            finally:
                self.active_pad().write(evdev.ecodes.EV_ABS, code, 0)
                self.active_pad().syn()
            wait_for("SDL neutral axis", partial(self.sdl_axis, index, neutral=True), 3)
        for code, value, expected in ((16, 1, 2), (16, -1, 8), (17, -1, 1), (17, 1, 4)):
            self.permission()
            self.active_pad().write(evdev.ecodes.EV_ABS, code, value)
            self.active_pad().syn()
            try:
                wait_for("actual SDL hat identity", partial(self.sdl_hat, expected), 3)
                qualified.append(["hat", code, expected])
            finally:
                self.active_pad().write(evdev.ecodes.EV_ABS, code, 0)
                self.active_pad().syn()
            wait_for("SDL neutral hat", partial(self.sdl_hat, 0), 3)
        return qualified

    def sdl_button(self, index: int, value: int) -> bool:
        """Observe one qualified SDL button."""
        self.active_sdl().SDL_JoystickUpdate()
        return self.active_sdl().SDL_JoystickGetButton(self.joystick, index) == value

    def sdl_axis(self, index: int, *, neutral: bool = False) -> bool:
        """Observe the suite axis at neutral or its qualification threshold."""
        self.active_sdl().SDL_JoystickUpdate()
        value = self.active_sdl().SDL_JoystickGetAxis(self.joystick, index)
        return value == 0 if neutral else value < SDL_AXIS_QUALIFICATION_THRESHOLD

    def sdl_hat(self, value: int) -> bool:
        """Observe the suite hat bit mask."""
        self.active_sdl().SDL_JoystickUpdate()
        return self.active_sdl().SDL_JoystickGetHat(self.joystick, 0) == value

    def xemu_settings(self) -> dict[str, object]:
        """Read bounded stock-generated TOML, never retain its private disc path."""
        descriptor = os.open(XEMU_CONFIG, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            require(
                stat.S_ISREG(os.fstat(stream.fileno()).st_mode),
                "Stock xemu TOML is not a regular file",
            )
            raw = stream.read(65537)
        require(len(raw) <= MAX_METADATA_BYTES, "Stock xemu TOML exceeds limit")
        return _record(tomllib.loads(raw.decode("utf-8")))

    def xemu_disc(self) -> Path:
        """Follow the selected disc through stock's ordinary ISO/squashfs route.

        For squashfs, require an actual read-only mount backed by that selected
        archive. Never mount, unpack, search another library or export paths.
        """
        files = object_record(
            object_record(self.xemu_settings().get("sys")).get("files")
        )
        dvd = files.get("dvd_path")
        if not isinstance(dvd, str):
            message = "Stock xemu selected disc missing"
            raise ProbeError(message)
        selected = Path("/userdata/roms") / self.selection.entry
        disc = Path(dvd)
        if selected.suffix.lower() == ".iso":
            require(disc == selected, "Stock xemu selected disc differs")
        else:
            require(
                selected.suffix.lower() == ".squashfs",
                "Unsupported stock xemu disc format",
            )
            mount = Path("/var/run/squashfs") / selected.stem
            require(
                disc.resolve().is_relative_to(mount)
                and os.statvfs(disc).f_flag & os.ST_RDONLY,
                "Stock squashfs disc escaped its read-only mount",
            )
            with Path("/proc/self/mountinfo").open(encoding="utf-8") as stream:
                raw = stream.read(1024 * 1024 + 1)
            require(len(raw) <= MAX_PROCFS_BYTES, "Mount observations exceed limit")
            matches = []
            for line in raw.splitlines():
                fields = line.split()
                separator = fields.index("-")
                mount_path = re.sub(
                    r"\\(040|011|012|134)",
                    lambda match: chr(int(match[1], 8)),
                    fields[4],
                )
                if mount_path == str(mount) and fields[separator + 1] == "squashfs":
                    matches.append(fields[separator + 2])
            require(
                len(matches) == 1 and re.fullmatch(r"/dev/loop[0-9]+", matches[0]),
                "Selected stock squashfs backing is not established",
            )
            backing = (
                Path("/sys/class/block") / Path(matches[0]).name / "loop/backing_file"
            )
            backing_path = Path(
                "/" + backing.read_text(encoding="utf-8").strip().lstrip("/")
            )
            backing_info, selected_info = backing_path.stat(), selected.stat()
            require(
                (backing_info.st_dev, backing_info.st_ino)
                == (selected_info.st_dev, selected_info.st_ino),
                "Stock squashfs is not backed by the selected archive",
            )
        require(
            stat.S_ISREG(disc.stat().st_mode), "Stock xemu disc is not a regular file"
        )
        return disc

    def xemu_prerequisites(self) -> None:
        """Keep external firmware read-only and seed only the inspected owned home."""
        self.result["prerequisites"] = {
            key: {"status": "missing"} for key in ("mcpx", "bios", "hdd")
        }
        for key, path in (
            ("mcpx", XEMU_FILES["bootrom_path"]),
            ("bios", XEMU_FILES["flashrom_path"]),
        ):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                require(
                    stat.S_ISREG(info.st_mode) and info.st_size > 0,
                    "Xbox firmware is not a nonempty regular file",
                )
                require(
                    os.fstatvfs(stream.fileno()).f_flag & os.ST_RDONLY,
                    "Xbox firmware input is not read-only mounted",
                )
                _record(self.result["prerequisites"])[key] = {
                    "status": "available",
                    "identity": hashlib.file_digest(stream, "sha256").hexdigest(),
                    "readonly": True,
                    "path": path,
                }
        userdata = Path("/home/retro/userdata")
        require(
            Path("/userdata").resolve() == userdata,
            "Xbox userdata is not the inspected disposable home",
        )
        self.permission()
        _record(self.result["prerequisites"])["hdd"] = seed_xemu_hdd(
            userdata, Path(XEMU_HDD)
        )
        self.result["disposable_state"] = {
            "identity_verified": True,
            "production_state_copied": False,
            "hdd": XEMU_FILES["hdd_path"],
            "eeprom": XEMU_FILES["eeprom_path"],
            "config": str(XEMU_CONFIG),
            "saves": "/userdata/saves/xbox",
            "cache": "/userdata/system/cache",
        }

    def xemu_consumption(self) -> bool:
        """Bind mapped SDL3, suite-pad FD and stock TOML/environment to this case."""
        pid = self.pinned_emulator().pid
        opened = _opened_input_devices(pid)
        pad = (os.major(self.pad_device), os.minor(self.pad_device))
        if pad not in opened:
            return False
        library_info = Path(XEMU_SDL).stat()
        with Path(f"/proc/{pid}/maps").open("rb") as stream:
            maps = stream.read(1024 * 1024 + 1)
        require(len(maps) <= MAX_PROCFS_BYTES, "xemu memory map exceeds limit")
        mapped = False
        for line in maps.splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) < PROC_MAP_REQUIRED_FIELDS:
                continue
            major, minor = (int(value, 16) for value in fields[3].split(b":"))
            if (
                b"x" in fields[1]
                and int(fields[4]) == library_info.st_ino
                and os.makedev(major, minor) == library_info.st_dev
            ):
                mapped = True
        require(mapped, "Actual xemu consumer did not map stock SDL3")
        environment: dict[bytes, str] = {
            key: value.decode("utf-8")
            for key, value in _process_environment(
                pid,
                (b"SDL_GAMECONTROLLERCONFIG", b"XDG_CONFIG_HOME", b"LC_NUMERIC"),
            ).items()
        }
        require(
            environment.get(b"XDG_CONFIG_HOME") == "/userdata/system/configs"
            and environment.get(b"LC_NUMERIC") == "C",
            "Actual xemu stock environment differs",
        )
        mapping = environment.get(b"SDL_GAMECONTROLLERCONFIG", "")
        rows = [row for row in mapping.splitlines() if row.startswith(self.guid + ",")]
        require(len(rows) == 1, "Actual xemu suite SDL mapping missing")
        bindings = sdl_mapping_bindings(rows[0])
        profile = _suite_profile()
        for sdl_name, es_name in (
            ("a", "b"),
            ("b", "a"),
            ("start", "start"),
            ("back", "select"),
        ):
            button = _profile_button(profile, es_name)
            require(
                bindings.get(sdl_name) == "b" + button,
                "xemu stock mapping did not consume suite buttons",
            )
        require(
            bindings.get("leftx") == "a0"
            and bindings.get("lefty") == "a1"
            and bindings.get("dpup") == "h0.1",
            "xemu stock mapping did not consume suite axes/hat",
        )
        if self.xemu_topology is None:
            self.xemu_topology = sdl3_gamepad(
                self.pad_device, mapping, self.definition["name"]
            )
        guid = self.xemu_topology["guid"]
        config = self.xemu_settings()
        files = object_record(object_record(config.get("sys")).get("files"))
        for key, expected in XEMU_FILES.items():
            require(
                files.get(key) == expected, "Stock xemu writable/firmware route differs"
            )
        self.xemu_disc()
        bindings_config = object_record(
            object_record(config.get("input")).get("bindings")
        )
        require(
            bindings_config.get("port1") == guid,
            "Stock xemu port binding does not match actual SDL3 GUID",
        )
        hotkeys = _hotkeys(Path("/var/run/hotkeygen.context"))
        generator = _stock_xemu_generator()
        expected_context = generator.XemuGenerator().getHotkeysContext()
        _validate_exit_context(hotkeys, expected_context, self.case.backend)
        require(
            any(
                source["name"] == "evmapy" for source in _stock_sources(self.integrity)
            ),
            "Stock launcher evmapy was not forwarded",
        )
        _record(self.result["profile"])["stock_configgen_consumed"] = True
        configured_files: dict[str, object] = {
            **XEMU_FILES,
            "dvd_identity": self.selection.digest,
        }
        self.result["native_device_consumption"] = {
            "status": "passed",
            "input_source": "SDL3",
            "pad_device": list(pad),
            "opened_devices": [list(device) for device in sorted(opened)],
            "sdl_object": {
                "status": "mapped",
                "inventory_path": XEMU_SDL,
                "sha256": digest(Path(XEMU_SDL)),
            },
            "consumer_topology": self.xemu_topology,
            "environment": {
                "sdl_mapping_guid": guid,
                "suite_mapping_consumed": True,
                "XDG_CONFIG_HOME": environment[b"XDG_CONFIG_HOME"],
                "LC_NUMERIC": environment[b"LC_NUMERIC"],
            },
            "generated_mapping": {"input.bindings.port1": guid},
            "stock_exit_context": "xemu",
            "config_path": str(XEMU_CONFIG),
            "configured_files": configured_files,
        }
        return True

    def duckstation_firmware(self) -> None:
        """Observe stock-recognized operator BIOS files, not boot compatibility."""
        generator = _stock_duckstation_generator()
        found = generator.find_bios(generator.bios_lists)
        self.result["prerequisites"] = {
            "bios": {"status": "missing" if not found else "available"}
        }
        require(found, "Eligible disc requires operator PS1 BIOS")
        self.bios_files = {}
        for region, name in found.items():
            path = Path("/userdata/bios") / name
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                require(
                    stat.S_ISREG(os.fstat(stream.fileno()).st_mode),
                    "BIOS is not a regular file",
                )
                self.bios_files[region] = (
                    name,
                    hashlib.file_digest(stream, "sha256").hexdigest(),
                )
        identities = sorted(
            (region, value[1]) for region, value in self.bios_files.items()
        )
        _record(_record(self.result["prerequisites"])["bios"]).update(
            identity=hashlib.sha256(json.dumps(identities).encode()).hexdigest(),
            stock_configured_route=False,
        )

    def prepare_duckstation_renderer(self) -> None:
        """Seed the undecorated PSX fixture and private observation in owned state."""
        configuration = Path("/userdata/system/batocera.conf")
        with configuration.open("a", encoding="utf-8") as stream:
            # Match the supported PSX setting used by the working beta profile.
            # Default bezels insert MangoHUD into stock configgen's command.
            # This fixture tests the emulator/shortcut, not that extra interposer;
            # runtime/user defaults and the wrapper's final environment stay intact.
            stream.write("\npsx.bezel=none\n")
            stream.write("\npsx.duckstation_gfxbackend=" + self.case.renderer + "\n")
        DUCKSTATION_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        settings: configparser.ConfigParser = CasePreservingConfigParser(
            interpolation=None
        )
        if DUCKSTATION_SETTINGS.exists():
            settings = self.duckstation_settings()
        settings["Logging"] = {
            "LogToFile": "true",
            "LogToConsole": "true",
            "LogLevel": "Info",
            "LogFilter": "",
        }
        with DUCKSTATION_SETTINGS.open("w", encoding="utf-8") as stream:
            settings.write(stream)
        log = DUCKSTATION_SETTINGS.parent / "duckstation.log"
        if log.exists() or log.is_symlink():
            message = "Unexpected prior DuckStation log in disposable state"
            raise ProbeError(message)

    def duckstation_renderer(self) -> bool:
        """Bind the private log inode while alive.

        Buffered renderer records are deliberately not required at this barrier.
        """
        selected = self.duckstation_settings().get("GPU", "Renderer", fallback="")
        if selected != self.case.renderer:
            message = "Generated DuckStation renderer differs from selected variant"
            raise ProbeError(message)
        pinned = self.emulator_identity
        if pinned is None:
            message = "Pinned DuckStation process missing"
            raise ProbeError(message)
        if self.duckstation_log_fd is not None:
            return True
        path = DUCKSTATION_SETTINGS.parent / "duckstation.log"
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return False
        try:
            info = os.fstat(descriptor)
            if not (
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and info.st_uid == os.getuid()
            ):
                message = "Unsafe DuckStation backend log"
                raise ProbeError(message)
            # Only a file opened by this pinned emulator can supply activation.
            opened = False
            for item in Path(f"/proc/{pinned.pid}/fd").iterdir():
                try:
                    other = item.stat()
                    opened |= (other.st_dev, other.st_ino) == (info.st_dev, info.st_ino)
                except FileNotFoundError:
                    continue
            if not opened:
                return False
            self.duckstation_log_fd = descriptor
            descriptor = -1
        finally:
            if descriptor != -1:
                os.close(descriptor)
        return True

    def finalize_duckstation_renderer(self) -> None:
        """Interpret the pinned log after normal emulator and launcher completion."""
        descriptor = self.duckstation_log_fd
        pinned = self.emulator_identity
        if pinned is None:
            message = "Pinned DuckStation process missing"
            raise ProbeError(message)
        if descriptor is None:
            message = "Pinned DuckStation backend log missing"
            raise ProbeError(message)
        selected = self.case.renderer
        mode = active_backend(os.pread(descriptor, 1024 * 1024 + 1, 0))
        if mode is None:
            message = "Actual DuckStation active backend evidence missing"
            raise ProbeError(message)
        if mode not in (
            ("OpenGL", "OpenGLES") if selected == "OpenGL" else ("Vulkan",)
        ):
            message = "Actual DuckStation active backend differs from variant"
            raise ProbeError(message)
        self.result["renderer"] = {
            "selected": selected,
            "active": mode,
            "activation": "pinned-open-file-device-context-hw-framebuffer",
            "pid": pinned.pid,
            "start": pinned.start,
            "visual_argument": self.result.get("qt_visual"),
            "discovery": "live-egl-x11" if selected == "OpenGL" else "not-run",
        }

    def duckstation_settings(self) -> configparser.ConfigParser:
        """Read only stock-generated settings in this owned disposable home."""
        if DUCKSTATION_SETTINGS.is_symlink():
            message = "DuckStation settings is a symlink"
            raise ProbeError(message)
        config = CasePreservingConfigParser(interpolation=None)
        with DUCKSTATION_SETTINGS.open(encoding="utf-8") as stream:
            config.read_file(stream)
        return config

    def standalone_output(self) -> bool:
        """Combine selected-disc access and backend render-window observations."""
        selected = set()
        backend_display: dict[str, object] = {}
        if self.case.backend == "xemu":
            disc = self.xemu_disc()
            backend_display["disc_format"] = {
                **inspect_xiso(disc),
                "media_identity": self.selection.digest,
            }
            info = disc.stat()
            selected.add((info.st_dev, info.st_ino))
        else:
            for member in self.selection.members:
                if Path(member.relative_path).suffix.lower() in (
                    ".cue",
                    ".toc",
                    ".ccd",
                    ".m3u",
                ):
                    continue
                info = (self.roms_view / member.relative_path).stat()
                selected.add((info.st_dev, info.st_ino))
        disc_open = False
        for path in Path(f"/proc/{self.pinned_emulator().pid}/fd").iterdir():
            try:
                info = path.stat()
                if (
                    stat.S_ISREG(info.st_mode)
                    and (info.st_dev, info.st_ino) in selected
                ):
                    disc_open = True
            except FileNotFoundError:
                continue
        render = self.active_desktop().render_window(
            self.pinned_emulator().pid, application=self.case.backend
        )
        backend_display["selected_disc_open"] = disc_open
        backend_display["render_window"] = render
        backend_display["non_dialog"] = render
        self.result["backend_display"] = backend_display
        return disc_open and bool(render)

    def duckstation_consumption(self) -> bool:
        """Bind the effective SDL mapping to the actual opened suite pad.

        A single observed joystick removes SDL player reassignment ambiguity.
        The configured index is labeled as such, not independently logged state.
        No RetroArch input drivers or final-keyboard FD are required by Qt.
        """
        pyudev = _stock_udev()
        context = pyudev.Context()
        opened = set()
        joysticks = set()
        for path in Path(f"/proc/{self.pinned_emulator().pid}/fd").iterdir():
            try:
                info = path.stat()
                if (
                    stat.S_ISCHR(info.st_mode)
                    and os.major(info.st_rdev) == LINUX_INPUT_MAJOR
                ):
                    device = (os.major(info.st_rdev), os.minor(info.st_rdev))
                    opened.add(device)
                    node = pyudev.Devices.from_device_number(
                        context, "char", info.st_rdev
                    )
                    if node.properties.get("ID_INPUT_JOYSTICK") == "1":
                        joysticks.add(device)
            except FileNotFoundError:
                continue
        pad = (os.major(self.pad_device), os.minor(self.pad_device))
        if pad not in opened:
            return False
        discovered = _record(
            _record(_record(self.result["pad_discovery"])["sdl"])["latest"]
        )["joysticks"]
        require(
            discovered == 1 and self.pad_index == 0 and joysticks == {pad},
            "DuckStation suite-pad topology is ambiguous",
        )
        environment = _process_environment(
            self.pinned_emulator().pid,
            (b"SDL_GAMECONTROLLERCONFIG", b"SDL_JOYSTICK_HIDAPI", b"XDG_CONFIG_HOME"),
        )
        require(
            environment.get(b"SDL_JOYSTICK_HIDAPI") == b"0"
            and environment.get(b"XDG_CONFIG_HOME") == b"/userdata/system/configs",
            "Actual DuckStation stock environment differs",
        )
        mappings = [
            row.split(b",")
            for row in environment.get(b"SDL_GAMECONTROLLERCONFIG", b"").splitlines()
            if row.startswith(self.guid.encode("ascii") + b",")
        ]
        require(len(mappings) == 1, "Actual DuckStation suite SDL mapping missing")
        row = mappings[0]
        require(
            len(row) > SDL_MAPPING_PREFIX_FIELDS
            and row[1] == self.definition["name"].encode("utf-8"),
            "Actual SDL mapping name differs",
        )
        bindings = dict(field.split(b":", 1) for field in row[2:] if b":" in field)
        profile = _suite_profile()
        for sdl_name, es_name in (
            (b"a", "b"),
            (b"b", "a"),
            (b"start", "start"),
            (b"back", "select"),
        ):
            button = _profile_button(profile, es_name)
            require(
                bindings.get(sdl_name) == ("b" + button).encode("ascii"),
                "Actual SDL environment did not consume suite buttons",
            )
        require(
            bindings.get(b"leftx") == b"a0"
            and bindings.get(b"lefty") == b"a1"
            and bindings.get(b"dpup") == b"h0.1",
            "Actual SDL environment did not consume suite axes/hat",
        )
        config = self.duckstation_settings()
        expected = {
            "InputSources.SDL": "true",
            "InputSources.Evdev": "false",
            "InputSources.XInput": "false",
            "InputSources.RawInput": "false",
            "Pad1.Type": "DigitalController",
            "Pad1.Start": "SDL-0/Start",
            "Pad1.Cross": "SDL-0/A",
        }
        for key, value in expected.items():
            section, option = key.split(".", 1)
            require(
                config.get(section, option, fallback=None) == value,
                "Stock DuckStation suite mapping differs",
            )
        require(
            config.get("BIOS", "SearchDirectory", fallback=None) == "/userdata/bios",
            "Stock DuckStation firmware route differs",
        )
        for region in ("NTSCU", "PAL", "NTSCJ"):
            bios = self.bios_files.get("Uni", self.bios_files.get(region))
            if bios is not None:
                require(
                    config.get("BIOS", "Path" + region, fallback=None) == bios[0],
                    "Stock DuckStation firmware selection differs",
                )
        _record(_record(self.result["prerequisites"])["bios"])[
            "stock_configured_route"
        ] = True
        hotkeys = _hotkeys(Path("/var/run/hotkeygen.context"))
        generator = _stock_duckstation_generator()
        expected_context = generator.DuckstationGenerator().getHotkeysContext()
        _validate_exit_context(hotkeys, expected_context, self.case.backend)
        require(
            any(
                source["name"] == "evmapy" for source in _stock_sources(self.integrity)
            ),
            "Stock launcher evmapy was not forwarded",
        )
        _record(self.result["profile"])["stock_configgen_consumed"] = True
        self.result["native_device_consumption"] = {
            "status": "passed",
            "input_source": "SDL",
            "pad_device": list(pad),
            "opened_devices": [list(device) for device in sorted(opened)],
            "generated_mapping": expected,
            "stock_exit_context": hotkeys["name"],
            "environment": {
                "sdl_mapping_guid": self.guid,
                "suite_mapping_consumed": True,
                "SDL_JOYSTICK_HIDAPI": "0",
                "XDG_CONFIG_HOME": "/userdata/system/configs",
            },
            "consumer_topology": {
                "discovered_joysticks": discovered,
                "opened_joysticks": [list(pad)],
                "configured_player_index": self.pad_index,
                "index_basis": "single-observed-suite-pad",
            },
        }
        return True

    def launch(self, arguments: Sequence[str]) -> None:
        """Start the owned stock launcher after validating media identity."""
        self.permission()
        verified = read_selection(
            self.directory / "selection.json",
            self.roms_view,
            catalog_path=self.catalog_path,
        )
        require(
            verified.digest == self.selection.digest,
            "Selected media identity changed before stock launch",
        )
        environment = None
        if self.case.backend == "duckstation":
            environment = launcher_environment(
                PROFILE.parent / OVERRIDE_NAME,
                RUNTIME_ROOT / OVERRIDE_NAME,
                os.environ,
            )
        # Explicit negative control only. Stock configgen must reject this
        # unavailable core before any emulator can supply passing observations.
        core = (
            "gow-native-absent" if self.control == "launcher-error" else self.case.core
        )
        # Drain unchanged stock logging into bounded private memory, never
        # collected artifacts. It contains environment and private ROM paths.
        self.launcher = subprocess.Popen(  # noqa: S603  # Stock launcher, validated media argv.
            [
                "/usr/bin/emulatorlauncher",
                "-system",
                self.case.system,
                "-rom",
                str(Path("/userdata/roms") / self.selection.entry),
                "-emulator",
                self.case.backend,
                "-core",
                core,
                *arguments,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
        )
        if self.launcher.stdout is None:
            message = "Private launcher pipe missing"
            raise ProbeError(message)
        self.launcher_output = PrivateOutput(self.launcher.stdout)
        self.launcher_start = process_stat(self.active_launcher().pid)[1]
        self.desktop = Desktop()

    def validate_emulator_command(self, path: Path) -> None:
        """Require stock backend argv before accepting a candidate child process."""
        command = (path / "cmdline").read_bytes().split(b"\0")
        if self.case.backend == "libretro":
            require(
                b"-L" in command
                and command.count(b"-L") == 1
                and command.index(b"-L") + 1 < len(command)
                and command[command.index(b"-L") + 1] == os.fsencode(self.core_path),
                "Actual emulator core command differs",
            )
        elif self.case.backend == "xemu":
            require(
                command[1:] == [b"-config_path", os.fsencode(XEMU_CONFIG), b""],
                "Actual xemu stock command differs",
            )
        else:
            arguments = command[1:]
            visual = None
            if arguments[:1] == [b"-visual"]:
                require(
                    self.case.renderer == "OpenGL"
                    and len(arguments) == DUCKSTATION_VISUAL_ARGUMENT_FIELDS
                    and re.fullmatch(rb"0x[0-9a-f]+", arguments[1])
                    and 0 < int(arguments[1], 16) <= MAX_X11_VISUAL,
                    "Actual DuckStation Qt visual argument differs",
                )
                visual = arguments[1].decode("ascii")
                arguments = arguments[2:]
            require(
                arguments[:3] == [b"-batch", b"-nogui", b"--"]
                and len(arguments) == DUCKSTATION_ARGUMENT_FIELDS
                and bool(arguments[3])
                and arguments[4] == b""
                and (visual is not None) == (self.case.renderer == "OpenGL"),
                "Actual DuckStation stock command differs",
            )
            self.result["qt_visual"] = visual

    def record_backend_identity(self) -> None:
        """Publish stock binary and core identities only after process pinning."""
        if self.case.backend == "libretro":
            self.result["backend_identity"] = {
                "executable_sha256": digest(Path(self.case.executable)),
                "core_sha256": digest(self.core_path),
                "core": self.case.core,
                "core_info_sha256": digest(self.info_path),
                **backend_versions(self.case),
            }
        elif self.case.backend == "duckstation":
            self.result["backend_identity"] = duckstation_identity()

    def _pin_emulator_descriptor(
        self, path: Path, pid: int, parent: int, start: int
    ) -> None:
        """Transfer one verified emulator pidfd, closing it on admission failure."""
        fd = os.pidfd_open(pid)
        try:
            require(
                live(fd) and process_stat(pid) == (parent, start),
                "Emulator identity raced pinning",
            )
            self.validate_emulator_command(path)
            require(
                (path / "exe").resolve() == Path(self.case.executable),
                "Actual emulator executable differs",
            )
            self.emulator_fd = fd
            self.emulator_identity = ProcessIdentity(pid, start)
            self.record_backend_identity()
        except BaseException:
            if self.emulator_fd != fd:
                os.close(fd)
            raise

    def pin_emulator(self) -> None:
        """Pin the stock ELF child with expected command and start ticks."""
        if self.emulator_fd is not None:
            return
        for path in Path("/proc").iterdir():
            if not path.name.isdecimal():
                continue
            try:
                pid = int(path.name)
                if (path / "comm").read_text(encoding="utf-8").strip() != Path(
                    self.case.executable
                ).name:
                    continue
                # A shebang can briefly inherit the wrapper basename before its
                # interpreter runs. Only the absolute stock ELF is a candidate;
                # do not weaken argv gates or pin that interval as the emulator.
                if self.case.backend == "duckstation" and (
                    path / "exe"
                ).resolve() != Path(self.case.executable):
                    continue
                parent, start = process_stat(pid)
                if parent != self.active_launcher().pid:
                    continue
                self._pin_emulator_descriptor(path, pid, parent, start)
            except (FileNotFoundError, ProcessLookupError):
                continue
            else:
                return

    def record_process_failure(
        self,
        role: str,
        pid: int,
        expected_start: int | None,
        descriptor: int | None,
        error: OSError | ProbeError,
    ) -> None:
        """Attribute a failed process read without retaining exception or comm text.

        These best-effort numeric/state samples diagnose a failed observation.
        They neither replace the original error nor authorize an exit result.

        Args:
            role: Fixed emulator or final-source attribution.
            pid: Numeric process whose operation raised.
            expected_start: Previously pinned procfs start ticks, when available.
            descriptor: Borrowed pidfd for that original process, when pinned.
            error: Original failure, retaining numeric errno only for OS errors.
        """
        pidfd_live = None
        if descriptor is not None:
            with contextlib.suppress(OSError, ValueError):
                pidfd_live = live(descriptor)
        state = "unavailable"
        current_start = None
        try:
            with Path(f"/proc/{pid}/stat").open(encoding="utf-8") as stream:
                value = stream.read(4097)
            if len(value) <= MAX_LEADER_STAT_BYTES:
                fields = value[value.rindex(")") + 2 :].split()
                if len(fields[0]) == 1 and fields[0] in "RSDZTtXxKWPI":
                    state = fields[0]
                else:
                    state = "unknown"
                current_start = int(fields[19])
        except (OSError, ValueError, IndexError):
            pass
        self.process_observation_failure = {
            "role": role,
            "pid": pid,
            "expected_start": expected_start,
            "pidfd_live": pidfd_live,
            "proc_state": state,
            "current_start": current_start,
            "errno": error.errno if isinstance(error, OSError) else None,
        }

    def pin_final(self, ready: dict[str, object] | None) -> int:
        """Keep the approved stock final source alive and identical across the case."""
        if ready is None or ready["app_uid"] != os.getuid():
            message = "Owned native transport is not ready"
            raise ProbeError(message)
        final = _record(ready["final"])
        pid = _integer(final["source_pid"])
        approved = ready["approved_process_ids"]
        if not isinstance(approved, list):
            message = "Approved native process list malformed"
            raise ProbeError(message)
        require(
            pid in approved,
            "Final source is not an approved app descendant",
        )
        node = Path(_text(final["node"])).stat()
        require(
            stat.S_ISCHR(node.st_mode) and os.major(node.st_rdev) == LINUX_INPUT_MAJOR,
            "Final event node identity invalid",
        )
        try:
            identity = (
                pid,
                process_stat(pid)[1],
                _text(final["sysname"]),
                _text(final["node"]),
                node.st_rdev,
            )
            if self.final_fd is None:
                self.final_fd = os.pidfd_open(pid)
                self.final_identity = identity
            require(
                live(self.final_fd)
                and identity == self.final_identity
                and process_stat(pid)[1] == identity[1],
                "Pinned final source changed or died",
            )
        except OSError as error:
            self.record_process_failure(
                "final-source",
                pid,
                self.final_identity[1] if self.final_identity is not None else None,
                self.final_fd,
                error,
            )
            raise
        return node.st_rdev

    def native_consumption(self) -> bool:
        """Require generated mapping, stock context, udev and opened device nodes."""
        ready = transport_ready(Path("/run/gow-full-x86-input-transport.json"))
        final_device = self.pin_final(ready)
        if self.case.backend == "duckstation":
            return self.duckstation_consumption()
        if self.case.backend == "xemu":
            return self.xemu_consumption()
        pyudev = _stock_udev()
        device = pyudev.Devices.from_device_number(
            pyudev.Context(), "char", final_device
        )
        classification = {
            key: value
            for key, value in device.properties.items()
            if key.startswith("ID_INPUT")
        }
        require(
            classification.get("ID_INPUT_KEYBOARD") == "1",
            "Final device is not classified as keyboard",
        )
        opened = [
            list(device) for device in _opened_input_devices(self.pinned_emulator().pid)
        ]
        expected_final = [os.major(final_device), os.minor(final_device)]
        expected_pad = [os.major(self.pad_device), os.minor(self.pad_device)]
        if expected_final not in opened or expected_pad not in opened:
            return False
        config = {}
        for line in (
            Path("/userdata/system/configs/retroarch/retroarchcustom.cfg")
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            key, separator, value = line.partition("=")
            if separator:
                config[key.strip()] = value.strip().strip('"')
        require(
            config.get("input_driver") == "udev"
            and config.get("input_joypad_driver") == "udev",
            "Actual RetroArch input backend is not native udev",
        )
        profile = _suite_profile()
        expected_mapping = {}
        for name in ("b", "a", "start", "select"):
            expected_mapping[f"input_player1_{name}_btn"] = _profile_button(
                profile, name
            )
        for key, value in expected_mapping.items():
            require(
                config.get(key) == value,
                "Stock configgen did not consume suite button mapping",
            )
        require(
            config.get("input_player1_up_btn") == "h0up",
            "Stock configgen did not consume suite hat mapping",
        )
        require(
            config.get("input_player1_l_x_minus_axis") == "-0",
            "Stock configgen did not consume suite axis mapping",
        )
        require(
            config.get("input_player1_joypad_index") == str(self.pad_index),
            "Stock configgen selected wrong native pad",
        )
        context = _hotkeys(Path("/var/run/hotkeygen.context"))
        generator = _stock_libretro_generator()
        expected = generator.LibretroGenerator().getHotkeysContext()
        _validate_exit_context(context, expected, self.case.backend)
        require(
            any(
                source["name"] == "evmapy" for source in _stock_sources(self.integrity)
            ),
            "Stock launcher evmapy was not forwarded",
        )
        _record(self.result["profile"])["stock_configgen_consumed"] = True
        final_identity = self.final_identity
        if final_identity is None:
            message = "Pinned final source identity missing"
            raise ProbeError(message)
        self.result["native_device_consumption"] = {
            "status": "passed",
            "input_driver": config["input_driver"],
            "input_joypad_driver": config["input_joypad_driver"],
            "final_udev": classification,
            "final_device": expected_final,
            "pad_device": expected_pad,
            "opened_devices": opened,
            "final_source": {
                "pid": final_identity[0],
                "start": final_identity[1],
                "pinned_live": True,
            },
            "generated_mapping": expected_mapping,
            "stock_exit_context": context["name"],
        }
        return True

    def observe_launch_failure(self, launcher_code: int | None) -> None:
        """Snapshot optional pre-chord diagnostics once, before reader cleanup.

        No emulator identity is needed. Unavailable or unrecognized logs cannot
        change acceptance, and later observations cannot replace this snapshot
        after the existing private reader clears its bytes.
        """
        if (
            launcher_code is None
            or "chord" in self.result
            or "launch_failure_diagnostic" in self.result
            or self.launcher_output is None
        ):
            return
        output = self.launcher_output.read_complete(timeout=0.25)
        self.result["launch_failure_diagnostic"] = {
            "launcher_code": launcher_code,
            "private_output": self.launcher_output.observation(),
            "exception_observation": (
                stock_launch_failure(output)
                if output is not None
                else _launch_exception_observation("stream-unavailable")
            ),
        }

    def observe_startup_failure(self) -> None:
        """Freeze DuckStation's optional pre-chord diagnostic after known failure.

        A dead pinned pidfd or a completed owned launcher permits one 250 ms
        settle through the existing reader. Ordinary live startup never waits.
        Completed launchers share the existing exception diagnostic's settle.
        Snapshot bytes are reduced and discarded even without EOF; subsequent
        output and reader cleanup cannot replace this observation.
        """
        if (
            self.case.backend != "duckstation"
            or "chord" in self.result
            or "startup_failure_diagnostic" in self.result
            or self.launcher is None
            or self.launcher_output is None
        ):
            return
        # These optional probes cannot turn unavailable metadata into death or
        # mask an error from the actual lifecycle's process/identity checks.
        launcher_code = None
        with contextlib.suppress(OSError):
            launcher_code = self.active_launcher().poll()
        if launcher_code is None:
            if self.emulator_identity is None or self.emulator_fd is None:
                return
            try:
                if not select.select([self.emulator_fd], [], [], 0)[0]:
                    return
            except (OSError, ValueError):
                return
        try:
            if launcher_code is None:
                self.launcher_output.read_complete(timeout=0.25)
            else:
                self.observe_launch_failure(launcher_code)
        finally:
            output, state = self.launcher_output.snapshot_available()
            self.result["startup_failure_diagnostic"] = {
                "launcher_code": launcher_code,
                "private_output": state,
                "log_observation": duckstation_startup_failure(output),
            }

    def observe_termination(self, launcher_code: int | None) -> None:
        """Retain pinned process completion and bounded optional log diagnostics."""
        if (
            self.termination_observed
            or launcher_code is None
            or self.emulator_identity is None
            or live(self.emulator_descriptor())
        ):
            return
        if self.launcher_output is None:
            message = "Private launcher output missing"
            raise ProbeError(message)
        self.termination_observed = True
        output = self.launcher_output.read_complete(timeout=0.25)
        classification: dict[str, object] = {
            "status": "stream-unavailable",
            "reason": None,
        }
        if output is not None:
            decision = stock_termination(output)
            self.emulator_termination = decision.kind
            classification = {
                "status": "classified" if decision.kind is not None else "rejected",
                "reason": decision.reason,
            }
            if decision.logging_error is not None:
                classification["logging_error"] = asdict(decision.logging_error)
        self.result["termination_observation"] = {
            "mechanism": "pidfd-and-stock-launcher",
            "kind": self.emulator_termination or "unavailable",
            "classification": classification,
            "private_output": self.launcher_output.observation(),
            "launcher": {
                "pid": self.active_launcher().pid,
                "start": self.launcher_start,
                "code": launcher_code,
            },
            "emulator": {
                "pid": self.pinned_emulator().pid,
                "start": self.pinned_emulator().start,
                "live": False,
            },
            "launcher_source_sha256": STOCK_LAUNCHER_SHA256,
            "log_sha256": (
                hashlib.sha256(output).hexdigest() if output is not None else None
            ),
            "complete": self.emulator_termination is not None,
        }
        self.retain_boundary("launcher-exit")

    def observe_pinned_lifetime(self, pinned: ProcessIdentity) -> bool:
        """Keep pidfd and start identity authoritative through main-thread exit."""
        try:
            try:
                start = process_stat(pinned.pid)[1]
            except ProcessLookupError:
                chord = _record(self.result.get("chord", {}))
                if (
                    chord.get("pressed") is not True
                    or chord.get("released") is not True
                    or not live(self.emulator_descriptor())
                ):
                    raise
                # A completed chord can end the main thread before workers.
                # Only Z metadata for this same pinned identity may wait on a
                # still-live thread-group pidfd.
                state, start = _process_leader_stat(pinned.pid)
                if state != "Z":
                    raise
            require(
                start == pinned.start,
                "Pinned emulator start identity changed",
            )
            alive = live(self.emulator_descriptor())
        except (FileNotFoundError, ProcessLookupError) as error:
            # Missing metadata proves death only for an ended pinned pidfd.
            # A live thread group still fails closed.
            if not live(self.emulator_descriptor()):
                alive = False
            else:
                self.record_process_failure(
                    "emulator", pinned.pid, pinned.start, self.emulator_fd, error
                )
                raise
        except (OSError, ProbeError) as error:
            self.record_process_failure(
                "emulator", pinned.pid, pinned.start, self.emulator_fd, error
            )
            raise
        return alive

    def observe_launch_output(
        self, pinned: ProcessIdentity, active: int | None, *, ready: bool
    ) -> tuple[bool, bool, int | None]:
        """Require backend, native-device and window evidence before pixel proof."""
        content = False
        if self.case.backend == "libretro":
            core_loaded = any(
                line.rstrip().endswith(" " + str(self.core_path))
                for line in Path(f"/proc/{pinned.pid}/maps")
                .read_text(encoding="utf-8")
                .splitlines()
            )
        else:
            core_loaded = self.standalone_output()
            if self.case.backend == "duckstation":
                core_loaded = self.duckstation_renderer() and core_loaded
        if core_loaded and active == pinned.pid and ready and self.native_consumption():
            if "emulator-before-exit" not in self.captures:
                candidate = self.directory / "render-sample.png"
                capture_checkpoint(candidate)
                try:
                    content = rendered_content(candidate)
                finally:
                    candidate.unlink()
            else:
                content = True
        if (
            self.control == "early-native-exit"
            and content
            and "chord" not in self.result
        ):
            # Native shortcut input deliberately precedes the no-exit barrier.
            # It is a failing control, not guest self-exit qualification.
            self.guide_start()
        if self.control == "pre-chord-death" and core_loaded:
            self.forced = True
            signal.pidfd_send_signal(self.emulator_descriptor(), signal.SIGTERM)
        if self.control == "withhold-readiness":
            content = False
        if self.control == "wrong-window":
            active = None
        return core_loaded, content, active

    def observe(self) -> Observation:
        """Sample pinned process, native consumption and render assertions."""
        self.pin_emulator()
        pinned = self.emulator_identity
        alive = self.emulator_fd is not None and live(self.emulator_descriptor())
        launcher_code = self.active_launcher().poll()
        self.observe_launch_failure(launcher_code)
        self.observe_startup_failure()
        self.observe_termination(launcher_code)
        observing_launch = self.case.backend == "libretro" or "chord" not in self.result
        active = (
            self.desktop.active_pid()
            if observing_launch and self.desktop is not None
            else None
        )
        core_loaded = False
        content = False
        transport = transport_ready(Path("/run/gow-full-x86-input-transport.json"))
        ready = transport is not None
        if self.final_fd is not None:
            self.pin_final(transport)
        if alive:
            pinned = self.pinned_emulator()
            alive = self.observe_pinned_lifetime(pinned)
        # Standalone render/config/device state may disappear before process exit.
        if alive and pinned is not None and observing_launch:
            core_loaded, content, active = self.observe_launch_output(
                pinned, active, ready=ready
            )
        return Observation(
            pinned,
            bool(alive),
            launcher_code,
            active,
            core_loaded,
            content,
            ready,
            self.forced,
            emulator_termination=self.emulator_termination,
            backend_display=(
                _optional_record(self.result.get("backend_display"))
                if observing_launch and self.case.backend != "libretro"
                else None
            ),
        )

    def checkpoint(self, name: str) -> dict[str, object]:
        """Capture one barrier, requiring nonblank pre-exit pixels."""
        if name not in self.captures:
            capture = capture_checkpoint(self.directory / (name + ".png"))
            if name == "emulator-before-exit":
                require(
                    rendered_content(self.directory / (name + ".png")),
                    "Emulator output became blank at exit barrier",
                )
            self.captures[name] = capture
        return self.captures[name]

    def guide_start(self) -> bool:
        """Return true only after native Guide+Start press and release complete."""
        self.permission()
        self.retain_boundary("before-chord")
        self.permission()
        require(
            live(self.emulator_descriptor()), "Emulator died at native chord boundary"
        )
        if self.control == "withhold-chord":
            return False
        codes = [self.definition["guide_code"], self.definition["start_code"]]
        self.result["chord"] = {
            "route": "owned-uinput-stock-evmapy-adapter-stock-hotkeygen",
            "pressed": False,
            "released": False,
        }
        for code in codes:
            self.active_pad().write(self.evdev.ecodes.EV_KEY, code, 1)
        self.active_pad().syn()
        _record(self.result["chord"])["pressed"] = True
        end = time.monotonic() + 0.25
        try:
            self.retain_boundary("chord-pressed")
            while time.monotonic() < end:
                self.permission()
                time.sleep(0.025)
        finally:
            self.release_input()
        _record(self.result["chord"])["released"] = True
        self.retain_boundary("chord-released")
        return True

    def release_input(self) -> None:
        """Release owned controls even when permission is revoked."""
        if self.pad is not None:
            for code in self.definition["buttons"]:
                self.active_pad().write(self.evdev.ecodes.EV_KEY, code, 0)
            for code in self.definition["axes"] + self.definition["hat"]:
                self.active_pad().write(self.evdev.ecodes.EV_ABS, code, 0)
            self.active_pad().syn()

    def run(self) -> None:
        """Execute stock launch and the observed shortcut-exit contract."""
        self.wait_permission()
        specification = importlib.util.find_spec("configgen")
        if specification is None or not specification.submodule_search_locations:
            message = "Stock configgen package missing"
            raise ProbeError(message)
        paths = [
            Path("/usr/bin/emulatorlauncher"),
            *(Path(path) for path in self.case.inventory_paths),
            Path("/usr/bin/udevadm"),
            Path("/usr/lib/libSDL2-2.0.so.0.3200.8"),
            Path("/lib/libudev.so.1.6.3"),
            CATALOG,
        ]
        require(
            len(specification.submodule_search_locations) == 1,
            "Ambiguous stock configgen package",
        )
        launcher_source = (
            Path(next(iter(specification.submodule_search_locations)))
            / "emulatorlauncher.py"
        )
        require(
            digest(launcher_source) == STOCK_LAUNCHER_SHA256,
            "Stock launcher differs from inspected source",
        )
        for directory in specification.submodule_search_locations:
            paths.extend(
                Path(directory) / relative
                for relative in (
                    "emulatorlauncher.py",
                    "controller.py",
                    "controllersConfig.py",
                    *(
                        (
                            "generators/libretro/libretroGenerator.py",
                            "generators/libretro/libretroControllers.py",
                        )
                        if self.case.backend == "libretro"
                        else ()
                    ),
                    "utils/hotkeygen.py",
                    "utils/logger.py",
                )
            )
        self.integrity.record_evidence(paths)
        if not self.select():
            return
        if self.case.backend == "duckstation":
            self.duckstation_firmware()
            self.prepare_duckstation_renderer()
        elif self.case.backend == "xemu":
            self.xemu_prerequisites()
            self.result["backend_identity"] = xemu_identity(self.directory)
        arguments = self.create_pad()
        self.launch(arguments)
        self.result["transition"] = EmulatorLifecycle(
            self, Clock(), ExitBudgets()
        ).run()
        if self.case.backend == "duckstation":
            self.finalize_duckstation_renderer()
        if self.case.backend != "libretro":
            display = _record(
                _record(self.result["transition"])["stock_launch_display"]
            )
            del display["exact_core_loaded"]
            display["exact_backend_loaded"] = True
            self.result.pop("backend_display", None)
        require(
            _record(self.result.get("chord", {})).get("pressed") is True
            and _record(self.result.get("chord", {})).get("released") is True,
            "Native Guide+Start press/release evidence missing",
        )
        require(
            self.control == "none",
            "Negative control unexpectedly reached a passing transition",
        )
        self.result["captures"] = list(self.captures.values())
        self.result["status"] = "passed"

    def stop_owned_processes(self, failures: list[str]) -> None:
        """Stop only the pinned emulator and this probe's launcher during teardown."""
        # Only teardown sends signals. Its use is explicit and cannot satisfy exit.
        if self.emulator_fd is not None and live(self.emulator_descriptor()):
            self.forced = True
            try:
                signal.pidfd_send_signal(self.emulator_descriptor(), signal.SIGTERM)
                if not select.select([self.emulator_fd], [], [], 3)[0]:
                    signal.pidfd_send_signal(self.emulator_descriptor(), signal.SIGKILL)
                if not select.select([self.emulator_fd], [], [], 2)[0]:
                    failures.append("Pinned emulator teardown timed out")
            except OSError:
                failures.append("Pinned emulator teardown failed")
        child = self.launcher
        if child is not None and child.poll() is None:
            try:
                child.terminate()
                try:
                    child.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                failures.append("Owned launcher teardown failed")

    def close_process_observers(self, failures: list[str]) -> None:
        """Close private launcher bytes and owned process or log descriptors."""
        if self.launcher_output is not None:
            try:
                self.launcher_output.close()
            except (OSError, RuntimeError):
                failures.append("Private stock launcher observation close failed")
        for name, fd in (
            ("emulator_fd", self.emulator_fd),
            ("final_fd", self.final_fd),
            ("duckstation_log_fd", self.duckstation_log_fd),
        ):
            if fd is not None:
                try:
                    os.close(fd)
                    setattr(self, name, None)
                except OSError:
                    failures.append("Owned process descriptor close failed")

    def close_native_input(self, failures: list[str]) -> None:
        """Retire the SDL reader before destroying its owned uinput controller."""
        try:
            if self.joystick is not None:
                self.active_sdl().SDL_JoystickClose(self.joystick)
            if self.sdl is not None:
                self.active_sdl().SDL_QuitSubSystem(self.active_sdl().SDL_INIT_JOYSTICK)
        except (OSError, RuntimeError):
            failures.append("Owned SDL discovery close failed")
        try:
            if self.pad is not None:
                self.active_pad().close()
        except (OSError, RuntimeError):
            failures.append("Owned native gamepad close failed")

    def record_final_integrity(self, failures: list[str]) -> None:
        """Record unchanged suite profile and stock binaries after owned teardown."""
        try:
            if self.profile_seeded and digest(PROFILE) != self.profile_hash:
                failures.append("Suite ES profile changed during case")
        except OSError:
            failures.append("Suite ES profile identity unavailable")
        try:
            self.integrity.record_final_hashes()
            self.result["stock_hashes"] = self.integrity.result.get("stock_hashes", {})
        except (OSError, RuntimeError):
            failures.append("Stock input integrity changed or unavailable")

    def close(self) -> list[str]:
        """Close owned resources without counting forced teardown as exit."""
        failures = []
        try:
            self.release_input()
        except (OSError, RuntimeError):
            failures.append("Owned input release failed")
        if self.result["status"] == "failed":
            try:
                self.result["failure_capture"] = capture_checkpoint(
                    self.directory / "emulator-failure.png"
                )
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
                self.result["failure_capture"] = {
                    "status": "unavailable",
                    "checkpoint": "emulator-failure",
                }
        self.stop_owned_processes(failures)
        self.close_process_observers(failures)
        try:
            if self.desktop is not None:
                self.desktop.close()
        except (OSError, RuntimeError):
            failures.append("Owned authenticated display close failed")
        self.close_native_input(failures)
        self.record_final_integrity(failures)
        self.result["captures"] = list(self.captures.values())
        self.result["cleanup"] = {
            "status": "failed" if failures else "passed",
            "errors": failures,
            "forced_emulator_teardown": self.forced,
        }
        if failures or self.forced:
            self.result["status"] = "failed"
        return failures


def _publish_result(probe: EmulatorProbe) -> bool:
    """Publish only selected fixed log fields and the final private-safe report."""
    try:
        publish_selected_log(
            probe.directory,
            [
                probe.case.identifier + ": " + _text(probe.result["status"]),
                *_strings(probe.result["errors"]),
            ],
        )
    except (OSError, ValueError, TypeError):
        probe.result["status"] = "failed"
        _strings(probe.result["errors"]).append("Selected emulator log unavailable")
    try:
        publish_json(probe.directory / "emulator-probe.json", probe.result)
    except (OSError, ValueError, TypeError):
        return False
    else:
        return True


def main() -> int:
    """Run in an inspected app session and publish private-safe evidence."""
    directory = Path(os.environ.get("GOW_NATIVE_RESULTS", ""))
    require(
        directory == Path("/home/retro/.native-evidence") and os.getuid() != 0,
        "Owned native evidence and app UID are required",
    )
    marker = Path("/home/retro/.native-owner").lstat()
    require(
        stat.S_ISREG(marker.st_mode)
        and marker.st_uid == 0
        and not marker.st_mode & 0o022,
        "Disposable native ownership marker missing",
    )
    control = os.environ.get("GOW_EMULATOR_NEGATIVE_CONTROL", "none")
    require(control in CONTROLS, "Unknown emulator negative control")
    probe = EmulatorProbe(
        directory,
        control,
        reproduce_required=os.environ.get("GOW_EMULATOR_REPRODUCE") == "1",
        case=os.environ.get("GOW_EMULATOR_CASE", "nes-fceumm"),
    )

    def interrupted(_number: int, _frame: FrameType | None) -> None:
        message = "Owned emulator diagnostic interrupted"
        raise InterruptedError(message)

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM):
        signal.signal(signum, interrupted)
    signal.alarm(240)
    published = False

    def final_boundary(name: str) -> None:
        try:
            probe.retain_boundary(name)
        except (OSError, RuntimeError, ValueError, TypeError):
            _strings(probe.result["errors"]).append(
                "Causal boundary unavailable: " + name
            )
            probe.result["status"] = "failed"

    try:
        publish_json(
            directory / "startup.json",
            {"uid": os.getuid(), "gid": os.getgid(), "mode": "stock-emulator-exit"},
        )
        probe.run()
    except (
        OSError,
        RuntimeError,
        ValueError,
        ImportError,
        LookupError,
        TypeError,
        ET.ParseError,
        subprocess.SubprocessError,
    ) as error:
        # Never persist arbitrary exceptions containing selected private paths.
        probe.result["errors"] = [
            "Native emulator observation failed",
            type(error).__name__,
        ]
        if isinstance(error, (TransitionError, ProbeError)):
            _strings(probe.result["errors"]).append(str(error))
        probe.result["status"] = "failed"
        probe.result["failure_observation"] = {
            "boundary": probe.boundary,
            "category": (
                "os"
                if isinstance(error, OSError)
                else "subprocess"
                if isinstance(error, subprocess.SubprocessError)
                else "transition"
                if isinstance(error, TransitionError)
                else "probe"
                if isinstance(error, ProbeError)
                else "python"
            ),
            "errno": error.errno if isinstance(error, OSError) else None,
        }
        if probe.process_observation_failure is not None:
            _record(probe.result["failure_observation"])["process"] = (
                probe.process_observation_failure
            )
        final_boundary("failure")
    finally:
        signal.alarm(0)
        final_boundary("cleanup-start")
        try:
            probe.close()
        except (OSError, RuntimeError, ValueError, LookupError, TypeError):
            probe.result["status"] = "failed"
            _strings(probe.result["errors"]).append(
                "Owned emulator cleanup did not complete"
            )
        else:
            final_boundary("cleanup-returned")
        published = _publish_result(probe)
    return (
        0
        if published and probe.result["status"] in ("passed", "skipped-no-media")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
