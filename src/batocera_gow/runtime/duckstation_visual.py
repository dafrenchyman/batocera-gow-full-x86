"""Select DuckStation's EGL config's X11 visual on the current live screen.

Policy pin: duckstation/old-releases 3a08ad18406efc1ddc4927a59bea715961bb63fa,
util/opengl_context{,_egl,_egl_x11}.cpp. This is an independent adapter, not a
vendored emulator implementation. Recheck ordering and attributes on upgrades.
"""

import ctypes
import os
from typing import Protocol, Self

RGBA_BITS = 8
TRUE_COLOR = 4
MAX_CONFIGS = 4096


class VisualSession(Protocol):
    """Borrowed EGL/X11 operations required by pinned visual selection."""

    def initialize(self) -> None:
        """Initialize the session's display without changing its environment."""
        ...

    def configs(self, *, es: bool) -> list[int]:
        """Return ordered window-compatible RGBA8 config candidates."""
        ...

    def attribute(self, config: int, key: int) -> int:
        """Read a native EGL attribute or raise VisualError."""
        ...

    def context_supported(
        self,
        config: int,
        *,
        es: bool,
        major: int,
        minor: int,
    ) -> bool:
        """Try and release the requested context without making it current."""
        ...

    def validate(self, visual: int) -> None:
        """Refuse a visual that is not valid on the selected live screen."""
        ...


class VisualError(RuntimeError):
    """The current session cannot supply a validated compatible visual."""


class VisualInfo(ctypes.Structure):
    """XVisualInfo's Xlib ABI, including native unsigned-long visual IDs."""

    _fields_ = [
        ("visual", ctypes.c_void_p),
        ("visualid", ctypes.c_ulong),
        ("screen", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("visual_class", ctypes.c_int),
        ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong),
        ("blue_mask", ctypes.c_ulong),
        ("colormap_size", ctypes.c_int),
        ("bits_per_rgb", ctypes.c_int),
    ]

    # ctypes' metaclass creates and initializes these native field descriptors.
    visual_class: int  # pyright: ignore[reportUninitializedInstanceVariable]
    depth: int  # pyright: ignore[reportUninitializedInstanceVariable]


class LiveVisual:
    """Own one authenticated Xlib connection and one EGL display for discovery."""

    def __init__(self) -> None:
        """Load stock client libraries and own a fresh authenticated X connection."""
        self.x = ctypes.CDLL("libX11.so.6")
        try:
            self.egl = ctypes.CDLL("libEGL.so")
        except OSError:
            self.egl = ctypes.CDLL("libEGL.so.1")
        pointer = ctypes.c_void_p
        integer = ctypes.c_int
        ints = ctypes.POINTER(integer)
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XOpenDisplay.restype = pointer
        self.x.XDefaultScreen.argtypes = [pointer]
        self.x.XDefaultScreen.restype = integer
        self.x.XGetVisualInfo.argtypes = [
            pointer,
            ctypes.c_long,
            ctypes.POINTER(VisualInfo),
            ints,
        ]
        self.x.XGetVisualInfo.restype = ctypes.POINTER(VisualInfo)
        self.x.XFree.argtypes = [pointer]
        self.x.XFree.restype = integer
        self.x.XCloseDisplay.argtypes = [pointer]
        self.x.XCloseDisplay.restype = integer
        for name, arguments, result in (
            ("eglGetDisplay", [pointer], pointer),
            ("eglQueryString", [pointer, integer], ctypes.c_char_p),
            ("eglGetProcAddress", [ctypes.c_char_p], pointer),
            ("eglInitialize", [pointer, ints, ints], integer),
            ("eglTerminate", [pointer], integer),
            (
                "eglChooseConfig",
                [pointer, ints, ctypes.POINTER(pointer), integer, ints],
                integer,
            ),
            ("eglGetConfigAttrib", [pointer, pointer, integer, ints], integer),
            ("eglBindAPI", [ctypes.c_uint], integer),
            ("eglCreateContext", [pointer, pointer, pointer, ints], pointer),
            ("eglDestroyContext", [pointer, pointer], integer),
        ):
            function = getattr(self.egl, name)
            function.argtypes = arguments
            function.restype = result
        self.connection: int | None = self.x.XOpenDisplay(None)
        if not self.connection:
            message = "Cannot authenticate to the current X11 display"
            raise VisualError(message)
        self.display: int | None = None
        self.initialized = False

    def __enter__(self) -> Self:
        """Borrow this connection for one discovery operation."""
        return self

    def __exit__(self, *_exception: object) -> None:
        """Release owned EGL state and always close the authenticated X connection."""
        try:
            if self.initialized:
                self.egl.eglTerminate(self.display)
        finally:
            self.x.XCloseDisplay(self.connection)

    def initialize(self) -> None:
        """Use the pinned EXT-X11 gate and native-display fallback, no overrides."""
        extensions = self.egl.eglQueryString(None, 0x3055)
        if extensions and b"EGL_EXT_platform_x11" in extensions:
            address = self.egl.eglGetProcAddress(b"eglGetPlatformDisplayEXT")
            if address:
                acquire = ctypes.CFUNCTYPE(
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_int),
                )(address)
                self.display = acquire(0x31D5, self.connection, None)
        if not self.display:
            self.display = self.egl.eglGetDisplay(self.connection)
        major, minor = ctypes.c_int(), ctypes.c_int()
        if not self.display or not self.egl.eglInitialize(
            self.display, ctypes.byref(major), ctypes.byref(minor)
        ):
            message = "Cannot initialize EGL on the current X11 display"
            raise VisualError(message)
        self.initialized = True

    def configs(self, *, es: bool) -> list[int]:
        """Retain EGL ordering for the pin's WINDOW/RGBA8/renderable request."""
        attributes = (ctypes.c_int * 15)(
            0x3040,
            0x0040 if es else 0x0008,  # ES3 or desktop OpenGL
            0x3033,
            0x0004,  # EGL_WINDOW_BIT
            0x3024,
            8,
            0x3023,
            8,
            0x3022,
            8,
            0x3021,
            8,
            0x3038,
            0,
            0,
        )
        count = ctypes.c_int()
        if not self.egl.eglChooseConfig(
            self.display, attributes, None, 0, ctypes.byref(count)
        ):
            message = "EGL config enumeration failed"
            raise VisualError(message)
        if count.value == 0:
            return []
        if not 0 < count.value <= MAX_CONFIGS:
            message = "EGL config count exceeds discovery bound"
            raise VisualError(message)
        values = (ctypes.c_void_p * count.value)()
        if not self.egl.eglChooseConfig(
            self.display, attributes, values, count.value, ctypes.byref(count)
        ):
            message = "EGL config enumeration failed"
            raise VisualError(message)
        if not 0 <= count.value <= len(values):
            message = "EGL config enumeration changed beyond its bound"
            raise VisualError(message)
        return [int(value) for value in values[: count.value] if value is not None]

    def attribute(self, config: int, key: int) -> int:
        """Read an EGLConfig attribute, refusing unavailable selection evidence."""
        value = ctypes.c_int()
        if not self.egl.eglGetConfigAttrib(
            self.display, config, key, ctypes.byref(value)
        ):
            message = "EGL config attribute unavailable"
            raise VisualError(message)
        return value.value

    def context_supported(
        self,
        config: int,
        *,
        es: bool,
        major: int,
        minor: int,
    ) -> bool:
        """Try pinned major/minor-only context attributes, releasing immediately."""
        attributes = (ctypes.c_int * 6)(0x3098, major, 0x30FB, minor, 0x3038, 0)
        if not self.egl.eglBindAPI(0x30A0 if es else 0x30A2):
            return False
        context = self.egl.eglCreateContext(self.display, config, None, attributes)
        if not context:
            return False
        if not self.egl.eglDestroyContext(self.display, context):
            message = "Cannot release the discovery EGL context"
            raise VisualError(message)
        return True

    def validate(self, visual: int) -> None:
        """Require one TrueColor visual on Xlib's actual selected screen."""
        if visual <= 0:
            message = "Chosen EGL config has no native X11 visual"
            raise VisualError(message)
        screen = int(self.x.XDefaultScreen(self.connection))
        template = VisualInfo(visualid=visual, screen=screen)
        count = ctypes.c_int()
        matches = self.x.XGetVisualInfo(
            self.connection, 0x1 | 0x2, ctypes.byref(template), ctypes.byref(count)
        )
        try:
            if (
                not matches
                or count.value != 1
                or matches[0].visual_class != TRUE_COLOR
                or matches[0].depth <= 0
            ):
                message = "Chosen EGL visual is not valid on the current X11 screen"
                raise VisualError(message)
        finally:
            if matches:
                self.x.XFree(matches)


