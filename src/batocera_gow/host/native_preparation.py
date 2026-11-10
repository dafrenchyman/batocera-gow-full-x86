"""Freshness-gated native image preparation and serial scenario ownership.

Importing this module resolves no settings and performs no Docker or SSH work.
Only an explicitly authorized caller may construct and prepare a native session.
"""

import base64
import hashlib
import json
import signal
import tempfile
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from types import FrameType, TracebackType
from typing import NoReturn, Self

from batocera_gow.host.common import docker_command
from batocera_gow.host.native_freshness import (
    MAX_IMAGE_BYTES,
    BuildSnapshot,
    DockerImages,
    LocalImages,
)
from batocera_gow.host.native_integration import (
    Artifacts,
    Coordinator,
    NativeCase,
    NativeConfig,
    SSHTransport,
    SystemClock,
    Transport,
    load_integrity,
    read_reproduction_record,
    sanitize,
)
from batocera_gow.host.native_matrix import (
    RECEIVER_CASES,
    advertised_coverage,
    aggregate_regression,
)
from batocera_gow.host.native_remote import (
    IMAGE_CHUNK_BYTES,
    NativeError,
    record,
    sequence,
    text,
)
from batocera_gow.host.settings import HostSettings
from batocera_gow.provenance import file_sha256
from batocera_gow.runtime.media_catalog import emulator_case, load_catalog
from batocera_gow.runtime.mounted_media import ContentRoots


def _interrupt(signum: int, _frame: FrameType | None) -> NoReturn:
    """Route authorized execution interruption through coordinator cleanup."""
    raise InterruptedError("Native execution received signal " + str(signum))


@contextmanager
def _cleanup_signals() -> Iterator[None]:
    """Restore borrowed process signal handlers after serial native ownership."""
    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, _interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def require_authorization(  # noqa: PLR0913 - connection knowledge and independent target/root/worker consent must stay explicit.
    *,
    enabled: bool,
    target: str,
    authorized_target: str | None,
    host_root: str,
    authorized_root: str | None,
    workers: str | None,
    worker_environment: Mapping[str, str],
) -> None:
    """Require deliberate effect authorization independently of settings values."""
    if not enabled or target != authorized_target or host_root != authorized_root:
        message = (
            "Native execution requires --authorize-native and exact "
            "target/resource authorization"
        )
        raise NativeError(message)
    if workers not in (None, "0", "no") or worker_environment.get(
        "PYTEST_XDIST_WORKER"
    ):
        message = "Native execution refuses parallel pytest workers"
        raise NativeError(message)


