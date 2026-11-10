"""Exercise installed runtime identity, audio and owned-process boundaries."""

import ctypes
import ctypes.util
import errno
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from batocera_gow.runtime import runtime


@pytest.fixture
def supervisor() -> Iterator[runtime.ProcessSupervisor]:
    """Reap all fixture-owned process groups even after an assertion fails."""
    owner = runtime.ProcessSupervisor(
        runtime.launch_process, time.monotonic, time.sleep
    )
    try:
        yield owner
    finally:
        owner.close()


@pytest.fixture
def sleep_command() -> list[str]:
    """Resolve the harmless long-lived executable used by ownership fixtures."""
    executable = shutil.which("sleep")
    assert executable is not None
    return [executable, "60"]


class TestRuntimeValues:
    """Keep configuration parsing independent from host account defaults."""

    def test_identity_preserves_explicit_zero(self) -> None:
        """Accept root explicitly rather than replacing zero with defaults."""
        assert runtime.identity({}) == (1000, 1000)
        assert runtime.identity({"PUID": "0", "PGID": "0"}) == (0, 0)

    @pytest.mark.parametrize("value", ["", "-1", " 0", "1:2", "4294967295", "one"])
    def test_identity_rejects_invalid_ids(self, value: str) -> None:
        """Reject ambiguous, negative and out-of-range account identifiers."""
        with pytest.raises(RuntimeError):
            runtime.identity({"PUID": value})

    @pytest.mark.parametrize(("value", "expected"), [("1920", 1920), ("1", 1)])
    def test_dimensions(self, value: str, expected: int) -> None:
        """Accept positive decimal dimensions, including the smallest valid value."""
        assert runtime.numeric(value, "width", positive=True) == expected

    @pytest.mark.parametrize("value", ["0", "-2", "1x2", ""])
    def test_dimensions_reject_invalid_values(self, value: str) -> None:
        """Reject empty, nondecimal and nonpositive dimensions."""
        with pytest.raises(RuntimeError):
            runtime.numeric(value, "width", positive=True)

    @pytest.mark.parametrize(
        ("server", "expected"),
        [
            ("unix:/run/wolf/pulse", "unix:/run/wolf/pulse"),
            ("tcp:session-host:4713", "tcp:session-host:4713"),
            ("/run/wolf/pulse", "unix:/run/wolf/pulse"),
        ],
    )
    def test_pulse_routing_keeps_session_identity(
        self, server: str, expected: str
    ) -> None:
        """Normalize socket syntax without losing negotiated sink or source."""
        env = {
            "PULSE_SERVER": server,
            "PULSE_SINK": "virtual_sink_123",
            "PULSE_SOURCE": "virtual_sink_123.monitor",
        }
        result = runtime.normalize_audio(env.copy())
        assert result["PULSE_SERVER"] == expected
        assert result["PULSE_SINK"] == env["PULSE_SINK"]
        assert result["PULSE_SOURCE"] == env["PULSE_SOURCE"]

    def test_pulse_routing_requires_session_sink(self) -> None:
        """Refuse routing that cannot identify the negotiated session sink."""
        with pytest.raises(RuntimeError):
            runtime.normalize_audio({"PULSE_SERVER": "unix:/socket"})

    def test_alsa_session_route_survives_appliance_and_user_load_hooks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pytestconfig: pytest.Config,
    ) -> None:
        """Evaluate real ALSA hooks and keep Pulse defaults despite user overrides."""
        soname = ctypes.util.find_library("asound")
        stock = Path("/usr/share/alsa/alsa.conf")
        if soname is None or not stock.is_file():
            pytest.skip("libasound and stock ALSA definitions are required")
        library = ctypes.CDLL(soname)
        pointer = ctypes.c_void_p
        library.snd_config_update_r.argtypes = [
            ctypes.POINTER(pointer),
            ctypes.POINTER(pointer),
            ctypes.c_char_p,
        ]
        library.snd_config_update_free.argtypes = [pointer]
        library.snd_config_search.argtypes = [
            pointer,
            ctypes.c_char_p,
            ctypes.POINTER(pointer),
        ]
        library.snd_config_evaluate.argtypes = [
            pointer,
            pointer,
            pointer,
            ctypes.POINTER(pointer),
        ]
        library.snd_config_get_string.argtypes = [
            pointer,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        library.snd_config_delete.argtypes = [pointer]
        root, update = pointer(), pointer()
        (tmp_path / ".asoundrc").write_text(
            "pcm.!default { type null }\nctl.!default { type hw card 0 }\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("PULSE_SERVER", "unix:/session-specific-pulse")
        monkeypatch.setenv("PULSE_SINK", "virtual_sink_test")
        monkeypatch.setenv("PULSE_SOURCE", "virtual_sink_test.monitor")
        monkeypatch.setattr(
            runtime, "HERE", pytestconfig.rootpath / "build-assets/runtime"
        )
        configuration = runtime.normalize_audio(
            {
                "PULSE_SERVER": "unix:/session-specific-pulse",
                "PULSE_SINK": "virtual_sink_test",
                "PULSE_SOURCE": "virtual_sink_test.monitor",
            }
        )["ALSA_CONFIG_PATH"]
        try:
            assert (
                library.snd_config_update_r(
                    ctypes.byref(root), ctypes.byref(update), os.fsencode(configuration)
                )
                >= 0
            )
            for name in (b"pcm.default", b"ctl.default"):
                node = pointer()
                assert library.snd_config_search(root, name, ctypes.byref(node)) == 0
                assert library.snd_config_evaluate(node, root, None, None) >= 0
                expected = {"type": "pulse", "server": "unix:/session-specific-pulse"}
                if name == b"pcm.default":
                    expected["device"] = "virtual_sink_test"
                for key, value in expected.items():
                    field, text = pointer(), ctypes.c_char_p()
                    assert (
                        library.snd_config_search(
                            node, key.encode(), ctypes.byref(field)
                        )
                        == 0
                    )
                    assert library.snd_config_get_string(field, ctypes.byref(text)) == 0
                    assert text.value is not None
                    assert text.value.decode() == value
        finally:
            if root.value:
                library.snd_config_delete(root)
            if update.value:
                library.snd_config_update_free(update)


class TestProcessOwnership:
    """Distinguish owned session groups from unrelated caller processes."""

    def test_owned_groups_exit_unrelated_process_survives(
        self, supervisor: runtime.ProcessSupervisor, sleep_command: list[str]
    ) -> None:
        """Terminate owned groups without killing another independent session."""
        # The fixture resolves sleep and supplies only a fixed duration.
        with subprocess.Popen(sleep_command, start_new_session=True) as unrelated:  # noqa: S603
            try:
                child = supervisor.spawn(sleep_command)
                supervisor.close()
                assert child.poll() is not None
                with pytest.raises(ProcessLookupError):
                    os.killpg(child.pid, 0)
                assert unrelated.poll() is None
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_dead_required_process_fails(
        self, supervisor: runtime.ProcessSupervisor
    ) -> None:
        """Treat a completed required dependency as a session failure."""
        child = supervisor.spawn([sys.executable, "-c", "raise SystemExit(7)"])
        child.wait(timeout=5)
        with pytest.raises(RuntimeError):
            supervisor.check([child])

    def test_borrowed_output_stream_survives_owned_process_cleanup(
        self, tmp_path: Path, supervisor: runtime.ProcessSupervisor
    ) -> None:
        """Reap the child without closing the caller's supplied output stream."""
        with (tmp_path / "child.log").open("w+", encoding="utf-8") as stream:
            child = supervisor.spawn(
                [sys.executable, "-c", "print('owned child')"], stdout=stream
            )
            child.wait(timeout=5)
            supervisor.close()
            assert not stream.closed
            stream.seek(0)
            assert stream.read() == "owned child\n"
            stream.write("caller still owns this stream\n")


def stock_environment_fixture(
    env: Mapping[str, str], directory: Path
) -> tuple[dict[str, str], dict[str, str]]:
    """Stand in for unavailable stock NVIDIA discovery during allocation tests."""
    assert directory == Path(env["GOW_CHILD_RUNTIME"])
    return dict(env), dict(env)


def stock_audio_fixture() -> None:
    """Skip only the external stock ALSA plugin prerequisite for setup failures."""


@pytest.mark.parametrize("stage", ["cookie", "xauth", "log"])
def test_session_partial_setup_revokes_owned_resources(
    stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revoke transferred descriptors and cookies after each setup allocation fails."""
    monkeypatch.setattr(runtime, "nvidia_environments", stock_environment_fixture)
    monkeypatch.setattr(runtime, "require_alsa_pulse", stock_audio_fixture)
    cookie = tmp_path / "Xauthority"
    log = tmp_path / "xwayland.log"
    true = shutil.which("true")
    assert true is not None
    if stage == "cookie":
        cookie.write_bytes(b"foreign cookie")
    elif stage == "log":
        log.mkdir()
    descriptor = os.open(os.devnull, os.O_RDONLY)
    env = {
        "GOW_CHILD_RUNTIME": str(tmp_path),
        "WAYLAND_SOCKET": str(descriptor),
        "GOW_XAUTH": str(tmp_path / "missing-xauth") if stage == "xauth" else true,
        "PULSE_SERVER": "unix:/session-pulse",
        "PULSE_SINK": "session-sink",
        "PULSE_SOURCE": "session-sink.monitor",
    }
    original = {
        number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)
    }
    session = runtime.Session(runtime.launch_process, time.monotonic, time.sleep)
    expected_error = {
        "cookie": FileExistsError,
        "xauth": FileNotFoundError,
        "log": IsADirectoryError,
    }[stage]
    try:
        with pytest.raises(expected_error):
            session.run([sys.executable, "-c", "raise SystemExit(0)"], env)
        if stage == "cookie":
            assert cookie.read_bytes() == b"foreign cookie"
        else:
            assert not cookie.exists()
        if stage == "log":
            assert log.is_dir()
        assert session.children == []
        for number, handler in original.items():
            assert signal.getsignal(number) == handler
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(descriptor)
    finally:
        session.close()
        try:
            os.close(descriptor)
        except OSError as error:
            if error.errno != errno.EBADF:
                raise
