"""Emit synthetic emulator stderr and wait for the launcher."""

import os
import sys


def main() -> None:
    """Run the isolated diagnostic fixture."""
    os.write(2, bytes.fromhex(sys.argv[1]))
    sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
