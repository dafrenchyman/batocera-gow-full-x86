"""Exercise preparation ownership and integrity through the transport boundary."""

import base64
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from batocera_gow.host import native_preparation, native_remote
from batocera_gow.host.native_freshness import BuildSnapshot, DockerImages, LocalImages
from batocera_gow.host.native_integration import Artifacts, NativeConfig
from batocera_gow.host.native_matrix import RECEIVER_CASES
from batocera_gow.host.native_preparation import NativeSession, require_authorization
from batocera_gow.host.native_remote import NativeError, record, sequence, text
from batocera_gow.provenance import INPUT_FILES, declared_inputs, tree_source
from batocera_gow.runtime.media_catalog import EMULATOR_CASES, load_catalog
from batocera_gow.runtime.mounted_media import ContentRoots
from tests.integration.local.test_native_integration import MatrixWorld, matrix_config


class Images:
    """Supply a local immutable image and synthetic save archive without Docker."""

    def __init__(self, inputs: str) -> None:
        """Observe only explicit saves through the local process boundary."""
        self.saves = 0
        self.inputs = inputs

    def inspect(self, image: str) -> dict[str, object]:
        """Observe only the requested immutable image."""
        return {
            "Id": image,
            "Config": {
                "Labels": {
                    "org.opencontainers.image.revision": "b" * 40,
                    "org.opencontainers.image.version": "43.1",
                    "io.gow.full-x86.experimental": "true",
                    "io.gow.full-x86.input.sha256": "c" * 64,
                    "io.gow.full-x86.source.kind": "git",
                    "io.gow.full-x86.declared-inputs.sha256": self.inputs,
                }
            },
        }

    def save(self, image: str, destination: Path, timeout: float) -> None:
        """Write harmless archive bytes through the local process boundary."""
        assert image == "sha256:" + "a" * 64
        assert 0 < timeout <= 300
        self.saves += 1
        destination.write_bytes(
            gzip.compress(b"synthetic docker-save archive", compresslevel=1, mtime=0)
        )


class Target:
    """Model exact images and independently owned state at the transport seam."""

    def __init__(self, *, present: bool = False, failure: str = "") -> None:
        """Retain independent foreign state and injected boundary failures."""
        self.present = present
        self.failure = failure
        self.states: dict[str, str] = {"foreign-state": "foreign-owner"}
        self.actions: list[str] = []
        self.archive = bytearray()
        self.loads = 0

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Expose state and integrity results independently of host sequencing."""
        assert timeout > 0
        action = text(value["action"])
        self.actions.append(action)
        if action == "preflight":
            return {"wolf_id": "f" * 64, "root_pin": [1, 2, 3, 4, 5]}
        if action == "snapshot":
            return {
                "session_count": 1 if self.failure == "busy" else 0,
                "lobbies": [],
                "containers": [],
            }
        if action == "image_status":
            return {"present": self.present, "image": value["image"]}
        return self._owned_request(value, action)

    def _owned_request(
        self, value: dict[str, object], action: str
    ) -> dict[str, object]:
        """Model only owner-validated transfer and disposable-state operations."""
        name = text(value["case_id"])
        owner = text(value["token"])
        if action == "allocate":
            if name in self.states:
                msg = "Owned allocation already exists"
                raise NativeError(msg)
            self.states[name] = owner
            if self.failure == "lost-allocation" or (
                self.failure == "lost-transfer-allocation"
                and name != "native-session-reservation"
            ):
                msg = "Allocation response lost after remote creation"
                raise NativeError(msg)
            return {"pin": {"owner": owner}}
        if self.states.get(name) != owner:
            msg = "Foreign state must survive"
            raise NativeError(msg)
        if action == "remove_state":
            if self.failure == "cleanup" and name != "native-session-reservation":
                msg = "Owned cleanup unresolved"
                raise NativeError(msg)
            del self.states[name]
            return {"removed": True}
        if action == "image_chunk":
            if self.failure == "chunk":
                msg = "Transfer interrupted after allocation"
                raise NativeError(msg)
            assert value["offset"] == len(self.archive)
            self.archive.extend(base64.b64decode(text(value["data"]), validate=True))
            return {"offset": len(self.archive)}
        if action == "image_load":
            assert value["offset"] == len(self.archive)
            assert value["sha256"] == hashlib.sha256(self.archive).hexdigest()
            self.loads += 1
            self.present = True
            return {
                "image": "sha256:" + "e" * 64
                if self.failure == "identity"
                else value["image"]
            }
        msg = "Unexpected preparation effect"
        raise AssertionError(msg)


class FilesystemOperations(native_remote.Operations):
    """Replace only live service observations, retaining checked file operations."""

    def snapshot(self) -> dict[str, object]:
        """Report no local fixture containers or lobbies using disposable state."""
        return {"session_count": 0, "lobbies": [], "containers": []}

    def verified_image(self) -> dict[str, object]:
        """Supply the fixture image identity after the real local load child."""
        return {"Id": "sha256:" + "a" * 64}


class FilesystemTarget(Target):
    """Deliver host requests to actual owned-state and image-file operations."""

    def __init__(self, root: Path, *, busy_after_chunk: bool) -> None:
        """Keep external service observations independent of filesystem admission."""
        super().__init__()
        self.root = root
        self.busy_after_chunk = busy_after_chunk
        self.offsets: list[int] = []

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Use checked dispatch for allocation, transfer, loading and cleanup."""
        action = text(value["action"])
        if action == "preflight":
            self.actions.append(action)
            return {
                "wolf_id": "f" * 64,
                "root_pin": native_remote.identity(self.root.stat()),
            }
        if action == "snapshot" and self.busy_after_chunk and self.offsets:
            self.actions.append(action)
            return {"session_count": 1, "lobbies": [], "containers": []}
        return super().request(value, timeout)

    def _owned_request(
        self, value: dict[str, object], action: str
    ) -> dict[str, object]:
        """Apply the production marker, inode, offset, digest and cleanup checks."""
        result = FilesystemOperations(value).dispatch()
        if action == "image_chunk":
            offset = result["offset"]
            assert isinstance(offset, int)
            self.offsets.append(offset)
        return result


