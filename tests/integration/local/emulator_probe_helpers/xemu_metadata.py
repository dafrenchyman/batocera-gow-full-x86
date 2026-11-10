"""Emit controlled xemu metadata and model timeout or termination refusal."""

import signal
import sys
import time
from pathlib import Path


def main() -> int:
    """Write only the supplied disposable config and publish the metadata protocol."""
    config = Path(sys.argv[1])
    config.write_text("private helper configuration", encoding="utf-8")
    mode = sys.argv[2]
    if mode == "ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    sys.stdout.write("ready\n")
    sys.stdout.flush()
    if mode in ("timeout", "ignore-term"):
        time.sleep(60)
    sys.stdout.write(
        "private library diagnostic and media filename\n"
        "xemu_version: 0.8.123\n"
        "xemu_commit: " + "a" * 40 + "\n"
        "xemu_date: Mon Jan 1 01:02:03 AM UTC 2024\n"
    )
    return 4 if mode == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
