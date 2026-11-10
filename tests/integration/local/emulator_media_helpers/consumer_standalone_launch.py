"""Hold a selected disc open across controlled worker and leader exit boundaries."""

import ctypes
import os
import sys
import threading
from pathlib import Path
from typing import BinaryIO


def main() -> None:
    """Run the owned child with the original readiness and command protocol."""
    with Path(sys.argv[1]).open("rb") as disc:
        run_consumer(disc)


def run_consumer(disc: BinaryIO) -> None:
    """Borrow the selected disc until close or process-lifetime commands arrive."""
    ending = threading.Event()

    def worker() -> None:
        """Handle disc closure and exit commands without changing worker lifetime."""
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        for command in sys.stdin.buffer:
            if command == b"close\n":
                disc.close()
                sys.stdout.write("closed\n")
                sys.stdout.flush()
            elif command == b"zombie\n":
                ending.set()
                sys.stdout.write("leader-exiting\n")
                sys.stdout.flush()
            elif command == b"exit\n":
                ending.set()
                break
        if sys.argv[2] in ("launcher-error", "thread-launcher-error"):
            os._exit(2)

    if sys.argv[2].startswith("thread-"):
        threading.Thread(target=worker).start()
        ending.wait()
        ctypes.CDLL(None).pthread_exit(None)
    else:
        worker()


if __name__ == "__main__":
    main()
