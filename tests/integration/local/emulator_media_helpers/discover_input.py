"""Observe real device identity through controlled SDL discovery snapshots."""

import json
import os
import sys
from pathlib import Path
from typing import TypedDict

from batocera_gow.runtime.emulator_probe import (
    SDLGamepadDiscovery,
    gamepad_device_observation,
)


class DiscoveryRequest(TypedDict):
    """Private fixture paths and ordered SDL discovery snapshots."""

    paths: list[str | None]
    polls: list[list[str | None]]
    node: str
    udev_data: str


def main() -> None:
    """Poll supplied SDL paths against the real character-device identity."""

    class SDL:
        """Supply the exact joystick-discovery protocol without exporting paths."""

        def __init__(self, paths: list[str | None]) -> None:
            """Retain the current ordered snapshot of discovered event paths."""
            self.paths = paths

        def SDL_JoystickUpdate(self) -> None:  # noqa: N802  # Exact borrowed SDL API name.
            """Leave the explicitly supplied discovery snapshot unchanged."""

        def SDL_NumJoysticks(self) -> int:  # noqa: N802  # Exact borrowed SDL API name.
            """Return the number of paths in the current discovery snapshot."""
            return len(self.paths)

        def SDL_JoystickPathForIndex(self, index: int) -> bytes | None:  # noqa: N802  # Exact borrowed SDL API name.
            """Return the current event path with SDL's byte-string boundary."""
            path = self.paths[index]
            return os.fsencode(path) if path is not None else None

        def SDL_GetError(self) -> bytes:  # noqa: N802  # Exact borrowed SDL API name.
            """Return a private diagnostic that must not escape public evidence."""
            return b"private SDL diagnostic must never be exported"

    request: DiscoveryRequest = json.loads(sys.argv[1])
    expected = Path("/dev/null").stat().st_rdev
    sdl = SDL(request["paths"])
    discovery = SDLGamepadDiscovery(sdl, expected)
    matches: list[int | str | None] = []
    for paths in request["polls"]:
        sdl.paths = paths
        try:
            matches.append(discovery.poll())
        except OSError:
            matches.append("os-error")
    sys.stdout.write(
        json.dumps(
            {
                "matches": matches,
                "sdl": discovery.evidence,
                "device": gamepad_device_observation(
                    Path(request["node"]), expected, Path(request["udev_data"])
                ),
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
