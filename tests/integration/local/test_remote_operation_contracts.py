"""Exercise maintained remote decisions locally, without Docker or a live API."""

import base64
import errno
import io
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict, Unpack

import pytest

from batocera_gow.host import native_remote
from batocera_gow.host.remote_payload import operations
from batocera_gow.host.remote_payload.activation import ActivationError, source_hash
from batocera_gow.host.remote_payload.activity import ActivityError
from batocera_gow.host.remote_payload.contracts import UI_REVISION
from batocera_gow.host.remote_payload.json_data import Json, decode, record, sequence

IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64
CASE = "local-contract-nes-libretro"
OWNER_KEY = "synthetic-run-owner"
# pragma: allowlist nextline secret
EMPTY_RUNNER_HASH = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


class RunOptions(TypedDict, total=False):
    """Describe the text subprocess options exercised by these transcripts."""

    input: str | None
    text: bool
    capture_output: bool
    timeout: float | None
    check: bool


class ProcessTranscript:
    """Supply raw executable responses and record argv separately from stdin."""

    def __init__(self) -> None:
        """Start with no permitted commands, so unexpected effects fail the test."""
        self.outputs: dict[tuple[str, ...], str] = {}
        self.failures: dict[
            tuple[str, ...], int | OSError | subprocess.TimeoutExpired
        ] = {}
        self.calls: list[tuple[tuple[str, ...], str | None]] = []
        self.api: dict[str, Json] = {}

    def __call__(
        self,
        args: list[str],
        **options: Unpack[RunOptions],
    ) -> subprocess.CompletedProcess[str]:
        """Model only subprocess output, never application validation or dispatch."""
        assert options.get("text", True)
        assert options.get("capture_output", True)
        assert not options.get("check", False)
        timeout = options.get("timeout")
        assert timeout is None or 0 < timeout <= 30
        argv = tuple(args)
        self.calls.append((argv, options.get("input")))
        failure = self.failures.get(argv)
        if isinstance(failure, (OSError, subprocess.TimeoutExpired)):
            raise failure
        if isinstance(failure, int):
            return subprocess.CompletedProcess(
                args, failure, "private-output", "private-error"
            )
        if args[0] == "curl":
            endpoint = next(v for v in args if v.startswith("http://"))
            key = endpoint.removeprefix("http://localhost/api/v1/")
            return subprocess.CompletedProcess(args, 0, json.dumps(self.api[key]), "")
        assert argv in self.outputs, argv
        return subprocess.CompletedProcess(args, 0, self.outputs[argv], "")

    def docker(self, *args: str, output: Json = "", privileged: bool = False) -> None:
        """Register one explicit Docker transcript, without invoking a daemon."""
        prefix = ("sudo", "-n", "docker") if privileged else ("docker",)
        self.outputs[(*prefix, *args)] = (
            output if isinstance(output, str) else json.dumps(output)
        )


def native_request(root: Path, action: str) -> dict[str, object]:
    """Select an isolated native run and a finite subprocess budget."""
    return {
        "timeout": 20,
        "wolf_container": "fixture-wolf",
        "api_socket": str(root / "not-a-real-socket"),
        "action": action,
        "host_root": str(root),
        "case_id": CASE,
        "token": OWNER_KEY,
        "uid": os.getuid() or 1000,
        "gid": os.getgid() or 1000,
        "container_id": CONTAINER,
        "image": IMAGE,
        "profile": "fixture-profile",
    }


@pytest.fixture
def native_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], Path, ProcessTranscript]:
    """Allocate real pinned state through dispatch, replacing only subprocesses."""
    root = tmp_path / "shared"
    root.mkdir(mode=0o700)
    request = native_request(root, "allocate")
    request["root_pin"] = native_remote.identity(root.stat())
    result = native_remote.Operations(request).dispatch()
    request["pin"] = result["pin"]
    boundary = ProcessTranscript()
    monkeypatch.setattr(subprocess, "run", boundary)
    return request, root / "test-runs" / CASE, boundary


def native_container(home: Path) -> dict[str, Json]:
    """Provide raw Docker ownership observations for one isolated run."""
    return {
        "Id": CONTAINER,
        "Name": "/fixture-owned",
        "Image": IMAGE,
        "Config": {
            "Labels": {"io.gow.integration.owner": OWNER_KEY},
            "Env": ["GOW_EMULATOR_CASE=nes-libretro"],  # pragma: allowlist secret
        },
        "Mounts": [{"Destination": "/home/retro", "Source": str(home), "Type": "bind"}],
        "State": {"Running": False, "Paused": False, "Status": "exited"},
    }


def allow_owned(boundary: ProcessTranscript, home: Path) -> dict[str, Json]:
    """Supply exact presence and inspection observations at the Docker boundary."""
    container = native_container(home)
    boundary.docker(
        "ps",
        "-aq",
        "--no-trunc",
        "--filter",
        "id=" + CONTAINER,
        output=CONTAINER + "\n",
    )
    boundary.docker("inspect", CONTAINER, output=[container])
    return container


def allow_snapshot(
    boundary: ProcessTranscript, containers: list[Json], lobbies: list[Json]
) -> None:
    """Supply raw discovery observations, including stopped containers."""
    boundary.api.update(
        sessions={"success": True, "sessions": []},
        lobbies={"success": True, "lobbies": lobbies},
    )
    ids = [str(native_remote.record(value)["Id"]) for value in containers]
    boundary.docker("ps", "-aq", "--no-trunc", output="\n".join(ids))
    if ids:
        boundary.docker("inspect", *ids, output=containers)


