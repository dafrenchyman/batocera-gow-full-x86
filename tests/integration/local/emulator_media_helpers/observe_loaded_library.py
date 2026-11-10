"""Bind a loaded libc function to its actual mapped library file."""

import ctypes
import hashlib
import json
import sys
from pathlib import Path

from batocera_gow.runtime.emulator_probe import loaded_object_observation


def main() -> None:
    """Compare the candidate file with real mapping and content identities."""
    libc = ctypes.CDLL(None)
    paths = [
        Path(line.split(maxsplit=5)[5])
        for line in Path("/proc/self/maps").read_text().splitlines()
        if line.endswith("/libc.so.6")
    ]
    path = paths[0]
    candidate = path if sys.argv[1] == "actual" else Path(sys.argv[2])
    sys.stdout.write(
        json.dumps(
            {
                "observation": loaded_object_observation(libc.getpid, candidate),
                "actual_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
