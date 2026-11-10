"""Retain an exclusive incomplete boundary until abrupt process loss."""

import sys
from pathlib import Path

from batocera_gow.runtime.emulator_probe import EmulatorProbe


def main() -> None:
    """Run the isolated diagnostic fixture."""
    probe = EmulatorProbe(Path(sys.argv[1]))
    probe.result["errors"] = ["synthetic-private-exception-path"]
    probe.retain_boundary("before-chord")
    try:
        probe.result["native_device_consumption"] = {"status": "passed"}
        probe.retain_boundary("before-chord")
    except FileExistsError:
        sys.stdout.write("retained\n")
        sys.stdout.flush()
    else:
        raise SystemExit(2)
    sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
