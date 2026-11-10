"""Observe bounded SDL discovery logging and restoration of the borrowed logger."""

import ctypes
import ctypes.util
import json
import sys

from batocera_gow.runtime.emulator_probe import SDLDiscoveryMode


def main() -> None:
    """Emit real SDL messages while tracking forwarding and restored state."""
    name = ctypes.util.find_library("SDL2-2.0")
    if name is None:
        raise SystemExit(77)
    library = ctypes.CDLL(name)
    callback_type = SDLDiscoveryMode.CALLBACK
    forwarded: list[list[int]] = []

    def original(
        _userdata: int | None, category: int, priority: int, _message: bytes | None
    ) -> None:
        """Record only forwarded categories and priorities, never message bytes."""
        forwarded.append([category, priority])

    original_callback = callback_type(original)
    library.SDL_LogSetOutputFunction.argtypes = [callback_type, ctypes.c_void_p]
    library.SDL_LogSetPriority.argtypes = [ctypes.c_int, ctypes.c_int]
    library.SDL_LogSetOutputFunction(original_callback, None)
    library.SDL_LogSetPriority(7, 5)
    library.SDL_LogSetPriority(0, 2)
    library.SDL_LogMessage.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    observer = SDLDiscoveryMode(library)
    for _ in range(300):
        library.SDL_LogMessage(7, 2, b"%s", b"Using udev for joystick device discovery")
    library.SDL_LogMessage(7, 2, b"%s", b"private unknown diagnostic")
    library.SDL_LogMessage(7, 5, b"%s", b"udev init failed, disabling udev integration")
    library.SDL_LogMessage(0, 2, b"%s", b"udev init failed, disabling udev integration")
    observer.close()
    current, userdata = (callback_type(), ctypes.c_void_p())
    library.SDL_LogGetOutputFunction(ctypes.byref(current), ctypes.byref(userdata))
    sys.stdout.write(
        json.dumps(
            {
                "observed": observer.observed,
                "forwarded": forwarded,
                "restored": ctypes.cast(current, ctypes.c_void_p).value
                == ctypes.cast(original_callback, ctypes.c_void_p).value,
                "priority": library.SDL_LogGetPriority(7),
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
