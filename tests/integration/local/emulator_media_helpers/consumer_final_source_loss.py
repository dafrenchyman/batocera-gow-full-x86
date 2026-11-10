"""Provide a real input-source lifetime with optional zombie main-thread state."""

import ctypes
import sys
import threading


def main() -> None:
    """Publish readiness and wait for the original source shutdown commands."""
    ending = threading.Event()

    def worker() -> None:
        """Keep the worker alive after main-thread exit when requested."""
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        sys.stdin.buffer.readline()
        ending.set()
        if sys.argv[1] == "thread-zombie":
            sys.stdin.buffer.readline()

    if sys.argv[1] == "thread-zombie":
        threading.Thread(target=worker).start()
        ending.wait()
        ctypes.CDLL(None).pthread_exit(None)
    else:
        worker()


if __name__ == "__main__":
    main()
