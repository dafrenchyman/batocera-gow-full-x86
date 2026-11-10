"""Apply the scoped Qt visual correction after unchanged stock configgen."""

import configparser
import os
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from .duckstation_visual import VisualError, discover_visual

SETTINGS = Path("/userdata/system/configs/duckstation/settings.ini")
STOCK_EXECUTABLE = "/usr/bin/duckstation-qt"
MAX_SETTINGS_BYTES = 1024 * 1024
MAX_VISUAL_ID = 0xFFFFFFFF


class CasePreservingConfigParser(configparser.ConfigParser):
    """Keep stock-generated section keys case-sensitive."""

    def optionxform(self, optionstr: str) -> str:
        """Return the stock key unchanged rather than folding its case."""
        return optionstr


def renderer(path: Path) -> str:
    """Read final generated GPU/Renderer without interpolation or unsafe files.

    Raises:
        OSError: If settings are unavailable or cannot be read without following links.
        ValueError: If settings are unsafe, oversized or lack a renderer decision.
        configparser.Error: If generated INI is malformed or ambiguous.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SETTINGS_BYTES:
            message = "Unsafe DuckStation settings file"
            raise ValueError(message)
        data = stream.read(MAX_SETTINGS_BYTES + 1)
    if len(data) > MAX_SETTINGS_BYTES:
        message = "Oversized DuckStation settings file"
        raise ValueError(message)
    settings = CasePreservingConfigParser(interpolation=None)
    settings.read_string(data)
    value = settings.get("GPU", "Renderer", fallback="")
    if not value:
        message = "Generated DuckStation GPU/Renderer is missing"
        raise ValueError(message)
    return value


def launch(
    arguments: Sequence[str], settings: Path, discover: Callable[[], int]
) -> None:
    """Exec the absolute stock emulator, adding only the OpenGL Qt visual pair.

    The pinned generator emits bare duckstation-qt and preserves inherited PATH.
    ES's partial PSX command selects this dedicated wrapper after configgen, not
    instead of generation. GPU/Renderer here is the final decision; an earlier
    frontend preference can be overwritten. Vulkan/other renderers do not load
    EGL/X11, discover a visual or gain arguments. No library path is rewritten.

    Raises:
        VisualError: If OpenGL discovery fails. Never launch uncorrected or switch
            renderers on failure; OpenGL failures must remain visible failures.
        OSError: If the stock executable or generated settings are unavailable.
        ValueError: If the generated renderer or discovery result is invalid.
    """
    forwarded = list(arguments)
    if renderer(settings) == "OpenGL":
        try:
            visual = discover()
        except OSError as error:
            # Loader/connection exceptions may contain private environment paths.
            message = "Cannot load or query live EGL/X11 for automatic visual discovery"
            raise VisualError(message) from error
        if type(visual) is not int or visual <= 0 or visual > MAX_VISUAL_ID:
            message = "Discovery returned an invalid native X11 visual"
            raise VisualError(message)
        forwarded = ["-visual", hex(visual), *forwarded]
    # Absolute exec avoids PATH recursion and retains the real stock executable,
    # PID/exit chain, generated environment and every remaining argument.
    os.execv(STOCK_EXECUTABLE, [STOCK_EXECUTABLE, *forwarded])  # noqa: S606


def main() -> int:
    """Fail clearly at the process boundary without leaking settings or media paths."""
    try:
        launch(sys.argv[1:], SETTINGS, discover_visual)
    except VisualError as error:
        sys.stderr.write(
            "DuckStation compatibility wrapper: OpenGL launch refused: "
            + str(error)
            + ". No uncorrected or renderer fallback was attempted.\n"
        )
        return 1
    except (OSError, ValueError, configparser.Error):
        # INI/OS exceptions can contain private configuration or media paths.
        sys.stderr.write(
            "DuckStation compatibility wrapper: launch refused. Cannot read final "
            "generated GPU/Renderer or exec the absolute stock emulator. "
            "No fallback was attempted.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