def test_native_snapshot_minimizes_private_api_and_container_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery exposes counts and ownership, not sessions, PINs or environment."""
    boundary = ProcessTranscript()
    container = native_container(tmp_path / "home")
    container["Config"] = {
        "Env": ["PASSWORD=private-data"],
        "Labels": {"unrelated": "private-data"},
    }
    allow_snapshot(
        boundary,
        [container],
        [
            {
                "id": "lobby-7",
                "name": "foreign-lobby",
                "started_by_profile_id": "profile-9",
                "pin_required": True,
                "connected_sessions": [{"private": "private-data"}],
                "runner": {},
                "pin": "private-data",
            }
        ],
    )
    boundary.api["sessions"] = {
        "success": True,
        "sessions": [{"private": "private-data"}, {}],
    }
    monkeypatch.setattr(subprocess, "run", boundary)
    result = native_remote.Operations(native_request(tmp_path, "snapshot")).dispatch()
    assert result == {
        "session_count": 2,
        "lobbies": [
            {
                "id": "lobby-7",
                "name": "foreign-lobby",
                "profile": "profile-9",
                "pin_required": True,
                "connected": 1,
                "runner_hash": EMPTY_RUNNER_HASH,
            }
        ],
        "containers": [
            {
                "id": CONTAINER,
                "name": "/fixture-owned",
                "image": IMAGE,
                "running": False,
                "paused": False,
                "status": "exited",
                "owner": None,
                "home": [str(tmp_path / "home")],
                "native": True,
            }
        ],
    }
    assert "private-data" not in json.dumps(result)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("damage", ["root", "uid", "parent"])
def test_native_allocation_refuses_unproven_root_or_identity(
    tmp_path: Path,
    damage: str,
) -> None:
    """A stale root pin, root app identity or unsafe parent cannot allocate."""
    request = native_request(tmp_path, "allocate")
    request["root_pin"] = native_remote.identity(tmp_path.stat())
    if damage == "root":
        request["root_pin"] = [0, 0, 0, 0, 0]
    elif damage == "uid":
        request["uid"] = 0
    else:
        (tmp_path / "test-runs").mkdir(mode=0o777)
        (tmp_path / "test-runs").chmod(0o777)
    with pytest.raises(
        native_remote.NativeError, match=r"identity changed|Non-root|Unsafe test-runs"
    ):
        native_remote.Operations(request).dispatch()
    assert not (tmp_path / "test-runs" / CASE).exists()


def test_native_lease_seed_and_revocation_use_only_pinned_control(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep case selection private and exclusive; revoke renewable input permission."""
    request, home, boundary = native_run
    allow_owned(boundary, home)
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    request.update(
        action="seed_selection",
        system="nes",
        selection={"schema": 1, "system": "nes", "selected": "private-media"},
    )
    assert native_remote.Operations(request).dispatch() == {"seeded": True}
    selection = home / ".native-control/selection.json"
    assert json.loads(selection.read_text(encoding="utf-8")) == {
        "schema": 1,
        "system": "nes",
        "selected": "private-media",
    }
    assert stat.S_IMODE(selection.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        native_remote.Operations(request).dispatch()
    request.update(action="lease", lease_seconds=7)
    assert native_remote.Operations(request).dispatch() == {"confirmed": True}
    lease = home / ".native-control/lease"
    assert json.loads(lease.read_text(encoding="utf-8")) == {"expires": 107.0}
    request["lease_seconds"] = 11
    native_remote.Operations(request).dispatch()
    assert json.loads(lease.read_text(encoding="utf-8")) == {"expires": 111.0}
    assert not (lease.parent / "lease-next").exists()
    request["action"] = "revoke"
    native_remote.Operations(request).dispatch()
    native_remote.Operations(request).dispatch()
    assert not lease.exists()
    assert selection.exists()


@pytest.mark.parametrize("damage", ["image", "token", "home", "case", "schema"])
def test_native_seed_refuses_mismatched_resource_or_replay(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    damage: str,
) -> None:
    """Neither plausible container names nor a foreign replay authorize writes."""
    request, home, boundary = native_run
    container = native_container(home)
    if damage == "image":
        container["Image"] = "sha256:" + "c" * 64
    elif damage == "token":
        container["Config"] = {
            "Labels": {"io.gow.integration.owner": "foreign"},
            # pragma: allowlist nextline secret
            "Env": ["GOW_EMULATOR_CASE=nes-libretro"],
        }
    elif damage == "home":
        container["Mounts"] = [
            {"Destination": "/home/retro", "Source": str(home.parent)}
        ]
    elif damage == "case":
        container["Config"] = {
            "Labels": {"io.gow.integration.owner": OWNER_KEY},
            "Env": ["GOW_EMULATOR_CASE=snes-libretro"],  # pragma: allowlist secret
        }
    boundary.docker("inspect", CONTAINER, output=[container])
    request.update(
        action="seed_selection",
        system="nes",
        selection={"schema": 2 if damage == "schema" else 1, "system": "nes"},
    )
    with pytest.raises(
        native_remote.NativeError, match=r"identity mismatch|selected-case"
    ):
        native_remote.Operations(request).dispatch()
    assert list((home / ".native-control").iterdir()) == []


@pytest.mark.parametrize(
    "blocker",
    [
        "startup",
        "container-owner",
        "container-home",
        "lobby-name",
        "lobby-runner",
        "none",
    ],
)
def test_native_state_removal_requires_independent_resource_absence(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    blocker: str,
) -> None:
    """Stopped containers and unconnected lobbies still retain their disposable home."""
    request, home, boundary = native_run
    foreign = home.parent / "foreign-run"
    foreign.mkdir()
    (foreign / "save").write_text("keep", encoding="utf-8")
    container = native_container(home if blocker == "container-home" else foreign)
    container["Config"] = {
        "Labels": {
            "io.gow.integration.owner": OWNER_KEY
            if blocker == "container-owner"
            else "foreign"
        }
    }
    lobbies: list[Json] = []
    if blocker.startswith("lobby"):
        lobbies.append(
            {
                "id": "lobby-1",
                "name": CASE if blocker == "lobby-name" else "other-run",
                "started_by_profile_id": "fixture-profile",
                "pin_required": True,
                "connected_sessions": [],
                "runner": {},
            }
        )
    allow_snapshot(
        boundary, [container] if blocker.startswith("container") else [], lobbies
    )
    request.update(
        action="remove_state",
        startup_resolved=blocker != "startup",
        # pragma: allowlist nextline secret
        runner_hash="44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    )
    if blocker == "none":
        assert native_remote.Operations(request).dispatch() == {"removed": True}
        assert not home.exists()
    else:
        with pytest.raises(
            native_remote.NativeError,
            match=r"forbids state removal|may still use disposable state",
        ):
            native_remote.Operations(request).dispatch()
        assert (home / ".native-owner").read_text(encoding="utf-8") == OWNER_KEY
    assert (foreign / "save").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("running", [False, True, None])
def test_native_container_removal_requires_explicit_stopped_state(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    *,
    running: bool | None,
) -> None:
    """Unknown state is not absence and cannot justify Docker removal."""
    request, home, boundary = native_run
    container = allow_owned(boundary, home)
    container["State"] = {"Running": running, "Paused": False}
    boundary.docker("inspect", CONTAINER, output=[container])
    boundary.docker("rm", CONTAINER)
    request["action"] = "remove_container"
    if running is False:
        assert native_remote.Operations(request).dispatch() == {"confirmed": True}
        assert boundary.calls[-1][0] == ("docker", "rm", CONTAINER)
    else:
        with pytest.raises(native_remote.NativeError, match="running or unknown"):
            native_remote.Operations(request).dispatch()
        assert not any(call[0][1] == "rm" for call in boundary.calls)
    assert home.exists()


@pytest.mark.parametrize("action", ["stop_container", "remove_container"])
@pytest.mark.parametrize("race", ["absent", "lost-response", "still-present"])
def test_native_container_cleanup_resolves_only_proven_absence(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    action: str,
    race: str,
) -> None:
    """A failed cleanup command is tolerated only when exact-ID absence is observed."""
    request, home, boundary = native_run
    allow_owned(boundary, home)
    presence = ("docker", "ps", "-aq", "--no-trunc", "--filter", "id=" + CONTAINER)
    effect = (
        ("docker", "rm", CONTAINER)
        if action == "remove_container"
        else ("docker", "stop", "--time", "3", CONTAINER)
    )
    request["action"] = action
    if race == "absent":
        boundary.outputs[presence] = ""
    else:
        boundary.failures[effect] = 1
        if race == "lost-response":
            # The second exact-ID observation occurs after the external command.
            original = boundary.__call__

            def execute(
                args: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                del kwargs
                result = original(args)
                if tuple(args) == effect:
                    boundary.outputs[presence] = ""
                return result

            # Patch the process seam, not owned-container validation.
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(subprocess, "run", execute)
                assert native_remote.Operations(request).dispatch() == {
                    "already_absent": True
                }
            return
    if race == "still-present":
        with pytest.raises(
            native_remote.NativeError, match="External operation failed"
        ):
            native_remote.Operations(request).dispatch()
    else:
        assert native_remote.Operations(request).dispatch() == {"already_absent": True}
        assert not any(call[0] == effect for call in boundary.calls)
    assert home.exists()


def test_native_create_keeps_private_payload_off_argv_and_checks_state_identity(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """A lobby for another state is refused before the API sees private data."""
    request, home, boundary = native_run
    payload = {
        "runner_state_folder": "test-runs/" + CASE,
        "name": CASE,
        "profile_id": "fixture-profile",
        "pin": "private-lobby-pin",
    }
    boundary.api["lobbies/create"] = {"success": True, "lobby_id": "allocated-7"}
    request.update(action="create", payload=payload)
    assert native_remote.Operations(request).dispatch() == {
        "success": True,
        "lobby_id": "allocated-7",
    }
    argv, stdin = boundary.calls[-1]
    assert stdin is not None
    assert json.loads(stdin) == payload
    assert "private-lobby-pin" not in " ".join(argv)
    assert argv[-4:] == (
        "--header",
        "Content-Type: application/json",
        "--data-binary",
        "@-",
    )
    payload["runner_state_folder"] = "test-runs/foreign"
    before = len(boundary.calls)
    with pytest.raises(native_remote.NativeError, match="does not match owned state"):
        native_remote.Operations(request).dispatch()
    assert len(boundary.calls) == before
    assert sorted(path.name for path in home.iterdir()) == [
        ".native-control",
        ".native-evidence",
        ".native-owner",
    ]


def test_native_integrity_preserves_only_validated_failure_categories(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """Packaged read-only failures retain actionable errno but no raw exception."""
    request, home, boundary = native_run
    allow_owned(boundary, home)
    command = (
        "docker",
        "exec",
        "-i",
        CONTAINER,
        "/usr/bin/python3",
        "-B",
        "/opt/gow-full-x86/native_checks.py",
        "inspect",
    )
    boundary.outputs[command] = json.dumps(
        {
            "ok": False,
            "inspection_failure": {
                "code": "os-error",
                "exception_class": "PermissionError",
                "errno": errno.EACCES,
                "message": "private-path",
            },
        }
    )
    request.update(action="integrity", hashes={"stock": "c" * 64})
    with pytest.raises(native_remote.InspectionError) as caught:
        native_remote.Operations(request).dispatch()
    assert caught.value.failure == {
        "code": "os-error",
        "exception_class": "PermissionError",
        "errno": 13,
    }
    assert "private-path" not in str(caught.value)
    assert home.exists()


def test_native_inspection_canonicalizes_binds_without_touching_content(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    tmp_path: Path,
) -> None:
    """Host aliases resolve to the actual mounted directories before comparison."""
    request, home, boundary = native_run
    roms = tmp_path / "roms"
    bios = tmp_path / "bios"
    roms.mkdir()
    bios.mkdir()
    alias = tmp_path / "rom-alias"
    alias.symlink_to(roms, target_is_directory=True)
    container = native_container(home)
    container["Mounts"] = [
        {"Destination": "/home/retro", "Source": str(home), "Type": "bind"},
        {"Destination": "/roms", "Source": str(alias), "Type": "bind"},
    ]
    boundary.docker("inspect", CONTAINER, output=[container])
    request.update(
        action="inspect", content_roots={"roms": str(alias), "bios": str(bios)}
    )
    result = native_remote.Operations(request).dispatch()
    assert result["content_roots"] == {"roms": str(roms), "bios": str(bios)}
    observed = native_remote.record(result["container"])
    assert native_remote.sequence(observed["Mounts"])[1] == {
        "Destination": "/roms",
        "Source": str(roms),
        "Type": "bind",
    }
    assert alias.is_symlink()
    assert list(roms.iterdir()) == list(bios.iterdir()) == []


def image_observation() -> dict[str, Json]:
    """Describe a synthetic already-local image with the required ancestry."""
    return {
        "Id": IMAGE,
        "Config": {
            "Labels": {
                "org.opencontainers.image.revision": "d" * 40,
                "io.gow.full-x86.input.sha256": "e" * 64,
                "org.opencontainers.image.version": "43.1",
                "io.gow.full-x86.experimental": "true",
                "io.gow.full-x86.source.kind": "git",
            },
            "Entrypoint": [
                "/usr/bin/python3",
                "/opt/gow-full-x86/input_transport.py",
                "--",
                "/opt/gow-full-x86/entrypoint.sh",
            ],
            "Cmd": ["/opt/gow-full-x86/frontend.sh"],
        },
    }


@pytest.mark.parametrize("damage", ["absent", "identity", "entrypoint", "kind", "none"])
def test_native_image_status_never_loads_or_pulls_unqualified_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    """Presence requires exact provenance and supervisor ancestry, not only a tag."""
    request = native_request(tmp_path, "image_status")
    request.update(source="d" * 40, stock_sha256="e" * 64)
    boundary = ProcessTranscript()
    image = image_observation()
    if damage == "identity":
        image["Id"] = "sha256:" + "f" * 64
    elif damage == "entrypoint":
        image["Config"] = {**record(image["Config"]), "Entrypoint": ["/bin/sh"]}
    elif damage == "kind":
        config = record(image["Config"])
        labels = record(config["Labels"])
        labels["io.gow.full-x86.source.kind"] = "worktree"
        config["Labels"] = labels
        image["Config"] = config
    boundary.docker(
        "image",
        "ls",
        "--quiet",
        "--no-trunc",
        output="" if damage == "absent" else IMAGE + "\n",
    )
    boundary.docker("image", "inspect", IMAGE, output=[image])
    monkeypatch.setattr(subprocess, "run", boundary)
    if damage in {"identity", "entrypoint", "kind"}:
        with pytest.raises(
            native_remote.NativeError,
            match=r"provenance mismatch|ancestry mismatch|source-kind",
        ):
            native_remote.Operations(request).dispatch()
    else:
        assert native_remote.Operations(request).dispatch() == (
            {"present": False}
            if damage == "absent"
            else {"present": True, "image": IMAGE}
        )
    assert all(
        call[0][1:3] in (("image", "ls"), ("image", "inspect"))
        for call in boundary.calls
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "failure", ["stderr", "timeout", "os", "large", "api", "shape"]
)
def test_native_process_and_api_failures_are_bounded_and_nonsecret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """External failures cannot become successful idle observations or leak output."""
    boundary = ProcessTranscript()
    command = ("docker", "image", "ls", "--quiet", "--no-trunc")
    boundary.outputs[command] = (
        "x" * (24 * 1024 * 1024 + 1) if failure == "large" else ""
    )
    if failure == "stderr":
        boundary.failures[command] = 2
    elif failure == "timeout":
        boundary.failures[command] = subprocess.TimeoutExpired(
            "private-command", 1, stderr="private-error"
        )
    elif failure == "os":
        boundary.failures[command] = OSError(errno.EACCES, "private-path")
    boundary.api["sessions"] = (
        {"success": False, "sessions": [], "error": "private-error"}
        if failure == "api"
        else []
    )
    request = native_request(
        tmp_path, "snapshot" if failure in {"api", "shape"} else "image_status"
    )
    monkeypatch.setattr(subprocess, "run", boundary)
    with pytest.raises(native_remote.NativeError) as caught:
        native_remote.Operations(request).dispatch()
    assert "private-" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_native_json_boundary_sanitizes_os_failure_and_disarms_timer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The JSON entry point reports a category and errno, never exception text."""
    request = native_request(tmp_path, "image_status")
    boundary = ProcessTranscript()
    boundary.failures[("docker", "image", "ls", "--quiet", "--no-trunc")] = OSError(
        errno.EACCES, "private-path"
    )
    monkeypatch.setattr(subprocess, "run", boundary)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    # The owner of a real process alarm is the process; this in-process test borrows it.
    timers: list[float] = []
    monkeypatch.setattr(signal, "signal", lambda _signum, _handler: None)
    monkeypatch.setattr(
        signal, "setitimer", lambda _kind, seconds: timers.append(seconds)
    )
    assert native_remote.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "ok": False,
        "operation_failure": {
            "category": "native",
            "code": "external-unavailable",
            "errno": None,
        },
        "error": (
            "Native operation failed closed; "
            "inspect the reported phase and owned identities."
        ),
    }
    assert timers == [20.0, 0]
    assert "private-path" not in output.out + output.err


@pytest.fixture
def deployment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[operations.Deployment, dict[str, Json], ProcessTranscript]:
    """Keep every remote write under temporary explicitly injected paths."""
    root = tmp_path / "deployment"
    home = tmp_path / "native-home"
    config = tmp_path / "config.toml"
    config.write_text("unrelated = 'keep'\n", encoding="utf-8")
    config.chmod(0o640)
    service = operations.Deployment(root, home=home, config=config)
    boundary = ProcessTranscript()
    boundary.docker(
        "image",
        "ls",
        "--format",
        "{{.ID}}",
        output="ui-image\nui-image\n",
        privileged=True,
    )
    boundary.docker(
        "image",
        "inspect",
        "ui-image",
        output=[
            {
                "RepoTags": ["fixture/wolf-ui:local"],
                "Config": {
                    "Labels": {"org.opencontainers.image.revision": UI_REVISION}
                },
            }
        ],
        privileged=True,
    )
    boundary.docker(
        "image", "inspect", IMAGE, output=[image_observation()], privileged=True
    )
    boundary.docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "/opt/gow-full-x86/check-runtime.sh",
        IMAGE,
        privileged=True,
    )
    boundary.docker("ps", "-aq", output="", privileged=True)
    boundary.docker("restart", "wolf-wolf-1", privileged=True)
    boundary.api.update(
        sessions={"success": True, "sessions": []},
        lobbies={"success": True, "lobbies": []},
        profiles={"success": True, "profiles": []},
    )
    monkeypatch.setattr(subprocess, "run", boundary)
    request: dict[str, Json] = {
        "action": "prepare",
        "image": IMAGE,
        "image_id": IMAGE,
        "local": True,
        "adapter_revision": "d" * 40,
        "required_bytes": 0,
    }
    return service, request, boundary


def test_deployment_prepare_and_registration_transaction_preserve_private_state(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
) -> None:
    """Prepare records ownership, then activation preserves metadata and no backups."""
    service, request, boundary = deployment
    assert service.dispatch(request) == {
        "prepared": True,
        "ui_revision": UI_REVISION,
        "native_home": str(service.home),
        "image": IMAGE,
    }
    assert stat.S_IMODE(service.root.stat().st_mode) == 0o700
    marker = service.root / "deployment.json"
    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert not service.home.exists()
    request["action"] = "read-registration"
    registration = service.dispatch(request)
    assert registration["config"] == "unrelated = 'keep'\n"
    assert registration["owned"] is False
    request.update(
        action="activate",
        expected_hash=source_hash("unrelated = 'keep'\n"),
        config="unrelated = 'keep'\nprivate_pin = 'only-in-config'\n",
        ui_revision=UI_REVISION,
    )
    original = service.config.stat()
    result = service.dispatch(request)
    assert result["changed"] is True
    assert (
        service.config.read_text(encoding="utf-8")
        == "unrelated = 'keep'\nprivate_pin = 'only-in-config'\n"
    )
    assert stat.S_IMODE(service.config.stat().st_mode) == 0o640
    assert (service.config.stat().st_uid, service.config.stat().st_gid) == (
        original.st_uid,
        original.st_gid,
    )
    saved = record(decode(marker.read_text(encoding="utf-8")))
    assert saved["registered"] is True
    assert saved["activated"] is True
    assert saved["registered_image"] == IMAGE
    assert "only-in-config" not in marker.read_text(encoding="utf-8")
    assert [path.name for path in service.root.iterdir()] == ["deployment.json"]
    assert sorted(path.name for path in service.root.parent.iterdir()) == [
        "config.toml",
        "deployment",
    ]
    assert [call[0] for call in boundary.calls].count(
        ("sudo", "-n", "docker", "restart", "wolf-wolf-1")
    ) == 1


@pytest.mark.parametrize("failure", ["changed-source", "busy", "revision", "restart"])
def test_deployment_activation_refuses_or_records_failed_restart_truthfully(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
    failure: str,
) -> None:
    """Preserve original bytes on refusal; retain ownership after restart failure."""
    service, request, boundary = deployment
    service.dispatch(request)
    request.update(
        action="activate",
        expected_hash=source_hash("unrelated = 'keep'\n"),
        config="new = 'private-value'\n",
        ui_revision=UI_REVISION,
    )
    if failure == "changed-source":
        service.config.write_text("operator edit\n", encoding="utf-8")
    elif failure == "busy":
        boundary.api["lobbies"] = {
            "success": True,
            "lobbies": [{"private": "not-empty"}],
        }
    elif failure == "revision":
        request["ui_revision"] = "f" * 40
    else:
        boundary.failures[("sudo", "-n", "docker", "restart", "wolf-wolf-1")] = 1
    expected = service.config.read_bytes()
    with pytest.raises((ActivationError, ActivityError, operations.RemoteError)):
        service.dispatch(request)
    saved = record(
        decode((service.root / "deployment.json").read_text(encoding="utf-8"))
    )
    if failure == "restart":
        assert service.config.read_text(encoding="utf-8") == "new = 'private-value'\n"
        assert saved["registered"] is True
        assert saved["activated"] is False
        del boundary.failures[("sudo", "-n", "docker", "restart", "wolf-wolf-1")]
        request["expected_hash"] = source_hash("new = 'private-value'\n")
        assert service.dispatch(request)["changed"] is False
        assert (
            record(
                decode((service.root / "deployment.json").read_text(encoding="utf-8"))
            )["activated"]
            is True
        )
    else:
        assert service.config.read_bytes() == expected
        assert saved["registered"] is False
        assert not any(call[0][3:4] == ("restart",) for call in boundary.calls)
    assert not any(
        path.name.startswith(".gow-") for path in service.root.parent.iterdir()
    )


@pytest.mark.parametrize("failure", ["space", "image", "labels", "runtime", "ui"])
def test_failed_preparation_cannot_authorize_later_operations(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
    failure: str,
) -> None:
    """Preparation ownership alone is not proof of usable image and prerequisites."""
    service, request, boundary = deployment
    if failure == "space":
        request["required_bytes"] = 1 << 100
    elif failure == "image":
        request["image_id"] = "sha256:" + "f" * 64
    elif failure == "labels":
        request["adapter_revision"] = "wrong"
    elif failure == "runtime":
        boundary.failures[
            (
                "sudo",
                "-n",
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "/opt/gow-full-x86/check-runtime.sh",
                IMAGE,
            )
        ] = 1
    else:
        boundary.docker("image", "inspect", "ui-image", output=[], privileged=True)
    with pytest.raises(operations.RemoteError):
        service.dispatch(request)
    request["action"] = "read-registration"
    with pytest.raises(
        operations.RemoteError, match="prepare the published image first"
    ):
        service.dispatch(request)
    assert not service.home.exists()
    assert service.config.read_text(encoding="utf-8") == "unrelated = 'keep'\n"
    if service.root.exists():
        assert "prepared_image" not in record(
            decode((service.root / "deployment.json").read_text(encoding="utf-8"))
        )


def test_deployment_diagnostics_refuse_partial_collision_and_preserve_foreign_file(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
) -> None:
    """Exclusive publication neither truncates an existing partial nor follows links."""
    service, request, _boundary = deployment
    service.dispatch(request)
    partial = service.root / "remote-session.json.partial"
    partial.write_text("operator-file", encoding="utf-8")
    request.update(
        action="write-diagnostics",
        filename="remote-session.json",
        diagnostics={
            "logs": "ready\npassword=private-value\nfinished",
            "access_token": "private-value",
            "status": "ok",
        },
    )
    with pytest.raises(FileExistsError):
        service.dispatch(request)
    assert partial.read_text(encoding="utf-8") == "operator-file"
    partial.unlink()
    assert service.dispatch(request) == {"saved": True}
    result = service.root / "remote-session.json"
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "logs": "ready\n[redacted sensitive log line]\nfinished",
        "status": "ok",
    }
    assert stat.S_IMODE(result.stat().st_mode) == 0o600
    foreign = service.root.parent / "foreign"
    foreign.write_text("keep", encoding="utf-8")
    result.unlink()
    result.symlink_to(foreign)
    with pytest.raises(operations.RemoteError, match="symlinked"):
        service.dispatch(request)
    assert foreign.read_text(encoding="utf-8") == "keep"
    assert not partial.exists()


def test_native_transfer_writes_exact_bytes_and_refuses_bad_offsets_or_digest(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """Write contiguous private chunks, and refuse loading after integrity failure."""
    request, home, boundary = native_run
    request.update(
        action="image_chunk", offset=0, data=base64.b64encode(b"first-").decode("ascii")
    )
    assert native_remote.Operations(request).dispatch() == {"offset": 6}
    archive = home / ".native-image.tar"
    assert archive.read_bytes() == b"first-"
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    request.update(offset=6, data=base64.b64encode(b"second").decode("ascii"))
    assert native_remote.Operations(request).dispatch() == {"offset": 12}
    assert archive.read_bytes() == b"first-second"
    request["offset"] = 7
    with pytest.raises(native_remote.NativeError, match="transfer identity changed"):
        native_remote.Operations(request).dispatch()
    request.update(action="image_load", offset=12, sha256="0" * 64)
    with pytest.raises(native_remote.NativeError, match="archive integrity mismatch"):
        native_remote.Operations(request).dispatch()
    assert archive.read_bytes() == b"first-second"
    assert boundary.calls == []


def test_native_transfer_accepts_full_chunk_and_refuses_oversize_without_appending(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """Admit a full finite chunk, preserving its bytes after oversized continuation."""
    request, home, boundary = native_run
    payload = bytes(range(256)) * (256 * 1024)
    request.update(
        action="image_chunk", offset=0, data=base64.b64encode(payload).decode("ascii")
    )
    assert native_remote.Operations(request).dispatch() == {"offset": 67108864}
    archive = home / ".native-image.tar"
    assert archive.read_bytes() == payload
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    request.update(
        offset=67108864, data=base64.b64encode(payload + b"x").decode("ascii")
    )
    with pytest.raises(native_remote.NativeError, match="bounded storage"):
        native_remote.Operations(request).dispatch()
    assert archive.read_bytes() == payload
    assert boundary.calls == []


def test_native_transfer_final_storage_byte_is_writable_but_cannot_overflow(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """Use a sparse owned archive to exercise the actual 32 GiB write boundary."""
    request, home, boundary = native_run
    archive = home / ".native-image.tar"
    with archive.open("wb") as stream:
        stream.truncate(34359738367)
    request.update(action="image_chunk", offset=34359738367, data="YQ==")
    assert native_remote.Operations(request).dispatch() == {"offset": 34359738368}
    request.update(offset=34359738368, data="Yg==")
    with pytest.raises(native_remote.NativeError, match="bounded storage"):
        native_remote.Operations(request).dispatch()
    assert archive.stat().st_size == 34359738368
    with archive.open("rb") as stream:
        stream.seek(-2, os.SEEK_END)
        assert stream.read() == b"\x00a"
    assert boundary.calls == []


@pytest.mark.parametrize("replacement", ["hardlink", "symlink", "fifo", "marker"])
def test_native_transfer_refuses_changed_owned_files_without_touching_foreign_bytes(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    replacement: str,
) -> None:
    """Reject changed ownership or non-private archive types before appending."""
    request, home, boundary = native_run
    request.update(action="image_chunk", offset=0, data="YQ==")
    assert native_remote.Operations(request).dispatch() == {"offset": 1}
    archive = home / ".native-image.tar"
    foreign = home.parent / "operator.bin"
    foreign.write_bytes(b"operator")
    if replacement == "hardlink":
        os.link(archive, home.parent / "foreign-link")
    elif replacement == "symlink":
        archive.unlink()
        archive.symlink_to(foreign)
    elif replacement == "fifo":
        archive.unlink()
        os.mkfifo(archive)
    else:
        (home / ".native-owner").write_bytes(b"changed-owner")
    request.update(offset=1, data="Yg==")
    with pytest.raises((native_remote.NativeError, OSError)):
        native_remote.Operations(request).dispatch()
    assert foreign.read_bytes() == b"operator"
    if replacement in {"hardlink", "marker"}:
        assert archive.read_bytes() == b"a"
    assert boundary.calls == []


@pytest.mark.parametrize("data", ["", "not base64!", "YQ", None, 7])
def test_native_transfer_invalid_chunk_data_cannot_modify_partial_archive(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    data: object,
) -> None:
    """Malformed or absent encoded bytes cannot alter an accepted partial upload."""
    request, home, boundary = native_run
    request.update(action="image_chunk", offset=0, data="YQ==")
    assert native_remote.Operations(request).dispatch() == {"offset": 1}
    request.update(offset=1, data=data)
    with pytest.raises((native_remote.NativeError, ValueError)):
        native_remote.Operations(request).dispatch()
    assert (home / ".native-image.tar").read_bytes() == b"a"
    assert boundary.calls == []


@pytest.mark.parametrize("offset", [-1, True, 32 * 1024**3 + 1])
def test_native_transfer_rejects_invalid_storage_bounds_before_file_creation(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    offset: int,
) -> None:
    """Negative, boolean and over-limit offsets cannot reserve or alter files."""
    request, home, boundary = native_run
    request.update(action="image_chunk", offset=offset, data="YQ==")
    with pytest.raises(
        native_remote.NativeError, match="bounded image transfer offset"
    ):
        native_remote.Operations(request).dispatch()
    assert not (home / ".native-image.tar").exists()
    assert boundary.calls == []


def test_native_collect_keeps_valid_completed_evidence_when_a_sibling_is_unsafe(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
) -> None:
    """An unsafe file is unavailable, not an excuse to drop other completed evidence."""
    request, home, boundary = native_run
    evidence = home / ".native-evidence"
    owner = evidence.stat()
    startup = evidence / "startup.json"
    startup.write_bytes(b'{"status":"ready"}')
    startup.chmod(0o600)
    os.chown(startup, owner.st_uid, owner.st_gid)
    report = evidence / "frontend-probe.json"
    report.write_bytes(b"unsafe-public-evidence")
    report.chmod(0o644)
    request.update(
        action="collect",
        files=["startup.json", "frontend-probe.json", "frontend-ready.png"],
    )
    assert native_remote.Operations(request).dispatch() == {
        "files": {"startup.json": "eyJzdGF0dXMiOiJyZWFkeSJ9"},
        "unavailable": ["frontend-probe.json"],
    }
    request["files"] = ["../.native-owner"]
    with pytest.raises(native_remote.NativeError, match="selected evidence name"):
        native_remote.Operations(request).dispatch()
    assert startup.read_bytes() == b'{"status":"ready"}'
    assert boundary.calls == []


@pytest.mark.parametrize("log_case", ["complete", "partial", "oversized"])
def test_native_incomplete_evidence_observes_only_fixed_bounded_startup_findings(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    monkeypatch: pytest.MonkeyPatch,
    log_case: str,
) -> None:
    """Bound, reap and close real local child pipes without retaining raw logs."""
    request, home, boundary = native_run
    container = allow_owned(boundary, home)
    container["State"] = {
        "Running": False,
        "Paused": False,
        "Restarting": False,
        "Dead": False,
        "OOMKilled": False,
        "ExitCode": 1,
        "Pid": 0,
    }
    boundary.docker("inspect", CONTAINER, output=[container])
    original_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def start_local_pipe(
        args: list[str],
        *,
        stdin: int,
        stdout: int,
        stderr: int,
    ) -> subprocess.Popen[bytes]:
        """Supply harmless local bytes through a real pipe instead of Docker."""
        assert args[0] == "docker"
        assert args[1] in {"logs", "top"}
        if args[1] == "top":
            program = (
                "print('PID PPID UID COMMAND')\n"
                "print('21 1 1000 /usr/bin/emulationstation private-argument')\n"
            )
        elif log_case == "oversized":
            program = (
                "import sys\n"
                "import time\n"
                "sys.stdout.write('x'*70000)\n"
                "sys.stdout.flush()\n"
                "time.sleep(30)\n"
            )
        elif log_case == "partial":
            program = (
                "import sys\n"
                "sys.stdout.write('gow-full-x86: D-Bus readiness timed out')\n"
            )
        else:
            program = (
                "print('private-unclassified-log')\n"
                "print('gow-full-x86: D-Bus readiness timed out')\n"
            )
        child = original_popen(
            [sys.executable, "-c", program], stdin=stdin, stdout=stdout, stderr=stderr
        )
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", start_local_pipe)
    request.update(action="collect", files=["startup.json"])
    result = native_remote.Operations(request).dispatch()
    observation = native_remote.record(result["startup_observation"])
    assert result["files"] == {}
    assert result["unavailable"] == []
    assert observation["container"] == "present"
    assert observation["logs"] == {
        "status": "truncated" if log_case == "oversized" else "complete",
        "failure_codes": ["runtime-dbus-timeout"] if log_case == "complete" else [],
    }
    assert observation["processes"] == {
        "status": "complete",
        "roles": [
            {"role": "emulationstation", "pid": 21, "parent_pid": 1, "uid": 1000}
        ],
    }
    assert "private-" not in json.dumps(result)
    assert len(children) == 2
    assert all(
        child.poll() is not None and child.stdout is not None and child.stdout.closed
        for child in children
    )
    assert list((home / ".native-evidence").iterdir()) == []


@pytest.mark.parametrize("damage", ["absent", "name", "hash", "none"])
def test_native_lobby_stop_revalidates_name_profile_and_runner_before_effect(
    native_run: tuple[dict[str, object], Path, ProcessTranscript],
    damage: str,
) -> None:
    """An observed lobby ID alone is not authority to stop another run's lobby."""
    request, home, boundary = native_run
    lobby: Json = {
        "id": "lobby-1",
        "name": "foreign" if damage == "name" else CASE,
        "started_by_profile_id": "fixture-profile",
        "pin_required": True,
        "connected_sessions": [],
        "runner": {},
    }
    allow_snapshot(boundary, [], [] if damage == "absent" else [lobby])
    boundary.api["lobbies/stop"] = {"success": True}
    request.update(
        action="stop_lobby",
        lobby_id="lobby-1",
        lobby_pin="private-lobby-pin",
        runner_hash="wrong"
        if damage == "hash"
        # pragma: allowlist nextline secret
        else "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    )
    if damage in {"name", "hash"}:
        with pytest.raises(native_remote.NativeError, match="Lobby identity changed"):
            native_remote.Operations(request).dispatch()
    else:
        assert native_remote.Operations(request).dispatch() == (
            {"already_absent": True} if damage == "absent" else {"success": True}
        )
    writes = [call for call in boundary.calls if call[1] is not None]
    if damage == "none":
        assert len(writes) == 1
        assert json.loads(writes[0][1] or "") == {
            "lobby_id": "lobby-1",
            "pin": "private-lobby-pin",
        }
        assert "private-lobby-pin" not in " ".join(writes[0][0])
    else:
        assert writes == []
    assert home.exists()


def deployment_container(service: operations.Deployment) -> dict[str, Json]:
    """Describe automatic mounts and capabilities independently of validation."""
    return {
        "Id": CONTAINER,
        "Name": "/WolfExperimental_11111111-2222-3333-4444-555555555555",
        "Image": IMAGE,
        "Config": {
            "Image": IMAGE,
            "Env": [
                "PUID=1000",
                "PGID=1000",
                "PASSWORD=private-env",
                "PULSE_SERVER=unix:/run/pulse",
            ],
        },
        "State": {"Running": True, "Status": "running"},
        "Mounts": [
            {"Destination": "/home/retro", "Source": str(service.home), "RW": True},
            {
                "Destination": "/home/retro/userdata/roms",
                "Source": str(service.root.parent / "roms"),
                "RW": False,
            },
            {
                "Destination": "/home/retro/userdata/bios",
                "Source": str(service.root.parent / "bios"),
                "RW": False,
            },
            {
                "Destination": "/usr/nvidia",
                "Source": str(service.root.parent / "drivers"),
                "RW": True,
            },
            {
                "Destination": "/usr/bin/fake-udev",
                "Source": str(service.root.parent / "fake-udev"),
                "RW": False,
            },
            {
                "Destination": "/run/udev",
                "Source": str(service.root.parent / "udev"),
                "RW": True,
            },
        ],
        "HostConfig": {
            "IpcMode": "private",
            "Privileged": False,
            "PidMode": "",
            "CapAdd": ["CAP_NET_ADMIN", "SYS_NICE"],
            "Devices": [{"PathInContainer": "/dev/uinput"}],
        },
    }


def allow_deployment_inspect(
    service: operations.Deployment,
    request: dict[str, Json],
    boundary: ProcessTranscript,
    container: dict[str, Json],
) -> None:
    """Supply synthetic identity and graphics transcripts without launching an app."""
    boundary.docker("ps", "-aq", output=CONTAINER, privileged=True)
    boundary.docker("inspect", CONTAINER, output=[container], privileged=True)
    boundary.docker(
        "exec",
        CONTAINER,
        "/bin/cat",
        "/run/gow-full-x86-session.json",
        output={
            "puid": 1000,
            "pgid": 1000,
            "display": ":0",
            # Inspected guest metadata only; this path is never opened locally.
            "xauthority": "/tmp/gow-full-x86-fixture/Xauthority",  # noqa: S108
        },
        privileged=True,
    )
    boundary.docker(
        "exec",
        CONTAINER,
        "/usr/bin/readlink",
        "/userdata",
        output="/home/retro/userdata\n",
        privileged=True,
    )
    boundary.docker(
        "exec",
        CONTAINER,
        "/bin/cat",
        "/home/retro/.gow-full-x86-state.json",
        output={"release": "43.1", "puid": 1000, "pgid": 1000},
        privileged=True,
    )
    boundary.docker(
        "exec",
        CONTAINER,
        "/bin/ps",
        "-eo",
        "pid,ppid,comm",
        output="PID PPID COMMAND\n1 0 supervisor\n",
        privileged=True,
    )
    boundary.docker(
        "exec",
        "--user",
        "1000:1000",
        "--env",
        "DISPLAY=:0",
        "--env",
        # pragma: allowlist nextline secret
        "XAUTHORITY=/tmp/gow-full-x86-fixture/Xauthority",
        "--env",
        "LD_LIBRARY_PATH=/usr/nvidia/lib:/usr/nvidia/lib32",
        CONTAINER,
        "glxinfo",
        "-B",
        output="OpenGL renderer: NVIDIA fixture",
        privileged=True,
    )
    boundary.docker(
        "logs",
        "--tail",
        "2000",
        CONTAINER,
        output="ready\nAuthorization: Bearer private-log\nfinished",
        privileged=True,
    )
    request.update(
        action="logs",
        roms_root=str(service.root.parent / "roms"),
        bios_root=str(service.root.parent / "bios"),
    )


def test_deployment_inspection_checks_runtime_identity_and_redacts_diagnostics(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
) -> None:
    """Only qualified automatic mounts and the session actor authorize diagnostics."""
    service, request, boundary = deployment
    service.dispatch(request)
    allow_deployment_inspect(service, request, boundary, deployment_container(service))
    result = service.dispatch(request)
    entries = result["containers"]
    assert isinstance(entries, list)
    assert len(entries) == 1
    observed = record(entries[0])
    assert observed["environment"] == {
        "PUID": "1000",
        "PGID": "1000",
        "PULSE_SERVER": "unix:/run/pulse",
    }
    assert observed["nvidia_renderer_verified"] is True
    assert observed["userdata_link"] == "/home/retro/userdata"
    assert observed["state_marker"] == {"release": "43.1", "puid": 1000, "pgid": 1000}
    assert observed["logs"] == "ready\n[redacted sensitive log line]\nfinished"
    assert "private-env" not in json.dumps(result)
    assert "private-log" not in json.dumps(result)
    assert [path.name for path in service.root.iterdir()] == ["deployment.json"]


def damage_container_observation(
    service: operations.Deployment, container: dict[str, Json], damage: str
) -> None:
    """Alter one raw Docker isolation observation, not the validator's result."""
    mounts = [record(item) for item in sequence(container["Mounts"])]
    host = record(container["HostConfig"])
    if damage == "image":
        container["Image"] = "sha256:" + "f" * 64
    elif damage == "home":
        mounts[0]["Source"] = str(service.root.parent / "foreign-home")
    elif damage == "duplicate":
        mounts.append(dict(mounts[0]))
    elif damage == "writable-roms":
        mounts[1]["RW"] = True
    elif damage == "automatic":
        mounts.pop()
    elif damage == "nvidia":
        mounts[3]["RW"] = False
    host_changes: dict[str, tuple[str, Json]] = {
        "ipc": ("IpcMode", "host"),
        "caps": ("CapAdd", ["SYS_ADMIN", "SYS_NICE", "NET_ADMIN"]),
        "uinput": ("Devices", []),
    }
    if damage in host_changes:
        key, value = host_changes[damage]
        host[key] = value
    container["Mounts"] = list(mounts)
    container["HostConfig"] = host


@pytest.mark.parametrize(
    "damage",
    [
        "image",
        "home",
        "duplicate",
        "writable-roms",
        "ipc",
        "caps",
        "uinput",
        "automatic",
        "nvidia",
        "identity",
        "userdata",
        "xauthority",
    ],
)
def test_deployment_diagnostics_refuse_unqualified_container_before_log_collection(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
    damage: str,
) -> None:
    """A matching runner prefix never bypasses isolation, content or actor checks."""
    service, request, boundary = deployment
    service.dispatch(request)
    container = deployment_container(service)
    damage_container_observation(service, container, damage)
    allow_deployment_inspect(service, request, boundary, container)
    if damage == "identity":
        boundary.docker(
            "exec",
            CONTAINER,
            "/bin/cat",
            "/home/retro/.gow-full-x86-state.json",
            output={"release": "43.1", "puid": 2000, "pgid": 1000},
            privileged=True,
        )
    elif damage == "userdata":
        boundary.docker(
            "exec",
            CONTAINER,
            "/usr/bin/readlink",
            "/userdata",
            output="/foreign/userdata",
            privileged=True,
        )
    elif damage == "xauthority":
        boundary.docker(
            "exec",
            CONTAINER,
            "/bin/cat",
            "/run/gow-full-x86-session.json",
            output={
                "puid": 1000,
                "pgid": 1000,
                "display": ":0",
                "xauthority": "/foreign/Xauthority",
            },
            privileged=True,
        )
    with pytest.raises(operations.RemoteError):
        service.dispatch(request)
    assert not any(call[0][3:4] == ("logs",) for call in boundary.calls)
    assert not service.home.exists()
    assert service.config.read_text(encoding="utf-8") == "unrelated = 'keep'\n"


@pytest.mark.parametrize(
    "damage", ["none", "root", "render", "wolf", "profile", "runtime"]
)
def test_native_preflight_derives_pinned_roots_and_effective_runtime_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    """Raw installed observations must agree before a disposable run can be prepared."""
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o700)
    runtime = tmp_path / "sockets"
    (runtime / "session").mkdir(parents=True)
    roms = tmp_path / "roms"
    bios = tmp_path / "bios"
    roms.mkdir()
    bios.mkdir()
    request = native_request(shared, "preflight")
    request.update(
        local_root="/wolf-state",
        content_roots={"roms": str(roms), "bios": str(bios)},
        protected=[str(tmp_path / "production")],
        render_node=str(roms) if damage == "render" else "/dev/null",
        source="d" * 40,
        stock_sha256="e" * 64,
    )
    # /dev/null supplies only a harmless character-device type observation,
    # never evidence of a GPU, device access or an actual native capability.
    boundary = ProcessTranscript()
    allow_snapshot(boundary, [], [])
    boundary.api["profiles"] = {
        "success": True,
        "profiles": [] if damage == "profile" else [{"id": "fixture-profile"}],
    }
    boundary.docker(
        "inspect",
        "fixture-wolf",
        output=[
            {
                "Id": "f" * 64,
                "Image": "installed-wolf-image",
                "Config": {
                    "Env": [
                        "HOST_APPS_STATE_FOLDER=/wolf-state",
                        "XDG_RUNTIME_DIR="
                        + (
                            "relative/session"
                            if damage == "runtime"
                            else "/socket-root/session"
                        ),
                        "NVIDIA_DRIVER_VOLUME_NAME=fixture-driver",
                        "WOLF_STOP_CONTAINER_ON_EXIT=TRUE",
                    ]
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Destination": "/wolf-state",
                        "Source": str(shared),
                        "RW": True,
                    },
                    {
                        "Type": "bind",
                        "Destination": "/socket-root",
                        "Source": str(runtime),
                        "RW": True,
                    },
                ],
                "State": {"Running": damage != "wolf"},
            }
        ],
    )
    info = shared.stat()
    boundary.docker(
        "exec",
        "f" * 64,
        "stat",
        "-Lc",
        "%d %i",
        "/wolf-state",
        output=f"{info.st_dev} {info.st_ino + (1 if damage == 'root' else 0)}",
    )
    boundary.docker(
        "image",
        "inspect",
        "installed-wolf-image",
        output=[
            {
                "Config": {
                    "Labels": {
                        "org.opencontainers.image.revision": (
                            # pragma: allowlist nextline secret
                            "ee271038da2b81c9e54c28c9daa7558692d415d6"
                        )
                    }
                }
            }
        ],
    )
    boundary.docker("image", "inspect", IMAGE, output=[image_observation()])
    boundary.docker(
        "volume",
        "inspect",
        "fixture-driver",
        output=[{"Mountpoint": str(tmp_path / "driver-volume")}],
    )
    original_read = Path.read_text

    def filesystem_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        """Provide a synthetic kernel device table, leaving owned files real."""
        if path == Path("/proc/devices"):
            return "Character devices:\n 13 input\n241 hidraw\n"
        return original_read(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(subprocess, "run", boundary)
    monkeypatch.setattr(Path, "read_text", filesystem_text)
    if damage != "none":
        with pytest.raises(
            native_remote.NativeError,
            match=(
                r"backing is not proven|render node|not qualified|"
                r"profile is unavailable|absolute/literal"
            ),
        ):
            native_remote.Operations(request).dispatch()
    else:
        result = native_remote.Operations(request).dispatch()
        assert result["root_pin"] == native_remote.identity(shared.stat())
        assert result["runtime_local"] == "/socket-root/session"
        assert result["runtime_host"] == str(runtime / "session")
        assert result["driver_mount"] == {
            "name": "fixture-driver",
            "source": str(tmp_path / "driver-volume"),
        }
        assert result["device_rules"] == ["c 13:* rwm", "c 241:* rwm"]
        assert result["stop_container_on_exit"] is True
        assert result["image"] == IMAGE
        assert result["snapshot"] == {
            "session_count": 0,
            "lobbies": [],
            "containers": [],
        }
    assert list(shared.iterdir()) == []
    assert not any(
        call[0][1] in {"run", "pull", "load", "restart"}
        for call in boundary.calls
        if call[0][0] == "docker"
    )


def test_native_expired_deadline_refuses_before_starting_an_external_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finite request lifetime is enforced even before the first subprocess starts."""
    ticks = iter([100.0, 121.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    boundary = ProcessTranscript()
    monkeypatch.setattr(subprocess, "run", boundary)
    service = native_remote.Operations(native_request(tmp_path, "image_status"))
    with pytest.raises(native_remote.NativeError, match="deadline expired"):
        service.dispatch()
    assert boundary.calls == []


@pytest.mark.parametrize("mismatch", [False, True])
def test_deployment_publication_requires_both_tags_to_match_verified_digest(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
    *,
    mismatch: bool,
) -> None:
    """Published preparation cannot trust a mutable tag without digest agreement."""
    service, request, boundary = deployment
    repository = "ghcr.io/dafrenchyman/batocera-gow-full-x86"
    published = repository + "@sha256:" + "c" * 64
    immutable = repository + ":sha-" + "d" * 40
    latest = repository + ":latest"
    request.update(
        local=False, image=published, sha_reference=immutable, latest_reference=latest
    )
    for reference in (immutable, latest):
        boundary.docker("pull", reference, privileged=True)
        boundary.docker(
            "image",
            "inspect",
            reference,
            output=[
                {
                    "RepoDigests": [
                        repository + "@sha256:" + "f" * 64
                        if mismatch and reference == latest
                        else published
                    ]
                }
            ],
            privileged=True,
        )
    boundary.docker("pull", published, privileged=True)
    boundary.docker(
        "image", "inspect", published, output=[image_observation()], privileged=True
    )
    boundary.docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "/opt/gow-full-x86/check-runtime.sh",
        published,
        privileged=True,
    )
    if mismatch:
        with pytest.raises(operations.RemoteError, match="digest differs"):
            service.dispatch(request)
        marker = record(
            decode((service.root / "deployment.json").read_text(encoding="utf-8"))
        )
        assert "prepared_image" not in marker
        assert not any(
            call[0] == ("sudo", "-n", "docker", "pull", published)
            for call in boundary.calls
        )
    else:
        assert service.dispatch(request)["image"] == published
        marker = record(
            decode((service.root / "deployment.json").read_text(encoding="utf-8"))
        )
        assert marker["prepared_image"] == published
        assert marker["image_id"] == IMAGE
        assert [
            call[0][-1] for call in boundary.calls if call[0][3:4] == ("pull",)
        ] == [immutable, latest, published]
    assert not service.home.exists()


def test_deployment_native_home_requires_registered_matching_release(
    deployment: tuple[operations.Deployment, dict[str, Json], ProcessTranscript],
) -> None:
    """Require deployment ownership and a compatible marker for an existing home."""
    service, request, _boundary = deployment
    service.dispatch(request)
    service.home.mkdir()
    sentinel = service.home / "save"
    sentinel.write_text("persistent-state", encoding="utf-8")
    request["action"] = "read-registration"
    with pytest.raises(operations.RemoteError, match="unowned occupied"):
        service.dispatch(request)
    ownership = service.root / "deployment.json"
    value = record(decode(ownership.read_text(encoding="utf-8")))
    value["registered"] = True
    ownership.write_text(json.dumps(value), encoding="utf-8")
    marker = service.home / ".gow-full-x86-state.json"
    marker.write_text('{"release":"42"}', encoding="utf-8")
    with pytest.raises(operations.RemoteError, match="another release"):
        service.dispatch(request)
    marker.write_text('{"release":"43.1"}', encoding="utf-8")
    assert service.dispatch(request)["owned"] is True
    assert sentinel.read_text(encoding="utf-8") == "persistent-state"
