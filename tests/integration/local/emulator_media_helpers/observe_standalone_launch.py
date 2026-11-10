"""Observe selected-disc launch readiness and real emulator shutdown boundaries."""

import hashlib
import io
import json
import os
import select
import struct
import subprocess
import sys
import time
import zlib
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import IO, TypedDict
from unittest.mock import patch

from batocera_gow.runtime import emulator_probe as module
from batocera_gow.runtime.emulator_lifecycle import (
    EmulatorLifecycle,
    ExitBudgets,
    Observation,
    PrivateOutput,
    ProcessIdentity,
)
from batocera_gow.runtime.input_transport import live, process_stat
from batocera_gow.runtime.mounted_media import MediaMember, MediaSelection
from batocera_gow.runtime.native_diagnostics import input_permitted


class Stage(TypedDict, total=False):
    """Private observations across the owned process shutdown boundaries."""

    lost: bool
    pressed: bool
    released: bool
    shutdown_live: bool
    zombie: dict[str, object]
    stat_boundary: bool
    pidfd_live_before_stat: bool
    pidfd_live_after_exit: bool
    actual_stat_error: str
    actual_stat_errno: int | None
    chord_at: float
    live_group_observations: list[dict[str, object]]
    waiting_polls: int
    waiting_live: bool
    premature_termination: bool


def main() -> None:
    """Run the launch observation with explicitly owned fixture patches."""
    with ExitStack() as patches:
        observe_launch(patches)


