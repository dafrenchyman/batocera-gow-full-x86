"""Observe termination using real pipes, pidfds and private boundaries."""

import os
import select
import subprocess
import sys
from pathlib import Path

from batocera_gow.runtime.emulator_lifecycle import PrivateOutput, ProcessIdentity
from batocera_gow.runtime.emulator_probe import EmulatorProbe
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.native_diagnostics import publish_json


def main() -> None:
    """Run the isolated diagnostic fixture."""
    probe = EmulatorProbe(Path(sys.argv[1]))
    writer: int | None
    reader, writer = os.pipe()
    launcher = subprocess.Popen(  # noqa: S603  # Fixed sibling script; synthetic record argv.
        [
            sys.executable,
            str(Path(__file__).with_name("diagnostics_termination_launcher.py")),
            sys.argv[2],
        ],
        stdin=subprocess.PIPE,
        stdout=writer,
        stderr=subprocess.PIPE,
    )
    if launcher.stdin is None or launcher.stderr is None:
        message = "Owned launcher pipes unavailable"
        raise RuntimeError(message)
    probe.launcher = launcher
    probe.launcher_start = process_stat(launcher.pid)[1]
    probe.launcher_output = PrivateOutput(os.fdopen(reader, "rb", buffering=0))
    try:
        if sys.argv[3] != "no-eof":
            os.close(writer)
            writer = None
        if not select.select([launcher.stderr], [], [], 2)[0]:
            message = "Child identity unavailable"
            raise RuntimeError(message)
        pid = int(launcher.stderr.readline())
        probe.emulator_fd = os.pidfd_open(pid)
        probe.emulator_identity = ProcessIdentity(pid, process_stat(pid)[1])
        launcher.stdin.write(b"exit\n")
        launcher.stdin.flush()
        probe.observe_termination(launcher.wait(timeout=2))
        probe.launcher_output.close()
        probe.retain_boundary("cleanup-returned")
        publish_json(probe.directory / "emulator-probe.json", probe.result)
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=2)
        probe.launcher_output.close()
        if probe.emulator_fd is not None:
            os.close(probe.emulator_fd)
        if writer is not None:
            os.close(writer)
        launcher.stdin.close()
        launcher.stderr.close()


if __name__ == "__main__":
    main()
