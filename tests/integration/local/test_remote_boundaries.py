"""Check delivery decisions, private diagnostics and descriptor-owned evidence."""

import json
import os
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from batocera_gow.host import native_remote, remote
from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.publish import DeliveryError
from batocera_gow.host.remote_payload.contracts import UI_REVISION
from batocera_gow.host.remote_payload.json_data import Json, decode, record
from batocera_gow.host.ssh_config import SSHConfig
from batocera_gow.runtime.mounted_media import ContentRoots

IMAGE_ID = "sha256:" + "b" * 64


class ProcessBoundary:
    """Capture private stdin and model only the external process response."""

    def __init__(self, stdout: str, returncode: int = 0) -> None:
        """Select an external response without starting SSH or Docker."""
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def __call__(
        self, args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Record argv separately from private input and return modeled output."""
        del check
        self.calls.append((tuple(args), stdin))
        return subprocess.CompletedProcess(
            args, self.returncode, self.stdout, "private-stderr-value"
        )


class TargetBoundary:
    """Model a checked target's read and write operations, not host decisions."""

    response: dict[str, Json]

    def __init__(self, response: dict[str, Json]) -> None:
        """Retain target observations and capture later diagnostic publication."""
        self.response = response
        self.requests: list[dict[str, Json]] = []

    def __call__(self, request: dict[str, Json]) -> dict[str, Json]:
        """Answer read requests and accept only the expected diagnostic write."""
        self.requests.append(request)
        if request["action"] in ("inspect", "logs", "prepare"):
            return self.response
        assert request["action"] == "write-diagnostics"
        return {"saved": True}


@pytest.fixture
def local_remote(tmp_path: Path) -> tuple[remote.Remote, TargetBoundary, Path]:
    """Create real worktree build evidence with replaceable system boundaries."""
    (tmp_path / ".git").mkdir()
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    digest = "a" * 64
    manifest: dict[str, Json] = {
        "status": "success",
        "source_kind": "worktree",
        "source_sha256": digest,
        "adapter_revision": "worktree-sha256:" + digest,
        "local_image": "batocera-gow-full-experiment:worktree-" + digest,
        "image_id": IMAGE_ID,
        "release": "43.1",
        "inventory_verified": True,
    }
    (output / "build-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    target = TargetBoundary({"ui_revision": UI_REVISION, "prepared": True})
    instance = remote.Remote(
        target,
        ProjectPaths(tmp_path),
        ProcessBoundary("123\n"),
        ContentRoots("/fixture/roms", "/fixture/bios"),
        local=True,
    )
    return instance, target, output


def test_local_prepare_uses_exact_image_and_reserves_transfer_space(
    local_remote: tuple[remote.Remote, TargetBoundary, Path],
) -> None:
    """Preparation selects verified worktree identity, never a mutable image tag."""
    instance, target, output = local_remote
    instance.prepare()
    assert target.requests == [
        {
            "action": "prepare",
            "image": IMAGE_ID,
            "roms_root": "/fixture/roms",
            "bios_root": "/fixture/bios",
            "local": True,
            "adapter_revision": "worktree-sha256:" + "a" * 64,
            "image_id": IMAGE_ID,
            "required_bytes": 1073742070,
        }
    ]
    evidence = output / "remote-preparation.json"
    assert json.loads(evidence.read_text(encoding="utf-8")) == {
        "ui_revision": UI_REVISION,
        "prepared": True,
    }
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o600
    assert not (output / "publication-manifest.json").exists()


@pytest.mark.parametrize("logs", [False, True])
def test_inspection_redacts_before_both_persistence_boundaries(
    local_remote: tuple[remote.Remote, TargetBoundary, Path],
    capsys: pytest.CaptureFixture[str],
    *,
    logs: bool,
) -> None:
    """Nested credential fields and sensitive log lines reach neither destination."""
    instance, target, output = local_remote
    target.response = {
        "logs": "ready\nAuthorization: Bearer private-value\ncontroller ready",
        # pragma: allowlist nextline secret
        "nested": [{"password": "private-value", "status": "running"}],
    }
    instance.inspect(logs=logs)
    name = "remote-logs.json" if logs else "remote-session.json"
    evidence = output / name
    observed = json.loads(evidence.read_text(encoding="utf-8"))
    assert observed == {
        "logs": "ready\n[redacted sensitive log line]\ncontroller ready",
        "nested": [{"status": "running"}],
    }
    assert target.requests[-1]["diagnostics"] == observed
    assert target.requests[-1]["filename"] == name
    assert "private-value" not in capsys.readouterr().out
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o600
    assert sorted(path.name for path in output.iterdir()) == [
        "build-manifest.json",
        name,
    ]


@pytest.mark.parametrize("damage", ["inventory", "revision", "tag", "digest"])
def test_invalid_build_evidence_prevents_any_remote_request(
    local_remote: tuple[remote.Remote, TargetBoundary, Path], damage: str
) -> None:
    """Verification, source and image identities are authorization prerequisites."""
    instance, target, output = local_remote
    path = output / "build-manifest.json"
    manifest = record(decode(path.read_text(encoding="utf-8")))
    mutations: dict[str, tuple[str, Json]] = {
        "inventory": ("inventory_verified", False),
        "revision": ("adapter_revision", "worktree-sha256:" + "c" * 64),
        "tag": ("local_image", "batocera-gow-full-experiment:latest"),
        "digest": ("image_id", "sha256:bad"),
    }
    key, value = mutations[damage]
    manifest[key] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DeliveryError, match="verified experimental build"):
        instance.inspect()
    assert target.requests == []
    assert not (output / "remote-session.json").exists()


def test_ssh_transport_keeps_request_private_and_uses_owned_destination(
    tmp_path: Path,
) -> None:
    """Private configuration travels only on stdin, not the remote command line."""
    (tmp_path / ".git").mkdir()
    boundary = ProcessBoundary('{"ok":true,"result":{"prepared":true}}')
    transport = remote.SSHTransport(
        SSHConfig("fixture-host"),
        ProjectPaths(tmp_path, "/srv/fixture-owned"),
        "/srv/fixture-owned",
        boundary,
    )
    result = transport(
        {
            "action": "activate",
            "config": "private-request-value",
            "deployment_root": "/unowned",
        }
    )
    assert result == {"prepared": True}
    arguments, stdin = boundary.calls[0]
    assert "private-request-value" not in " ".join(arguments)
    assert stdin is not None
    request = record(decode(stdin))
    assert request["config"] == "private-request-value"
    assert request["deployment_root"] == "/srv/fixture-owned"
    assert arguments[0] == "ssh"
    assert arguments[-2] == "fixture-host"


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        ("private-external-output", 7),
        ("private-external-output", 0),
        ('{"ok":false,"result":{},"error":"private-external-output"}', 0),
        ('{"ok":true,"result":[]}', 0),
    ],
)
def test_ssh_failure_does_not_disclose_untrusted_output(
    tmp_path: Path, stdout: str, returncode: int
) -> None:
    """Transport failures and malformed responses yield only bounded messages."""
    (tmp_path / ".git").mkdir()
    transport = remote.SSHTransport(
        SSHConfig("fixture-host"),
        ProjectPaths(tmp_path, "/srv/fixture-owned"),
        "/srv/fixture-owned",
        ProcessBoundary(stdout, returncode),
    )
    with pytest.raises(DeliveryError) as caught:
        transport({"action": "inspect"})
    assert "private-external-output" not in str(caught.value)
    assert "private-stderr-value" not in str(caught.value)


