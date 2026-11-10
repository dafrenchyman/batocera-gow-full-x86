"""Run through Python stdin in a disposable stock experiment image, without binds."""

import importlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from batocera_gow.runtime import runtime, transport_probe

pytestmark = pytest.mark.runtime


@pytest.fixture(autouse=True)
def stock_container() -> None:
    """Reject host execution before any stock paths or linker cache are touched."""
    if (
        not Path("/.dockerenv").exists()
        or not Path("/usr/bin/emulatorlauncher").is_file()
    ):
        pytest.skip("requires a disposable stock experiment container")


def test_stock_context_aliases_keep_semantics_and_owned_restoration() -> None:
    """Pin the real stock command's aliases, then restore its absent context.

    This uses no input device or hotkey daemon. The stock CLI signals this
    fixture's process only after synchronously writing its real context file.
    """
    context = Path("/var/run/hotkeygen.context")
    pid = Path("/var/run/hotkeygen.pid")
    assert not context.exists()
    assert not context.is_symlink()
    assert not pid.exists()
    assert not pid.is_symlink()
    mappings: dict[str, str | list[str]] = {
        "exit": ["KEY_LEFTCTRL", "KEY_F12"],
        "menu": ["BTN_LEFT"],
        "save_state": "KEY_F9",
        "command": "printf 'fixture\\n'",
    }
    probe = transport_probe.Probe()
    probe.evdev = importlib.import_module("evdev")
    probe.context_saved = True
    previous_handler = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    written: bytes | None = None
    identity: transport_probe.FileIdentity | None = None
    pid_identity: transport_probe.FileIdentity | None = None
    try:
        with pid.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        pid_identity = transport_probe.file_identity(pid)
        probe.command(
            [
                "/usr/bin/hotkeygen",
                "--disable-common",
                "--new-context",
                "fixture-owned-context",
                json.dumps(mappings),
            ]
        )
        identity = transport_probe.file_identity(context)
        written = context.read_bytes()
        saved = json.loads(written)
        assert saved == {
            "name": "fixture-owned-context",
            "keys": {
                "exit": ["KEY_LEFTCTRL", "KEY_F12"],
                "menu": ["BTN_MOUSE"],
                "save_state": "KEY_F9",
                "command": "printf 'fixture\\n'",
            },
        }
        probe.context_changed = True
        probe.remember_context("fixture-owned-context", mappings)
        probe.require_context_ownership()
        assert context.read_bytes() == written
        probe.restore_context()
        assert not context.exists()
        assert not probe.context_changed
    finally:
        if (
            identity is not None
            and context.exists()
            and transport_probe.file_identity(context) == identity
            and context.read_bytes() == written
        ):
            context.unlink()
        if (
            pid_identity is not None
            and pid.exists()
            and transport_probe.file_identity(pid) == pid_identity
            and pid.read_text(encoding="utf-8") == str(os.getpid())
        ):
            pid.unlink()
        signal.signal(signal.SIGHUP, previous_handler)


