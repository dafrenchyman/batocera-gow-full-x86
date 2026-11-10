"""Opt-in native frontend, receiver and selected stock-emulator verification.

Host tests inject transport and clock at the lifecycle boundary. Actual native
runs deliver native_remote.py unchanged to sudo Python over stdin, without an
installed helper or saved private request.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shlex
import signal
import stat
import struct
import subprocess
import sys
import time
import uuid
import zlib
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, field, replace
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from batocera_gow.host.common import docker_command
from batocera_gow.host.media_qualification import (
    CaseIdentity,
    NativeObservations,
    Qualification,
    evaluate_qualification,
    load_cases,
)
from batocera_gow.host.native_freshness import BuildSnapshot, DockerImages
from batocera_gow.host.native_matrix import (
    NO_MEDIA,
    RECEIVER_CASES,
    QualifiedInput,
    advertised_coverage,
    aggregate_regression,
    case_identity,
    outcome_counts,
)
from batocera_gow.host.native_remote import (
    EMULATOR_BOUNDARY_FILES,
    InspectionError,
    NativeError,
    number,
    open_directory,
    operation_failure,
    record,
    sequence,
    startup_observation,
    text,
)
from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SSHConfig
from batocera_gow.runtime.media_catalog import (
    DUCKSTATION_PACKAGE_SOURCE,
    EMULATOR_CASES,
    STOCK_SHA256,
    XEMU_HDD_SHA256,
    XEMU_HDD_USE,
    XEMU_PACKAGE_SOURCE,
    XEMU_SDL,
    Catalog,
    EmulatorCase,
    emulator_case,
    emulator_tier,
    load_catalog,
)
from batocera_gow.runtime.mounted_media import (
    XISO_SECTOR_SIZE,
    XISO_VOLUME_OFFSET,
    ContentRoots,
    EffectiveMount,
    MediaError,
)

UINT32_MAX = (1 << 32) - 1
DEVICE_ID_FIELDS = 2
INODE_ID_FIELDS = 3
INPUT_DEVICE_MAJOR = 13
SECCOMP_FILTER = 2
MIN_EMULATOR_LIVE_SECONDS = 2
MAX_GAMEPADS = 64
PNG_SIGNATURE_SIZE = 8
PNG_HEADER_SIZE = 13
MAX_CAPTURE_DIMENSION = 8192
MAX_STARTUP_OBSERVATIONS = 16
FRONTEND_RECEIVER_CASES = ("frontend", "receivers")

EMULATOR_CONTROLS = (
    "none",
    "withhold-readiness",
    "withhold-chord",
    "wrong-window",
    "pre-chord-death",
    "launcher-error",
    "early-native-exit",
)
ENTRYPOINT = [
    "/usr/bin/python3",
    "/opt/gow-full-x86/input_transport.py",
    "--",
    "/opt/gow-full-x86/entrypoint.sh",
]
LIMITS = [
    (
        "Discovery polling has a detection race; it is not atomic server reservation "
        "or strict shared-kernel input isolation."
    ),
    (
        "Exact local image preflight does not disable stock Wolf's automatic-pull "
        "fallback after concurrent external image removal."
    ),
    (
        "Synthetic server input and authenticated server pixels do not prove physical "
        "Moonlight forwarding, decoded client video or heard audio."
    ),
    (
        "Gameplay, menus and other shortcuts remain untested. A smoke subset is not "
        "the full six-backend gate; graceful source removal is not abrupt "
        "crash-recovery proof."
    ),
    (
        "Observed shortcut exit does not qualify graceful shutdown, save persistence "
        "or frontend recovery; stock-log classification is diagnostic only."
    ),
    (
        "A dispatched create without observed running owned container has no "
        "qualified finite cancellation barrier; unresolved state is retained."
    ),
    (
        "Missing-startup diagnostics add read-only observation latency; "
        "a later success does not establish that a timing-sensitive startup "
        "failure is repaired."
    ),
]


def proc_ids_match(value: object, expected: int) -> bool:
    """Accept exactly four proc UID/GID IDs separated by ASCII spaces or tabs."""
    return (
        isinstance(value, str)
        and re.fullmatch(r"[ \t]*[0-9]+(?:[ \t]+[0-9]+){3}[ \t]*", value) is not None
        and all(int(identifier) == expected for identifier in value.split())
    )


class Transport(Protocol):
    """The bounded delivered-request seam, not a deployment client."""

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Return a validated response or fail without echoing private bytes."""
        ...


class Clock(Protocol):
    """Monotonic scheduling injected for deterministic boundary tests."""

    def now(self) -> float:
        """Return monotonic seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Advance or wait without exceeding the caller's remaining budget."""
        ...


class SystemClock:
    """The real entrypoint's monotonic clock."""

    def now(self) -> float:
        """Return monotonic seconds."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Wait a bounded observation interval, never retry an assertion."""
        time.sleep(seconds)


class SSHTransport:
    """Deliver the standalone helper verbatim, keeping requests only in memory."""

    def __init__(self, config: SSHConfig, payload: str) -> None:
        """Borrow validated SSH settings and the checked standalone helper source."""
        self.config, self.payload = config, payload

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Bound the SSH child and discard arbitrary remote output on failure."""
        command = "sudo -n python3 -I -B -c " + shlex.quote(self.payload)
        try:
            result = subprocess.run(  # noqa: S603 - validated SSH argv; only the maintained helper is quoted into the remote command.
                [*self.config.argv(), command],
                input=json.dumps(value),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            msg = "SSH unavailable or deadline expired"
            raise NativeError(msg) from error
        try:
            response = record(json.loads(result.stdout))
        except (ValueError, NativeError) as error:
            msg = "Missing or malformed delivered-helper response"
            raise NativeError(msg) from error
        if result.returncode or response.get("ok") is not True:
            if value.get("action") == "integrity" and response.get("ok") is False:
                try:
                    failure = InspectionError(
                        record(response.get("inspection_failure"))
                    )
                except NativeError:
                    pass
                else:
                    raise failure
            if "operation_failure" in response:
                failure_details = operation_failure(response["operation_failure"])
                description = (
                    text(failure_details["category"])
                    + "/"
                    + text(failure_details["code"])
                )
                if failure_details["errno"] is not None:
                    description += " errno=" + str(failure_details["errno"])
                raise NativeError("Remote operation failed closed: " + description)
            msg = "Remote operation failed closed"
            raise NativeError(msg)
        return record(response.get("result"))


@dataclass(frozen=True)
class Budgets:
    """Finite operator-selected seconds, pending native qualification."""

    call: float = 15
    create: float = 30
    startup: float = 120
    scenario: float = 180
    evidence: float = 30
    cleanup: float = 90
    poll: float = 0.5
    lease: float = 10

    def __post_init__(self) -> None:
        """Require finite deadlines and leases longer than observation intervals."""
        for value in self.as_dict().values():
            number(value)
        if self.lease <= self.poll or self.call < self.poll:
            msg = "Lease/call budgets must exceed the observation interval"
            raise NativeError(msg)

    def as_dict(self) -> dict[str, float]:
        """Expose selected budgets independently of observed timings."""
        return {
            "call": self.call,
            "create": self.create,
            "startup": self.startup,
            "scenario": self.scenario,
            "evidence": self.evidence,
            "cleanup": self.cleanup,
            "poll": self.poll,
            "lease": self.lease,
        }


@dataclass(frozen=True)
class NativeConfig:
    """Only settings required for owned native frontend/receiver execution."""

    image: str
    source: str
    stock_sha256: str
    roots: ContentRoots
    hashes: dict[str, object]
    render_node: str
    video_caps: str
    infrastructure: tuple[str, ...] = ()
    host_root: str = "/etc/wolf"
    local_root: str = "/etc/wolf"
    wolf_container: str = "wolf"
    api_socket: str = "/var/run/wolf/wolf.sock"
    profile: str = "user"
    uid: int = 1000
    gid: int = 1000
    tier: str = "frontend-receivers"
    budgets: Budgets = Budgets()
    selection: dict[str, object] | None = None
    negative_control: str = "none"
    case_selections: dict[str, dict[str, object]] = field(default_factory=dict)
    qualified_inputs: dict[str, QualifiedInput] = field(default_factory=dict)
    expanded_selection: tuple[str, ...] = ()
    project_root: Path = field(kw_only=True)
    catalog: Catalog = field(kw_only=True)
    receiver_case: str | None = None

    def _validate_identity(self) -> None:
        """Require exact build identity, literal paths and non-root execution."""
        if (
            not re.fullmatch(r"sha256:[a-f0-9]{64}", self.image)
            or not re.fullmatch(
                r"(?:[a-f0-9]{40}|worktree-sha256:[a-f0-9]{64})", self.source
            )
            or not re.fullmatch(r"[a-f0-9]{64}", self.stock_sha256)
        ):
            msg = "Exact image/source/stock provenance required"
            raise NativeError(msg)
        for value in (
            self.host_root,
            self.local_root,
            self.api_socket,
            self.render_node,
        ):
            path = Path(value)
            text(value)
            if not path.is_absolute() or str(path) != value or ".." in path.parts:
                msg = "Native paths must be canonical absolute literals"
                raise NativeError(msg)
        if (
            self.uid <= 0
            or self.gid <= 0
            or self.tier
            not in (
                "frontend-receivers",
                "frontend-smoke",
                "receiver-smoke",
                "regression",
                "expanded",
                *(case.tier for case in EMULATOR_CASES),
            )
        ):
            msg = "Non-root identity and explicit native tier required"
            raise NativeError(msg)

    def _validate_matrix_selection(self) -> None:
        """Require complete matrix inventory and identical DuckStation replay inputs."""
        for name, selection in self.case_selections.items():
            declaration = emulator_case(name)
            if self.tier not in ("regression", "expanded") or (
                selection.get("schema") != 1
                or selection.get("system") != declaration.system
            ):
                msg = "Per-case reproduction does not match matrix tier"
                raise NativeError(msg)
        required_cases = (
            EMULATOR_CASES
            if self.tier == "regression"
            else tuple(emulator_case(name) for name in self.qualified_inputs)
            if self.tier == "expanded"
            else ()
        )
        if any(
            path not in self.hashes
            for declaration in required_cases
            for path in declaration.inventory_paths
        ):
            msg = "Selected stock backend inventory is incomplete"
            raise NativeError(msg)
        if self.tier != "expanded" and (
            self.qualified_inputs or self.expanded_selection
        ):
            msg = "Qualification selection requires expanded tier"
            raise NativeError(msg)
        gl = self.case_selections.get("psx-duckstation")
        vk = self.case_selections.get("psx-duckstation-vulkan")
        if gl is not None and vk is not None and gl != vk:
            msg = "Full DuckStation variants require the same selected media"
            raise NativeError(msg)

    def _validate_selection(self) -> None:
        """Bind replay and qualified cases to their stock declarations and tier."""
        if self.negative_control not in EMULATOR_CONTROLS or (
            emulator_tier(self.tier) is None
            and (self.selection is not None or self.negative_control != "none")
        ):
            msg = "Emulator inputs/controls require explicit emulator smoke"
            raise NativeError(msg)
        selected_case = emulator_tier(self.tier)
        if selected_case is not None:
            stock_declaration = self.catalog.system(selected_case.system)
            if (
                selected_case.backend,
                selected_case.core,
            ) not in stock_declaration.backends:
                msg = "Implemented case differs from stock declaration"
                raise NativeError(msg)
            if self.selection is not None and (
                self.selection.get("schema") != 1
                or self.selection.get("system") != selected_case.system
            ):
                msg = "Reproduction system does not match selected case"
                raise NativeError(msg)
            if any(path not in self.hashes for path in selected_case.inventory_paths):
                msg = "Selected stock backend inventory is incomplete"
                raise NativeError(msg)
        self._validate_matrix_selection()

    def _validate_boundary(self) -> None:
        """Validate packaged hashes and explicit infrastructure identities."""
        if any(
            not re.fullmatch(r"[a-f0-9]{64}", value) for value in self.infrastructure
        ):
            msg = "Infrastructure exemptions require exact immutable Docker IDs"
            raise NativeError(msg)
        text(self.video_caps)
        text(self.profile)
        if not self.hashes:
            msg = "Packaged source and stock hashes required"
            raise NativeError(msg)
        for name, digest in self.hashes.items():
            path = Path(name)
            if (
                not path.is_absolute()
                or str(path) != name
                or ".." in path.parts
                or not isinstance(digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", digest)
            ):
                msg = "Canonical packaged paths and SHA-256 hashes required"
                raise NativeError(msg)
        if self.wolf_container.startswith("-"):
            msg = "Wolf container must be an identity, not an option"
            raise NativeError(msg)
        text(self.wolf_container)
        if self.receiver_case is not None and (
            self.receiver_case not in RECEIVER_CASES or self.tier != "receiver-smoke"
        ):
            msg = "A receiver selector requires its explicit receiver tier"
            raise NativeError(msg)

    def __post_init__(self) -> None:
        """Reject invalid frozen native configuration before transport effects."""
        self._validate_identity()
        self._validate_selection()
        self._validate_boundary()


class Artifacts:
    """Exclusive owner-only local publication anchored against symlink escape."""

    def __init__(self, root: Path, run_id: str) -> None:
        """Allocate exclusive owner-only evidence through pinned parents."""
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            msg = "Invalid artifact run identity"
            raise NativeError(msg)
        absolute = root.absolute()
        if ".." in absolute.parts:
            msg = "Artifact root must not traverse parent directories"
            raise NativeError(msg)
        parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in absolute.parts[1:]:
                with suppress(FileExistsError):
                    os.mkdir(part, 0o700, dir_fd=parent)
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                )
                os.close(parent)
                parent = child
            os.mkdir(run_id, 0o700, dir_fd=parent)
            self.descriptor = os.open(
                run_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
        finally:
            os.close(parent)
        self.path = root.absolute() / run_id
        self.pin = os.fstat(self.descriptor)

    def put(self, name: str, data: bytes) -> None:
        """Publish complete fsynced bytes exclusively after checking path ownership."""
        if not re.fullmatch(r"[a-z0-9_-]+\.(json|png|log)", name):
            msg = "Unsafe local artifact name"
            raise NativeError(msg)
        descriptor = open_directory(self.path)
        try:
            current = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if (current.st_dev, current.st_ino, current.st_uid) != (
            self.pin.st_dev,
            self.pin.st_ino,
            os.getuid(),
        ) or current.st_mode & 0o077:
            msg = "Local artifact ownership changed"
            raise NativeError(msg)
        temporary = "." + name + "-" + uuid.uuid4().hex
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=self.descriptor,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(
                temporary,
                name,
                src_dir_fd=self.descriptor,
                dst_dir_fd=self.descriptor,
                follow_symlinks=False,
            )
            try:
                os.unlink(temporary, dir_fd=self.descriptor)
            except OSError:
                # A failed local publication must not leave an apparently
                # committed passing report which authorizes expanded input.
                os.unlink(name, dir_fd=self.descriptor)
                raise
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=self.descriptor)

    def close(self) -> None:
        """Release the artifact descriptor without deleting retained evidence."""
        os.close(self.descriptor)


def read_private_artifact(path: Path, maximum: int = 16 * 1024 * 1024) -> bytes:
    """Read bounded owner-only evidence through no-follow pinned components.

    Args:
        path: Exact selected local artifact, never a directory scan.
        maximum: Maximum allowed bytes, including for retained real PNG evidence.

    Returns:
        Stable file bytes. No content is printed or copied into public output.

    Raises:
        NativeError: If ownership, privacy, type, size or read identity differs.
    """
    parent = open_directory(path.absolute().parent)
    try:
        parent_info = os.fstat(parent)
        if parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o077:
            msg = "Reproduction parent must be an owner-only directory"
            raise NativeError(msg)
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_mode & 0o077
            or before.st_nlink != 1
            or before.st_size > maximum
        ):
            msg = "Reproduction record must be bounded, private and regular"
            raise NativeError(msg)
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if len(data) > maximum or (
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (after.st_ino, after.st_size, after.st_mtime_ns):
            msg = "Reproduction record changed during read"
            raise NativeError(msg)
    return data


def read_reproduction_record(path: Path) -> dict[str, object]:
    """Read a private bounded JSON replay record without following symlinks.

    Native mounted-media validation still rechecks its complete selected member
    identity immediately before use. This local reader never opens media itself.
    """
    return record(json.loads(read_private_artifact(path, 1024 * 1024)))


def sanitize(value: object) -> object:
    """Discard sensitive log lines/keys before any evidence persistence."""
    forbidden = re.compile(
        r"(?i)(authorization|bearer\s|access[_ -]?token|password|pairing|"
        r"aes[_ -]?(?:key|iv)|client[_ -]?secret|private[_ -]?key|"
        r"gh[pousr]_[A-Za-z0-9]+|BEGIN .*PRIVATE KEY)"
    )
    if isinstance(value, str):
        return "\n".join(
            "[redacted sensitive log line]" if forbidden.search(line) else line
            for line in value.splitlines()
        )
    if isinstance(value, dict):
        return {
            str(k): sanitize(v)
            for k, v in value.items()
            if not forbidden.search(str(k))
            and str(k) not in ("environment", "argv", "wrapper")
        }
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


def selected_probe_evidence(probe: dict[str, object]) -> dict[str, object]:
    """Retain complete selected consumer proof without arbitrary environment data.

    The summary sanitizer stays deliberately lossy. Only the final emulator-probe
    capture retains the fixed, nonsecret SDL observations required by the native
    validators. Invalid values are omitted, never replaced with expected values.
    Missing observations therefore still fail validation on replay.
    """
    retained = record(sanitize(probe))
    consumption = probe.get("native_device_consumption")
    if not isinstance(consumption, dict):
        return retained
    environment = consumption.get("environment")
    backend = probe.get("backend")
    if not isinstance(environment, dict) or backend not in ("duckstation", "xemu"):
        return retained
    selected: dict[str, object] = {}
    guid = environment.get("sdl_mapping_guid")
    if isinstance(guid, str) and re.fullmatch(r"[a-f0-9]{32}", guid):
        selected["sdl_mapping_guid"] = guid
    consumed = environment.get("suite_mapping_consumed")
    if type(consumed) is bool:
        selected["suite_mapping_consumed"] = consumed
    for key, expected in (
        ("XDG_CONFIG_HOME", "/userdata/system/configs"),
        ("SDL_JOYSTICK_HIDAPI", "0")
        if backend == "duckstation"
        else ("LC_NUMERIC", "C"),
    ):
        if environment.get(key) == expected:
            selected[key] = environment[key]
    retained_consumption = record(retained["native_device_consumption"])
    retained_consumption["environment"] = selected
    retained["native_device_consumption"] = retained_consumption
    return retained


def _png_dimensions(chunk: bytes) -> tuple[int, int]:
    """Validate the exact supported RGB PNG header and bounded dimensions."""
    width, height, depth, colour, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", chunk
    )
    if (
        not 0 < width <= MAX_CAPTURE_DIMENSION
        or not 0 < height <= MAX_CAPTURE_DIMENSION
        or (depth, colour, compression, filtering, interlace) != (8, 2, 0, 0, 0)
    ):
        msg = "Unsupported capture PNG encoding"
        raise NativeError(msg)
    return width, height


def _png_pixels(compressed: bytearray, width: int, height: int) -> None:
    """Require one complete RGB pixel stream within its declared dimensions."""
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, height * (width * 3 + 1) + 1)
    except zlib.error as error:
        msg = "Capture PNG has invalid compressed data"
        raise NativeError(msg) from error
    if len(pixels) != height * (width * 3 + 1) or not decoder.eof:
        msg = "Capture PNG has invalid pixel data"
        raise NativeError(msg)


def png_identity(data: bytes) -> tuple[int, int]:
    """Validate actual PNG structure/CRCs rather than accepting a named file."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        msg = "Capture is not PNG"
        raise NativeError(msg)
    offset, width, height, compressed, ended = 8, 0, 0, bytearray(), False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        if (
            offset + length + 12 > len(data)
            or zlib.crc32(kind + chunk) & UINT32_MAX
            != struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])[0]
        ):
            msg = "Malformed capture PNG chunk"
            raise NativeError(msg)
        if kind == b"IHDR":
            if offset != PNG_SIGNATURE_SIZE or length != PNG_HEADER_SIZE:
                msg = "Malformed capture PNG header"
                raise NativeError(msg)
            width, height = _png_dimensions(chunk)
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            ended = length == 0 and offset + 12 == len(data)
            break
        offset += length + 12
    if not width or not height or not ended or not compressed:
        msg = "Incomplete capture PNG"
        raise NativeError(msg)
    _png_pixels(compressed, width, height)
    return width, height


