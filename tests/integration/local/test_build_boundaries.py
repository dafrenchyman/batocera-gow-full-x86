"""Exercise owned build artifacts with disposable files and local process models."""

import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from batocera_gow.builder.assemble import assemble_in_builder, extract_archive
from batocera_gow.builder.inventory import saved_image_layer
from batocera_gow.host.build import Build, BuildError
from batocera_gow.host.common import ProjectPaths, docker_command
from batocera_gow.host.settings import HostSettings


@pytest.fixture
def build_project(tmp_path: Path) -> Build:
    """Create an independent declared-input tree without consulting real Git."""
    for directory in (
        ".git",
        "src/batocera_gow/runtime",
        "src/batocera_gow/host",
        "build-assets/runtime",
        "tests/assets/input",
        "output/gow-full-x86",
    ):
        (tmp_path / directory).mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".dockerignore",
        "LICENSE",
    ):
        (tmp_path / name).write_text("fixture\n", encoding="utf-8")
    for name in (
        "src/batocera_gow/__init__.py",
        "src/batocera_gow/runtime/__init__.py",
        "src/batocera_gow/runtime/session.py",
        "src/batocera_gow/host/private.py",
        "build-assets/runtime/launch.sh",
        "tests/assets/input/gamepad.json",
    ):
        (tmp_path / name).write_text(name + "\n", encoding="utf-8")
    return Build(
        ProjectPaths(tmp_path),
        ["unconfigured-docker"],
        dict(os.environ),
        working_tree=True,
    )


def test_download_reuses_only_checksum_verified_cache(build_project: Build) -> None:
    """Verified cache avoids downloading; corruption is retained and refused."""
    cache = build_project.root / "cache"
    cache.mkdir()
    image = cache / "release.img.gz"
    image.write_bytes(b"official fixture bytes")
    release: dict[str, object] = {
        "image_url": "https://invalid.example/release.img.gz",
        "compressed_md5": hashlib.md5(
            b"official fixture bytes", usedforsecurity=False
        ).hexdigest(),
    }
    path, digest = build_project.download(release)
    assert path == image
    assert digest == hashlib.sha256(b"official fixture bytes").hexdigest()
    image.write_bytes(b"corrupt")
    with pytest.raises(BuildError, match="checksum mismatch"):
        build_project.download(release)
    assert image.read_bytes() == b"corrupt"
    assert not image.with_suffix(".gz.partial").exists()


def test_download_promotes_owned_partial_only_after_validation(
    build_project: Build,
) -> None:
    """A local curl model resumes partial bytes and failure cannot promote them."""
    executable = build_project.root / "curl"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import pathlib,sys\n"
        "destination = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "with destination.open('ab') as stream: stream.write(b'complete')\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    build_project.env["PATH"] = str(build_project.root)
    cache = build_project.root / "cache"
    cache.mkdir()
    partial = cache / "release.gz.partial"
    partial.write_bytes(b"in")
    release: dict[str, object] = {
        "image_url": "https://invalid.example/release.gz",
        "compressed_md5": hashlib.md5(b"incomplete", usedforsecurity=False).hexdigest(),
    }
    image, _digest = build_project.download(release)
    assert image.read_bytes() == b"incomplete"
    assert not partial.exists()
    image.unlink()
    with pytest.raises(BuildError, match="checksum mismatch"):
        build_project.download(release)
    assert not image.exists()
    assert partial.read_bytes() == b"complete"


def test_worktree_identity_refuses_input_change_before_promotion(
    build_project: Build,
) -> None:
    """Saved provenance identifies actual inputs and detects mode-only mutation."""
    source = build_project.source_identity()
    saved = build_project.output / f"source-{source.tag}.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == source.inputs
    assert source.kind == "worktree"
    assert source.revision.startswith("worktree-sha256:")
    build_project.verify_source(source)
    launcher = build_project.root / "build-assets/runtime/launch.sh"
    launcher.chmod(0o755)
    with pytest.raises(BuildError, match="inputs changed"):
        build_project.verify_source(source)
    assert not (build_project.output / "build-manifest.json").exists()


