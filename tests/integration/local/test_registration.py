"""Preservation, ownership and activation behavior at real filesystem boundaries."""

import json
import os
import stat
import tomllib
from pathlib import Path

import pytest

from batocera_gow.host import registration as reg
from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.publish import DeliveryError, SystemRunner
from batocera_gow.host.remote import Remote
from batocera_gow.host.remote_payload.activation import activate_config, source_hash
from batocera_gow.host.remote_payload.activity import ActivityError, require_idle
from batocera_gow.host.remote_payload.contracts import REPOSITORY, TITLE, UI_REVISION
from batocera_gow.host.remote_payload.json_data import Json, record, text
from batocera_gow.runtime.mounted_media import ContentRoots

IMAGE = REPOSITORY + "@sha256:" + "a" * 64
MOUNTS = [
    "/ROMs:/home/retro/userdata/roms:ro",
    "/ROMs/bioses:/home/retro/userdata/bios:ro",
]
OLD_APP = """[[profiles.apps]]
# Keep the existing library exactly as it was.
title = "Batocera"
start_audio_server = true
[profiles.apps.runner]
type = "docker"
name = "Batocera"
image = "ghcr.io/dafrenchyman/batocera-gow:latest"
mounts = ["/ROMs:/userdata/roms:ro", "/ROMs/bioses:/userdata/bios:ro"]
"""
CONFIG = (
    """# Pairing settings must not be backed up or rewritten.
uuid = "fixture-not-a-secret"
[[profiles]]
id = "moonlight"
name = "Moonlight"
[[profiles.apps]]
title = "Desktop"
[profiles.apps.runner]
type = "docker"
name = "Desktop"
image = "desktop:latest"

[[profiles]]
id = "user"
name = "User"
"""
    + OLD_APP
    + """
[[profiles]]
id = "guest"
name = "Guest"
"""
)


def test_insertion_preserves_unrelated_bytes_profiles_and_capabilities() -> None:
    """Only the owned app is added, retaining unrelated original TOML verbatim."""
    result = reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS)
    assert OLD_APP in result
    before, after = tomllib.loads(CONFIG), tomllib.loads(result)
    assert reg.without_experiment(before) == reg.without_experiment(after)
    app = next(profile for profile in after["profiles"] if profile["id"] == "user")[
        "apps"
    ][-1]
    host = json.loads(app["runner"]["base_create_json"])["HostConfig"]
    assert host["IpcMode"] == "private"
    assert host["Privileged"] is False
    assert app["start_audio_server"] is True
    assert app["start_virtual_compositor"] is True
    assert app["runner"]["mounts"] == MOUNTS


def test_owned_idempotence_and_local_update_preserve_other_apps() -> None:
    """An owned app can update to a verified local identity without duplication."""
    initial = reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS)
    assert reg.transform_config(initial, IMAGE, mounts=MOUNTS, owned=True) == initial
    local = "sha256:" + "b" * 64
    result = reg.transform_config(initial, local, mounts=MOUNTS, owned=True)
    assert OLD_APP in result
    assert reg.without_experiment(tomllib.loads(initial)) == reg.without_experiment(
        tomllib.loads(result)
    )
    apps = [
        app
        for profile in tomllib.loads(result)["profiles"]
        for app in profile.get("apps", [])
        if reg.experiment(app)
    ]
    assert len(apps) == 1
    assert apps[0]["runner"]["image"] == local


@pytest.mark.parametrize(
    "image",
    [
        "batocera-gow-full-experiment:latest",
        REPOSITORY + ":latest",
        "ghcr.io/dafrenchyman/batocera-gow@sha256:" + "b" * 64,
        "ghcr.io/dafrenchyman/batocera-gow-full-experiment@sha256:" + "b" * 64,
    ],
)
def test_registration_refuses_mutable_or_foreign_images(image: str) -> None:
    """Only the dedicated immutable registry image or exact local ID is permitted."""
    with pytest.raises(reg.RegistrationError):
        reg.transform_config(CONFIG, image, mounts=MOUNTS)