@pytest.fixture
def session_inputs(
    tmp_path: Path,
) -> tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts]:
    """Create matching real local provenance and explicit borrowed dependencies."""
    root = tmp_path / "checkout"
    for relative in (
        "src/batocera_gow/runtime",
        "build-assets/runtime",
        "tests/assets/input",
    ):
        (root / relative).mkdir(parents=True)
    for name in INPUT_FILES:
        (root / name).write_text("synthetic", encoding="utf-8")
    stage = root / "output/runtime"
    stage.mkdir(parents=True)
    image = "sha256:" + "a" * 64
    images = Images(declared_inputs(root)["sha256"])
    manifest = root / "output/build.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "success",
                "inventory_verified": True,
                "release": "43.1",
                "image_id": image,
                "declared_inputs": declared_inputs(root),
                "adapter_revision": "b" * 40,
                "input_sha256": "c" * 64,
                "runtime_inputs": tree_source(stage),
            }
        ),
        encoding="utf-8",
    )
    snapshot = BuildSnapshot.verify(root, manifest, stage, images)
    config = NativeConfig(
        image,
        "b" * 40,
        "c" * 64,
        ContentRoots("/srv/roms", "/srv/bios"),
        {"/opt/gow-full-x86/example.py": "d" * 64},
        "/dev/dri/renderD128",
        "caps",
        project_root=Path.cwd(),
        catalog=load_catalog(),
    )
    artifacts = Artifacts(tmp_path / "evidence", "a" * 32)
    return snapshot, config, images, artifacts


@pytest.mark.parametrize("busy_after_chunk", [False, True])
def test_large_archive_preparation_consumes_checked_chunks_and_cleans_partial_state(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    busy_after_chunk: bool,
) -> None:
    """Load exact multichunk bytes locally or refuse new contention before append."""
    snapshot, config, _images, artifacts = session_inputs
    source = tmp_path / "archive.bin"
    with source.open("wb") as stream:
        for _ in range(65):
            stream.write(os.urandom(1024**2))
        stream.write(b"\x00\xfflast-chunk\n")
    receipt = tmp_path / "load-receipt"
    executable = tmp_path / "docker"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import gzip, hashlib, io, json, pathlib, shutil, sys\n"
        "if sys.argv[1:3] == ['image', 'save']:\n"
        "    assert sys.argv[3:] == ['sha256:' + 'a' * 64]\n"
        f"    with pathlib.Path({str(source)!r}).open('rb') as source:\n"
        "        shutil.copyfileobj(source, sys.stdout.buffer)\n"
        "    sys.exit(0)\n"
        "assert sys.argv[1:] == ['image', 'load']\n"
        "encoded = sys.stdin.buffer.read()\n"
        "with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as actual, "
        f"pathlib.Path({str(source)!r}).open('rb') as expected:\n"
        "    digest = hashlib.sha256()\n"
        "    while block := expected.read(1048576):\n"
        "        assert actual.read(len(block)) == block\n"
        "        digest.update(block)\n"
        "    assert actual.read(1) == b''\n"
        f"pathlib.Path({str(receipt)!r}).write_text(json.dumps({{\n"
        "    'raw_sha256': digest.hexdigest(), 'encoded_bytes': len(encoded),\n"
        "    'encoded_sha256': hashlib.sha256(encoded).hexdigest()\n"
        "}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    root = tmp_path / "shared"
    foreign = root / "test-runs/foreign-state"
    foreign.mkdir(parents=True)
    (foreign / ".native-owner").write_bytes(b"foreign-owner")
    config = replace(
        config,
        host_root=str(root),
        uid=os.getuid() or 1000,
        gid=os.getgid() or 1000,
        # Coverage traces every character of this fixture's 89-MiB base64 request.
        # Retain checked dispatch and full chunks within a finite local budget.
        budgets=replace(config.budgets, call=60),
    )
    target = FilesystemTarget(root, busy_after_chunk=busy_after_chunk)
    session = NativeSession(
        snapshot, config, target, DockerImages([str(executable)]), artifacts
    )
    try:
        if busy_after_chunk:
            with (
                pytest.raises(InterruptedError, match="Unrelated native activity"),
                session,
            ):
                pytest.fail("Contention after a partial upload must refuse setup")
            assert target.offsets == [67108864]
            assert not receipt.exists()
            assert "image_load" not in target.actions
        else:
            with session:
                assert session.preparation["status"] == "passed"
                consumed = record(json.loads(receipt.read_bytes()))
                assert target.offsets == [67108864, consumed["encoded_bytes"]]
                with source.open("rb") as stream:
                    expected = hashlib.file_digest(stream, "sha256").hexdigest()
                assert consumed["raw_sha256"] == expected
                assert (
                    session.preparation["archive_sha256"] == consumed["encoded_sha256"]
                )
                assert session.preparation["archive_bytes"] == consumed["encoded_bytes"]
            for index, action in enumerate(target.actions):
                if action in {"image_chunk", "image_load"}:
                    assert target.actions[index - 1] == "snapshot"
        assert (foreign / ".native-owner").read_bytes() == b"foreign-owner"
        assert list((root / "test-runs").iterdir()) == [foreign]
        assert not list(artifacts.path.glob("native-image-*"))
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is True
        assert aggregate["full_regression_gate"] is False
    finally:
        artifacts.close()


