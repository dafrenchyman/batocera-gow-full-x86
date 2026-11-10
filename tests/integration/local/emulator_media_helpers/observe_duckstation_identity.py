"""Observe DuckStation identity while preserving stdout and stderr boundaries."""

import json
import subprocess
import sys
from unittest.mock import patch

from batocera_gow.runtime.emulator_probe import duckstation_identity
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Feed retained process output through the installed identity observer."""
    captured = subprocess.CompletedProcess(
        ["/usr/bin/duckstation-qt", "-version"],
        1,
        stdout=sys.argv[1],
        stderr=sys.argv[2],
    )
    with (
        patch(
            "batocera_gow.runtime.emulator_probe.subprocess.run", return_value=captured
        ),
        patch("batocera_gow.runtime.emulator_probe.digest", return_value="a" * 64),
    ):
        try:
            sys.stdout.write(json.dumps(duckstation_identity()) + "\n")
        except ProbeError:
            sys.stdout.write(json.dumps({"status": "nonpassing"}) + "\n")
            raise SystemExit(2) from None


if __name__ == "__main__":
    main()
