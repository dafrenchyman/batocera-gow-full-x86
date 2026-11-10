"""Verify explicit stock-preserving builds before any native transport activity."""

import json
import os
import re
import select
import subprocess
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from batocera_gow.host.native_remote import NativeError, record, sequence, text
from batocera_gow.provenance import (
    InputManifest,
    declared_inputs,
    file_sha256,
    tree_source,
)

BUILD_GUIDANCE = (
    "Native setup requires a new explicit batocera-gow-build before retrying"
)
MAX_IMAGE_BYTES = 32 * 1024**3


def _write_archive(stream: BinaryIO, data: bytes) -> None:
    """Bound compressed storage before each write, including the gzip trailer."""
    if stream.tell() + len(data) > MAX_IMAGE_BYTES:
        message = "Local image archive exceeds bounded native transfer storage"
        raise NativeError(message)
    stream.write(data)


def _save_archive(command: list[str], stream: BinaryIO, timeout: float) -> None:
    """Supervise a pipe producer and gzip its exact bytes within one deadline."""
    deadline = time.monotonic() + timeout
    # The gzip wrapper has no filename and a zero timestamp, unlike path-based gzip.
    compressor = zlib.compressobj(level=1, wbits=31)
    raw_bytes = 0
    with subprocess.Popen(  # noqa: S603 - frozen trusted Docker argv; no shell or destination path.
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    ) as child:
        try:
            if child.stdout is None:
                message = "Local image save output unavailable"
                raise NativeError(message)
            descriptor = child.stdout.fileno()
            os.set_blocking(descriptor, False)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                if not select.select([descriptor], [], [], remaining)[0]:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    data = os.read(descriptor, 1024**2)
                except BlockingIOError:
                    continue
                if not data:
                    break
                raw_bytes += len(data)
                if raw_bytes > MAX_IMAGE_BYTES:
                    message = "Local image save exceeds bounded raw archive size"
                    raise NativeError(message)
                _write_archive(stream, compressor.compress(data))
            child.wait(timeout=max(0, deadline - time.monotonic()))
            if child.returncode:
                raise subprocess.CalledProcessError(child.returncode, command)
            _write_archive(stream, compressor.flush())
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(command, timeout)
        finally:
            # Popen.kill polls before signalling and is a no-op after a reaped exit.
            # Kill before waiting so an open pipe or an early EOF cannot hang cleanup.
            child.kill()
            child.wait()


class LocalImages(Protocol):
    """The local Docker process boundary, never an implicit image builder."""

    def inspect(self, image: str) -> dict[str, object]:
        """Return inspection of exactly the supplied immutable image."""
        ...

    def save(self, image: str, destination: Path, timeout: float) -> None:
        """Save a Docker-loadable archive with a finite deadline to owned storage."""
        ...


