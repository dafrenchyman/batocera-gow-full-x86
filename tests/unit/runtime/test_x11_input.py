"""Consumer-visible input ordering, held-state ownership and teardown behavior."""

import errno
import json
import os
import socket
import time
from pathlib import Path

import pytest

from batocera_gow.runtime import input_worker, x11_input


def assert_closed_descriptor(descriptor: int) -> None:
    """Assert descriptor revocation by errno, independent of platform wording."""
    with pytest.raises(OSError) as error:  # noqa: PT011 - errno, not platform wording, is the contract.
        os.fstat(descriptor)
    assert error.value.errno == errno.EBADF


class RecordingSink:
    """Record consumer-visible desktop operations while enforcing hold ownership."""

    def __init__(self) -> None:
        """Start with an independent desktop and no held keys or buttons."""
        self.events: list[tuple[str, int, int]] = []
        self.keys: set[int] = set()
        self.buttons: set[int] = set()
        self.position = [0, 0]
        self.flushes = 0
        self.closes = 0

    def _transition(self, held: set[int], code: int, *, pressed: bool) -> None:
        if pressed:
            if code in held:
                error_message = f"duplicate press for {code}"
                raise AssertionError(error_message)
            held.add(code)
        else:
            if code not in held:
                error_message = f"unowned release for {code}"
                raise AssertionError(error_message)
            held.remove(code)

    def key(self, code: int, *, pressed: bool) -> None:
        """Record a key transition while refusing duplicate or foreign releases."""
        self._transition(self.keys, code, pressed=pressed)
        self.events.append(("key", code, pressed))

    def button(self, code: int, *, pressed: bool) -> None:
        """Record a pointer-button transition under the same ownership checks."""
        self._transition(self.buttons, code, pressed=pressed)
        self.events.append(("button", code, pressed))

    def motion(self, dx: int, dy: int) -> None:
        """Record bounded wire motion and retain its cumulative position."""
        if not (-32768 <= dx <= 32767 and -32768 <= dy <= 32767):
            error_message = "motion exceeds XTEST wire coordinates"
            raise AssertionError(error_message)
        self.position[0] += dx
        self.position[1] += dy
        self.events.append(("motion", dx, dy))

    def flush(self) -> None:
        """Count desktop flushes without inventing input events."""
        self.flushes += 1

    def close(self) -> None:
        """Record closure so borrowed-resource tests detect ownership violations."""
        self.closes += 1


