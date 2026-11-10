"""Retain pinned emulator failure diagnostics before launcher cleanup."""

import json
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

from batocera_gow.runtime.emulator_lifecycle import (
    EmulatorLifecycle,
    ExitBudgets,
    PrivateOutput,
    ProcessIdentity,
    TransitionError,
)
from batocera_gow.runtime.emulator_probe import EmulatorProbe
from batocera_gow.runtime.input_transport import process_stat
from batocera_gow.runtime.native_diagnostics import publish_json


def main() -> None:  # noqa: C901, PLR0912, PLR0915  # Keep synchronization phases within one owned process lifetime.
    """Run the isolated diagnostic fixture."""
    directory, variant, trigger = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    data = sys.stdin.buffer.read()
    probe = EmulatorProbe(directory, case="psx-duckstation")
    launcher = subprocess.Popen(  # noqa: S603  # Fixed sibling script; synthetic stderr argv.
        [
            sys.executable,
            str(Path(__file__).with_name("diagnostics_failure_launcher.py")),
            data[:32000].hex(),
            data[32000:].hex(),
            variant,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if launcher.stdin is None or launcher.stdout is None or launcher.stderr is None:
        message = "Owned launcher pipes unavailable"
        raise RuntimeError(message)
    probe.launcher = launcher
    probe.launcher_start = process_stat(launcher.pid)[1]
    probe.launcher_output = PrivateOutput(launcher.stdout)

    def control_line() -> bytes:
        """Read one bounded-deadline launcher synchronization line."""
        if launcher.stderr is None:
            message = "Owned launcher control unavailable"
            raise RuntimeError(message)
        if not select.select([launcher.stderr], [], [], 3)[0]:
            message = "Owned launcher control unavailable"
            raise RuntimeError(message)
        return launcher.stderr.readline()

    try:
        pid = int(control_line())
        probe.emulator_identity = ProcessIdentity(pid, process_stat(pid)[1])
        probe.emulator_fd = os.pidfd_open(pid)
        # An ordinary live pinned child must not acquire a failure diagnostic.
        live_watchdog = threading.Timer(2.0, lambda: os._exit(92))
        live_watchdog.start()
        probe.observe_startup_failure()
        live_watchdog.cancel()
        if "startup_failure_diagnostic" in probe.result:
            message = "Live startup acquired a failure diagnostic"
            raise RuntimeError(message)
        launcher.stdin.write(b"end\n")
        launcher.stdin.flush()
        if control_line() != b"ended\n":
            message = "Owned emulator did not exit"
            raise RuntimeError(message)
        deadline = time.monotonic() + 3
        while (
            variant not in ("delayed", "withheld")
            and probe.launcher_output.retained_bytes < len(data)
        ) or (variant == "eof" and not probe.launcher_output.observation()["eof"]):
            if time.monotonic() >= deadline:
                message = "Owned reader did not reach fixture boundary"
                raise RuntimeError(message)
            time.sleep(0.001)
        if variant == "unavailable":
            probe.launcher_output.close()
        if variant == "post-chord":
            probe.result["chord"] = {"pressed": True, "released": True}
        if variant in ("delayed", "withheld"):
            if probe.launcher_output.retained_bytes != 0:
                message = "Buffered child stderr escaped before failure observation"
                raise RuntimeError(message)
            launcher.stdin.write(b"settle\n")
            launcher.stdin.flush()
        # The writer stays open. This watchdog detects an unbounded EOF wait in
        # the consumer, not fixture startup or drainer throughput.
        settle_watchdog = threading.Timer(2.0, lambda: os._exit(91))
        settle_watchdog.start()
        if trigger == "boundary":
            probe.retain_boundary("failure")
        at_failure_boundary = probe.result.get("startup_failure_diagnostic")

        # Only the native permission gate is controlled. Process identity, pidfd,
        # launcher, reader, observation and lifecycle failure are real.
        class Clock:
            """Reject waits once the pinned emulator has exited."""

            def now(self) -> float:
                """Return the fixed lifecycle origin in seconds."""
                return 0.0

            def sleep(self, seconds: float) -> None:
                """Reject any additional lifecycle delay."""
                del seconds
                message = "Dead emulator must fail without another wait"
                raise RuntimeError(message)

        failure = None
        try:
            with patch.object(probe, "permission", new=lambda: None):
                EmulatorLifecycle(probe, Clock(), ExitBudgets()).run()
        except TransitionError as error:
            failure = type(error).__name__
        settle_watchdog.cancel()
        before_cleanup = probe.result.get("startup_failure_diagnostic")
        if trigger != "boundary":
            probe.retain_boundary("failure")
        launcher.stdin.write(b"late\n")
        launcher.stdin.flush()
        if control_line() != b"late\n":
            message = "Owned launcher did not reach late-output boundary"
            raise RuntimeError(message)
        deadline = time.monotonic() + 3
        while variant not in ("eof", "unavailable") and (
            probe.launcher_output.retained_bytes
            <= (0 if variant == "withheld" else len(data))
        ):
            if time.monotonic() >= deadline:
                message = "Owned reader did not receive late fixture bytes"
                raise RuntimeError(message)
            time.sleep(0.001)
        probe.observe()
        probe.retain_boundary("cleanup-start")
        probe.launcher_output.close()
        probe.observe()
        probe.retain_boundary("cleanup-returned")
        publish_json(directory / "emulator-probe.json", probe.result)
        sys.stdout.write(
            json.dumps(
                {
                    "failure": failure,
                    "launcher_pending": launcher.poll() is None,
                    "before_cleanup": before_cleanup,
                    "forced": probe.forced,
                    "at_failure_boundary": at_failure_boundary,
                }
            )
            + "\n"
        )
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=2)
        probe.launcher_output.close()
        if probe.emulator_fd is not None:
            os.close(probe.emulator_fd)
        launcher.stdin.close()
        launcher.stderr.close()


if __name__ == "__main__":
    main()