class DockerImages:
    """Run local Docker image operations with an injected command prefix."""

    def __init__(self, command: list[str]) -> None:
        """Borrow a trusted local Docker argv prefix without invoking a shell."""
        self.command = tuple(command)

    def inspect(self, image: str) -> dict[str, object]:
        """Inspect one immutable local image without pulling or changing tags."""
        try:
            completed = subprocess.run(  # noqa: S603 - trusted Docker prefix; immutable ID is a separate argv element.
                [*self.command, "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode:
                raise NativeError(BUILD_GUIDANCE)
            values = sequence(json.loads(completed.stdout))
            if len(values) != 1:
                raise NativeError(BUILD_GUIDANCE)
            return record(values[0])
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise NativeError(BUILD_GUIDANCE) from error

    def save(self, image: str, destination: Path, timeout: float) -> None:
        """Gzip exact Docker-save bytes to exclusive parent-owned private storage.

        Bound raw bytes, compressed bytes and the combined save/compression time.
        The caller owns destination cleanup, including partial output on failure.
        Docker receives only a pipe, never authority to create the output path.
        """
        try:
            with os.fdopen(
                os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                "wb",
            ) as stream:
                _save_archive([*self.command, "image", "save", image], stream, timeout)
        except subprocess.CalledProcessError as error:
            message = "Local image save failed"
            raise NativeError(message) from error
        except (OSError, subprocess.TimeoutExpired) as error:
            message = "Bounded local image save failed"
            raise NativeError(message) from error


def _build_image(
    build: dict[str, object],
    inputs: InputManifest,
    staged: InputManifest,
) -> str:
    """Require successful stock verification and exact declared/staged identity."""
    image = text(build.get("image_id"))
    source_revision = text(build.get("adapter_revision"))
    stock = text(build.get("input_sha256"))
    if (
        build.get("status") != "success"
        or build.get("inventory_verified") is not True
        or build.get("release") != "43.1"
        or re.fullmatch(r"sha256:[a-f0-9]{64}", image) is None
        or re.fullmatch(
            r"(?:[a-f0-9]{40}|worktree-sha256:[a-f0-9]{64})",
            source_revision,
        )
        is None
        or re.fullmatch(r"[a-f0-9]{64}", stock) is None
        or build.get("declared_inputs") != inputs
        or build.get("runtime_inputs") != staged
        or (
            source_revision.startswith("worktree-sha256:")
            and source_revision != "worktree-sha256:" + inputs["sha256"]
        )
    ):
        raise NativeError(BUILD_GUIDANCE)
    return image


def _verify_local_image(
    local: dict[str, object],
    build: dict[str, object],
    inputs: InputManifest,
) -> None:
    """Bind immutable local image metadata to the actual declared inputs."""
    labels = record(record(local.get("Config")).get("Labels"))
    source = text(build.get("adapter_revision"))
    source_kind = "worktree" if source.startswith("worktree-sha256:") else "git"
    expected = {
        "org.opencontainers.image.revision": source,
        "org.opencontainers.image.version": "43.1",
        "io.gow.full-x86.experimental": "true",
        "io.gow.full-x86.input.sha256": text(build.get("input_sha256")),
        "io.gow.full-x86.source.kind": source_kind,
        "io.gow.full-x86.declared-inputs.sha256": inputs["sha256"],
    }
    if (
        local.get("Id") != build.get("image_id")
        or any(labels.get(key) != value for key, value in expected.items())
        or (
            source_kind == "worktree"
            and labels.get("io.gow.full-x86.source.sha256") != inputs["sha256"]
        )
    ):
        raise NativeError(BUILD_GUIDANCE)


def _verify_stage(root: Path, runtime: Path) -> None:
    """Reject a recorded stage that does not contain the actual consumed inputs."""
    mappings = (
        (root / "src/batocera_gow/runtime", runtime / "batocera_gow/runtime"),
        (root / "build-assets/runtime", runtime),
        (root / "tests/assets/input", runtime),
    )
    for source_directory, destination in mappings:
        for path in source_directory.rglob("*"):
            if (
                path.is_file()
                and path.suffix != ".pyc"
                and "__pycache__" not in path.parts
            ):
                installed = destination / path.relative_to(source_directory)
                if installed.is_symlink() or file_sha256(path) != file_sha256(
                    installed
                ):
                    raise NativeError(BUILD_GUIDANCE)


@dataclass(frozen=True)
class BuildSnapshot:
    """A stock-verified exact image bound to complete current and staged inputs."""

    root: Path
    runtime: Path
    image: str
    inputs: InputManifest
    runtime_inputs: InputManifest

    @classmethod
    def verify(
        cls,
        root: Path,
        manifest: Path,
        runtime: Path,
        images: LocalImages,
    ) -> "BuildSnapshot":
        """Reject stale, incomplete or swapped build evidence before remote work.

        Args:
            root: Explicit independent project root containing declared inputs.
            manifest: Successful stock-verified build record, never repaired here.
            runtime: Explicit staged runtime root, not a path trusted from JSON.
            images: Borrowed local image inspection boundary.

        Returns:
            A snapshot suitable for prelaunch and end-of-run drift checks.

        Raises:
            NativeError: If an explicit rebuild or local immutable image is needed.
        """
        try:
            build = record(json.loads(manifest.read_text(encoding="utf-8")))
            inputs = declared_inputs(root)
            staged = tree_source(runtime)
            image = _build_image(build, inputs, staged)
            _verify_stage(root, runtime)
            local_image = images.inspect(image)
            _verify_local_image(local_image, build, inputs)
        except (NativeError, OSError, ValueError, TypeError, KeyError) as error:
            raise NativeError(BUILD_GUIDANCE) from error
        return cls(root, runtime, image, inputs, staged)

    def assert_current(self) -> None:
        """Refuse any later launch or passing current-checkout claim after drift."""
        try:
            matched = (
                declared_inputs(self.root) == self.inputs
                and tree_source(self.runtime) == self.runtime_inputs
            )
        except (OSError, ValueError) as error:
            message = "Native input drift detected; run a new explicit build"
            raise NativeError(message) from error
        if not matched:
            message = "Native input drift detected; run a new explicit build"
            raise NativeError(message)
