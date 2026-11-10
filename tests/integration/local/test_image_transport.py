"""Exact image transport preserves layer bytes and reports process refusal."""

import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

from batocera_gow.host.image import ImagePackager


def test_load_stream_keeps_layer_bytes_and_digest(tmp_path: Path) -> None:
    """Docker-save transport embeds the original archive as the sole exact layer."""
    layer = tmp_path / "root.tar"
    layer.write_bytes(b"contractual layer bytes\x00\xff\n")
    saved = tmp_path / "saved.tar"
    reader = tmp_path / "capture.py"
    reader.write_text(
        "import pathlib,sys\n"
        "pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    packager = ImagePackager(
        [sys.executable, str(reader), str(saved)], tmp_path, dict(os.environ)
    )
    image = packager.load(layer, "fixture:exact", {"identity": "fixture"})
    with tarfile.open(saved) as archive:
        layer_stream = archive.extractfile("layer/layer.tar")
        assert layer_stream is not None
        with layer_stream:
            assert layer_stream.read() == layer.read_bytes()
        manifest_stream = archive.extractfile("manifest.json")
        assert manifest_stream is not None
        with manifest_stream:
            manifest = json.load(manifest_stream)
        assert manifest[0]["Layers"] == ["layer/layer.tar"]
        config_stream = archive.extractfile(manifest[0]["Config"])
        assert config_stream is not None
        with config_stream:
            config_bytes = config_stream.read()
        config = json.loads(config_bytes)
        assert image == "sha256:" + hashlib.sha256(config_bytes).hexdigest()
        assert config["rootfs"]["diff_ids"] == [
            "sha256:" + hashlib.sha256(layer.read_bytes()).hexdigest()
        ]
        assert (
            config["config"]["Entrypoint"][1] == "/opt/gow-full-x86/input_transport.py"
        )
        assert config["config"]["Labels"] == {"identity": "fixture"}


def test_loader_failure_cannot_return_success(tmp_path: Path) -> None:
    """A complete consumer drain followed by refusal never yields an image claim."""
    layer = tmp_path / "root.tar"
    layer.write_bytes(b"layer")
    reader = tmp_path / "refuse.py"
    reader.write_text(
        "import sys\nsys.stdin.buffer.read()\nraise SystemExit(3)\n", encoding="utf-8"
    )
    packager = ImagePackager([sys.executable, str(reader)], tmp_path, dict(os.environ))
    with pytest.raises(RuntimeError, match="Docker rejected"):
        packager.load(layer, "fixture:refused", {})
