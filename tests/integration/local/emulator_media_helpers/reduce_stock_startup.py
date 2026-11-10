"""Reduce private stock startup bytes to public categories."""

import json
import sys

from batocera_gow.runtime.emulator_probe import stock_launch_failure


def main() -> None:
    """Run the isolated diagnostic fixture."""
    sys.stdout.write(json.dumps(stock_launch_failure(sys.stdin.buffer.read())) + "\n")


if __name__ == "__main__":
    main()
