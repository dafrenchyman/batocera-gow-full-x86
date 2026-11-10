"""Observe bounded private pipe snapshots without waiting for EOF."""

import json
import os
import sys
import time

from batocera_gow.runtime.emulator_lifecycle import PrivateOutput


def main() -> None:
    """Run the isolated diagnostic fixture."""
    reader, writer = os.pipe()
    stream = os.fdopen(reader, "rb", buffering=0)
    output = PrivateOutput(stream)
    variant = sys.argv[1]
    size = {
        "small": 73,
        "limit": 65536,
        "oversize": 65537,
        "overflow": 8 * 1024 * 1024 + 1,
        "read-error": 73,
    }[variant]
    payload = b"x" * (size - 24) + b"\nprivate_snapshot_value\n"
    try:
        os.write(writer, payload)
        deadline = time.monotonic() + 3
        while output.retained_bytes < min(size, 8 * 1024 * 1024) or (
            variant == "overflow" and not output.observation()["overflow"]
        ):
            if time.monotonic() >= deadline:
                message = "Owned drainer did not receive fixture bytes"
                raise RuntimeError(message)
            time.sleep(0.001)
        if variant == "read-error":
            stream.close()
            while not output.observation()["read_failed"]:
                if time.monotonic() >= deadline:
                    message = "Closed descriptor did not report unavailable"
                    raise RuntimeError(message)
                time.sleep(0.001)
        data, state = output.snapshot_available()
        if variant != "read-error":
            os.write(writer, b"late_private_value\n")
        output.close()
        cleared, closed = output.snapshot_available()
        expected = payload if size <= 65536 else b"private_snapshot_value\n"
        detached = data is None or (isinstance(data, bytes) and data == expected)
        sys.stdout.write(
            json.dumps(
                {
                    "state": state,
                    "detached": detached,
                    "data_size": None if data is None else len(data),
                    "cleared": cleared is None,
                    "closed": closed,
                }
            )
            + "\n"
        )
    finally:
        os.close(writer)
        output.close()


if __name__ == "__main__":
    main()