@pytest.mark.parametrize(
    ("config", "owned"),
    [
        (CONFIG.replace('title = "Desktop"', f'title = "{TITLE}"'), True),
        (CONFIG + '\n[[profiles]]\nid="user"\n', False),
    ],
)
def test_profile_and_identity_collisions_refuse_mutation(
    config: str, *, owned: bool
) -> None:
    """A reserved title in another profile and duplicated user profile both fail."""
    with pytest.raises(reg.RegistrationError):
        reg.transform_config(config, IMAGE, mounts=MOUNTS, owned=owned)


def test_unowned_existing_app_and_changed_source_are_refused() -> None:
    """Neither identical content nor a caller hash grants missing ownership."""
    initial = reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS)
    with pytest.raises(reg.RegistrationError):
        reg.transform_config(initial, IMAGE, mounts=MOUNTS)
    with pytest.raises(reg.RegistrationError):
        reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS, expected_hash="0" * 64)


@pytest.mark.parametrize(
    ("sessions", "lobbies", "containers"),
    [
        ([{"paused": True}], [], []),
        ([], [{"id": "open"}], []),
        ({"error": True}, [], []),
        ([], {"success": False}, []),
        (
            [],
            [],
            [
                {
                    "Name": "/Steam_12345678-1234-1234-1234-123456789abc",
                    "State": {"Running": True},
                }
            ],
        ),
        ([], [], [{"Name": "/Batocera_123456789", "State": {"Paused": True}}]),
    ],
)
def test_idle_refuses_busy_or_unknown_observations(
    sessions: object, lobbies: object, containers: list[object]
) -> None:
    """Unknown API state and either app runner identity cannot be treated as idle."""
    with pytest.raises(ActivityError):
        require_idle(sessions, lobbies, containers)
    require_idle({"sessions": []}, {"lobbies": []}, [])


def test_activation_atomically_preserves_metadata_without_private_backup(
    tmp_path: Path,
) -> None:
    """Replace the inode while preserving owner, permissions and extended attributes."""
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    path.chmod(0o640)
    os.setxattr(path, "user.gow-test", b"retained")
    before = path.stat()
    ownership: list[bool] = []
    restarts: list[str] = []
    new = reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS)
    assert activate_config(
        path,
        source_hash(CONFIG),
        new,
        lambda: None,
        lambda: restarts.append("wolf-wolf-1"),
        ownership.append,
    )
    after = path.stat()
    assert before.st_ino != after.st_ino
    assert (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)) == (
        before.st_uid,
        before.st_gid,
        0o640,
    )
    assert os.getxattr(path, "user.gow-test") == b"retained"
    assert path.read_text(encoding="utf-8") == new
    assert restarts == ["wolf-wolf-1"]
    assert ownership == [False, True]
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("concurrent", [False, True])
def test_final_idle_or_concurrent_edit_blocks_activation(
    tmp_path: Path, *, concurrent: bool
) -> None:
    """A final idle refusal or changed source leaves activation effects untouched."""
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    count = 0
    restarts: list[bool] = []
    ownership: list[bool] = []

    def idle() -> None:
        nonlocal count
        count += 1
        if concurrent:
            path.write_text(CONFIG + "# Concurrent edit\n", encoding="utf-8")
        elif count == 2:
            message = "new lobby"
            raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        activate_config(
            path,
            source_hash(CONFIG),
            "new",
            idle,
            lambda: restarts.append(True),
            ownership.append,
        )
    assert path.read_text(encoding="utf-8") == CONFIG + (
        "# Concurrent edit\n" if concurrent else ""
    )
    assert restarts == []
    assert ownership == []


