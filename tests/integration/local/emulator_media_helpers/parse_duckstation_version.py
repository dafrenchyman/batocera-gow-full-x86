"""Parse DuckStation version output and its informational exit status."""

import json
import sys

from batocera_gow.runtime.emulator_probe import parse_duckstation_version
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Publish safe version metadata without treating exit one as a launch."""
    try:
        sys.stdout.write(
            json.dumps(parse_duckstation_version(sys.argv[1], int(sys.argv[2]))) + "\n"
        )
    except ProbeError:
        sys.stdout.write(json.dumps({"status": "nonpassing"}) + "\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
