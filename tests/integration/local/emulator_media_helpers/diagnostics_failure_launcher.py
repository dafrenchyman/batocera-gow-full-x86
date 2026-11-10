"""Buffer emulator stderr across controlled failure and late-output boundaries."""

import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    """Run the isolated diagnostic fixture."""
    header, separator, payload = bytes.fromhex(
        sys.argv[1] + sys.argv[2],
    ).partition(b":runCommand ")
    variant = sys.argv[3]
    emulator = subprocess.Popen(  # noqa: S603  # Fixed sibling script; synthetic payload argv.
        [
            sys.executable,
            str(Path(__file__).with_name("diagnostics_failure_emulator.py")),
            payload.hex(),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if emulator.stdin is None:
        message = "Owned emulator input unavailable"
        raise RuntimeError(message)
    try:
        sys.stderr.write(f"{emulator.pid}\n")
        sys.stderr.flush()
        sys.stdin.buffer.readline()
        _, buffered_stderr = emulator.communicate(b"end\n", timeout=2)
        sys.stderr.write("ended\n")
        sys.stderr.flush()
        if variant in ("delayed", "withheld"):
            sys.stdin.buffer.readline()
            if variant == "delayed":
                time.sleep(0.05)
        if variant != "withheld":
            os.write(1, header + separator + buffered_stderr)
        if variant == "eof":
            os.close(1)
        sys.stdin.buffer.readline()
        if variant not in ("eof", "unavailable"):
            os.write(
                1,
                b"\n2026-10-30 12:00:00,001 ERROR "
                b"(emulatorlauncher.py:596):runCommand "
                b"qt.qpa.xcb: could not connect to display late_private_value\n",
            )
        sys.stderr.write("late\n")
        sys.stderr.flush()
        sys.stdin.buffer.readline()
    finally:
        if emulator.poll() is None:
            emulator.kill()
            emulator.wait(timeout=2)
        emulator.stdin.close()


if __name__ == "__main__":
    main()
