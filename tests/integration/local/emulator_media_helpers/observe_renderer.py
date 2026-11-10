"""Bind generated DuckStation renderer settings to the pinned process's open log."""

import json
import os
import subprocess
import sys
from pathlib import Path

from batocera_gow.runtime import emulator_probe as module
from batocera_gow.runtime.emulator_lifecycle import ProcessIdentity
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Observe the buffered renderer log before and after the real writer exits."""
    directory, mode, renderer = (Path(sys.argv[1]), sys.argv[2], sys.argv[3])
    module.DUCKSTATION_SETTINGS = directory / "settings.ini"
    probe = module.EmulatorProbe(
        directory,
        case="psx-duckstation-vulkan" if renderer == "Vulkan" else "psx-duckstation",
    )
    probe.result["qt_visual"] = None if renderer == "Vulkan" else "0x125"
    path = directory / ("other.log" if mode == "unopened" else "duckstation.log")
    child = subprocess.Popen(  # noqa: S603  # Fixed checked buffered-log writer with owned file argv.
        [
            sys.executable,
            str(Path(__file__).with_name("consumer_renderer_log.py")),
            str(path),
            str(directory / "other.log"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert child.stdout is not None
    assert child.stdin is not None
    try:
        assert child.stdout.readline() == b"opened\n"
        probe.emulator_identity = ProcessIdentity(child.pid, process_stat(child.pid)[1])
        empty_alive = (directory / "duckstation.log").read_bytes() == b""
        try:
            passed = probe.duckstation_renderer()
            assert probe.result.get("renderer") is None
            child.stdin.write(b"exit\n")
            child.stdin.flush()
            assert child.wait(timeout=2) == 0
            if passed:
                probe.finalize_duckstation_renderer()
        except (ProbeError, OSError):
            passed = False
        sys.stdout.write(
            json.dumps(
                {
                    "passed": passed,
                    "empty_alive": empty_alive,
                    "renderer": probe.result.get("renderer"),
                }
            )
            + "\n"
        )
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=2)
        if probe.duckstation_log_fd is not None:
            os.close(probe.duckstation_log_fd)


if __name__ == "__main__":
    main()