@pytest.fixture
def docker_save_child(tmp_path: Path) -> list[str]:
    """Run an executable image producer with binary output and private failures."""
    child = tmp_path / "selected docker.py"
    child.write_text(
        "import os, pathlib, sys, time\n"
        f"pathlib.Path({str(child.with_suffix('.pid'))!r}).write_text(str(os.getpid()))\n"
        "mode, operation, action, image = sys.argv[1:]\n"
        "assert (operation, action) == ('image', 'save')\n"
        "assert image in ('sha256:fixture', 'sha256:' + 'a' * 64)\n"
        "if mode in ('raw-limit', 'raw-over', 'encoded-over'):\n"
        "    count = 4096 + int(mode == 'raw-over')\n"
        "    data = os.urandom(count) if mode == 'encoded-over' else b'\\0' * count\n"
        "    os.write(1, data)\n"
        "    if mode == 'raw-over':\n"
        "        time.sleep(60)\n"
        "    sys.exit(0)\n"
        "if mode != 'empty-timeout':\n"
        "    os.write(1, b'archive\\x00\\xff\\n')\n"
        "if mode == 'closed-timeout':\n"
        "    os.close(1)\n"
        "if mode == 'busy-timeout':\n"
        "    while True:\n"
        "        os.write(1, b'\\0' * 1024)\n"
        "        time.sleep(0.01)\n"
        "if mode in ('timeout', 'closed-timeout', 'empty-timeout'):\n"
        "    time.sleep(60)\n"
        "if mode == 'failure':\n"
        "    print('synthetic-private-diagnostic', file=sys.stderr)\n"
        "    sys.exit(17)\n",
        encoding="utf-8",
    )
    return [sys.executable, str(child)]


def test_save_stream_is_readable_private_owned_and_exclusive(
    tmp_path: Path, docker_save_child: list[str]
) -> None:
    """Selected argv produces exact bytes without delegating path ownership."""
    command = [*docker_save_child, "success"]
    images = DockerImages(command)
    command[:] = ["must-not-use-mutated-command"]
    with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
        directory = Path(temporary)
        archive = directory / "image.tar"
        images.save("sha256:fixture", archive, 5)
        encoded = archive.read_bytes()
        assert gzip.decompress(encoded) == b"archive\x00\xff\n"
        assert encoded[:8] == b"\x1f\x8b\x08\x00\x00\x00\x00\x00"
        assert archive.stat().st_uid == os.geteuid()
        assert archive.stat().st_mode & 0o777 == 0o600
        assert directory.stat().st_mode & 0o777 == 0o700
        with pytest.raises(NativeError) as failure:
            images.save("sha256:fixture", archive, 5)
        assert isinstance(failure.value.__cause__, FileExistsError)
        assert archive.read_bytes() == encoded
    assert not directory.exists()


@pytest.mark.parametrize(
    "mode",
    [
        "failure",
        "timeout",
        "closed-timeout",
        "empty-timeout",
        "busy-timeout",
        "missing",
    ],
)
def test_save_failure_retains_cause_and_owner_can_clean_partial_archive(
    tmp_path: Path, docker_save_child: list[str], mode: str
) -> None:
    """Failed children expose no private stderr and cannot obstruct owner cleanup."""
    command = (
        [str(tmp_path / "synthetic-private-missing")]
        if mode == "missing"
        else [*docker_save_child, mode]
    )
    with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
        directory = Path(temporary)
        archive = directory / "image.tar"
        with pytest.raises(NativeError) as failure:
            DockerImages(command).save(
                "sha256:fixture", archive, 0.3 if mode.endswith("timeout") else 5
            )
        assert "synthetic-private" not in str(failure.value)
        cause = failure.value.__cause__
        if mode == "failure":
            assert isinstance(cause, subprocess.CalledProcessError)
            assert cause.returncode == 17
        elif mode.endswith("timeout"):
            assert isinstance(cause, subprocess.TimeoutExpired)
        else:
            assert isinstance(cause, FileNotFoundError)
        assert archive.stat().st_uid == os.geteuid()
        assert archive.stat().st_mode & 0o777 == 0o600
        if mode in ("missing", "empty-timeout"):
            assert archive.read_bytes() == b""
        else:
            assert archive.read_bytes().startswith(b"\x1f\x8b\x08\x00")
        if mode != "missing":
            pid = int(Path(docker_save_child[1]).with_suffix(".pid").read_text())
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    assert not directory.exists()


