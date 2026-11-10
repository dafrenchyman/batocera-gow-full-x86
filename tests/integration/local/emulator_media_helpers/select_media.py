"""Select mounted media through the installed emulator probe."""

import json
import sys
from pathlib import Path

from batocera_gow.runtime.emulator_probe import EmulatorProbe


def main() -> None:
    """Run the isolated diagnostic fixture."""
    try:
        probe = EmulatorProbe(
            Path(sys.argv[1]),
            roms_view=Path(sys.argv[2]),
            catalog_path=Path(sys.argv[3]),
            reproduction=Path(sys.argv[4]),
            reproduce_required=sys.argv[5] == "yes",
            case=sys.argv[6],
        )
        selected = probe.select()
        sys.stdout.write(
            json.dumps({"selected": selected, "report": probe.result}) + "\n"
        )
    except (OSError, RuntimeError, ValueError) as error:
        sys.stdout.write(json.dumps({"failure": type(error).__name__}) + "\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