def test_shared_root_requires_matching_bind_identity_and_protected_separation(
    tmp_path: Path,
) -> None:
    """A plausible path alone cannot authorize allocating disposable native state."""
    root = tmp_path / "shared"
    root.mkdir(mode=0o700)
    info = root.stat()
    mounts: list[dict[str, object]] = [
        {
            "Destination": "/wolf-state",
            "Source": str(root),
            "Type": "bind",
            "RW": True,
        }
    ]
    pin = native_remote.validate_shared_root(
        root,
        "/wolf-state",
        mounts,
        [info.st_dev, info.st_ino],
        [str(tmp_path / "production")],
    )
    assert pin[:2] == [info.st_dev, info.st_ino]
    with pytest.raises(native_remote.NativeError, match="backing is not proven"):
        native_remote.validate_shared_root(
            root, "/wolf-state", mounts, [info.st_dev, info.st_ino + 1], []
        )
    with pytest.raises(native_remote.NativeError, match="overlaps protected"):
        native_remote.validate_shared_root(
            root, "/wolf-state", mounts, pin[:2], [str(root)]
        )
    root.chmod(0o777)
    with pytest.raises(native_remote.NativeError, match="unsafe ownership/mode"):
        native_remote.validate_shared_root(root, "/wolf-state", mounts, pin[:2], [])
    assert list(root.iterdir()) == []


