"""Echo startup bytes after the owner releases the launcher."""

import sys


def main() -> None:
    """Run the isolated diagnostic fixture."""
    sys.stdin.buffer.readline()
    data = sys.stdin.buffer.read()
    data += b"x" * (8 * 1024 * 1024 + 1) if sys.argv[1] == "overflow" else b""
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
