"""Load one preassembled layer without metadata-losing filesystem repackaging."""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path


class ImagePackager:
    """Stream exact archive bytes to an explicitly configured Docker command."""

    def __init__(self, docker: list[str], root: Path, env: dict[str, str]) -> None:
        """Borrow command configuration; own only the subprocess started by load."""
        self.docker, self.root, self.env = docker, root, env

    @staticmethod
    def encoded(value: object) -> bytes:
        """Encode deterministic Docker metadata without modifying layer content."""
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
        """Write an owned metadata member; the caller retains archive ownership."""
        info = tarfile.TarInfo(name)
        info.mode, info.mtime, info.size = 0o644, 0, len(data)
        archive.addfile(info, io.BytesIO(data))

    def load(self, layer: Path, tag: str, labels: dict[str, str]) -> str:
        """Load the existing tar as one unchanged layer and return its config digest.

        Args:
            layer: Complete metadata-preserving root filesystem archive.
            tag: Candidate local Docker reference, not a publication request.
            labels: Build provenance attached to the Docker image configuration.

        Raises:
            RuntimeError: Docker refuses the stream or does not supply its pipe.
            OSError: The archive or subprocess cannot be accessed.
        """
        digest = hashlib.sha256()
        with layer.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        config = self.encoded(
            {
                "architecture": "amd64",
                "os": "linux",
                "config": {
                    "User": "0",
                    "WorkingDir": "/",
                    "Env": [
                        "GOW_FULL_X86_EXPERIMENT=1",
                        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    ],
                    "Entrypoint": [
                        "/usr/bin/python3",
                        "/opt/gow-full-x86/input_transport.py",
                        "--",
                        "/opt/gow-full-x86/entrypoint.sh",
                    ],
                    "Cmd": ["/opt/gow-full-x86/frontend.sh"],
                    "Labels": labels,
                },
                "rootfs": {
                    "type": "layers",
                    "diff_ids": ["sha256:" + digest.hexdigest()],
                },
                "history": [
                    {
                        "created_by": (
                            "complete official Batocera userspace "
                            "plus isolated GoW startup adapter"
                        )
                    }
                ],
            }
        )
        config_name = hashlib.sha256(config).hexdigest() + ".json"
        manifest = self.encoded(
            [{"Config": config_name, "RepoTags": [tag], "Layers": ["layer/layer.tar"]}]
        )
        # Docker receives only this invocation's argv and owned archive stream.
        process = subprocess.Popen(  # noqa: S603
            [*self.docker, "load"], cwd=self.root, env=self.env, stdin=subprocess.PIPE
        )
        try:
            if process.stdin is None:
                message = "Docker image load did not supply its input pipe"
                raise RuntimeError(message)
            with tarfile.open(
                fileobj=process.stdin, mode="w|", format=tarfile.PAX_FORMAT
            ) as archive:
                self.add(archive, config_name, config)
                self.add(archive, "manifest.json", manifest)
                info = tarfile.TarInfo("layer/layer.tar")
                info.mode, info.mtime, info.size = 0o644, 0, layer.stat().st_size
                with layer.open("rb") as stream:
                    archive.addfile(info, stream)
            process.stdin.close()
            if process.wait():
                message = "Docker rejected the complete metadata-preserving layer"
                raise RuntimeError(message)
        finally:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        return "sha256:" + config_name.removesuffix(".json")
