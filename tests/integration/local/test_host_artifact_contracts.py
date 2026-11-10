"""Exercise local closure artifacts and private media through command consumers."""

import json
import os
import shlex
import shutil
import sys
import tarfile
from pathlib import Path

import pytest

from batocera_gow.host.build import Build, BuildError
from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.media import main as media_main


@pytest.fixture
def closure_build(tmp_path: Path) -> Build:
    """Supply an owned Nix process transcript and real tar/file operations."""
    (tmp_path / ".git").mkdir()
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    store = tmp_path / "store with space"
    store.mkdir()
    (store / "payload").write_bytes(b"closure fixture content")
    (store / "payload").chmod(0o751)
    outputs = {name: str(store) for name in ("xwayland", "xauth", "util-linux", "mesa")}
    (tmp_path / "outputs.json").write_text(json.dumps(outputs), encoding="utf-8")
    (tmp_path / "sizes.json").write_text('[{"narSize": 17}]', encoding="utf-8")
    commands = tmp_path / "bin"
    commands.mkdir()
    program = (
        f"#!{sys.executable}\n"
        "import json,pathlib,sys\n"
        "root = pathlib.Path(__file__).resolve().parents[1]\n"
        "name = pathlib.Path(sys.argv[0]).name\n"
        "if name == 'nix-instantiate': print((root/'outputs.json').read_text())\n"
        "elif name == 'nix': print((root/'sizes.json').read_text())\n"
        "elif name == 'nix-store':\n"
        "    if '--requisites' in sys.argv:\n"
        "        print(str(root/'store with space'))\n"
        "        print(str(root/'store with space'))\n"
        "    else: print('sha256:fixture-closure-hash')\n"
    )
    for name in ("nix-instantiate", "nix", "nix-store", "nix-build"):
        executable = commands / name
        executable.write_text(program, encoding="utf-8")
        executable.chmod(0o700)
    tar = shutil.which("tar")
    assert tar is not None
    (commands / "tar").symlink_to(tar)
    return Build(
        ProjectPaths(tmp_path),
        ["must-not-contact-docker"],
        dict(os.environ, PATH=str(commands)),
    )


@pytest.mark.parametrize("shape", ["list", "object"])
def test_closure_inventory_preserves_unique_bytes_and_shell_safe_paths(
    closure_build: Build,
    shape: str,
) -> None:
    """Deduplicate requisites, retain bytes/mode and publish usable quoted paths."""
    if shape == "object":
        (closure_build.root / "sizes.json").write_text(
            '{"fixture": {"narSize": 17}}',
            encoding="utf-8",
        )
    assert closure_build.bridge() == 17
    store = closure_build.root / "store with space"
    with tarfile.open(closure_build.output / "bridge.tar") as archive:
        payload = archive.getmember(str(store / "payload").lstrip("/"))
        assert payload.mode == 0o751
        extracted = archive.extractfile(payload)
        assert extracted is not None
        with extracted:
            assert extracted.read() == b"closure fixture content"
        assert len(archive.getmembers()) == 2
    manifest = json.loads(
        (closure_build.output / "bridge-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["closure_bytes"] == 17
    assert manifest["hashes"] == {str(store): "sha256:fixture-closure-hash"}
    assignments = shlex.split(
        (closure_build.output / "bridge.env").read_text(encoding="utf-8")
    )
    assert assignments == [
        "export",
        f"GOW_XWAYLAND={store}/bin/Xwayland",
        "export",
        f"GOW_XAUTH={store}/bin/xauth",
        "export",
        f"GOW_SETPRIV={store}/bin/setpriv",
        "export",
        f"GOW_MESA_DRIVERS={store}/lib/dri",
    ]


@pytest.mark.parametrize(
    "sizes", ['[{"narSize":true}]', '[{"narSize":-1}]', '[{"narSize":"17"}]', "null"]
)
def test_invalid_closure_sizes_cannot_publish_success_artifacts(
    closure_build: Build,
    sizes: str,
) -> None:
    """Refuse invalid external size evidence before creating a closure archive."""
    (closure_build.root / "sizes.json").write_text(sizes, encoding="utf-8")
    with pytest.raises((ValueError, BuildError), match="closure size"):
        closure_build.bridge()
    assert not (closure_build.output / "bridge.tar").exists()
    assert not (closure_build.output / "bridge.env").exists()
    assert not (closure_build.output / "bridge-manifest.json").exists()


@pytest.fixture
def media_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy the authenticated stock catalog and create one private ROM candidate."""
    for key in tuple(os.environ):
        if key.startswith("BATOCERA_GOW_"):
            monkeypatch.delenv(key)
    catalog = tmp_path / "tests/assets/media/stock-es_systems.cfg"
    catalog.parent.mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).resolve().parents[2] / "assets/media/stock-es_systems.cfg",
        catalog,
    )
    (tmp_path / "roms/nes").mkdir(parents=True)
    (tmp_path / "roms/nes/private-title.nes").write_bytes(b"synthetic selected bytes")
    return tmp_path


def test_media_cli_select_reproduce_and_drift_keep_content_private(
    media_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public CLI retains a private immutable choice, not ROM names or bytes."""
    record = media_project / "selection.json"
    common = ["--project-root", str(media_project)]
    assert media_main([*common, "catalog", "--system", "nes"]) == 0
    catalog = json.loads(capsys.readouterr().out)
    assert catalog["directory"] == "/userdata/roms/nes"
    assert catalog["extensions"] == [".nes", ".unif", ".unf", ".zip", ".7z"]
    assert catalog["backends"] == [
        ["libretro", "fceumm"],
        ["libretro", "mesen"],
        ["libretro", "nestopia"],
    ]
    select = [
        *common,
        "select",
        "--system",
        "nes",
        "--roms-view",
        str(media_project / "roms"),
        "--record",
        str(record),
    ]
    assert media_main(select) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "status": "selected privately",
        "native_executed": False,
    }
    assert "private-title" not in output
    assert record.stat().st_mode & 0o777 == 0o600
    original = record.read_bytes()
    reproduce = [
        *common,
        "reproduce",
        "--roms-view",
        str(media_project / "roms"),
        "--record",
        str(record),
    ]
    assert media_main(reproduce) == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "private identity reproduced",
        "native_executed": False,
    }
    assert media_main(select) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert record.read_bytes() == original
    (media_project / "roms/nes/private-title.nes").write_bytes(b"modified media")
    assert media_main(reproduce) == 2
    failure = capsys.readouterr().out
    assert json.loads(failure)["status"] == "error"
    assert "private-title" not in failure
    assert str(media_project) not in failure
    assert record.read_bytes() == original
