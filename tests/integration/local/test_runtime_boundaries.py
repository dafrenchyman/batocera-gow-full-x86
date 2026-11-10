"""Exercise local runtime decisions without stock services, mounts or a GPU."""

import errno
import grp
import json
import os
import pwd
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import pytest

from batocera_gow.runtime import runtime


class RootedPaths:
    """Redirect absolute appliance paths into one independently owned directory."""

    def __init__(self, root: Path) -> None:
        """Borrow the directory containing this test's appliance filesystem."""
        self.root = root

    def __call__(self, value: str | Path) -> Path:
        """Keep fixture paths intact and redirect other absolute paths."""
        path = Path(value)
        if path.is_absolute() and not path.is_relative_to(self.root):
            return self.root / path.relative_to("/")
        return path

    def file(self, name: str, content: str = "fixture\n") -> Path:
        """Create one appliance file and its owned parent directories."""
        path = self(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


@pytest.fixture
def appliance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RootedPaths:
    """Confine runtime pathname access without replacing its filesystem decisions."""
    paths = RootedPaths(tmp_path)
    monkeypatch.setattr(runtime, "Path", paths)
    return paths


@pytest.fixture
def nvidia_payload(appliance: RootedPaths) -> RootedPaths:
    """Create inert driver names and manifests, never load their dummy bytes."""
    for directory in ("lib", "lib32"):
        for library in ("libcuda.so.1", "libGLX_nvidia.so.0", "libEGL_nvidia.so.0"):
            appliance.file(f"/usr/nvidia/{directory}/{library}")
    appliance.file("/usr/nvidia/lib/libnvidia-egl-wayland.so.1")
    appliance.file("/dev/nvidiactl")
    for name in (
        "glvnd/egl_vendor.d/10_nvidia.json",
        "vulkan/icd.d/nvidia_icd.json",
        "egl/egl_external_platform.d/10_wayland.json",
    ):
        appliance.file(
            "/usr/nvidia/share/" + name,
            json.dumps(
                {
                    "file_format_version": "1.0.0",
                    "ICD": {
                        "library_path": "libnvidia-egl-wayland.so.1",
                        "api_version": "1.3.275",
                    },
                    "vendor_extension": {"keep": True},
                }
            ),
        )
    return appliance


def test_nvidia_selectors_separate_loaders_and_preserve_vendor_inputs(
    nvidia_payload: RootedPaths,
) -> None:
    """Publish private selectors and architecture links without rewriting drivers."""
    paths = nvidia_payload
    directory = paths.root / "session"
    directory.mkdir()
    inputs = {
        path: path.read_bytes() for path in paths("/usr/nvidia/share").rglob("*.json")
    }
    env = {
        "LD_LIBRARY_PATH": "/stock/application",
        "LD_PRELOAD": "/stock/interposer.so",
        "GOW_BRIDGE_LIBRARY_PATH": "/bridge/lib",
        "GOW_MESA_DRIVERS": "/bridge/dri",
        "GOW_FIXTURE_LABEL": "fixture-session",
    }
    bridge, application = runtime.nvidia_environments(env, directory)
    assert env["LD_LIBRARY_PATH"] == "/stock/application"
    assert bridge["LD_LIBRARY_PATH"] == (
        f"{paths('/usr/nvidia/lib')}:{paths('/usr/nvidia/lib32')}:/bridge/lib"
    )
    assert application["LD_LIBRARY_PATH"].endswith(":/stock/application")
    assert bridge["LIBGL_DRIVERS_PATH"] == "/bridge/dri"
    assert "LIBGL_DRIVERS_PATH" not in application
    assert bridge["LD_PRELOAD"] == "/stock/interposer.so"
    assert application["LD_PRELOAD"] == (
        f"{directory}/injected-cuda/$LIB/libcuda.so.1:"
        f"{directory}/injected-cuda/$LIB/libGLX_nvidia.so.0:/stock/interposer.so"
    )
    for environment in (bridge, application):
        assert environment["GOW_FIXTURE_LABEL"] == "fixture-session"
        assert environment["__GLX_VENDOR_LIBRARY_NAME"] == "nvidia"
        assert environment["VK_DRIVER_FILES"] == str(directory / "nvidia-vulkan.json")
    for name, library in (
        ("nvidia-egl.json", "libEGL_nvidia.so.0"),
        ("nvidia-vulkan.json", "libGLX_nvidia.so.0"),
        ("10_wayland.json", "libnvidia-egl-wayland.so.1"),
    ):
        assert json.loads((directory / name).read_text(encoding="utf-8")) == {
            "file_format_version": "1.0.0",
            "ICD": {
                "library_path": str(paths("/usr/nvidia/lib") / library),
                "api_version": "1.3.275",
            },
            "vendor_extension": {"keep": True},
        }
    for token, architecture in (("lib64", "lib"), ("lib", "lib32")):
        for library in ("libcuda.so.1", "libGLX_nvidia.so.0"):
            link = directory / "injected-cuda" / token / library
            assert link.is_symlink()
            assert link.readlink() == paths(f"/usr/nvidia/{architecture}/{library}")
    assert {path: path.read_bytes() for path in inputs} == inputs


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("device", "NVIDIA device"),
        ("manifest", "invalid NVIDIA driver manifest"),
        ("platform", "missing injected NVIDIA EGL platform library"),
        ("cuda32", "missing injected NVIDIA CUDA library"),
    ],
)
def test_nvidia_startup_refuses_incomplete_injection(
    damage: str, reason: str, nvidia_payload: RootedPaths
) -> None:
    """Reject incomplete payloads instead of silently selecting appliance drivers."""
    paths = nvidia_payload
    directory = paths.root / "session"
    directory.mkdir()
    if damage == "manifest":
        paths.file("/usr/nvidia/share/vulkan/icd.d/nvidia_icd.json", "[]")
    else:
        names = {
            "device": "/dev/nvidiactl",
            "platform": "/usr/nvidia/lib/libnvidia-egl-wayland.so.1",
            "cuda32": "/usr/nvidia/lib32/libcuda.so.1",
        }
        paths(names[damage]).unlink()
    with pytest.raises(RuntimeError, match=reason):
        runtime.nvidia_environments({}, directory)


