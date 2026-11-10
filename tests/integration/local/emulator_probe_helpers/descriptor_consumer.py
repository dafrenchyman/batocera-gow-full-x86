"""Hold real file descriptors until the parent releases the child through stdin."""

import sys
from contextlib import ExitStack
from pathlib import Path


def main() -> None:
    """Keep every supplied input file open across the readiness boundary."""
    with ExitStack() as files:
        for path in sys.argv[1:]:
            files.enter_context(Path(path).open("rb"))
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