class TestInputOwnership:
    """Exercise input state using a recording desktop borrowed by the adapter."""

    def setup_method(self) -> None:
        """Create independent input state for each behavioral case."""
        # Pytest initializes these per-test resources before every test method.
        self.sink = RecordingSink()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.state = x11_input.InputState(self.sink)  # pyright: ignore[reportUninitializedInstanceVariable]

    def teardown_method(self) -> None:
        """Release remaining holds without closing the borrowed desktop."""
        self.state.close()

    def key(self, source: str, code: int, value: int) -> None:
        """Feed one Linux key transition from an identified producer."""
        self.state.feed(source, x11_input.EV_KEY, code, value)

    def report(self, source: str) -> None:
        """Finish one producer's evdev frame."""
        self.state.feed(source, x11_input.EV_SYN, x11_input.SYN_REPORT, 0)

    def test_duplicate_press_and_repeat_preserve_one_hold_until_release(self) -> None:
        """Duplicate press and repeat preserve one hold until release."""
        self.key("keyboard", 30, 1)
        self.key("keyboard", 30, 1)
        self.key("keyboard", 30, 2)
        self.key("keyboard", 30, 2)
        assert self.sink.keys == {30}
        self.key("keyboard", 30, 0)
        assert self.sink.keys == set()
        assert self.sink.events == [("key", 30, True), ("key", 30, False)]

    def test_orphan_repeat_or_release_cannot_acquire_or_release_someone_elses_hold(
        self,
    ) -> None:
        """Orphan repeat or release cannot acquire or release someone elses hold."""
        self.key("owner", 30, 1)
        self.key("other", 30, 2)
        self.key("other", 30, 0)
        self.state.remove_source("other")
        assert self.sink.keys == {30}
        self.key("owner", 30, 0)
        self.key("other", 31, 2)
        self.key("other", 31, 0)
        assert self.sink.keys == set()
        assert len(self.sink.events) == 2

    def test_two_sources_share_key_until_last_release(self) -> None:
        """Two sources share key until last release."""
        self.key("first", 29, 1)
        self.key("second", 29, 1)
        self.key("first", 29, 0)
        assert self.sink.keys == {29}
        self.key("first", 29, 0)
        self.key("second", 29, 2)
        self.key("second", 29, 0)
        assert self.sink.events == [("key", 29, True), ("key", 29, False)]

    def test_disconnect_releases_only_its_own_holds_and_discards_pending_motion(
        self,
    ) -> None:
        """Disconnect releases only its own holds and discards pending motion."""
        self.key("first", 29, 1)
        self.key("first", 46, 1)
        self.key("second", 29, 1)
        self.key("second", 42, 1)
        self.state.feed("first", x11_input.EV_REL, x11_input.REL_X, 15)
        self.state.remove_source("first")
        assert self.sink.keys == {29, 42}
        assert self.sink.position == [0, 0]
        self.state.remove_source("first")
        self.report("first")
        assert self.sink.position == [0, 0]
        self.state.remove_source("second")
        assert self.sink.keys == set()

    def test_cleanup_does_not_reset_unrelated_desktop_holds(self) -> None:
        """Cleanup does not reset unrelated desktop holds."""
        self.sink.keys.add(42)
        self.sink.buttons.add(3)
        self.key("keyboard", 29, 1)
        self.key("mouse", 0x110, 1)
        self.state.remove_source("keyboard")
        self.state.close()
        assert self.sink.keys == {42}
        assert self.sink.buttons == {3}

    def test_shutdown_releases_shared_holds_once_and_is_idempotent(self) -> None:
        """Shutdown releases shared holds once and is idempotent."""
        self.key("first", 29, 1)
        self.key("second", 29, 1)
        self.key("first", 46, 1)
        self.key("second", 0x110, 1)
        self.state.close()
        assert self.sink.keys == set()
        assert self.sink.buttons == set()
        assert self.sink.events[-3:] == [
            ("button", 1, False),
            ("key", 46, False),
            ("key", 29, False),
        ]
        events = list(self.sink.events)
        self.state.close()
        self.state.remove_source("first")
        assert self.sink.closes == 0
        assert self.sink.events == events
        with pytest.raises(RuntimeError, match="closed"):
            self.key("first", 30, 1)

    def test_modifier_order_matches_producer_without_combination_mapping(self) -> None:
        """Modifier order matches producer without combination mapping."""
        for code, value in (
            (29, 1),
            (42, 1),
            (46, 1),
            (46, 2),
            (46, 0),
            (42, 0),
            (29, 0),
        ):
            self.key("keyboard", code, value)
        assert self.sink.events == [
            ("key", 29, True),
            ("key", 42, True),
            ("key", 46, True),
            ("key", 46, False),
            ("key", 42, False),
            ("key", 29, False),
        ]

    def test_disconnect_unwinds_later_keys_before_their_modifiers(self) -> None:
        """Disconnect unwinds later keys before their modifiers."""
        for code in (29, 42, 46):
            self.key("keyboard", code, 1)
        self.state.remove_source("keyboard")
        assert self.sink.events[-3:] == [
            ("key", 46, False),
            ("key", 42, False),
            ("key", 29, False),
        ]

    def test_mouse_button_order_and_shared_ownership(self) -> None:
        """Mouse button order and shared ownership."""
        self.key("first", 0x111, 1)
        self.key("first", 0x112, 1)
        self.key("second", 0x111, 1)
        self.key("first", 0x111, 2)
        self.state.remove_source("first")
        assert self.sink.buttons == {3}
        self.key("second", 0x111, 0)
        assert self.sink.events == [
            ("button", 3, True),
            ("button", 2, True),
            ("button", 2, False),
            ("button", 3, False),
        ]

    def test_motion_accumulates_per_source_only_until_its_report(self) -> None:
        """Motion accumulates per source only until its report."""
        for code, value in (
            (x11_input.REL_X, 12),
            (x11_input.REL_Y, -4),
            (x11_input.REL_X, -5),
            (x11_input.REL_Y, 1),
        ):
            self.state.feed("first", x11_input.EV_REL, code, value)
        self.state.feed("second", x11_input.EV_REL, x11_input.REL_X, 9)
        assert self.sink.position == [0, 0]
        self.report("first")
        assert self.sink.position == [7, -3]
        self.report("first")
        assert self.sink.events == [("motion", 7, -3)]
        self.report("second")
        assert self.sink.position == [16, -3]
        assert self.sink.flushes == 3

    def test_move_before_button_press_does_not_become_a_drag(self) -> None:
        """Move before button press does not become a drag."""
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 12)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_Y, -4)
        self.key("mouse", 0x110, 1)
        assert self.sink.flushes == 0
        self.report("mouse")
        assert self.sink.events == [("motion", 12, -4), ("button", 1, True)]

    def test_button_press_before_move_keeps_the_drag(self) -> None:
        """Button press before move keeps the drag."""
        self.key("mouse", 0x110, 1)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 12)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_Y, -4)
        self.report("mouse")
        assert self.sink.events == [("button", 1, True), ("motion", 12, -4)]

    def test_move_before_button_release_remains_inside_the_drag(self) -> None:
        """Move before button release remains inside the drag."""
        self.key("mouse", 0x110, 1)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 12)
        self.key("mouse", 0x110, 0)
        assert self.sink.flushes == 0
        self.report("mouse")
        assert self.sink.events == [
            ("button", 1, True),
            ("motion", 12, 0),
            ("button", 1, False),
        ]

    def test_modifier_edges_separate_motion_segments_without_early_flush(self) -> None:
        """Modifier edges separate motion segments without early flush."""
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 2)
        self.key("mouse", 29, 1)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 3)
        self.key("mouse", 29, 0)
        assert self.sink.flushes == 0
        self.report("mouse")
        assert self.sink.events == [
            ("motion", 2, 0),
            ("key", 29, True),
            ("motion", 3, 0),
            ("key", 29, False),
        ]

    def test_wheel_and_motion_segments_keep_producer_order(self) -> None:
        """Wheel and motion segments keep producer order."""
        for code, value in (
            (x11_input.REL_WHEEL, 1),
            (x11_input.REL_X, 5),
            (x11_input.REL_Y, -2),
            (x11_input.REL_HWHEEL, -1),
            (x11_input.REL_X, 3),
            (x11_input.REL_WHEEL, -1),
        ):
            self.state.feed("mouse", x11_input.EV_REL, code, value)
        assert self.sink.events == []
        self.report("mouse")
        assert self.sink.events == [
            ("button", 4, True),
            ("button", 4, False),
            ("motion", 5, -2),
            ("button", 6, True),
            ("button", 6, False),
            ("motion", 3, 0),
            ("button", 5, True),
            ("button", 5, False),
        ]

    def test_long_motion_frames_are_not_truncated_by_x_protocol(self) -> None:
        """Long motion frames are not truncated by x protocol."""
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_X, 70000)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_Y, -70000)
        self.report("mouse")
        assert self.sink.position == [70000, -70000]
        self.report("mouse")
        assert self.sink.position == [70000, -70000]

    def test_wheel_is_framed_and_never_leaves_a_button_held(self) -> None:
        """Wheel is framed and never leaves a button held."""
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_WHEEL, 2)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_WHEEL, -1)
        self.state.feed("mouse", x11_input.EV_REL, x11_input.REL_HWHEEL, -1)
        assert self.sink.events == []
        self.report("mouse")
        assert self.sink.events == [
            ("button", 4, True),
            ("button", 4, False),
            ("button", 4, True),
            ("button", 4, False),
            ("button", 5, True),
            ("button", 5, False),
            ("button", 6, True),
            ("button", 6, False),
        ]
        assert self.sink.buttons == set()
        self.report("mouse")
        assert len(self.sink.events) == 8

    def test_dropped_frame_releases_affected_holds_and_reports_failure(self) -> None:
        """Dropped frame releases affected holds and reports failure."""
        self.key("broken", 29, 1)
        self.key("broken", 46, 1)
        self.key("healthy", 29, 1)
        self.key("broken", 0x110, 1)
        self.state.feed("broken", x11_input.EV_REL, x11_input.REL_X, 30)
        with pytest.raises(RuntimeError, match=r"dropped.*broken"):
            self.state.feed("broken", x11_input.EV_SYN, x11_input.SYN_DROPPED, 0)
        assert self.sink.keys == {29}
        assert self.sink.buttons == set()
        assert self.sink.position == [0, 0]
        # Events after the drop are an incomplete frame, not fresh presses.
        self.key("broken", 46, 1)
        self.state.feed("broken", x11_input.EV_REL, x11_input.REL_X, 50)
        self.report("broken")
        assert self.sink.keys == {29}
        assert self.sink.position == [0, 0]
        self.key("broken", 30, 1)
        assert self.sink.keys == {29, 30}

    def test_ancillary_scan_metadata_does_not_change_key_ownership(self) -> None:
        """Ancillary scan metadata does not change key ownership."""
        self.key("keyboard", 30, 1)
        self.state.feed("keyboard", x11_input.EV_MSC, 4, 0x70004)
        self.report("keyboard")
        assert self.sink.keys == {30}
        assert self.sink.events == [("key", 30, True)]

    def test_invalid_or_unsupported_input_does_not_disturb_existing_hold(self) -> None:
        """Invalid or unsupported input does not disturb existing hold."""
        self.key("keyboard", 29, 1)
        invalid: list[tuple[object, object, object]] = [
            (x11_input.EV_KEY, 0, 1),
            (x11_input.EV_KEY, 248, 1),
            (x11_input.EV_KEY, 0x100, 1),
            (x11_input.EV_KEY, 0x130, 1),
            (x11_input.EV_KEY, 30, 3),
            (x11_input.EV_REL, 2, 1),
            (x11_input.EV_REL, 11, 120),
            (x11_input.EV_SYN, 2, 0),
            (x11_input.EV_SYN, x11_input.SYN_REPORT, 1),
            (x11_input.EV_MSC, 6, 1),
            (3, 0, 1),
            (5, 0, 1),
            (x11_input.EV_KEY, -1, 1),
            (x11_input.EV_KEY, 30, 2**31),
            (x11_input.EV_KEY, 30, True),
            (x11_input.EV_KEY, "30", 1),
        ]
        for event in invalid:
            with pytest.raises(ValueError, match=r"integer|unsupported|invalid"):
                self.state.feed("keyboard", *event)
            assert self.sink.keys == {29}
            assert self.sink.events == [("key", 29, True)]

    def test_shutdown_attempts_remaining_releases_and_keeps_borrowed_sink_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing release does not block other releases or close a borrowed sink."""
        self.key("keyboard", 29, 1)
        self.key("keyboard", 46, 1)
        real_key = self.sink.key

        def fail_one_release(code: int, *, pressed: bool) -> None:
            if code == 46 and not pressed:
                error_message = "injected X connection failure"
                raise RuntimeError(error_message)
            real_key(code, pressed=pressed)

        monkeypatch.setattr(self.sink, "key", fail_one_release)
        with pytest.raises(RuntimeError, match="X connection failure"):
            self.state.close()
        assert 29 not in self.sink.keys
        assert self.sink.closes == 0
        self.state.close()
        assert self.sink.closes == 0

    def test_failed_disconnect_release_is_retried_during_final_close(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failed disconnect release is retried during final close."""
        self.key("keyboard", 29, 1)
        real_key = self.sink.key

        def fail_release(code: int, *, pressed: bool) -> None:
            if not pressed:
                error_message = "temporary release failure"
                raise RuntimeError(error_message)
            real_key(code, pressed=pressed)

        monkeypatch.setattr(self.sink, "key", fail_release)
        with pytest.raises(RuntimeError, match="temporary release failure"):
            self.state.remove_source("keyboard")
        monkeypatch.setattr(self.sink, "key", real_key)
        self.state.close()
        assert self.sink.keys == set()