def select_visual(session: VisualSession, *, prefer_es: bool) -> int:
    """Reproduce pinned config/version choice, then validate its live screen ID.

    EGL returns ordered candidates. DuckStation chooses the first exact RGBA8
    match, or the first returned config if none match exactly. Choosing an
    arbitrary depth32/TrueColor visual would not reproduce that policy. A
    context failure moves to the next pinned version, not another config.

    Args:
        session: Borrowed live EGL/X11 boundary, closed by the entry point.
        prefer_es: The pin's existing PREFER_GLES_CONTEXT=1 preference.

    Returns:
        The positive, live X11 visual ID belonging to the selected EGL config.

    Raises:
        VisualError: If no pinned context/config yields a screen-valid visual.
    """
    session.initialize()
    desktop = [(False, 4, minor) for minor in range(6, -1, -1)] + [
        (False, 3, minor) for minor in range(3, -1, -1)
    ]
    embedded = [(True, 3, minor) for minor in (2, 1, 0)]
    for es, major, minor in embedded + desktop if prefer_es else desktop + embedded:
        configs = session.configs(es=es)
        if not configs:
            continue
        config = next(
            (
                candidate
                for candidate in configs
                if all(
                    session.attribute(candidate, key) == RGBA_BITS
                    for key in (0x3024, 0x3023, 0x3022, 0x3021)
                )
            ),
            configs[0],
        )
        if session.context_supported(config, es=es, major=major, minor=minor):
            visual = session.attribute(config, 0x302E)
            # IDs are X-server/screen-local. Never cache the successful diagnostic
            # ID: docs/completed/specs/wolf-integration/research/
            # duckstation-startup-failure.md#actual-egl-config-and-qt-window-trace
            # The corrected Qt comparison proves surface creation, not gameplay
            # or shortcut acceptance. HUD-enabled launches still need native proof.
            session.validate(visual)
            return visual
    message = "No supported DuckStation EGL context/config for this X11 session"
    raise VisualError(message)


def discover_visual() -> int:
    """Discover afresh using unchanged post-configgen environment and X authority."""
    with LiveVisual() as session:
        return select_visual(
            session, prefer_es=os.environ.get("PREFER_GLES_CONTEXT") == "1"
        )
