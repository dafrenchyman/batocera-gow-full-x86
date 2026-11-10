"""Model requests and observed ownership at the approved coordinator boundary.

These deterministic observations are host logic fixtures, never native evidence.
The filesystem and delivered-helper tests exercise their real public effects.
"""

import base64
import dataclasses
import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import zlib
from collections.abc import Iterator
from contextlib import closing
from importlib.resources import files
from pathlib import Path, PosixPath
from typing import override

import pytest

from batocera_gow.host import native_matrix
from batocera_gow.host.native_integration import (
    ENTRYPOINT,
    Artifacts,
    Budgets,
    Coordinator,
    NativeConfig,
    SSHTransport,
    load_integrity,
    main,
    png_identity,
    read_reproduction_record,
    sanitize,
)
from batocera_gow.host.native_matrix import RECEIVER_CASES
from batocera_gow.host.native_remote import (
    NativeError,
    Operations,
    OwnedState,
    identity,
    number,
    record,
    sequence,
    text,
)
from batocera_gow.host.ssh_config import SettingsError, SSHConfig
from batocera_gow.runtime import native_diagnostics as diagnostics
from batocera_gow.runtime.media_catalog import (
    EMULATOR_CASES,
    STOCK_SHA256,
    load_catalog,
)
from batocera_gow.runtime.mounted_media import ContentRoots
from batocera_gow.runtime.native_diagnostics import DiagnosticError, frontend_ready_flag

MISSING_OBSERVATION = object()


def alter_observations(
    report: dict[str, object],
    changes: dict[tuple[str, ...], object],
) -> None:
    """Apply explicitly declared fixture damage to independently modeled evidence.

    Args:
        report: Mutable synthetic report, never a native observation.
        changes: Field paths and replacement values. MISSING_OBSERVATION deletes
            a field so absence is distinct from a null or malformed value.
    """
    for path, value in changes.items():
        parent = report
        for key in path[:-1]:
            child = record(parent[key])
            parent[key] = child
            parent = child
        if value is MISSING_OBSERVATION:
            del parent[path[-1]]
        else:
            parent[path[-1]] = value


def fixture_png(*, invalid_compression: bool = False) -> bytes:
    """Encode real tiny PNG pixels for transfer validation, not native proof."""

    def chunk(kind: bytes, value: bytes) -> bytes:
        return (
            struct.pack(">I", len(value))
            + kind
            + value
            + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(
            b"IDAT",
            b"invalid zlib stream"
            if invalid_compression
            else zlib.compress(b"\x00\x12\x34\x56"),
        )
        + chunk(b"IEND", b"")
    )


class FakeClock:
    """Advance deadlines without sleeps or wall-clock timing assertions."""

    def __init__(self) -> None:
        """Start the modeled monotonic clock at zero seconds."""
        self.value = 0.0

    def now(self) -> float:
        """Return deterministic monotonic seconds."""
        return self.value

    def sleep(self, seconds: float) -> None:
        """Advance exactly the requested finite observation interval."""
        self.value += seconds


class World:
    """A native resource lifecycle, with independent observation/failure knobs."""

    def __init__(self, clock: FakeClock) -> None:
        """Create isolated resource observations driven by the supplied clock."""
        self.clock = clock
        self.effects: list[str] = []
        self.requests: list[dict[str, object]] = []
        self.active: dict[str, object] | None = None
        self.lobby = False
        self.container = False
        self.running = False
        self.busy = False
        self.late_contention = False
        self.discovery_loss = False
        self.lost_create = False
        self.late_start = False
        self.bad_isolation = False
        self.withhold_report = False
        self.bad_report = False
        self.missing_receiver = False
        self.capture_loss = False
        self.invalid_compression = False
        self.devices: list[dict[str, object]] = [
            {
                "PathOnHost": "/dev/uinput",
                "PathInContainer": "/dev/uinput",
                "CgroupPermissions": "rwm",
            }
        ]
        self.final_source: dict[str, object] = {
            "source_pid": 23,
            "role": "final",
            "name": "batocera hotkeys",
            "node": "/dev/input/event77",
            "sysname": "input103",
        }
        self.fail_stop = False
        self.fail_collect = False
        self.change_identity = False
        self.leased = False
        self.cleaned: list[str] = []

    def snapshot(self) -> dict[str, object]:
        """Observe a world, including resources whose create response was lost."""
        if self.discovery_loss and self.leased:
            msg = "Discovery unavailable"
            raise NativeError(msg)
        case = self.active
        lobbies: list[object] = []
        containers: list[object] = []
        if case is not None:
            if self.lobby:
                lobbies.append(
                    {
                        "id": "lobby-1",
                        "name": case["case_id"],
                        "profile": "user",
                        "runner_hash": case["runner_hash"],
                        "pin_required": True,
                        "connected": 0,
                    }
                )
            if self.container:
                containers.append(
                    {
                        "id": "e" * 64,
                        "name": "fixture",
                        "owner": case["token"],
                        "image": "sha256:"
                        + ("f" if self.change_identity and self.leased else "a") * 64,
                        "home": [
                            text(case["host_root"])
                            + "/test-runs/"
                            + text(case["case_id"])
                        ],
                        "native": True,
                        "running": self.running,
                        "paused": False,
                    }
                )
        return {
            "session_count": 1
            if self.busy or (self.late_contention and self.leased)
            else 0,
            "lobbies": lobbies,
            "containers": containers,
        }

    def inspection(self, request: dict[str, object]) -> dict[str, object]:
        """Supply a meaningful effective container, not an echo of inspection args."""
        receiver = text(request["case_id"]).endswith("-receivers")
        home = text(request["host_root"]) + "/test-runs/" + text(request["case_id"])
        environment = [
            "PUID=1000",
            "PGID=1000",
            "LANG=en_US.UTF-8",
            "LC_ALL=en_US.UTF-8",
            "GOW_NATIVE_RESULTS=/home/retro/.native-evidence",
            "GOW_NATIVE_LEASE=/home/retro/.native-control/lease",
            "GOW_NATIVE_FRONTEND_TIMEOUT=4",
        ]
        if receiver:
            environment.extend(
                [
                    "GOW_INPUT_TRIAL_RESULTS=/home/retro/.native-evidence",
                    "GOW_INPUT_TRIAL_GATE=/home/retro/.native-control/lease",
                ]
            )
        return {
            "content_roots": {"roms": "/library", "bios": "/library/bios"},
            "container": {
                "Image": "sha256:" + "a" * 64,
                "State": {"Running": True},
                "Config": {
                    "Entrypoint": ENTRYPOINT,
                    "Cmd": ["/usr/bin/python3", "/opt/gow-full-x86/transport_probe.py"]
                    if receiver
                    else ["/opt/gow-full-x86/frontend.sh"],
                    "Env": environment,
                },
                "HostConfig": {
                    "Privileged": self.bad_isolation,
                    "PidMode": "",
                    "IpcMode": "private",
                    "NetworkMode": "bridge",
                    "ShmSize": 2 * 1024**3,
                    "CapAdd": ["NET_ADMIN", "SYS_NICE", "SYS_PTRACE"],
                    "SecurityOpt": [],
                    "DeviceCgroupRules": ["c 13:* rwm", "c 240:* rwm"],
                    "Devices": self.devices,
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": source,
                        "Destination": destination,
                        "RW": writable,
                    }
                    for source, destination, writable in [
                        (home, "/home/retro", True),
                        (home + "/udev", "/run/udev", True),
                        ("/library", "/home/retro/userdata/roms", False),
                        ("/library/bios", "/home/retro/userdata/bios", False),
                        (
                            text(request["host_root"]) + "/fake-udev",
                            "/usr/bin/fake-udev",
                            True,
                        ),
                    ]
                ],
            },
        }

    def evidence(self, request: dict[str, object]) -> dict[str, object]:
        """Publish reports only after inspection has opened a permission lease."""
        if self.fail_collect:
            msg = "Evidence transfer failed"
            raise NativeError(msg)
        files: dict[str, object] = {
            "startup.json": base64.b64encode(b'{"uid":1000,"gid":1000}').decode()
        }
        if not self.leased or self.withhold_report:
            return {"files": files}
        receiver = text(request["case_id"]).endswith("-receivers")
        names = list(RECEIVER_CASES) if receiver else ["frontend-ready"]
        captures = [
            {
                "path": name + ".png",
                "sha256": hashlib.sha256(fixture_png()).hexdigest(),
                "mechanism": "authenticated-libX11-XGetImage-stock-Pillow",
            }
            for name in names
        ]
        if receiver:
            rows = [
                {"name": name, "status": "passed", "capture": capture}
                for name, capture in zip(names, captures, strict=True)
            ]
            if self.missing_receiver:
                rows.pop()
            report: dict[str, object] = {
                "status": "passed",
                "cases": rows,
                "not_run_cases": [],
                "cleanup": {"status": "passed"},
                "stock_hashes": {"unchanged": True},
            }
        else:
            report = {
                "status": "passed",
                "frontend": {
                    "pid": 22,
                    "executable": "emulationstation",
                    "active_window": True,
                    "completed_initialization": True,
                    "ready_flag_identity": [1, 2, 1000],
                    "pinned_final_source_live": True,
                },
                "transport": {
                    "ready": True,
                    "worker_connected": True,
                    "app_uid": 1000,
                    "approved_process_ids": [22, 23],
                    "final": self.final_source,
                },
                "captures": captures,
            }
        name = "transport-probe.json" if receiver else "frontend-probe.json"
        files[name] = base64.b64encode(
            b"not-json" if self.bad_report else json.dumps(report).encode()
        ).decode()
        files["selected.log"] = base64.b64encode(
            b"actual modeled observation\\nauthorization: synthetic-sensitive-marker\\n"
        ).decode()
        if not self.capture_loss:
            for capture in captures:
                files[text(capture["path"])] = base64.b64encode(
                    fixture_png(invalid_compression=self.invalid_compression)
                ).decode()
        return {"files": files}

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Apply one bounded request to independent lifecycle state."""
        assert timeout > 0
        self.requests.append(value)
        action = text(value["action"])
        if action in ("preflight", "integrity"):
            return self._prerequisites(action)
        if action == "snapshot":
            return self.snapshot()
        if action in ("allocate", "create"):
            return self._start(value)
        if action == "inspect":
            return self.inspection(value)
        if action == "collect":
            return self.evidence(value)
        return self._finish(value)

    def _prerequisites(self, action: str) -> dict[str, object]:
        """Return independently modeled host and installed runtime observations."""
        if action == "preflight":
            return {
                "wolf_id": "wolf-1",
                "root_pin": [1, 2, 3, 0],
                "runtime_local": "/run/fixture-sockets",
                "runtime_host": "/var/run/wolf",
                "device_rules": ["c 13:* rwm", "c 240:* rwm"],
            }
        return {
            "hashes": {"/opt/gow-full-x86/runtime.py": "d" * 64},
            "credentials": [
                {
                    "pid": 22,
                    "Uid": "1000 1000 1000 1000",
                    "Gid": "1000 1000 1000 1000",
                    "Groups": "1000",
                    "CapInh": "0000000000000000",
                    "CapPrm": "0000000000000000",
                    "CapEff": "0000000000000000",
                    "CapAmb": "0000000000000000",
                    "NoNewPrivs": "1",
                }
            ],
            "supervisor_pid": 1,
            "effective_seccomp": 2,
            "uinput": [10, 223],
            "approved_process_ids": [22],
            "uinput_actors": [
                {
                    "pid": 22,
                    "parent_pid": 1,
                    "start_time_ticks": 2200,
                    "application_root_pid": 22,
                    "read_write": True,
                }
            ],
            "userdata": {"link": "/home/retro/userdata", "identity": [1, 2, 1000]},
        }

    def _start(self, value: dict[str, object]) -> dict[str, object]:
        """Allocate a fresh owner or model a create response lost after effects."""
        action = text(value["action"])
        self.effects.append(action)
        self.active = value
        if action == "allocate":
            self.leased = False
            return {"pin": {"home": [1, 2, 3, 1000]}}
        self.lobby = True
        self.container = not self.late_start
        self.running = self.container
        if self.lost_create:
            msg = "Lost create response"
            raise NativeError(msg)
        return {"lobby_id": "lobby-1"}

    def _finish(self, value: dict[str, object]) -> dict[str, object]:
        """Model permission and cleanup effects without weakening absence checks."""
        action = text(value["action"])
        response: dict[str, object] = {"confirmed": True}
        if action == "lease":
            self.effects.append("input")
            self.leased = True
        elif action == "revoke":
            self.effects.append("release")
        elif action == "stop_lobby":
            self.effects.append(action)
            if self.fail_stop:
                msg = "Lobby stop failed"
                raise NativeError(msg)
            self.lobby = False
        elif action == "stop_container":
            self.effects.append(action)
            self.running = False
            # Stock Wolf normally removes the lobby when its runner exits.
            self.lobby = False
        elif action == "remove_container":
            assert not self.running
            self.effects.append(action)
            self.container = False
        elif action == "remove_state":
            assert not self.container
            assert not self.lobby
            assert value["startup_resolved"] is True
            self.effects.append(action)
            self.cleaned.append(text(value["case_id"]))
            self.active = None
            response = {"removed": True}
        else:
            raise AssertionError("Unexpected operation " + action)
        return response


def config(tier: str = "frontend-receivers") -> NativeConfig:
    """Keep finite tiny fake-clock budgets independent of native timing claims."""
    return NativeConfig(
        "sha256:" + "a" * 64,
        "worktree-sha256:" + "b" * 64,
        "c" * 64,
        ContentRoots("/library", "/library/bios"),
        {
            "/opt/gow-full-x86/runtime.py": "d" * 64,
            **(
                {
                    "/opt/gow-full-x86/suite-gamepad.json": "3" * 64,
                    "/opt/gow-full-x86/suite-es-input.cfg": "4" * 64,
                    "/usr/bin/retroarch": "5" * 64,
                    "/usr/bin/udevadm": "8" * 64,
                    "/usr/lib/libSDL2-2.0.so.0.3200.8": "9" * 64,
                    "/lib/libudev.so.1.6.3": "a" * 64,
                    "/usr/lib/libretro/fceumm_libretro.so": "6" * 64,
                    "/usr/share/libretro/info/fceumm_libretro.info": "7" * 64,
                    "/usr/lib/python3.12/site-packages/configgen/emulatorlauncher.py": (
                        # pragma: allowlist nextline secret
                        "73313380a3d40a44580c2e046eadf1f2b8c315cf475a0d56dd0a916e0b0a6a1f"
                    ),
                }
                if tier == "nes-smoke"
                else {}
            ),
        },
        "/dev/dri/renderD128",
        "video/x-raw",
        tier=tier,
        project_root=Path.cwd(),
        catalog=load_catalog(),
        budgets=Budgets(
            call=2,
            create=3,
            startup=4,
            scenario=4,
            evidence=3,
            cleanup=4,
            poll=0.5,
            lease=1,
        ),
    )


def execute(
    tmp_path: Path,
    world: World,
    *,
    tier: str = "frontend-receivers",
    native_config: NativeConfig | None = None,
) -> tuple[Coordinator, dict[str, object]]:
    """Exercise the public coordinator and real artifact publication together."""
    run_id = "1" * 32
    artifacts = Artifacts(tmp_path / "output", run_id)
    coordinator = Coordinator(
        native_config or config(tier), world, world.clock, artifacts, run_id
    )
    try:
        return coordinator, coordinator.run()
    finally:
        artifacts.close()


class DeliveredStartupWorld(World):
    """Observe a failed second case through the delivered helper and real state."""

    def __init__(
        self, root: Path, monkeypatch: pytest.MonkeyPatch, finding: str
    ) -> None:
        """Stage local SSH and Docker adapters for bounded startup observations."""
        super().__init__(FakeClock())
        self.root, self.finding = root, finding
        self.model = root / "startup-docker.json"
        ssh = root / "ssh"
        ssh.write_text(
            "#!" + sys.executable + "\n"
            "import os, shlex, sys\n"
            "payload = shlex.split(sys.argv[-1])[-1]\n"
            "os.execv(sys.executable, [sys.executable, '-I', '-B', '-c', payload])\n",
            encoding="utf-8",
        )
        docker = root / "docker"
        # This stdlib-only Docker transcript may be killed at the output bound.
        # The delivered application payload above must still load site hooks.
        docker.write_text(
            "#!"
            + sys.executable
            + " -S\n"
            + r"""
import json
import os
import pathlib
import sys

model = json.loads(pathlib.Path(os.environ["STARTUP_DOCKER_STATE"]).read_text())
action, *args = sys.argv[1:]
expected = model["container"]["Id"]
finding = model["finding"]
secret = "synthetic-private-startup-marker"  # pragma: allowlist secret
if action == "ps":
    if args != ["-aq", "--no-trunc", "--filter", "id=" + expected]:
        raise SystemExit(2)
    if finding == "unknown-container":
        print(secret)
        raise SystemExit(1)
    if finding != "absent":
        print(expected)
elif action == "inspect":
    if args != [expected]:
        raise SystemExit(2)
    print(json.dumps([model["container"]]))
elif action == "top":
    if args != [expected, "-eo", "pid,ppid,uid,args"]:
        raise SystemExit(2)
    print("PID PPID UID COMMAND")
    print("4100 4000 0 python3 /opt/gow-full-x86/input_transport.py -- " + secret)
    print("4107 4100 1000 python3 /opt/gow-full-x86/input_worker.py " + secret)
    print("4108 4100 1000 python3 /opt/gow-full-x86/runtime.py session " + secret)
    print("4150 4108 1000 /nix/store/fixture/bin/Xwayland :0 " + secret)
    print("4160 4108 1000 /private/" + secret)
elif action == "logs":
    if args != ["--tail", "64", expected]:
        raise SystemExit(2)
    if finding == "oversize":
        try:
            sys.stdout.write(secret + "x" * 100000)
            sys.stdout.write(
                "\ngow-full-x86: Wolf session Pulse server, "
                "sink and source are required\n"
            )
        except BrokenPipeError:
            pass
    elif finding == "many-lines":
        print(("RuntimeError: " + secret + "\n") * 64, end="")
        print("gow-full-x86: Wolf session Pulse server, sink and source are required")
    else:
        print("RuntimeError: " + secret)
        if finding == "audio":
            print(
                "gow-full-x86: Wolf session Pulse server, "
                "sink and source are required"
            )
        elif finding == "lookalike":
            print(
                "gow-full-x86: Wolf session Pulse server, "
                "sink and source are required " + secret
            )
else:
    raise SystemExit(2)
