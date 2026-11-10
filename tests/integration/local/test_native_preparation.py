"""Exercise native freshness before any transport effects using local fixtures."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.host.native_freshness import BuildSnapshot
from batocera_gow.host.native_preparation import open_native_session
from batocera_gow.host.native_remote import NativeError
from batocera_gow.host.settings import HostSettings
from batocera_gow.provenance import INPUT_FILES, declared_inputs, tree_source


class LocalImage:
    """Observe immutable local image checks without contacting a Docker daemon."""

    def __init__(self, image: str, *, inputs: str = "", source: str = "b" * 40) -> None:
        """Retain the supplied actual image identity and all inspection requests."""
        self.image = image
        self.calls: list[str] = []
        self.labels: dict[str, object] = {
            "org.opencontainers.image.revision": source,
            "org.opencontainers.image.version": "43.1",
            "io.gow.full-x86.experimental": "true",
            "io.gow.full-x86.input.sha256": "c" * 64,
            "io.gow.full-x86.source.kind": (
                "worktree" if source.startswith("worktree-sha256:") else "git"
            ),
            "io.gow.full-x86.source.sha256": inputs,
            "io.gow.full-x86.declared-inputs.sha256": inputs,
        }

    def inspect(self, image: str) -> dict[str, object]:
        """Return the actual available immutable identity, not a mutable tag."""
        self.calls.append(image)
        return {"Id": self.image, "Config": {"Labels": self.labels}}

    def save(self, image: str, destination: Path, timeout: float) -> None:
        """Write synthetic archive bytes only at the explicit process seam."""
        assert image == self.image
        assert 0 < timeout <= 300
        destination.write_bytes(b"synthetic image archive")


@pytest.fixture
def built_checkout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create complete declared inputs and stock-verified committed provenance."""
    root = tmp_path / "checkout"
    for relative in (
        "src/batocera_gow/runtime",
        "build-assets/runtime",
        "tests/assets/input",
    ):
        (root / relative).mkdir(parents=True)
    for name in INPUT_FILES:
        (root / name).write_text("fixture", encoding="utf-8")
    stage = root / "output/runtime"
    (stage / "batocera_gow/runtime").mkdir(parents=True)
    source = b'"""Synthetic runtime module."""\n'
    (root / "src/batocera_gow/runtime/example.py").write_bytes(source)
    (stage / "batocera_gow/runtime/example.py").write_bytes(source)
    manifest = root / "output/build.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "success",
                "inventory_verified": True,
                "release": "43.1",
                "image_id": "sha256:" + "a" * 64,
                "adapter_revision": "b" * 40,
                "input_sha256": "c" * 64,
                "declared_inputs": declared_inputs(root),
                "runtime_inputs": tree_source(stage),
            }
        ),
        encoding="utf-8",
    )
    return root, manifest, stage


def test_matching_committed_and_dirty_inputs_accept_exact_local_image(
    built_checkout: tuple[Path, Path, Path],
) -> None:
    """Both source modes compare the same full canonical current-input record."""
    root, manifest, stage = built_checkout
    inputs = declared_inputs(root)["sha256"]
    for source in ("b" * 40, "worktree-sha256:" + inputs):
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["adapter_revision"] = source
        manifest.write_text(json.dumps(document), encoding="utf-8")
        local = LocalImage("sha256:" + "a" * 64, inputs=inputs, source=source)
        snapshot = BuildSnapshot.verify(root, manifest, stage, local)
        assert snapshot.image == "sha256:" + "a" * 64
        assert local.calls == [snapshot.image]


def _damage_manifest(manifest: Path, damage: str) -> None:
    """Exercise missing, malformed and incomplete success evidence separately."""
    if damage == "missing":
        manifest.unlink()
    elif damage == "invalid":
        manifest.write_text("not JSON", encoding="utf-8")
    else:
        document = json.loads(manifest.read_text(encoding="utf-8"))
        if damage == "worktree":
            document["adapter_revision"] = "worktree-sha256:" + "e" * 64
        elif damage == "unverified":
            document["inventory_verified"] = False
        else:
            del document["declared_inputs"]["entries"]
        manifest.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "invalid",
        "unverified",
        "worktree",
        "incomplete",
        "module",
        "added",
        "deleted",
        "mode",
        "asset",
        "dependency",
        "stage",
    ],
)
def test_stale_build_refuses_before_local_image_or_transport(
    built_checkout: tuple[Path, Path, Path],
    damage: str,
) -> None:
    """No native preparation can repair, relabel or fall back from stale inputs."""
    root, manifest, stage = built_checkout
    if damage in ("missing", "invalid", "unverified", "incomplete", "worktree"):
        _damage_manifest(manifest, damage)
    elif damage == "module":
        (root / "src/batocera_gow/runtime/example.py").write_bytes(b"changed")
    elif damage == "added":
        (root / "src/added.py").write_bytes(b"added")
    elif damage == "deleted":
        (root / "src/batocera_gow/runtime/example.py").unlink()
    elif damage == "mode":
        (root / "src/batocera_gow/runtime/example.py").chmod(0o700)
    elif damage == "asset":
        (root / "build-assets/runtime/new.conf").write_bytes(b"new")
    elif damage == "dependency":
        (root / "uv.lock").write_bytes(b"changed")
    else:
        (stage / "batocera_gow/runtime/example.py").write_bytes(b"swapped")
    local = LocalImage("sha256:" + "a" * 64)
    with pytest.raises(NativeError, match=r"explicit.*build|build.*explicit"):
        BuildSnapshot.verify(root, manifest, stage, local)
    assert local.calls == []