def prepared_state(paths: RootedPaths) -> runtime.StateInitializer:
    """Create valid local state for refusal scenarios.

    Args:
        paths: Isolated filesystem receiving all appliance file accesses.

    Returns:
        An initializer using the test process's existing UID and GID.
    """
    home = paths.root / "home/retro"
    state = runtime.StateInitializer(os.getuid(), os.getgid(), home)
    for name in ("roms", "bios", "system"):
        (state.final / name).mkdir(parents=True, exist_ok=True)
    for name, text in (
        ("data.version", "43.1\n"),
        ("batocera.conf", "system.language=en_US\n"),
        ("machine-id", "fixture-machine-identity\n"),
    ):
        (state.final / "system" / name).write_text(text, encoding="utf-8")
    paths.file("/usr/share/batocera/batocera.version", "43.1\n")
    return state


@pytest.mark.parametrize("damage", ["release", "empty", "symlink", "escape"])
def test_state_outputs_refuse_stale_missing_or_aliased_identity(
    damage: str, appliance: RootedPaths
) -> None:
    """Require nonempty contained regular outputs matching the packaged release."""
    state = prepared_state(appliance)
    state.validate_outputs()
    output = state.final / "system/machine-id"
    if damage == "release":
        (state.final / "system/data.version").write_text("42\n", encoding="utf-8")
    elif damage == "empty":
        output.write_bytes(b"")
    else:
        destination = (
            state.final / "system/batocera.conf"
            if damage == "symlink"
            else appliance.file("/outside/identity")
        )
        output.unlink()
        output.symlink_to(destination)
    with pytest.raises(RuntimeError, match="initialized"):
        state.validate_outputs()