""",
            encoding="utf-8",
        )
        for executable in (ssh, docker):
            executable.chmod(0o700)
        monkeypatch.setenv("PATH", str(root) + os.pathsep + os.environ.get("PATH", ""))
        monkeypatch.setenv("STARTUP_DOCKER_STATE", str(self.model))
        helper = files("batocera_gow.host").joinpath("native_remote.py")
        self.transport = SSHTransport(
            SSHConfig("fixture-only"), helper.read_text(encoding="utf-8")
        )

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Keep native outcomes injected; collect actual selected startup evidence."""
        action = value["action"]
        receiver = str(value.get("case_id", "")).endswith("-receivers")
        if action == "collect" and receiver:
            return self.transport.request(value, timeout)
        result = super().request(value, timeout)
        if action == "allocate":
            state = OwnedState(
                self.root,
                text(value["case_id"]),
                text(value["token"]),
                os.getuid() or 1000,
                os.getgid() or 1000,
            )
            return {"pin": state.allocate()}
        if action == "create" and receiver:
            self.model.write_text(
                json.dumps(
                    {
                        "finding": self.finding,
                        "container": {
                            "Id": "e" * 64,
                            "Image": "sha256:" + "a" * 64,
                            "Config": {
                                "Labels": {"io.gow.integration.owner": value["token"]}
                            },
                            "Mounts": [
                                {
                                    "Source": str(
                                        self.root / "test-runs" / text(value["case_id"])
                                    ),
                                    "Destination": "/home/retro",
                                }
                            ],
                            "State": {
                                "Running": True,
                                "Paused": False,
                                "Restarting": False,
                                "Dead": False,
                                "OOMKilled": False,
                                "ExitCode": 0,
                                "Pid": 4100,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
        elif action == "remove_state":
            OwnedState(
                self.root,
                text(value["case_id"]),
                text(value["token"]),
                os.getuid() or 1000,
                os.getgid() or 1000,
            ).remove(record(value["pin"]))
        return result


@pytest.mark.parametrize(
    "finding",
    [
        "audio",
        "unknown",
        "lookalike",
        "absent",
        "unknown-container",
        "oversize",
        "many-lines",
    ],
)
def test_missing_second_case_startup_retains_only_owned_bounded_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, finding: str
) -> None:
    """Frontend success cannot hide a receiver startup failure or invent its cause."""
    world = DeliveredStartupWorld(tmp_path, monkeypatch, finding)
    native_config = dataclasses.replace(config(), host_root=str(tmp_path))
    _, report = execute(tmp_path, world, native_config=native_config)
    rows = [record(row) for row in sequence(report["cases"])]
    assert report["status"] == "failed"
    assert report["full_frontend_receiver_gate"] is False
    assert rows[0]["status"] == "passed"
    assert rows[1]["status"] in ("failed", "interrupted")
    observations = [record(row) for row in sequence(rows[1]["startup_observations"])]
    assert observations
    observation = record(observations[0]["observation"])
    if finding in ("absent", "unknown-container"):
        assert observation["container"] == (
            "absent" if finding == "absent" else "unknown"
        )
        assert "state" not in observation
    else:
        assert observation["container"] == "present"
        assert record(observation["state"])["pid"] == 4100
        process_evidence = record(observation["processes"])
        assert process_evidence["status"] == "complete"
        assert {
            record(process)["role"] for process in sequence(process_evidence["roles"])
        } == {"supervisor", "input-worker", "runtime-session", "xwayland"}
        logs = record(observation["logs"])
        assert logs["status"] == (
            "truncated" if finding in ("oversize", "many-lines") else "complete"
        )
        assert logs["failure_codes"] == (
            ["runtime-audio-contract"] if finding == "audio" else []
        )
    if finding == "audio":
        assert rows[1]["status"] == "failed"
        assert "Native startup failed: runtime-audio-contract" in sequence(
            rows[1]["errors"]
        )
    checks = [record(row) for row in sequence(report["receiver_checks"])]
    assert len(checks) == 5
    assert all(row["status"] == "not-run" for row in checks)
    assert all(record(row["cleanup"])["state_removed"] is True for row in rows)
    assert world.effects.count("create") == 2
    assert world.effects.count("input") == 1
    creates = [
        index for index, effect in enumerate(world.effects) if effect == "create"
    ]
    assert world.effects.index("remove_state") < creates[1]
    assert not (tmp_path / "test-runs" / ("1" * 32 + "-receivers")).exists()
    output = tmp_path / "output" / ("1" * 32)
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert saved["cases"][1]["startup_observations"] == rows[1]["startup_observations"]
    assert all(
        b"synthetic-private-startup-marker" not in path.read_bytes()
        for path in output.iterdir()
    )


def test_missing_final_report_keeps_runtime_observations_after_valid_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A startup marker cannot suppress owned failure attribution or invent a pass."""

    class StartedWorld(DeliveredStartupWorld):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            result = super().request(value, timeout)
            if value["action"] == "allocate" and text(value["case_id"]).endswith(
                "-receivers"
            ):
                diagnostics.publish_json(
                    self.root
                    / "test-runs"
                    / text(value["case_id"])
                    / ".native-evidence/startup.json",
                    {"uid": 1000, "gid": 1000},
                )
            return result

    world = StartedWorld(tmp_path, monkeypatch, "unknown")
    native_config = dataclasses.replace(config(), host_root=str(tmp_path))
    coordinator, report = execute(tmp_path, world, native_config=native_config)
    rows = [record(row) for row in sequence(report["cases"])]
    assert rows[0]["status"] == "passed"
    assert rows[1]["status"] in ("failed", "interrupted")
    assert rows[1]["errors"]
    assert report["status"] == "failed"
    assert report["full_frontend_receiver_gate"] is False
    assert rows[1]["report"] is None
    observations = [record(row) for row in sequence(rows[1]["startup_observations"])]
    assert observations
    assert all(row["phase"] == "receivers:cleanup" for row in observations)
    observation = record(observations[0]["observation"])
    assert observation["container"] == "present"
    assert record(observation["state"])["pid"] == 4100
    assert record(observation["logs"]) == {
        "status": "complete",
        "failure_codes": [],
    }
    processes = record(observation["processes"])
    assert processes["status"] == "complete"
    assert {record(process)["role"] for process in sequence(processes["roles"])} == {
        "supervisor",
        "input-worker",
        "runtime-session",
        "xwayland",
    }
    # With no final report, ordinary scenario expiry can classify as interrupted.
    # Require the full scenario budget, not an earlier discovery or lease failure.
    scenario = [
        call for call in coordinator.timings if call["phase"] == "receivers:scenario"
    ]
    assert {call["operation"] for call in scenario} == {"snapshot", "collect", "lease"}
    assert all(call["elapsed"] == 0 for call in scenario)
    assert scenario[-1]["operation"] == "lease"
    assert observations[0]["observed"] == (
        number(scenario[0]["started"]) + native_config.budgets.scenario
    )
    assert world.effects.count("input") > 1
    assert all(
        record(check)["status"] == "not-run"
        for check in sequence(report["receiver_checks"])
    )
    for row in rows:
        cleanup = record(row["cleanup"])
        assert cleanup["status"] == "passed"
        assert cleanup["lobby_absent"] is True
        assert cleanup["container_absent"] is True
        assert cleanup["state_removed"] is True
    assert not world.container
    assert not world.lobby
    assert not (tmp_path / "test-runs" / ("1" * 32 + "-receivers")).exists()
    output = tmp_path / "output" / ("1" * 32)
    assert json.loads((output / "receivers-startup.json").read_bytes()) == {
        "uid": 1000,
        "gid": 1000,
    }
    assert not (output / "receivers-transport-probe.json").exists()
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert saved["cases"][1]["report"] is None
    assert saved["cases"][1]["startup_observations"] == observations
    assert all(
        b"synthetic-private-startup-marker" not in path.read_bytes()
        for path in output.iterdir()
    )


@pytest.mark.parametrize("field", ["container", "state", "logs", "processes", "extra"])
def test_unrecognized_startup_fields_cannot_leak_or_open_second_case_input(
    tmp_path: Path, field: str
) -> None:
    """Only the fixed startup schema may enter persisted cross-case evidence."""
    # pragma: allowlist nextline secret
    secret = "synthetic-private-startup-marker"  # noqa: S105  # Privacy-test marker.
    observation: dict[str, object] = {
        "container": "present",
        "state": {
            "running": True,
            "paused": False,
            "restarting": False,
            "dead": False,
            "oom_killed": False,
            "exit_code": 0,
            "pid": 4100,
        },
        "logs": {"status": "complete", "failure_codes": []},
        "processes": {"status": "complete", "roles": []},
    }
    if field == "container":
        observation[field] = secret
    elif field == "state":
        observation[field] = {**record(observation[field]), "error": secret}
    elif field == "logs":
        observation[field] = {"status": "complete", "failure_codes": [secret]}
    elif field == "processes":
        observation[field] = {
            "status": "complete",
            "roles": [{"role": secret, "pid": 4108, "parent_pid": 4100, "uid": 1000}],
        }
    else:
        observation[field] = secret

    class UnrecognizedStartupWorld(World):
        def evidence(self, request: dict[str, object]) -> dict[str, object]:
            response = super().evidence(request)
            if text(request["case_id"]).endswith("-receivers"):
                response["startup_observation"] = observation
            return response

    world = UnrecognizedStartupWorld(FakeClock())
    _, report = execute(tmp_path, world)
    rows = [record(row) for row in sequence(report["cases"])]
    assert rows[0]["status"] == "passed"
    assert rows[1]["status"] == "failed"
    assert rows[1]["startup_observations"] == []
    assert report["status"] == "failed"
    assert world.effects.count("input") == 1
    assert all(record(row["cleanup"])["state_removed"] is True for row in rows)
    output = tmp_path / "output" / ("1" * 32)
    assert all(secret.encode() not in path.read_bytes() for path in output.iterdir())


class DeliveredCleanupWorld(World):
    """Run discovery/cleanup through the real helper and local Docker transport."""

    def __init__(
        self,
        root: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        race: str,
        fault: str = "",
    ) -> None:
        """Stage real owned-state cleanup with controlled local Docker races."""
        super().__init__(FakeClock())
        self.root = root
        self.model = root / "docker-state.json"
        self.race = race
        self.fault = fault
        self.teardown = False
        ssh = root / "ssh"
        ssh.write_text(
            "#!" + sys.executable + "\n"
            "import os, shlex, sys\n"
            "payload = shlex.split(sys.argv[-1])[-1]\n"
            "os.execv(sys.executable, [sys.executable, '-I', '-B', '-c', payload])\n",
            encoding="utf-8",
        )
        docker = root / "docker"
        docker.write_text(
            "#!"
            + sys.executable
            + "\n"
            + r"""
import json
import os
import pathlib
import sys

path = pathlib.Path(os.environ["CLEANUP_DOCKER_STATE"])
model = json.loads(path.read_text())
containers = model["containers"]
expected = "e" * 64
action, *args = sys.argv[1:]
output, error, status = "", "", 0
if action == "ps":
    filters = [value[3:] for value in args if value.startswith("id=")]
    if model["unknown"]:
        status = 1
    elif filters:
        if filters != [expected]:
            status = 1
        elif model["absence_ready"] and model["fault"].startswith("query-"):
            model["unknown"] = True
            fault = model["fault"]
            if fault == "query-failed":
                status = 1
            elif fault == "query-prefix":
                output = expected[:12] + "\n"
            elif fault == "query-foreign":
                output = "f" * 64 + "\n"
            elif fault == "query-duplicate":
                output = (expected + "\n") * 2
            else:
                output = "malformed observation\n"
        else:
            if model["race"] == "before-query":
                containers.pop(expected, None)
            output = expected + "\n" if expected in containers else ""
    else:
        output = "".join(identifier + "\n" for identifier in containers)
elif action == "inspect":
    if model["race"] == "snapshot" and model["scenario"] and not model["absence_ready"]:
        fault = model["fault"]
        missing = "f" * 64 if fault == "foreign-missing" else expected
        removed = containers[missing]
        if fault != "still-present":
            containers.pop(missing)
        model["absence_ready"] = True
        rows = [containers[identifier] for identifier in args if identifier != missing]
        if fault == "duplicate-row":
            rows.append(rows[0])
        elif fault == "missing-row":
            rows = []
        elif fault == "extra-row":
            rows.append({**removed, "Id": "d" * 64})
        elif fault == "owned-row":
            rows.append(removed)
        elif fault == "incomplete-state":
            rows[0]["State"] = {}
        elif fault == "paused-foreign":
            rows[0]["State"]["Paused"] = True
        elif fault == "running-foreign":
            rows[0]["State"]["Running"] = True
        output = json.dumps(rows)
        if fault == "malformed-json":
            output = "["
        elif fault == "nonlist-json":
            output = "{}"
        elif fault == "empty-json":
            output = ""
        error = "Error: No such object: " + missing + "\n"
        status = 1
        if fault == "unknown-missing":
            error = "Error: No such object: " + "d" * 64 + "\n"
        elif fault == "prefix-missing":
            error = "Error: No such object: " + expected[:12] + "\n"
        elif fault == "extra-error":
            error += "private daemon failure must not escape\n"
        elif fault == "duplicate-error":
            error *= 2
        elif fault == "unrelated-error":
            error = "private daemon failure must not escape\n"
        elif fault == "exit-two":
            status = 2
        elif fault == "success-missing-row":
            status, output, error = 0, "[]", ""
    elif model["race"] == "inspect" and args == [expected]:
        containers.pop(expected, None)
        model["absence_ready"] = True
        status = 1
    elif model["fault"] == "global-inspect":
        containers.pop("f" * 64, None)
        status = 1
    elif model["fault"] == "malformed-inspect" and args == [expected]:
        output = "{}"
    elif model["fault"] == "inspect-failed" and args == [expected]:
        status = 1
    elif model["fault"].startswith("changed-") and args == [expected]:
        observed = json.loads(json.dumps(containers[expected]))
        if model["fault"] == "changed-owner":
            observed["Config"]["Labels"]["io.gow.integration.owner"] = "foreign"
        elif model["fault"] == "changed-image":
            observed["Image"] = "sha256:" + "f" * 64
        else:
            observed["Mounts"][0]["Source"] = "/foreign/home"
        output = json.dumps([observed])
    elif any(identifier not in containers for identifier in args):
        status = 1
    else:
        output = json.dumps([containers[identifier] for identifier in args])
elif action in ("stop", "rm"):
    identifier = args[-1]
    model["effects"].append({"operation": action, "id": identifier})
    if identifier != expected or identifier not in containers:
        status = 1
    elif model["race"] == action:
        containers.pop(identifier)
        model["absence_ready"] = True
        status = 1
    elif model["fault"] == action + "-failed":
        model["absence_ready"] = True
        status = 1
    elif action == "stop":
        containers[identifier]["State"]["Running"] = False
    else:
        containers.pop(identifier)
else:
    status = 2
path.write_text(json.dumps(model))
sys.stdout.write(output)
sys.stderr.write(error)
raise SystemExit(status)
""",
            encoding="utf-8",
        )
        curl = root / "curl"
        curl.write_text(
            "#!" + sys.executable + "\n"
            "import json, sys\n"
            "endpoint = sys.argv[-1].rsplit('/', 1)[-1]\n"
            "if endpoint not in ('sessions', 'lobbies'):\n"
            "    raise SystemExit(2)\n"
            "print(json.dumps({'success': True, endpoint: []}))\n",
            encoding="utf-8",
        )
        for executable in (ssh, docker, curl):
            executable.chmod(0o700)
        monkeypatch.setenv("PATH", str(root) + os.pathsep + os.environ.get("PATH", ""))
        monkeypatch.setenv("CLEANUP_DOCKER_STATE", str(self.model))
        helper = files("batocera_gow.host").joinpath("native_remote.py")
        self.transport = SSHTransport(
            SSHConfig("fixture-only"), helper.read_text(encoding="utf-8")
        )

    def saved_model(self) -> dict[str, object]:
        """Read externally visible resource state, not command-string assertions."""
        return record(json.loads(self.model.read_text(encoding="utf-8")))

    def delivered(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Execute the unchanged isolated payload against only owned local files."""
        request = {
            **value,
            "uid": os.getuid() or 1000,
            "gid": os.getgid() or 1000,
            "root_pin": identity(self.root.stat()),
        }
        return self.transport.request(request, timeout)

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Deliver real discovery and cleanup around modeled probe observations."""
        action = value["action"]
        if action == "allocate":
            super().request(value, timeout)
            return self.delivered(value, timeout)
        if action == "snapshot" and (
            self.teardown or (self.race == "snapshot" and self.model.exists())
        ):
            return self.delivered(value, timeout)
        if action in ("stop_container", "remove_container", "remove_state"):
            self.effects.append(text(action))
            result = self.delivered(value, timeout)
            if action == "remove_state":
                self.cleaned.append(text(value["case_id"]))
                self.active = None
            return result
        result = super().request(value, timeout)
        if action == "create":
            model = {
                "race": self.race,
                "fault": self.fault,
                "unknown": False,
                "absence_ready": False,
                "scenario": False,
                "effects": [],
                "containers": {
                    "e" * 64: {
                        "Id": "e" * 64,
                        "Name": "/owned-native",
                        "Image": value["image"],
                        "Config": {
                            "Labels": {"io.gow.integration.owner": value["token"]}
                        },
                        "Mounts": [
                            {
                                "Destination": "/home/retro",
                                "Source": str(
                                    self.root / "test-runs" / text(value["case_id"])
                                ),
                            }
                        ],
                        "State": {"Running": True, "Paused": False},
                    },
                    "f" * 64: {
                        "Id": "f" * 64,
                        "Name": "/unrelated-stopped",
                        "Image": "sha256:" + "f" * 64,
                        "Config": {"Labels": {}},
                        "Mounts": [],
                        "State": {"Running": False, "Paused": False},
                    },
                },
            }
            self.model.write_text(json.dumps(model), encoding="utf-8")
        elif action == "lease" and self.race == "snapshot":
            model = self.saved_model()
            model["scenario"] = True
            self.model.write_text(json.dumps(model), encoding="utf-8")
        elif action == "stop_lobby":
            self.teardown = True
        return result


def test_bound_owned_disappearance_during_snapshot_preserves_normal_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete partial inspect plus exact owned absence is not discovery loss."""
    world = DeliveredCleanupWorld(tmp_path, monkeypatch, race="snapshot")
    coordinator, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(
            config("frontend-smoke"), host_root=str(tmp_path)
        ),
    )
    assert report["status"] == "passed"
    assert coordinator.interrupted is None
    row = record(sequence(report["cases"])[0])
    assert row["status"] == "passed"
    assert record(row["cleanup"])["known_container_id"] == "e" * 64
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects.count("input") == 1
    assert not (tmp_path / "test-runs" / ("1" * 32 + "-frontend")).exists()
    model = world.saved_model()
    assert model["absence_ready"] is True
    assert set(record(model["containers"])) == {"f" * 64}
    assert record(record(model["containers"])["f" * 64])["Name"] == "/unrelated-stopped"
    assert model["effects"] == []


@pytest.mark.parametrize(
    "fault",
    [
        "foreign-missing",
        "unknown-missing",
        "prefix-missing",
        "extra-error",
        "duplicate-error",
        "unrelated-error",
        "exit-two",
        "duplicate-row",
        "missing-row",
        "extra-row",
        "owned-row",
        "malformed-json",
        "nonlist-json",
        "empty-json",
        "success-missing-row",
        "incomplete-state",
        "paused-foreign",
        "running-foreign",
        "still-present",
        "query-failed",
        "query-malformed",
        "query-prefix",
        "query-foreign",
        "query-duplicate",
    ],
)
def test_snapshot_disappearance_never_hides_unknown_or_incomplete_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Partial/error/foreign observations interrupt before a later input or case."""
    world = DeliveredCleanupWorld(tmp_path, monkeypatch, race="snapshot", fault=fault)
    coordinator, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(config(), host_root=str(tmp_path)),
    )
    assert report["status"] == "failed"
    assert coordinator.interrupted is not None
    rows = [record(row) for row in sequence(report["cases"])]
    assert rows[0]["status"] == "interrupted"
    assert rows[1]["status"] == "not-run"
    assert world.effects.count("input") == 1
    assert world.effects.count("create") == 1
    if fault != "foreign-missing":
        assert "f" * 64 in record(world.saved_model()["containers"])
    output = tmp_path / "output" / ("1" * 32)
    assert all(
        b"private daemon failure" not in path.read_bytes() for path in output.iterdir()
    )


@pytest.mark.parametrize(
    "binding", ["no-case", "unobserved", "owner", "image", "home", "marker", "pin"]
)
def test_snapshot_reconciliation_requires_independently_bound_owned_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, binding: str
) -> None:
    """Neither preflight nor an unbound/changed capability can classify absence."""
    world = DeliveredCleanupWorld(tmp_path, monkeypatch, race="snapshot")
    native_config = dataclasses.replace(
        config("frontend-smoke"), host_root=str(tmp_path)
    )
    with closing(Artifacts(tmp_path / "output", "1" * 32)) as artifacts:
        coordinator = Coordinator(
            native_config, world, world.clock, artifacts, "1" * 32
        )
        case = coordinator.make_case("frontend")
        deadline = world.clock.now() + 2
        case.pin = record(coordinator.call("allocate", deadline, case)["pin"])
        case.create_dispatched = True
        coordinator.call("create", deadline, case, payload=case.payload)
        model = world.saved_model()
        if binding in ("owner", "image", "home"):
            if binding == "owner":
                change: tuple[str, ...] = (
                    "Config",
                    "Labels",
                    "io.gow.integration.owner",
                )
                value = "foreign"
            elif binding == "image":
                change, value = ("Image",), "sha256:" + "f" * 64
            else:
                change, value = ("Mounts",), "foreign"
            alter_observations(
                model,
                {
                    ("containers", "e" * 64, *change): [
                        {"Destination": "/home/retro", "Source": "/foreign/home"}
                    ]
                    if binding == "home"
                    else value
                },
            )
            world.model.write_text(json.dumps(model), encoding="utf-8")
            with pytest.raises((NativeError, InterruptedError)):
                coordinator.discover(deadline, case)
            assert case.container_id is None
        elif binding != "unobserved":
            coordinator.discover(deadline, case)
            assert case.container_id == "e" * 64
            assert case.startup_resolved is True
        if binding == "marker":
            (tmp_path / "test-runs" / case.case_id / ".native-owner").write_text(
                "foreign", encoding="utf-8"
            )
        elif binding == "pin":
            case.pin["home"] = [0, 0, 0, 1000]
        model["scenario"] = True
        world.model.write_text(json.dumps(model), encoding="utf-8")
        with pytest.raises((NativeError, InterruptedError)):
            coordinator.discover(deadline, None if binding == "no-case" else case)
        assert "input" not in world.effects
        assert "f" * 64 in record(world.saved_model()["containers"])
        assert (tmp_path / "test-runs" / case.case_id).is_dir()


@pytest.mark.parametrize(
    ("race", "operation"),
    [
        ("before-query", "stop_container"),
        ("inspect", "stop_container"),
        ("stop", "stop_container"),
        ("rm", "remove_container"),
    ],
)
def test_automatic_owned_removal_is_confirmed_without_false_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str, operation: str
) -> None:
    """Wolf removal may win before inspect, during stop or during explicit removal."""
    world = DeliveredCleanupWorld(tmp_path, monkeypatch, race=race)
    _, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(
            config("frontend-smoke"), host_root=str(tmp_path)
        ),
    )
    assert report["status"] == "passed"
    row = record(sequence(report["cases"])[0])
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "passed"
    assert cleanup["container_absent"] is True
    assert cleanup["lobby_absent"] is True
    assert cleanup["state_removed"] is True
    attempt = next(
        record(value)
        for value in sequence(cleanup["attempts"])
        if record(value)["operation"] == operation
    )
    assert attempt["already_absent"] is True
    assert not (tmp_path / "test-runs" / ("1" * 32 + "-frontend")).exists()
    model = world.saved_model()
    assert set(record(model["containers"])) == {"f" * 64}
    assert all(
        record(effect)["id"] == "e" * 64 for effect in sequence(model["effects"])
    )
    assert world.effects.count("create") == 1


@pytest.mark.parametrize(
    ("race", "fault"),
    [
        ("none", "stop-failed"),
        ("none", "rm-failed"),
        ("none", "malformed-inspect"),
        ("none", "inspect-failed"),
        ("none", "changed-owner"),
        ("none", "changed-image"),
        ("none", "changed-home"),
        ("stop", "query-failed"),
        ("stop", "query-malformed"),
        ("stop", "query-prefix"),
        ("stop", "query-foreign"),
        ("stop", "query-duplicate"),
        ("none", "global-inspect"),
    ],
)
def test_failed_or_unknown_owned_absence_retains_state_and_stops_later_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str, fault: str
) -> None:
    """Errors, partial IDs and incomplete global discovery never authorize deletion."""
    world = DeliveredCleanupWorld(tmp_path, monkeypatch, race=race, fault=fault)
    _, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(config(), host_root=str(tmp_path)),
    )
    assert report["status"] == "failed"
    rows = [record(value) for value in sequence(report["cases"])]
    cleanup = record(rows[0]["cleanup"])
    assert cleanup["status"] == "incomplete"
    assert cleanup["state_removed"] is False
    assert rows[1]["status"] == "not-run"
    assert world.effects.count("create") == 1
    assert "remove_state" not in world.effects
    assert (tmp_path / "test-runs" / ("1" * 32 + "-frontend")).is_dir()
    assert not any(
        record(attempt).get("already_absent") is True
        for attempt in sequence(cleanup["attempts"])
    )
    model = world.saved_model()
    if fault != "global-inspect":
        assert "f" * 64 in record(model["containers"])
    assert all(
        record(effect)["id"] == "e" * 64 for effect in sequence(model["effects"])
    )
    saved = json.loads(
        (tmp_path / "output" / ("1" * 32) / "report.json").read_text(encoding="utf-8")
    )
    assert saved["cases"][0]["cleanup"] == cleanup


class RuntimeFiles:
    """Real proc/package files with controlled kernel metadata and live handles."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Create proc-style files with controlled device and pidfd observations."""
        self.root = root
        self.status: dict[str, object] = {
            "pid": 1,
            "app_uid": 1000,
            "approved_process_ids": [22, 23],
        }
        self.dead: set[int] = set()
        self.writers: list[int] = []
        (root / "opt/gow-full-x86").mkdir(parents=True)
        (root / "home/retro/userdata").mkdir(parents=True)
        (root / "userdata").symlink_to("/home/retro/userdata")
        (root / "run").mkdir()
        (root / "proc/self").mkdir(parents=True)
        (root / "proc/self/status").write_text("Seccomp:\t2\n", encoding="utf-8")
        source = b"packaged runtime fixture\n"
        (root / "opt/gow-full-x86/runtime.py").write_bytes(source)
        self.hashes: dict[str, object] = {
            "/opt/gow-full-x86/runtime.py": hashlib.sha256(source).hexdigest()
        }
        self.process(7, 1, [1000], "/opt/gow-full-x86/input_worker.py")
        self.process(
            22,
            1,
            [0, 1000],
            "/opt/gow-full-x86/runtime.py",
            action="session",
        )
        self.process(23, 22, [0, 1000], "/opt/gow-full-x86/transport_probe.py")
        self.publish()

        class ObservedPath(PosixPath):
            """Supply device/owner observations unavailable to unprivileged hosts."""

            def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
                if self == root / "dev/uinput":
                    return os.stat_result(
                        (stat.S_IFCHR | 0o660, 5, 1, 1, 0, 0, 0, 0, 0, 0),
                        {"st_rdev": os.makedev(10, 223)},
                    )
                info = super().stat(follow_symlinks=follow_symlinks)
                return os.stat_result(
                    (
                        info.st_mode,
                        info.st_ino,
                        info.st_dev,
                        info.st_nlink,
                        0,
                        info.st_gid,
                        info.st_size,
                        info.st_atime,
                        info.st_mtime,
                        info.st_ctime,
                    )
                )

        def observed_path(name: str) -> Path:
            return ObservedPath(root / name.lstrip("/"))

        def pidfd_open(pid: int, flags: int = 0) -> int:
            del flags
            if not (root / "proc" / str(pid)).is_dir():
                raise ProcessLookupError(pid)
            reader, writer = os.pipe()
            self.writers.append(writer)
            if pid in self.dead:
                os.write(writer, b"exited")
            return reader

        monkeypatch.setattr(diagnostics, "Path", observed_path)
        monkeypatch.setattr(os, "pidfd_open", pidfd_open)
        monkeypatch.setattr(os, "getpid", lambda: 99)

    def close(self) -> None:
        """Release the owned pipe peers after inspector descriptors are closed."""
        for descriptor in self.writers:
            os.close(descriptor)

    def publish(self) -> None:
        """Publish actual root-controlled status bytes for the inspector to parse."""
        path = self.root / "run/gow-full-x86-input-transport.json"
        path.write_text(json.dumps(self.status), encoding="utf-8")

    def process(  # noqa: PLR0913 - independent proc credentials, ancestry, argv and status mutations are explicit fixture inputs.
        self,
        pid: int,
        parent: int,
        groups: list[int],
        command: str,
        *,
        action: str = "",
        fields: dict[str, str] | None = None,
    ) -> None:
        """Write proc observations without replacing inspection decisions."""
        directory = self.root / "proc" / str(pid)
        directory.mkdir(exist_ok=True)
        credentials = {
            "Uid": "1000\t1000\t1000\t1000",
            "Gid": "1000\t1000\t1000\t1000",
            "Groups": " ".join(str(group) for group in groups),
            "CapInh": "0000000000000000",
            "CapPrm": "0000000000000000",
            "CapEff": "0000000000000000",
            "CapAmb": "0000000000000000",
            "NoNewPrivs": "1",
            **(fields or {}),
        }
        (directory / "status").write_text(
            "".join(f"{key}:\t{value}\n" for key, value in credentials.items()),
            encoding="utf-8",
        )
        (directory / "cmdline").write_bytes(
            b"python3\0" + command.encode() + b"\0" + action.encode() + b"\0"
        )
        (directory / "stat").write_text(
            f"{pid} (fixture actor) S {parent} " + "0 " * 17 + f"{pid * 100}\n",
            encoding="utf-8",
        )

    def inspect(self) -> dict[str, object]:
        """Run the actual packaged inspector against the filesystem observations."""
        return record(
            diagnostics.inspect_runtime(
                {"uid": 1000, "gid": 1000, "hashes": self.hashes}
            )
        )


@pytest.fixture
def runtime_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[RuntimeFiles]:
    """Keep all observed files and kernel-handle substitutes test-owned."""
    files = RuntimeFiles(tmp_path / "inspection", monkeypatch)
    try:
        yield files
    finally:
        files.close()


def test_stock_libudev_inspection_allows_only_exact_inventory_path(
    runtime_files: RuntimeFiles,
) -> None:
    """Read actual hashed bytes without opening arbitrary /lib inspection paths."""
    library = runtime_files.root / "lib/libudev.so.1.6.3"
    library.parent.mkdir()
    library.write_bytes(b"synthetic stock libudev bytes")
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    runtime_files.hashes["/lib/libudev.so.1.6.3"] = digest
    assert record(runtime_files.inspect()["hashes"])["/lib/libudev.so.1.6.3"] == digest
    library.write_bytes(b"changed")
    with pytest.raises(DiagnosticError, match="integrity mismatch"):
        runtime_files.inspect()
    del runtime_files.hashes["/lib/libudev.so.1.6.3"]
    runtime_files.hashes["/lib/private.so"] = digest
    with pytest.raises(DiagnosticError, match="Invalid integrity inspection path"):
        runtime_files.inspect()


@pytest.mark.parametrize("separator", [" ", "\t", " \t "])
def test_proc_credential_separators_reach_the_inspected_input_gate(
    tmp_path: Path, runtime_files: RuntimeFiles, separator: str
) -> None:
    """Consume actual proc-file observations, including normal kernel tabs."""
    runtime_files.process(
        23,
        22,
        [0, 1000],
        "/opt/gow-full-x86/transport_probe.py",
        fields={
            "Uid": separator.join(["1000"] * 4),
            "Gid": separator.join(["1000"] * 4),
        },
    )

    class ProcWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "integrity":
                return runtime_files.inspect()
            return super().request(value, timeout)

    world = ProcWorld(FakeClock())
    _, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(
            config("frontend-smoke"), hashes=runtime_files.hashes
        ),
    )
    assert report["status"] == "passed"
    row = record(sequence(report["cases"])[0])
    assert row["isolation"] is not None
    assert "input" in world.effects
    assert record(row["cleanup"])["state_removed"] is True


@pytest.mark.parametrize("field", ["Uid", "Gid"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(Ellipsis, id="missing"),
        None,
        1000,
        True,
        [1000, 1000, 1000, 1000],
        "",
        "1000\t1000\t1000",
        "1000\t1000\t1000\t1000\t1000",
        "1000\t1000\t0\t1000",
        "-1000\t1000\t1000\t1000",
        "+1000\t1000\t1000\t1000",
        "1000x\t1000\t1000\t1000",
        "\uff11\uff10\uff10\uff10\t1000\t1000\t1000",
        "1000\n1000\t1000\t1000",
        "1000\t1000\t1000\t1000\n",
        "1000\r1000\t1000\t1000",
        "1000\v1000\t1000\t1000",
        "1000\f1000\t1000\t1000",
        "1000\0 1000\t1000\t1000",
        "1000\x1f1000\t1000\t1000",
        "1000\x7f1000\t1000\t1000",
        "1000\u00a01000\t1000\t1000",
    ],
)
def test_invalid_proc_credentials_deny_input_and_preserve_cleanup(
    tmp_path: Path, field: str, value: object
) -> None:
    """Only four matching ASCII decimal IDs cross the host credential boundary."""
    credential_value = value

    class InvalidCredentialsWorld(World):
        @override
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            result = super().request(value, timeout)
            if value.get("action") == "integrity":
                credential = record(sequence(result["credentials"])[0])
                if credential_value is Ellipsis:
                    credential.pop(field)
                else:
                    credential[field] = credential_value
                result["credentials"] = [credential]
            return result

    world = InvalidCredentialsWorld(FakeClock())
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["isolation"] is None
    assert row["report"] is None
    assert "input" not in world.effects
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "passed"
    assert cleanup["lobby_absent"] is True
    assert cleanup["container_absent"] is True
    assert cleanup["state_removed"] is True
    saved = json.loads(
        (tmp_path / "output" / ("1" * 32) / "report.json").read_text(encoding="utf-8")
    )
    assert saved["cases"][0]["cleanup"] == cleanup


def test_tabs_in_non_proc_literals_still_deny_the_input_gate(tmp_path: Path) -> None:
    """The proc-field exception cannot relax effective environment validation."""

    class TabbedEnvironmentWorld(World):
        def inspection(self, request: dict[str, object]) -> dict[str, object]:
            observed = super().inspection(request)
            container = record(observed["container"])
            configuration = record(container["Config"])
            configuration["Env"] = [
                *sequence(configuration["Env"]),
                "UNRELATED=not\tliteral",
            ]
            container["Config"] = configuration
            observed["container"] = container
            return observed

    world = TabbedEnvironmentWorld(FakeClock())
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["isolation"] is None
    assert "input" not in world.effects
    assert record(row["cleanup"])["status"] == "passed"
    assert record(row["cleanup"])["state_removed"] is True


def test_restricted_worker_and_approved_native_actors_open_input(
    tmp_path: Path, runtime_files: RuntimeFiles
) -> None:
    """Actor authority, not a privileged XTEST worker, qualifies native input."""

    class InspectedWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "integrity":
                return runtime_files.inspect()
            return super().request(value, timeout)

    world = InspectedWorld(FakeClock())
    _, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(
            config("frontend-smoke"), hashes=runtime_files.hashes
        ),
    )
    assert report["status"] == "passed"
    row = record(sequence(report["cases"])[0])
    integrity = record(record(row["isolation"])["packaged_integrity"])
    assert {record(v)["pid"] for v in sequence(integrity["credentials"])} == {
        7,
        22,
        23,
    }
    actors = [record(v) for v in sequence(integrity["uinput_actors"])]
    assert {v["pid"] for v in actors} == {22, 23}
    assert all(v["application_root_pid"] == 22 for v in actors)
    assert all(v["read_write"] is True for v in actors)
    assert "input" in world.effects
    assert record(row["cleanup"])["state_removed"] is True


@pytest.mark.parametrize(
    "approved",
    [
        None,
        [],
        "22",
        [True],
        [0],
        [-1],
        ["22"],
        [22, 22],
        [99999],
        [23],
        [7, 22, 23],
    ],
)
def test_invalid_approval_cannot_borrow_capable_app_uid_process(
    runtime_files: RuntimeFiles, approved: object
) -> None:
    """Capability-free processes with device groups do not establish ancestry."""
    runtime_files.status["approved_process_ids"] = approved
    runtime_files.publish()
    with pytest.raises(DiagnosticError):
        runtime_files.inspect()


def test_absent_approval_cannot_borrow_capable_app_uid_process(
    runtime_files: RuntimeFiles,
) -> None:
    """A missing ProcessTree approval field supplies no application authority."""
    del runtime_files.status["approved_process_ids"]
    runtime_files.publish()
    with pytest.raises(DiagnosticError):
        runtime_files.inspect()


def test_restricted_unapproved_process_is_not_exempted_by_name(
    runtime_files: RuntimeFiles,
) -> None:
    """Only application approval changes device requirements, never worker spelling."""
    runtime_files.process(7, 1, [1000], "/usr/bin/unrelated-support")
    result = runtime_files.inspect()
    assert {record(v)["pid"] for v in sequence(result["credentials"])} == {7, 22, 23}
    assert {record(v)["pid"] for v in sequence(result["uinput_actors"])} == {22, 23}


@pytest.mark.parametrize("parent", [1, 7, 23, 99999])
def test_approved_probe_outside_live_application_branch_is_rejected(
    runtime_files: RuntimeFiles, parent: int
) -> None:
    """Approval numbers alone cannot authorize a sibling, cycle or foreign actor."""
    runtime_files.process(23, parent, [0, 1000], "/opt/gow-full-x86/transport_probe.py")
    with pytest.raises(DiagnosticError):
        runtime_files.inspect()


def test_denied_approved_probe_cannot_borrow_root_or_unapproved_access(
    runtime_files: RuntimeFiles,
) -> None:
    """Even a capable approved runtime and extra capable sibling cannot mask denial."""
    runtime_files.process(23, 22, [1000], "/opt/gow-full-x86/transport_probe.py")
    runtime_files.process(24, 1, [0, 1000], "/opt/gow-full-x86/transport_probe.py")
    with pytest.raises(DiagnosticError, match="Native app cannot read/write uinput"):
        runtime_files.inspect()


@pytest.mark.parametrize("pid", [7, 23])
@pytest.mark.parametrize(
    "fields",
    [
        {"Uid": "1000 0 1000 1000"},
        {"Gid": "1000 0 1000 1000"},
        {"Uid": "2000 2000 2000 2000"},
        {"Gid": "2000 2000 2000 2000"},
        {"CapInh": "0000000000000001"},
        {"CapPrm": "0000000000000001"},
        {"CapEff": "0000000000000001"},
        {"CapAmb": "0000000000000001"},
        {"NoNewPrivs": "0"},
    ],
)
def test_worker_and_actor_privilege_checks_remain_mandatory(
    runtime_files: RuntimeFiles, pid: int, fields: dict[str, str]
) -> None:
    """Neither restricted support nor approved application roles waive credentials."""
    runtime_files.process(
        pid,
        1 if pid == 7 else 22,
        [1000] if pid == 7 else [0, 1000],
        "/opt/gow-full-x86/input_worker.py"
        if pid == 7
        else "/opt/gow-full-x86/transport_probe.py",
        fields=fields,
    )
    with pytest.raises(DiagnosticError):
        runtime_files.inspect()


def test_dead_approved_application_root_cannot_qualify_live_probe(
    runtime_files: RuntimeFiles,
) -> None:
    """A readable pidfd closes ancestry even when proc files and approval remain."""
    runtime_files.dead.add(22)
    with pytest.raises(DiagnosticError):
        runtime_files.inspect()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("uinput_actors", None),
        ("uinput_actors", []),
        ("approved_process_ids", None),
        ("approved_process_ids", []),
        ("approved_process_ids", [22]),
        ("approved_process_ids", [True, 22, 23]),
    ],
)
def test_host_refuses_incomplete_actual_actor_evidence_before_input(
    tmp_path: Path, runtime_files: RuntimeFiles, field: str, value: object
) -> None:
    """Lost or unapproved actor evidence cannot be replaced by credential success."""
    actor_value = value

    class IncompleteActorsWorld(World):
        @override
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "integrity":
                result = runtime_files.inspect()
                result[field] = actor_value
                return result
            return super().request(value, timeout)

    world = IncompleteActorsWorld(FakeClock())
    _, report = execute(
        tmp_path,
        world,
        native_config=dataclasses.replace(
            config("frontend-smoke"), hashes=runtime_files.hashes
        ),
    )
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["isolation"] is None
    assert "input" not in world.effects
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "passed"
    assert cleanup["lobby_absent"] is True
    assert cleanup["container_absent"] is True
    assert cleanup["state_removed"] is True
    saved = json.loads(
        (tmp_path / "output" / ("1" * 32) / "report.json").read_text(encoding="utf-8")
    )
    assert saved["cases"][0]["cleanup"] == cleanup