@pytest.mark.skipif(
    os.getuid() != 0, reason="linker cache initialization requires container root"
)
class TestStockLibraryDiscovery:
    """Check the stock dynamic loader after dropping the app's privileges."""

    def test_launcher_discovers_sdl_after_privilege_drop_without_rewriting_links(
        self,
    ) -> None:
        """Launcher discovers sdl after privilege drop without rewriting links."""
        directories = (
            Path("/usr/lib"),
            Path("/lib"),
            Path("/lib32"),
            Path("/usr/lib/mangohud"),
        )
        before = {
            str(p): str(p.readlink())
            for directory in directories
            if directory.is_dir()
            for p in directory.iterdir()
            if p.is_symlink()
        }
        runtime.initialize_library_cache()
        # Fixed stock import code runs through the explicitly injected setpriv tool.
        result = subprocess.run(  # noqa: S603
            [
                os.environ["GOW_SETPRIV"],
                "--reuid",
                "1234",
                "--regid",
                "1234",
                "--clear-groups",
                sys.executable,
                "-c",
                (
                    "import configgen.emulatorlauncher; import sdl2; "
                    "version = sdl2.SDL_version(); sdl2.SDL_GetVersion(version); "
                    "print(version.major)"
                ),
            ],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "2"
        after = {
            str(p): str(p.readlink())
            for directory in directories
            if directory.is_dir()
            for p in directory.iterdir()
            if p.is_symlink()
        }
        assert after == before

    @pytest.mark.skipif(
        Path("/usr/nvidia").exists(),
        reason="synthetic libraries require an absent driver payload directory",
    )
    def test_wine_discovers_injected_transitive_dependencies_without_rewriting_links(
        self,
    ) -> None:
        """Wine discovers injected transitive dependencies without rewriting links."""
        # Rename only copied ELF dynamic strings. This needs no compiler in the
        # stock image and exercises the real loader, not ctypes discovery mocks.
        old_name, new_name = b"libz.so.1\0", b"libg.so.1\0"
        fixtures = {}
        for name in ("libpng16.so.16", "libz.so.1"):
            data = (Path("/usr/lib") / name).read_bytes()
            assert data.count(old_name) == 1, name
            fixtures[name] = data.replace(old_name, new_name)
        env = dict(
            os.environ, LD_LIBRARY_PATH="/usr/lib:/lib32:/usr/wine/wine-proton/lib/wine"
        )
        for directory in (Path("/usr/nvidia/lib"), Path("/usr/nvidia/lib32")):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                root.chmod(0o755)
                consumer = root / "libpng16.so.16"
                consumer.write_bytes(fixtures["libpng16.so.16"])
                existed = directory.is_dir()
                directory.mkdir(parents=True, exist_ok=True)
                dependency = directory / new_name.rstrip(b"\0").decode()
                assert not dependency.exists(), str(dependency)
                links = {
                    str(p): str(p.readlink())
                    for p in directory.iterdir()
                    if p.is_symlink()
                }
                command = [
                    os.environ["GOW_SETPRIV"],
                    "--reuid",
                    "1234",
                    "--regid",
                    "1234",
                    "--clear-groups",
                    sys.executable,
                    "-c",
                    (
                        "import ctypes, sys; library = ctypes.CDLL(sys.argv[1]); "
                        "print(library.png_access_version_number())"
                    ),
                    str(consumer),
                ]
                try:
                    # Fixed consumer code loads only the generated ELF fixture.
                    missing = subprocess.run(  # noqa: S603
                        command,
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=20,
                        check=False,
                    )
                    assert missing.returncode != 0
                    assert "libg.so.1" in missing.stderr
                    dependency.write_bytes(fixtures["libz.so.1"])
                    # An absolute dlopen of libpng must discover its dependency
                    # through ld.so.cache, despite Wine's stock LD_LIBRARY_PATH.
                    runtime.initialize_library_cache()
                    # Repeat the same bounded loader check after cache initialization.
                    result = subprocess.run(  # noqa: S603
                        command,
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=20,
                        check=False,
                    )
                    assert result.returncode == 0, result.stderr
                    assert int(result.stdout.strip()) > 10000
                    assert {
                        str(p): str(p.readlink())
                        for p in directory.iterdir()
                        if p.is_symlink()
                    } == links
                finally:
                    dependency.unlink(missing_ok=True)
                    if not existed:
                        directory.rmdir()
                    runtime.initialize_library_cache()

    @pytest.mark.skipif(
        not (Path("/usr/nvidia/lib/libGLX_nvidia.so.0").is_file()),
        reason="requires the injected NVIDIA driver payload",
    )
    def test_injected_nvidia_dependencies_resolve_with_stock_wine_search_path(
        self,
    ) -> None:
        """Injected nvidia dependencies resolve with stock wine search path."""
        directory = Path("/usr/nvidia/lib")
        before = {
            str(p): str(p.readlink()) for p in directory.iterdir() if p.is_symlink()
        }
        runtime.initialize_library_cache()
        # The injected setpriv executable lists the pinned stock NVIDIA library.
        result = subprocess.run(  # noqa: S603
            [
                os.environ["GOW_SETPRIV"],
                "--reuid",
                "1234",
                "--regid",
                "1234",
                "--clear-groups",
                "/lib/ld-linux-x86-64.so.2",
                "--list",
                str(directory / "libGLX_nvidia.so.0"),
            ],
            env=dict(
                os.environ,
                LD_LIBRARY_PATH="/usr/lib:/lib32:/usr/wine/wine-proton/lib/wine",
            ),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "not found" not in result.stdout
        assert "/usr/nvidia/lib/libnvidia-glsi.so." in result.stdout
        assert {
            str(p): str(p.readlink()) for p in directory.iterdir() if p.is_symlink()
        } == before

    @pytest.mark.skipif(
        not (
            Path("/usr/nvidia/lib/libcuda.so.1").is_file()
            and Path("/dev/nvidiactl").exists()
        ),
        reason="requires the injected NVIDIA driver and GPU",
    )
    def test_stock_wine_search_path_keeps_injected_cuda_driver(self) -> None:
        """Stock wine search path keeps injected cuda driver."""
        runtime.initialize_library_cache()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o755)
            _, env = runtime.nvidia_environments(
                dict(
                    os.environ,
                    GOW_BRIDGE_LIBRARY_PATH=os.environ.get(
                        "GOW_BRIDGE_LIBRARY_PATH", "/usr/lib"
                    ),
                ),
                root,
            )
            runtime.chown_tree(root, 1234, 1234)
            env["LD_LIBRARY_PATH"] = "/usr/lib:/lib32:/usr/wine/wine-proton/lib/wine"
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import ctypes; from pathlib import Path; "
                        'cuda = ctypes.CDLL("libcuda.so.1"); '
                        "assert cuda.cuInit(0) == 0; "
                        "loaded = {line.split()[-1] for line in "
                        'Path("/proc/self/maps").read_text().splitlines() '
                        'if "/libcuda.so." in line}; '
                        "assert loaded == {str(Path("
                        "'/usr/nvidia/lib/libcuda.so.1').resolve())}, loaded"
                    ),
                ],
                env=env,
                user=1234,
                group=1234,
                extra_groups=[],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            # The same preload token must resolve to the injected 32-bit CUDA
            # object, rather than producing a wrong-ELF-class warning.
            result32 = subprocess.run(
                [
                    "/lib/ld-linux.so.2",
                    "--list",
                    "/lib32/libc.so.6",
                ],
                env=env,
                user=1234,
                group=1234,
                extra_groups=[],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            assert result32.returncode == 0, result32.stderr
            assert "cannot be preloaded" not in result32.stderr
            assert "wrong ELF class" not in result32.stderr
            assert "libcuda.so.1" in result32.stdout