def test_wrong_local_image_and_mid_run_drift_cannot_pass(
    built_checkout: tuple[Path, Path, Path],
) -> None:
    """A matching tag or old snapshot cannot establish current-checkout evidence."""
    root, manifest, stage = built_checkout
    with pytest.raises(NativeError, match=r"explicit.*build|build.*explicit"):
        BuildSnapshot.verify(
            root,
            manifest,
            stage,
            LocalImage("sha256:" + "e" * 64, inputs=declared_inputs(root)["sha256"]),
        )
    snapshot = BuildSnapshot.verify(
        root,
        manifest,
        stage,
        LocalImage("sha256:" + "a" * 64, inputs=declared_inputs(root)["sha256"]),
    )
    (root / "uv.lock").write_bytes(b"changed after setup")
    with pytest.raises(NativeError, match="drift"):
        snapshot.assert_current()


@pytest.mark.parametrize(
    "label",
    [
        "org.opencontainers.image.revision",
        "org.opencontainers.image.version",
        "io.gow.full-x86.experimental",
        "io.gow.full-x86.input.sha256",
        "io.gow.full-x86.source.kind",
        "io.gow.full-x86.declared-inputs.sha256",
    ],
)
@pytest.mark.parametrize("disposition", ["missing", "mismatched"])
def test_local_image_metadata_must_bind_exact_canonical_inputs(
    built_checkout: tuple[Path, Path, Path],
    label: str,
    disposition: str,
) -> None:
    """An exact image ID cannot replace canonical source/stock metadata."""
    root, manifest, stage = built_checkout
    image = "sha256:" + "a" * 64
    local = LocalImage(image, inputs=declared_inputs(root)["sha256"])
    if disposition == "missing":
        del local.labels[label]
    else:
        local.labels[label] = "unrelated"
    with pytest.raises(NativeError, match=r"explicit.*build|build.*explicit"):
        BuildSnapshot.verify(root, manifest, stage, local)
    assert local.calls == [image]


def test_dirty_image_label_must_match_the_same_canonical_input_digest(
    built_checkout: tuple[Path, Path, Path],
) -> None:
    """Dirty image metadata cannot bind an unrelated historical worktree."""
    root, manifest, stage = built_checkout
    inputs = declared_inputs(root)["sha256"]
    source = "worktree-sha256:" + inputs
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["adapter_revision"] = source
    manifest.write_text(json.dumps(document), encoding="utf-8")
    image = "sha256:" + "a" * 64
    local = LocalImage(image, inputs=inputs, source=source)
    local.labels["io.gow.full-x86.source.sha256"] = "e" * 64
    with pytest.raises(NativeError, match=r"explicit.*build|build.*explicit"):
        BuildSnapshot.verify(root, manifest, stage, local)
    assert local.calls == [image]


@pytest.mark.parametrize("consumer", ["session", "cli"])
def test_native_consumers_use_selected_file_docker_snapshot(
    built_checkout: tuple[Path, Path, Path],
    tmp_path: Path,
    consumer: str,
) -> None:
    """Selected-file Docker reaches freshness without ambient settings rereads."""
    root, manifest, stage = built_checkout
    marker = tmp_path / "docker-request.json"
    docker = tmp_path / "docker.py"
    docker.write_text(
        "import json,pathlib,sys\n"
        f"pathlib.Path({str(marker)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('[]')\n",
        encoding="utf-8",
    )
    dotenv = tmp_path / "selected.env"
    values = {
        "DOCKER": shlex.join([sys.executable, str(docker)]),
        "BATOCERA_GOW_SSH_TARGET": "fixture",
        "BATOCERA_GOW_HOST_ROOT": "/owned",
        "BATOCERA_GOW_BUILD_MANIFEST": str(manifest),
        "BATOCERA_GOW_STOCK_MANIFEST": str(tmp_path / "stock.json"),
        "BATOCERA_GOW_RUNTIME_ROOT": str(stage),
        "BATOCERA_GOW_RENDER_NODE": "/dev/dri/renderD128",
        "BATOCERA_GOW_VIDEO_CAPS": "caps",
        "BATOCERA_GOW_ROMS_ROOT": "/srv/roms",
        "BATOCERA_GOW_BIOS_ROOT": "/srv/bios",
    }
    dotenv.write_text(
        "".join(f"{name}='{value}'\n" for name, value in values.items()),
        encoding="utf-8",
    )
    if consumer == "session":
        settings = HostSettings.resolve(env_file=dotenv, environ={})
        dotenv.write_text("DOCKER=must-not-reread\n", encoding="utf-8")
        with (
            pytest.raises(NativeError, match="explicit batocera-gow-build"),
            open_native_session(
                settings,
                project_root=root,
                enabled=True,
                authorized_target="fixture",
                authorized_root="/owned",
                worker_environment={},
            ),
        ):
            pytest.fail("Invalid local image cannot authorize remote activity")
    else:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("BATOCERA_GOW_") and key != "DOCKER"
        }
        result = subprocess.run(  # noqa: S603 - installed command with synthetic explicit settings only.
            [
                sys.executable,
                "-I",
                "-m",
                "batocera_gow.host.native_integration",
                "--env-file",
                str(dotenv),
                "--project-root",
                str(root),
                "run",
                "--authorize-native",
                "--native-authorized-target",
                "fixture",
                "--native-authorized-root",
                "/owned",
            ],
            env=environment,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        assert result.returncode == 2
        assert "explicit batocera-gow-build" in result.stderr
    assert json.loads(marker.read_bytes()) == [
        "image",
        "inspect",
        "sha256:" + "a" * 64,
    ]
