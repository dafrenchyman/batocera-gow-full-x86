"""Reduce DuckStation startup bytes without launching an emulator."""

import json
import sys

from batocera_gow.runtime.emulator_probe import duckstation_startup_failure


def main() -> None:
    """Run the isolated diagnostic fixture."""
    data = sys.stdin.buffer.read()
    sys.stdout.write(
        json.dumps(
            duckstation_startup_failure(None if sys.argv[1] == "unavailable" else data)
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
