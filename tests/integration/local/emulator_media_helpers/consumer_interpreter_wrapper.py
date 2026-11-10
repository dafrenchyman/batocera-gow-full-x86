"""Hold the interpreter identity until instructed to exec the owned stock ELF."""

import ctypes
import os
import sys
from pathlib import Path


def main() -> None:
    """Keep argv unchanged while crossing the real interpreter-to-ELF boundary."""
    ctypes.CDLL(None).prctl(15, b"duckstation-qt", 0, 0, 0)
    sys.stdout.write("interpreter\n")
    sys.stdout.flush()
    sys.stdin.buffer.readline()
    executable = str(Path(__file__).parent.parent / "duckstation-qt")
    os.execv(executable, [executable, *sys.argv[1:]])  # noqa: S606  # Exec the owned compiled sibling with unchanged Qt argv.


if __name__ == "__main__":
    main()