@pytest.mark.parametrize("mode", ["success", "failure"])
def test_session_owns_real_save_archive_cleanup(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    docker_save_child: list[str],
    mode: str,
) -> None:
    """Preparation consumes real child bytes and removes owned storage on failure."""
    snapshot, config, _, artifacts = session_inputs
    images = DockerImages([*docker_save_child, mode])
    target = Target()
    try:
        if mode == "success":
            with NativeSession(snapshot, config, target, images, artifacts):
                assert gzip.decompress(target.archive) == b"archive\x00\xff\n"
                assert target.loads == 1
        else:
            with (
                pytest.raises(NativeError),
                NativeSession(snapshot, config, target, images, artifacts),
            ):
                pytest.fail("Failed save must not yield")
            assert target.archive == b""
            assert target.loads == 0
        assert not list(artifacts.path.glob("native-image-*"))
        assert target.states == {"foreign-state": "foreign-owner"}
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is True
    finally:
        artifacts.close()


@pytest.mark.parametrize("mode", ["raw-limit", "raw-over", "encoded-over"])
def test_save_bounds_raw_producer_and_compressed_storage_before_writing(
    tmp_path: Path,
    docker_save_child: list[str],
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Compressible overflow cannot escape the raw cap or leave a live producer."""
    monkeypatch.setattr("batocera_gow.host.native_freshness.MAX_IMAGE_BYTES", 4096)
    archive = tmp_path / "image.tar.gz"
    images = DockerImages([*docker_save_child, mode])
    if mode == "raw-limit":
        images.save("sha256:fixture", archive, 5)
        assert gzip.decompress(archive.read_bytes()) == b"\0" * 4096
    else:
        message = "bounded raw archive size" if mode == "raw-over" else "bounded native"
        with pytest.raises(NativeError, match=message):
            images.save("sha256:fixture", archive, 0.3 if mode == "encoded-over" else 5)
    assert archive.stat().st_size <= 4096
    pid = int(Path(docker_save_child[1]).with_suffix(".pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.fixture
def docker_archive_child(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a genuine one-layer Docker-save tar and an independent load consumer."""
    layer_bytes = io.BytesIO()
    with tarfile.open(fileobj=layer_bytes, mode="w") as layer:
        member = tarfile.TarInfo("usr/bin/fixture")
        payload = b"stock\x00\xffpayload\n"
        member.size = len(payload)
        member.uid, member.gid, member.mode, member.mtime = 123, 456, 0o751, 1700000123
        layer.addfile(member, io.BytesIO(payload))
        link = tarfile.TarInfo("fixture-link")
        link.type, link.linkname = tarfile.SYMTYPE, "usr/bin/fixture"
        layer.addfile(link)
    layer_data = layer_bytes.getvalue()
    config_data = json.dumps(
        {
            "architecture": "amd64",
            "os": "linux",
            "rootfs": {
                "type": "layers",
                "diff_ids": ["sha256:" + hashlib.sha256(layer_data).hexdigest()],
            },
        }
    ).encode()
    config_name = hashlib.sha256(config_data).hexdigest() + ".json"
    manifest = json.dumps(
        [{"Config": config_name, "RepoTags": [], "Layers": ["layer/layer.tar"]}]
    ).encode()
    source = tmp_path / "original-docker-save.tar"
    with tarfile.open(source, "w") as archive:
        for name, data in (
            ("manifest.json", manifest),
            (config_name, config_data),
            ("layer/layer.tar", layer_data),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    receipt = tmp_path / "consumed-docker-save.json"
    child = tmp_path / "docker"
    child.write_text(
        f"#!{sys.executable}\n"
        "import gzip, hashlib, io, json, pathlib, shutil, sys, tarfile\n"
        "if sys.argv[1:3] == ['image', 'save']:\n"
        "    assert sys.argv[3:] == ['sha256:' + 'a' * 64]\n"
        f"    with pathlib.Path({str(source)!r}).open('rb') as source:\n"
        "        shutil.copyfileobj(source, sys.stdout.buffer)\n"
        "    sys.exit(0)\n"
        "assert sys.argv[1:] == ['image', 'load']\n"
        "encoded = sys.stdin.buffer.read()\n"
        "raw = gzip.decompress(encoded)\n"
        "with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:\n"
        "    with archive.extractfile('manifest.json') as stream:\n"
        "        manifest, = json.load(stream)\n"
        "    assert manifest['RepoTags'] == []\n"
        "    assert manifest['Layers'] == ['layer/layer.tar']\n"
        "    with archive.extractfile(manifest['Config']) as stream:\n"
        "        config_data = stream.read()\n"
        "    expected_config_name = hashlib.sha256(config_data).hexdigest() + '.json'\n"
        "    assert manifest['Config'] == expected_config_name\n"
        "    config = json.loads(config_data)\n"
        "    assert config['architecture'] == 'amd64' and config['os'] == 'linux'\n"
        "    with archive.extractfile('layer/layer.tar') as stream:\n"
        "        layer_data = stream.read()\n"
        "    assert config['rootfs'] == {'type': 'layers', 'diff_ids': "
        "['sha256:' + hashlib.sha256(layer_data).hexdigest()]}\n"
        "with tarfile.open(fileobj=io.BytesIO(layer_data), mode='r:') as layer:\n"
        "    assert layer.getnames() == ['usr/bin/fixture', 'fixture-link']\n"
        "    member = layer.getmember('usr/bin/fixture')\n"
        "    assert (member.uid, member.gid, member.mode, member.mtime) == "
        "(123, 456, 0o751, 1700000123)\n"
        "    with layer.extractfile(member) as stream:\n"
        "        assert stream.read() == b'stock\\x00\\xffpayload\\n'\n"
        "    link = layer.getmember('fixture-link')\n"
        "    assert link.issym() and link.linkname == 'usr/bin/fixture'\n"
        f"pathlib.Path({str(receipt)!r}).write_text(json.dumps({{\n"
        "    'encoded_sha256': hashlib.sha256(encoded).hexdigest(),\n"
        "    'encoded_bytes': len(encoded),\n"
        "    'raw_sha256': hashlib.sha256(raw).hexdigest()\n"
        "}))\n",
        encoding="utf-8",
    )
    child.chmod(0o700)
    return child, source, receipt


@pytest.mark.parametrize("malformed", [False, True])
def test_session_checked_load_consumes_compressed_docker_tar_and_preserves_metadata(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    docker_archive_child: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    malformed: bool,
) -> None:
    """Real save/load children preserve exact tar bytes or fail with owned cleanup."""
    snapshot, config, _, artifacts = session_inputs
    executable, source, receipt = docker_archive_child
    if malformed:
        source.write_bytes(b"malformed Docker-save bytes\x00\xff")
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ["PATH"])
    root = tmp_path / "shared"
    foreign = root / "test-runs/foreign-state"
    foreign.mkdir(parents=True)
    (foreign / ".native-owner").write_bytes(b"foreign-owner")
    config = replace(
        config, host_root=str(root), uid=os.getuid() or 1000, gid=os.getgid() or 1000
    )
    target = FilesystemTarget(root, busy_after_chunk=False)
    session = NativeSession(
        snapshot, config, target, DockerImages([str(executable)]), artifacts
    )
    try:
        if malformed:
            with pytest.raises(NativeError, match="Bounded image load failed"), session:
                pytest.fail("Malformed Docker-save output must not pass preparation")
            assert not receipt.exists()
        else:
            with session:
                consumed = record(json.loads(receipt.read_bytes()))
                assert (
                    consumed["raw_sha256"]
                    == hashlib.sha256(source.read_bytes()).hexdigest()
                )
                assert (
                    session.preparation["archive_sha256"] == consumed["encoded_sha256"]
                )
                assert session.preparation["archive_bytes"] == consumed["encoded_bytes"]
                assert session.preparation["status"] == "passed"
        assert (foreign / ".native-owner").read_bytes() == b"foreign-owner"
        assert list((root / "test-runs").iterdir()) == [foreign]
        assert not list(artifacts.path.glob("native-image-*"))
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is True
        assert aggregate["full_regression_gate"] is False
    finally:
        artifacts.close()


class TransferClock:
    """Advance only the session's clock, leaving real subprocess timers untouched."""

    def __init__(self) -> None:
        """Start a deterministic transfer with no elapsed inter-operation delay."""
        self.value = 1000.0
        self.pending = 0.0

    def monotonic(self) -> float:
        """Apply accumulated upload time at the next session decision boundary."""
        self.value += self.pending
        self.pending = 0.0
        return self.value

    def now(self) -> float:
        """Observe ordinary coordinator calls without advancing their duration."""
        return self.value

    def sleep(self, seconds: float) -> None:
        """Advance bounded coordinator observations without real sleeps."""
        self.value += seconds


class TimedFilesystemTarget(FilesystemTarget):
    """Measure load allowances while consuming actual checked archive operations."""

    def __init__(
        self,
        root: Path,
        clock: TransferClock,
        timing: tuple[float, float, float],
        failure: NativeError | None,
    ) -> None:
        """Inject upload, final discovery and load elapsed seconds at their seams."""
        super().__init__(root, busy_after_chunk=False)
        self.clock = clock
        self.timing = timing
        self.load_failure = failure
        self.load_allowances: list[tuple[object, float]] = []

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Dispatch real file effects before simulating response delay or loss."""
        action = text(value["action"])
        if action == "image_load":
            self.load_allowances.append((value["timeout"], timeout))
        result = super().request(value, timeout)
        if action == "image_chunk":
            # Elapsed upload time is observed between the completed chunk call
            # and the session's final discovery, not inside an ordinary call.
            self.clock.pending = self.timing[0]
        elif action == "snapshot" and self.offsets:
            self.clock.value += self.timing[1]
        elif action == "image_load":
            self.clock.value += self.timing[2]
            if self.load_failure is not None:
                raise self.load_failure
        return result


@pytest.mark.parametrize(
    "scenario",
    [
        ((895.0, 3.0, 1.0), 2.0, ""),
        ((0.0, 3.0, 1.0), 300.0, ""),
        ((895.0, 5.0, 0.0), None, "deadline"),
        ((895.0, 3.0, 2.0), 2.0, "deadline"),
        ((0.0, 3.0, 300.0), 300.0, "deadline"),
        ((895.0, 3.0, 3.0), 2.0, "transport"),
    ],
    ids=[
        "discovery-reduces-load-budget",
        "within-budget-load-capped-at-300",
        "discovery-exhausts-whole-budget",
        "successful-load-at-whole-deadline",
        "successful-load-at-load-ceiling",
        "late-transport-error-preserved",
    ],
)
def test_session_load_respects_absolute_transfer_deadline(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    docker_archive_child: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: tuple[tuple[float, float, float], float | None, str],
) -> None:
    """Discovery and late load responses cannot endorse expired preparation."""
    timing, allowance, failure = scenario
    snapshot, config, _, artifacts = session_inputs
    executable, source, receipt = docker_archive_child
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ["PATH"])
    root = tmp_path / "shared"
    foreign = root / "test-runs/foreign-state"
    foreign.mkdir(parents=True)
    (foreign / ".native-owner").write_bytes(b"foreign-owner")
    config = replace(
        config, host_root=str(root), uid=os.getuid() or 1000, gid=os.getgid() or 1000
    )
    clock = TransferClock()
    monkeypatch.setattr(native_preparation, "time", clock)
    monkeypatch.setattr(native_preparation, "SystemClock", lambda: clock)
    original = NativeError("Load response lost after checked consumption")
    target = TimedFilesystemTarget(
        root, clock, timing, original if failure == "transport" else None
    )
    session = NativeSession(
        snapshot, config, target, DockerImages([str(executable)]), artifacts
    )
    try:
        if failure:
            message = "deadline expired" if failure == "deadline" else str(original)
            with pytest.raises(NativeError, match=message) as caught, session:
                pytest.fail("Expired or failed load must not yield a prepared session")
            if failure == "transport":
                assert caught.value is original
            assert session.preparation["status"] != "passed"
            with pytest.raises(NativeError, match="not ready"):
                session.run("frontend")
        else:
            with session:
                assert session.preparation["status"] == "passed"
        assert target.load_allowances == (
            [] if allowance is None else [(allowance, allowance)]
        )
        assert receipt.exists() is (allowance is not None)
        if receipt.exists():
            consumed = record(json.loads(receipt.read_bytes()))
            assert (
                consumed["raw_sha256"]
                == hashlib.sha256(source.read_bytes()).hexdigest()
            )
        assert target.actions[target.actions.index("image_chunk") - 1] == "snapshot"
        if "image_load" in target.actions:
            assert target.actions[target.actions.index("image_load") - 1] == "snapshot"
        assert (foreign / ".native-owner").read_bytes() == b"foreign-owner"
        assert list((root / "test-runs").iterdir()) == [foreign]
        assert not list(artifacts.path.glob("native-image-*"))
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is True
        assert aggregate["full_regression_gate"] is False
        if failure:
            assert aggregate["status"] == "failed"
            assert aggregate["evidence_complete"] is False
            assert record(aggregate["preparation"])["status"] != "passed"
    finally:
        artifacts.close()


@pytest.mark.parametrize("present", [False, True])
def test_preparation_reuses_or_transfers_once_and_preserves_foreign_state(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    *,
    present: bool,
) -> None:
    """Repeat preparation does not upload again and completion removes owned state."""
    snapshot, config, images, artifacts = session_inputs
    target = Target(present=present)
    try:
        with NativeSession(snapshot, config, target, images, artifacts) as session:
            session.prepare()
            assert session.preparation["reused"] is present
            assert target.loads == (0 if present else 1)
            assert "native-session-reservation" in target.states
        assert target.states == {"foreign-state": "foreign-owner"}
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["full_regression_gate"] is False
        assert aggregate["emulator_exit_coverage"] == "No emulator exit coverage"
    finally:
        artifacts.close()


@pytest.mark.parametrize("failure", ["chunk", "identity", "busy"])
def test_setup_failure_cleans_owned_allocations_before_fixture_yield(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    failure: str,
) -> None:
    """Failed transfer, loaded identity and contention cannot leak owned state."""
    snapshot, config, images, artifacts = session_inputs
    target = Target(failure=failure)
    try:
        with (
            pytest.raises((NativeError, InterruptedError)),
            NativeSession(snapshot, config, target, images, artifacts),
        ):
            pytest.fail("Nonpassing preparation must not yield")
        assert target.states == {"foreign-state": "foreign-owner"}
        if failure == "busy":
            assert "allocate" not in target.actions
    finally:
        artifacts.close()


def test_unresolved_cleanup_blocks_later_cases_and_retains_ownership_evidence(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
) -> None:
    """An unresolved owned archive is not converted to a passing session."""
    snapshot, config, images, artifacts = session_inputs
    target = Target(failure="cleanup")
    session = NativeSession(snapshot, config, target, images, artifacts)
    try:
        with pytest.raises(NativeError, match="cleanup"), session:
            pytest.fail("Unresolved transfer cleanup must fail setup")
        with pytest.raises(NativeError):
            session.run("frontend")
        assert target.states["foreign-state"] == "foreign-owner"
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["status"] == "failed"
        assert aggregate["cleanup_complete"] is False
    finally:
        artifacts.close()


@pytest.mark.parametrize(
    ("workers", "environment"),
    [("2", {}), ("auto", {}), (None, {"PYTEST_XDIST_WORKER": "gw0"})],
)
def test_native_authorization_refuses_unsafe_workers(
    workers: str | None,
    environment: dict[str, str],
) -> None:
    """Session scope never substitutes for actual serial execution."""
    with pytest.raises(NativeError, match="parallel"):
        require_authorization(
            enabled=True,
            target="fixture",
            authorized_target="fixture",
            host_root="/owned",
            authorized_root="/owned",
            workers=workers,
            worker_environment=environment,
        )


@pytest.mark.parametrize(
    ("enabled", "target", "root"),
    [
        (False, "fixture", "/owned"),
        (True, "other", "/owned"),
        (True, "fixture", "/foreign"),
    ],
)
def test_settings_cannot_grant_native_resource_authorization(
    *,
    enabled: bool,
    target: str,
    root: str,
) -> None:
    """Known connection/settings data still needs independent explicit permission."""
    with pytest.raises(NativeError, match="authorization"):
        require_authorization(
            enabled=enabled,
            target="fixture",
            authorized_target=target,
            host_root="/owned",
            authorized_root=root,
            workers=None,
            worker_environment={},
        )


@pytest.mark.parametrize("failure", ["lost-allocation", "lost-transfer-allocation"])
def test_lost_allocation_response_retains_recovery_and_blocks_success(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    failure: str,
) -> None:
    """Response loss cannot erase successful remote writes from cleanup accounting."""
    snapshot, config, images, artifacts = session_inputs
    target = Target(failure=failure)
    session = NativeSession(snapshot, config, target, images, artifacts)
    try:
        with pytest.raises(NativeError, match="cleanup"), session:
            pytest.fail("Uncertain allocation must not yield")
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is False
        assert aggregate["status"] == "failed"
        assert aggregate["reservation"] is not None
        assert "native-session-reservation" in target.states
        assert target.states["foreign-state"] == "foreign-owner"
        assert "remove_state" not in target.actions
        if failure == "lost-transfer-allocation":
            transfer = record(record(aggregate["preparation"])["transfer"])
            assert transfer["case_id"] in target.states
            assert transfer["pin"] is None
            assert transfer["cleanup_complete"] is False
            assert len(text(transfer["owner_marker_sha256"])) == 64
        with pytest.raises(NativeError):
            session.run("frontend")
    finally:
        artifacts.close()


class SessionWorld(MatrixWorld):
    """Keep session reservation independent from modeled per-case remote resources."""

    def __init__(self, *, mismatch: bool = False) -> None:
        """Choose whether a remote consumer deliberately returns another PSX disc."""
        super().__init__()
        self.reservation_target = Target(present=True)
        self.psx_cases: set[str] = set()
        self.receiver: str | None = None
        self.mismatch = mismatch

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Dispatch real session/coordinator requests at the external transport seam."""
        if (
            value["action"] == "image_status"
            or value.get("case_id") == "native-session-reservation"
        ):
            return self.reservation_target.request(value, timeout)
        if value["action"] == "allocate":
            self.receiver = None
            if "-psx-" in text(value["case_id"]):
                self.psx_cases.add(text(value["case_id"]))
        if value["action"] == "create":
            environment = sequence(record(record(value["payload"])["runner"])["env"])
            self.receiver = next(
                (
                    item.removeprefix("GOW_INPUT_TRIAL_CASE=")
                    for item in environment
                    if isinstance(item, str)
                    and item.startswith("GOW_INPUT_TRIAL_CASE=")
                ),
                None,
            )
        result = super().request(value, timeout)
        if value["action"] == "inspect" and self.receiver is not None:
            container = record(result["container"])
            configuration = record(container["Config"])
            configuration["Env"] = [
                *sequence(configuration["Env"]),
                "GOW_INPUT_TRIAL_CASE=" + self.receiver,
            ]
            container["Config"] = configuration
            result["container"] = container
        if value["action"] == "collect" and self.receiver is not None:
            self._receiver_evidence(result)
        if value["action"] == "collect" and "-psx-" in text(value["case_id"]):
            contents = record(result["files"])
            if (
                "selection.json" in contents
                and self.mismatch
                and len(self.psx_cases) > 1
            ):
                selected = record(
                    json.loads(base64.b64decode(text(contents["selection.json"])))
                )
                selected["entry"] = "psx/different-private-disc.cue"
                contents["selection.json"] = base64.b64encode(
                    json.dumps(selected).encode()
                ).decode()
                result["files"] = contents
        return result

    def _receiver_evidence(self, result: dict[str, object]) -> None:
        """Model a receiver's selected assertion and explicitly unexecuted siblings."""
        contents = record(result["files"])
        if "transport-probe.json" not in contents:
            return
        probe = record(
            json.loads(base64.b64decode(text(contents["transport-probe.json"])))
        )
        probe["cases"] = [
            row
            for row in sequence(probe["cases"])
            if record(row)["name"] == self.receiver
        ]
        probe["not_run_cases"] = [
            name for name in RECEIVER_CASES if name != self.receiver
        ]
        contents["transport-probe.json"] = base64.b64encode(
            json.dumps(probe).encode()
        ).decode()
        result["files"] = contents


@pytest.mark.parametrize("reverse", [False, True])
def test_session_full_aggregation_reuses_first_psx_selection_in_either_order(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    monkeypatch: pytest.MonkeyPatch,
    *,
    reverse: bool,
) -> None:
    """Independent native cases retain full gates and one renderer media identity."""
    snapshot, _config, images, artifacts = session_inputs
    world = SessionWorld()
    monkeypatch.setattr(native_preparation, "SystemClock", lambda: world.clock)
    names = ["frontend", *RECEIVER_CASES, *(case.identifier for case in EMULATOR_CASES)]
    if reverse:
        names.reverse()
    session = NativeSession(snapshot, matrix_config(), world, images, artifacts)
    try:
        with session:
            for name in names:
                assert session.run(name)["status"] == "passed"
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["full_regression_gate"] is True
        assert aggregate["full_frontend_receiver_gate"] is True
        assert aggregate["cleanup_complete"] is True
        assert len(sequence(aggregate["receiver_checks"])) == 5
        assert len(sequence(aggregate["regression_matrix"])) == 6
        seeded = [
            request
            for request in world.requests
            if request["action"] == "seed_selection"
        ]
        assert len(seeded) == 1
        assert record(seeded[0]["selection"])["entry"] == "psx/private-title.cue"
        assert world.reservation_target.states == {"foreign-state": "foreign-owner"}
        assert len(world.allocations) == len(world.removals) == 13
    finally:
        artifacts.close()


def test_session_rejects_cross_renderer_selection_mismatch_and_retains_failed_report(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A self-consistent second record cannot qualify a different renderer disc."""
    snapshot, _config, images, artifacts = session_inputs
    world = SessionWorld(mismatch=True)
    monkeypatch.setattr(native_preparation, "SystemClock", lambda: world.clock)
    session = NativeSession(snapshot, matrix_config(), world, images, artifacts)
    try:
        session.prepare()
        assert session.run("psx-duckstation")["status"] == "passed"
        with pytest.raises(NativeError, match="different selected media"):
            session.run("psx-duckstation-vulkan")
        with pytest.raises(NativeError, match="different selected media"):
            session.finish()
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["full_regression_gate"] is False
        assert aggregate["selection_status"] == "failed"
        assert aggregate["cleanup_complete"] is True
        assert world.reservation_target.states == {"foreign-state": "foreign-owner"}
    finally:
        artifacts.close()


def test_psx_selection_error_cannot_release_incomplete_cleanup_reservation(
    session_inputs: tuple[BuildSnapshot, NativeConfig, LocalImages, Artifacts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Combined media-validation and teardown failures retain the session barrier."""
    snapshot, _config, images, artifacts = session_inputs
    world = SessionWorld(mismatch=True)
    world.cleanup_failure_case = "psx-duckstation-vulkan"
    monkeypatch.setattr(native_preparation, "SystemClock", lambda: world.clock)
    session = NativeSession(snapshot, matrix_config(), world, images, artifacts)
    try:
        session.prepare()
        assert session.run("psx-duckstation")["status"] == "passed"
        with pytest.raises(NativeError, match="different selected media"):
            session.run("psx-duckstation-vulkan")
        returned = session.reports["psx-duckstation-vulkan"]
        assert returned["cleanup_complete"] is False
        assert record(sequence(returned["cases"])[0])["status"] == "passed"
        assert session.retain_reservation is True
        with pytest.raises(NativeError):
            session.run("frontend")
        with pytest.raises(NativeError):
            session.finish()
        assert "native-session-reservation" in world.reservation_target.states
        assert world.reservation_target.states["foreign-state"] == "foreign-owner"
        aggregate = record(
            json.loads((artifacts.path / "session-report.json").read_bytes())
        )
        assert aggregate["cleanup_complete"] is False
        assert aggregate["full_regression_gate"] is False
    finally:
        artifacts.close()