@dataclass
class NativeCase:
    """Observed ownership and lifecycle evidence for exactly one native home."""

    name: str
    case_id: str
    token: str
    payload: dict[str, object]
    runner_hash: str
    pin: dict[str, object] | None = None
    lobby_id: str | None = None
    container_id: str | None = None
    create_dispatched: bool = False
    startup_resolved: bool = False
    gate_open: bool = False
    report: dict[str, object] | None = None
    startup_observations: list[dict[str, object]] = field(default_factory=list)
    startup_observations_truncated: bool = False
    captures: dict[str, str] = field(default_factory=dict)
    source_digests: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    cleanup: dict[str, object] = field(
        default_factory=lambda: {"status": "not-run", "attempts": []}
    )
    isolation: dict[str, object] | None = None
    interruption: str | None = None


class Coordinator:
    """Own finite frontend/receiver transitions and independent bounded cleanup."""

    def __init__(
        self,
        config: NativeConfig,
        transport: Transport,
        clock: Clock,
        artifacts: Artifacts,
        run_id: str,
    ) -> None:
        """Borrow lifecycle boundaries and own this run's observations."""
        self.config, self.transport, self.clock, self.artifacts, self.run_id = (
            config,
            transport,
            clock,
            artifacts,
            run_id,
        )
        self.wolf_id: str | None = None
        self.interrupted: str | None = None
        self.replay_selections = dict(config.case_selections)
        self.phase = "configuration"
        self.timings: list[dict[str, object]] = []
        self.cases: list[NativeCase] = []
        self.preflight: dict[str, object] = {}
        self.verify_inputs: Callable[[], None] | None = None

    def selection_for(self, name: str) -> dict[str, object] | None:
        """Resolve exactly one case's replay input, never reroll a failed selection."""
        qualified = self.config.qualified_inputs.get(name)
        counterpart = {
            "psx-duckstation": "psx-duckstation-vulkan",
            "psx-duckstation-vulkan": "psx-duckstation",
        }.get(name, "")
        return (
            qualified.selection
            if qualified is not None
            else self.replay_selections.get(
                name, self.replay_selections.get(counterpart, self.config.selection)
            )
        )

    def _qualified_case_row(
        self, path: Path, identity: CaseIdentity, proof: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Verify immutable historical success and the exact selected row."""
        report_bytes = read_private_artifact(path.parent / "report.json")
        if hashlib.sha256(report_bytes).hexdigest() != proof.get("report_sha256"):
            msg = "Qualified report identity changed"
            raise NativeError(msg)
        report = record(json.loads(report_bytes))
        if (
            report.get("status") != "passed"
            or report.get("image") != self.config.image
            or report.get("source") != self.config.source
            or report.get("publication_error")
            or report.get("interruption")
            or report.get("errors")
        ):
            msg = "Qualified run evidence is nonpassing"
            raise NativeError(msg)
        rows = [
            record(row)
            for row in sequence(report.get("cases"))
            if record(row).get("name") == identity.case
        ]
        if len(rows) != 1:
            msg = "Qualified case is missing or duplicated"
            raise NativeError(msg)
        row = rows[0]
        summary = record(row.get("report"))
        if (
            row.get("status") != "passed"
            or record(row.get("cleanup")).get("status") != "passed"
        ):
            msg = "Qualified case behavior or cleanup is nonpassing"
            raise NativeError(msg)
        return row, summary

    def _qualified_probe(
        self,
        path: Path,
        identity: CaseIdentity,
        row: dict[str, object],
        summary: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, str]]:
        """Rehash all retained artifacts and recover complete native proof."""
        captures = record(row.get("captures"))
        probe_name = identity.case + "-emulator-probe.json"
        if probe_name not in captures:
            msg = "Required qualified final emulator-probe capture missing"
            raise NativeError(msg)
        probe: dict[str, object] | None = None
        verified: dict[str, str] = {}
        for name, digest in captures.items():
            if not re.fullmatch(r"[a-z0-9_-]+\.(json|png|log)", name):
                msg = "Invalid qualified artifact identity"
                raise NativeError(msg)
            data = read_private_artifact(path.parent / name)
            if hashlib.sha256(data).hexdigest() != digest:
                msg = "Qualified evidence missing or changed"
                raise NativeError(msg)
            if name.endswith(".png"):
                png_identity(data)
            verified[name] = text(digest)
            if name == probe_name:
                probe = record(json.loads(data))
        if probe is None or sanitize(probe) != summary:
            msg = "Qualified final probe differs from persisted summary"
            raise NativeError(msg)
        if emulator_case(identity.case).backend in ("duckstation", "xemu") and (
            not isinstance(
                record(probe.get("native_device_consumption")).get("environment"), dict
            )
        ):
            msg = (
                "Qualified final probe lacks selected native-consumption environment; "
                "legacy lossy evidence cannot authorize replay"
            )
            raise NativeError(msg)
        return probe, verified

    def load_qualification(self, path: Path) -> QualifiedInput:
        """Revalidate a selected private proof and every retained evidence artifact.

        The historical report is immutable. Its digest-bound final probe capture
        supplies the complete selected native assertions; the persisted row is
        only a sanitized summary. Both must agree before the unchanged validator
        and exact-input identity derivation can authorize replay.
        """
        proof_bytes = read_private_artifact(path, 1024 * 1024)
        proof = record(json.loads(proof_bytes))
        qualification = record(proof.get("qualification"))
        value = record(qualification.get("identity"))
        identity = CaseIdentity(
            **{key: text(value.get(key)) for key in CaseIdentity.__dataclass_fields__}
        )
        if (
            proof.get("schema") != 1
            or qualification.get("status") != "qualified"
            or identity.image != self.config.image
            or identity.source != self.config.source
            or identity.catalog != STOCK_SHA256
            or proof.get("report") != "report.json"
        ):
            msg = "Qualification does not match exact current inputs"
            raise NativeError(msg)
        if any(
            name not in self.config.hashes
            for name in emulator_case(identity.case).inventory_paths
        ):
            msg = "Selected stock backend inventory is incomplete"
            raise NativeError(msg)
        row, summary = self._qualified_case_row(path, identity, proof)
        probe, verified = self._qualified_probe(path, identity, row, summary)
        historical = self.make_case(identity.case)
        historical.report, historical.captures = probe, verified
        self.validate_report(historical)
        if (
            case_identity(identity.case, probe, self.config.image, self.config.source)
            != identity
        ):
            msg = "Qualification identity differs from observed inputs"
            raise NativeError(msg)
        selection = read_reproduction_record(
            path.parent / (identity.case + "-selection.json")
        )
        if (
            selection.get("digest") != identity.media
            or selection.get("system") != identity.system
        ):
            msg = "Qualified replay identity differs"
            raise NativeError(msg)
        return QualifiedInput(
            identity, selection, probe, hashlib.sha256(proof_bytes).hexdigest()
        )

    def base(self, action: str, case: NativeCase | None = None) -> dict[str, object]:
        """Assemble only required request fields, never the host environment."""
        c = self.config
        result: dict[str, object] = {
            "action": action,
            "wolf_container": self.wolf_id or c.wolf_container,
            "api_socket": c.api_socket,
            "image": c.image,
            "source": c.source,
            "stock_sha256": c.stock_sha256,
            "host_root": c.host_root,
            "local_root": c.local_root,
            "uid": c.uid,
            "gid": c.gid,
            "profile": c.profile,
            "root_pin": self.preflight.get("root_pin"),
        }
        result["render_node"] = c.render_node
        result["content_roots"] = {"roms": c.roots.roms, "bios": c.roots.bios}
        if case is not None:
            result.update(
                case_id=case.case_id,
                token=case.token,
                pin=case.pin,
                lobby_id=case.lobby_id,
                container_id=case.container_id,
                runner_hash=case.runner_hash,
                lobby_pin=case.payload.get("pin"),
                startup_resolved=case.startup_resolved or not case.create_dispatched,
            )
        return result

    def call(
        self,
        action: str,
        deadline: float,
        case: NativeCase | None = None,
        **values: object,
    ) -> dict[str, object]:
        """Enforce deadline boundaries before and after every external call."""
        started = self.clock.now()
        remaining = deadline - started
        if remaining <= 0:
            raise NativeError("Deadline expired before " + action)
        duration = min(
            remaining,
            self.config.budgets.create
            if action == "create"
            else self.config.budgets.call,
        )
        request = self.base(action, case)
        request.update(values, timeout=max(0.001, duration - min(0.5, duration / 10)))
        try:
            result = self.transport.request(request, duration)
            if self.clock.now() >= min(deadline, started + duration):
                raise NativeError("Deadline expired during " + action)
            return result
        finally:
            self.timings.append(
                {
                    "phase": self.phase,
                    "operation": action,
                    "started": started,
                    "elapsed": self.clock.now() - started,
                    "deadline": deadline,
                    "call_budget": duration,
                }
            )

    def _snapshot_rows(
        self, deadline: float, case: NativeCase | None
    ) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
        """Require complete independently observed session, lobby and container rows."""
        snapshot = self.call("snapshot", deadline, case)
        if type(snapshot.get("session_count")) is not int:
            msg = "Incomplete session discovery"
            raise NativeError(msg)
        lobbies = [record(v) for v in sequence(snapshot.get("lobbies"))]
        containers = [record(v) for v in sequence(snapshot.get("containers"))]
        return snapshot, lobbies, containers

    def _owned_containers(
        self, containers: list[dict[str, object]], case: NativeCase | None
    ) -> list[dict[str, object]]:
        """Match independent container owner, immutable image and home identities."""
        owned_containers: list[dict[str, object]] = []
        for container in containers:
            if (
                case is not None
                and container.get("owner") == case.token
                and container.get("image") == self.config.image
                and container.get("home")
                == [str(Path(self.config.host_root) / "test-runs" / case.case_id)]
            ):
                owned_containers.append(container)
            elif case is not None and (
                container.get("owner") == case.token
                or container.get("id") == case.container_id
            ):
                msg = "Observed owned container identity changed"
                raise InterruptedError(msg)
        return owned_containers

    def _bind_observed_resources(
        self,
        case: NativeCase,
        owned_lobbies: list[dict[str, object]],
        owned_containers: list[dict[str, object]],
    ) -> None:
        """Bind discovered identities and require observed actual startup."""
        if owned_lobbies:
            observed = text(owned_lobbies[0].get("id"))
            if case.lobby_id is not None and case.lobby_id != observed:
                msg = "Lobby identity changed"
                raise NativeError(msg)
            case.lobby_id = observed
        if owned_containers:
            observed = text(owned_containers[0].get("id"))
            if case.container_id is not None and case.container_id != observed:
                msg = "Container identity changed"
                raise NativeError(msg)
            case.container_id = observed
            if owned_containers[0].get("running") is True:
                # Observing actual startup resolves a lost create response,
                # but an absent instantaneous scan never cancels dispatch.
                case.startup_resolved = True

    def _foreign_containers(
        self,
        containers: list[dict[str, object]],
        owned_containers: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Classify every active foreign container without treating unknown as idle."""
        active_foreign: list[dict[str, object]] = []
        for container in containers:
            if (
                type(container.get("running")) is not bool
                or type(container.get("paused")) is not bool
            ):
                msg = "Incomplete Docker activity discovery"
                raise NativeError(msg)
            if not container["running"] and not container["paused"]:
                continue
            if container in owned_containers or container.get("id") == self.wolf_id:
                continue
            if (
                container.get("native") is True
                or container.get("id") not in self.config.infrastructure
            ):
                active_foreign.append(container)
        return active_foreign

    def discover(
        self, deadline: float, case: NativeCase | None, *, enforce_idle: bool = True
    ) -> dict[str, object]:
        """Recover identities from independent markers, never a name alone."""
        if self.clock.now() >= deadline:
            msg = "Discovery phase deadline expired"
            raise NativeError(msg)
        try:
            snapshot, lobbies, containers = self._snapshot_rows(deadline, case)
        except (NativeError, OSError, ValueError) as error:
            if case is not None and enforce_idle:
                self.interrupted = "Reliable discovery lost"
                raise InterruptedError(self.interrupted) from error
            raise
        owned_lobbies = [
            lobby
            for lobby in lobbies
            if (
                case is not None
                and lobby.get("name") == case.case_id
                and lobby.get("profile") == self.config.profile
                and lobby.get("runner_hash") == case.runner_hash
                and lobby.get("pin_required") is True
            )
        ]
        owned_containers = self._owned_containers(containers, case)
        if len(owned_lobbies) > 1 or len(owned_containers) > 1:
            msg = "Ambiguous owned native resources"
            raise NativeError(msg)
        if case is not None:
            self._bind_observed_resources(case, owned_lobbies, owned_containers)
        unrelated = [v for v in lobbies if v not in owned_lobbies]
        active_foreign = self._foreign_containers(containers, owned_containers)
        contention = bool(
            snapshot["session_count"]
            or unrelated
            or active_foreign
            or any(v.get("connected") != 0 for v in owned_lobbies)
        )
        if contention:
            if case is not None:
                self.interrupted = (
                    "Unrelated native activity or unclassified active "
                    "container detected"
                )
                case.interruption = self.interrupted
            if enforce_idle:
                msg = (
                    "Unrelated native activity or unclassified active "
                    "container detected"
                )
                raise InterruptedError(msg)
        return {"lobbies": owned_lobbies, "containers": owned_containers}

    def make_case(self, name: str) -> NativeCase:
        """Use independent homes and collision-resistant capability identities."""
        if name not in ("frontend", "receivers"):
            emulator_case(name)
        c = self.config
        case_id = self.run_id + "-" + name
        token = uuid.uuid4().hex + uuid.uuid4().hex
        env = [
            "LANG=en_US.UTF-8",
            "LC_ALL=en_US.UTF-8",
            "GOW_NATIVE_RESULTS=/home/retro/.native-evidence",
            "GOW_NATIVE_LEASE=/home/retro/.native-control/lease",
            "GOW_NATIVE_FRONTEND_TIMEOUT=" + str(c.budgets.scenario),
        ]
        options: dict[str, object] = {
            "Labels": {"io.gow.integration.owner": token},
            "HostConfig": {
                "IpcMode": "private",
                "Privileged": False,
                "ShmSize": 2 * 1024**3,
                "NetworkMode": "bridge",
                "CapAdd": ["NET_ADMIN", "SYS_NICE", "SYS_PTRACE"],
            },
        }
        if name == "receivers":
            options["Cmd"] = [
                "/usr/bin/python3",
                "/opt/gow-full-x86/transport_probe.py",
            ]
            env.extend(
                [
                    "GOW_INPUT_TRIAL_RESULTS=/home/retro/.native-evidence",
                    "GOW_INPUT_TRIAL_GATE=/home/retro/.native-control/lease",
                ]
            )
            if c.receiver_case is not None:
                env.append("GOW_INPUT_TRIAL_CASE=" + c.receiver_case)
        if any(case.identifier == name for case in EMULATOR_CASES):
            options["Cmd"] = [
                "/usr/bin/python3",
                "/opt/gow-full-x86/emulator_probe.py",
            ]
            env.append("GOW_EMULATOR_NEGATIVE_CONTROL=" + c.negative_control)
            env.append("GOW_EMULATOR_CASE=" + name)
            if self.selection_for(name) is not None:
                env.append("GOW_EMULATOR_REPRODUCE=1")
        runner: dict[str, object] = {
            "type": "docker",
            "name": "GowNative" + self.run_id,
            "image": c.image,
            "mounts": c.roots.wolf_mounts(),
            "devices": ["/dev/uinput:/dev/uinput:rwm"],
            "env": env,
            "ports": [],
            "base_create_json": json.dumps(options, separators=(",", ":")),
        }
        payload: dict[str, object] = {
            "profile_id": c.profile,
            "name": case_id,
            "pin": [int(v) for v in str(int(uuid.uuid4().hex[:8], 16)).zfill(10)],
            "multi_user": False,
            "stop_when_everyone_leaves": False,
            "runner_state_folder": "test-runs/" + case_id,
            "runner": runner,
            "video_settings": {
                "width": 1280,
                "height": 720,
                "refresh_rate": 60,
                "wayland_render_node": c.render_node,
                "runner_render_node": c.render_node,
                "video_producer_buffer_caps": c.video_caps,
            },
            "audio_settings": {"channel_count": 2},
            "client_settings": {"run_uid": c.uid, "run_gid": c.gid},
        }
        digest = hashlib.sha256(
            json.dumps(runner, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return NativeCase(
            name,
            case_id,
            token,
            payload,
            digest,
        )

    def _validate_container_process(
        self, case: NativeCase, container: dict[str, object]
    ) -> None:
        """Validate effective image, command, namespaces and supervisor capabilities."""
        config, host = (
            record(container.get("Config")),
            record(container.get("HostConfig")),
        )
        state = record(container.get("State"))
        expected_command = (
            ["/opt/gow-full-x86/frontend.sh"]
            if case.name == "frontend"
            else [
                "/usr/bin/python3",
                "/opt/gow-full-x86/"
                + (
                    "emulator_probe.py"
                    if any(item.identifier == case.name for item in EMULATOR_CASES)
                    else "transport_probe.py"
                ),
            ]
        )
        if (
            config.get("Entrypoint") != ENTRYPOINT
            or config.get("Cmd") != expected_command
            or container.get("Image") != self.config.image
            or state.get("Running") is not True
        ):
            msg = "Effective image/command/supervisor mismatch"
            raise NativeError(msg)
        added_caps = [
            text(v).removeprefix("CAP_") for v in sequence(host.get("CapAdd"))
        ]
        if (
            host.get("Privileged") is not False
            or host.get("PidMode") not in ("", "private")
            or host.get("IpcMode") != "private"
            or host.get("NetworkMode") != "bridge"
            or host.get("ShmSize") != 2 * 1024**3
            or sorted(added_caps) != ["NET_ADMIN", "SYS_NICE", "SYS_PTRACE"]
            or host.get("CapDrop") not in (None, [])
            or host.get("SecurityOpt") not in (None, [], ["no-new-privileges"])
        ):
            msg = "Effective namespace/capability/seccomp/shared-memory mismatch"
            raise NativeError(msg)

    def _validate_container_mounts(
        self,
        case: NativeCase,
        container: dict[str, object],
        inspection: dict[str, object],
    ) -> None:
        """Require exact homes and read-only content without source shadows."""
        mounts = [
            EffectiveMount.from_docker(v) for v in sequence(container.get("Mounts"))
        ]
        canonical_roots = record(inspection.get("content_roots"))
        ContentRoots(
            text(canonical_roots.get("roms")), text(canonical_roots.get("bios"))
        ).validate_mounts(mounts)
        home = str(Path(self.config.host_root) / "test-runs" / case.case_id)
        for destination, source in (
            ("/home/retro", home),
            ("/run/udev", home + "/udev"),
        ):
            matches = [v for v in mounts if v.destination.rstrip("/") == destination]
            if (
                len(matches) != 1
                or matches[0].kind != "bind"
                or matches[0].source != source
                or matches[0].writable is not True
            ):
                msg = "Automatic native home/udev binding mismatch"
                raise NativeError(msg)
        local_runtime = Path(text(self.preflight.get("runtime_local")))
        host_runtime = Path(text(self.preflight.get("runtime_host")))
        fake_udev = [m for m in mounts if m.destination == "/usr/bin/fake-udev"]
        if (
            len(fake_udev) != 1
            or fake_udev[0].source != self.config.host_root + "/fake-udev"
            or fake_udev[0].kind != "bind"
        ):
            msg = "Automatic installed fake-udev binding missing or changed"
            raise NativeError(msg)
        for mount in mounts:
            destination = mount.destination.rstrip("/")
            if destination in (
                "/home/retro",
                "/run/udev",
                "/home/retro/userdata/roms",
                "/home/retro/userdata/bios",
                "/usr/bin/fake-udev",
            ):
                continue
            if destination == "/usr/nvidia":
                driver = record(self.preflight.get("driver_mount"))
                if mount.kind != "volume" or mount.source != driver.get("source"):
                    msg = "Native NVIDIA driver volume mismatch"
                    raise NativeError(msg)
                continue
            target = Path(destination)
            if (
                target.parent == local_runtime
                and re.fullmatch(r"(?:wayland-[0-9]+|pulse-socket)", target.name)
                and mount.kind == "bind"
                and mount.source == str(host_runtime / target.name)
            ):
                continue
            msg = "Unknown effective mount or packaged-source/stock shadow"
            raise NativeError(msg)

    def _validate_container_environment(
        self, case: NativeCase, config: dict[str, object]
    ) -> None:
        """Require exact UID/GID and diagnostic permissions without duplicate keys."""
        environment = [text(v) for v in sequence(config.get("Env"))]
        if (
            environment.count("PUID=" + str(self.config.uid)) != 1
            or environment.count("PGID=" + str(self.config.gid)) != 1
        ):
            msg = "Effective app UID/GID contract mismatch"
            raise NativeError(msg)
        for expected in sequence(record(case.payload.get("runner")).get("env")):
            setting = text(expected)
            key = setting.split("=", 1)[0]
            if [value for value in environment if value.split("=", 1)[0] == key] != [
                setting
            ]:
                msg = "Effective diagnostic permission/evidence environment mismatch"
                raise NativeError(msg)

    def _validate_container_devices(self, host: dict[str, object]) -> None:
        """Validate actual uinput access and the complete native device allowlist."""
        devices = [record(v) for v in sequence(host.get("Devices"))]
        if not any(
            v.get("PathOnHost") == "/dev/uinput"
            and v.get("PathInContainer") == "/dev/uinput"
            and set(text(v.get("CgroupPermissions"))) == set("rwm")
            for v in devices
        ):
            msg = "Effective native input permission missing"
            raise NativeError(msg)
        expected_rules = sorted(
            text(v) for v in sequence(self.preflight.get("device_rules"))
        )
        if (
            sorted(text(v) for v in sequence(host.get("DeviceCgroupRules")))
            != expected_rules
        ):
            msg = "Unknown or incomplete native device cgroup rules"
            raise NativeError(msg)
        device_pattern = (
            r"/dev/(?:uinput|input/event[0-9]+|hidraw[0-9]+|"
            r"dri/(?:card[0-9]+|renderD[0-9]+)|"
            r"nvidia(?:[0-9]+|ctl|-modeset|-uvm(?:-tools)?|"
            r"-caps/nvidia-cap[0-9]+))"
        )
        if any(
            v.get("PathOnHost") != v.get("PathInContainer")
            or not re.fullmatch(device_pattern, text(v.get("PathInContainer")))
            or not set(text(v.get("CgroupPermissions"))).issubset(set("rwm"))
            for v in devices
        ):
            msg = "Unknown native device access"
            raise NativeError(msg)

    def _validate_credentials(
        self, integrity: dict[str, object]
    ) -> list[dict[str, object]]:
        """Require inspected stock hashes and capability-free app credentials."""
        credentials = [record(v) for v in sequence(integrity.get("credentials"))]
        uinput = sequence(integrity.get("uinput"))
        userdata = record(integrity.get("userdata"))
        if (
            userdata.get("link") != "/home/retro/userdata"
            or len(sequence(userdata.get("identity"))) != INODE_ID_FIELDS
        ):
            msg = "Native userdata binding is not established"
            raise NativeError(msg)
        if (
            integrity.get("hashes") != self.config.hashes
            or integrity.get("supervisor_pid") != 1
            or integrity.get("effective_seccomp") != SECCOMP_FILTER
            or len(uinput) != DEVICE_ID_FIELDS
            or any(type(v) is not int or v < 0 for v in uinput)
        ):
            msg = "Incomplete packaged integrity/input observations"
            raise NativeError(msg)
        if not credentials or any(
            not proc_ids_match(v.get("Uid"), self.config.uid)
            or not proc_ids_match(v.get("Gid"), self.config.gid)
            or any(
                v.get(key) != "0000000000000000"
                for key in ("CapInh", "CapPrm", "CapEff", "CapAmb")
            )
            or v.get("NoNewPrivs") != "1"
            for v in credentials
        ):
            msg = "Incomplete capability-free app identity observations"
            raise NativeError(msg)
        return credentials

    def _validate_actor_lineage(self, actors: list[dict[str, object]]) -> None:
        """Prove all approved input actors descend from one pinned application root."""
        by_pid = {actor["pid"]: actor for actor in actors}
        roots = {actor["application_root_pid"] for actor in actors}
        if len(by_pid) != len(actors) or len(roots) != 1:
            msg = "Incomplete approved native uinput actor observations"
            raise NativeError(msg)
        root = next(iter(roots))
        if root not in by_pid or by_pid[root]["parent_pid"] != 1:
            msg = "Incomplete approved native uinput actor observations"
            raise NativeError(msg)
        for actor in actors:
            ancestor = actor["pid"]
            visited: set[object] = set()
            while ancestor != root:
                if ancestor in visited or ancestor not in by_pid:
                    msg = "Incomplete approved native uinput actor observations"
                    raise NativeError(msg)
                visited.add(ancestor)
                ancestor = by_pid[ancestor]["parent_pid"]

    def _validate_uinput_actors(
        self, integrity: dict[str, object], credentials: list[dict[str, object]]
    ) -> None:
        """Require observed read/write access for every approved input actor."""
        approved = sequence(integrity.get("approved_process_ids"))
        actors = [record(v) for v in sequence(integrity.get("uinput_actors"))]
        if (
            not approved
            or any(type(pid) is not int or pid <= 1 for pid in approved)
            or len(set(approved)) != len(approved)
            or not actors
        ):
            msg = "Incomplete approved native uinput actor observations"
            raise NativeError(msg)
        for actor in actors:
            for key in (
                "pid",
                "parent_pid",
                "start_time_ticks",
                "application_root_pid",
            ):
                number = actor.get(key)
                minimum = 1 if key in ("pid", "application_root_pid") else 0
                if type(number) is not int or number <= minimum:
                    msg = "Incomplete approved native uinput actor observations"
                    raise NativeError(msg)
            if (
                actor.get("read_write") is not True
                or actor["pid"] not in approved
                or not any(c.get("pid") == actor["pid"] for c in credentials)
            ):
                msg = "Incomplete approved native uinput actor observations"
                raise NativeError(msg)
        self._validate_actor_lineage(actors)

    def inspect(self, case: NativeCase, deadline: float) -> None:
        """Close the input gate unless effective packaged isolation is complete."""
        inspection = self.call("inspect", deadline, case)
        container = record(inspection.get("container"))
        config, host = (
            record(container.get("Config")),
            record(container.get("HostConfig")),
        )
        self._validate_container_process(case, container)
        self._validate_container_mounts(case, container, inspection)
        self._validate_container_environment(case, config)
        self._validate_container_devices(host)
        integrity = self.call("integrity", deadline, case, hashes=self.config.hashes)
        credentials = self._validate_credentials(integrity)
        self._validate_uinput_actors(integrity, credentials)
        case.isolation = {
            "private_pid_ipc_network": True,
            "default_seccomp": True,
            "shared_memory_bytes": host.get("ShmSize"),
            "capabilities": host.get("CapAdd"),
            "automatic_home_udev": True,
            "readonly_content": True,
            "packaged_integrity": integrity,
        }

    def _retain_startup_observation(
        self, case: NativeCase, response: dict[str, object]
    ) -> None:
        """Retain bounded safe startup observations and reject fatal codes."""
        observation = startup_observation(response["startup_observation"])
        previous = case.startup_observations
        if not previous or previous[-1]["observation"] != observation:
            row: dict[str, object] = {
                "phase": self.phase,
                "observed": self.clock.now(),
                "observation": observation,
            }
            if len(previous) == MAX_STARTUP_OBSERVATIONS:
                previous[-1] = row
                case.startup_observations_truncated = True
            else:
                previous.append(row)
        if (
            self.phase == case.name + ":startup"
            and observation["container"] == "present"
        ):
            codes = sequence(record(observation["logs"])["failure_codes"])
            if codes:
                raise NativeError(
                    "Native startup failed: " + ", ".join(text(code) for code in codes)
                )

    def _retain_evidence_file(
        self,
        case: NativeCase,
        name: str,
        encoded: object,
        report_name: str,
        selected: Sequence[str],
    ) -> None:
        """Verify selected file identity before private exclusive publication."""
        if name not in selected:
            msg = "Unrequested remote evidence was returned"
            raise NativeError(msg)
        data = base64.b64decode(text(encoded), validate=True)
        key = case.name + "-" + name
        digest = hashlib.sha256(data).hexdigest()
        if key in case.source_digests and case.source_digests[key] != digest:
            msg = "Published source evidence identity changed"
            raise NativeError(msg)
        case.source_digests[key] = digest
        if name.endswith(".json"):
            value = record(json.loads(data))
            if name == report_name:
                case.report = value
            # Selected paths belong only in ticket01's private record.
            if name != "selection.json":
                retained = (
                    selected_probe_evidence(value)
                    if name == "emulator-probe.json"
                    else sanitize(value)
                )
                data = json.dumps(retained, indent=2, sort_keys=True).encode() + b"\n"
        elif name.endswith(".png"):
            png_identity(data)
        elif name == "selected.log":
            data = str(sanitize(data.decode("utf-8"))).encode()
        if key not in case.captures:
            self.artifacts.put(key, data)
            case.captures[key] = hashlib.sha256(data).hexdigest()

    def collect(
        self, case: NativeCase, deadline: float, *, diagnose_missing: bool = False
    ) -> bool:
        """Transfer sanitized diagnostics and complete selected proof before removal."""
        report_name = (
            "frontend-probe.json"
            if case.name == "frontend"
            else "emulator-probe.json"
            if any(item.identifier == case.name for item in EMULATOR_CASES)
            else "transport-probe.json"
        )
        captures = (
            ["frontend-ready.png", "frontend-failure.png"]
            if case.name == "frontend"
            else [
                "emulator-before-exit.png",
                "emulator-failure.png",
                "selection.json",
                *EMULATOR_BOUNDARY_FILES,
            ]
            if any(item.identifier == case.name for item in EMULATOR_CASES)
            else [*[name + ".png" for name in RECEIVER_CASES], "receiver-failure.png"]
        )
        selected = ["startup.json", "selected.log", report_name, *captures]
        response = self.call(
            "collect",
            deadline,
            case,
            files=selected,
            observe_incomplete=diagnose_missing,
        )
        if "startup_observation" in response:
            self._retain_startup_observation(case, response)
        files = record(response.get("files"))
        failures: list[str] = []
        for unavailable in sequence(response.get("unavailable", [])):
            if unavailable not in selected:
                msg = "Unrequested remote evidence failure was returned"
                raise NativeError(msg)
            failures.append("Selected evidence unavailable: " + text(unavailable))
        # Validate and retain independent files even if the report is malformed.
        # Neither retention nor a structurally valid PNG asserts capture identity.
        for name, encoded in files.items():
            try:
                self._retain_evidence_file(case, name, encoded, report_name, selected)
            except (NativeError, OSError, ValueError, binascii.Error) as error:
                # Keep arbitrary JSON/decoder payloads out of the public report.
                failures.append(
                    str(error)
                    if isinstance(error, NativeError)
                    else "Malformed or unavailable selected evidence: " + name
                )
        if failures:
            raise NativeError("; ".join(failures))
        return "startup.json" in files

    def validate_duckstation(
        self,
        report: dict[str, object],
        profile: dict[str, object],
        consumption: dict[str, object],
        display: dict[str, object],
    ) -> None:
        """Require actual Qt/SDL observations, not libretro's driver/FD contract."""
        backend = record(report.get("backend_identity"))
        version = record(backend.get("reported_version"))
        tag, branch = version.get("tag"), version.get("branch")
        if (
            backend.get("variant") != "duckstation-qt"
            or backend.get("executable") != "/usr/bin/duckstation-qt"
            or backend.get("package_source") != DUCKSTATION_PACKAGE_SOURCE
            or version.get("argument") != "-version"
            or version.get("exit_code") != 1
            or not isinstance(tag, str)
            or not isinstance(branch, str)
            or re.fullmatch(r"[A-Za-z0-9._+-]{0,80}", tag) is None
            or re.fullmatch(r"[A-Za-z0-9._+-]{0,80}", branch) is None
            or version.get("output") != f"DuckStation Version {tag} ({branch})"
        ):
            msg = "Actual DuckStation version/source observation missing"
            raise NativeError(msg)
        renderer = record(report.get("renderer"))
        expected_renderer = emulator_case(text(report.get("case"))).renderer
        visual = renderer.get("visual_argument")
        pinned = record(record(report.get("transition")).get("emulator"))
        visual_valid = (
            (
                isinstance(visual, str)
                and re.fullmatch(r"0x[0-9a-f]+", visual) is not None
                and 0 < int(visual, 16) <= UINT32_MAX
            )
            if expected_renderer == "OpenGL"
            else visual is None
        )
        if (
            renderer.get("selected") != expected_renderer
            or renderer.get("active")
            not in (
                ("OpenGL", "OpenGLES") if expected_renderer == "OpenGL" else ("Vulkan",)
            )
            or renderer.get("activation")
            != "pinned-open-file-device-context-hw-framebuffer"
            or renderer.get("discovery")
            != ("live-egl-x11" if expected_renderer == "OpenGL" else "not-run")
            or not visual_valid
            or renderer.get("pid") != pinned.get("pid")
            or renderer.get("start") != pinned.get("start")
        ):
            msg = (
                "DuckStation selected/active renderer or Qt correction evidence differs"
            )
            raise NativeError(msg)
        bios = record(record(report.get("prerequisites")).get("bios"))
        topology = record(consumption.get("consumer_topology"))
        environment = record(consumption.get("environment"))
        mapping = record(consumption.get("generated_mapping"))
        index = profile.get("sdl_index")
        if (
            bios.get("status") != "available"
            or not re.fullmatch(r"[a-f0-9]{64}", text(bios.get("identity")))
            or consumption.get("input_source") != "SDL"
            or consumption.get("stock_exit_context") != "duckstation"
            or type(index) is not int
            or index != 0
            or topology.get("discovered_joysticks") != 1
            or topology.get("configured_player_index") != 0
            or topology.get("index_basis") != "single-observed-suite-pad"
            or sequence(topology.get("opened_joysticks"))
            != [sequence(consumption.get("pad_device"))]
            or environment.get("sdl_mapping_guid") != profile.get("guid")
            or environment.get("SDL_JOYSTICK_HIDAPI") != "0"
            or environment.get("XDG_CONFIG_HOME") != "/userdata/system/configs"
            or environment.get("suite_mapping_consumed") is not True
            or bios.get("stock_configured_route") is not True
            or any(
                mapping.get("InputSources." + key) != value
                for key, value in (
                    ("SDL", "true"),
                    ("Evdev", "false"),
                    ("XInput", "false"),
                    ("RawInput", "false"),
                )
            )
            or mapping.get("Pad1.Type") != "DigitalController"
            or mapping.get("Pad1.Start") != f"SDL-{index}/Start"
            or mapping.get("Pad1.Cross") != f"SDL-{index}/A"
            or any(
                display.get(key) is not True
                for key in ("selected_disc_open", "render_window", "non_dialog")
            )
        ):
            msg = "DuckStation disc/render/firmware/SDL evidence incomplete"
            raise NativeError(msg)

    def validate_xemu(
        self,
        report: dict[str, object],
        consumption: dict[str, object],
        display: dict[str, object],
    ) -> None:
        """Require stock Xbox files and independently observed SDL3 consumption."""
        backend = record(report.get("backend_identity"))
        version = record(backend.get("reported_version"))
        if (
            backend.get("variant") != "xemu"
            or backend.get("executable") != "/usr/bin/xemu"
            or backend.get("package_source") != XEMU_PACKAGE_SOURCE
            or version.get("argument") != "-version"
            or type(version.get("exit_code")) is not int
            or version.get("exit_code") != 0
            or version.get("disposable_config") is not True
            or version.get("version") != "0.8.134"
            or version.get("revision") != XEMU_PACKAGE_SOURCE["revision"]
            or version.get("date") != "Fri May 29 06:08:30 AM UTC 2026"
        ):
            msg = "Actual xemu metadata/helper observation missing"
            raise NativeError(msg)
        disc_format = record(display.get("disc_format"))
        image_size = disc_format.get("image_size")
        root_sector = disc_format.get("root_directory_sector")
        root_size = disc_format.get("root_directory_size")
        media_identity = disc_format.get("media_identity")
        if (
            disc_format.get("format") != "xdvdfs"
            or type(disc_format.get("sector_size")) is not int
            or disc_format.get("sector_size") != XISO_SECTOR_SIZE
            or type(disc_format.get("volume_offset")) is not int
            or disc_format.get("volume_offset") != XISO_VOLUME_OFFSET
            or type(image_size) is not int
            or type(root_sector) is not int
            or type(root_size) is not int
            or not isinstance(media_identity, str)
            or re.fullmatch(r"[a-f0-9]{64}", media_identity) is None
            or media_identity != record(report.get("media")).get("identity")
        ):
            msg = "Selected xemu XISO structure evidence incomplete"
            raise NativeError(msg)
        if (
            image_size < XISO_VOLUME_OFFSET + XISO_SECTOR_SIZE
            or not 0 <= root_sector <= UINT32_MAX
            or not 0 <= root_size <= UINT32_MAX
            or root_sector * XISO_SECTOR_SIZE + root_size > image_size
        ):
            msg = "Selected xemu XISO descriptor/root extent invalid"
            raise NativeError(msg)
        prerequisites = record(report.get("prerequisites"))
        for key, path in (
            ("mcpx", "/userdata/bios/mcpx_1.0.bin"),
            ("bios", "/userdata/bios/Complex_4627.bin"),
        ):
            firmware = record(prerequisites.get(key))
            if (
                firmware.get("status") != "available"
                or firmware.get("readonly") is not True
                or firmware.get("path") != path
                or not re.fullmatch(r"[a-f0-9]{64}", text(firmware.get("identity")))
            ):
                msg = "Eligible Xbox disc requires read-only firmware"
                raise NativeError(msg)
        hdd = record(prerequisites.get("hdd"))
        state = record(report.get("disposable_state"))
        expected_state = {
            "hdd": "/userdata/saves/xbox/xbox_hdd.qcow2",
            "eeprom": "/userdata/saves/xbox/xemu_eeprom.bin",
            "config": "/userdata/system/configs/xemu/xemu.toml",
            "saves": "/userdata/saves/xbox",
            "cache": "/userdata/system/cache",
        }
        if (
            hdd.get("status") != "available"
            or hdd.get("route") != "stock"
            or hdd.get("source_identity") != XEMU_HDD_SHA256
            or hdd.get("source_readonly") is not True
            or hdd.get("use_disposition") != XEMU_HDD_USE
            or hdd.get("owned_copy") is not True
            or state.get("identity_verified") is not True
            or state.get("production_state_copied") is not False
            or any(state.get(key) != path for key, path in expected_state.items())
        ):
            msg = "Qualified stock HDD/disposable Xbox state missing"
            raise NativeError(msg)
        environment = record(consumption.get("environment"))
        mapping = record(consumption.get("generated_mapping"))
        files = record(consumption.get("configured_files"))
        sdl = record(consumption.get("sdl_object"))
        topology = record(consumption.get("consumer_topology"))
        gamepads = topology.get("discovered_gamepads")
        guid = environment.get("sdl_mapping_guid")
        if (
            consumption.get("input_source") != "SDL3"
            or consumption.get("stock_exit_context") != "xemu"
            or consumption.get("config_path") != expected_state["config"]
            or sdl.get("status") != "mapped"
            or sdl.get("inventory_path") != XEMU_SDL
            or sdl.get("sha256") != self.config.hashes.get(XEMU_SDL)
            or not re.fullmatch(r"[a-f0-9]{32}", text(guid))
            or mapping.get("input.bindings.port1") != guid
            or topology.get("guid") != guid
            or type(gamepads) is not int
            or not 1 <= gamepads <= MAX_GAMEPADS
            or topology.get("matching_guid_gamepads") != 1
            or topology.get("suite_device_matched") is not True
            or environment.get("suite_mapping_consumed") is not True
            or environment.get("XDG_CONFIG_HOME") != "/userdata/system/configs"
            or environment.get("LC_NUMERIC") != "C"
            or files.get("flashrom_path") != "/userdata/bios/Complex_4627.bin"
            or files.get("bootrom_path") != "/userdata/bios/mcpx_1.0.bin"
            or files.get("hdd_path") != expected_state["hdd"]
            or files.get("eeprom_path") != expected_state["eeprom"]
            or files.get("dvd_identity") != record(report.get("media")).get("identity")
            or any(
                display.get(key) is not True
                for key in ("selected_disc_open", "render_window", "non_dialog")
            )
        ):
            msg = "xemu stock TOML/disc/SDL3 consumer evidence incomplete"
            raise NativeError(msg)

    def _validate_frontend(self, report: dict[str, object]) -> list[dict[str, object]]:
        """Validate actual frontend readiness and pinned final input ownership."""
        frontend, transport = (
            record(report.get("frontend")),
            record(report.get("transport")),
        )
        if (
            frontend.get("active_window") is not True
            or frontend.get("completed_initialization") is not True
            or frontend.get("pinned_final_source_live") is not True
            or frontend.get("executable") != "emulationstation"
            or len(sequence(frontend.get("ready_flag_identity"))) != INODE_ID_FIELDS
            or transport.get("ready") is not True
            or transport.get("worker_connected") is not True
        ):
            msg = "Normal frontend readiness or final worker evidence missing"
            raise NativeError(msg)
        final = record(transport.get("final"))
        approved = sequence(transport.get("approved_process_ids"))
        flag = sequence(frontend.get("ready_flag_identity"))
        if (
            transport.get("app_uid") != self.config.uid
            or final.get("role") != "final"
            or final.get("name") != "batocera hotkeys"
            or final.get("source_pid") not in approved
            or frontend.get("pid") not in approved
            or flag[2] != self.config.uid
            or not re.fullmatch(r"input[0-9]+", text(final.get("sysname")))
            or not re.fullmatch(r"/dev/input/event[0-9]+", text(final.get("node")))
        ):
            msg = "Pinned frontend/final-source observation is incomplete"
            raise NativeError(msg)
        expected = [record(v) for v in sequence(report.get("captures"))]
        if len(expected) != 1 or expected[0].get("path") != "frontend-ready.png":
            msg = "Normal frontend readiness capture missing"
            raise NativeError(msg)
        return expected

    def _validate_pad_discovery(self, report: dict[str, object]) -> None:
        """Require actual pad classification and mapped stock libraries."""
        profile = record(report.get("profile"))
        discovery = record(report.get("pad_discovery"))
        publication = record(discovery.get("publication"))
        if (
            sequence(discovery.get("event_device"))
            != sequence(profile.get("event_device"))
            or discovery.get("discovery_mode") != {"udev_selected": True}
            or record(publication.get("properties")).get("ID_INPUT") != "1"
            or record(publication.get("properties")).get("ID_INPUT_JOYSTICK") != "1"
            or not re.fullmatch(
                r"[a-f0-9]{64}", text(publication.get("classifier_sha256"))
            )
            or publication.get("classifier_sha256")
            != self.config.hashes.get("/usr/bin/udevadm")
        ):
            msg = "Stock suite-pad classification/discovery evidence missing"
            raise NativeError(msg)
        for key, path in (
            ("sdl_object", "/usr/lib/libSDL2-2.0.so.0.3200.8"),
            ("udev_object", "/lib/libudev.so.1.6.3"),
        ):
            loaded = record(discovery.get(key))
            if (
                loaded.get("status") != "mapped"
                or loaded.get("inventory_path") != path
                or not re.fullmatch(r"[a-f0-9]{64}", text(loaded.get("sha256")))
                or loaded.get("sha256") != self.config.hashes.get(path)
            ):
                msg = "Loaded discovery library differs from stock inventory"
                raise NativeError(msg)

    def _validate_native_exit(
        self, case: NativeCase, report: dict[str, object], selected_case: EmulatorCase
    ) -> None:
        """Require causal native input, pinned exit and successful launcher."""
        transition = record(report.get("transition"))
        consumption = record(report.get("native_device_consumption"))
        profile = record(report.get("profile"))
        chord = record(report.get("chord"))
        emulator = record(transition.get("emulator"))
        libretro = selected_case.backend == "libretro"
        final_device = sequence(consumption.get("final_device")) if libretro else []
        pad = sequence(consumption.get("pad_device"))
        opened = sequence(consumption.get("opened_devices"))
        display = record(transition.get("stock_launch_display"))
        termination = record(report.get("termination_observation"))
        launcher = record(termination.get("launcher"))
        ended = record(termination.get("emulator"))
        launcher_sources = [
            digest
            for path, digest in self.config.hashes.items()
            if re.fullmatch(
                r"/usr/lib/python3\.[0-9]+/site-packages/configgen/emulatorlauncher\.py",
                path,
            )
        ]
        if (
            transition.get("native_guide_start") is not True
            or transition.get("same_emulator_exited") is not True
            or type(transition.get("launcher_code")) is not int
            or transition.get("launcher_code") != 0
            or termination.get("mechanism") != "pidfd-and-stock-launcher"
            or ended.get("pid") != emulator.get("pid")
            or ended.get("start") != emulator.get("start")
            or ended.get("live") is not False
            or type(launcher.get("code")) is not int
            or launcher.get("code") != 0
            or len(launcher_sources) != 1
            or termination.get("launcher_source_sha256") != launcher_sources[0]
            or launcher.get("pid") == emulator.get("pid")
            or transition.get("forced_teardown") is not False
            or number(transition.get("live_before_chord_seconds"))
            < MIN_EMULATOR_LIVE_SECONDS
            or display.get("active_pid") != emulator.get("pid")
            or any(
                display.get(key) is not True
                for key in (
                    "exact_core_loaded" if libretro else "exact_backend_loaded",
                    "rendered_content",
                    "live",
                )
            )
            or profile.get("stock_configgen_consumed") is not True
            or not sequence(profile.get("qualified_controls"))
            or sequence(profile.get("event_device")) != pad
            or not re.fullmatch(r"[a-f0-9]{32}", text(profile.get("guid")))
            or consumption.get("status") != "passed"
            or len(pad) != DEVICE_ID_FIELDS
            or any(
                type(value) is not int or number(value) < 0
                for value in [*final_device, *pad]
            )
            or pad[0] != INPUT_DEVICE_MAJOR
            or pad not in opened
            or chord.get("route") != "owned-uinput-stock-evmapy-adapter-stock-hotkeygen"
            or chord.get("pressed") is not True
            or chord.get("released") is not True
            or record(report.get("cleanup")).get("status") != "passed"
            or record(report.get("cleanup")).get("forced_emulator_teardown")
            is not False
            or record(report.get("stock_hashes")).get("unchanged") is not True
            or case.name + "-selection.json" not in case.captures
        ):
            msg = "Stock emulator native launch/observed-exit evidence incomplete"
            raise NativeError(msg)
        for identity in (emulator, launcher):
            if (
                type(identity.get("pid")) is not int
                or type(identity.get("start")) is not int
            ):
                msg = "Pinned emulator/launcher identity missing"
                raise NativeError(msg)
            pid, start = identity["pid"], identity["start"]
            if (
                not isinstance(pid, int)
                or pid <= 1
                or not isinstance(start, int)
                or start <= 0
            ):
                msg = "Pinned emulator/launcher identity invalid"
                raise NativeError(msg)

    def _validate_native_input(
        self, report: dict[str, object], selected_case: EmulatorCase
    ) -> None:
        """Validate backend-specific consumption of the actual native input devices."""
        transition = record(report.get("transition"))
        consumption = record(report.get("native_device_consumption"))
        profile = record(report.get("profile"))
        display = record(transition.get("stock_launch_display"))
        libretro = selected_case.backend == "libretro"
        final_device = sequence(consumption.get("final_device")) if libretro else []
        pad = sequence(consumption.get("pad_device"))
        opened = sequence(consumption.get("opened_devices"))
        if libretro:
            source = record(consumption.get("final_source"))
            if (
                consumption.get("input_driver") != "udev"
                or consumption.get("input_joypad_driver") != "udev"
                or record(consumption.get("final_udev")).get("ID_INPUT_KEYBOARD") != "1"
                or source.get("pinned_live") is not True
                or len(final_device) != DEVICE_ID_FIELDS
                or final_device == pad
                or final_device[0] != INPUT_DEVICE_MAJOR
                or final_device not in opened
                or any(
                    type(source.get(key)) is not int or number(source.get(key)) <= 1
                    for key in ("pid", "start")
                )
            ):
                msg = "RetroArch native final-device evidence missing"
                raise NativeError(msg)
        elif selected_case.backend == "xemu":
            self.validate_xemu(report, consumption, display)
        else:
            self.validate_duckstation(report, profile, consumption, display)

    def _validate_suite_inputs(self, report: dict[str, object]) -> None:
        """Bind controller and selected media identities to inspected suite assets."""
        profile = record(report.get("profile"))
        for key in ("sha256", "definition_sha256", "template_sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", text(profile.get(key))):
                msg = "Suite profile identity missing"
                raise NativeError(msg)
        for key, path in (
            ("definition_sha256", "/opt/gow-full-x86/suite-gamepad.json"),
            ("template_sha256", "/opt/gow-full-x86/suite-es-input.cfg"),
        ):
            if profile.get(key) != self.config.hashes.get(path):
                msg = "Suite asset identity differs from inspected package"
                raise NativeError(msg)
        if record(report.get("media")).get("catalog_sha256") != STOCK_SHA256:
            msg = "Selected media stock catalog identity differs"
            raise NativeError(msg)
        if not re.fullmatch(
            r"[a-f0-9]{64}", text(record(report.get("media")).get("identity"))
        ):
            msg = "Private selected media identity missing"
            raise NativeError(msg)

    def _validate_backend_image(
        self, report: dict[str, object], selected_case: EmulatorCase
    ) -> None:
        """Match observed binaries, cores and versions to stock inventory."""
        backend = record(report.get("backend_identity"))
        libretro = selected_case.backend == "libretro"
        identities = [("executable_sha256", selected_case.executable)]
        if libretro:
            identities.extend(
                [
                    ("core_sha256", selected_case.core_path),
                    ("core_info_sha256", selected_case.info_path),
                ]
            )
            if (
                backend.get("core") != selected_case.core
                or backend.get("core_library") != selected_case.library
                or not re.fullmatch(
                    r"[A-Za-z0-9._+-]{1,64}", text(backend.get("retroarch_version"))
                )
                or not re.fullmatch(
                    r"[A-Za-z0-9 ._+()/-]{1,80}", text(backend.get("core_version"))
                )
            ):
                msg = "Actual RetroArch/core version observation missing"
                raise NativeError(msg)
        for key, path in identities:
            if not re.fullmatch(r"[a-f0-9]{64}", text(backend.get(key))) or backend.get(
                key
            ) != self.config.hashes.get(path):
                msg = "Actual backend differs from inspected stock inventory"
                raise NativeError(msg)

    def _validate_emulator(
        self, case: NativeCase, report: dict[str, object], selected_case: EmulatorCase
    ) -> list[dict[str, object]]:
        """Validate the stock native launch, causal exit and backend observations."""
        self._validate_pad_discovery(report)
        self._validate_native_exit(case, report, selected_case)
        self._validate_native_input(report, selected_case)
        self._validate_suite_inputs(report)
        self._validate_backend_image(report, selected_case)
        transition = record(report.get("transition"))
        expected = [record(v) for v in sequence(transition.get("captures"))]
        if [capture.get("path") for capture in expected] != [
            "emulator-before-exit.png",
        ]:
            msg = "Emulator transition captures missing"
            raise NativeError(msg)
        return expected

    def _validate_receivers(self, report: dict[str, object]) -> list[dict[str, object]]:
        """Validate only executed receiver trials without claiming unselected rows."""
        rows = [record(v) for v in sequence(report.get("cases"))]
        if (
            [r.get("name") for r in rows]
            != list(
                (self.config.receiver_case,)
                if self.config.receiver_case
                else RECEIVER_CASES
            )
            or any(r.get("status") != "passed" for r in rows)
            or report.get("not_run_cases")
            != (
                [name for name in RECEIVER_CASES if name != self.config.receiver_case]
                if self.config.receiver_case
                else []
            )
            or record(report.get("cleanup")).get("status") != "passed"
            or record(report.get("stock_hashes")).get("unchanged") is not True
        ):
            msg = "Five receiver assertions/integrity/owned probe cleanup incomplete"
            raise NativeError(msg)
        expected = [record(row.get("capture")) for row in rows]
        if any(
            record(row.get("capture")).get("path") != text(row.get("name")) + ".png"
            for row in rows
        ):
            msg = "Receiver checkpoint does not match its assertion"
            raise NativeError(msg)
        return expected

    @staticmethod
    def _validate_capture_digests(
        case: NativeCase, expected: list[dict[str, object]]
    ) -> None:
        """Match every authenticated capture to its actual transferred digest."""
        if not expected:
            msg = "Required captures missing"
            raise NativeError(msg)
        for capture in expected:
            path = text(capture.get("path"))
            key = case.name + "-" + path
            if capture.get(
                "mechanism"
            ) != "authenticated-libX11-XGetImage-stock-Pillow" or case.captures.get(
                key
            ) != capture.get("sha256"):
                msg = "Authenticated probe capture missing or transfer digest differs"
                raise NativeError(msg)

    def validate_report(self, case: NativeCase) -> None:
        """Require all independent assertions and their matching real captures."""
        report = case.report
        selected_case = next(
            (item for item in EMULATOR_CASES if item.identifier == case.name), None
        )
        if (
            selected_case is not None
            and report is not None
            and (
                report.get("case") != selected_case.identifier
                or report.get("system") != selected_case.system
                or report.get("backend") != selected_case.backend
                or report.get("core") != selected_case.core
                or report.get("assertions") != "stock-native-observed-exit-v3"
                or report.get("negative_control") != "none"
            )
        ):
            msg = "Emulator report differs from selected stock case"
            raise NativeError(msg)
        if case.name + "-selected.log" not in case.captures:
            msg = "Required selected diagnostic log missing"
            raise NativeError(msg)
        if (
            selected_case is not None
            and report is not None
            and report.get("status") == "skipped-no-media"
        ):
            if case.name in self.config.qualified_inputs:
                msg = "Qualified exact-input execution cannot become a media skip"
                raise NativeError(msg)
            if (
                report.get("reason") != "Skipped: no compatible mounted media"
                or record(report.get("native_device_consumption")).get("status")
                != "untested"
                or record(report.get("cleanup")).get("status") != "passed"
                or record(report.get("stock_hashes")).get("unchanged") is not True
            ):
                msg = "Media absence must retain untested consumption and integrity"
                raise NativeError(msg)
            return
        if report is None or report.get("status") != "passed":
            msg = "Native probe did not pass"
            raise NativeError(msg)
        if case.name == "frontend":
            expected = self._validate_frontend(report)
        elif selected_case is not None:
            expected = self._validate_emulator(case, report, selected_case)
        else:
            expected = self._validate_receivers(report)
        self._validate_capture_digests(case, expected)
        qualified = self.config.qualified_inputs.get(case.name)
        if (
            qualified is not None
            and case_identity(case.name, report, self.config.image, self.config.source)
            != qualified.identity
        ):
            msg = "Expanded native result changed qualified input identity"
            raise NativeError(msg)

    def _ready_case(self, case: NativeCase) -> None:
        """Observe startup and recheck exact inputs before opening the gate."""
        b = self.config.budgets
        self.phase = case.name + ":startup"
        deadline = self.clock.now() + b.startup
        while True:
            self.discover(deadline, case)
            if case.container_id is not None and self.collect(case, deadline):
                self.inspect(case, deadline)
                break
            self.pause(deadline)
        selection = self.selection_for(case.name)
        if selection is not None:
            selected_case = emulator_case(case.name)
            self.call(
                "seed_selection",
                deadline,
                case,
                selection=selection,
                system=selected_case.system,
            )
        qualified = self.config.qualified_inputs.get(case.name)
        if qualified is not None:
            checked = self.call(
                "verify_qualified",
                deadline,
                case,
                expected=qualified.probe,
            )
            if checked.get("matched") is not True:
                msg = "Expanded exact-input prerequisites differ"
                raise NativeError(msg)

    def _observe_case(self, case: NativeCase) -> None:
        """Lease only owned native execution until all assertions are observed."""
        b = self.config.budgets
        self.phase = case.name + ":scenario"
        deadline = self.clock.now() + b.scenario
        while True:
            self.discover(deadline, case)
            self.collect(case, deadline)
            if case.report is not None:
                self.validate_report(case)
                break
            self.call(
                "lease",
                deadline,
                case,
                lease_seconds=min(b.lease, deadline - self.clock.now()),
            )
            case.gate_open = True
            self.pause(deadline)

    def run_case(self, case: NativeCase) -> None:
        """Allocate, create once, inspect, lease, observe and always clean up."""
        b = self.config.budgets
        allocation_attempted = False
        try:
            self.phase = case.name + ":preflight"
            self.discover(self.clock.now() + b.call, None)
            allocation_attempted = True
            case.pin = record(
                self.call("allocate", self.clock.now() + b.call, case).get("pin")
            )
            self.phase = case.name + ":create"
            case.create_dispatched = True
            response = self.call(
                "create", self.clock.now() + b.create, case, payload=case.payload
            )
            case.lobby_id = text(response.get("lobby_id"))
            self._ready_case(case)
            self._observe_case(case)
        except (
            NativeError,
            MediaError,
            OSError,
            ValueError,
            InterruptedError,
        ) as error:
            case.errors.append(str(error))
            if isinstance(error, InterruptedError) or (
                self.phase.endswith((":startup", ":scenario"))
                and "discover" in str(error).lower()
            ):
                self.interrupted = str(error)
                case.interruption = str(error)
        finally:
            if case.pin is not None:
                self.cleanup_case(case)
            elif allocation_attempted:
                case.cleanup = {
                    "status": "incomplete",
                    "state_relative": "test-runs/" + case.case_id,
                    "reason": (
                        "Allocation identity response unavailable; state is not "
                        "authorized for removal"
                    ),
                }

    def pause(self, deadline: float) -> None:
        """Observe within a deadline without an off-by-one boundary action."""
        remaining = deadline - self.clock.now()
        if remaining <= 0:
            msg = "Phase deadline expired"
            raise NativeError(msg)
        self.clock.sleep(min(self.config.budgets.poll, remaining))

    def _cleanup_evidence(self, case: NativeCase) -> None:
        """Retain final independent evidence after startup or scenario failure."""
        evidence_deadline = self.clock.now() + self.config.budgets.evidence
        try:
            while True:
                self.collect(case, evidence_deadline, diagnose_missing=True)
                if case.report is not None:
                    break
                self.pause(evidence_deadline)
        except (NativeError, OSError, ValueError, InterruptedError) as error:
            case.errors.append("Evidence collection: " + str(error))

    @staticmethod
    def _resolved_startup(case: NativeCase) -> bool:
        """Require observed startup before accepting create cancellation."""
        if not case.startup_resolved:
            msg = "Unresolved dispatched startup has no qualified cancellation barrier"
            raise NativeError(msg)
        return case.startup_resolved

    def _confirm_absence(
        self,
        case: NativeCase,
        failures: list[str],
        remove_stopped: Callable[[], object],
    ) -> bool:
        """Prove independent absence before authorizing disposable state removal."""
        absent = not case.create_dispatched
        deadline = self.clock.now() + self.config.budgets.cleanup
        removal_attempted = False
        try:
            while not absent:
                observed = self.discover(deadline, case, enforce_idle=False)
                containers = [record(v) for v in sequence(observed.get("containers"))]
                lobbies = sequence(observed.get("lobbies"))
                if (
                    containers
                    and not removal_attempted
                    and all(
                        v.get("running") is False and v.get("paused") is False
                        for v in containers
                    )
                ):
                    remove_stopped()
                    removal_attempted = True
                if not lobbies and not containers:
                    absent = self._resolved_startup(case)
                    break
                self.pause(deadline)
        except (NativeError, OSError, ValueError, InterruptedError) as error:
            failures.append("Absence confirmation: " + str(error))
        return absent

    def _cleanup_stop_container(
        self,
        case: NativeCase,
        failures: list[str],
        stop: Callable[[], object],
    ) -> None:
        """Stop only an owned container still present after fresh discovery."""
        try:
            observed = self.discover(
                self.clock.now() + self.config.budgets.call,
                case,
                enforce_idle=False,
            )
            if sequence(observed.get("containers")):
                stop()
        except (NativeError, OSError, ValueError, InterruptedError) as error:
            failures.append("Container stop discovery: " + str(error))

    def cleanup_case(self, case: NativeCase) -> None:
        """Attempt independent teardown steps even after evidence/stop failure."""
        self.phase = case.name + ":cleanup"
        attempts: list[object] = []
        failures: list[str] = []

        # Each independent action gets its own finite call budget. Absence has a
        # separate phase budget and never inherits an expired scenario deadline.
        def attempt(action: str, **values: object) -> dict[str, object] | None:
            try:
                result = self.call(
                    action, self.clock.now() + self.config.budgets.call, case, **values
                )
                observation: dict[str, object] = {
                    "operation": action,
                    "status": "passed",
                }
                if result.get("already_absent") is True:
                    observation["already_absent"] = True
                attempts.append(observation)
            except (NativeError, OSError, ValueError, InterruptedError) as error:
                failures.append(action + ": " + str(error))
                attempts.append({"operation": action, "status": "failed"})
                return None
            else:
                return result

        attempt("revoke")
        self._cleanup_evidence(case)
        # Recover even a lost create response using exact runner hash, profile,
        # label, immutable image and effective state evidence. Never retry create.
        try:
            self.discover(
                self.clock.now() + self.config.budgets.call, case, enforce_idle=False
            )
        except (NativeError, OSError, ValueError, InterruptedError) as error:
            failures.append("Ownership recovery: " + str(error))
        if case.lobby_id is not None:
            attempt("stop_lobby")
        if case.container_id is not None:
            # A stop may race Wolf's own removal. Fresh discovery distinguishes
            # confirmed absence from a failed inspect before another operation.
            self._cleanup_stop_container(
                case, failures, lambda: attempt("stop_container")
            )
        absent = self._confirm_absence(
            case, failures, lambda: attempt("remove_container")
        )
        removed = False
        if absent:
            removed = attempt("remove_state") is not None
        else:
            failures.append(
                "Disposable state retained because native absence/startup is unresolved"
            )
        case.cleanup = {
            "status": "passed" if absent and removed and not failures else "incomplete",
            "attempts": attempts,
            "errors": failures,
            "lobby_absent": absent,
            "container_absent": absent,
            "state_removed": removed,
            "startup_resolved": case.startup_resolved,
            "known_lobby_id": case.lobby_id,
            "known_container_id": case.container_id,
            "state_relative": "test-runs/" + case.case_id,
        }

    def qualification_observations(self, case: NativeCase) -> NativeObservations:
        """Summarize validated native assertions and both independent cleanup gates.

        Revalidate the final collected probe before publishing reusable proof.
        Device consumption is backend-specific: SDL/SDL3 observations are actual
        consumption, not an inferred RetroArch final-keyboard check.
        """
        self.validate_report(case)
        probe = record(case.report)
        transition = record(probe.get("transition"))
        display = record(transition.get("stock_launch_display"))
        chord = record(probe.get("chord"))
        consumption = record(probe.get("native_device_consumption"))
        renderer = record(probe.get("renderer") or {})
        probe_cleanup = record(probe.get("cleanup"))
        return NativeObservations(
            stock_launch_display=(
                display.get("rendered_content") is True and display.get("live") is True
            ),
            live_before_chord=number(transition.get("live_before_chord_seconds"))
            >= MIN_EMULATOR_LIVE_SECONDS,
            native_guide_start=(
                transition.get("native_guide_start") is True
                and chord.get("pressed") is True
                and chord.get("released") is True
            ),
            same_emulator_exited=transition.get("same_emulator_exited") is True,
            launcher_completed=(
                type(transition.get("launcher_code")) is int
                and transition.get("launcher_code") == 0
            ),
            native_device_consumed=(
                consumption.get("status") == "passed" if consumption else None
            ),
            stock_integrity=record(probe.get("stock_hashes")).get("unchanged") is True,
            evidence_retained=bool(case.captures) and not case.errors,
            cleanup_complete=(
                probe_cleanup.get("status") == "passed"
                and probe_cleanup.get("forced_emulator_teardown") is False
                and transition.get("forced_teardown") is False
                and case.cleanup.get("status") == "passed"
                and all(
                    case.cleanup.get(key) is True
                    for key in ("lobby_absent", "container_absent", "state_removed")
                )
            ),
            renderer_selected=(
                text(renderer["selected"])
                if renderer.get("selected") is not None
                else None
            ),
            renderer_active=(
                text(renderer["active"]) if renderer.get("active") is not None else None
            ),
        )

    def _execute_cases(self, names: list[str]) -> None:
        """Run serial cases until drift, interruption or cleanup barriers."""
        if self.verify_inputs is not None:
            self.verify_inputs()
        self.phase = "preflight"
        self.preflight = self.call(
            "preflight",
            self.clock.now() + self.config.budgets.call,
            protected=[
                str(Path(self.config.host_root) / "profile-data"),
                self.config.roots.roms,
                self.config.roots.bios,
            ],
        )
        self.wolf_id = text(self.preflight.get("wolf_id"))
        self.discover(self.clock.now() + self.config.budgets.call, None)
        for name in names:
            if self.verify_inputs is not None:
                self.verify_inputs()
            case = self.make_case(name)
            self.cases.append(case)
            self.run_case(case)
            if (
                name == "psx-duckstation"
                and self.selection_for("psx-duckstation-vulkan") is None
                and name + "-selection.json" in case.captures
            ):
                self.replay_selections["psx-duckstation-vulkan"] = (
                    read_reproduction_record(
                        self.artifacts.path / (name + "-selection.json")
                    )
                )
            if self.interrupted is not None or case.cleanup.get("status") != "passed":
                break
        if self.verify_inputs is not None:
            self.verify_inputs()

    def _case_rows(self, names: list[str]) -> list[dict[str, object]]:
        """Keep behavior, capture, cleanup and ownership dispositions separate."""
        rows: list[dict[str, object]] = []
        for name in names:
            case = next((c for c in self.cases if c.name == name), None)
            if case is None:
                rows.append(
                    {
                        "name": name,
                        "status": "not-run",
                        "reason": self.interrupted
                        or "Prerequisite or previous cleanup barrier failed",
                    }
                )
            else:
                rows.append(
                    {
                        "name": name,
                        "status": "interrupted"
                        if case.interruption
                        else "failed"
                        if case.errors or case.report is None
                        else "skipped-no-media"
                        if case.report is not None
                        and case.report.get("status") == "skipped-no-media"
                        else "passed",
                        "reason": NO_MEDIA
                        if case.report is not None
                        and case.report.get("status") == "skipped-no-media"
                        else case.interruption
                        or "; ".join(case.errors)
                        or "Validated requested assertions",
                        "errors": case.errors,
                        "startup_observations": case.startup_observations,
                        "startup_observations_truncated": (
                            case.startup_observations_truncated
                        ),
                        "isolation": case.isolation,
                        "captures": case.captures,
                        "evidence": {
                            "transfer_status": "retained"
                            if case.captures
                            else "missing",
                            "assertions_validated": not case.errors
                            and case.report is not None,
                            "files": case.captures,
                        },
                        "cleanup": case.cleanup,
                        "report": sanitize(case.report),
                    }
                )
                rows[-1]["ownership"] = {
                    "case_id": case.case_id,
                    "owner_marker_sha256": hashlib.sha256(
                        case.token.encode()
                    ).hexdigest(),
                    "state_identity": case.pin,
                    "create_dispatched": case.create_dispatched,
                    "startup_resolved": case.startup_resolved,
                    "lobby_id": case.lobby_id,
                    "container_id": case.container_id,
                }
        return rows

    def _assemble_report(
        self, names: list[str], errors: list[str], selected_case: EmulatorCase | None
    ) -> dict[str, object]:
        """Assemble maintained gates without inflating skips or smoke subsets."""
        rows = self._case_rows(names)
        passed = (
            not errors
            and not self.interrupted
            and len(self.cases) == len(names)
            and all(
                not c.errors
                and c.report is not None
                and c.cleanup.get("status") == "passed"
                for c in self.cases
            )
        )
        report: dict[str, object] = {
            "schema": 1,
            "run_id": self.run_id,
            "tier": self.config.tier,
            "status": "passed" if passed else "failed",
            "diagnostic_only": False,
            "image": self.config.image,
            "source": self.config.source,
            "stock_sha256": self.config.stock_sha256,
            "budgets_seconds": self.config.budgets.as_dict(),
            "phase": self.phase,
            "timings": self.timings,
            "errors": errors,
            "interruption": self.interrupted,
            "cases": rows,
            "required_receiver_checks": list(RECEIVER_CASES),
            "limits": LIMITS,
            "emulator_exit_coverage": (
                selected_case.label + " native Guide+Start observed exit"
                if selected_case is not None
                and passed
                and any(row.get("status") == "passed" for row in rows)
                else "No emulator exit coverage"
            ),
            "preflight": {k: v for k, v in self.preflight.items() if k != "snapshot"},
        }
        report["full_frontend_receiver_gate"] = (
            all(
                row.get("status") == "passed"
                for row in rows
                if row["name"] in ("frontend", "receivers")
            )
            and sum(row["name"] in FRONTEND_RECEIVER_CASES for row in rows)
            == len(FRONTEND_RECEIVER_CASES)
            and not errors
            and not self.interrupted
        )
        report["counts"] = outcome_counts(rows)
        receiver = next((case for case in self.cases if case.name == "receivers"), None)
        observed_rows = (
            [record(v) for v in sequence(receiver.report.get("cases"))]
            if receiver is not None
            and receiver.report is not None
            and isinstance(receiver.report.get("cases"), list)
            else []
        )
        report["receiver_checks"] = [
            next(
                (row for row in observed_rows if row.get("name") == name),
                {"name": name, "status": "not-run"},
            )
            for name in RECEIVER_CASES
        ]
        evidence_complete = not errors and all(
            not case.errors and case.report is not None for case in self.cases
        )
        cleanup_complete = all(
            case.cleanup.get("status") == "passed" for case in self.cases
        )
        report["full_frontend_receiver_gate"] = bool(
            report["full_frontend_receiver_gate"]
            and evidence_complete
            and cleanup_complete
        )
        report["evidence_complete"] = evidence_complete
        report["cleanup_complete"] = cleanup_complete
        report["catalog_sha256"] = STOCK_SHA256
        report["layout"] = "src/batocera_gow"
        report["full_regression_gate"] = False
        if self.config.tier == "regression":
            report.update(
                aggregate_regression(
                    rows,
                    [record(value) for value in sequence(report["receiver_checks"])],
                    evidence_complete=evidence_complete,
                    cleanup_complete=cleanup_complete,
                    interrupted=self.interrupted is not None,
                )
            )
        if self.config.tier in ("regression", "expanded"):
            exit_cases = [
                case.name
                for case in self.cases
                if case.name not in ("frontend", "receivers")
                and not case.errors
                and case.report is not None
                and case.report.get("status") == "passed"
                and case.cleanup.get("status") == "passed"
            ]
            report["emulator_exit_cases"] = exit_cases
            report["emulator_exit_coverage"] = (
                "Native Guide+Start observed exit: " + ", ".join(exit_cases)
                if exit_cases
                else "No emulator exit coverage"
            )
        report["requested_expanded_cases"] = list(self.config.expanded_selection)
        report["assertions"] = {
            "frontend": {
                "expected": "Normal frontend visible and final native transport ready",
                "observed": next(
                    (row["status"] for row in rows if row["name"] == "frontend"),
                    "not-run",
                ),
            },
            "receivers": {
                "expected": list(RECEIVER_CASES),
                "observed": report["receiver_checks"],
            },
            "emulator": {
                "expected": "stock-native-observed-exit-v3",
                "requires": [
                    "stock launch and rendered output",
                    "same live pinned emulator",
                    "native Guide+Start press/release",
                    "pinned emulator ended",
                    "stock launcher code zero",
                    "applicable native-device consumption",
                    "stock integrity",
                    "retained authenticated evidence",
                    "owned cleanup",
                ],
                "observed": [
                    {
                        "case": row["name"],
                        "status": row["status"],
                        "reason": row.get("reason"),
                    }
                    for row in rows
                    if row["name"] not in ("frontend", "receivers")
                ],
            },
        }
        return report

    def _qualifications(
        self, report: dict[str, object]
    ) -> dict[str, tuple[Qualification, NativeObservations]]:
        """Revalidate complete native success before publishing reusable proof."""
        qualifications: dict[str, tuple[Qualification, NativeObservations]] = {}
        if (
            report["status"] == "passed"
            and report["evidence_complete"]
            and report["cleanup_complete"]
        ):
            for case in self.cases:
                if (
                    case.name in ("frontend", "receivers")
                    or record(case.report).get("status") != "passed"
                ):
                    continue
                observations = self.qualification_observations(case)
                identity = case_identity(
                    case.name,
                    record(case.report),
                    self.config.image,
                    self.config.source,
                )
                qualified = evaluate_qualification(
                    identity,
                    Qualification("unqualified", None),
                    observations,
                    use_authorized=True,
                    distributed=False,
                    distribution_cleared=False,
                )
                if qualified.status != "qualified":
                    msg = "Validated native case could not qualify"
                    raise NativeError(msg)
                qualifications[case.name] = (qualified, observations)
        return qualifications

    def _publish_report(self, report: dict[str, object], names: list[str]) -> None:
        """Publish digest-bound proof; downgrade every gate if publication fails."""
        try:
            qualifications = self._qualifications(report)
            if self.config.tier in ("regression", "expanded"):
                report["coverage"] = advertised_coverage(
                    tuple(qualifications),
                    tuple(
                        name for name in names if name not in ("frontend", "receivers")
                    ),
                    project_root=self.config.project_root,
                )
            report_bytes = (
                json.dumps(sanitize(report), indent=2, sort_keys=True).encode() + b"\n"
            )
            for name, (qualified, observations) in qualifications.items():
                self.artifacts.put(
                    name + "-qualification.json",
                    json.dumps(
                        {
                            "schema": 1,
                            "report": "report.json",
                            "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                            "qualification": asdict(qualified),
                            "observations": asdict(observations),
                            "limits": list(LIMITS),
                        },
                        indent=2,
                        sort_keys=True,
                    ).encode()
                    + b"\n",
                )
            self.artifacts.put("report.json", report_bytes)
        except (NativeError, OSError, ValueError, TypeError) as error:
            report["status"] = "failed"
            report["full_regression_gate"] = False
            report["full_frontend_receiver_gate"] = False
            report["evidence_complete"] = False
            report["publication_error"] = str(error)
            if self.config.tier in ("regression", "expanded"):
                report["coverage"] = advertised_coverage(
                    (),
                    tuple(
                        name for name in names if name not in ("frontend", "receivers")
                    ),
                    project_root=self.config.project_root,
                )

    def run(self) -> dict[str, object]:
        """Produce separate behavior, evidence and cleanup outcomes on every path."""
        selected_case = emulator_tier(self.config.tier)
        names = (
            ["frontend", "receivers", *(case.identifier for case in EMULATOR_CASES)]
            if self.config.tier == "regression"
            else ["frontend", "receivers", *self.config.qualified_inputs]
            if self.config.tier == "expanded"
            else ["frontend", "receivers"]
            if self.config.tier == "frontend-receivers"
            else [selected_case.identifier]
            if selected_case is not None
            else ["frontend" if self.config.tier == "frontend-smoke" else "receivers"]
        )
        errors: list[str] = []
        try:
            self._execute_cases(names)
        except (
            NativeError,
            MediaError,
            OSError,
            ValueError,
            InterruptedError,
        ) as error:
            errors.append(str(error))
        report = self._assemble_report(names, errors, selected_case)
        self._publish_report(report, names)
        return report


def load_integrity(
    build_path: Path,
    stock_path: Path,
    runtime: Path,
    tier: str = "nes-smoke",
) -> tuple[str, str, str, dict[str, object]]:
    """Require successful build inventory and derive exact stock/additive hashes."""
    build = record(json.loads(build_path.read_text(encoding="utf-8")))
    if (
        build.get("status") != "success"
        or build.get("inventory_verified") is not True
        or build.get("release") != "43.1"
    ):
        msg = "Successful exact-image stock inventory evidence required"
        raise NativeError(msg)
    stock = record(
        record(json.loads(stock_path.read_text(encoding="utf-8"))).get("entries")
    )
    hashes: dict[str, object] = {}
    for name, entry_value in stock.items():
        entry = record(entry_value)
        if "sha256" in entry and (
            name
            in (
                "/usr/bin/hotkeygen",
                "/usr/bin/evmapy",
                "/usr/bin/emulatorlauncher",
                *(path for case in EMULATOR_CASES for path in case.inventory_paths),
                "/usr/bin/udevadm",
                "/usr/lib/libSDL2-2.0.so.0.3200.8",
                "/lib/libudev.so.1.6.3",
                "/usr/share/evmapy/hotkeys.keys",
                "/usr/share/emulationstation/es_systems.cfg",
            )
            or name.startswith("/etc/hotkeygen/")
            or re.match(r"/usr/lib/python3\.[0-9]+/site-packages/evmapy/", name)
            or re.match(
                r"/usr/lib/python3\.[0-9]+/site-packages/configgen/.+\.py$", name
            )
        ):
            hashes[name] = text(entry["sha256"])
    required = (
        "/usr/bin/hotkeygen",
        "/usr/bin/evmapy",
        "/usr/bin/emulatorlauncher",
        "/usr/bin/udevadm",
        "/usr/lib/libSDL2-2.0.so.0.3200.8",
        "/lib/libudev.so.1.6.3",
        "/etc/hotkeygen/default_mapping.conf",
        "/etc/hotkeygen/default_context.conf",
        "/etc/hotkeygen/common_context.conf",
        "/usr/share/evmapy/hotkeys.keys",
        "/usr/share/emulationstation/es_systems.cfg",
        *(
            tuple(path for case in EMULATOR_CASES for path in case.inventory_paths)
            if tier == "regression"
            else selected_case.inventory_paths
            if (selected_case := emulator_tier(tier)) is not None
            else ("/usr/bin/retroarch",)
        ),
    )
    if not all(name in hashes for name in required) or not any(
        re.match(r"/usr/lib/python3\.[0-9]+/site-packages/evmapy/.+\.py$", name)
        for name in hashes
    ):
        msg = "Stock input/catalog inventory is incomplete"
        raise NativeError(msg)
    for path in runtime.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_file():
            hashes["/opt/gow-full-x86/" + str(path.relative_to(runtime))] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return (
        text(build.get("image_id")),
        text(build.get("adapter_revision")),
        text(build.get("input_sha256")),
        hashes,
    )


def _resolve_cli_settings(
    args: argparse.Namespace,
) -> tuple[SSHConfig, ContentRoots, HostSettings]:
    """Resolve one frozen settings snapshot and exact native effect authorization."""
    supplied = {
        "SSH_TARGET": args.ssh_target,
        "SSH_IDENTITY_FILE": args.ssh_identity_file,
        "BUILD_MANIFEST": args.build_manifest,
        "STOCK_MANIFEST": args.stock_manifest,
        "RUNTIME_ROOT": args.runtime_root,
        "RENDER_NODE": args.render_node,
        "VIDEO_CAPS": args.video_caps,
        "WOLF_CONTAINER": args.wolf_container,
        "API_SOCKET": args.api_socket,
        "HOST_ROOT": args.host_root,
        "LOCAL_ROOT": args.local_root,
        "PROFILE": args.profile,
        "UID": args.uid,
        "OUTPUT": args.output,
        "GID": args.gid,
    }
    overrides = {
        "BATOCERA_GOW_" + key: str(value)
        for key, value in supplied.items()
        if value is not None
    }
    if args.infrastructure_container is not None:
        overrides["BATOCERA_GOW_INFRASTRUCTURE_CONTAINERS"] = " ".join(
            args.infrastructure_container
        )
    settings = HostSettings.resolve(env_file=args.env_file, overrides=overrides)
    args.host_root = settings.get("BATOCERA_GOW_HOST_ROOT", "/etc/wolf")
    args.local_root = settings.get("BATOCERA_GOW_LOCAL_ROOT", "/etc/wolf")
    args.wolf_container = settings.get("BATOCERA_GOW_WOLF_CONTAINER", "wolf")
    args.api_socket = settings.get("BATOCERA_GOW_API_SOCKET", "/var/run/wolf/wolf.sock")
    args.profile = settings.get("BATOCERA_GOW_PROFILE", "user")
    args.uid = int(settings.get("BATOCERA_GOW_UID", "1000") or "")
    args.gid = int(settings.get("BATOCERA_GOW_GID", "1000") or "")
    args.render_node = settings.get("BATOCERA_GOW_RENDER_NODE")
    args.video_caps = settings.get("BATOCERA_GOW_VIDEO_CAPS")
    args.infrastructure_container = (
        settings.get("BATOCERA_GOW_INFRASTRUCTURE_CONTAINERS") or ""
    ).split()
    build_value = settings.get("BATOCERA_GOW_BUILD_MANIFEST")
    stock_value = settings.get("BATOCERA_GOW_STOCK_MANIFEST")
    args.build_manifest = (
        Path(build_value)
        if build_value
        else args.project_root / "output/gow-full-x86/build-manifest.json"
    )
    args.stock_manifest = Path(stock_value) if stock_value else None
    runtime_value = settings.get("BATOCERA_GOW_RUNTIME_ROOT")
    args.runtime_root = Path(runtime_value) if runtime_value else None
    args.output = Path(
        settings.get("BATOCERA_GOW_OUTPUT") or args.project_root / "output/integration"
    )
    ssh = settings.ssh()
    roots = ContentRoots.from_environment(settings.values)
    if (
        ssh.target != args.native_authorized_target
        or args.host_root != args.native_authorized_root
    ):
        msg = "Explicit exact target/resource authorization is required"
        raise NativeError(msg)
    if os.environ.get("PYTEST_XDIST_WORKER"):
        msg = "Native execution refuses parallel pytest workers"
        raise NativeError(msg)
    if (
        args.build_manifest is None
        or args.stock_manifest is None
        or args.render_node is None
        or args.video_caps is None
    ):
        msg = "Build/stock manifests and installed render-node/video-caps are required"
        raise NativeError(msg)
    return ssh, roots, settings


def _cli_configuration(
    args: argparse.Namespace,
    budgets: Budgets,
    roots: ContentRoots,
    settings: HostSettings,
) -> tuple[NativeConfig, BuildSnapshot, dict[str, dict[str, object]]]:
    """Bind explicit CLI inputs to the successful immutable local build snapshot."""
    runtime = args.runtime_root or args.project_root / "output/gow-full-x86/runtime"
    snapshot = BuildSnapshot.verify(
        args.project_root,
        args.build_manifest,
        runtime,
        DockerImages(docker_command(settings.values)),
    )
    image, source, stock, hashes = load_integrity(
        args.build_manifest, args.stock_manifest, runtime, args.tier
    )
    selection = (
        read_reproduction_record(args.reproduce_selection)
        if args.reproduce_selection is not None
        else None
    )
    case_selections: dict[str, dict[str, object]] = {}
    for argument in args.case_selection:
        name, separator, filename = argument.partition("=")
        emulator_case(name)
        if not separator or not filename or name in case_selections:
            msg = "Per-case reproduction must be a unique CASE=RECORD"
            raise NativeError(msg)
        case_selections[name] = read_reproduction_record(Path(filename))
    config = NativeConfig(
        image,
        source,
        stock,
        roots,
        hashes,
        args.render_node,
        args.video_caps,
        tuple(args.infrastructure_container),
        args.host_root,
        args.local_root,
        args.wolf_container,
        args.api_socket,
        args.profile,
        args.uid,
        args.gid,
        args.tier,
        budgets,
        selection,
        args.negative_control,
        case_selections,
        expanded_selection=tuple(args.case),
        project_root=args.project_root,
        catalog=load_catalog(
            args.project_root / "tests/assets/media/stock-es_systems.cfg"
        ),
    )
    return config, snapshot, case_selections


def _apply_cli_qualifications(
    coordinator: Coordinator,
    args: argparse.Namespace,
    case_selections: dict[str, dict[str, object]],
) -> None:
    """Revalidate exact private proof before allowing any expanded native replay."""
    qualified_inputs: dict[str, QualifiedInput] = {}
    for path in args.qualification:
        qualified = coordinator.load_qualification(path)
        name = qualified.identity.case
        if name in qualified_inputs:
            msg = "Duplicate expanded qualification"
            raise NativeError(msg)
        if not args.case or name in args.case:
            qualified_inputs[name] = qualified
    for name, qualified in qualified_inputs.items():
        if name in case_selections and case_selections[name] != qualified.selection:
            msg = "Expanded replay differs from qualified selection"
            raise NativeError(msg)
    coordinator.config = replace(coordinator.config, qualified_inputs=qualified_inputs)


def _run_cli(args: argparse.Namespace, budgets: Budgets) -> int:
    """Own local evidence and interruption cleanup for an authorized native run."""
    if not args.authorize_native:
        msg = "Explicit --authorize-native is required before SSH"
        raise NativeError(msg)
    ssh, roots, settings = _resolve_cli_settings(args)
    config, snapshot, case_selections = _cli_configuration(
        args, budgets, roots, settings
    )
    run_id = uuid.uuid4().hex
    artifacts = Artifacts(args.output, run_id)
    try:
        coordinator = Coordinator(
            config,
            SSHTransport(
                ssh,
                files("batocera_gow.host")
                .joinpath("native_remote.py")
                .read_text(encoding="utf-8"),
            ),
            SystemClock(),
            artifacts,
            run_id,
        )
        coordinator.verify_inputs = snapshot.assert_current
        _apply_cli_qualifications(coordinator, args, case_selections)

        def interrupted(signum: int, _frame: object) -> None:
            coordinator.interrupted = "Operator signal " + str(signum)
            raise InterruptedError(coordinator.interrupted)

        previous = {
            s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            report = coordinator.run()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        sys.stdout.write(
            str(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": report["status"],
                        "artifacts": str(artifacts.path),
                        "emulator_exit_coverage": report["emulator_exit_coverage"],
                    }
                )
            )
            + "\n"
        )
        return 0 if report["status"] == "passed" else 1
    finally:
        artifacts.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Expose target-independent planning and explicitly authorized native tiers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--native-authorized-target")
    parser.add_argument("--native-authorized-root")
    parser.add_argument("operation", choices=("plan", "run"))
    parser.add_argument(
        "--tier",
        choices=(
            "frontend-receivers",
            "frontend-smoke",
            "receiver-smoke",
            "regression",
            "expanded",
            *(case.tier for case in EMULATOR_CASES),
        ),
        default="frontend-receivers",
    )
    parser.add_argument(
        "--authorize-native",
        action="store_true",
        help=(
            "Authorize this target's suite-owned native lobbies/state/input "
            "and bounded owned cleanup only"
        ),
    )
    parser.add_argument("--build-manifest", type=Path)
    parser.add_argument("--stock-manifest", type=Path)
    parser.add_argument("--render-node")
    parser.add_argument("--video-caps")
    parser.add_argument("--ssh-target")
    parser.add_argument("--ssh-identity-file")
    parser.add_argument("--wolf-container")
    parser.add_argument("--api-socket")
    parser.add_argument("--host-root")
    parser.add_argument("--local-root")
    parser.add_argument("--profile")
    parser.add_argument("--uid", type=int)
    parser.add_argument("--gid", type=int)
    parser.add_argument("--infrastructure-container", action="append")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reproduce-selection", type=Path)
    parser.add_argument(
        "--case-selection",
        action="append",
        default=[],
        metavar="CASE=RECORD",
        help=(
            "Replay one exact private selection in regression/expanded; repeat per case"
        ),
    )
    parser.add_argument(
        "--qualification",
        action="append",
        default=[],
        type=Path,
        help=(
            "Explicit private selected-run proof for expanded; never scans directories"
        ),
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="CASE",
        help=("Expanded selection; absent qualified proof remains a visible gap"),
    )
    parser.add_argument("--negative-control", choices=EMULATOR_CONTROLS, default="none")
    for name, value in Budgets().as_dict().items():
        parser.add_argument("--" + name + "-seconds", type=float, default=value)
    args = parser.parse_args(argv)
    if args.case:
        catalog_path = args.project_root / "tests/assets/media/stock-es_systems.cfg"
        available = {
            case.identifier
            for case in load_cases(
                args.project_root / "tests/assets/media/cases.json",
                catalog_path=catalog_path,
            )
        }
        if any(name not in available for name in args.case):
            parser.error("Expanded case is not declared in the selected project")
    try:
        budgets = Budgets(
            **{
                name: number(getattr(args, name + "_seconds"))
                for name in Budgets().as_dict()
            }
        )
    except NativeError as error:
        sys.stderr.write(str("Native budget invalid: " + str(error)) + "\n")
        return 2
    if (
        (args.case_selection and args.tier not in ("regression", "expanded"))
        or ((args.qualification or args.case) and args.tier != "expanded")
        or len(args.case) != len(set(args.case))
    ):
        parser.error("Per-case inputs/qualification require their matching matrix tier")
    if args.operation == "plan":
        sys.stdout.write(
            str(
                json.dumps(
                    {
                        "tier": args.tier,
                        "requested_cases": (
                            [
                                "frontend",
                                "receivers",
                                *(case.identifier for case in EMULATOR_CASES),
                            ]
                            if args.tier == "regression"
                            else ["frontend", "receivers"]
                            if args.tier == "expanded"
                            else [selected_case.identifier]
                            if (selected_case := emulator_tier(args.tier)) is not None
                            else ["frontend"]
                            if args.tier == "frontend-smoke"
                            else ["receivers"]
                            if args.tier == "receiver-smoke"
                            else ["frontend", "receivers"]
                        ),
                        "receiver_checks": (
                            RECEIVER_CASES
                            if args.tier
                            in (
                                "frontend-receivers",
                                "receiver-smoke",
                                "regression",
                                "expanded",
                            )
                            else ()
                        ),
                        "budgets_seconds": budgets.as_dict(),
                        "expanded_requested": args.case,
                        "qualification_record_count": len(args.qualification),
                        "qualification_validation": (
                            "Run validates explicit records before any SSH; "
                            "plan does not establish qualification"
                        ),
                        "coverage": advertised_coverage(
                            (), (), project_root=args.project_root
                        ),
                        "native_effects": False,
                        "limits": LIMITS,
                    },
                    indent=2,
                )
            )
            + "\n"
        )
        return 0
    try:
        return _run_cli(args, budgets)
    except (NativeError, MediaError, OSError, ValueError) as error:
        message = (
            str(error)
            if isinstance(error, (NativeError, MediaError))
            else "Native configuration or build input is invalid or unavailable"
        )
        sys.stderr.write(str("Native prerequisite failed: " + message) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