def test_restart_failure_records_unactivated_state_and_allows_retry(
    tmp_path: Path,
) -> None:
    """Failed restart records inactive state; retry preserves identical bytes."""
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    new = reg.transform_config(CONFIG, IMAGE, mounts=MOUNTS)
    ownership: list[bool] = []

    def broken() -> None:
        message = "restart failed"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        activate_config(
            path, source_hash(CONFIG), new, lambda: None, broken, ownership.append
        )
    assert path.read_text(encoding="utf-8") == new
    assert ownership == [False]
    inode = path.stat().st_ino
    assert not activate_config(
        path,
        source_hash(new),
        new,
        lambda: None,
        lambda: None,
        ownership.append,
        retry_restart=True,
    )
    assert path.stat().st_ino == inode
    assert ownership == [False, True]


def test_remote_registration_uses_real_transform_and_transaction(
    tmp_path: Path,
) -> None:
    """Transport replacement preserves the actual host transform/activation behavior."""
    (tmp_path / ".git").mkdir()
    paths = ProjectPaths(tmp_path)
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    publication: dict[str, Json] = {
        "status": "success",
        "adapter_revision": "a" * 40,
        "digest": "sha256:" + "a" * 64,
        "sha_reference": REPOSITORY + ":sha-" + "a" * 40,
        "latest_reference": REPOSITORY + ":latest",
    }
    (output / "publication-manifest.json").write_text(
        json.dumps(publication), encoding="utf-8"
    )
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    restarts: list[str] = []
    baseline = record(tomllib.loads(CONFIG))

    def transport(request: dict[str, Json]) -> dict[str, Json]:
        if request["action"] == "read-registration":
            return {
                "config": path.read_text(encoding="utf-8"),
                "owned": False,
                "ui_revision": UI_REVISION,
                "profiles": baseline,
            }
        assert request["action"] == "activate"
        changed = activate_config(
            path,
            text(request["expected_hash"]),
            text(request["config"]),
            lambda: require_idle([], [], []),
            lambda: restarts.append("wolf-wolf-1"),
            lambda _active: None,
        )
        profiles = record(tomllib.loads(path.read_text(encoding="utf-8")))
        for data in (baseline, profiles):
            profile_items = data["profiles"]
            assert isinstance(profile_items, list)
            for profile in profile_items:
                assert isinstance(profile, dict)
                app_items = profile.get("apps", [])
                assert isinstance(app_items, list)
                for app in app_items:
                    assert isinstance(app, dict)
                    app.pop("start_audio_server", None)
        return {
            "config": path.read_text(encoding="utf-8"),
            "profiles": profiles,
            "changed": changed,
        }

    Remote(
        transport, paths, SystemRunner(paths, {}), ContentRoots("/ROMs", "/ROMs/bioses")
    ).register()
    assert restarts == ["wolf-wolf-1"]
    assert OLD_APP in path.read_text(encoding="utf-8")
    assert (
        json.loads((output / "remote-registration.json").read_text(encoding="utf-8"))[
            "registered"
        ]
        is True
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "failed"),
        ("inventory_verified", False),
        ("release", "42"),
        ("image_id", "sha256:123"),
        ("local_image", "foreign:latest"),
    ],
)
def test_local_deployment_rejects_invalid_build_evidence(
    tmp_path: Path, field: str, value: Json
) -> None:
    """Invalid local provenance cannot bypass publication by selecting local mode."""
    (tmp_path / ".git").mkdir()
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    manifest: dict[str, Json] = {
        "status": "success",
        "inventory_verified": True,
        "release": "43.1",
        "adapter_revision": "a" * 40,
        "image_id": "sha256:" + "b" * 64,
        "local_image": "batocera-gow-full-experiment:sha-" + "a" * 40,
    }
    manifest[field] = value
    (output / "build-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    paths = ProjectPaths(tmp_path)
    operator = Remote(
        lambda request: {},  # noqa: ARG005 - Retain the protocol's keyword name.
        paths,
        SystemRunner(paths, {}),
        ContentRoots("/ROMs", "/ROMs/bioses"),
        local=True,
    )
    with pytest.raises(DeliveryError, match="verified experimental build"):
        operator.image()