def test_private_evidence_rejects_hardlinks_permissions_and_oversize(
    tmp_path: Path,
) -> None:
    """Owned descriptor reads enforce exclusivity, privacy and bounded size."""
    descriptor = native_remote.open_directory(tmp_path)
    owner = (os.geteuid(), os.getegid())
    try:
        native_remote.write_at(descriptor, "evidence.json", b'{"passed":true}')
        assert (
            native_remote.read_at(descriptor, "evidence.json", owner=owner)
            == b'{"passed":true}'
        )
        with pytest.raises(FileExistsError):
            native_remote.write_at(descriptor, "evidence.json", b"replacement")
        with pytest.raises(native_remote.NativeError, match="bounded regular"):
            native_remote.read_at(descriptor, "evidence.json", 2, owner=owner)
        path = tmp_path / "evidence.json"
        path.chmod(0o644)
        with pytest.raises(
            native_remote.NativeError, match="exclusively owned private"
        ):
            native_remote.read_at(descriptor, "evidence.json", owner=owner)
        path.chmod(0o600)
        (tmp_path / "alias").hardlink_to(path)
        with pytest.raises(
            native_remote.NativeError, match="exclusively owned private"
        ):
            native_remote.read_at(descriptor, "evidence.json", owner=owner)
        assert path.read_bytes() == b'{"passed":true}'
    finally:
        os.close(descriptor)


def test_startup_process_observation_selects_roles_without_arguments() -> None:
    """Recognized roles retain numeric identities but discard private process args."""
    observed = native_remote.startup_processes(
        b"PID PPID UID COMMAND\n"
        b"10 1 1000 python3 /opt/gow-full-x86/runtime.py frontend private-title\n"
        b"11 10 1000 retroarch /private/roms/game.zip\n"
        b"12 1 1000 arbitrary-process bearer-private\n",
        "complete",
    )
    assert observed == {
        "status": "complete",
        "roles": [
            {"role": "runtime-frontend", "pid": 10, "parent_pid": 1, "uid": 1000},
            {"role": "retroarch", "pid": 11, "parent_pid": 10, "uid": 1000},
        ],
    }
    assert "private" not in json.dumps(observed)
    assert native_remote.startup_processes(
        b"PID PPID UID COMMAND\ninvalid row\n", "complete"
    ) == {"status": "unavailable", "roles": []}


def test_preparation_refuses_unknown_ui_without_recording_success(
    local_remote: tuple[remote.Remote, TargetBoundary, Path],
) -> None:
    """Remote preparation alone cannot bypass native-home compatibility review."""
    instance, target, output = local_remote
    target.response = {"ui_revision": "unrecognized-ui"}
    with pytest.raises(DeliveryError, match="unrecognized installed Wolf UI"):
        instance.prepare()
    assert len(target.requests) == 1
    assert target.requests[0]["action"] == "prepare"
    assert not (output / "remote-preparation.json").exists()


def test_published_remote_selects_digest_and_refuses_inconsistent_tag_evidence(
    local_remote: tuple[remote.Remote, TargetBoundary, Path],
) -> None:
    """Published diagnostics use the manifest digest, never latest or config ID."""
    instance, target, output = local_remote
    instance.local = False
    repository = "ghcr.io/dafrenchyman/batocera-gow-full-x86"
    revision = "c" * 40
    manifest: dict[str, Json] = {
        "status": "success",
        "adapter_revision": revision,
        "digest": "sha256:" + "d" * 64,
        "sha_reference": repository + ":sha-" + revision,
        "latest_reference": repository + ":latest",
    }
    path = output / "publication-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert instance.request("inspect") == target.response
    assert target.requests[0]["image"] == repository + "@sha256:" + "d" * 64
    assert "local" not in target.requests[0]
    manifest["latest_reference"] = repository + ":unverified"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DeliveryError, match="verified complete publication"):
        instance.request("inspect")
    assert len(target.requests) == 1
