"""Parse retained RetroArch version output without starting an emulator."""

import json
import sys

from batocera_gow.runtime.emulator_probe import parse_retroarch_version
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Publish the parsed version or the existing nonpassing exit record."""
    try:
        sys.stdout.write(
            json.dumps({"version": parse_retroarch_version(sys.argv[1])}) + "\n"
        )
    except ProbeError:
        sys.stdout.write(json.dumps({"status": "nonpassing"}) + "\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
