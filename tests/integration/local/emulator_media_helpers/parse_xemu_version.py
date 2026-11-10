"""Parse the bounded version records emitted by a successful xemu identity run."""

import json
import sys

from batocera_gow.runtime.emulator_probe import parse_xemu_version
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Publish validated xemu metadata or the original nonpassing exit record."""
    try:
        sys.stdout.write(
            json.dumps(parse_xemu_version(sys.argv[1], int(sys.argv[2]))) + "\n"
        )
    except ProbeError:
        sys.stdout.write(json.dumps({"status": "nonpassing"}) + "\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
