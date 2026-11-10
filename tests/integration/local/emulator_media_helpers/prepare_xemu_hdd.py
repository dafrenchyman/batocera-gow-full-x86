"""Exercise xemu seed qualification against owned disposable userdata."""

import json
import sys
from pathlib import Path

from batocera_gow.runtime.emulator_probe import seed_xemu_hdd


def main() -> None:
    """Publish seed preparation results without replacing existing state."""
    try:
        sys.stdout.write(
            json.dumps(seed_xemu_hdd(Path(sys.argv[1]), Path(sys.argv[2]))) + "\n"
        )
    except (OSError, RuntimeError, ValueError) as error:
        sys.stdout.write(json.dumps({"failure": type(error).__name__}) + "\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
