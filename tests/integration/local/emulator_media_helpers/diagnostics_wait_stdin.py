"""Wait for the owning launcher to release standard input."""

import sys


def main() -> None:
    """Run the isolated diagnostic fixture."""
    sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