class NativeSession:
    """Own one prepared image and independent serial case coordinators."""

    def __init__(
        self,
        snapshot: BuildSnapshot,
        config: NativeConfig,
        transport: Transport,
        images: LocalImages,
        artifacts: Artifacts,
    ) -> None:
        """Borrow explicit build/transport boundaries and own only session evidence."""
        if snapshot.image != config.image:
            message = "Native configuration differs from verified image"
            raise NativeError(message)
        self.snapshot = snapshot
        self.config = config
        self.transport = transport
        self.images = images
        self.artifacts = artifacts
        self.reports: dict[str, dict[str, object]] = {}
        self.preparation: dict[str, object] = {"status": "not-run"}
        self.blocked: str | None = None
        self.retain_reservation = False
        self.prepared = False
        self.running = False
        self.reservation: tuple[Coordinator, NativeCase] | None = None
        self.psx_selections: dict[str, dict[str, object]] = {}

    def __enter__(self) -> Self:
        """Prepare once and unwind all owned resources if setup cannot yield."""
        completed = False
        try:
            self.prepare()
            completed = True
            return self
        finally:
            if not completed:
                self.finish()

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finalize aggregate evidence and owned reservation without masking drift."""
        self.finish()

    def _remove_owned_state(self, coordinator: Coordinator, case: NativeCase) -> None:
        """Require an explicit successful owned-state removal response."""
        if not case.pin:
            message = "Native allocation response is unresolved; retain owned state"
            raise NativeError(message)
        result = coordinator.call(
            "remove_state",
            time.monotonic() + self.config.budgets.cleanup,
            case,
            startup_resolved=True,
        )
        if result.get("removed") is not True:
            message = "Native owned-state cleanup unresolved"
            raise NativeError(message)

    def _upload_image(
        self,
        coordinator: Coordinator,
        transfer: NativeCase,
        archive: Path,
        deadline: float,
        identity: tuple[int, str],
    ) -> None:
        """Stream one bounded archive and verify digest and loaded image."""
        size, digest = identity
        offset = 0
        with archive.open("rb") as stream:
            while data := stream.read(IMAGE_CHUNK_BYTES):
                coordinator.discover(time.monotonic() + self.config.budgets.call, None)
                response = coordinator.call(
                    "image_chunk",
                    deadline,
                    transfer,
                    offset=offset,
                    data=base64.b64encode(data).decode("ascii"),
                )
                offset += len(data)
                if response.get("offset") != offset:
                    message = "Remote image transfer offset mismatch"
                    raise NativeError(message)
        coordinator.discover(time.monotonic() + self.config.budgets.call, None)
        started = time.monotonic()
        remaining = min(300, deadline - started)
        if remaining <= 0:
            message = "Native image transfer deadline expired"
            raise NativeError(message)
        request = coordinator.base("image_load", transfer)
        request.update(offset=size, sha256=digest, timeout=remaining)
        loaded = self.transport.request(request, remaining)
        if time.monotonic() >= started + remaining:
            message = "Native image transfer deadline expired"
            raise NativeError(message)
        if loaded.get("image") != self.snapshot.image:
            message = "Loaded native image identity mismatch"
            raise NativeError(message)
        self.preparation.update(
            status="passed",
            image=self.snapshot.image,
            reused=False,
            archive_sha256=digest,
            archive_bytes=size,
        )

    def _transfer_image(self, coordinator: Coordinator) -> None:
        """Own temporary archive storage and cleanup of one exclusive transfer home."""
        transfer = coordinator.make_case("frontend")
        attempted = False
        transfer_evidence: dict[str, object] = {
            "case_id": transfer.case_id,
            "pin": None,
            "owner_marker_sha256": hashlib.sha256(transfer.token.encode()).hexdigest(),
            "cleanup_complete": False,
        }
        deadline = time.monotonic() + 900
        try:
            with tempfile.TemporaryDirectory(
                prefix="native-image-", dir=self.artifacts.path
            ) as temporary:
                archive = Path(temporary) / "image.tar.gz"
                self.images.save(
                    self.snapshot.image, archive, min(300, deadline - time.monotonic())
                )
                size = archive.stat().st_size
                if not 0 < size <= MAX_IMAGE_BYTES:
                    message = (
                        "Local image archive exceeds bounded native transfer storage"
                    )
                    raise NativeError(message)
                digest = file_sha256(archive)
                coordinator.discover(time.monotonic() + self.config.budgets.call, None)
                self.preparation = {
                    "status": "preparing",
                    "transfer": transfer_evidence,
                }
                attempted = True
                allocation = coordinator.call("allocate", deadline, transfer)
                transfer.pin = record(allocation.get("pin"))
                transfer_evidence["pin"] = transfer.pin
                self._upload_image(
                    coordinator, transfer, archive, deadline, (size, digest)
                )
        finally:
            if attempted:
                try:
                    self._remove_owned_state(coordinator, transfer)
                    transfer_evidence["cleanup_complete"] = True
                except (NativeError, OSError, ValueError) as error:
                    transfer_evidence["cleanup_complete"] = False
                    self.retain_reservation = True
                    self.blocked = "Native image transfer cleanup unresolved"
                    self.preparation["status"] = "failed"
                    raise NativeError(self.blocked) from error

    def prepare(self) -> None:
        """Reuse exact remote image or upload/load once after read-only safety gates."""
        if self.prepared:
            return
        self.snapshot.assert_current()
        coordinator = Coordinator(
            self.config, self.transport, SystemClock(), self.artifacts, uuid.uuid4().hex
        )
        preflight = coordinator.call(
            "preflight",
            time.monotonic() + self.config.budgets.call,
            prepare_image=True,
            protected=[
                str(Path(self.config.host_root) / "profile-data"),
                self.config.roots.roms,
                self.config.roots.bios,
            ],
        )
        coordinator.preflight = preflight
        coordinator.wolf_id = text(preflight.get("wolf_id"))
        coordinator.discover(time.monotonic() + self.config.budgets.call, None)
        reservation = coordinator.make_case("frontend")
        reservation.case_id = "native-session-reservation"
        self.reservation = (coordinator, reservation)
        allocated = coordinator.call(
            "allocate", time.monotonic() + self.config.budgets.call, reservation
        )
        reservation.pin = record(allocated.get("pin"))
        status = coordinator.call(
            "image_status", time.monotonic() + self.config.budgets.call
        )
        if status.get("present") is True:
            if status.get("image") != self.snapshot.image:
                message = "Remote image identity mismatch"
                raise NativeError(message)
            self.preparation = {
                "status": "passed",
                "image": self.snapshot.image,
                "reused": True,
            }
            self.prepared = True
            return
        if status.get("present") is not False:
            message = "Remote image availability is unknown"
            raise NativeError(message)
        self._transfer_image(coordinator)
        self.snapshot.assert_current()
        self.prepared = True

    def run(self, name: str) -> dict[str, object]:
        """Execute actual maintained assertions with independent owned case state."""
        if not self.prepared or self.blocked or self.running or name in self.reports:
            message = (
                self.blocked or "Native session is not ready for a new serial case"
            )
            raise NativeError(message)
        self.snapshot.assert_current()
        receiver = name if name in RECEIVER_CASES else None
        tier = (
            "frontend-smoke"
            if name == "frontend"
            else "receiver-smoke"
            if receiver
            else emulator_case(name).tier
        )
        selection = (
            next(iter(self.psx_selections.values()), None)
            if name in ("psx-duckstation", "psx-duckstation-vulkan")
            else None
        )
        config = replace(
            self.config, tier=tier, receiver_case=receiver, selection=selection
        )
        run_id = uuid.uuid4().hex
        artifacts = Artifacts(self.artifacts.path, run_id)
        self.running = True
        try:
            coordinator = Coordinator(
                config, self.transport, SystemClock(), artifacts, run_id
            )
            coordinator.verify_inputs = self.snapshot.assert_current
            report = coordinator.run()
            self.reports[name] = report
            if report.get("cleanup_complete") is not True:
                self.retain_reservation = True
                self.blocked = "Native cleanup or isolation barrier unresolved"
            elif report.get("interruption"):
                self.blocked = "Native case interrupted after cleanup"
            self._retain_psx_selection(name, report, artifacts.path)
            self.snapshot.assert_current()
        except (NativeError, OSError, ValueError, InterruptedError):
            self.blocked = (
                self.blocked or "Native case failed before a current-input result"
            )
            raise
        else:
            return report
        finally:
            self.running = False
            artifacts.close()

    def _retain_psx_selection(
        self, name: str, report: dict[str, object], directory: Path
    ) -> None:
        """Bind independently executed renderers to the same private disc record."""
        if name not in ("psx-duckstation", "psx-duckstation-vulkan"):
            return
        rows = [record(row) for row in sequence(report.get("cases"))]
        if not any(
            row.get("name") == name and row.get("status") == "passed" for row in rows
        ):
            return
        selected = read_reproduction_record(directory / (name + "-selection.json"))
        self.psx_selections[name] = selected
        self._check_psx_selections()
        if self.blocked:
            raise NativeError(self.blocked)

    def _check_psx_selections(self) -> None:
        """Refuse aggregate acceptance if renderer observations name different media."""
        selections = list(self.psx_selections.values())
        if selections and any(value != selections[0] for value in selections[1:]):
            self.blocked = "DuckStation renderers used different selected media"

    def finish(self) -> dict[str, object]:
        """Publish full aggregate semantics; a selected subset never passes the gate."""
        self._check_psx_selections()
        if self.reservation is not None and not self.retain_reservation:
            coordinator, reservation = self.reservation
            try:
                self._remove_owned_state(coordinator, reservation)
                self.reservation = None
            except (NativeError, OSError, ValueError):
                self.blocked = "Native reservation cleanup unresolved"
                self.retain_reservation = True
        drift: str | None = None
        try:
            self.snapshot.assert_current()
        except NativeError as error:
            drift = str(error)
            self.blocked = drift
        rows: list[dict[str, object]] = []
        receivers: list[dict[str, object]] = []
        for name, report in self.reports.items():
            if name in RECEIVER_CASES:
                observed = [
                    record(row) for row in sequence(report.get("receiver_checks"))
                ]
                receivers.extend(row for row in observed if row.get("name") == name)
            else:
                rows.extend(record(row) for row in sequence(report.get("cases")))
        receiver_passed = len(receivers) == len(RECEIVER_CASES) and all(
            row.get("status") == "passed" for row in receivers
        )
        if receivers:
            rows.append(
                {
                    "name": "receivers",
                    "status": "passed" if receiver_passed else "failed",
                }
            )
        evidence = (
            self.prepared
            and not self.blocked
            and all(
                report.get("evidence_complete") is True
                for report in self.reports.values()
            )
        )
        cleanup = (
            not self.retain_reservation
            and self.reservation is None
            and all(
                report.get("cleanup_complete") is True
                for report in self.reports.values()
            )
        )
        aggregate = aggregate_regression(
            rows,
            receivers,
            evidence_complete=evidence,
            cleanup_complete=cleanup,
            interrupted=self.blocked is not None,
        )
        aggregate.update(
            schema=1,
            image=self.snapshot.image,
            declared_inputs=self.snapshot.inputs,
            runtime_inputs=self.snapshot.runtime_inputs,
            preparation=self.preparation,
            cases=rows,
            receiver_checks=receivers,
            selected_cases=list(self.reports),
            reports=self.reports,
            drift=drift,
            session_error=self.blocked,
            full_frontend_receiver_gate=(
                receiver_passed
                and evidence
                and cleanup
                and any(
                    row.get("name") == "frontend" and row.get("status") == "passed"
                    for row in rows
                )
            ),
            selection_status=(
                "passed"
                if self.reports
                and evidence
                and cleanup
                and all(
                    report.get("status") == "passed" for report in self.reports.values()
                )
                else "failed"
            ),
            reservation=(
                {
                    "case_id": self.reservation[1].case_id,
                    "pin": self.reservation[1].pin,
                    "owner_marker_sha256": hashlib.sha256(
                        self.reservation[1].token.encode()
                    ).hexdigest(),
                }
                if self.reservation is not None
                else None
            ),
            coverage=advertised_coverage(
                [
                    str(row["name"])
                    for row in rows
                    if row.get("status") == "passed"
                    and row.get("name") not in ("frontend", "receivers")
                ],
                [
                    name
                    for name in self.reports
                    if name not in ("frontend", *RECEIVER_CASES)
                ],
                project_root=self.config.project_root,
            ),
        )
        self.artifacts.put(
            "session-report.json",
            json.dumps(sanitize(aggregate), indent=2, sort_keys=True).encode() + b"\n",
        )
        if self.blocked:
            raise NativeError(self.blocked)
        return aggregate


def configured_native(
    settings: HostSettings,
    project_root: Path,
    build: Path,
    stock: Path,
    runtime: Path,
) -> NativeConfig:
    """Assemble frozen native configuration from one already-resolved snapshot."""
    image, source, stock_sha, hashes = load_integrity(
        build, stock, runtime, "regression"
    )

    def setting(name: str, default: str | None = None) -> str:
        value = settings.get("BATOCERA_GOW_" + name, default)
        if not value:
            raise NativeError(
                "Required native setting is missing: BATOCERA_GOW_" + name
            )
        return value

    try:
        return NativeConfig(
            image,
            source,
            stock_sha,
            ContentRoots.from_environment(settings.values),
            hashes,
            setting("RENDER_NODE"),
            setting("VIDEO_CAPS"),
            tuple(
                (settings.get("BATOCERA_GOW_INFRASTRUCTURE_CONTAINERS") or "").split()
            ),
            host_root=setting("HOST_ROOT", "/etc/wolf"),
            local_root=setting("LOCAL_ROOT", "/etc/wolf"),
            wolf_container=setting("WOLF_CONTAINER", "wolf"),
            api_socket=setting("API_SOCKET", "/var/run/wolf/wolf.sock"),
            profile=setting("PROFILE", "user"),
            uid=int(setting("UID", "1000")),
            gid=int(setting("GID", "1000")),
            tier="regression",
            project_root=project_root,
            catalog=load_catalog(
                project_root / "tests/assets/media/stock-es_systems.cfg"
            ),
        )
    except ValueError:
        msg = "Native settings are invalid"
        raise NativeError(msg) from None


@contextmanager
def open_native_session(  # noqa: PLR0913 - explicit target/root consent and worker safety are independent of settings.
    settings: HostSettings,
    *,
    project_root: Path,
    authorized_target: str | None,
    authorized_root: str | None,
    enabled: bool,
    workers: str | None = None,
    worker_environment: Mapping[str, str],
) -> Iterator[NativeSession]:
    """Own fixture preparation and finalization, including failure before yield."""
    ssh = settings.ssh()
    host_root = settings.get("BATOCERA_GOW_HOST_ROOT", "/etc/wolf") or "/etc/wolf"
    require_authorization(
        enabled=enabled,
        target=ssh.target,
        authorized_target=authorized_target,
        host_root=host_root,
        authorized_root=authorized_root,
        workers=workers,
        worker_environment=worker_environment,
    )
    root = project_root.resolve()
    build = Path(
        settings.get("BATOCERA_GOW_BUILD_MANIFEST")
        or root / "output/gow-full-x86/build-manifest.json"
    )
    stock_value = settings.get("BATOCERA_GOW_STOCK_MANIFEST")
    if not stock_value:
        msg = "BATOCERA_GOW_STOCK_MANIFEST must select the verified stock inventory"
        raise NativeError(msg)
    stock = Path(stock_value)
    runtime = Path(
        settings.get("BATOCERA_GOW_RUNTIME_ROOT")
        or root / "output/gow-full-x86/runtime"
    )
    images = DockerImages(docker_command(settings.values))
    snapshot = BuildSnapshot.verify(root, build, runtime, images)
    config = configured_native(settings, root, build, stock, runtime)
    artifacts = Artifacts(
        Path(settings.get("BATOCERA_GOW_OUTPUT") or root / "output/integration"),
        uuid.uuid4().hex,
    )
    try:
        session = NativeSession(
            snapshot,
            config,
            SSHTransport(
                ssh,
                files("batocera_gow.host")
                .joinpath("native_remote.py")
                .read_text(encoding="utf-8"),
            ),
            images,
            artifacts,
        )
        with _cleanup_signals(), session:
            yield session
    finally:
        artifacts.close()