@pytest.mark.parametrize("damage", ["identity", "marker-link", "work", "content"])
def test_state_startup_refusal_preserves_foreign_and_interrupted_content(
    damage: str, appliance: RootedPaths
) -> None:
    """Refuse incompatible or interrupted homes before stock mutation begins."""
    state = prepared_state(appliance)
    if damage in {"identity", "marker-link"}:
        marker = json.dumps(
            {"release": "43.1", "puid": os.getuid() + 1, "pgid": os.getgid()}
        )
        if damage == "identity":
            state.marker.write_text(marker, encoding="utf-8")
        else:
            foreign = appliance.file("/foreign-marker", marker)
            state.marker.symlink_to(foreign)
        reason = "state release/identity mismatch"
    elif damage == "work":
        state.work.mkdir()
        (state.work / "evidence").write_bytes(b"interrupted population")
        reason = "interrupted or unrelated"
    else:
        reason = "unrecognized contents"
    configuration = state.final / "system/batocera.conf"
    with pytest.raises(RuntimeError, match=reason):
        state.run()
    assert configuration.read_text(encoding="utf-8") == "system.language=en_US\n"
    if damage == "work":
        assert (state.work / "evidence").read_bytes() == b"interrupted population"
    if damage == "marker-link":
        assert state.marker.is_symlink()
    assert not state.seed.exists()


def test_account_creation_is_confined_and_existing_identity_is_not_rewritten(
    appliance: RootedPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Append absent identities once and refuse an incompatible existing user."""
    group_file = appliance.file("/etc/group", "stock:x:12:\n")
    passwd_file = appliance.file("/etc/passwd", "stock:x:12:12::/:/bin/false\n")

    def missing_number(number: int) -> None:
        raise KeyError(number)

    def missing_name(name: str) -> None:
        raise KeyError(name)

    monkeypatch.setattr(grp, "getgrgid", missing_number)
    monkeypatch.setattr(grp, "getgrnam", missing_name)
    monkeypatch.setattr(pwd, "getpwuid", missing_number)
    monkeypatch.setattr(pwd, "getpwnam", missing_name)
    assert runtime.account(1234, 2345) == "gowfull1234"
    assert (
        group_file.read_text(encoding="utf-8") == "stock:x:12:\ngowfull2345:x:2345:\n"
    )
    assert passwd_file.read_text(encoding="utf-8") == (
        "stock:x:12:12::/:/bin/false\n"
        "gowfull1234:x:1234:2345:GoW full x86:/userdata/system:/bin/bash\n"
    )

    def existing_group(number: int) -> grp.struct_group:
        return grp.struct_group(("existing", "x", number, []))

    def incompatible_user(number: int) -> pwd.struct_passwd:
        return pwd.struct_passwd(("existing", "x", number, 99, "", "/", "/bin/false"))

    monkeypatch.setattr(grp, "getgrgid", existing_group)
    monkeypatch.setattr(pwd, "getpwuid", incompatible_user)
    before = passwd_file.read_bytes(), group_file.read_bytes()
    with pytest.raises(RuntimeError, match="incompatible primary GID"):
        runtime.account(1234, 2345)
    assert (passwd_file.read_bytes(), group_file.read_bytes()) == before


def test_wayland_connection_borrows_socket_permissions_and_owns_only_connection(
    tmp_path: Path,
) -> None:
    """Connect locally without relaxing the server's directory or socket mode."""
    path = tmp_path / "wayland-fixture"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        server.listen(1)
        path.chmod(0o600)
        before = path.stat().st_mode, tmp_path.stat().st_mode
        with runtime.connect_wayland(
            {"XDG_RUNTIME_DIR": str(tmp_path), "WAYLAND_DISPLAY": path.name}
        ) as connection:
            accepted, _ = server.accept()
            with accepted:
                connection.sendall(b"owned-session")
                assert accepted.recv(32) == b"owned-session"
                assert connection.gettimeout() is None
        assert path.exists()
        assert (path.stat().st_mode, tmp_path.stat().st_mode) == before
    with pytest.raises(RuntimeError, match="WAYLAND_DISPLAY is missing"):
        runtime.connect_wayland({})


class FrontendProcesses:
    """Replace stock executables with owned Python processes and literal results."""

    def __init__(self, directory: Path, stop_flag: str) -> None:
        """Select which stock flag the first frontend process creates."""
        self.directory = directory
        self.stop_flag = stop_flag
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None,
        stdout: TextIO | int | None,
        stderr: int | None,
        pass_fds: Sequence[int],
    ) -> subprocess.Popen[bytes]:
        """Record selected frontend inputs and run an independently specified child."""
        assert env is not None
        self.calls.append((list(command), dict(env)))
        flag = self.stop_flag if len(self.calls) == 1 else ""
        program = (
            "import pathlib,sys; "
            "flag=sys.argv[1]; "
            "pathlib.Path(sys.argv[2],flag).touch() if flag else None; "
            "raise SystemExit(7)"
        )
        return runtime.launch_process(
            [sys.executable, "-c", program, flag, str(self.directory)],
            env=env,
            stdout=stdout,
            stderr=stderr,
            pass_fds=pass_fds,
        )


