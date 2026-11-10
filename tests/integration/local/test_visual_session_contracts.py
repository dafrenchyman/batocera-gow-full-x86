"""Exercise LiveVisual transactions against external X11/EGL ABI responses.

These local collaborators qualify discovery policy and resource ownership, not
stock libraries, a real authenticated display, GPU support or emulator output.
"""

import ctypes
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from batocera_gow.runtime.duckstation_visual import (
    LiveVisual,
    VisualError,
    VisualInfo,
    discover_visual,
)

if TYPE_CHECKING:
    # ctypes exposes no public generic type for native callback pointers.
    from ctypes import _Pointer


class TerminationFunction:
    """Allow signature assignment on a callable that can raise a Python error."""

    def __init__(self, operation: Callable[[int | None], int]) -> None:
        """Keep the external operation and its configured C signature together."""
        self.operation = operation
        self.argtypes: list[object] = []
        self.restype: object = None

    def __call__(self, display: int | None) -> int:
        """Invoke EGL termination without swallowing its exception."""
        return self.operation(display)


class DisplayLibraries(ctypes.CDLL):
    """Own synthetic native handles and expose fixed Xlib/EGL C entry points."""

    # Controlled C callbacks deliberately bypass CDLL's shared-library loading.
    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Allocate independent driver responses without loading a host library."""
        self.events: list[tuple[object, ...]] = []
        self.loads: list[str] = []
        self.versioned_only = False
        self.authenticated = True
        self.extensions = ctypes.create_string_buffer(b"EGL_EXT_platform_x11")
        self.extensions_present = True
        self.platform_available = True
        self.platform_display = 0x202
        self.legacy_display = 0x203
        self.initialize_ok = True
        self.terminate_error = False
        self.config_values: list[int | None] = [0x301, None, 0x302]
        self.config_count = 3
        self.returned_count = 3
        self.query_ok = True
        self.fetch_ok = True
        self.unavailable_attribute: int | None = None
        self.bind_ok = True
        self.context_ok = True
        self.destroy_ok = True
        self.visual_id = 0x125
        self.visual_count = 1
        self.visual_present = True
        self.visual = VisualInfo(visual_class=4, depth=24)
        self.connections: set[int] = set()
        self.displays: set[int] = set()
        self.contexts: set[int] = set()
        self.allocations: set[int] = set()
        self._configure_x11()
        self._configure_egl()

    def _configure_x11(self) -> None:
        integer = ctypes.c_int
        pointer = ctypes.c_void_p
        ints = ctypes.POINTER(integer)
        self.XOpenDisplay = ctypes.CFUNCTYPE(pointer, ctypes.c_char_p)(self.open)
        self.XDefaultScreen = ctypes.CFUNCTYPE(integer, pointer)(self.screen)
        self.XGetVisualInfo = ctypes.CFUNCTYPE(
            pointer, pointer, ctypes.c_long, ctypes.POINTER(VisualInfo), ints
        )(self.visual_info)
        self.XFree = ctypes.CFUNCTYPE(integer, pointer)(self.free)
        self.XCloseDisplay = ctypes.CFUNCTYPE(integer, pointer)(self.close)

    def _configure_egl(self) -> None:
        integer = ctypes.c_int
        pointer = ctypes.c_void_p
        ints = ctypes.POINTER(integer)
        self.eglGetDisplay = ctypes.CFUNCTYPE(pointer, pointer)(self.get_display)
        # Return stable owned storage, avoiding c_char_p callback allocations.
        self.eglQueryString = ctypes.CFUNCTYPE(pointer, pointer, integer)(self.query)
        self.platform = ctypes.CFUNCTYPE(pointer, ctypes.c_uint, pointer, ints)(
            self.get_platform_display
        )
        self.eglGetProcAddress = ctypes.CFUNCTYPE(pointer, ctypes.c_char_p)(self.proc)
        self.eglInitialize = ctypes.CFUNCTYPE(integer, pointer, ints, ints)(
            self.initialize
        )
        self.eglTerminate = TerminationFunction(self.terminate)
        self.eglChooseConfig = ctypes.CFUNCTYPE(
            integer, pointer, ints, ctypes.POINTER(pointer), integer, ints
        )(self.choose)
        self.eglGetConfigAttrib = ctypes.CFUNCTYPE(
            integer, pointer, pointer, integer, ints
        )(self.attribute)
        self.eglBindAPI = ctypes.CFUNCTYPE(integer, ctypes.c_uint)(self.bind)
        self.eglCreateContext = ctypes.CFUNCTYPE(
            pointer, pointer, pointer, pointer, ints
        )(self.create)
        self.eglDestroyContext = ctypes.CFUNCTYPE(integer, pointer, pointer)(
            self.destroy
        )

    def load(self, name: str) -> ctypes.CDLL:
        """Resolve only the documented client sonames, optionally requiring .1."""
        self.loads.append(name)
        if name == "libEGL.so" and self.versioned_only:
            message = "unversioned EGL client absent"
            raise OSError(message)
        assert name in {"libX11.so.6", "libEGL.so", "libEGL.so.1"}
        return self

    def open(self, name: bytes | None) -> int | None:
        """Record authentication inputs and allocate only authenticated handles."""
        self.events.append(
            ("open", name, os.environ.get("DISPLAY"), os.environ.get("XAUTHORITY"))
        )
        if not self.authenticated:
            return None
        self.connections.add(0x101)
        return 0x101

    def close(self, connection: int) -> int:
        """Release the connection without altering any other client's state."""
        self.events.append(("close", connection))
        self.connections.discard(connection)
        return 0

    def screen(self, connection: int) -> int:
        """Use a nondefault screen to detect hard-coded screen-zero lookups."""
        self.events.append(("screen", connection))
        return 2

    def visual_info(
        self,
        connection: int,
        mask: int,
        template: "_Pointer[VisualInfo]",
        count: "_Pointer[ctypes.c_int]",
    ) -> int | None:
        """Supply an allocated match or null while reporting the server's count."""
        self.events.append(
            ("visual", connection, mask, template[0].visualid, template[0].screen)
        )
        count[0] = self.visual_count
        if not self.visual_present:
            return None
        address = ctypes.addressof(self.visual)
        self.allocations.add(address)
        return address

    def free(self, address: int) -> int:
        """Release only the allocated visual match returned to this transaction."""
        self.events.append(("free", address))
        self.allocations.discard(address)
        return 0

    def query(self, display: int | None, key: int) -> int | None:
        """Return process-wide EGL client extensions from owned byte storage."""
        self.events.append(("extensions", display, key))
        return ctypes.addressof(self.extensions) if self.extensions_present else None

    def proc(self, name: bytes) -> int | None:
        """Publish the real callable address for the platform-X11 extension."""
        self.events.append(("proc", name))
        if not self.platform_available:
            return None
        return ctypes.cast(self.platform, ctypes.c_void_p).value

    def get_platform_display(
        self,
        platform: int,
        connection: int,
        attributes: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Acquire an X11 display only through the extension's fixed ABI."""
        self.events.append(("platform", platform, connection, bool(attributes)))
        return self.platform_display

    def get_display(self, connection: int) -> int:
        """Expose legacy display acquisition separately from the EXT path."""
        self.events.append(("legacy", connection))
        return self.legacy_display

    def initialize(
        self,
        display: int,
        major: "_Pointer[ctypes.c_int]",
        minor: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Transfer display ownership only after successful initialization."""
        self.events.append(("initialize", display))
        major[0], minor[0] = 1, 5
        if self.initialize_ok:
            self.displays.add(display)
        return int(self.initialize_ok)

    def terminate(self, display: int | None) -> int:
        """End initialized display ownership, optionally reporting a teardown error."""
        self.events.append(("terminate", display))
        assert display is not None
        self.displays.discard(display)
        if self.terminate_error:
            message = "EGL termination transport failed"
            raise OSError(message)
        return 1

    # eglChooseConfig fixes five arguments after self; do not reshape its ABI.
    def choose(
        self,
        display: int,
        attributes: "_Pointer[ctypes.c_int]",
        values: "_Pointer[ctypes.c_void_p]",
        capacity: int,
        count: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Return bounded config storage independently from the driver's count."""
        self.events.append(("choose", display, tuple(attributes[:15]), capacity))
        if not values:
            count[0] = self.config_count
            return int(self.query_ok)
        for index, value in enumerate(self.config_values[:capacity]):
            values[index] = value
        count[0] = self.returned_count
        return int(self.fetch_ok)

    def attribute(
        self,
        display: int,
        config: int,
        key: int,
        value: "_Pointer[ctypes.c_int]",
    ) -> int:
        """Report RGBA8 evidence and a config-specific native visual identity."""
        self.events.append(("attribute", display, config, key))
        value[0] = self.visual_id if key == 0x302E else 8
        return int(key != self.unavailable_attribute)

    def bind(self, api: int) -> int:
        """Record desktop versus embedded API selection independently."""
        self.events.append(("bind", api))
        return int(self.bind_ok)

    def create(
        self,
        display: int,
        config: int,
        shared: int | None,
        attributes: "_Pointer[ctypes.c_int]",
    ) -> int | None:
        """Allocate an unshared temporary context with explicit version attributes."""
        self.events.append(("create", display, config, shared, tuple(attributes[:6])))
        if not self.context_ok:
            return None
        self.contexts.add(0x401)
        return 0x401

    def destroy(self, display: int, context: int) -> int:
        """Release only successfully created discovery contexts."""
        self.events.append(("destroy", display, context))
        if self.destroy_ok:
            self.contexts.discard(context)
        return int(self.destroy_ok)


@pytest.fixture
def libraries(monkeypatch: pytest.MonkeyPatch) -> DisplayLibraries:
    """Replace library loading only, leaving all discovery methods untouched."""
    driver = DisplayLibraries()
    monkeypatch.setattr(ctypes, "CDLL", driver.load)
    monkeypatch.setenv("DISPLAY", ":73.2")
    monkeypatch.setenv("XAUTHORITY", "/session/private.Xauthority")
    monkeypatch.delenv("PREFER_GLES_CONTEXT", raising=False)
    return driver


def test_discovery_selects_native_visual_and_releases_owned_resources(
    libraries: DisplayLibraries,
) -> None:
    """Select the driver's config visual on the live screen, then release it all."""
    libraries.versioned_only = True
    assert discover_visual() == 0x125
    assert libraries.loads == ["libX11.so.6", "libEGL.so", "libEGL.so.1"]
    assert libraries.events[0] == ("open", None, ":73.2", "/session/private.Xauthority")
    assert ("platform", 0x31D5, 0x101, False) in libraries.events
    assert ("legacy", 0x101) not in libraries.events
    assert (
        "create",
        0x202,
        0x301,
        None,
        (0x3098, 4, 0x30FB, 6, 0x3038, 0),
    ) in libraries.events
    assert ("attribute", 0x202, 0x301, 0x302E) in libraries.events
    assert libraries.events[-5:] == [
        ("screen", 0x101),
        ("visual", 0x101, 3, 0x125, 2),
        ("free", ctypes.addressof(libraries.visual)),
        ("terminate", 0x202),
        ("close", 0x101),
    ]
    assert not libraries.connections
    assert not libraries.displays
    assert not libraries.contexts
    assert not libraries.allocations


def test_discovery_requires_authenticated_x_connection(
    libraries: DisplayLibraries,
) -> None:
    """Failed X authentication never initializes EGL or manufactures a visual."""
    libraries.authenticated = False
    with pytest.raises(VisualError, match="Cannot authenticate"):
        discover_visual()
    assert libraries.events == [("open", None, ":73.2", "/session/private.Xauthority")]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize(
    "fallback",
    ["no-extensions", "empty-extensions", "other-platform", "no-proc", "null-display"],
)
def test_platform_x11_gate_falls_back_to_native_display(
    libraries: DisplayLibraries,
    fallback: str,
) -> None:
    """Missing X11 extension support or acquisition falls back to native Xlib EGL."""
    if fallback == "no-extensions":
        libraries.extensions_present = False
    elif fallback == "empty-extensions":
        libraries.extensions = ctypes.create_string_buffer(b"")
    elif fallback == "other-platform":
        libraries.extensions = ctypes.create_string_buffer(
            b"EGL_KHR_platform_x11 EGL_EXT_platform_wayland"
        )
    elif fallback == "no-proc":
        libraries.platform_available = False
    else:
        libraries.platform_display = 0
    assert discover_visual() == 0x125
    expected: list[tuple[object, ...]] = [("extensions", None, 0x3055)]
    if fallback in {"no-proc", "null-display"}:
        expected.append(("proc", b"eglGetPlatformDisplayEXT"))
    if fallback == "null-display":
        expected.append(("platform", 0x31D5, 0x101, False))
    assert libraries.events[1 : 1 + len(expected)] == expected
    assert libraries.events[1 + len(expected) : 3 + len(expected)] == [
        ("legacy", 0x101),
        ("initialize", 0x203),
    ]
    assert libraries.events[-2:] == [("terminate", 0x203), ("close", 0x101)]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize("failure", ["missing-display", "initialization"])
def test_uninitialized_discovery_closes_x_without_terminating_egl(
    libraries: DisplayLibraries,
    failure: str,
) -> None:
    """Partial startup releases X, but never terminates an uninitialized display."""
    libraries.platform_display = 0
    if failure == "missing-display":
        libraries.legacy_display = 0
    else:
        libraries.initialize_ok = False
    with pytest.raises(VisualError, match="Cannot initialize EGL"):
        discover_visual()
    assert libraries.events[-1] == ("close", 0x101)
    assert not any(event[0] == "terminate" for event in libraries.events)
    assert not libraries.connections
    assert not libraries.displays


def test_termination_exception_still_closes_x(
    libraries: DisplayLibraries,
) -> None:
    """A teardown exception cannot strand the authenticated X connection."""
    libraries.terminate_error = True
    with pytest.raises(OSError, match="EGL termination transport failed"):
        discover_visual()
    assert libraries.events[-2:] == [("terminate", 0x202), ("close", 0x101)]
    assert not libraries.connections
    assert not libraries.displays
    assert not libraries.contexts
    assert not libraries.allocations


@pytest.mark.parametrize("es", [False, True])
def test_config_enumeration_preserves_order_filters_null_and_uses_window_rgba8(
    libraries: DisplayLibraries,
    *,
    es: bool,
) -> None:
    """Two-phase enumeration preserves driver order, not numeric config order."""
    libraries.config_values = [0x309, None, 0x301]
    with LiveVisual() as session:
        session.initialize()
        assert session.configs(es=es) == [0x309, 0x301]
    attributes = (
        0x3040,
        0x0040 if es else 0x0008,
        0x3033,
        0x0004,
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
    assert [event for event in libraries.events if event[0] == "choose"] == [
        ("choose", 0x202, attributes, 0),
        ("choose", 0x202, attributes, 3),
    ]
    assert not libraries.connections
    assert not libraries.displays


def test_config_count_at_discovery_bound_is_accepted(
    libraries: DisplayLibraries,
) -> None:
    """The inclusive allocation limit still yields the driver's usable prefix."""
    libraries.config_count = 4096
    with LiveVisual() as session:
        session.initialize()
        assert session.configs(es=False) == [0x301, 0x302]
    assert [event[3] for event in libraries.events if event[0] == "choose"] == [0, 4096]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize("returned", [0, 2])
def test_config_fetch_may_shrink_within_allocated_bound(
    libraries: DisplayLibraries,
    returned: int,
) -> None:
    """Only the reported initialized prefix can become candidate configs."""
    libraries.returned_count = returned
    with LiveVisual() as session:
        session.initialize()
        assert session.configs(es=False) == ([] if returned == 0 else [0x301])
    assert not libraries.connections
    assert not libraries.displays


def test_empty_config_query_does_not_allocate_or_fetch(
    libraries: DisplayLibraries,
) -> None:
    """A legitimate empty candidate set remains empty without a second query."""
    libraries.config_count = 0
    with LiveVisual() as session:
        session.initialize()
        assert session.configs(es=False) == []
    assert [event[3] for event in libraries.events if event[0] == "choose"] == [0]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("query-failure", "EGL config enumeration failed"),
        ("negative-count", "EGL config count exceeds discovery bound"),
        ("oversized-count", "EGL config count exceeds discovery bound"),
        ("fetch-failure", "EGL config enumeration failed"),
        ("negative-return", "EGL config enumeration changed beyond its bound"),
        ("oversized-return", "EGL config enumeration changed beyond its bound"),
    ],
)
def test_invalid_config_enumeration_refuses_visual_and_cleans_session(
    libraries: DisplayLibraries,
    fault: str,
    message: str,
) -> None:
    """Failed or impossible driver counts cannot escape as usable visual IDs."""
    if fault == "query-failure":
        libraries.query_ok = False
    elif fault == "fetch-failure":
        libraries.fetch_ok = False
    elif fault == "negative-count":
        libraries.config_count = -1
    elif fault == "oversized-count":
        libraries.config_count = 4097
    elif fault == "negative-return":
        libraries.returned_count = -1
    else:
        libraries.returned_count = 4
    with pytest.raises(VisualError, match=message):
        discover_visual()
    assert not any(event[0] in {"create", "visual"} for event in libraries.events)
    assert libraries.events[-2:] == [("terminate", 0x202), ("close", 0x101)]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize("es", [False, True])
@pytest.mark.parametrize(
    "outcome", ["supported", "bind-refused", "context-refused", "release-failed"]
)
def test_context_api_version_and_release_contract(
    libraries: DisplayLibraries,
    outcome: str,
    *,
    es: bool,
) -> None:
    """Try an unshared versioned context and release it without making it current."""
    libraries.bind_ok = outcome != "bind-refused"
    libraries.context_ok = outcome != "context-refused"
    libraries.destroy_ok = outcome != "release-failed"
    with LiveVisual() as session:
        session.initialize()
        if outcome == "release-failed":
            with pytest.raises(
                VisualError, match="Cannot release the discovery EGL context"
            ):
                session.context_supported(0x301, es=es, major=3, minor=1)
        else:
            supported = session.context_supported(0x301, es=es, major=3, minor=1)
            assert supported is (outcome == "supported")
    expected: list[tuple[object, ...]] = [("bind", 0x30A0 if es else 0x30A2)]
    if outcome != "bind-refused":
        expected.append(
            ("create", 0x202, 0x301, None, (0x3098, 3, 0x30FB, 1, 0x3038, 0))
        )
    if outcome in {"supported", "release-failed"}:
        expected.append(("destroy", 0x202, 0x401))
    assert libraries.events[5:-2] == expected
    assert libraries.contexts == ({0x401} if outcome == "release-failed" else set())
    assert not libraries.connections
    assert not libraries.displays


def test_embedded_discovery_uses_es_api_and_version_attributes(
    libraries: DisplayLibraries,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment preference affects the real native context request."""
    monkeypatch.setenv("PREFER_GLES_CONTEXT", "1")
    assert discover_visual() == 0x125
    assert ("bind", 0x30A0) in libraries.events
    assert (
        "create",
        0x202,
        0x301,
        None,
        (0x3098, 3, 0x30FB, 2, 0x3038, 0),
    ) in libraries.events
    assert not libraries.contexts


@pytest.mark.parametrize("key", [0x3024, 0x302E])
def test_unavailable_config_attribute_refuses_discovery_and_releases_display(
    libraries: DisplayLibraries,
    key: int,
) -> None:
    """Missing color or native-visual evidence cannot produce a selected visual."""
    libraries.unavailable_attribute = key
    with pytest.raises(VisualError, match="EGL config attribute unavailable"):
        discover_visual()
    assert ("attribute", 0x202, 0x301, key) in libraries.events
    assert not any(event[0] == "visual" for event in libraries.events)
    assert (("destroy", 0x202, 0x401) in libraries.events) is (key == 0x302E)
    assert not libraries.contexts
    assert libraries.events[-2:] == [("terminate", 0x202), ("close", 0x101)]
    assert not libraries.connections
    assert not libraries.displays


@pytest.mark.parametrize(
    "fault",
    [
        "zero-id",
        "negative-id",
        "null-match",
        "no-match",
        "multiple",
        "not-truecolor",
        "zero-depth",
        "negative-depth",
    ],
)
def test_invalid_live_screen_visual_is_refused_and_match_is_freed(
    libraries: DisplayLibraries,
    fault: str,
) -> None:
    """A native visual must identify one positive-depth TrueColor screen match."""
    if fault in {"zero-id", "negative-id"}:
        libraries.visual_id = 0 if fault == "zero-id" else -1
    elif fault == "null-match":
        libraries.visual_present = False
    elif fault in {"no-match", "multiple"}:
        libraries.visual_count = 0 if fault == "no-match" else 2
    elif fault == "not-truecolor":
        libraries.visual.visual_class = 3
    else:
        libraries.visual.depth = 0 if fault == "zero-depth" else -1
    with pytest.raises(
        VisualError,
        match=r"Chosen EGL (config has no native X11 visual|visual is not valid)",
    ):
        discover_visual()
    looked_up = fault not in {"zero-id", "negative-id"}
    assert (("visual", 0x101, 3, 0x125, 2) in libraries.events) is looked_up
    freed = ("free", ctypes.addressof(libraries.visual))
    assert (freed in libraries.events) is (looked_up and libraries.visual_present)
    assert libraries.events[-2:] == [("terminate", 0x202), ("close", 0x101)]
    assert not libraries.allocations
    assert not libraries.contexts
    assert not libraries.connections
    assert not libraries.displays