def test_runtime_staging_replaces_stale_output_and_excludes_host_code(
    build_project: Build,
) -> None:
    """Runtime gets required assets and fixtures but no host dependencies or pyc."""
    root = build_project.root
    (root / "tests/assets/input/directory").mkdir()
    bytecode = root / "src/batocera_gow/runtime/__pycache__"
    bytecode.mkdir()
    (bytecode / "session.pyc").write_bytes(b"host bytecode")
    (root / "src/batocera_gow/runtime/stray.pyc").write_bytes(b"bytecode")
    (build_project.output / "bridge.env").write_text(
        "export BRIDGE=fixture\n", encoding="utf-8"
    )
    stale = build_project.output / "runtime"
    stale.mkdir()
    (stale / "obsolete").write_bytes(b"remove")
    staged = build_project.stage_runtime()
    assert (staged / "batocera_gow/runtime/session.py").read_text(
        encoding="utf-8"
    ) == "src/batocera_gow/runtime/session.py\n"
    assert (staged / "gamepad.json").read_text(
        encoding="utf-8"
    ) == "tests/assets/input/gamepad.json\n"
    assert (staged / "bridge.env").read_text(
        encoding="utf-8"
    ) == "export BRIDGE=fixture\n"
    assert not (staged / "obsolete").exists()
    assert not (staged / "batocera_gow/host").exists()
    assert not list(staged.rglob("*.pyc"))
    assert not list(staged.rglob("__pycache__"))