@pytest.mark.parametrize(
    "flag", ["restart.please", "reboot.please", "shutdown.please", ""]
)
def test_frontend_flags_control_restarts_and_restore_caller_resources(
    flag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Honor stock restart/quit decisions without changing the caller's cwd or env."""
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    executable = tmp_path / "batocera-settings-get"
    executable.write_text(f"#!{sys.executable}\nprint('fr_FR')\n", encoding="utf-8")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    original_chdir = os.chdir

    def enter_userdata(path: str | Path) -> None:
        original_chdir(userdata if str(path) == "/userdata" else path)

    monkeypatch.setattr(os, "chdir", enter_userdata)
    cwd = Path.cwd()
    handlers = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    process_factory = FrontendProcesses(tmp_path, flag)
    frontend = runtime.Frontend(process_factory, time.monotonic, time.sleep)
    env = dict(os.environ, LANG="caller-language")
    result = frontend.run(env, tmp_path, ["fixture-frontend", "--windowed"])
    assert result == (0 if flag in {"reboot.please", "shutdown.please"} else 7)
    assert len(process_factory.calls) == (2 if flag == "restart.please" else 1)
    assert process_factory.calls[0][0] == ["fixture-frontend", "--windowed"]
    if flag == "restart.please":
        assert process_factory.calls[1][0] == [
            "fixture-frontend",
            "--windowed",
            "--no-startup-game",
        ]
    assert all(
        environment["LANG"] == "fr_FR.UTF-8" for _, environment in process_factory.calls
    )
    assert env["LANG"] == "caller-language"
    assert Path.cwd() == cwd
    assert all(
        signal.getsignal(number) == handler for number, handler in handlers.items()
    )
    assert not any((tmp_path / name).exists() for name in runtime.Frontend.FLAGS)
    assert frontend.children == []


class SessionProcesses:
    """Supply real local children for display, bus, daemon and frontend roles."""

    def __init__(self, directory: Path) -> None:
        """Borrow the private session directory used for readiness effects."""
        self.directory = directory
        self.children: list[subprocess.Popen[bytes]] = []
        self.environments: list[dict[str, str]] = []

    def __call__(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None,
        stdout: TextIO | int | None,
        stderr: int | None,
        pass_fds: Sequence[int],
    ) -> subprocess.Popen[bytes]:
        """Allocate processes whose readiness is visible through files and procfs."""
        assert env is not None
        self.environments.append(dict(env))
        if command[0] == "dbus-daemon":
            program = (
                "import socket,sys,time; "
                "s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); time.sleep(60)"
            )
            arguments = [str(self.directory / "bus")]
        elif command[0] == "fixture-frontend":
            program = (
                "import json,os,pathlib,sys; "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(os.environ))); "
                "raise SystemExit(17)"
            )
            arguments = [str(self.directory / "frontend.json")]
        else:
            program = (
                "import signal,time; "
                "signal.signal(signal.SIGHUP,lambda *_:None); time.sleep(60)"
            )
            arguments = []
        child = runtime.launch_process(
            [sys.executable, "-c", program, *arguments],
            env=env,
            stdout=stdout,
            stderr=stderr,
            pass_fds=pass_fds,
        )
        self.children.append(child)
        return child


def fixture_executable(path: Path, program: str) -> None:
    """Write an owned executable running only the supplied local Python fixture."""
    path.write_text(f"#!{sys.executable}\n{program}\n", encoding="utf-8")
    path.chmod(0o700)


