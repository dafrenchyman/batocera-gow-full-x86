"""Hold renderer log bytes buffered until the owned process receives shutdown."""

import pathlib
import sys


def main() -> None:
    """Publish open-log readiness before flushing the buffered renderer record."""
    data = pathlib.Path(sys.argv[2]).read_bytes()
    with pathlib.Path(sys.argv[1]).open("wb", buffering=8192) as stream:
        stream.write(data)
        sys.stdout.write("opened\n")
        sys.stdout.flush()
        sys.stdin.buffer.readline()


if __name__ == "__main__":
    main()