def test_worker_removal_closes_descriptor_after_release_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing desktop release cannot leak the worker's received source FD."""
    sink = RecordingSink()
    state = x11_input.InputState(sink)
    state.feed("producer", x11_input.EV_KEY, 30, 1)
    original_key = sink.key

    def reject_release(code: int, *, pressed: bool) -> None:
        if not pressed:
            message = "release failed"
            raise RuntimeError(message)
        original_key(code, pressed=pressed)

    parent, connection = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with parent, connection:
        # The socket itself is borrowed and remains open after source removal.
        worker = input_worker.Worker(
            connection,
            x11_input.XTestSink,
            input_worker.open_authority,
            time.monotonic,
            time.sleep,
        )
        worker.state = state
        read_fd, write_fd = os.pipe()
        worker.sources["producer"] = read_fd, b""
        monkeypatch.setattr(sink, "key", reject_release)
        try:
            with pytest.raises(RuntimeError, match="release failed"):
                worker.remove("producer")
            assert_closed_descriptor(read_fd)
            assert worker.sources == {}
            assert connection.fileno() >= 0
            assert sink.closes == 0
        finally:
            os.close(write_fd)


def test_worker_teardown_attempts_all_resources_after_state_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State teardown failure still closes owned event, authority and sink resources."""
    sink = RecordingSink()
    authority = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    read_fd, write_fd = os.pipe()

    class FailingState(x11_input.InputState):
        """Release holds, then simulate a desktop teardown failure."""

        def close(self) -> None:
            """Fail after attempting normal held-state cleanup."""
            super().close()
            message = "state cleanup failed"
            raise RuntimeError(message)

    def open_authority(uid: int, gid: int) -> int:
        del uid, gid
        return authority

    def open_sink(display: str, cookie: str) -> RecordingSink:
        del display, cookie
        return sink

    monkeypatch.setattr(input_worker, "InputState", FailingState)
    parent, connection = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        worker = input_worker.Worker(
            connection, open_sink, open_authority, time.monotonic, time.sleep
        )
        worker.sources["producer"] = read_fd, b""
        parent.send(b'{"op":"close"}')
        with pytest.raises(RuntimeError, match="state cleanup failed"):
            worker.run(os.getuid(), os.getgid())
        assert sink.closes == 1
        assert worker.sources == {}
        for descriptor in (read_fd, authority):
            assert_closed_descriptor(descriptor)
        # Borrowed connection survives even a failed worker teardown.
        connection.send(b"still borrowed")
        assert json.loads(parent.recv(8192)) == {"op": "ready"}
        assert parent.recv(8192) == b"still borrowed"
    finally:
        os.close(write_fd)
        parent.close()
        connection.close()