def test_session_startup_authenticates_before_frontend_and_revokes_resources(
    nvidia_payload: RootedPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise normal startup ordering and cleanup with no native display claims."""
    paths = nvidia_payload
    directory = paths.root / "session"
    directory.mkdir()
    tools = paths.root / "tools"
    tools.mkdir()
    fixture_executable(
        tools / "xauth",
        "import pathlib,sys; pathlib.Path(sys.argv[2]).write_bytes(b'fixture-cookie')",
    )
    fixture_executable(
        tools / "xset",
        "import os,pathlib; "
        "assert pathlib.Path(os.environ['XAUTHORITY']).read_bytes()"
        "==b'fixture-cookie'; "
        "assert os.environ['DISPLAY']==':0'",
    )
    fixture_executable(
        tools / "batocera-resolution",
        "import pathlib,sys; "
        f"pathlib.Path({str(directory / 'resolution.json')!r})"
        ".write_text(repr(sys.argv[1:]))",
    )
    fixture_executable(
        tools / "hotkeygen",
        "import pathlib,sys; "
        f"pathlib.Path({str(directory / 'context.txt')!r})"
        ".write_text(repr(sys.argv[1:]))",
    )
    for name in ("pcm", "ctl"):
        paths.file(f"/usr/lib/alsa-lib/libasound_module_{name}_pulse.so")

    def session_paths(value: str | Path) -> Path:
        """Expose only real child status records alongside the appliance fixture."""
        path = Path(value)
        if len(path.parts) == 4 and path.parts[1] == "proc" and path.parts[2].isdigit():
            return path
        return paths(value)

    monkeypatch.setattr(runtime, "Path", session_paths)
    monkeypatch.setenv("PATH", str(tools))
    descriptor = os.open(os.devnull, os.O_RDONLY)
    env = {
        "PATH": str(tools),
        "GOW_CHILD_RUNTIME": str(directory),
        "GOW_XAUTH": str(tools / "xauth"),
        "GOW_XWAYLAND": "fixture-xwayland",
        "WAYLAND_SOCKET": str(descriptor),
        "WAYLAND_DISPLAY": "wolf-display",
        "SWAYSOCK": "wolf-control",
        "PULSE_SERVER": "/fixture/pulse",
        "PULSE_SINK": "fixture-sink",
        "PULSE_SOURCE": "fixture-sink.monitor",
        "GAMESCOPE_WIDTH": "1280",
        "GAMESCOPE_HEIGHT": "720",
    }
    processes = SessionProcesses(directory)
    session = runtime.Session(processes, time.monotonic, time.sleep)
    assert session.run(["fixture-frontend"], env) == 17
    app_env = json.loads((directory / "frontend.json").read_text(encoding="utf-8"))
    assert app_env["DISPLAY"] == ":0"
    assert app_env["HOME"] == "/userdata/system"
    assert app_env["XDG_RUNTIME_DIR"] == str(directory)
    assert app_env["SDL_VIDEODRIVER"] == "x11"
    assert app_env["QT_QPA_PLATFORM"] == "xcb"
    assert app_env["PULSE_SERVER"] == "unix:/fixture/pulse"
    assert app_env["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={directory}/bus"
    assert not {"WAYLAND_DISPLAY", "WAYLAND_SOCKET", "SWAYSOCK"} & app_env.keys()
    assert (directory / "resolution.json").read_text(encoding="utf-8") == (
        "['setOutput', 'auto']"
    )
    assert (directory / "context.txt").read_text(encoding="utf-8") == (
        "['--default-context']"
    )
    assert env["WAYLAND_DISPLAY"] == "wolf-display"
    assert env["PULSE_SERVER"] == "/fixture/pulse"
    assert processes.environments[0]["WAYLAND_SOCKET"] == str(descriptor)
    assert len(processes.children) == 5
    assert all(child.poll() is not None for child in processes.children)
    assert not (directory / "Xauthority").exists()
    assert (directory / "xwayland.log").is_file()
    with pytest.raises(OSError, match=r"\[Errno 9\]") as error:
        os.fstat(descriptor)
    assert error.value.errno == errno.EBADF