def test_normal_frontend_then_five_receiver_checks_wait_for_cleanup(
    tmp_path: Path,
) -> None:
    """A next case needs real observed absence, not just stop success."""
    world = World(FakeClock())
    _, report = execute(tmp_path, world)
    assert report["status"] == "passed"
    assert world.effects.count("create") == 2
    assert world.effects.index("input") > world.effects.index("create")
    first_removed = world.effects.index("remove_state")
    second_create = world.effects.index("create", world.effects.index("create") + 1)
    assert first_removed < second_create
    rows = [record(v) for v in sequence(report["cases"])]
    receiver = record(rows[1]["report"])
    assert [record(r)["name"] for r in sequence(receiver["cases"])] == list(
        RECEIVER_CASES
    )
    output = tmp_path / "output" / ("1" * 32)
    assert len(list(output.glob("*.png"))) == 6
    assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
    for row in rows:
        for name, digest in record(row["captures"]).items():
            assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(
    "path",
    [
        "/dev/nvidia0",
        "/dev/nvidia12",
        "/dev/nvidiactl",
        "/dev/nvidia-modeset",
        "/dev/nvidia-uvm",
        "/dev/nvidia-uvm-tools",
        "/dev/nvidia-caps/nvidia-cap1",
        "/dev/dri/card0",
        "/dev/dri/renderD128",
    ],
)
def test_effective_native_gpu_devices_allow_inspected_input_gate(
    tmp_path: Path, path: str
) -> None:
    """Wolf GPU paths pass actual isolation consumption before the first lease."""
    world = World(FakeClock())
    world.devices.append(
        {"PathOnHost": path, "PathInContainer": path, "CgroupPermissions": "rwm"}
    )
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "passed"
    row = record(sequence(report["cases"])[0])
    assert row["isolation"] is not None
    actions = [request["action"] for request in world.requests]
    assert (
        actions.index("inspect") < actions.index("integrity") < actions.index("lease")
    )
    assert "input" in world.effects
    assert record(row["cleanup"])["state_removed"] is True


@pytest.mark.parametrize(
    ("host_path", "container_path", "permissions"),
    [
        ("/dev/nvidiamodeset", "/dev/nvidiamodeset", "rwm"),
        ("/dev/nvidiauvm", "/dev/nvidiauvm", "rwm"),
        ("/dev/nvidiauvm-tools", "/dev/nvidiauvm-tools", "rwm"),
        ("/dev/nvidia-ctl", "/dev/nvidia-ctl", "rwm"),
        ("/dev/nvidia-uvm/foreign", "/dev/nvidia-uvm/foreign", "rwm"),
        ("/dev/nvidia-unknown", "/dev/nvidia-unknown", "rwm"),
        ("/dev/sda", "/dev/sda", "rwm"),
        ("/dev/nvidia0", "/dev/nvidia1", "rwm"),
        ("/dev/sda", "/dev/nvidia-uvm", "rwm"),
        ("/dev/nvidia-uvm", "/dev/sda", "rwm"),
        ("/dev/nvidia-uvm", "/dev/nvidia-uvm", "rwmx"),
    ],
)
def test_effective_unknown_or_mismatched_device_denies_input_and_still_cleans(
    tmp_path: Path, host_path: str, container_path: str, permissions: str
) -> None:
    """Rejected effective devices never obtain a lease or suppress owned cleanup."""
    world = World(FakeClock())
    world.devices.append(
        {
            "PathOnHost": host_path,
            "PathInContainer": container_path,
            "CgroupPermissions": permissions,
        }
    )
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["status"] == "failed"
    assert row["isolation"] is None
    assert row["report"] is None
    assert "input" not in world.effects
    assert not any(request["action"] == "integrity" for request in world.requests)
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "passed"
    assert cleanup["lobby_absent"] is True
    assert cleanup["container_absent"] is True
    assert cleanup["state_removed"] is True
    assert world.lobby is False
    assert world.container is False
    assert world.active is None
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert world.effects.index("remove_container") < world.effects.index("remove_state")
    saved = json.loads(
        (tmp_path / "output" / ("1" * 32) / "report.json").read_text(encoding="utf-8")
    )
    assert saved["status"] == "failed"
    assert saved["cases"][0]["status"] == "failed"
    assert saved["cases"][0]["cleanup"] == cleanup


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sysname", "event77"),
        ("node", "/dev/input/input103"),
        ("node", "/dev/input/event77/foreign"),
        ("role", "semantic"),
        ("source_pid", 99),
    ],
)
def test_frontend_rejects_unpinned_or_malformed_final_source(
    tmp_path: Path, field: str, value: object
) -> None:
    """Independent kernel identifiers still require approved live final ancestry."""
    world = World(FakeClock())
    world.final_source[field] = value
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["status"] == "failed"
    assert "Pinned frontend/final-source observation is incomplete" in sequence(
        row["errors"]
    )
    assert record(row["cleanup"])["state_removed"] is True


def test_crc_valid_invalid_compression_cannot_suppress_teardown_or_final_report(
    tmp_path: Path,
) -> None:
    """Decoder failure during both collection phases preserves independent cleanup."""
    world = World(FakeClock())
    world.invalid_compression = True
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["status"] == "failed"
    errors = sequence(row["errors"])
    assert "Capture PNG has invalid compressed data" in errors
    assert "Evidence collection: Capture PNG has invalid compressed data" in errors
    assert record(row["cleanup"])["status"] == "passed"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert world.effects.index("remove_container") < world.effects.index("remove_state")
    saved = json.loads(
        (tmp_path / "output" / ("1" * 32) / "report.json").read_text(encoding="utf-8")
    )
    assert saved["status"] == "failed"
    assert saved["cases"][0]["cleanup"]["state_removed"] is True


def test_busy_preflight_has_no_allocation_creation_or_input(tmp_path: Path) -> None:
    """Busy discovery is a refusal, never an empty successful test run."""
    world = World(FakeClock())
    world.busy = True
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert world.effects == []
    assert all(record(v)["status"] == "not-run" for v in sequence(report["cases"]))


@pytest.mark.parametrize(
    "fault", ["late_contention", "discovery_loss", "change_identity"]
)
def test_late_activity_or_lost_discovery_stops_subsequent_input_and_cases(
    tmp_path: Path, fault: str
) -> None:
    """Interruptions do not delete foreign resources or start another case."""
    world = World(FakeClock())
    setattr(world, fault, True)
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert report["interruption"] is not None
    assert world.effects.count("create") == 1
    assert world.effects.count("input") == 1
    assert "release" in world.effects
    assert record(sequence(report["cases"])[1])["status"] == "not-run"


@pytest.mark.parametrize(
    "fault",
    [
        "bad_isolation",
        "bad_report",
        "missing_receiver",
        "capture_loss",
        "withhold_report",
        "fail_collect",
    ],
)
def test_failed_prerequisite_assertion_or_evidence_cannot_pass(
    tmp_path: Path, fault: str
) -> None:
    """Malformed/missing assertions and evidence are not repaired by cleanup."""
    world = World(FakeClock())
    setattr(world, fault, True)
    _, report = execute(tmp_path, world, tier="receiver-smoke")
    assert report["status"] == "failed"
    assert world.effects.count("create") == 1
    assert "release" in world.effects
    if fault == "bad_isolation":
        assert "input" not in world.effects
    assert "remove_state" in world.effects


def test_lost_create_response_recovers_observed_owned_container_but_never_retries(
    tmp_path: Path,
) -> None:
    """Recovery authorizes cleanup, not a replacement attempt or green case."""
    world = World(FakeClock())
    world.lost_create = True
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    creates = [r for r in world.requests if r["action"] == "create"]
    assert len(creates) == 2
    assert [r["case_id"] for r in creates] == [
        "1" * 32 + "-frontend",
        "1" * 32 + "-receivers",
    ]
    assert len({text(r["case_id"]) for r in creates}) == 2
    first_cleanup = next(
        i for i, r in enumerate(world.requests) if r["action"] == "remove_state"
    )
    second_create = world.requests.index(creates[1])
    assert first_cleanup < second_create
    barrier = world.requests[first_cleanup]
    assert barrier["case_id"] == creates[0]["case_id"]
    rows = [record(v) for v in sequence(report["cases"])]
    assert all(row["status"] == "failed" for row in rows)
    assert all("Lost create response" in sequence(row["errors"]) for row in rows)
    assert all(record(row["cleanup"])["status"] == "passed" for row in rows)
    assert "input" not in world.effects
    assert world.effects.count("remove_state") == 2


def test_late_unobserved_startup_retains_state_even_after_lobby_stop(
    tmp_path: Path,
) -> None:
    """One empty Docker scan is not a cancellation barrier."""
    world = World(FakeClock())
    world.lost_create = world.late_start = True
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert "stop_lobby" in world.effects
    assert "remove_state" not in world.effects
    row = record(sequence(report["cases"])[0])
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "incomplete"
    assert cleanup["state_removed"] is False
    assert world.effects.count("create") == 1