def observe_launch(patches: ExitStack) -> None:  # noqa: C901, PLR0915  # One owned process lifetime retains the original scenario boundaries.
    """Exercise real child lifetimes across launch and shutdown boundaries."""
    directory, case, loss = (Path(sys.argv[1]), sys.argv[2], sys.argv[3])
    disc = directory / "selected.iso"
    image = bytearray(67584)
    image[65536:65556] = b"MICROSOFT*XBOX*MEDIA"
    image[65536 + 2028 : 65536 + 2048] = b"MICROSOFT*XBOX*MEDIA"
    struct.pack_into("<II", image, 65536 + 20, 0, 0)
    disc.write_bytes(image)
    config = directory / "xemu.toml"
    config.write_text(
        "[sys.files]\ndvd_path = " + json.dumps(str(disc)), encoding="utf-8"
    )
    module.XEMU_CONFIG = config
    # Empty-root XDVDFS metadata is synthetic, not bootable console content.
    child = subprocess.Popen(  # noqa: S603  # Fixed checked child script; owned disc and mode argv.
        [
            sys.executable,
            str(Path(__file__).with_name("consumer_standalone_launch.py")),
            str(disc),
            loss,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def command(value: bytes, expected: bytes) -> None:
        child_input.write(value)
        child_input.flush()
        if not select.select([child_output], [], [], 2)[0]:
            message = "Owned child response timed out"
            raise RuntimeError(message)
        if child_output.readline() != expected:
            message = "Unexpected owned child response"
            raise RuntimeError(message)

    assert child.stdin is not None
    assert child.stdout is not None
    assert child.stderr is not None
    child_input, child_output = child.stdin, child.stdout
    probe = module.EmulatorProbe(directory, case=case, roms_view=directory)
    member = MediaMember(str(disc), hashlib.sha256(image).hexdigest(), len(image))
    identity = {
        "system": probe.case.system,
        "entry": str(disc),
        "members": [[member.relative_path, member.sha256, member.size]],
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    probe.selection = MediaSelection(probe.case.system, str(disc), (member,), digest)
    probe.result["media"] = {
        "identity": digest,
        "route": "existing-readonly-mounted-private-media",
        "private_record": "selection.json",
    }
    probe.launcher = child
    probe.launcher_start = process_stat(child.pid)[1]
    launcher_start = probe.launcher_start
    probe.emulator_fd = os.pidfd_open(child.pid)
    emulator_fd = probe.emulator_fd
    probe.emulator_identity = ProcessIdentity(child.pid, probe.launcher_start)
    probe.launcher_output = PrivateOutput(child.stderr)
    launcher_output = probe.launcher_output
    stage: Stage = {
        "lost": False,
        "pressed": False,
        "released": False,
        "shutdown_live": False,
    }

    def exit_child(*, reap: bool) -> None:
        child_input.write(b"exit\n")
        child_input.flush()
        if not select.select([emulator_fd], [], [], 2)[0]:
            message = "Owned child exit timed out"
            raise RuntimeError(message)
        os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
        if reap:
            child.wait(timeout=2)

    def zombie_leader() -> None:
        command(b"zombie\n", b"leader-exiting\n")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            fields = (
                Path(f"/proc/{child.pid}/stat")
                .read_bytes()
                .rpartition(b") ")[2]
                .split()
            )
            if fields[0] == b"Z":
                tasks = len(tuple(Path(f"/proc/{child.pid}/task").iterdir()))
                if tasks < 2 or not live(emulator_fd):
                    message = "Owned zombie leader did not retain a live worker"
                    raise RuntimeError(message)
                try:
                    process_stat(child.pid)
                except ProcessLookupError:
                    pass
                else:
                    message = "Actual zombie leader was accepted as a live leader"
                    raise RuntimeError(message)
                stage["zombie"] = {
                    "state": "Z",
                    "tasks": tasks,
                    "start": int(fields[19]),
                    "pidfd_live": live(emulator_fd),
                    "launcher_code": child.poll(),
                }
                return
            select.select([emulator_fd], [], [], 0.001)
        message = "Owned main thread did not reach zombie state"
        raise RuntimeError(message)

    actual_open = Path.open

    def metadata_open(  # noqa: PLR0913, PLR0917  # Preserve the exact borrowed Path.open argument contract.
        path: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[bytes] | IO[str]:
        if (
            str(path) == f"/proc/{child.pid}/stat"
            and mode == "rb"
            and stage.get("zombie")
        ):
            if loss == "thread-metadata-denied":
                raise PermissionError(13, "Synthetic denied shutdown metadata")
            if loss == "thread-metadata-missing":
                raise FileNotFoundError(2, "Synthetic missing shutdown metadata")
            with actual_open(path, "rb", buffering) as stream:
                raw = stream.read()
            prefix, separator, tail = raw.rpartition(b") ")
            fields = tail.split()
            if loss == "thread-metadata-wrong-pid":
                raw = (
                    str(child.pid + 1).encode()
                    + b" ("
                    + prefix.partition(b" (")[2]
                    + separator
                    + tail
                )
            elif loss == "thread-metadata-wrong-start":
                fields[19] = str(int(fields[19]) + 1).encode()
                raw = prefix + separator + b" ".join(fields)
            elif loss == "thread-metadata-not-zombie":
                fields[0] = b"S"
                raw = prefix + separator + b" ".join(fields)
            elif loss == "thread-metadata-malformed":
                raw = prefix + separator + b"Z invalid"
            elif loss == "thread-metadata-oversized":
                raw += b"0" * 4097
            return io.BytesIO(raw)
        return actual_open(path, mode, buffering, encoding, errors, newline)

    if loss.startswith("thread-metadata-"):
        patches.enter_context(patch.object(Path, "open", metadata_open))

    def observe_stat(pid: int) -> tuple[int, int]:
        if pid == child.pid and stage.get("zombie") and (loss == "thread-stat-denied"):
            raise PermissionError(13, "Synthetic denied original stat")
        if pid == child.pid and stage["released"] and (not stage.get("stat_boundary")):
            stage["stat_boundary"] = True
            stage["pidfd_live_before_stat"] = live(emulator_fd)
            if loss in ("race-zombie", "race-reaped", "stat-denied-after-exit"):
                exit_child(reap=loss == "race-reaped")
                stage["pidfd_live_after_exit"] = live(emulator_fd)
                try:
                    process_stat(pid)
                except (FileNotFoundError, ProcessLookupError) as error:
                    stage["actual_stat_error"] = type(error).__name__
                    stage["actual_stat_errno"] = error.errno
                else:
                    message = "Owned exit did not remove live proc metadata"
                    raise RuntimeError(message)
            if loss in ("stat-denied", "stat-denied-after-exit"):
                raise PermissionError(13, "Synthetic denied proc metadata")
            if loss == "stat-missing-live":
                raise FileNotFoundError(2, "Synthetic missing proc metadata")
            if loss == "stat-lookup-live":
                raise ProcessLookupError(pid)
            if loss == "wrong-start":
                parent, start = process_stat(pid)
                return (parent, start + 1)
        return process_stat(pid)

    if not loss.startswith("thread-") or loss == "thread-stat-denied":
        patches.enter_context(patch.object(module, "process_stat", observe_stat))

    class Display:
        """Control only the owned child's visible and active window observations."""

        visible = True
        unavailable = False

        def active_pid(self) -> int:
            """Return the owned child while display observations remain available."""
            if self.unavailable:
                message = "Owned display gone during shutdown"
                raise FileNotFoundError(message)
            return child.pid

        def render_window(self, pid: int, *, application: str) -> bool:  # noqa: ARG002  # Borrowed desktop API; only visibility is controlled here.
            """Return the selected launch window's controlled visibility."""
            if self.unavailable:
                message = "Owned render window gone during shutdown"
                raise FileNotFoundError(message)
            return self.visible

    display = Display()
    patches.enter_context(patch.object(probe, "desktop", display))

    def lose_readiness() -> None:
        if stage["lost"]:
            return
        stage["lost"] = True
        if loss.endswith("window"):
            display.visible = False
        else:
            command(b"close\n", b"closed\n")

    def png_chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff\xff\xff"))
        + png_chunk(b"IEND", b"")
    )

    def capture(path: Path) -> dict[str, str]:
        path.write_bytes(png)
        if path.name == "emulator-before-exit.png" and loss.startswith("capture-"):
            lose_readiness()
        if path.name == "emulator-before-exit.png" and loss == "pre-chord-death":
            exit_child(reap=False)
        if path.name == "emulator-before-exit.png" and loss == "thread-pre-chord":
            zombie_leader()
        return {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    patches.enter_context(patch.object(module, "capture_checkpoint", capture))
    patches.enter_context(
        patch.object(module, "rendered_content", lambda path: path.read_bytes() == png)
    )
    patches.enter_context(
        patch.object(module, "transport_ready", lambda _path: {"fixture": True})
    )

    def consumption() -> bool:
        if stage["pressed"]:
            message = "Owned native configuration gone during shutdown"
            raise FileNotFoundError(message)
        return True

    patches.enter_context(patch.object(probe, "native_consumption", consumption))
    patches.enter_context(patch.object(probe, "duckstation_renderer", consumption))

    class Pad:
        """Trigger the controlled shutdown changes on native chord boundaries."""

        def __init__(self) -> None:
            """Own the held-key set for this single synthetic pad."""
            self.held: set[int] = set()

        def write(self, event_type: int, code: int, value: int) -> None:  # noqa: ARG002  # Preserve the native-pad write interface.
            """Track held keys without creating or qualifying a native device."""
            if value:
                self.held.add(code)
            else:
                self.held.discard(code)

        def syn(self) -> None:
            """Apply press and release observations to the real owned process."""
            if self.held == {1, 2} and (not stage["pressed"]):
                stage["pressed"] = True
                stage["chord_at"] = clock.value
                lose_readiness()
                display.visible = False
                probe.standalone_output()
                stage["shutdown_live"] = live(emulator_fd)
                config.unlink()
                display.unavailable = True
            elif stage["pressed"] and (not self.held):
                stage["released"] = True
                if loss == "forced-teardown":
                    probe.forced = True
                if loss == "wrong-pid":
                    probe.emulator_identity = ProcessIdentity(
                        os.getpid(), process_stat(os.getpid())[1]
                    )
                if loss.startswith("thread-"):
                    zombie_leader()
                if loss == "thread-wrong-identity":
                    probe.emulator_identity = ProcessIdentity(
                        child.pid, launcher_start + 1
                    )

    patches.enter_context(patch.object(probe, "pad", Pad()))
    patches.enter_context(
        patch.object(
            probe,
            "evdev",
            SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, EV_ABS=3)),
            create=True,
        )
    )
    patches.enter_context(
        patch.object(
            probe,
            "definition",
            {
                "guide_code": 1,
                "start_code": 2,
                "buttons": [1, 2],
                "axes": [],
                "hat": [],
            },
            create=True,
        )
    )
    native_guide_start = probe.guide_start

    def guide_start() -> bool:
        completed = native_guide_start()
        if loss in ("thread-incomplete-press", "thread-incomplete-release"):
            key = "pressed" if loss == "thread-incomplete-press" else "released"
            chord = probe.result["chord"]
            assert isinstance(chord, dict)
            chord[key] = False
        return completed

    patches.enter_context(patch.object(probe, "guide_start", guide_start))

    def permission() -> None:
        if loss == "thread-lease-loss" and stage.get("waiting_polls", 0) >= 2:
            message = "Owned inspection lease expired during worker shutdown"
            raise RuntimeError(message)
        input_permitted()

    patches.enter_context(patch.object(probe, "permission", permission))
    runtime_observe = probe.observe

    def observe() -> Observation:
        row = runtime_observe()
        if stage.get("zombie") and live(emulator_fd):
            stage.setdefault("live_group_observations", []).append(
                {"alive": row.alive, "launcher_code": row.launcher_code}
            )
        return row

    patches.enter_context(patch.object(probe, "observe", observe))

    class Clock:
        """Advance lifecycle deadlines without replacing real process observations."""

        value = 0.0

        def now(self) -> float:
            """Return elapsed synthetic lifecycle time in seconds."""
            return self.value

        def sleep(self, seconds: float) -> None:
            """Advance deadlines and drive the selected shutdown transition."""
            self.value += seconds
            if loss.startswith("interval-") and self.value >= 0.1:
                lose_readiness()
            if stage["released"] and child.poll() is None:
                if loss.startswith("thread-"):
                    stage["waiting_polls"] = stage.get("waiting_polls", 0) + 1
                    stage["waiting_live"] = live(emulator_fd)
                    stage["premature_termination"] = (
                        probe.result.get("termination_observation") is not None
                    )
                    if loss == "thread-timeout" or stage["waiting_polls"] < 4:
                        return
                child_input.write(b"exit\n")
                child_input.flush()
                child.wait(timeout=2)

    clock = Clock()
    transition = None
    failure = None
    failure_errno: int | None = None
    try:
        if not select.select([child_output], [], [], 2)[0]:
            message = "Owned child readiness timed out"
            raise RuntimeError(message)
        if child_output.readline() != b"ready\n":
            message = "Owned child failed to open selected disc"
            raise RuntimeError(message)
        try:
            transition = EmulatorLifecycle(
                probe,
                clock,
                ExitBudgets(startup=1, before_chord=0.2, exit=1, poll=0.05),
            ).run()
        except (OSError, RuntimeError) as error:
            failure = type(error).__name__
            failure_errno = error.errno if isinstance(error, OSError) else None
        sys.stdout.write(
            json.dumps(
                {
                    "transition": transition,
                    "failure": failure,
                    "stage": stage,
                    "latest_display": probe.result.get("backend_display"),
                    "chord": probe.result.get("chord"),
                    "launch_failure_diagnostic": probe.result.get(
                        "launch_failure_diagnostic"
                    ),
                    "child_code": child.poll(),
                    "forced": probe.forced,
                    "failure_errno": failure_errno,
                    "process_failure": getattr(
                        probe, "process_observation_failure", None
                    ),
                    "identity": {"pid": child.pid, "start": probe.launcher_start},
                }
            )
            + "\n"
        )
    finally:
        patches.close()
        if child.poll() is None:
            child_input.write(b"exit\n")
            child_input.flush()
            child.wait(timeout=2)
        launcher_output.close()
        os.close(emulator_fd)
        child_input.close()
        child_output.close()


if __name__ == "__main__":
    main()
