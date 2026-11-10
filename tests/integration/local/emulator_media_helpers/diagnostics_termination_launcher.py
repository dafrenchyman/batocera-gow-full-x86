"""Own a synthetic child and emit the supplied termination record."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run the isolated diagnostic fixture."""
    child = subprocess.Popen(  # noqa: S603  # Fixed sibling script without external executable input.
        [sys.executable, str(Path(__file__).with_name("diagnostics_wait_stdin.py"))],
        stdin=subprocess.PIPE,
    )
    try:
        sys.stderr.write(f"{child.pid}\n")
        sys.stderr.flush()
        sys.stdin.buffer.readline()
        child.communicate(b"exit")
        os.write(1, bytes.fromhex(sys.argv[1]))
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)


if __name__ == "__main__":
    main()