def test_independent_stop_failure_still_attempts_container_cleanup(
    tmp_path: Path,
) -> None:
    """A failed stop response remains nonpassing even if later cleanup succeeds."""
    world = World(FakeClock())
    world.fail_stop = True
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert "stop_container" in world.effects
    assert "remove_container" in world.effects
    assert "remove_state" in world.effects
    assert world.effects.count("create") == 1


def test_expired_scenario_has_fresh_finite_cleanup_budgets(tmp_path: Path) -> None:
    """Exact boundary expiry cannot suppress release or teardown."""
    world = World(FakeClock())
    world.withhold_report = True
    coordinator, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    assert "remove_state" in world.effects
    cleanup_times = [
        row for row in coordinator.timings if str(row["phase"]).endswith(":cleanup")
    ]
    assert cleanup_times
    assert all(
        float(text_value) > 0
        for text_value in [row["call_budget"] for row in cleanup_times]
        if isinstance(text_value, (float, int))
    )


def test_missing_or_invalid_ssh_and_unapproved_run_fail_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuration rejection needs no real target or credential file."""
    monkeypatch.delenv("BATOCERA_GOW_SSH_TARGET", raising=False)
    assert main(["run"]) == 2
    assert main(["run", "--authorize-native"]) == 2
    for target in (
        "",
        "-oProxyCommand=bad",
        "wolf;touch bad",
        "user@host extra",
        "user@@host",
    ):
        with pytest.raises(SettingsError):
            SSHConfig.from_environment({"BATOCERA_GOW_SSH_TARGET": target})
    assert main(["plan"]) == 0


def test_alias_agent_and_optional_identity_path_need_no_key_reads() -> None:
    """The override is a pathname and ordinary SSH aliases remain unchanged."""
    agent = SSHConfig.from_environment({"BATOCERA_GOW_SSH_TARGET": "wolf-test"})
    assert agent.identity_file is None
    identity_config = SSHConfig.from_environment(
        {
            "BATOCERA_GOW_SSH_TARGET": "tester@[2001:db8::1]",
            "BATOCERA_GOW_SSH_IDENTITY_FILE": "/nonexistent/key with spaces",
        }
    )
    assert identity_config.identity_file == "/nonexistent/key with spaces"
    assert identity_config.target == "tester@[2001:db8::1]"


def test_artifact_collision_symlink_and_sensitive_lines_are_refused_or_redacted(
    tmp_path: Path,
) -> None:
    """Owner-only artifacts never overwrite or persist synthetic secret markers."""
    artifacts = Artifacts(tmp_path, "2" * 32)
    try:
        artifacts.put(
            "selected.log",
            str(
                sanitize("safe\nauthorization: synthetic-sensitive-marker\nend")
            ).encode(),
        )
        with pytest.raises(FileExistsError):
            artifacts.put("selected.log", b"overwrite")
        with pytest.raises(NativeError):
            artifacts.put("../foreign.log", b"escape")
    finally:
        artifacts.close()
    assert "synthetic-sensitive-marker" not in (
        tmp_path / ("2" * 32) / "selected.log"
    ).read_text(encoding="utf-8")
    (tmp_path / "linked").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((NotADirectoryError, PermissionError)):
        Artifacts(tmp_path / "linked", "3" * 32)


def test_png_validation_rejects_empty_forged_and_corrupt_capture() -> None:
    """A .png filename or signature alone supplies no accepted capture."""
    assert png_identity(fixture_png()) == (1, 1)
    for value in (
        b"",
        b"\x89PNG\r\n\x1a\n",
        fixture_png()[:-1],
        fixture_png()[:30] + b"x" + fixture_png()[31:],
    ):
        with pytest.raises(NativeError):
            png_identity(value)


def test_stock_frontend_ready_flag_requires_real_owned_regular_file(
    tmp_path: Path,
) -> None:
    """A missing flag or symlink cannot promote a splash/process to ready."""
    flag = tmp_path / "emulationstation.ready"
    assert frontend_ready_flag(flag, os.getuid()) is None
    flag.write_text("", encoding="utf-8")
    assert frontend_ready_flag(flag, os.getuid()) is not None
    with pytest.raises(DiagnosticError):
        frontend_ready_flag(flag, os.getuid() + 1)
    flag.unlink()
    flag.symlink_to(tmp_path / "other")
    with pytest.raises(DiagnosticError):
        frontend_ready_flag(flag, os.getuid())


def test_delivered_helper_allocates_real_state_without_host_imports(
    tmp_path: Path,
) -> None:
    """Run the exact SSH payload under isolated Python in a foreign cwd."""
    helper = files("batocera_gow.host").joinpath("native_remote.py")
    uid, gid = os.getuid() or 1000, os.getgid() or 1000
    request: dict[str, object] = {
        "action": "allocate",
        "wolf_container": "unused",
        "api_socket": "/unused",
        "timeout": 2,
        "uid": uid,
        "gid": gid,
        "host_root": str(tmp_path),
        "root_pin": identity(tmp_path.stat()),
        "case_id": "d" * 32,
        "token": "synthetic-owner",
    }
    # The isolated interpreter executes checked package bytes with JSON stdin.
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-B", "-c", helper.read_text(encoding="utf-8")],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0
    response = record(json.loads(completed.stdout))
    assert response["ok"] is True
    home = tmp_path / "test-runs" / ("d" * 32)
    assert home.is_dir()
    pin = record(record(response["result"])["pin"])
    OwnedState(tmp_path, "d" * 32, "synthetic-owner", uid, gid).remove(pin)
    assert not home.exists()


def test_delivered_os_failure_keeps_errno_without_private_exception_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual missing-state failure crosses SSH only as a fixed category and errno."""
    world = DeliveredStartupWorld(tmp_path, monkeypatch, "unknown")
    missing = tmp_path / "synthetic-private-operation-path"
    request: dict[str, object] = {
        "action": "revoke",
        "wolf_container": "unused",
        "api_socket": "/unused",
        "timeout": 2,
        "uid": os.getuid() or 1000,
        "gid": os.getgid() or 1000,
        "host_root": str(missing),
        "case_id": "d" * 32,
        "token": "synthetic-owner",
        "pin": {},
    }
    with pytest.raises(NativeError, match=r"os/unclassified errno=2") as failure:
        world.transport.request(request, 5)
    assert "synthetic-private-operation-path" not in str(failure.value)
    assert not missing.exists()


