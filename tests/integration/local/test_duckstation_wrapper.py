"""Exercise installed DuckStation policy, owned overrides and real exec behavior."""

import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.runtime.duckstation_backend import active_backend
from batocera_gow.runtime.duckstation_install import (
    install_override,
    launcher_environment,
)
from batocera_gow.runtime.duckstation_visual import (
    VisualError,
    select_visual,
)


@pytest.fixture
def override_asset(pytestconfig: pytest.Config) -> Path:
    """Provide the declared build input, not a Python-module-adjacent resource."""
    return pytestconfig.rootpath / "build-assets/runtime/es_systems_gow_duckstation.cfg"


def invoke(program: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run installed modules with a finite lifetime and inherited stock environment."""
    return subprocess.run(  # noqa: S603 - The interpreter and test program are controlled fixtures.
        [sys.executable, "-c", program, *arguments],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


@pytest.fixture
def profile(tmp_path: Path) -> tuple[Path, Path]:
    """Create owned userdata containing an unrelated catalog to preserve."""
    home = tmp_path / "home"
    destination = home / "userdata/system/configs/emulationstation"
    destination.mkdir(parents=True)
    (destination / "es_systems_other.cfg").write_text(
        "<systemList><system><name>nes</name><command>user-nes</command></system></systemList>",
        encoding="utf-8",
    )
    return home, destination


def test_startup_installs_only_partial_command_and_repeated_install_is_noop(
    profile: tuple[Path, Path],
    override_asset: Path,
) -> None:
    """Install once without replacing unrelated bytes or an existing inode."""
    home, directory = profile
    before = (directory / "es_systems_other.cfg").read_bytes()
    assert (
        install_override(home, os.getuid(), os.getgid(), override_asset) == "installed"
    )
    destination = directory / "es_systems_gow_duckstation.cfg"
    identity = destination.stat()
    assert destination.read_bytes() == override_asset.read_bytes()
    assert (
        install_override(home, os.getuid(), os.getgid(), override_asset)
        == "already-installed"
    )
    current = destination.stat()
    assert (current.st_ino, current.st_mtime_ns) == (
        identity.st_ino,
        identity.st_mtime_ns,
    )
    assert (directory / "es_systems_other.cfg").read_bytes() == before
    (directory / "es_systems_conflict.cfg").write_text(
        "<systemList><system><name>psx</name><command>user-psx</command></system></systemList>",
        encoding="utf-8",
    )
    assert (
        install_override(home, os.getuid(), os.getgid(), override_asset)
        == "preserved-conflicting-psx-command"
    )
    assert destination.stat().st_ino == identity.st_ino


@pytest.mark.parametrize(
    "conflict",
    [
        "destination",
        "partial",
        "full",
        "backend",
        "malformed",
        "symlink",
        "directory-symlink",
    ],
)
def test_startup_preserves_modified_or_conflicting_user_commands(
    tmp_path: Path,
    profile: tuple[Path, Path],
    override_asset: Path,
    conflict: str,
) -> None:
    """Refuse unsafe directories and leave foreign commands and targets untouched."""
    home, directory = profile
    destination = directory / "es_systems_gow_duckstation.cfg"
    outside = tmp_path / "foreign"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("never modify", encoding="utf-8")
    if conflict == "destination":
        destination.write_text("user-owned command", encoding="utf-8")
    elif conflict == "symlink":
        destination.symlink_to(sentinel)
    elif conflict == "directory-symlink":
        directory.rename(directory.with_name("displaced"))
        directory.symlink_to(outside, target_is_directory=True)
    else:
        name = "es_systems.cfg" if conflict == "full" else "es_systems_user.cfg"
        contents = "<command>custom-psx</command>"
        if conflict == "backend":
            contents = (
                '<emulators><emulator name="duckstation" command="custom"/></emulators>'
            )
        text = (
            "<systemList><system><name>psx</name>" + contents + "</system></systemList>"
        )
        (directory / name).write_text(
            "invalid XML" if conflict == "malformed" else text,
            encoding="utf-8",
        )
    if conflict == "directory-symlink":
        with pytest.raises((OSError, ValueError)):
            install_override(home, os.getuid(), os.getgid(), override_asset)
    else:
        result = install_override(home, os.getuid(), os.getgid(), override_asset)
        assert result.startswith("preserved-")
    assert sentinel.read_text(encoding="utf-8") == "never modify"
    if conflict == "destination":
        assert destination.read_text(encoding="utf-8") == "user-owned command"
    elif conflict == "symlink":
        assert destination.is_symlink()
    else:
        assert not destination.exists()


EXEC = """
import sys
from pathlib import Path
from batocera_gow.runtime import duckstation_wrapper as wrapper
wrapper.STOCK_EXECUTABLE = sys.argv[2]
def discover():
    Path(sys.argv[3]).write_text('discovery ran', encoding='utf-8')
    if sys.argv[4] == 'failure':
        raise wrapper.VisualError('controlled discovery failure')
    return 0x125
wrapper.launch(
    ['-batch', '-nogui', '--', 'private disc.chd'], Path(sys.argv[1]), discover,
)
"""


@pytest.mark.parametrize("renderer", ["OpenGL", "Vulkan", "Software", "Automatic"])
def test_wrapper_exec_preserves_pid_environment_and_non_qt_arguments(
    tmp_path: Path,
    renderer: str,
) -> None:
    """Exec the stock consumer without changing its parent, loader or media argv."""
    settings = tmp_path / "settings.ini"
    settings.write_text("[GPU]\nRenderer=" + renderer + "\n", encoding="utf-8")
    child = tmp_path / "stock-consumer"
    child.write_text(
        "#!" + sys.executable + "\nimport json, os, sys\n"
        "print(json.dumps({'argv':sys.argv[1:],'parent':os.getppid(),"
        "'path':os.environ['PATH'],'loader':os.environ.get('LD_LIBRARY_PATH')}))\n",
        encoding="utf-8",
    )
    child.chmod(0o755)
    witness = tmp_path / "discovery"
    result = invoke(EXEC, str(settings), str(child), str(witness), "success")
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["parent"] == os.getpid(), "wrapper must exec rather than spawn"
    suffix = ["-batch", "-nogui", "--", "private disc.chd"]
    assert observed["argv"] == (
        ["-visual", "0x125", *suffix] if renderer == "OpenGL" else suffix
    )
    assert observed["path"] == os.environ["PATH"]
    assert observed["loader"] == os.environ.get("LD_LIBRARY_PATH")
    assert witness.exists() is (renderer == "OpenGL")


@pytest.mark.parametrize(
    "contents",
    [
        "[GPU]\nRenderer=OpenGL\n",
        "[GPU]\n",
        "[GPU]\nRenderer=OpenGL\nRenderer=Vulkan\n",
    ],
)
def test_wrapper_failure_never_executes_uncorrected_or_falls_back(
    tmp_path: Path,
    contents: str,
) -> None:
    """Invalid settings or failed discovery never reach the stock executable."""
    settings = tmp_path / "settings.ini"
    settings.write_text(contents, encoding="utf-8")
    child = tmp_path / "stock-consumer"
    marker = tmp_path / "launched"
    child.write_text(
        "#!"
        + sys.executable
        + "\nfrom pathlib import Path\n"
        + f"Path({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    child.chmod(0o755)
    result = invoke(
        EXEC, str(settings), str(child), str(tmp_path / "discovery"), "failure"
    )
    assert result.returncode != 0
    assert not marker.exists()


class DriverDisplay:
    """Supply ordered driver responses without opening a native display."""

    def __init__(self, scenario: str = "normal") -> None:
        """Select one controlled driver outcome and retain attempted contexts."""
        self.scenario = scenario
        self.tried: list[tuple[int, bool, int, int]] = []
        self.closed = False

    def initialize(self) -> None:
        """Leave the synthetic driver ready without allocating EGL resources."""

    def configs(self, *, es: bool) -> list[int]:
        """Return driver order with an oversized first candidate."""
        if self.scenario == "no-exact":
            return [90]
        return [40] if es else [90, 20, 30]

    def attribute(self, config: int, key: int) -> int:
        """Return native visual IDs or the candidate's component depth."""
        native_visual_attribute = 0x302E
        oversized_config = 90
        if key == native_visual_attribute:
            return {90: 0x925, 20: 0x125, 30: 0x325, 40: 0x425}[config]
        return 10 if config == oversized_config else 8

    def context_supported(
        self, config: int, *, es: bool, major: int, minor: int
    ) -> bool:
        """Record each attempt and accept desktop 4.5 or ES unless exhausted."""
        self.tried.append((config, es, major, minor))
        supported_minor = 5
        return (es or minor == supported_minor) and self.scenario != "exhausted"

    def validate(self, visual: int) -> None:
        """Reject a selected visual only for the foreign-screen scenario."""
        if self.scenario == "wrong-screen":
            message = f"Visual {visual} belongs to a different screen"
            raise VisualError(message)

    def close(self) -> None:
        """Record accidental disposal of the caller-owned driver session."""
        self.closed = True


def test_live_policy_selects_first_exact_config_not_first_or_arbitrary_depth32() -> (
    None
):
    """Prefer the first exact RGBA8 configuration and preserve version order."""
    display = DriverDisplay()
    expected_visual = 0x125
    assert select_visual(display, prefer_es=False) == expected_visual
    assert display.tried == [(20, False, 4, 6), (20, False, 4, 5)]
    assert display.closed is False


def test_live_policy_retains_existing_es_preference_and_validates_selected_screen() -> (
    None
):
    """Retain ES preference while rejecting wrong screens and exhausted contexts."""
    preferred = DriverDisplay("prefer-es")
    expected_visual = 0x425
    assert select_visual(preferred, prefer_es=True) == expected_visual
    assert preferred.tried == [(40, True, 3, 2)]
    refused = DriverDisplay("wrong-screen")
    with pytest.raises(VisualError):
        select_visual(refused, prefer_es=False)
    assert refused.closed is False
    exhausted = DriverDisplay("exhausted")
    with pytest.raises(VisualError):
        select_visual(exhausted, prefer_es=False)
    expected_attempts = 14
    assert len(exhausted.tried) == expected_attempts
    assert preferred.closed is False
    assert exhausted.closed is False


@pytest.mark.parametrize("mode", ["OpenGL", "OpenGLES", "Vulkan"])
@pytest.mark.parametrize(
    "defect",
    [
        "none",
        "resize",
        "preference-only",
        "framebuffer-first",
        "context-first",
        "fallback",
        "recreated",
        "partial",
        "unrelated-tail",
        "device-tail",
        "context-tail",
        "fallback-tail",
        "header-tail",
    ],
)
def test_active_backend_requires_ordered_real_consumer_records(
    mode: str, defect: str
) -> None:
    """Classify only complete active-device evidence, never a preference or fallback."""
    api = "OpenGL" if mode == "OpenGLES" else mode
    attempt = "[    0.0100] I/Host: Trying to create a " + api + " GPU device...\n"
    context = ""
    if mode != "Vulkan":
        context = (
            "[    0.0200] I/OpenGLContext: Created an OpenGL"
            + (" ES" if mode == "OpenGLES" else "")
            + " context\n"
        )
    framebuffer = "[    0.0300] I/GPU_HW: Created HW framebuffer of 1024x512\n"
    complete = attempt + context + framebuffer
    records = {
        "none": complete,
        "preference-only": attempt,
        "framebuffer-first": framebuffer + attempt + context,
        "context-first": (
            (context or "[    0.0050] I/OpenGLContext: Created an OpenGL context\n")
            + attempt
            + framebuffer
        ),
        "resize": (
            complete + "[    0.0400] I/GPU_HW: Created HW framebuffer of 2048x1024\n"
        ),
        "fallback": (
            complete
            + "[    0.0400] E(CreateGPU): Failed to initialize OpenGL renderer, "
            "falling back to software renderer\n"
        ),
        "recreated": complete + attempt,
        "partial": complete.rstrip("\n"),
        "unrelated-tail": (
            complete + "[    0.0400] I/System: incomplete unrelated diagnostic"
        ),
        "device-tail": complete + attempt.rstrip("\n"),
        "context-tail": (complete + "[    0.0400] I/OpenGLContext: Created an OpenGL"),
        "fallback-tail": complete + "[    0.0400] E(CreateGPU): Failed to initialize",
        "header-tail": complete + "[    0.",
    }
    data = records[defect]
    assert active_backend(data.encode("utf-8")) == (
        mode if defect in ("none", "resize", "unrelated-tail") else None
    )


def test_live_policy_uses_driver_first_config_only_when_no_exact_rgba8_exists() -> None:
    """Fall back to driver order only when no exact RGBA8 configuration exists."""
    display = DriverDisplay("no-exact")
    expected_visual = 0x925
    assert select_visual(display, prefer_es=False) == expected_visual
    assert display.tried == [(90, False, 4, 6), (90, False, 4, 5)]


@pytest.mark.parametrize(
    "state", ["installed", "modified", "symlink", "missing", "conflicting"]
)
def test_native_launch_prefix_comes_from_the_exact_installed_es_override(
    tmp_path: Path,
    override_asset: Path,
    state: str,
) -> None:
    """Expose the wrapper only for an unchanged, unambiguous installed command."""
    installed = tmp_path / "es_systems_gow_duckstation.cfg"
    if state in ("installed", "conflicting"):
        installed.write_bytes(override_asset.read_bytes())
        if state == "conflicting":
            (tmp_path / "es_systems_custom.cfg").write_text(
                "<systemList><system><name>psx</name><command>user-psx</command></system></systemList>",
                encoding="utf-8",
            )
    elif state == "modified":
        installed.write_text(
            "<systemList><system><name>psx</name><command>custom</command></system></systemList>",
            encoding="utf-8",
        )
    elif state == "symlink":
        installed.symlink_to(override_asset)
    original = {
        "PATH": "/stock/bin:/usr/bin",
        "LD_LIBRARY_PATH": "/stock/libraries",
        "sentinel": "preserved",
    }
    environment = dict(original)
    if state != "installed":
        with pytest.raises((OSError, ValueError, RuntimeError)):
            launcher_environment(installed, override_asset, environment)
        assert environment == original
        return
    result = launcher_environment(installed, override_asset, environment)
    assert environment == original
    assert result == {
        "PATH": "/opt/gow-full-x86/emulator-wrappers:/stock/bin:/usr/bin",
        "LD_LIBRARY_PATH": "/stock/libraries",
        "sentinel": "preserved",
    }


def test_failed_publication_open_removes_only_owned_staging(
    profile: tuple[Path, Path],
    override_asset: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unwind staging after an OS open failure without touching user catalogs."""
    home, directory = profile
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    original_open = os.open

    def refuse_creation(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        """Fail at exclusive file creation while retaining actual directory I/O."""
        if flags & os.O_CREAT:
            raise PermissionError(errno.EACCES, "Controlled publication failure")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", refuse_creation)
        with pytest.raises(PermissionError):
            install_override(home, os.getuid(), os.getgid(), override_asset)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