@pytest.mark.parametrize("selection", ["configured", "direct"])
@pytest.mark.parametrize("exit_code", [0, 9])
def test_packaging_consumes_frozen_docker_argv(
    build_project: Build,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    selection: str,
) -> None:
    """The real child uses selected argv, not changed dotenv or environment."""
    root = build_project.root
    executable = root / ("selected docker" if selection == "configured" else "docker")
    context = "fixture context 'quoted' ; $(touch injected)"
    prefix = ["--context", context] if selection == "configured" else []
    executable.write_text(
        f"#!{sys.executable}\n"
        "import hashlib,json,pathlib,sys\n"
        f"assert sys.argv[1:{len(prefix) + 1}] == {prefix!r}\n"
        f"args = sys.argv[{len(prefix) + 1}:]\n"
        "assert args[:4] == ['run', '--rm', '--network', 'none']\n"
        "assert 'fixture-builder' in args and '--inside' in args\n"
        "mounts = dict((part.split('=', 1)[1] for part in arg.split(',')[1:3])"
        " for arg in args if arg.startswith('type=bind,src='))\n"
        "stock = pathlib.Path(next(src for src,dst in mounts.items()"
        " if dst == '/inputs/stock_root'))\n"
        "output = pathlib.Path(next(src for src,dst in mounts.items()"
        " if dst == '/work'))\n"
        "digest = hashlib.sha256(stock.read_bytes()).hexdigest()\n"
        "(output / 'consumed-stock.sha256').write_text(digest)\n"
        f"if {exit_code}: raise SystemExit({exit_code})\n"
        "(output / 'package-manifest.json').write_text("
        "json.dumps({'consumed_stock_sha256': digest}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    selected = root / "selected.env"
    selected.write_text(
        "DOCKER="
        + json.dumps(
            shlex.join(
                [str(executable), *prefix] if selection == "configured" else ["docker"]
            )
        )
        + "\n",
        encoding="utf-8",
    )
    settings = HostSettings.resolve(env_file=selected, environ={})
    docker = docker_command(settings.values)
    build = Build(build_project.paths, docker, dict(os.environ), working_tree=True)
    build.env["PATH"] = str(root)
    source = build.source_identity()
    selected.write_text("DOCKER=must-not-reread\n", encoding="utf-8")
    monkeypatch.setenv("DOCKER", "must-not-use-ambient-docker")
    build.env["DOCKER"] = "must-not-use-child-environment"
    docker[:] = ["must-not-use-mutated-caller-argv"]
    assembly = root / "assembly"
    assembly.mkdir()
    (assembly / "stock-root.tar").write_bytes(b"complete fixture stock")
    (assembly / "stock-share.tar").write_bytes(b"fixture share")
    (build.output / "stock-manifest.json").write_text("{}", encoding="utf-8")
    (build.output / "bridge.tar").write_bytes(b"fixture bridge")
    runtime = root / "runtime"
    runtime.mkdir()
    output = build.output / ("packaging-" + source.tag)
    if exit_code:
        with pytest.raises(subprocess.CalledProcessError) as failure:
            build.package(assembly, runtime, "fixture-builder", source)
        assert failure.value.returncode == 1
        assert not (output / "package-manifest.json").exists()
    else:
        assert build.package(assembly, runtime, "fixture-builder", source) == output
        manifest = json.loads(
            (output / "package-manifest.json").read_text(encoding="utf-8")
        )
        assert manifest == {
            "consumed_stock_sha256": hashlib.sha256(
                b"complete fixture stock"
            ).hexdigest()
        }
    assert (output / "consumed-stock.sha256").read_text(
        encoding="utf-8"
    ) == hashlib.sha256(b"complete fixture stock").hexdigest()
    assert not (root / "injected").exists()


def test_assembly_process_failure_cleans_only_fresh_owned_products(
    build_project: Build,
) -> None:
    """Networkless builder failure triggers real cleanup, not unrelated deletion."""
    image = build_project.root / "cache/release.gz"
    image.parent.mkdir()
    image.write_bytes(b"compressed fixture")
    (build_project.assets / "release.json").write_text(
        json.dumps(
            {
                "compressed_md5": hashlib.md5(
                    image.read_bytes(), usedforsecurity=False
                ).hexdigest()
            }
        ),
        encoding="utf-8",
    )
    model = build_project.root / "docker_model.py"
    model.write_text(
        "import pathlib,sys\n"
        "from batocera_gow.builder.assemble import clean_failed_assembly\n"
        "args = sys.argv[1:]\n"
        "mount = next(a for a in args if a.startswith('type=bind,src=') "
        "and a.endswith(',dst=/work'))\n"
        "output = pathlib.Path(mount.split(',')[1].removeprefix('src='))\n"
        "if 'cleanup' in args:\n"
        "    clean_failed_assembly(output)\n"
        "else:\n"
        "    (output / 'root').mkdir()\n"
        "    (output / 'root/partial').write_bytes(b'unfinished')\n"
        "    raise SystemExit(9)\n",
        encoding="utf-8",
    )
    build_project.docker = [sys.executable, str(model)]
    sentinel = build_project.output / "operator-save"
    sentinel.write_bytes(b"preserve")
    with pytest.raises(subprocess.CalledProcessError):
        build_project.assemble(image, "fixture-builder", 0)
    assemblies = list(build_project.output.glob("assembly-*"))
    assert len(assemblies) == 1
    assert list(assemblies[0].iterdir()) == []
    assert sentinel.read_bytes() == b"preserve"
    assert not (build_project.output / "build-manifest.json").exists()


def test_assembly_refuses_bad_official_bytes_before_creating_output(
    build_project: Build,
) -> None:
    """Corrupt official input cannot start a builder or allocate assembly state."""
    image = build_project.root / "bad.gz"
    image.write_bytes(b"bad")
    (build_project.assets / "release.json").write_text(
        '{"compressed_md5":"not-the-checksum"}', encoding="utf-8"
    )
    output = build_project.output / "fresh"
    with pytest.raises(ValueError, match="checksum mismatch"):
        assemble_in_builder(
            image,
            output,
            "unused",
            1,
            project_root=build_project.root,
            docker=["must-not-execute"],
        )
    assert not output.exists()


def test_archive_extraction_preserves_links_and_modes(tmp_path: Path) -> None:
    """Validated real tar extraction retains executable, hardlink and symlink data."""
    source = tmp_path / "source"
    source.mkdir()
    executable = source / "program"
    executable.write_bytes(b"stock bytes")
    executable.chmod(0o751)
    (source / "alias").hardlink_to(executable)
    (source / "pointer").symlink_to("program")
    archive = tmp_path / "stock.tar"
    with tarfile.open(archive, "w") as stream:
        stream.add(source, arcname=".")
    destination = tmp_path / "root"
    destination.mkdir()
    extract_archive(archive, destination)
    assert (destination / "program").read_bytes() == b"stock bytes"
    assert (destination / "program").stat().st_mode & 0o777 == 0o751
    assert (destination / "alias").stat().st_ino == (
        destination / "program"
    ).stat().st_ino
    assert (destination / "pointer").readlink() == Path("program")


@pytest.mark.parametrize("layers", [[], ["one", "two"]])
def test_docker_save_rejects_nonflat_images_without_partial_layer(
    tmp_path: Path, layers: list[str]
) -> None:
    """No absent or multi-layer image can masquerade as verified flat stock."""
    archive = tmp_path / "save.tar"
    content = json.dumps([{"Layers": layers}]).encode()
    with tarfile.open(archive, "w") as stream:
        member = tarfile.TarInfo("manifest.json")
        member.size = len(content)
        stream.addfile(member, io.BytesIO(content))
    with pytest.raises(ValueError, match="one flattened filesystem layer"):
        saved_image_layer(archive, tmp_path)
    assert not (tmp_path / "filesystem-layer.tar").exists()


def test_docker_save_copies_untrusted_layer_bytes_without_unpacking(
    tmp_path: Path,
) -> None:
    """Reading a save archive does not extract nested paths or overwrite evidence."""
    archive = tmp_path / "save.tar"
    content = json.dumps([{"Layers": ["../../layer"]}]).encode()
    with tarfile.open(archive, "w") as stream:
        for name, data in (
            ("manifest.json", content),
            ("../../layer", b"unaltered layer\x00\xff"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
    layer = saved_image_layer(archive, tmp_path)
    assert layer.read_bytes() == b"unaltered layer\x00\xff"
    with pytest.raises(FileExistsError):
        saved_image_layer(archive, tmp_path)
    assert layer.read_bytes() == b"unaltered layer\x00\xff"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "filesystem-layer.tar",
        "save.tar",
    ]


@pytest.mark.parametrize("valid_provenance", [True, False])
def test_builder_records_immutable_base_and_selected_interpreter(
    build_project: Build, *, valid_provenance: bool
) -> None:
    """A tools-image claim needs a pinned base plus package/interpreter evidence."""
    model = build_project.root / "docker_model.py"
    model.write_text(
        "import json,pathlib,sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['image', 'inspect']:\n"
        "    print(json.dumps([{'RepoDigests': "
        + repr(["debian@sha256:" + "d" * 64] if valid_provenance else [])
        + "}]))\n"
        "elif args[0] == 'build':\n"
        "    base = args[args.index('--build-arg') + 1]\n"
        "    pathlib.Path('selected-base').write_text(base)\n"
        "elif 'dpkg-query' in args:\n"
        "    print('tar\\t1.35\\nacl\\t2.3')\n"
        "elif '/opt/batocera-gow/bin/python' in args:\n"
        "    print('3.12.8 fixture interpreter')\n"
        "elif args[0] != 'pull':\n"
        "    raise SystemExit(11)\n",
        encoding="utf-8",
    )
    build_project.docker = [sys.executable, str(model)]
    evidence = build_project.output / "builder-manifest.json"
    if not valid_provenance:
        with pytest.raises(ValueError, match="lacks immutable provenance"):
            build_project.builder()
        assert not evidence.exists()
        assert not (build_project.root / "selected-base").exists()
        return
    _builder, base = build_project.builder()
    assert base == "debian@sha256:" + "d" * 64
    assert (build_project.root / "selected-base").read_text(
        encoding="utf-8"
    ) == "DEBIAN_BASE=debian@sha256:" + "d" * 64
    assert json.loads(evidence.read_text(encoding="utf-8")) == {
        "base": "debian@sha256:" + "d" * 64,
        "packages": "tar\t1.35\nacl\t2.3\n",
        "project_python": "3.12.8 fixture interpreter",
    }
