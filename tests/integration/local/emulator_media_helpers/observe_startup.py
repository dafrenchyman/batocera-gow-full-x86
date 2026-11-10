"""Retain early launcher failure diagnostics through reader cleanup."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from batocera_gow.runtime.emulator_lifecycle import (
    EmulatorLifecycle,
    ExitBudgets,
    PrivateOutput,
    TransitionError,
)
from batocera_gow.runtime.emulator_probe import EmulatorProbe
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.native_diagnostics import publish_json


def main() -> None:
    """Run the isolated diagnostic fixture."""
    probe = EmulatorProbe(Path(sys.argv[1]), case="psx-duckstation")
    writer: int | None
    reader, writer = os.pipe()
    launcher = subprocess.Popen(  # noqa: S603  # Fixed sibling script; fixture variant argv.
        [
            sys.executable,
            str(Path(__file__).with_name("diagnostics_startup_launcher.py")),
            sys.argv[2],
        ],
        stdin=subprocess.PIPE,
        stdout=writer,
        stderr=subprocess.PIPE,
    )
    probe.launcher = launcher
    probe.launcher_start = process_stat(launcher.pid)[1]
    probe.launcher_output = PrivateOutput(os.fdopen(reader, "rb", buffering=0))
    try:
        if sys.argv[2] != "no-eof":
            os.close(writer)
            writer = None
        launcher.communicate(b"go\n" + sys.stdin.buffer.read(), timeout=5)

        # No native input is authorized by this host fixture. Only the permission
        # boundary is controlled; observe/pinning, pipe and lifecycle are real.
        class Clock:
            """Reject waits after the completed launcher has been observed."""

            def now(self) -> float:
                """Return the fixed lifecycle origin in seconds."""
                return 0.0

            def sleep(self, seconds: float) -> None:
                """Reject any additional lifecycle delay."""
                del seconds
                message = "Completed launcher must fail without waiting"
                raise RuntimeError(message)

        try:
            with patch.object(probe, "permission", new=lambda: None):
                EmulatorLifecycle(probe, Clock(), ExitBudgets()).run()
        except TransitionError as error:
            if str(error) != "Launcher exited before native chord":
                raise
        else:
            message = "Early launcher was accepted"
            raise RuntimeError(message)
        probe.retain_boundary("failure")
        # A second observation must not replace retained diagnostics after clearing.
        probe.launcher_output.close()
        probe.observe()
        probe.retain_boundary("cleanup-returned")
        publish_json(probe.directory / "emulator-probe.json", probe.result)
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=2)
        probe.launcher_output.close()
        if writer is not None:
            os.close(writer)


if __name__ == "__main__":
    main()