@pytest.mark.parametrize(
    ("failure", "category"),
    [
        (
            "raise DiagnosticError('Native app cannot read/write uinput')",
            "app-uinput-access",
        ),
        ("raise DiagnosticError(SECRET)", "unknown-diagnostic"),
        ("raise RuntimeError(SECRET)", "unexpected-exception; RuntimeError"),
        (
            "raise type(SECRET, (Exception,), {})(SECRET)",
            "unexpected-exception; Exception",
        ),
        (
            "raise FileNotFoundError(2, SECRET, '/private/' + SECRET)",
            "os-error; FileNotFoundError; errno=2",
        ),
    ],
)
def test_packaged_inspection_failure_is_attributed_without_secrets_and_cleans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    category: str,
) -> None:
    """Execute the delivered helper and wrapper, not an echoed error response."""
    # pragma: allowlist nextline secret
    secret = "synthetic-credential-do-not-persist"  # noqa: S105  # Privacy-test marker.
    package = tmp_path / "batocera_gow/runtime"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    module = package / "native_diagnostics.py"
    (package / "native_checks.py").write_bytes(
        files("batocera_gow.runtime").joinpath("native_checks.py").read_bytes(),
    )
    launcher = tmp_path / "native_checks.py"
    launcher.write_text(
        "from batocera_gow.runtime.native_checks import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    (tmp_path / "_inspection_fixture.py").write_text(
        "SECRET = " + repr(secret) + "\n", encoding="utf-8"
    )
    module.write_text(
        "import sys\n"
        "from _inspection_fixture import SECRET\n"
        "print(SECRET)\n"
        "print(SECRET, file=sys.stderr)\n"
        "class DiagnosticError(RuntimeError): pass\n"
        "def inspect_runtime(request):\n"
        "    " + failure + "\n",
        encoding="utf-8",
    )
    module.chmod(0o400)
    # These executable adapters replace only SSH/Docker transport. Both execute
    # the real delivered programs with stdin intact and no native effects.
    ssh = tmp_path / "ssh"
    ssh.write_text(
        "#!" + sys.executable + "\n"
        "import os, shlex, sys\n"
        "payload = shlex.split(sys.argv[-1])[-1]\n"
        "os.execv(sys.executable, [sys.executable, '-I', '-B', '-c', payload])\n",
        encoding="utf-8",
    )
    docker = tmp_path / "docker"
    docker.write_text(
        "#!" + sys.executable + "\n"
        "import json, os, pathlib, sys\n"
        "if sys.argv[1] == 'ps':\n"
        "    print('e' * 64)\n"
        "elif sys.argv[1] == 'inspect':\n"
        "    print(pathlib.Path(os.environ['INSPECTION_CONTAINER']).read_text())\n"
        "elif sys.argv[1] == 'exec':\n"
        "    args = sys.argv[sys.argv.index('/usr/bin/python3') + 1:]\n"
        "    args[-2] = os.environ['INSPECTION_LAUNCHER']\n"
        "    os.execv(sys.executable, [sys.executable, *args])\n"
        "else:\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    ssh.chmod(0o700)
    docker.chmod(0o700)
    container_record = tmp_path / "container.json"
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("INSPECTION_CONTAINER", str(container_record))
    monkeypatch.setenv("INSPECTION_LAUNCHER", str(launcher))
    helper = files("batocera_gow.host").joinpath("native_remote.py")
    transport = SSHTransport(
        SSHConfig("fixture-only"), helper.read_text(encoding="utf-8")
    )
    uid, gid = os.getuid() or 1000, os.getgid() or 1000
    state = OwnedState(tmp_path, "e" * 32, "fixture-owner", uid, gid)
    pin = state.allocate()
    container_record.write_text(
        json.dumps(
            [
                {
                    "Id": "e" * 64,
                    "Image": "sha256:" + "a" * 64,
                    "Config": {"Labels": {"io.gow.integration.owner": "fixture-owner"}},
                    "Mounts": [
                        {"Destination": "/home/retro", "Source": str(state.path)}
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    class InspectionWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "integrity":
                return transport.request(
                    {
                        **value,
                        "host_root": str(tmp_path),
                        "case_id": "e" * 32,
                        "token": "fixture-owner",
                        "container_id": "e" * 64,
                        "pin": pin,
                        "uid": uid,
                        "gid": gid,
                    },
                    timeout,
                )
            result = super().request(value, timeout)
            if value.get("action") == "remove_state":
                state.remove(pin)
            return result

    world = InspectionWorld(FakeClock())
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert "Packaged inspection failed: " + category in sequence(row["errors"])
    assert row["isolation"] is None
    assert row["report"] is None
    assert "input" not in world.effects
    cleanup = record(row["cleanup"])
    assert cleanup["status"] == "passed"
    assert cleanup["lobby_absent"] is True
    assert cleanup["container_absent"] is True
    assert cleanup["state_removed"] is True
    assert not state.path.exists()
    assert not world.container
    assert not world.lobby
    output = tmp_path / "output" / ("1" * 32)
    assert secret not in json.dumps(report)
    assert all(secret.encode() not in path.read_bytes() for path in output.iterdir())


def test_operator_interruption_revokes_input_and_still_cleans(tmp_path: Path) -> None:
    """An interrupted native request cannot open another lease or case."""

    class InterruptedWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "lease":
                msg = "Operator signal"
                raise InterruptedError(msg)
            return super().request(value, timeout)

    world = InterruptedWorld(FakeClock())
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert report["interruption"] == "Operator signal"
    assert world.effects.count("create") == 1
    assert "input" not in world.effects
    assert "release" in world.effects
    assert "remove_state" in world.effects


def test_late_allocation_response_retains_unknown_identity(tmp_path: Path) -> None:
    """An effect at a call deadline is not treated as a safe acknowledgement."""

    class LateWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            result = super().request(value, timeout)
            if value.get("action") == "allocate":
                self.clock.sleep(timeout)
            return result

    world = LateWorld(FakeClock())
    _, report = execute(tmp_path, world)
    assert report["status"] == "failed"
    assert world.effects == ["allocate"]
    first = record(sequence(report["cases"])[0])
    assert record(first["cleanup"])["status"] == "incomplete"
    assert record(sequence(report["cases"])[1])["status"] == "not-run"


def test_local_evidence_collision_cannot_suppress_owned_teardown(
    tmp_path: Path,
) -> None:
    """Real publication failure leaves foreign evidence untouched and fails."""
    world = World(FakeClock())
    run_id = "4" * 32
    artifacts = Artifacts(tmp_path, run_id)
    foreign = b"previous owner's evidence"
    artifacts.put("frontend-startup.json", foreign)
    coordinator = Coordinator(
        config("frontend-smoke"), world, world.clock, artifacts, run_id
    )
    try:
        report = coordinator.run()
    finally:
        artifacts.close()
    assert report["status"] == "failed"
    assert (tmp_path / run_id / "frontend-startup.json").read_bytes() == foreign
    assert "remove_state" in world.effects
    assert world.effects.count("create") == 1


def test_ssh_process_timeout_reaps_only_owned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise a real hung transport process, never a native-success fixture."""
    executable = tmp_path / "ssh"
    pidfile = tmp_path / "ssh.pid"
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import os, pathlib, time\n"
        "pathlib.Path(os.environ['NATIVE_TEST_PID']).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("NATIVE_TEST_PID", str(pidfile))
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        transport = SSHTransport(SSHConfig("fixture-only"), "unused")
        with pytest.raises(NativeError):
            transport.request({"action": "snapshot"}, 1)
        assert unrelated.poll() is None
        pid = int(pidfile.read_text(encoding="utf-8"))
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_unavailable_ssh_binary_is_a_bounded_transport_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing transport cannot be mistaken for empty native discovery."""
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(NativeError):
        SSHTransport(SSHConfig("fixture-only"), "unused").request(
            {"action": "snapshot"}, 1
        )


def test_incomplete_integrity_observation_cannot_open_input(tmp_path: Path) -> None:
    """A bare success boolean is not evidence of packaged app isolation."""

    class IncompleteWorld(World):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            if value.get("action") == "integrity":
                return {"verified": True}
            return super().request(value, timeout)

    world = IncompleteWorld(FakeClock())
    _, report = execute(tmp_path, world, tier="frontend-smoke")
    assert report["status"] == "failed"
    assert "input" not in world.effects
    assert "remove_state" in world.effects


@pytest.mark.parametrize(
    ("tier", "core", "info"),
    [
        ("nes-smoke", "fceumm", "fceumm"),
        ("snes-smoke", "snes9x", "snes9x"),
        ("megadrive-smoke", "genesisplusgx", "genesis_plus_gx"),
        ("atari2600-smoke", "stella", "stella"),
    ],
)
def test_stock_hash_selection_uses_installed_python_inventory(
    tmp_path: Path, tier: str, core: str, info: str
) -> None:
    """Derive exact hashes from regular metadata, not unhashed stock aliases."""
    names = (
        "/usr/bin/hotkeygen",
        "/usr/bin/evmapy",
        "/etc/hotkeygen/default_mapping.conf",
        "/etc/hotkeygen/default_context.conf",
        "/etc/hotkeygen/common_context.conf",
        "/usr/share/evmapy/hotkeys.keys",
        "/usr/share/emulationstation/es_systems.cfg",
        "/usr/lib/python3.13/site-packages/evmapy/controller.py",
        "/usr/bin/emulatorlauncher",
        "/usr/bin/retroarch",
        "/usr/bin/udevadm",
        "/usr/lib/libSDL2-2.0.so.0.3200.8",
        "/lib/libudev.so.1.6.3",
        "/usr/lib/libretro/fceumm_libretro.so",
        "/usr/share/libretro/info/fceumm_libretro.info",
        "/usr/lib/libretro/snes9x_libretro.so",
        "/usr/share/libretro/info/snes9x_libretro.info",
        "/usr/lib/libretro/genesisplusgx_libretro.so",
        "/usr/share/libretro/info/genesis_plus_gx_libretro.info",
        "/usr/lib/libretro/stella_libretro.so",
        "/usr/share/libretro/info/stella_libretro.info",
        "/usr/lib/python3.13/site-packages/configgen/controller.py",
    )
    # These two records reproduce the pinned stock manifest's metadata seam.
    canonical_info = "/usr/share/libretro/info/genesis_plus_gx_libretro.info"
    alias_info = "/usr/share/libretro/info/genesisplusgx_libretro.info"
    # pragma: allowlist nextline secret
    info_sha256 = "9793bff8d9e298a7ee0c94c0511dab242200ca60fbe87e3720eb9231a3e0166a"
    entries: dict[str, object] = {name: {"sha256": "d" * 64} for name in names}
    entries[canonical_info] = {"type": 32768, "sha256": info_sha256}
    entries[alias_info] = {
        "type": 40960,
        "target": "genesis_plus_gx_libretro.info",
    }
    stock = tmp_path / "stock.json"
    stock.write_text(json.dumps({"schema": 1, "entries": entries}), encoding="utf-8")
    build = tmp_path / "build.json"
    build.write_text(
        json.dumps(
            {
                "status": "success",
                "inventory_verified": True,
                "release": "43.1",
                "image_id": "sha256:" + "a" * 64,
                "adapter_revision": "worktree-sha256:" + "b" * 64,
                "input_sha256": "c" * 64,
            }
        ),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime"
    source, wrapper, catalog = stage_integrity_runtime(runtime)
    image, revision, stock_sha, hashes = load_integrity(build, stock, runtime, tier)
    assert image == "sha256:" + "a" * 64
    assert revision == "worktree-sha256:" + "b" * 64
    assert stock_sha == "c" * 64
    assert all(hashes[name] == "d" * 64 for name in names if name != canonical_info)
    assert hashes[canonical_info] == info_sha256
    assert alias_info not in hashes
    assert hashes["/opt/gow-full-x86/support.py"] == hashlib.sha256(source).hexdigest()
    assert (
        hashes["/opt/gow-full-x86/batocera_gow/runtime/media_catalog.py"]
        == hashlib.sha256(source).hexdigest()
    )
    assert (
        hashes["/opt/gow-full-x86/suite-gamepad.json"]
        == hashlib.sha256(b"synthetic test asset").hexdigest()
    )
    for asset in (wrapper, catalog):
        packaged = "/opt/gow-full-x86/" + str(asset.relative_to(runtime))
        assert hashes[packaged] == hashlib.sha256(asset.read_bytes()).hexdigest()
        asset.write_bytes(asset.read_bytes() + b"\n")
        changed = load_integrity(build, stock, runtime, tier)[3]
        assert changed[packaged] != hashes[packaged]
    for missing in (
        "/usr/lib/libretro/" + core + "_libretro.so",
        "/usr/share/libretro/info/" + info + "_libretro.info",
    ):
        incomplete = dict(entries)
        del incomplete[missing]
        stock.write_text(json.dumps({"entries": incomplete}), encoding="utf-8")
        with pytest.raises(NativeError, match="inventory is incomplete"):
            load_integrity(build, stock, runtime, tier)
    if tier == "megadrive-smoke":
        wrong_metadata = dict(entries)
        del wrong_metadata[canonical_info]
        wrong_metadata[
            "/usr/share/libretro/info/genesis_plus_gx_wide_libretro.info"
        ] = {
            # pragma: allowlist nextline secret
            "sha256": "8aa2205e8a3ea2cf2ed04d5ae83eed52c4e9ca6b8d2722afa2bb853a9939357c"
        }
        stock.write_text(json.dumps({"entries": wrong_metadata}), encoding="utf-8")
        with pytest.raises(NativeError, match="inventory is incomplete"):
            load_integrity(build, stock, runtime, tier)


def stage_integrity_runtime(runtime: Path) -> tuple[bytes, Path, Path]:
    """Stage synthetic installed files for transitive integrity hashing.

    Args:
        runtime: Owned temporary runtime tree to populate.

    Returns:
        Source bytes and the wrapper/catalog paths whose mutations are tested.
    """
    runtime.mkdir()
    source = b'"""Synthetic package source, not native evidence."""\n'
    (runtime / "support.py").write_bytes(source)
    package = runtime / "batocera_gow/runtime"
    package.mkdir(parents=True)
    for name in ("media_catalog.py", "mounted_media.py"):
        (package / name).write_bytes(source)
    for name in ("suite-gamepad.json", "suite-es-input.cfg"):
        (runtime / name).write_bytes(b"synthetic test asset")
    wrapper = runtime / "emulator-wrappers/duckstation-qt"
    wrapper.parent.mkdir()
    wrapper.write_bytes(
        b"#!/bin/sh\n"
        b'exec /usr/bin/python3 /opt/gow-full-x86/duckstation_wrapper.py "$@"\n',
    )
    catalog = runtime / "es_systems_gow_duckstation.cfg"
    catalog.write_bytes(b"<systemList/>")
    return source, wrapper, catalog


class EmulatorWorld(World):
    """Independent emulator evidence at the same inspected native lifecycle."""

    def __init__(self, clock: FakeClock, failure: str = "none") -> None:
        """Choose a modeled emulator outcome without performing native effects."""
        super().__init__(clock)
        self.failure = failure
        self.reproducing = False
        self.case_name = "nes-fceumm"

    def inspection(self, request: dict[str, object]) -> dict[str, object]:
        """Observe the emulator command and independently controlled mount access."""
        result = super().inspection(request)
        container = record(result["container"])
        settings = record(container["Config"])
        settings["Cmd"] = ["/usr/bin/python3", "/opt/gow-full-x86/emulator_probe.py"]
        settings["Env"] = [
            *sequence(settings["Env"]),
            "GOW_EMULATOR_NEGATIVE_CONTROL=none",
            "GOW_EMULATOR_CASE=" + self.case_name,
            *(["GOW_EMULATOR_REPRODUCE=1"] if self.reproducing else []),
        ]
        container["Config"] = settings
        result["container"] = container
        if self.failure == "writable-media":
            mounts = [record(item) for item in sequence(container["Mounts"])]
            next(
                item
                for item in mounts
                if item["Destination"] == "/home/retro/userdata/roms"
            )["RW"] = True
            container["Mounts"] = mounts
        return result

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Model selection seeding and independently installed stock hashes."""
        if value["action"] == "seed_selection":
            assert not self.leased
            self.effects.append("reproduction")
            self.requests.append(dict(value))
            return {"seeded": True}
        result = super().request(value, timeout)
        if value["action"] == "integrity":
            # Independent installed-file observations, not requested hashes.
            result["hashes"] = {
                "/opt/gow-full-x86/runtime.py": "d" * 64,
                "/opt/gow-full-x86/suite-gamepad.json": "3" * 64,
                "/opt/gow-full-x86/suite-es-input.cfg": "4" * 64,
                "/usr/bin/retroarch": "5" * 64,
                "/usr/bin/udevadm": "8" * 64,
                "/usr/lib/libSDL2-2.0.so.0.3200.8": "9" * 64,
                "/lib/libudev.so.1.6.3": "a" * 64,
                "/usr/lib/libretro/fceumm_libretro.so": "6" * 64,
                "/usr/share/libretro/info/fceumm_libretro.info": "7" * 64,
                "/usr/lib/python3.12/site-packages/configgen/emulatorlauncher.py": (
                    # pragma: allowlist nextline secret
                    "73313380a3d40a44580c2e046eadf1f2b8c315cf475a0d56dd0a916e0b0a6a1f"
                ),
            }
        return result

    def _passing_report(self, captures: list[dict[str, str]]) -> dict[str, object]:
        """Construct independent libretro launch, native-input and exit evidence."""
        report: dict[str, object] = {
            "status": "passed",
            "case": "nes-fceumm",
            "system": "nes",
            "backend": "libretro",
            "core": "fceumm",
            "assertions": "stock-native-observed-exit-v3",
            "negative_control": "none",
            "media": {"identity": "1" * 64, "catalog_sha256": STOCK_SHA256},
            "pad_discovery": {
                "event_device": [13, 78],
                "discovery_mode": {"udev_selected": True},
                "publication": {
                    "properties": {"ID_INPUT": "1", "ID_INPUT_JOYSTICK": "1"},
                    "classifier_sha256": "8" * 64,
                },
                "sdl_object": {
                    "status": "mapped",
                    "inventory_path": "/usr/lib/libSDL2-2.0.so.0.3200.8",
                    "sha256": "9" * 64,
                },
                "udev_object": {
                    "status": "mapped",
                    "inventory_path": "/lib/libudev.so.1.6.3",
                    "sha256": "a" * 64,
                },
            },
            "profile": {
                "sha256": "2" * 64,
                "definition_sha256": "3" * 64,
                "template_sha256": "4" * 64,
                "guid": "03" * 16,
                "qualified_controls": [["button", 315, 7], ["button", 316, 8]],
                "stock_configgen_consumed": True,
                "event_device": [13, 78],
            },
            "backend_identity": {
                "core": "fceumm",
                "executable_sha256": "5" * 64,
                "core_sha256": "6" * 64,
                "core_info_sha256": "7" * 64,
                "retroarch_version": "1.21.0",
                "core_library": "FCEUmm",
                "core_version": "(SVN)",
            },
            "native_device_consumption": {
                "status": "passed",
                "input_driver": "udev",
                "input_joypad_driver": "udev",
                "final_udev": {"ID_INPUT_KEYBOARD": "1"},
                "final_device": [13, 77],
                "pad_device": [13, 78],
                "final_source": {"pid": 23, "start": 2300, "pinned_live": True},
                "opened_devices": [[13, 77], [13, 78]],
            },
            "chord": {
                "route": "owned-uinput-stock-evmapy-adapter-stock-hotkeygen",
                "pressed": True,
                "released": True,
            },
            "transition": {
                "emulator": {"pid": 31, "start": 3100},
                "stock_launch_display": {
                    "active_pid": 31,
                    "exact_core_loaded": True,
                    "rendered_content": True,
                    "live": True,
                },
                "live_before_chord_seconds": 2,
                "native_guide_start": True,
                "same_emulator_exited": True,
                "launcher_code": 0,
                "forced_teardown": False,
                "captures": captures,
            },
            "termination_observation": {
                "mechanism": "pidfd-and-stock-launcher",
                "kind": "unavailable",
                "complete": False,
                "classification": {"status": "rejected", "reason": "logging-error"},
                "emulator": {"pid": 31, "start": 3100, "live": False},
                "launcher": {"pid": 30, "start": 3000, "code": 0},
                "launcher_source_sha256": (
                    # pragma: allowlist nextline secret
                    "73313380a3d40a44580c2e046eadf1f2b8c315cf475a0d56dd0a916e0b0a6a1f"
                ),
                "log_sha256": "8" * 64,
            },
            "cleanup": {"status": "passed", "forced_emulator_teardown": False},
            "stock_hashes": {"unchanged": True},
        }
        return report

    def _damage_report(self, report: dict[str, object]) -> None:
        """Remove or alter exactly the observation selected by the scenario."""
        changes: dict[str, dict[tuple[str, ...], object]] = {
            "wrong-process": {("transition", "emulator"): {"pid": -1, "start": 3100}},
            "forced": {("transition", "forced_teardown"): True},
            "receiver-only": {("native_device_consumption",): {"status": "passed"}},
            "no-chord": {("chord", "pressed"): False},
            "unreleased-chord": {("chord", "released"): False},
            "old-assertion": {("assertions",): "stock-native-exit-v2"},
            "cleanup-forced": {("cleanup", "forced_emulator_teardown"): True},
            "cleanup-failed": {("cleanup", "status"): "failed"},
            "no-profile-consumption": {("profile", "stock_configgen_consumed"): False},
            "launcher-error": {("transition", "launcher_code"): 1},
            "wrong-asset": {("profile", "template_sha256"): "e" * 64},
            "wrong-backend": {("backend_identity", "executable_sha256"): "e" * 64},
            "signaled-log": {
                ("termination_observation", "kind"): "signaled",
                ("termination_observation", "complete"): True,
                ("termination_observation", "classification"): {
                    "status": "classified",
                    "reason": None,
                },
                ("termination_observation", "log_sha256"): None,
            },
            "no-stream": {
                ("termination_observation", "kind"): "unavailable",
                ("termination_observation", "complete"): False,
                ("termination_observation", "classification"): {
                    "status": "stream-unavailable",
                    "reason": None,
                },
                ("termination_observation", "log_sha256"): None,
            },
            "emulator-live": {("termination_observation", "emulator", "live"): True},
            "launcher-pending": {("termination_observation", "launcher", "code"): None},
            "wrong-launcher": {("termination_observation", "launcher", "pid"): 31},
            "missing-termination": {("termination_observation",): MISSING_OBSERVATION},
            "wrong-termination-process": {
                ("termination_observation", "emulator"): {
                    "pid": 32,
                    "start": 3200,
                    "live": False,
                },
            },
            "wrong-termination-source": {
                ("termination_observation", "launcher_source_sha256"): "e" * 64,
            },
            "missing-classification": {("pad_discovery", "publication"): {}},
            "wrong-classifier": {
                ("pad_discovery", "publication", "classifier_sha256"): "e" * 64,
            },
            "unknown-mode": {("pad_discovery", "discovery_mode"): {}},
            "fallback-mode": {
                ("pad_discovery", "discovery_mode"): {
                    "udev_selected": True,
                    "fallback_init_failed": True,
                },
            },
            "wrong-sdl": {("pad_discovery", "sdl_object", "sha256"): "e" * 64},
            "wrong-udev": {("pad_discovery", "udev_object", "sha256"): "e" * 64},
        }
        alter_observations(report, changes.get(self.failure, {}))

    @override
    def evidence(self, request: dict[str, object]) -> dict[str, object]:
        """Publish independent synthetic report and private identity artifacts."""
        files: dict[str, object] = {
            "startup.json": base64.b64encode(b'{"uid":1000,"gid":1000}').decode(),
        }
        if not self.leased:
            return {"files": files}
        names = ("emulator-before-exit",)
        captures = [
            {
                "path": name + ".png",
                "sha256": hashlib.sha256(fixture_png()).hexdigest(),
                "mechanism": "authenticated-libX11-XGetImage-stock-Pillow",
            }
            for name in names
        ]
        report = self._passing_report(captures)
        if self.failure == "absence":
            report = {
                "case": "nes-fceumm",
                "system": "nes",
                "backend": "libretro",
                "core": "fceumm",
                "assertions": "stock-native-observed-exit-v3",
                "negative_control": "none",
                "status": "skipped-no-media",
                "reason": "Skipped: no compatible mounted media",
                "native_device_consumption": {"status": "untested"},
                "stock_hashes": {"unchanged": True},
                "cleanup": {"status": "passed"},
            }
        else:
            self._damage_report(report)
        files["emulator-probe.json"] = base64.b64encode(
            json.dumps(report).encode()
        ).decode()
        if self.failure == "report-loss":
            del files["emulator-probe.json"]
        files["selected.log"] = base64.b64encode(b"bounded owned observations").decode()
        if self.failure != "absence":
            # This path belongs only in the private selection artifact.
            files["selection.json"] = base64.b64encode(
                b'{"schema":1,"system":"nes","entry":"nes/private-title.nes"}'
            ).decode()
            for name in names:
                if self.failure == "capture-loss" and name == "emulator-before-exit":
                    continue
                files[name + ".png"] = base64.b64encode(fixture_png()).decode()
        return {"files": files}


class RemainingLibretroWorld(EmulatorWorld):
    """Supply case-specific observations independently of coordinator requests."""

    def __init__(
        self, clock: FakeClock, system: str, core: str, failure: str = "none"
    ) -> None:
        """Select the independent stock system, core and modeled failure."""
        super().__init__(clock, failure)
        self.system = system
        self.core = core
        self.case_name = system + "-" + core

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Supply each remaining libretro core's distinct installed inventory."""
        result = super().request(value, timeout)
        if value["action"] == "integrity":
            hashes = record(result["hashes"])
            hashes.update(
                {
                    "/usr/lib/libretro/snes9x_libretro.so": "b" * 64,
                    "/usr/share/libretro/info/snes9x_libretro.info": "c" * 64,
                    "/usr/lib/libretro/genesisplusgx_libretro.so": "e" * 64,
                    "/usr/share/libretro/info/genesis_plus_gx_libretro.info": "f" * 64,
                    "/usr/lib/libretro/stella_libretro.so": "0" * 64,
                    "/usr/share/libretro/info/stella_libretro.info": "1" * 64,
                }
            )
            result["hashes"] = hashes
        return result

    def evidence(self, request: dict[str, object]) -> dict[str, object]:
        """Adapt the generic libretro observations to the selected stock core."""
        result = super().evidence(request)
        files = record(result["files"])
        if "emulator-probe.json" not in files:
            return result
        report = record(
            json.loads(base64.b64decode(text(files["emulator-probe.json"])))
        )
        report.update(
            case=self.system + "-" + self.core,
            system=self.system,
            core=self.core,
        )
        if self.failure not in ("absence", "wrong-case-absence"):
            digest, info_digest, library = {
                "snes9x": ("b" * 64, "c" * 64, "Snes9x"),
                "genesisplusgx": ("e" * 64, "f" * 64, "Genesis Plus GX"),
                "stella": ("0" * 64, "1" * 64, "Stella"),
            }[self.core]
            backend = record(report["backend_identity"])
            backend.update(
                core=self.core,
                core_sha256=digest,
                core_info_sha256=info_digest,
                core_library=library,
            )
            report["backend_identity"] = backend
            if self.failure == "other-system":
                report["system"] = "nes"
            elif self.failure == "other-core":
                report["core"] = "picodrive"
            elif self.failure == "other-case":
                report["case"] = "nes-fceumm"
            elif self.failure == "other-backend-core":
                backend["core"] = "fceumm"
                report["backend_identity"] = backend
            elif self.failure == "other-backend-info":
                backend["core_info_sha256"] = "c" * 64
                report["backend_identity"] = backend
            elif self.failure == "unopened-final":
                consumption = record(report["native_device_consumption"])
                consumption["opened_devices"] = [[13, 78]]
                report["native_device_consumption"] = consumption
            files["selection.json"] = base64.b64encode(
                json.dumps(
                    {"schema": 1, "system": self.system, "entry": "private-title"}
                ).encode()
            ).decode()
        if self.failure == "wrong-case-absence":
            report = {
                "status": "skipped-no-media",
                "case": "nes-fceumm",
                "system": "nes",
                "backend": "libretro",
                "core": "fceumm",
                "assertions": "stock-native-observed-exit-v3",
                "negative_control": "none",
                "reason": "Skipped: no compatible mounted media",
                "native_device_consumption": {"status": "untested"},
                "stock_hashes": {"unchanged": True},
                "cleanup": {"status": "passed"},
            }
        files["emulator-probe.json"] = base64.b64encode(
            json.dumps(report).encode()
        ).decode()
        result["files"] = files
        return result


def remaining_libretro_config(tier: str) -> NativeConfig:
    """Pin distinct core inventories so another core's evidence cannot pass."""
    nes = config("nes-smoke")
    return dataclasses.replace(
        nes,
        tier=tier,
        hashes={
            **nes.hashes,
            "/usr/lib/libretro/snes9x_libretro.so": "b" * 64,
            "/usr/share/libretro/info/snes9x_libretro.info": "c" * 64,
            "/usr/lib/libretro/genesisplusgx_libretro.so": "e" * 64,
            "/usr/share/libretro/info/genesis_plus_gx_libretro.info": "f" * 64,
            "/usr/lib/libretro/stella_libretro.so": "0" * 64,
            "/usr/share/libretro/info/stella_libretro.info": "1" * 64,
        },
    )


class DuckstationWorld(EmulatorWorld):
    """Model stock Qt/SDL observations without RetroArch-only requirements."""

    def __init__(
        self, clock: FakeClock, failure: str = "none", renderer: str = "OpenGL"
    ) -> None:
        """Select the standalone renderer and a controlled observation failure."""
        super().__init__(clock, failure)
        self.renderer = renderer
        self.case_name = "psx-duckstation" + ("-vulkan" if renderer == "Vulkan" else "")

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Replace libretro inventory with the independent Qt backend inventory."""
        result = super().request(value, timeout)
        if value["action"] == "integrity":
            hashes = record(result["hashes"])
            for path in (
                "/usr/bin/retroarch",
                "/usr/lib/libretro/fceumm_libretro.so",
                "/usr/share/libretro/info/fceumm_libretro.info",
            ):
                del hashes[path]
            hashes.update(
                {
                    "/usr/bin/duckstation-qt": (
                        # pragma: allowlist nextline secret
                        "24814978c0b8cd8a0b8eea756396c0b0df2067d1fb5adb64a3c5c34fd876c1fe"
                    ),
                    (
                        "/usr/lib/python3.12/site-packages/configgen/generators/"
                        "duckstation/duckstationGenerator.py"
                    ): (
                        # pragma: allowlist nextline secret
                        "00751590cabf239f2cdab37e8edcbe3c7460373beda0b4a59fe60cd1a9e32536"
                    ),
                }
            )
            result["hashes"] = hashes
        return result

    def evidence(self, request: dict[str, object]) -> dict[str, object]:
        """Publish Qt-specific controller, renderer and BIOS observations."""
        result = super().evidence(request)
        files = record(result["files"])
        if "emulator-probe.json" not in files:
            return result
        report = record(
            json.loads(base64.b64decode(text(files["emulator-probe.json"]))),
        )
        report.update(
            case=self.case_name,
            system="psx",
            backend="duckstation",
            core="duckstation",
        )
        if self.failure != "absence":
            self._configure_duckstation(report)
            files["selection.json"] = base64.b64encode(
                b'{"schema":1,"system":"psx","entry":"psx/private-title.cue"}',
            ).decode()
            self._damage_duckstation(report)
            if self.failure == "missing-bios":
                del files["emulator-before-exit.png"]
        files["emulator-probe.json"] = base64.b64encode(
            json.dumps(report).encode(),
        ).decode()
        result["files"] = files
        return result

    def _configure_duckstation(self, report: dict[str, object]) -> None:
        """Replace libretro assumptions with independent standalone observations."""
        report["backend_identity"] = {
            "variant": "duckstation-qt",
            "reported_version": {
                "argument": "-version",
                "exit_code": 1,
                "output": "DuckStation Version  ()",
                "tag": "",
                "branch": "",
            },
            "package_source": {
                "version": "v0.1-7294",
                # pragma: allowlist nextline secret
                "revision": "3a08ad18406efc1ddc4927a59bea715961bb63fa",
                "recipe": (
                    "https://github.com/batocera-linux/batocera.linux/blob/"
                    "155c2d8d304cbb53db52e9479dcf683392821d5c/"
                    "package/batocera/emulators/duckstation/duckstation.mk"
                ),
            },
            "executable": "/usr/bin/duckstation-qt",
            "executable_sha256": (
                # pragma: allowlist nextline secret
                "24814978c0b8cd8a0b8eea756396c0b0df2067d1fb5adb64a3c5c34fd876c1fe"
            ),
        }
        report["prerequisites"] = {
            "bios": {
                "status": "available",
                "identity": "c" * 64,
                "stock_configured_route": True,
            },
        }
        profile = record(report["profile"])
        profile["sdl_index"] = 0
        report["profile"] = profile
        # Stock Qt consumes SDL and settings.ini, not a final-keyboard event FD.
        report["native_device_consumption"] = {
            "status": "passed",
            "input_source": "SDL",
            "pad_device": [13, 78],
            "opened_devices": [[13, 78]],
            "stock_exit_context": "duckstation",
            "consumer_topology": {
                "discovered_joysticks": 1,
                "opened_joysticks": [[13, 78]],
                "configured_player_index": 0,
                "index_basis": "single-observed-suite-pad",
            },
            "environment": {
                "sdl_mapping_guid": "03" * 16,
                "suite_mapping_consumed": True,
                "SDL_JOYSTICK_HIDAPI": "0",
                "XDG_CONFIG_HOME": "/userdata/system/configs",
            },
            "generated_mapping": {
                "InputSources.SDL": "true",
                "InputSources.Evdev": "false",
                "InputSources.XInput": "false",
                "InputSources.RawInput": "false",
                "Pad1.Type": "DigitalController",
                "Pad1.Start": "SDL-0/Start",
                "Pad1.Cross": "SDL-0/A",
            },
        }
        transition = record(report["transition"])
        pinned = record(transition["emulator"])
        report["renderer"] = {
            "selected": self.renderer,
            "active": self.renderer,
            "pid": pinned["pid"],
            "start": pinned["start"],
            "activation": "pinned-open-file-device-context-hw-framebuffer",
            "visual_argument": "0x125" if self.renderer == "OpenGL" else None,
            "discovery": "live-egl-x11" if self.renderer == "OpenGL" else "not-run",
        }
        display = record(transition["stock_launch_display"])
        del display["exact_core_loaded"]
        display["exact_backend_loaded"] = True
        display.update(selected_disc_open=True, render_window=True, non_dialog=True)
        transition["stock_launch_display"] = display
        report["transition"] = transition

    def _damage_duckstation(self, report: dict[str, object]) -> None:
        """Apply one backend failure without altering unrelated observations."""
        other_renderer = "Vulkan" if self.renderer == "OpenGL" else "OpenGL"
        changes: dict[str, dict[tuple[str, ...], object]] = {
            "wrong-renderer": {("renderer", "selected"): other_renderer},
            "missing-active-renderer": {("renderer", "active"): MISSING_OBSERVATION},
            "wrong-active-renderer": {("renderer", "active"): other_renderer},
            "wrong-renderer-pid": {("renderer", "pid"): 9999},
            "wrong-visual": {
                ("renderer", "visual_argument"): (
                    None if self.renderer == "OpenGL" else "0x125"
                ),
            },
            "wrong-discovery": {
                ("renderer", "discovery"): (
                    "not-run" if self.renderer == "OpenGL" else "live-egl-x11"
                ),
            },
            "other-backend": {("backend",): "libretro"},
            "other-case": {("case",): "nes-fceumm"},
            "wrong-executable": {("backend_identity", "executable_sha256"): "e" * 64},
            "missing-version": {
                ("backend_identity", "reported_version"): MISSING_OBSERVATION,
            },
            "unopened-pad": {("native_device_consumption", "opened_devices"): []},
            "multiple-pads": {
                (
                    "native_device_consumption",
                    "consumer_topology",
                    "discovered_joysticks",
                ): 2,
            },
            "configured-index-only": {
                (
                    "native_device_consumption",
                    "consumer_topology",
                    "opened_joysticks",
                ): MISSING_OBSERVATION,
            },
            "dialog-output": {
                ("transition", "stock_launch_display", "non_dialog"): False,
            },
            "wrong-environment": {
                (
                    "native_device_consumption",
                    "environment",
                    "SDL_JOYSTICK_HIDAPI",
                ): "1",
            },
            "missing-consumption": {
                ("native_device_consumption",): {"status": "passed"},
            },
            "pre-chord-death": {
                ("transition", "stock_launch_display", "live"): False,
                ("transition", "live_before_chord_seconds"): 0,
            },
            "missing-bios": {
                ("status",): "failed",
                ("prerequisites",): {"bios": {"status": "missing"}},
                ("native_device_consumption",): {"status": "untested"},
                ("profile", "stock_configgen_consumed"): False,
                ("backend_identity",): MISSING_OBSERVATION,
                ("chord",): MISSING_OBSERVATION,
                ("transition",): MISSING_OBSERVATION,
                ("termination_observation",): MISSING_OBSERVATION,
            },
        }
        alter_observations(report, changes.get(self.failure, {}))


def duckstation_config() -> NativeConfig:
    """Require the inventoried Qt executable and actual stock generator."""
    nes = config("nes-smoke")
    return dataclasses.replace(
        nes,
        tier="psx-smoke",
        hashes={
            path: digest
            for path, digest in {
                **nes.hashes,
                "/usr/bin/duckstation-qt": (
                    # pragma: allowlist nextline secret
                    "24814978c0b8cd8a0b8eea756396c0b0df2067d1fb5adb64a3c5c34fd876c1fe"
                ),
                (
                    "/usr/lib/python3.12/site-packages/configgen/generators/"
                    "duckstation/duckstationGenerator.py"
                    # pragma: allowlist nextline secret
                ): "00751590cabf239f2cdab37e8edcbe3c7460373beda0b4a59fe60cd1a9e32536",
            }.items()
            if path != "/usr/bin/retroarch" and "/libretro/" not in path
        },
    )


@pytest.mark.parametrize("diagnostic", ["none", "no-stream"])
def test_duckstation_observed_exit_accepts_standalone_evidence(
    tmp_path: Path, diagnostic: str
) -> None:
    """Qt/SDL evidence can pass without a libretro core or native keyboard FD."""
    world = DuckstationWorld(FakeClock(), diagnostic)
    coordinator, report = execute(tmp_path, world, native_config=duckstation_config())
    assert report["status"] == "passed"
    assert report["full_frontend_receiver_gate"] is False
    rows = [record(row) for row in sequence(report["cases"])]
    assert len(rows) == 1
    assert rows[0]["name"] == "psx-duckstation"
    assert rows[0]["status"] == "passed"
    assert record(report["counts"])["passed"] == 1
    assert report["emulator_exit_coverage"] != "No emulator exit coverage"
    observed = record(rows[0]["report"])
    backend = record(observed["backend_identity"])
    assert backend["variant"] == "duckstation-qt"
    assert record(backend["reported_version"]) == {
        "argument": "-version",
        "exit_code": 1,
        "output": "DuckStation Version  ()",
        "tag": "",
        "branch": "",
    }
    assert record(backend["package_source"])["version"] == "v0.1-7294"
    assert record(observed["native_device_consumption"])["pad_device"] == [13, 78]
    private = coordinator.artifacts.path / "psx-duckstation-selection.json"
    assert private.stat().st_mode & 0o777 == 0o600
    capture = coordinator.artifacts.path / "psx-duckstation-emulator-before-exit.png"
    assert capture.is_file()
    assert "private-title" not in json.dumps(report)
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert record(rows[0]["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize("condition", ["absence", "missing-bios"])
def test_duckstation_only_media_absence_is_a_nonblocking_skip(
    tmp_path: Path, condition: str
) -> None:
    """A selected disc lacking operator BIOS is a failure, not an empty library."""
    world = DuckstationWorld(FakeClock(), condition)
    _, report = execute(tmp_path, world, native_config=duckstation_config())
    row = record(sequence(report["cases"])[0])
    assert row["name"] == "psx-duckstation"
    assert report["status"] == ("passed" if condition == "absence" else "failed")
    assert row["status"] == ("skipped-no-media" if condition == "absence" else "failed")
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == (
        1 if condition == "absence" else 0
    )
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    observed = record(row["report"])
    assert record(observed["native_device_consumption"])["status"] == "untested"
    if condition == "missing-bios":
        assert record(record(observed["prerequisites"])["bios"])["status"] == "missing"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    "failure",
    [
        "other-backend",
        "other-case",
        "wrong-executable",
        "missing-version",
        "unopened-pad",
        "missing-consumption",
        "pre-chord-death",
        "multiple-pads",
        "configured-index-only",
        "dialog-output",
        "wrong-environment",
    ],
)
def test_duckstation_missing_or_mismatched_backend_evidence_fails(
    tmp_path: Path, failure: str
) -> None:
    """A claimed pass cannot replace the selected stock backend's observations."""
    world = DuckstationWorld(FakeClock(), failure)
    _, report = execute(tmp_path, world, native_config=duckstation_config())
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["name"] == "psx-duckstation"
    assert row["status"] == "failed"
    assert row["report"] is not None
    assert row["isolation"] is not None
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 0
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


class XemuWorld(EmulatorWorld):
    """Model independent SDL3/stock-disk observations, not an Xbox boot claim."""

    def __init__(self, clock: FakeClock, failure: str = "none") -> None:
        """Choose the Xbox outcome and public metadata-only disc-format evidence."""
        super().__init__(clock, failure)
        self.case_name = "xbox-xemu"
        self.selection_entry = "xbox/private-xbox-disc.iso"
        # Public descriptor/extent evidence from the resolved ISO, not the
        # selected archive's suffix, an open CD-ROM FD or rendered BIOS pixels.
        self.disc_format: object = {
            "format": "xdvdfs",
            "sector_size": 2048,
            "volume_offset": 65536,
            "image_size": 73728,
            "root_directory_sector": 34,
            "root_directory_size": 28,
            "media_identity": "1" * 64,
        }

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Observe independent SDL3, stock generator and stock HDD identities."""
        result = super().request(value, timeout)
        if value["action"] == "integrity":
            hashes = record(result["hashes"])
            for path in (
                "/usr/bin/retroarch",
                "/usr/lib/libretro/fceumm_libretro.so",
                "/usr/share/libretro/info/fceumm_libretro.info",
            ):
                del hashes[path]
            hashes.update(
                {
                    "/usr/bin/xemu": "b" * 64,
                    "/usr/lib/libSDL3.so.0.4.2": "c" * 64,
                    (
                        "/usr/lib/python3.12/site-packages/configgen/generators/"
                        "xemu/xemuGenerator.py"
                    ): "5" * 64,
                    (
                        "/usr/lib/python3.12/site-packages/configgen/generators/"
                        "xemu/xemuConfig.py"
                    ): "6" * 64,
                    (
                        "/usr/lib/python3.12/site-packages/configgen/generators/"
                        "xemu/xemuPaths.py"
                    ): "7" * 64,
                    "/usr/share/xemu/data/xbox_hdd.qcow2": (
                        # pragma: allowlist nextline secret
                        "eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed"
                    ),
                }
            )
            result["hashes"] = hashes
        return result

    def evidence(self, request: dict[str, object]) -> dict[str, object]:
        """Publish Xbox-specific input, firmware and disc-format observations."""
        result = super().evidence(request)
        files = record(result["files"])
        if "emulator-probe.json" not in files:
            return result
        report = record(
            json.loads(base64.b64decode(text(files["emulator-probe.json"]))),
        )
        report.update(case="xbox-xemu", system="xbox", backend="xemu", core="xemu")
        if self.failure != "absence":
            self._configure_xemu_inputs(report)
            self._configure_xemu_transition(report)
            files["selection.json"] = base64.b64encode(
                json.dumps(
                    {"schema": 1, "system": "xbox", "entry": self.selection_entry},
                ).encode(),
            ).decode()
            self._damage_xemu(report)
        files["emulator-probe.json"] = base64.b64encode(
            json.dumps(report).encode(),
        ).decode()
        result["files"] = files
        return result

    def _configure_xemu_inputs(self, report: dict[str, object]) -> None:
        """Provide independently pinned executable, firmware and SDL3 inputs."""
        report["backend_identity"] = {
            "variant": "xemu",
            "executable": "/usr/bin/xemu",
            "executable_sha256": "b" * 64,
            # Successful version-helper metadata is independent of launcher logs.
            "reported_version": {
                "argument": "-version",
                "exit_code": 0,
                "disposable_config": True,
                "version": "0.8.134",
                # pragma: allowlist nextline secret
                "revision": "fc9980d2962cbec656253106ea2e121fab1e68d4",
                "date": "Fri May 29 06:08:30 AM UTC 2026",
            },
            "package_source": {
                "version": "v0.8.134",
                # pragma: allowlist nextline secret
                "revision": "fc9980d2962cbec656253106ea2e121fab1e68d4",
                "recipe": (
                    "https://github.com/batocera-linux/batocera.linux/blob/"
                    "155c2d8d304cbb53db52e9479dcf683392821d5c/"
                    "package/batocera/emulators/xemu/xemu.mk"
                ),
            },
        }
        report["prerequisites"] = {
            "mcpx": {
                "status": "available",
                "identity": "d" * 64,
                "readonly": True,
                "path": "/userdata/bios/mcpx_1.0.bin",
            },
            "bios": {
                "status": "available",
                "identity": "e" * 64,
                "readonly": True,
                "path": "/userdata/bios/Complex_4627.bin",
            },
            "hdd": {
                "status": "available",
                "route": "stock",
                "source_identity": (
                    # pragma: allowlist nextline secret
                    "eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed"
                ),
                "source_readonly": True,
                "use_disposition": "unchanged-stock-private-disposable-use",
                "owned_copy": True,
            },
        }
        report["disposable_state"] = {
            "identity_verified": True,
            "production_state_copied": False,
            "hdd": "/userdata/saves/xbox/xbox_hdd.qcow2",
            "eeprom": "/userdata/saves/xbox/xemu_eeprom.bin",
            "config": "/userdata/system/configs/xemu/xemu.toml",
            "saves": "/userdata/saves/xbox",
            "cache": "/userdata/system/cache",
        }
        report["native_device_consumption"] = {
            "status": "passed",
            "input_source": "SDL3",
            "pad_device": [13, 78],
            "opened_devices": [[13, 78]],
            "stock_exit_context": "xemu",
            "sdl_object": {
                "status": "mapped",
                "inventory_path": "/usr/lib/libSDL3.so.0.4.2",
                "sha256": "c" * 64,
            },
            "consumer_topology": {
                "guid": "03" * 16,
                "discovered_gamepads": 1,
                "matching_guid_gamepads": 1,
                "suite_device_matched": True,
            },
            "environment": {
                "sdl_mapping_guid": "03" * 16,
                "suite_mapping_consumed": True,
                "XDG_CONFIG_HOME": "/userdata/system/configs",
                "LC_NUMERIC": "C",
            },
            "generated_mapping": {"input.bindings.port1": "03" * 16},
            "config_path": "/userdata/system/configs/xemu/xemu.toml",
            "configured_files": {
                "flashrom_path": "/userdata/bios/Complex_4627.bin",
                "bootrom_path": "/userdata/bios/mcpx_1.0.bin",
                "hdd_path": "/userdata/saves/xbox/xbox_hdd.qcow2",
                "eeprom_path": "/userdata/saves/xbox/xemu_eeprom.bin",
                "dvd_identity": "1" * 64,
            },
        }

    def _configure_xemu_transition(self, report: dict[str, object]) -> None:
        """Select Xbox process IDs without repairing injected identity failures."""
        transition = record(report["transition"])
        emulator = record(transition["emulator"])
        if emulator["pid"] == 31:
            emulator.update(pid=91, start=9100)
        transition["emulator"] = emulator
        display = record(transition["stock_launch_display"])
        del display["exact_core_loaded"]
        display.update(
            active_pid=91,
            exact_backend_loaded=True,
            selected_disc_open=True,
            render_window=True,
            non_dialog=True,
        )
        if self.disc_format is not None:
            display["disc_format"] = self.disc_format
        transition["stock_launch_display"] = display
        report["transition"] = transition
        if "termination_observation" in report:
            termination = record(report["termination_observation"])
            ended = record(termination["emulator"])
            if ended["pid"] == 31:
                ended.update(pid=91, start=9100)
            termination["emulator"] = ended
            launcher = record(termination["launcher"])
            if launcher["pid"] == 30:
                launcher.update(pid=90, start=9000)
            termination["launcher"] = launcher
            report["termination_observation"] = termination

    def _damage_xemu(self, report: dict[str, object]) -> None:
        """Damage one selected Xbox prerequisite or consumption observation."""
        changes: dict[str, dict[tuple[str, ...], object]] = {
            "wrong-executable": {("backend_identity", "executable_sha256"): "0" * 64},
            "package-version-only": {
                ("backend_identity", "reported_version"): MISSING_OBSERVATION,
            },
            "metadata-helper-failed": {
                ("backend_identity", "reported_version", "exit_code"): 1,
            },
            "wrong-case": {("case",): "psx-duckstation"},
            "unopened-pad": {("native_device_consumption", "opened_devices"): []},
            "sdl2-only": {
                ("native_device_consumption", "sdl_object"): {
                    "status": "mapped",
                    "inventory_path": "/usr/lib/libSDL2-2.0.so.0.3200.8",
                    "sha256": "9" * 64,
                },
            },
            "wrong-port": {
                ("native_device_consumption", "generated_mapping"): {
                    "input.bindings.port1": "04" * 16,
                },
            },
            "wrong-environment": {
                (
                    "native_device_consumption",
                    "environment",
                    "suite_mapping_consumed",
                ): False,
            },
            "wrong-config-path": {
                ("native_device_consumption", "config_path"): (
                    "/userdata/system/configs/xemu/other.toml"
                ),
            },
            "wrong-disc": {
                (
                    "native_device_consumption",
                    "configured_files",
                    "dvd_identity",
                ): "0" * 64,
            },
            "writable-firmware": {("prerequisites", "bios", "readonly"): False},
            "production-hdd": {("disposable_state", "production_state_copied"): True},
            "wrong-hdd-seed": {("prerequisites", "hdd", "source_identity"): "0" * 64},
            "unqualified-hdd": {
                ("prerequisites", "hdd", "use_disposition"): "unqualified",
            },
            "missing-sdl3-guid": {
                (
                    "native_device_consumption",
                    "consumer_topology",
                    "guid",
                ): MISSING_OBSERVATION,
            },
            "ambiguous-sdl3-guid": {
                (
                    "native_device_consumption",
                    "consumer_topology",
                    "matching_guid_gamepads",
                ): 2,
            },
            "boot-failed": {
                ("transition", "stock_launch_display", "rendered_content"): False,
                ("transition", "stock_launch_display", "non_dialog"): False,
            },
            "pre-chord-death": {
                ("transition", "stock_launch_display", "rendered_content"): False,
                ("transition", "stock_launch_display", "non_dialog"): False,
                ("transition", "stock_launch_display", "live"): False,
                ("transition", "live_before_chord_seconds"): 0,
            },
        }
        prerequisite = self.failure.removeprefix("missing-")
        if self.failure.startswith("missing-") and prerequisite in (
            "mcpx",
            "bios",
            "hdd",
        ):
            alter_observations(
                report,
                {("prerequisites", prerequisite): {"status": "missing"}},
            )
        else:
            alter_observations(report, changes.get(self.failure, {}))


def xemu_config() -> NativeConfig:
    """Pin an independent stock inventory, retaining common pad-discovery SDL2."""
    nes = config("nes-smoke")
    return dataclasses.replace(
        nes,
        tier="xbox-smoke",
        hashes={
            path: digest
            for path, digest in {
                **nes.hashes,
                "/usr/bin/xemu": "b" * 64,
                "/usr/lib/libSDL3.so.0.4.2": "c" * 64,
                (
                    "/usr/lib/python3.12/site-packages/configgen/generators/"
                    "xemu/xemuGenerator.py"
                ): "5" * 64,
                (
                    "/usr/lib/python3.12/site-packages/configgen/generators/"
                    "xemu/xemuConfig.py"
                ): "6" * 64,
                (
                    "/usr/lib/python3.12/site-packages/configgen/generators/"
                    "xemu/xemuPaths.py"
                ): "7" * 64,
                "/usr/share/xemu/data/xbox_hdd.qcow2": (
                    # pragma: allowlist nextline secret
                    "eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed"
                ),
            }.items()
            if path != "/usr/bin/retroarch" and "/libretro/" not in path
        },
    )


@pytest.mark.parametrize("diagnostic", ["no-stream", "signaled-log"])
def test_xemu_observed_exit_retains_its_own_standalone_evidence(
    tmp_path: Path, diagnostic: str
) -> None:
    """Diagnostic classification and final keyboard FDs are not Xbox exit gates."""
    world = XemuWorld(FakeClock(), diagnostic)
    coordinator, report = execute(tmp_path, world, native_config=xemu_config())
    assert report["status"] == "passed"
    assert report["full_frontend_receiver_gate"] is False
    rows = [record(row) for row in sequence(report["cases"])]
    assert len(rows) == 1
    assert rows[0]["name"] == "xbox-xemu"
    assert rows[0]["status"] == "passed"
    assert record(report["counts"])["passed"] == 1
    observed = record(rows[0]["report"])
    assert record(record(observed["transition"])["emulator"]) == {
        "pid": 91,
        "start": 9100,
    }
    assert record(record(observed["prerequisites"])["hdd"])["route"] == "stock"
    assert record(observed["native_device_consumption"])["input_source"] == "SDL3"
    assert report["emulator_exit_coverage"] != "No emulator exit coverage"
    assert (coordinator.artifacts.path / "xbox-xemu-emulator-before-exit.png").is_file()
    private = coordinator.artifacts.path / "xbox-xemu-selection.json"
    assert private.stat().st_mode & 0o777 == 0o600
    assert "private-xbox-disc" not in json.dumps(report)
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert record(rows[0]["cleanup"])["state_removed"] is True


def test_xemu_media_absence_is_nonblocking_and_never_exit_coverage(
    tmp_path: Path,
) -> None:
    """Xbox absence stays an untested skip despite complete owned cleanup."""
    world = XemuWorld(FakeClock(), "absence")
    _, report = execute(tmp_path, world, native_config=xemu_config())
    row = record(sequence(report["cases"])[0])
    assert report["status"] == "passed"
    assert row["name"] == "xbox-xemu"
    assert row["status"] == "skipped-no-media"
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 1
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    consumption = record(record(row["report"])["native_device_consumption"])
    assert consumption["status"] == "untested"
    assert record(row["cleanup"])["state_removed"] is True


@pytest.mark.parametrize("extension", [".iso", ".squashfs"])
@pytest.mark.parametrize(
    ("root_sector", "root_size", "image_size"),
    [
        (33, 28, 71680),
        (264, 2048, 544768),
        (47, 4097, 102400),
        (0, 0, 67584),
        (10, 0, 67584),
        (33, 0, 67584),
        (34, 28, 69660),
    ],
)
def test_xemu_xiso_structure_accepts_supported_extents_on_stock_media_routes(
    tmp_path: Path,
    extension: str,
    root_sector: int,
    root_size: int,
    image_size: int,
) -> None:
    """The host accepts public extent evidence without private paths or bytes.

    For stock squashfs this is evidence about its already resolved inner ISO,
    not the compressed archive. This models host validation only, not a mount,
    emulator launch, executable image or successful guest boot.
    """
    world = XemuWorld(FakeClock())
    world.selection_entry = "xbox/private-xbox-disc" + extension
    world.disc_format = {
        **record(world.disc_format),
        "root_directory_sector": root_sector,
        "root_directory_size": root_size,
        "image_size": image_size,
    }
    coordinator, report = execute(tmp_path, world, native_config=xemu_config())
    row = record(sequence(report["cases"])[0])
    assert report["status"] == "passed"
    assert row["status"] == "passed"
    display = record(
        record(record(row["report"])["transition"])["stock_launch_display"]
    )
    assert display["disc_format"] == world.disc_format
    private = coordinator.artifacts.path / "xbox-xemu-selection.json"
    assert json.loads(private.read_text())["entry"] == world.selection_entry
    assert "private-xbox-disc" not in json.dumps(report)
    assert record(row["cleanup"])["state_removed"] is True


@pytest.mark.parametrize("extension", [".iso", ".squashfs"])
@pytest.mark.parametrize(
    "missing",
    [
        "disc_format",
        "format",
        "sector_size",
        "volume_offset",
        "image_size",
        "root_directory_sector",
        "root_directory_size",
        "media_identity",
    ],
)
def test_xemu_xiso_structure_missing_evidence_cannot_pass_or_be_media_absence(
    tmp_path: Path, extension: str, missing: str
) -> None:
    """An open selected CD and render booleans do not establish Xbox format."""
    world = XemuWorld(FakeClock())
    world.selection_entry = "xbox/private-xbox-disc" + extension
    if missing == "disc_format":
        world.disc_format = None
    else:
        evidence = record(world.disc_format)
        del evidence[missing]
        world.disc_format = evidence
    _, report = execute(tmp_path, world, native_config=xemu_config())
    row = record(sequence(report["cases"])[0])
    assert report["status"] == "failed"
    assert row["status"] == "failed"
    observed = record(row["report"])
    display = record(record(observed["transition"])["stock_launch_display"])
    assert all(
        display[key] is True
        for key in (
            "selected_disc_open",
            "render_window",
            "non_dialog",
            "rendered_content",
        )
    )
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 0
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("disc_format", True),
        ("disc_format", {}),
        ("format", "iso9660"),
        ("format", True),
        ("media_identity", "0" * 64),
        ("sector_size", 2352),
        ("sector_size", "2048"),
        ("sector_size", 2048.0),
        ("sector_size", True),
        ("volume_offset", 67584),
        ("volume_offset", True),
        ("volume_offset", 65536.0),
        ("image_size", 67583),
        ("image_size", -1),
        ("image_size", False),
        ("image_size", 73728.0),
        ("root_directory_sector", -1),
        ("root_directory_sector", True),
        ("root_directory_sector", 0x100000000),
        ("root_directory_sector", 34.0),
        ("root_directory_sector", "34"),
        ("root_directory_sector", 36),
        ("root_directory_size", -1),
        ("root_directory_size", True),
        ("root_directory_size", "28"),
        ("root_directory_size", 28.0),
        ("root_directory_size", 0x100000000),
        ("root_directory_size", 4097),
    ],
)
def test_xemu_xiso_structure_invalid_evidence_cannot_pass_or_be_media_absence(
    tmp_path: Path, field: str, value: object
) -> None:
    """Validate format, integer units, supported offset, extent and selection."""
    world = XemuWorld(FakeClock())
    if field == "disc_format":
        world.disc_format = value
    else:
        world.disc_format = {**record(world.disc_format), field: value}
    _, report = execute(tmp_path, world, native_config=xemu_config())
    row = record(sequence(report["cases"])[0])
    assert report["status"] == "failed"
    assert row["status"] == "failed"
    display = record(
        record(record(row["report"])["transition"])["stock_launch_display"]
    )
    assert all(
        display[key] is True
        for key in (
            "selected_disc_open",
            "render_window",
            "non_dialog",
            "rendered_content",
        )
    )
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 0
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    "failure",
    [
        "missing-mcpx",
        "missing-bios",
        "missing-hdd",
        "wrong-executable",
        "package-version-only",
        "metadata-helper-failed",
        "wrong-case",
        "unopened-pad",
        "sdl2-only",
        "wrong-port",
        "wrong-environment",
        "wrong-config-path",
        "wrong-disc",
        "writable-firmware",
        "production-hdd",
        "wrong-hdd-seed",
        "unqualified-hdd",
        "missing-sdl3-guid",
        "ambiguous-sdl3-guid",
        "boot-failed",
        "pre-chord-death",
    ],
)
def test_xemu_eligible_backend_or_prerequisite_failure_cannot_pass_or_skip(
    tmp_path: Path, failure: str
) -> None:
    """A nominal pass must not hide missing Xbox inputs or ineffective stock setup."""
    world = XemuWorld(FakeClock(), failure)
    _, report = execute(tmp_path, world, native_config=xemu_config())
    row = record(sequence(report["cases"])[0])
    assert report["status"] == "failed"
    assert row["name"] == "xbox-xemu"
    assert row["status"] == "failed"
    assert row["report"] is not None
    assert row["isolation"] is not None
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 0
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("tier", "system", "core"),
    [
        ("snes-smoke", "snes", "snes9x"),
        ("megadrive-smoke", "megadrive", "genesisplusgx"),
        ("atari2600-smoke", "atari2600", "stella"),
    ],
)
def test_remaining_libretro_smoke_retains_only_selected_observed_exit(
    tmp_path: Path, tier: str, system: str, core: str
) -> None:
    """A selected backend gets its own accepted evidence, never NES coverage."""
    world = RemainingLibretroWorld(FakeClock(), system, core)
    _, report = execute(tmp_path, world, native_config=remaining_libretro_config(tier))
    assert report["status"] == "passed"
    assert report["full_frontend_receiver_gate"] is False
    rows = [record(row) for row in sequence(report["cases"])]
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == system + "-" + core
    assert row["status"] == "passed"
    assert record(row["report"])["core"] == core
    assert record(report["counts"])["passed"] == 1
    assert report["emulator_exit_coverage"] != "No emulator exit coverage"
    output = tmp_path / "output" / ("1" * 32)
    assert (output / (system + "-" + core + "-emulator-before-exit.png")).is_file()
    assert not (output / "nes-fceumm-emulator-before-exit.png").exists()
    assert "private-title" not in json.dumps(report)
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects.count("create") == 1
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("tier", "system", "core"),
    [
        ("snes-smoke", "snes", "snes9x"),
        ("megadrive-smoke", "megadrive", "genesisplusgx"),
        ("atari2600-smoke", "atari2600", "stella"),
    ],
)
def test_remaining_libretro_absence_never_claims_exit_or_native_consumption(
    tmp_path: Path, tier: str, system: str, core: str
) -> None:
    """Only the selected row skips, without borrowing another core's success."""
    world = RemainingLibretroWorld(FakeClock(), system, core, "absence")
    _, report = execute(tmp_path, world, native_config=remaining_libretro_config(tier))
    assert report["status"] == "passed"
    rows = [record(row) for row in sequence(report["cases"])]
    assert len(rows) == 1
    assert rows[0]["name"] == system + "-" + core
    assert rows[0]["status"] == "skipped-no-media"
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 1
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    observed = record(rows[0]["report"])
    assert record(observed["native_device_consumption"])["status"] == "untested"
    assert record(rows[0]["cleanup"])["state_removed"] is True
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("tier", "system", "core", "failure"),
    [
        ("snes-smoke", "snes", "snes9x", "other-system"),
        ("snes-smoke", "snes", "snes9x", "wrong-case-absence"),
        ("snes-smoke", "snes", "snes9x", "other-backend-core"),
        ("megadrive-smoke", "megadrive", "genesisplusgx", "other-core"),
        ("megadrive-smoke", "megadrive", "genesisplusgx", "other-backend-info"),
        ("atari2600-smoke", "atari2600", "stella", "other-case"),
        ("atari2600-smoke", "atari2600", "stella", "unopened-final"),
        ("snes-smoke", "snes", "snes9x", "launcher-error"),
        ("megadrive-smoke", "megadrive", "genesisplusgx", "cleanup-forced"),
        ("atari2600-smoke", "atari2600", "stella", "no-chord"),
    ],
)
def test_remaining_libretro_eligible_failure_cannot_pass_or_become_media_skip(
    tmp_path: Path, tier: str, system: str, core: str, failure: str
) -> None:
    """Valid receiver/profile evidence cannot repair wrong consumers or exit."""
    world = RemainingLibretroWorld(FakeClock(), system, core, failure)
    _, report = execute(tmp_path, world, native_config=remaining_libretro_config(tier))
    assert report["status"] == "failed"
    row = record(sequence(report["cases"])[0])
    assert row["name"] == system + "-" + core
    assert row["status"] == "failed"
    assert row["report"] is not None
    assert row["isolation"] is not None
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 0
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert "input" in world.effects
    assert record(row["cleanup"])["state_removed"] is True
    assert world.effects.count("create") == 1
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("tier", "case"),
    [
        ("snes-smoke", "snes-snes9x"),
        ("megadrive-smoke", "megadrive-genesisplusgx"),
        ("atari2600-smoke", "atari2600-stella"),
    ],
)
def test_remaining_libretro_plan_is_separate_and_target_independent(
    tier: str,
    case: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real CLI advertises one implemented subset without remote permission."""
    monkeypatch.delenv("BATOCERA_GOW_SSH_TARGET", raising=False)
    assert main(["plan", "--tier", tier]) == 0
    plan = record(json.loads(capsys.readouterr().out))
    assert plan["requested_cases"] == [case]
    assert plan["receiver_checks"] == []
    assert plan["native_effects"] is False


def test_remaining_libretro_refuses_another_system_reproduction_before_run() -> None:
    """A NES selection cannot start a SNES lifecycle or be treated as absence."""
    with pytest.raises(NativeError, match="Reproduction system"):
        dataclasses.replace(
            remaining_libretro_config("snes-smoke"),
            selection={"schema": 1, "system": "nes", "entry": "nes/private-title.nes"},
        )


@pytest.mark.parametrize("diagnostic", ["none", "signaled-log", "no-stream"])
def test_nes_smoke_keeps_native_evidence_and_cleanup_separate(
    tmp_path: Path, diagnostic: str
) -> None:
    """Observed exit passes without log classification or a replacement frontend."""
    world = EmulatorWorld(FakeClock(), diagnostic)
    _, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "passed"
    assert report["full_frontend_receiver_gate"] is False
    assert record(report["counts"])["passed"] == 1
    assert "private-title" not in json.dumps(report)
    assert world.effects.index("release") < world.effects.index("stop_lobby")
    assert world.effects[-1] == "remove_state"


def test_nes_media_absence_is_nonblocking_but_never_exit_coverage(
    tmp_path: Path,
) -> None:
    """NES absence cannot contribute emulator exit coverage."""
    world = EmulatorWorld(FakeClock(), "absence")
    _, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "passed"
    assert record(report["counts"])["passed"] == 0
    assert record(report["counts"])["skipped-no-media"] == 1
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize(
    ("tier", "failure"),
    [
        ("nes-smoke", failure)
        for failure in (
            "wrong-process",
            "forced",
            "receiver-only",
            "no-chord",
            "unreleased-chord",
            "old-assertion",
            "cleanup-forced",
            "cleanup-failed",
            "no-profile-consumption",
            "launcher-error",
            "capture-loss",
            "wrong-asset",
            "wrong-backend",
            "missing-termination",
            "wrong-termination-process",
            "wrong-termination-source",
            "emulator-live",
            "launcher-pending",
            "wrong-launcher",
            "missing-classification",
            "wrong-classifier",
            "unknown-mode",
            "fallback-mode",
            "wrong-sdl",
            "wrong-udev",
        )
    ]
    + [
        (tier, failure)
        for failure in (
            "no-chord",
            "unreleased-chord",
            "no-profile-consumption",
            "launcher-error",
            "emulator-live",
            "wrong-termination-process",
            "cleanup-forced",
            "capture-loss",
        )
        for tier in ("psx-smoke", "xbox-smoke")
    ],
)
def test_incomplete_emulator_evidence_fails_and_still_cleans_owned_state(
    tmp_path: Path, tier: str, failure: str
) -> None:
    """Each backend rejects incomplete evidence while retaining owned cleanup."""
    world: EmulatorWorld
    if tier == "nes-smoke":
        world = EmulatorWorld(FakeClock(), failure)
        selected_config = config("nes-smoke")
    elif tier == "psx-smoke":
        world = DuckstationWorld(FakeClock(), failure)
        selected_config = duckstation_config()
    else:
        world = XemuWorld(FakeClock(), failure)
        selected_config = xemu_config()
    _, report = execute(
        tmp_path,
        world,
        native_config=selected_config,
    )
    assert report["status"] == "failed"
    assert record(report["counts"])["passed"] == 0
    case = record(sequence(report["cases"])[0])
    assert case["isolation"] is not None
    assert case["report"] is not None
    assert "input" in world.effects
    assert world.effects[-1] == "remove_state"


@pytest.mark.parametrize("mismatch", ["changed", "missing", "additional"])
def test_nes_integrity_mismatch_prevents_selection_seed_and_input(
    tmp_path: Path, mismatch: str
) -> None:
    """Independent file observations must reject incompatible expected inventory."""
    world = EmulatorWorld(FakeClock())
    world.reproducing = True
    configuration = config("nes-smoke")
    hashes = dict(configuration.hashes)
    if mismatch == "changed":
        hashes["/usr/bin/retroarch"] = "e" * 64
    elif mismatch == "missing":
        del hashes["/opt/gow-full-x86/suite-es-input.cfg"]
    else:
        hashes["/opt/gow-full-x86/unobserved.py"] = "e" * 64
    configuration = dataclasses.replace(
        configuration,
        hashes=hashes,
        selection={"schema": 1, "system": "nes", "entry": "nes/private-title.nes"},
    )
    _, report = execute(tmp_path, world, native_config=configuration)
    assert report["status"] == "failed"
    case = record(sequence(report["cases"])[0])
    assert case["isolation"] is None
    assert case["report"] is None
    assert "reproduction" not in world.effects
    assert "input" not in world.effects
    assert world.effects[-1] == "remove_state"


def test_media_mount_failure_prevents_eligibility_and_input(tmp_path: Path) -> None:
    """Writable content mounts prevent eligibility checks and native input."""
    world = EmulatorWorld(FakeClock(), "writable-media")
    _, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "failed"
    assert "input" not in world.effects
    assert world.effects[-1] == "remove_state"


def test_reproduction_is_seeded_only_after_inspection_and_before_input(
    tmp_path: Path,
) -> None:
    """Reproduction is inspected before seeding and seeded before input leases."""
    world = EmulatorWorld(FakeClock())
    world.reproducing = True
    configuration = dataclasses.replace(
        config("nes-smoke"),
        selection={"schema": 1, "system": "nes", "entry": "nes/private-title.nes"},
    )
    _, report = execute(tmp_path, world, native_config=configuration)
    assert report["status"] == "passed"
    actions = [request["action"] for request in world.requests]
    assert actions.index("integrity") < actions.index("seed_selection")
    assert world.effects.index("reproduction") < world.effects.index("input")


def test_private_reproduction_reader_preserves_only_the_owned_record(
    tmp_path: Path,
) -> None:
    """An owner-only reproduction record survives reading without extra fields."""
    tmp_path.chmod(0o700)
    path = tmp_path / "selection.json"
    document = {"schema": 1, "system": "nes", "entry": "nes/private-title.nes"}
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    assert read_reproduction_record(path) == document


@pytest.mark.parametrize(
    "failure", ["symlink", "public-file", "public-parent", "oversize", "special"]
)
def test_private_reproduction_reader_refuses_unsafe_files(
    tmp_path: Path, failure: str
) -> None:
    """Unsafe reproduction files cannot supply authority for a selected run."""
    tmp_path.chmod(0o700)
    path = tmp_path / "selection.json"
    path.write_text('{"schema":1,"system":"nes"}')
    path.chmod(0o600)
    if failure == "symlink":
        target = tmp_path / "target.json"
        path.rename(target)
        path.symlink_to(target)
    elif failure == "public-file":
        path.chmod(0o644)
    elif failure == "public-parent":
        tmp_path.chmod(0o755)
    elif failure == "oversize":
        path.write_bytes(b" " * (1024 * 1024 + 1))
    else:
        path.unlink()
        os.mkfifo(path, 0o600)
    with pytest.raises((NativeError, OSError)):
        read_reproduction_record(path)


def test_failed_probe_keeps_already_published_private_selection(tmp_path: Path) -> None:
    """Final probe loss does not discard the already published private selection."""
    world = EmulatorWorld(FakeClock(), "report-loss")
    coordinator, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "failed"
    assert world.effects[-1] == "remove_state"
    private = coordinator.artifacts.path / "nes-fceumm-selection.json"
    assert record(json.loads(private.read_text()))["entry"] == "nes/private-title.nes"
    assert private.stat().st_mode & 0o777 == 0o600
    assert "private-title" not in json.dumps(report)


class FilesystemEmulatorWorld(EmulatorWorld):
    """Collect real atomic publications through the helper before real removal."""

    def __init__(self, root: Path, report_failure: str) -> None:
        """Stage atomic filesystem evidence for a controlled final-report failure."""
        super().__init__(FakeClock())
        self.root, self.report_failure = root, report_failure
        self.state: OwnedState | None = None
        self.published = False

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Use actual helper collection and owned removal around modeled input."""
        action = value["action"]
        if action == "collect":
            # Docker attribution has its separate delivered-helper seam above.
            # This fixture owns filesystem collection, not a native Docker host.
            return Operations(
                dict(value, host_root=str(self.root), observe_incomplete=False)
            ).dispatch()
        result = super().request(value, timeout)
        if action == "allocate":
            self.state = OwnedState(
                self.root,
                text(value["case_id"]),
                text(value["token"]),
                os.getuid(),
                os.getgid(),
            )
            pin = self.state.allocate()
            diagnostics.publish_json(
                self.state.path / ".native-evidence/startup.json",
                {"uid": 1000, "gid": 1000},
            )
            return {"pin": pin}
        if action == "lease" and not self.published:
            assert self.state is not None
            directory = self.state.path / ".native-evidence"
            diagnostics.publish_bytes(
                directory / "emulator-before-exit.png", fixture_png()
            )
            diagnostics.publish_bytes(directory / "emulator-failure.png", fixture_png())
            diagnostics.publish_selected_log(directory, ["owned failure observation"])
            diagnostics.publish_json(
                directory / "emulator-chord-released.json",
                {
                    "status": "incomplete",
                    "boundary": "chord-released",
                    "observations": {"chord": {"pressed": True, "released": True}},
                },
            )
            diagnostics.publish_json(
                directory / "selection.json",
                {"schema": 1, "system": "nes", "entry": "nes/private-title.nes"},
            )
            # A killed encoder leaves only the nonpublished name. Arbitrary
            # owned files are not selected evidence, even if they are valid PNGs.
            (directory / "emulator-failure.png.partial").write_bytes(fixture_png()[:30])
            (directory / "render-sample.png").write_bytes(fixture_png())
            if self.report_failure == "malformed":
                diagnostics.publish_bytes(directory / "emulator-probe.json", b"{broken")
            elif self.report_failure in ("symlink", "hardlink", "public", "fifo"):
                capture = directory / "emulator-failure.png"
                capture.unlink()
                foreign = self.root / "foreign.png"
                foreign.write_bytes(fixture_png())
                foreign.chmod(0o600)
                if self.report_failure == "symlink":
                    capture.symlink_to(foreign)
                elif self.report_failure == "hardlink":
                    os.link(foreign, capture)
                elif self.report_failure == "fifo":
                    os.mkfifo(capture, 0o600)
                else:
                    capture.write_bytes(fixture_png())
                    capture.chmod(0o644)
            self.published = True
        elif action == "remove_state":
            assert self.state is not None
            self.state.remove(record(value["pin"]))
        return result


@pytest.mark.parametrize("report_failure", ["missing", "malformed"])
def test_complete_failure_captures_survive_missing_report_and_real_owned_cleanup(
    tmp_path: Path, report_failure: str
) -> None:
    """Neither report loss nor JSON failure discards other complete evidence."""
    world = FilesystemEmulatorWorld(tmp_path, report_failure)
    coordinator, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "failed"
    assert record(report["counts"])["passed"] == 0
    case = record(sequence(report["cases"])[0])
    assert case["isolation"] is not None
    assert case["report"] is None
    assert record(case["cleanup"])["status"] == "passed"
    assert world.state is not None
    assert not world.state.path.exists()
    assert world.effects[-1] == "remove_state"
    output = coordinator.artifacts.path
    for name in ("emulator-before-exit.png", "emulator-failure.png"):
        path = output / ("nes-fceumm-" + name)
        assert path.read_bytes() == fixture_png()
        assert path.stat().st_mode & 0o777 == 0o600
    assert (output / "nes-fceumm-selection.json").is_file()
    boundary = output / "nes-fceumm-emulator-chord-released.json"
    assert record(json.loads(boundary.read_text(encoding="utf-8")))["status"] == (
        "incomplete"
    )
    assert boundary.stat().st_mode & 0o777 == 0o600
    assert not any(
        ".partial" in path.name or "render-sample" in path.name
        for path in output.iterdir()
    )


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "public", "fifo"])
def test_unsafe_capture_is_not_read_and_does_not_discard_safe_owned_evidence(
    tmp_path: Path, unsafe: str
) -> None:
    """An unsafe capture is refused without losing other complete owned evidence."""
    world = FilesystemEmulatorWorld(tmp_path, unsafe)
    coordinator, report = execute(tmp_path, world, tier="nes-smoke")
    assert report["status"] == "failed"
    case = record(sequence(report["cases"])[0])
    assert any(
        "Selected evidence unavailable" in text(error)
        for error in sequence(case["errors"])
    )
    assert record(case["cleanup"])["status"] == "passed"
    assert world.state is not None
    assert not world.state.path.exists()
    assert (tmp_path / "foreign.png").read_bytes() == fixture_png()
    output = coordinator.artifacts.path
    assert (
        output / "nes-fceumm-emulator-before-exit.png"
    ).read_bytes() == fixture_png()
    assert not (output / "nes-fceumm-emulator-failure.png").exists()


@pytest.mark.parametrize("renderer", ["OpenGL", "Vulkan"])
@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "wrong-renderer",
        "missing-active-renderer",
        "wrong-active-renderer",
        "wrong-renderer-pid",
        "wrong-visual",
        "wrong-discovery",
    ],
)
def test_duckstation_variants_require_their_own_active_mode_and_correction(
    tmp_path: Path,
    renderer: str,
    failure: str,
) -> None:
    """Each renderer needs its own active mode and applicable visual correction."""
    world = DuckstationWorld(FakeClock(), failure, renderer)
    native_config = dataclasses.replace(
        duckstation_config(),
        tier="psx-vulkan-smoke" if renderer == "Vulkan" else "psx-smoke",
    )
    coordinator, report = execute(tmp_path, world, native_config=native_config)
    row = record(sequence(report["cases"])[0])
    assert report["status"] == ("passed" if failure == "none" else "failed")
    assert row["name"] == (
        "psx-duckstation-vulkan" if renderer == "Vulkan" else "psx-duckstation"
    )
    assert row["status"] == ("passed" if failure == "none" else "failed")
    assert record(row["cleanup"])["status"] == "passed"
    assert world.effects[-1] == "remove_state"
    assert (
        coordinator.artifacts.path / (str(row["name"]) + "-selection.json")
    ).is_file()


def test_full_matrix_keeps_absent_media_separate_from_failed_run_evidence() -> None:
    """Six absent backends can pass eligibility, never failed evidence or coverage."""
    rows: list[dict[str, object]] = [
        {"name": "frontend", "status": "passed"},
        {"name": "receivers", "status": "passed"},
    ]
    rows.extend(
        {
            "name": name,
            "status": "skipped-no-media",
            "reason": "Skipped: no compatible mounted media",
        }
        for name in (
            "nes-fceumm",
            "snes-snes9x",
            "megadrive-genesisplusgx",
            "atari2600-stella",
            "psx-duckstation",
            "psx-duckstation-vulkan",
            "xbox-xemu",
        )
    )
    receivers: list[dict[str, object]] = [
        {"name": name, "status": "passed"} for name in RECEIVER_CASES
    ]
    result = native_matrix.aggregate_regression(
        rows, receivers, evidence_complete=False, cleanup_complete=True
    )
    assert result["status"] == "failed"
    assert result["emulator_exit_coverage"] == "No emulator exit coverage"
    assert result["backend_counts"] == {
        "passed": 0,
        "failed": 0,
        "skipped-no-media": 6,
        "blocked": 0,
        "interrupted": 0,
        "not-run": 0,
    }
    assert len(sequence(result["regression_matrix"])) == 6
    assert record(result["counts"])["passed"] == 2


def matrix_config(tier: str = "regression") -> NativeConfig:
    """Combine independent installed-inventory fixtures without native claims."""
    return dataclasses.replace(
        config("nes-smoke"),
        tier=tier,
        hashes={
            **remaining_libretro_config("snes-smoke").hashes,
            **duckstation_config().hashes,
            **xemu_config().hashes,
        },
    )


class MatrixWorld(World):
    """Run existing lifecycle/behavior models as separate sequential owners."""

    def __init__(
        self,
        *,
        absent: bool = False,
        fail_case: str = "",
        unsafe_cleanup: bool = False,
        changed_qualified_input: bool = False,
        cleanup_failure_case: str = "",
    ) -> None:
        """Select independent case owners and optional lifecycle-failure controls."""
        super().__init__(FakeClock())
        self.current: World | None = None
        self.absent = absent
        self.fail_case = fail_case
        self.unsafe_cleanup = unsafe_cleanup
        self.cleanup_failure_case = cleanup_failure_case
        self.changed_qualified_input = changed_qualified_input
        self.allocations: list[str] = []
        self.removals: list[str] = []

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Dispatch sequential modeled owners without sharing owned case state."""
        action = text(value["action"])
        if action == "allocate":
            self._allocate_case(value)
        if action == "create" and isinstance(self.current, EmulatorWorld):
            runner = record(record(value["payload"])["runner"])
            self.current.reproducing = "GOW_EMULATOR_REPRODUCE=1" in sequence(
                runner["env"]
            )
        if action == "verify_qualified":
            assert self.current is not None
            assert not self.current.leased
            self.effects.append("qualified-input-check")
            self.requests.append(value)
            return {"matched": not self.changed_qualified_input}
        result = (
            self.current.request(value, timeout)
            if self.current is not None
            else super().request(value, timeout)
        )
        if action == "integrity":
            result["hashes"] = matrix_config().hashes
        if action == "remove_state":
            self.removals.append(self.allocations[-1])
        if action == "collect":
            files = record(result["files"])
            if "selection.json" in files and "emulator-probe.json" in files:
                probe = record(
                    json.loads(base64.b64decode(text(files["emulator-probe.json"])))
                )
                selection = record(
                    json.loads(base64.b64decode(text(files["selection.json"])))
                )
                selection["digest"] = record(probe["media"])["identity"]
                selection["members"] = [["private-title", "1" * 64, 1]]
                files["selection.json"] = base64.b64encode(
                    json.dumps(selection).encode()
                ).decode()
                result["files"] = files
        return result

    def _allocate_case(self, value: dict[str, object]) -> None:
        """Create a case-specific owner only after the prior owner was removed."""
        assert len(self.allocations) == len(self.removals), (
            "previous owner still exists"
        )
        name = text(value["case_id"])[33:]
        self.allocations.append(name)
        failure = (
            "wrong-process"
            if name == self.fail_case
            else "absence"
            if self.absent
            else "none"
        )
        if name == "nes-fceumm":
            self.current = EmulatorWorld(self.clock, failure)
        elif name.startswith(("snes-", "megadrive-", "atari2600-")):
            system, core = name.split("-", 1)
            self.current = RemainingLibretroWorld(self.clock, system, core, failure)
        elif name.startswith("psx-"):
            self.current = DuckstationWorld(
                self.clock,
                failure,
                "Vulkan" if name.endswith("-vulkan") else "OpenGL",
            )
        elif name == "xbox-xemu":
            self.current = XemuWorld(self.clock, failure)
        else:
            self.current = World(self.clock)
        self.current.effects = self.effects
        self.current.requests = self.requests
        if self.unsafe_cleanup or name == self.cleanup_failure_case:
            self.current.fail_stop = True


def passing_matrix_rows() -> list[dict[str, object]]:
    """Supply validated dispositions at the approved aggregation seam."""
    return [
        {"name": name, "status": "passed"}
        for name in (
            "frontend",
            "receivers",
            *(case.identifier for case in EMULATOR_CASES),
        )
    ]


@pytest.mark.parametrize(
    "missing", ["frontend", "receivers", *(case.identifier for case in EMULATOR_CASES)]
)
def test_regression_cannot_pass_a_missing_required_case(missing: str) -> None:
    """A missing Vulkan result cannot be supplied by OpenGL or another backend."""
    result = native_matrix.aggregate_regression(
        [row for row in passing_matrix_rows() if row["name"] != missing],
        [{"name": name, "status": "passed"} for name in RECEIVER_CASES],
        evidence_complete=True,
        cleanup_complete=True,
    )
    assert result["status"] == "failed"
    assert record(result["counts"])["not-run"] == 1
    assert result["full_regression_gate"] is False


@pytest.mark.parametrize(
    "outcome", ["failed", "blocked", "interrupted", "not-run", "unknown"]
)
def test_regression_preserves_nonpassing_backend_dispositions(outcome: str) -> None:
    """Nominal passing neighbors do not hide an independently failed variant."""
    rows = passing_matrix_rows()
    rows[-2]["status"] = outcome
    result = native_matrix.aggregate_regression(
        rows,
        [{"name": name, "status": "passed"} for name in RECEIVER_CASES],
        evidence_complete=True,
        cleanup_complete=True,
    )
    assert result["status"] == "failed"
    duck = record(sequence(result["regression_matrix"])[4])
    assert duck["status"] != "passed"
    assert record(sequence(duck["variants"])[1])["status"] == outcome


@pytest.mark.parametrize(
    "failure",
    ["duplicate", "receiver", "evidence", "cleanup", "interruption", "false-skip"],
)
def test_regression_run_level_and_assertion_failures_veto_success(failure: str) -> None:
    """Behavior counts cannot override independent report, isolation or cleanup loss."""
    rows = passing_matrix_rows()
    receivers: list[dict[str, object]] = [
        {"name": name, "status": "passed"} for name in RECEIVER_CASES
    ]
    if failure == "duplicate":
        rows.append(dict(rows[-1]))
    if failure == "receiver":
        receivers.pop()
    if failure == "false-skip":
        rows[-1]["status"] = "skipped-no-media"
        rows[-1]["reason"] = "Eligible input failed to launch"
    result = native_matrix.aggregate_regression(
        rows,
        receivers,
        evidence_complete=failure != "evidence",
        cleanup_complete=failure != "cleanup",
        interrupted=failure == "interruption",
    )
    assert result["status"] == "failed"
    assert result["full_regression_gate"] is False


def test_full_regression_runs_all_owners_and_honest_zero_media_coverage(
    tmp_path: Path,
) -> None:
    """All seven actual media absences are nonblocking, never passing exit proof."""
    world = MatrixWorld(absent=True)
    _, report = execute(tmp_path, world, native_config=matrix_config())
    assert report["status"] == "passed"
    assert report["full_regression_gate"] is True
    assert report["full_frontend_receiver_gate"] is True
    assert len(sequence(report["regression_matrix"])) == 6
    assert record(report["counts"])["passed"] == 2
    assert record(report["counts"])["skipped-no-media"] == 7
    assert record(report["backend_counts"])["skipped-no-media"] == 6
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    assert (
        world.allocations
        == world.removals
        == ["frontend", "receivers", *(case.identifier for case in EMULATOR_CASES)]
    )
    assert len(sequence(report["receiver_checks"])) == 5


def test_full_regression_cleanup_barrier_preserves_all_unrun_rows(
    tmp_path: Path,
) -> None:
    """A failed owned stop prevents the next allocation and cannot produce a gate."""
    world = MatrixWorld(absent=True, unsafe_cleanup=True)
    _, report = execute(tmp_path, world, native_config=matrix_config())
    assert report["status"] == "failed"
    assert report["full_regression_gate"] is False
    assert report["cleanup_complete"] is False
    assert world.allocations == ["frontend"]
    assert record(report["counts"])["not-run"] == 8
    assert len(sequence(report["regression_matrix"])) == 6


def test_expanded_exposes_all_advertised_gaps_without_promoting_templates(
    tmp_path: Path,
) -> None:
    """No exact proof means no emulator allocation, including requested RPCS3."""
    configuration = dataclasses.replace(
        matrix_config("expanded"), expanded_selection=("ps3-rpcs3",)
    )
    world = MatrixWorld()
    _, report = execute(tmp_path, world, native_config=configuration)
    assert report["status"] == "passed"
    assert report["full_regression_gate"] is False
    assert world.allocations == ["frontend", "receivers"]
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    coverage = record(report["coverage"])
    assert len(sequence(coverage["systems"])) == 253
    mappings = [record(row) for row in sequence(coverage["mappings"])]
    assert len(mappings) == 477
    assert all(
        row["status"] in ("unqualified", "no-executable-definition") for row in mappings
    )
    assert {
        row["backend"] for row in mappings if row["system"] in ("ps3", "xbox360")
    } >= {"rpcs3", "xenia", "xenia-canary"}


@pytest.mark.parametrize(
    "change", ["none", "evidence", "image", "firmware", "profile", "media"]
)
def test_expanded_qualification_revalidates_retained_exact_inputs(
    tmp_path: Path, change: str
) -> None:
    """Real coordinator artifacts are required, not a hand-written qualified flag."""
    world = MatrixWorld()
    configuration = dataclasses.replace(matrix_config(), tier="nes-smoke")
    first, report = execute(tmp_path / "first", world, native_config=configuration)
    assert report["status"] == "passed"
    proof_path = first.artifacts.path / "nes-fceumm-qualification.json"
    if change == "evidence":
        (first.artifacts.path / "nes-fceumm-emulator-before-exit.png").unlink()
    elif change != "none":
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["qualification"]["identity"][change] = "different-input"
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
    artifacts = Artifacts(tmp_path / "next", "2" * 32)
    try:
        target = Coordinator(
            matrix_config("expanded"), MatrixWorld(), FakeClock(), artifacts, "2" * 32
        )
        if change != "none":
            with pytest.raises((NativeError, OSError, ValueError)):
                target.load_qualification(proof_path)
        else:
            qualified = target.load_qualification(proof_path)
            assert qualified.identity.case == "nes-fceumm"
            assert qualified.selection["digest"] == qualified.identity.media
    finally:
        artifacts.close()


class SelectedEnvironmentWorld(MatrixWorld):
    """Supply required selected consumer fields beside nonsecret privacy controls."""

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Add privacy controls beside the selected standalone input environment."""
        result = super().request(value, timeout)
        if value["action"] == "collect":
            files = record(result["files"])
            if "emulator-probe.json" in files:
                probe = record(
                    json.loads(base64.b64decode(text(files["emulator-probe.json"])))
                )
                consumption = record(probe["native_device_consumption"])
                environment = record(consumption["environment"])
                environment["UNSELECTED_PRIVATE_VALUE"] = (
                    "synthetic-replay-private-marker"
                )
                consumption["environment"] = environment
                probe["native_device_consumption"] = consumption
                probe["argv"] = ["synthetic-replay-private-marker"]
                probe["wrapper"] = {"data": "synthetic-replay-private-marker"}
                probe["authorization"] = "synthetic-replay-private-marker"
                files["emulator-probe.json"] = base64.b64encode(
                    json.dumps(probe).encode()
                ).decode()
                result["files"] = files
        return result


@pytest.mark.parametrize(
    ("case_name", "tier"),
    [
        ("psx-duckstation", "psx-smoke"),
        ("psx-duckstation-vulkan", "psx-vulkan-smoke"),
        ("xbox-xemu", "xbox-smoke"),
    ],
)
def test_expanded_standalone_round_trip_preserves_selected_environment(
    tmp_path: Path, case_name: str, tier: str
) -> None:
    """Serialized private proof replays real SDL fields without retaining secrets."""
    first, report = execute(
        tmp_path / "first",
        SelectedEnvironmentWorld(),
        native_config=matrix_config(tier),
    )
    assert report["status"] == "passed"
    proof_path = first.artifacts.path / (case_name + "-qualification.json")
    artifacts = Artifacts(tmp_path / "next", "2" * 32)
    world = MatrixWorld()
    target = Coordinator(
        matrix_config("expanded"), world, world.clock, artifacts, "2" * 32
    )
    try:
        qualified = target.load_qualification(proof_path)
        summary = record(sequence(report["cases"])[0])["report"]
        assert "environment" not in record(record(summary)["native_device_consumption"])
        selected = record(qualified.probe["native_device_consumption"])
        environment = record(selected["environment"])
        assert environment["sdl_mapping_guid"] == "03" * 16
        assert environment["suite_mapping_consumed"] is True
        assert environment["XDG_CONFIG_HOME"] == "/userdata/system/configs"
        if case_name == "xbox-xemu":
            assert environment["LC_NUMERIC"] == "C"
        else:
            assert environment["SDL_JOYSTICK_HIDAPI"] == "0"
        proof = record(json.loads(proof_path.read_text(encoding="utf-8")))
        assert (
            dataclasses.asdict(qualified.identity)
            == record(proof["qualification"])["identity"]
        )
        assert qualified.selection["digest"] == qualified.identity.media
        for path in first.artifacts.path.iterdir():
            assert b"synthetic-replay-private-marker" not in path.read_bytes()
        target.config = dataclasses.replace(
            target.config, qualified_inputs={case_name: qualified}
        )
        result = target.run()
    finally:
        artifacts.close()
    assert result["status"] == "passed"
    assert world.allocations == world.removals == ["frontend", "receivers", case_name]
    assert world.effects.count("qualified-input-check") == 1
    assert record(result["counts"])["passed"] == 3


@pytest.mark.parametrize("tier", ["psx-smoke", "psx-vulkan-smoke", "xbox-smoke"])
def test_standalone_invalid_selected_environment_is_not_persisted_as_private_data(
    tmp_path: Path, tier: str
) -> None:
    """Known field names do not permit arbitrary values into retained evidence."""

    class InvalidEnvironmentWorld(SelectedEnvironmentWorld):
        def request(
            self, value: dict[str, object], timeout: float
        ) -> dict[str, object]:
            result = super().request(value, timeout)
            files = record(result.get("files", {}))
            if "emulator-probe.json" in files:
                probe = record(
                    json.loads(base64.b64decode(text(files["emulator-probe.json"])))
                )
                consumption = record(probe["native_device_consumption"])
                environment = record(consumption["environment"])
                consumption["environment"] = dict.fromkeys(
                    environment, "synthetic-replay-private-marker"
                )
                probe["native_device_consumption"] = consumption
                files["emulator-probe.json"] = base64.b64encode(
                    json.dumps(probe).encode()
                ).decode()
                result["files"] = files
            return result

    first, report = execute(
        tmp_path, InvalidEnvironmentWorld(), native_config=matrix_config(tier)
    )
    assert report["status"] == "failed"
    assert record(sequence(report["cases"])[0])["status"] == "failed"
    assert not list(first.artifacts.path.glob("*-qualification.json"))
    for path in first.artifacts.path.iterdir():
        assert b"synthetic-replay-private-marker" not in path.read_bytes()


@pytest.mark.parametrize(
    ("case_name", "tier"),
    [
        ("psx-duckstation", "psx-smoke"),
        ("psx-duckstation-vulkan", "psx-vulkan-smoke"),
        ("xbox-xemu", "xbox-smoke"),
    ],
)
@pytest.mark.parametrize(
    "damage",
    [
        "unlisted",
        "missing",
        "corrupt",
        "malformed",
        "wrong-case",
        "summary-mismatch",
        "lossy-environment",
        "invalid-environment",
        "stale-identity",
    ],
)
def test_expanded_standalone_incomplete_or_inconsistent_proof_refuses_before_transport(
    tmp_path: Path, case_name: str, tier: str, damage: str
) -> None:
    """Even rehashed synthetic proof cannot replace missing native observations."""
    first, report = execute(
        tmp_path / "first", MatrixWorld(), native_config=matrix_config(tier)
    )
    assert report["status"] == "passed"
    directory = first.artifacts.path
    proof_path = directory / (case_name + "-qualification.json")
    report_path = directory / "report.json"
    capture_name = case_name + "-emulator-probe.json"
    capture_path = directory / capture_name
    persisted = record(json.loads(report_path.read_bytes()))
    row = record(sequence(persisted["cases"])[0])
    damage_replay_evidence(row, capture_path, damage)
    persisted["cases"] = [row]
    report_bytes = json.dumps(persisted).encode()
    report_path.write_bytes(report_bytes)
    proof = record(json.loads(proof_path.read_bytes()))
    proof["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    proof_path.write_text(json.dumps(proof), encoding="utf-8")
    artifacts = Artifacts(tmp_path / "next", "2" * 32)
    world = MatrixWorld()
    target = Coordinator(
        matrix_config("expanded"), world, world.clock, artifacts, "2" * 32
    )
    try:
        with pytest.raises((NativeError, OSError, ValueError)) as failure:
            target.load_qualification(proof_path)
        if damage == "lossy-environment":
            assert "selected native-consumption environment" in str(failure.value)
        assert world.requests == []
        assert world.allocations == []
        assert world.effects == []
    finally:
        artifacts.close()


def damage_replay_evidence(
    row: dict[str, object],
    capture_path: Path,
    damage: str,
) -> None:
    """Damage retained proof while keeping each independent failure observable.

    Args:
        row: Mutable case summary from a real modeled coordinator run.
        capture_path: Persisted complete probe artifact for that case.
        damage: Selected absence, corruption or inconsistent observation scenario.
    """
    captures = record(row["captures"])
    probe = record(json.loads(capture_path.read_bytes()))
    if damage == "unlisted":
        del captures[capture_path.name]
    elif damage == "missing":
        capture_path.unlink()
    elif damage == "corrupt":
        capture_path.write_bytes(b"changed after publication")
    else:
        changes: dict[str, dict[tuple[str, ...], object]] = {
            "wrong-case": {("case",): "nes-fceumm"},
            "lossy-environment": {
                ("native_device_consumption", "environment"): MISSING_OBSERVATION,
            },
            "invalid-environment": {
                (
                    "native_device_consumption",
                    "environment",
                    "suite_mapping_consumed",
                ): False,
            },
            "stale-identity": {("profile", "sha256"): "f" * 64},
        }
        alter_observations(probe, changes.get(damage, {}))
        if damage == "summary-mismatch":
            alter_observations(
                row,
                {("report", "negative_control"): "withheld-chord"},
            )
        elif damage == "stale-identity":
            row["report"] = sanitize(probe)
        data = b"{incomplete" if damage == "malformed" else json.dumps(probe).encode()
        capture_path.write_bytes(data)
        captures[capture_path.name] = hashlib.sha256(data).hexdigest()
    row["captures"] = captures


def test_expanded_changed_current_input_never_opens_emulator_lease(
    tmp_path: Path,
) -> None:
    """A stale mounted input fails before assertion input but still owns cleanup."""
    first, report = execute(
        tmp_path / "first",
        MatrixWorld(),
        native_config=dataclasses.replace(matrix_config(), tier="nes-smoke"),
    )
    assert report["status"] == "passed"
    artifacts = Artifacts(tmp_path / "next", "2" * 32)
    world = MatrixWorld(changed_qualified_input=True)
    target = Coordinator(
        matrix_config("expanded"), world, world.clock, artifacts, "2" * 32
    )
    try:
        qualified = target.load_qualification(
            first.artifacts.path / "nes-fceumm-qualification.json"
        )
        target.config = dataclasses.replace(
            target.config, qualified_inputs={"nes-fceumm": qualified}
        )
        result = target.run()
    finally:
        artifacts.close()
    assert result["status"] == "failed"
    assert (
        world.allocations == world.removals == ["frontend", "receivers", "nes-fceumm"]
    )
    assert world.effects.count("input") == 2
    assert world.effects.count("qualified-input-check") == 1
    assert record(sequence(result["cases"])[-1])["status"] == "failed"


def test_full_regression_failed_eligible_case_is_not_an_absence_skip(
    tmp_path: Path,
) -> None:
    """Wrong pinned processes veto the gate even when later rows clean up safely."""
    world = MatrixWorld(absent=True, fail_case="nes-fceumm")
    _, report = execute(tmp_path, world, native_config=matrix_config())
    assert report["status"] == "failed"
    assert report["full_regression_gate"] is False
    nes = next(
        record(row)
        for row in sequence(report["cases"])
        if record(row)["name"] == "nes-fceumm"
    )
    assert nes["status"] == "failed"
    assert record(nes["report"])["status"] == "passed"
    assert record(record(nes["report"])["transition"])["emulator"] == {
        "pid": -1,
        "start": 3100,
    }
    assert record(nes["cleanup"])["status"] == "passed"
    assert len(world.allocations) == len(world.removals) == 9
    assert record(report["backend_counts"])["failed"] == 1
    assert record(report["backend_counts"])["skipped-no-media"] == 5
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"


def test_full_regression_requires_seven_independent_exit_variants(
    tmp_path: Path,
) -> None:
    """All seven validated exits retain reusable private proofs, never six variants."""
    world = MatrixWorld()
    coordinator, report = execute(tmp_path, world, native_config=matrix_config())
    assert report["status"] == "passed"
    assert report["full_regression_gate"] is True
    assert record(report["counts"])["passed"] == 9
    assert record(report["backend_counts"])["passed"] == 6
    assert len(sequence(report["emulator_exit_cases"])) == 7
    for case in EMULATOR_CASES:
        path = coordinator.artifacts.path / (case.identifier + "-qualification.json")
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        proof = record(json.loads(path.read_text(encoding="utf-8")))
        assert record(proof["qualification"])["status"] == "qualified"
        assert (
            proof["report_sha256"]
            == hashlib.sha256(
                (coordinator.artifacts.path / "report.json").read_bytes()
            ).hexdigest()
        )
        observations = record(proof["observations"])
        assert observations["native_device_consumed"] is True
        assert observations["cleanup_complete"] is True
        assert observations["evidence_retained"] is True
    assert world.allocations == world.removals


def test_expanded_executes_only_current_qualified_replay_and_retains_gaps(
    tmp_path: Path,
) -> None:
    """An exact NES proof never authorizes RPCS3 or any other current definition."""
    first, report = execute(
        tmp_path / "first",
        MatrixWorld(),
        native_config=dataclasses.replace(matrix_config(), tier="nes-smoke"),
    )
    assert report["status"] == "passed"
    artifacts = Artifacts(tmp_path / "next", "2" * 32)
    world = MatrixWorld()
    target = Coordinator(
        matrix_config("expanded"), world, world.clock, artifacts, "2" * 32
    )
    try:
        qualified = target.load_qualification(
            first.artifacts.path / "nes-fceumm-qualification.json"
        )
        target.config = dataclasses.replace(
            target.config, qualified_inputs={"nes-fceumm": qualified}
        )
        result = target.run()
    finally:
        artifacts.close()
    assert result["status"] == "passed"
    assert result["full_regression_gate"] is False
    assert (
        world.allocations == world.removals == ["frontend", "receivers", "nes-fceumm"]
    )
    assert world.effects.count("qualified-input-check") == 1
    assert record(result["counts"])["passed"] == 3
    assert record(result["coverage"])["qualified_definition_count"] == 1


def test_matrix_inventory_missing_backend_refuses_before_allocation() -> None:
    """A full matrix cannot silently degrade into the existing RetroArch-only gate."""
    complete = matrix_config()
    for case in EMULATOR_CASES:
        hashes = dict(complete.hashes)
        del hashes[case.inventory_paths[-1]]
        with pytest.raises(NativeError, match="inventory is incomplete"):
            dataclasses.replace(complete, hashes=hashes)


def test_regression_mixed_pass_and_actual_absence_counts_remain_separate() -> None:
    """Five executed backend passes do not turn absent Mega Drive into an exit."""
    rows = passing_matrix_rows()
    absent = next(row for row in rows if row["name"] == "megadrive-genesisplusgx")
    absent.update(
        status="skipped-no-media", reason="Skipped: no compatible mounted media"
    )
    result = native_matrix.aggregate_regression(
        rows,
        [{"name": name, "status": "passed"} for name in RECEIVER_CASES],
        evidence_complete=True,
        cleanup_complete=True,
    )
    assert result["status"] == "passed"
    assert record(result["backend_counts"])["passed"] == 5
    assert record(result["backend_counts"])["skipped-no-media"] == 1
    assert len(sequence(result["emulator_exit_cases"])) == 6
    assert "megadrive-genesisplusgx" not in sequence(result["emulator_exit_cases"])


@pytest.mark.parametrize("tier", ["nes-smoke", "regression"])
def test_emulator_cleanup_failure_cannot_publish_qualification(
    tmp_path: Path, tier: str
) -> None:
    """Validated emulator behavior is not reusable proof before owned cleanup passes."""
    world = MatrixWorld(cleanup_failure_case="nes-fceumm")
    coordinator, report = execute(tmp_path, world, native_config=matrix_config(tier))
    row = next(
        record(value)
        for value in sequence(report["cases"])
        if record(value)["name"] == "nes-fceumm"
    )
    assert row["status"] == "passed"
    assert record(row["cleanup"])["status"] == "incomplete"
    assert report["status"] == "failed"
    assert not (coordinator.artifacts.path / "nes-fceumm-qualification.json").exists()
    assert report["emulator_exit_coverage"] == "No emulator exit coverage"
    if tier == "regression":
        assert record(report["coverage"])["qualified_definition_count"] == 0
        assert record(report["counts"])["not-run"] == 6


@pytest.mark.parametrize("collision", ["report.json", "nes-fceumm-qualification.json"])
def test_failed_qualification_publication_cannot_be_reused(
    tmp_path: Path, collision: str
) -> None:
    """Publication collisions fail coverage and cannot authorize expanded input."""
    run_id = "5" * 32
    artifacts = Artifacts(tmp_path, run_id)
    original = b'{"status":"failed"}\n'
    artifacts.put(collision, original)
    world = MatrixWorld()
    coordinator = Coordinator(matrix_config(), world, world.clock, artifacts, run_id)
    try:
        report = coordinator.run()
        assert report["status"] == "failed"
        assert report["full_regression_gate"] is False
        assert report["evidence_complete"] is False
        assert report["publication_error"]
        assert record(report["coverage"])["qualified_definition_count"] == 0
        assert (artifacts.path / collision).read_bytes() == original
        with pytest.raises((NativeError, OSError, ValueError)):
            coordinator.load_qualification(
                artifacts.path / "nes-fceumm-qualification.json"
            )
    finally:
        artifacts.close()
    assert world.allocations == world.removals


def test_failed_full_run_does_not_qualify_an_earlier_passing_emulator(
    tmp_path: Path,
) -> None:
    """A valid NES result stays diagnostic when another eligible row fails the run."""
    coordinator, report = execute(
        tmp_path, MatrixWorld(fail_case="snes-snes9x"), native_config=matrix_config()
    )
    rows = [record(row) for row in sequence(report["cases"])]
    assert report["status"] == "failed"
    assert (
        next(row for row in rows if row["name"] == "nes-fceumm")["status"] == "passed"
    )
    assert (
        next(row for row in rows if row["name"] == "snes-snes9x")["status"] == "failed"
    )
    assert "nes-fceumm" in sequence(report["emulator_exit_cases"])
    assert record(report["coverage"])["qualified_definition_count"] == 0
    assert not (coordinator.artifacts.path / "nes-fceumm-qualification.json").exists()


@pytest.mark.parametrize("target", ["report.json", "nes-fceumm-qualification.json"])
def test_report_sync_failure_leaves_no_reusable_passing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """A complete buffered JSON write is not a committed qualification report."""
    sync = os.fsync

    def fail_report_sync(descriptor: int) -> None:
        path = Path("/proc/self/fd", str(descriptor)).readlink()
        if path.name == target or path.name.startswith("." + target + "-"):
            msg = "Injected report durability failure"
            raise OSError(msg)
        sync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_report_sync)
    coordinator, report = execute(
        tmp_path, MatrixWorld(), native_config=matrix_config()
    )
    assert report["status"] == "failed"
    assert report["publication_error"]
    assert record(report["coverage"])["qualified_definition_count"] == 0
    assert not (coordinator.artifacts.path / "report.json").exists()
    proof = coordinator.artifacts.path / "nes-fceumm-qualification.json"
    assert proof.is_file() is (target == "report.json")
    with pytest.raises(FileNotFoundError):
        coordinator.load_qualification(proof)
    assert not any(
        path.name.startswith(".") for path in coordinator.artifacts.path.iterdir()
    )
