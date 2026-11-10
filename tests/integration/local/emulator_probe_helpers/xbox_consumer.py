"""Hold a controlled library mapping and input files for procfs observations."""

import mmap
import sys
from contextlib import ExitStack
from pathlib import Path


def main() -> None:
    """Retain the requested mapping protection and open inputs until stdin releases."""
    protection = mmap.PROT_READ
    if sys.argv[2] != "nonexecutable-map":
        protection |= mmap.PROT_EXEC
    with ExitStack() as files:
        library = files.enter_context(Path(sys.argv[1]).open("rb"))
        files.enter_context(mmap.mmap(library.fileno(), 0, prot=protection))
        for path in sys.argv[3:]:
            files.enter_context(Path(path).open("rb"))
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
