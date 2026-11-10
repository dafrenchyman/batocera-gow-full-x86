"""Exercise owned input acquisition with real descriptors and confined metadata.

Kernel ioctl, pidfd_getfd, device creation and classifier execution are explicit
external boundaries. These tests do not qualify uinput or stock/native consumers.
"""

import array
import base64
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import pytest

from batocera_gow.runtime import input_transport as broker
from batocera_gow.runtime import udev_input


class ProbeExecutable(Path):
    """Resolve the packaged probe's interpreter alias to the local interpreter."""

    def samefile(self, other_path: str | os.PathLike[str]) -> bool:
        """Compare real inodes after mapping the synthetic process's executable."""
        executable = (
            sys.executable if str(other_path) == "/usr/bin/python3" else other_path
        )
        return super().samefile(executable)


class TemporaryEventNode(broker.EventNode):
    """Replace privileged node creation, retaining real inode/open/cleanup checks."""

    # The fixture substitutes a regular file for the base's privileged device.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, path: Path, *, created: bool, after_open: Callable[[], None]
    ) -> None:
        """Allocate an ordinary owned file instead of calling mknod."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unconsumed-event-data")
        self.created = created
        self.identity = broker.node_identity(path.lstat())
        self.after_open = after_open
        self.opened: list[int] = []

    def open(self) -> int:
        """Use the production inode check, then expose a kernel-race boundary."""
        descriptor = super().open()
        self.opened.append(descriptor)
        self.after_open()
        return descriptor


class AcquisitionEnvironment:
    """Provide confined kernel metadata and external classifier responses."""

    def __init__(self, root: Path) -> None:
        """Own a real pidfd and creator independently of the source under test."""
        self.root = root
        self.event = root / "sys/devices/virtual/input/input7/event9"
        self.event.mkdir(parents=True)
        (self.event / "dev").write_text("13:73\n", encoding="utf-8")
        self.runtime = root / "runtime"
        self.runtime.mkdir()
        (self.runtime / "suite-gamepad.json").write_text(
            json.dumps(
                {
                    "name": "suite controller",
                    "bus": 3,
                    "vendor": 4,
                    "product": 5,
                    "version": 6,
                }
            ),
            encoding="utf-8",
        )
        self.cmdline = root / "cmdline"
        self.cmdline.write_bytes(
            b"/usr/bin/python3\0/opt/gow-full-x86/emulator_probe.py\0"
        )
        self.classifier = root / "udevadm"
        self.classifier.write_bytes(b"independent-classifier-fixture\n")
        self.records = root / "udev-data"
        self.records.mkdir(mode=0o700)
        self.label = b"ordinary controller"
        self.identity: tuple[int, ...] = (3, 4, 5, 6)
        self.kernel_name = "input7"
        self.created = True
        self.nodes: list[TemporaryEventNode] = []
        self.duplicates: list[int] = []
        self.notifications: list[dict[str, str]] = []
        self.classification = "ID_INPUT=1\nID_INPUT_KEY=1\n"
        self.after_open: Callable[[], None] = lambda: None
        self.after_duplicate: Callable[[], None] = lambda: None
        self.after_classify: Callable[[], None] = lambda: None
        self.on_notification: Callable[[str], None] = lambda _action: None
        self.failed_notification: str | None = None
        self.duplicate_error: int | None = None
        self.duplicate_from: int | None = None
        self.ioctl_error: int | None = None
        self.original_open = os.open
        self.process = broker.OwnedProcess(os.getpid())
        try:
            self.creator = os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC)
        except BaseException:
            self.process.close()
            raise

    def path(self, value: str | os.PathLike[str]) -> Path:
        """Map only device/sysfs/probe paths; leave real proc stat reads intact."""
        path = Path(value)
        if path == Path("/dev/uinput"):
            return Path(os.devnull)
        if str(path).startswith(("/sys/devices/virtual/input", "/dev/input")):
            return self.root / path.relative_to("/")
        if path == Path(f"/proc/{self.process.pid}/cmdline"):
            return self.cmdline
        if path == Path(f"/proc/{self.process.pid}/exe"):
            return ProbeExecutable(sys.executable)
        return path

    def classifier_path(self, value: str | os.PathLike[str]) -> Path:
        """Supply classifier bytes for the real publisher's digest checks."""
        return self.classifier if str(value) == "/usr/bin/udevadm" else Path(value)

    def open(
        self,
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        """Confine the real OwnedRecord directory without changing its lifecycle."""
        target = self.records if path == "/run/udev/data" else path
        return self.original_open(target, flags, mode, dir_fd=dir_fd)

    def node(self, path: Path, devt: int, gid: int) -> TemporaryEventNode:
        """Create an ordinary inode at the configured device-creation boundary."""
        del devt, gid
        node = TemporaryEventNode(
            path, created=self.created, after_open=self.after_open
        )
        self.nodes.append(node)
        return node

    def ioctl(
        self,
        descriptor: int,
        request: int,
        data: "bytearray | array.array[int]",
        mutate: Literal[True],
    ) -> int:
        """Fill real mutable ioctl buffers with external device identities."""
        assert mutate is True
        os.fstat(descriptor)
        if self.ioctl_error is not None:
            raise OSError(self.ioctl_error, "kernel ioctl refused")
        if isinstance(data, array.array):
            data[:] = array.array("H", self.identity)
        else:
            value = (
                self.kernel_name.encode("ascii")
                if request == 0x8080552C
                else self.label
            )
            data[: len(value) + 1] = value + b"\0"
        return 0

    def syscall(self, number: int, pidfd: int, descriptor: int, flags: int) -> int:
        """Transfer a real duplicate at pidfd_getfd, never a made-up descriptor."""
        del number, descriptor, flags
        os.fstat(pidfd)
        if self.duplicate_error is not None:
            ctypes.set_errno(self.duplicate_error)
            return -1
        original = self.creator if self.duplicate_from is None else self.duplicate_from
        duplicate = os.dup(original)
        self.duplicates.append(duplicate)
        self.after_duplicate()
        return duplicate

    def run(
        self,
        command: list[str],
        *,
        capture_output: bool,
        timeout: int,
        check: bool,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        """Supply classifier output and retain decoded external advertisements."""
        del capture_output, timeout, check, text
        if command[0] == "/usr/bin/udevadm":
            self.after_classify()
            return subprocess.CompletedProcess(command, 0, self.classification, "")
        payload = base64.b64decode(command[2]).decode("ascii")
        self.notifications.append(
            dict(field.split("=", 1) for field in payload.split("\0") if field)
        )
        action = self.notifications[-1]["ACTION"]
        self.on_notification(action)
        failed = action == self.failed_notification
        return subprocess.CompletedProcess(
            command, int(failed), b"", b"fixture notification failed" if failed else b""
        )

    def source(self, *, suite: bool = False) -> broker.Source:
        """Transfer a freshly duplicated creator to production acquisition."""
        return broker.Source(
            self.process, (19, os.dup(self.creator)), "input7", os.getgid(), suite=suite
        )

    def close(self) -> None:
        """Release fixture ownership, separately from transferred source ownership."""
        os.close(self.creator)
        self.process.close()


@pytest.fixture
def acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AcquisitionEnvironment]:
    """Keep all source checks intact while replacing privileged external APIs."""
    environment = AcquisitionEnvironment(tmp_path)
    try:
        monkeypatch.setattr(broker, "Path", environment.path)
        monkeypatch.setattr(broker, "RUNTIME_ROOT", environment.runtime)
        monkeypatch.setattr(broker, "EventNode", environment.node)
        monkeypatch.setattr(broker.LIBC, "syscall", environment.syscall)
        monkeypatch.setattr(fcntl, "ioctl", environment.ioctl)
        monkeypatch.setattr(udev_input, "Path", environment.classifier_path)
        monkeypatch.setattr(os, "open", environment.open)
        monkeypatch.setattr(subprocess, "run", environment.run)
        yield environment
    finally:
        environment.close()


def assert_closed(descriptors: list[int]) -> None:
    """Require kernel EBADF, rather than trusting a collaborator's close count."""
    for descriptor in descriptors:
        with pytest.raises(OSError, match="Bad file descriptor") as caught:
            os.fstat(descriptor)
        assert caught.value.errno == errno.EBADF


@pytest.mark.parametrize("owned_node", [False, True])
def test_semantic_acquisition_retains_reader_and_keeps_private_pins_out_of_summary(
    acquisition: AcquisitionEnvironment, *, owned_node: bool
) -> None:
    """Ordinary devices retain readable data but receive no invented classification."""
    acquisition.created = owned_node
    source = acquisition.source()
    try:
        assert source.valid()
        assert source.reader is not None
        assert source.creator is not None
        assert os.read(source.reader, 64) == b"unconsumed-event-data"
        assert source.summary() == {
            "sysname": "input7",
            "name": "ordinary controller",
            "node": str(acquisition.root / "dev/input/event9"),
            "source_pid": os.getpid(),
            "role": "semantic",
        }
        assert list(acquisition.records.iterdir()) == []
        assert acquisition.notifications == []
        assert_closed(acquisition.duplicates)
        transferred = [source.creator, source.reader]
    finally:
        source.close()
    assert_closed(transferred)
    assert acquisition.nodes[0].path.exists() is not owned_node
    assert not source.valid()
    os.fstat(acquisition.creator)
    assert acquisition.process.valid()


@pytest.mark.parametrize("suite", [False, True])
def test_owned_final_device_publishes_required_key_class_and_withdraws_it(
    acquisition: AcquisitionEnvironment, *, suite: bool
) -> None:
    """A final hotkey device publishes classifier-derived keys, not joystick flags."""
    acquisition.label = b"batocera hotkeys"
    source = acquisition.source(suite=suite)
    record = acquisition.records / "c13:73"
    try:
        assert record.read_bytes() == b"E:ID_INPUT=1\nE:ID_INPUT_KEY=1\n"
        summary = source.summary()
        assert summary["role"] == "final"
        assert summary["udev_properties"] == {"ID_INPUT": "1", "ID_INPUT_KEY": "1"}
        assert (
            summary["udev_classifier_sha256"]
            == hashlib.sha256(b"independent-classifier-fixture\n").hexdigest()
        )
        assert set(summary) == {
            "sysname",
            "name",
            "node",
            "source_pid",
            "role",
            "udev_properties",
            "udev_classifier_sha256",
        }
        assert acquisition.notifications[0]["ACTION"] == "add"
        assert acquisition.notifications[0]["DEVNAME"] == str(acquisition.nodes[0].path)
    finally:
        source.close()
    assert not record.exists()
    assert [event["ACTION"] for event in acquisition.notifications] == ["add", "remove"]
    assert not acquisition.nodes[0].path.exists()
    assert_closed(acquisition.duplicates)


def test_suite_gamepad_requires_full_identity_and_stock_joystick_class(
    acquisition: AcquisitionEnvironment,
) -> None:
    """The configured probe pad remains semantic but gains actual parsed metadata."""
    acquisition.label = b"suite controller"
    acquisition.classification = "ID_INPUT=1\nID_INPUT_JOYSTICK=1\n"
    source = acquisition.source(suite=True)
    try:
        assert source.valid()
        assert source.summary()["role"] == "semantic"
        assert source.summary()["udev_properties"] == {
            "ID_INPUT": "1",
            "ID_INPUT_JOYSTICK": "1",
        }
        assert (acquisition.records / "c13:73").read_bytes() == (
            b"E:ID_INPUT=1\nE:ID_INPUT_JOYSTICK=1\n"
        )
    finally:
        source.close()
    assert list(acquisition.records.iterdir()) == []


def test_invalid_utf8_device_label_is_public_metadata_not_a_decode_failure(
    acquisition: AcquisitionEnvironment,
) -> None:
    """A kernel label is decoded safely without inventing final-device status."""
    acquisition.label = b"controller-\xff"
    source = acquisition.source()
    try:
        assert source.summary()["name"] == "controller-\ufffd"
        assert source.summary()["role"] == "semantic"
        assert acquisition.notifications == []
    finally:
        source.close()


@pytest.mark.parametrize("failure", ["revoked", "notification"])
def test_publication_failure_rolls_back_node_reader_creator_and_metadata(
    acquisition: AcquisitionEnvironment, failure: str
) -> None:
    """No consumer-visible record survives a failed live check or advertisement."""
    acquisition.label = b"batocera hotkeys"
    expected: type[Exception] = RuntimeError
    if failure == "revoked":

        def revoke() -> None:
            acquisition.process.start += 1

        acquisition.after_classify = revoke
        expected = ProcessLookupError
    else:
        acquisition.failed_notification = "add"
    creator = os.dup(acquisition.creator)
    with pytest.raises(expected, match=r"ownership lost|fake-udev add failed"):
        broker.Source(acquisition.process, (19, creator), "input7", 42)
    assert not acquisition.nodes[0].path.exists()
    assert list(acquisition.records.iterdir()) == []
    assert_closed([creator, *acquisition.nodes[0].opened, *acquisition.duplicates])


def test_failed_withdrawal_still_revokes_source_and_closes_all_owned_resources(
    acquisition: AcquisitionEnvironment,
) -> None:
    """Metadata withdrawal precedes node deletion even when notification fails."""
    acquisition.label = b"batocera hotkeys"
    source = acquisition.source()
    assert source.creator is not None
    assert source.reader is not None
    transferred = [source.creator, source.reader]
    boundary: list[tuple[bool, bool, bool]] = []

    def observe(action: str) -> None:
        assert action == "remove"
        for descriptor in transferred:
            os.fstat(descriptor)
        boundary.append(
            (
                source.valid(),
                acquisition.nodes[0].path.exists(),
                (acquisition.records / "c13:73").exists(),
            )
        )

    acquisition.on_notification = observe
    acquisition.failed_notification = "remove"
    try:
        with pytest.raises(RuntimeError, match="fake-udev remove failed"):
            source.close()
    finally:
        source.close()
    assert boundary == [(False, True, False)]
    assert not acquisition.nodes[0].path.exists()
    assert list(acquisition.records.iterdir()) == []
    assert_closed([*transferred, *acquisition.duplicates])


def test_missing_kernel_identity_closes_creator_before_any_node_allocation(
    acquisition: AcquisitionEnvironment,
) -> None:
    """An acquisition failure before reader creation still consumes its creator."""
    (acquisition.event / "dev").unlink()
    creator = os.dup(acquisition.creator)
    with pytest.raises(FileNotFoundError, match="dev"):
        broker.Source(acquisition.process, (19, creator), "input7", 42)
    assert_closed([creator])
    assert acquisition.nodes == []
    assert acquisition.notifications == []


@pytest.mark.parametrize("mismatch", ["name", "bus", "vendor", "product", "version"])
def test_suite_lookalikes_do_not_acquire_publication(
    acquisition: AcquisitionEnvironment, mismatch: str
) -> None:
    """Matching a label alone, or only part of the numeric identity, is insufficient."""
    acquisition.label = b"suite controller"
    if mismatch == "name":
        acquisition.label = b"other controller"
    else:
        identity = list(acquisition.identity)
        identity[("bus", "vendor", "product", "version").index(mismatch)] += 1
        acquisition.identity = tuple(identity)
    source = acquisition.source(suite=True)
    try:
        assert source.valid()
        assert "udev_properties" not in source.summary()
        assert list(acquisition.records.iterdir()) == []
        assert acquisition.notifications == []
    finally:
        source.close()


@pytest.mark.parametrize("label", [b"batocera hotkeys", b"suite controller"])
def test_metadata_is_refused_for_borrowed_nodes_without_deleting_them(
    acquisition: AcquisitionEnvironment, label: bytes
) -> None:
    """A kernel-identified existing node is not adopted for metadata publication."""
    acquisition.label = label
    acquisition.created = False
    creator = os.dup(acquisition.creator)
    with pytest.raises(RuntimeError, match="preexisting input node"):
        broker.Source(acquisition.process, (19, creator), "input7", 42, suite=True)
    node = acquisition.nodes[0]
    assert node.path.read_bytes() == b"unconsumed-event-data"
    assert_closed([creator, *node.opened])
    assert list(acquisition.records.iterdir()) == []
    assert acquisition.notifications == []


@pytest.mark.parametrize("suite", [False, True])
def test_wrong_stock_class_refuses_publication_and_closes_acquired_resources(
    acquisition: AcquisitionEnvironment, *, suite: bool
) -> None:
    """Final keyboards and suite pads cannot trade their required stock classes."""
    acquisition.label = b"suite controller" if suite else b"batocera hotkeys"
    acquisition.classification = (
        "ID_INPUT=1\nID_INPUT_KEY=1\n" if suite else "ID_INPUT=1\nID_INPUT_JOYSTICK=1\n"
    )
    creator = os.dup(acquisition.creator)
    with pytest.raises(RuntimeError, match="lacks required stock input classification"):
        broker.Source(acquisition.process, (19, creator), "input7", 42, suite=suite)
    assert_closed([creator, *acquisition.nodes[0].opened, *acquisition.duplicates])
    assert not acquisition.nodes[0].path.exists()
    assert list(acquisition.records.iterdir()) == []
    assert acquisition.notifications == []


@pytest.mark.parametrize("race", ["creator", "device", "process", "ioctl"])
def test_acquisition_rechecks_ownership_before_reading_or_advertising_events(
    acquisition: AcquisitionEnvironment, race: str
) -> None:
    """A stale creator, kernel identity or process cannot become an admitted source."""
    acquisition.label = b"batocera hotkeys"
    expected: type[Exception] = RuntimeError
    if race == "creator":
        acquisition.kernel_name = "input8"
    elif race == "device":

        def change_device() -> None:
            (acquisition.event / "dev").write_text("13:74\n", encoding="utf-8")

        acquisition.after_open = change_device
    elif race == "process":

        def revoke() -> None:
            acquisition.process.start += 1

        acquisition.after_open = revoke
        expected = ProcessLookupError
    else:
        acquisition.ioctl_error = errno.EIO
        expected = OSError
    creator = os.dup(acquisition.creator)
    with pytest.raises(expected):
        broker.Source(acquisition.process, (19, creator), "input7", 42)
    assert_closed([creator, *acquisition.nodes[0].opened])
    assert not acquisition.nodes[0].path.exists()
    assert acquisition.notifications == []
    assert list(acquisition.records.iterdir()) == []


@pytest.mark.parametrize(
    "mismatch", ["regular-fd", "device-number", "new-creator", "old-creator", "event"]
)
def test_validation_refuses_disagreeing_descriptors_and_closes_each_new_duplicate(
    acquisition: AcquisitionEnvironment,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    """Both creator pins and the event device must still identify one kernel source."""
    source = acquisition.source()
    try:
        if mismatch == "regular-fd":
            acquisition.duplicate_from = os.open(acquisition.cmdline, os.O_RDONLY)
        elif mismatch == "device-number":
            original_path = acquisition.path

            def path(value: str | os.PathLike[str]) -> Path:
                return (
                    Path("/dev/zero")
                    if str(value) == "/dev/uinput"
                    else original_path(value)
                )

            monkeypatch.setattr(broker, "Path", path)
        elif mismatch in ("new-creator", "old-creator"):
            original_ioctl = acquisition.ioctl

            def ioctl(
                descriptor: int,
                request: int,
                data: "bytearray | array.array[int]",
                mutate: Literal[True],
            ) -> int:
                result = original_ioctl(descriptor, request, data, mutate)
                changed = descriptor == source.creator
                if changed == (mismatch == "old-creator") and isinstance(
                    data, bytearray
                ):
                    data[:7] = b"input8\0"
                return result

            monkeypatch.setattr(fcntl, "ioctl", ioctl)
        else:
            (acquisition.event / "dev").write_text("13:74\n", encoding="utf-8")
        assert not source.valid()
        assert_closed(acquisition.duplicates)
        assert source.creator is not None
        os.fstat(source.creator)
    finally:
        source.close()
        if acquisition.duplicate_from is not None:
            os.close(acquisition.duplicate_from)
    assert not acquisition.nodes[0].path.exists()


@pytest.mark.parametrize("boundary", ["ioctl", "descriptor-transfer"])
@pytest.mark.parametrize(
    "error", [errno.ENOENT, errno.ENODEV, errno.EBADF, errno.ESRCH, errno.EINVAL]
)
def test_expected_kernel_revocations_are_invalid_sources_not_broker_failures(
    acquisition: AcquisitionEnvironment, error: int, boundary: str
) -> None:
    """The documented disappearance errors revoke a source without escaping."""
    source = acquisition.source()
    try:
        if boundary == "ioctl":
            acquisition.ioctl_error = error
        else:
            acquisition.duplicate_error = error
        assert not source.valid()
        assert_closed(acquisition.duplicates)
    finally:
        source.close()


@pytest.mark.parametrize("boundary", ["ioctl", "descriptor-transfer"])
def test_unexpected_kernel_errors_escape_but_do_not_leak_validation_duplicates(
    acquisition: AcquisitionEnvironment, boundary: str
) -> None:
    """Permission failures remain actionable instead of being hidden as revocation."""
    source = acquisition.source()
    try:
        if boundary == "ioctl":
            acquisition.ioctl_error = errno.EPERM
        else:
            acquisition.duplicate_error = errno.EPERM
        with pytest.raises(
            OSError, match=r"kernel ioctl refused|Operation not permitted"
        ) as caught:
            source.valid()
        assert caught.value.errno == errno.EPERM
        assert_closed(acquisition.duplicates)
    finally:
        source.close()


@pytest.mark.parametrize("revocation", ["process", "duplicate", "probe-command"])
def test_process_and_probe_revocation_prevent_descriptor_admission(
    acquisition: AcquisitionEnvironment, revocation: str
) -> None:
    """A stale process, lost descriptor or replaced probe command loses authority."""
    source = acquisition.source(suite=True)
    try:
        if revocation == "process":
            acquisition.process.start += 1
        elif revocation == "duplicate":
            acquisition.duplicate_error = errno.ESRCH
        else:
            acquisition.cmdline.write_bytes(
                b"/usr/bin/python3\0private-unrelated-task\0"
            )
        assert not source.valid()
        assert_closed(acquisition.duplicates)
    finally:
        source.close()


def test_descriptor_transfer_race_closes_the_new_pin_before_refusing_source(
    acquisition: AcquisitionEnvironment,
) -> None:
    """A process identity change inside pidfd_getfd cannot leak its returned FD."""
    source = acquisition.source()

    def revoke() -> None:
        acquisition.process.start += 1

    acquisition.after_duplicate = revoke
    try:
        assert not source.valid()
        assert_closed(acquisition.duplicates)
    finally:
        source.close()


def test_reacquiring_a_closed_source_refuses_without_allocating_an_event_node(
    acquisition: AcquisitionEnvironment,
) -> None:
    """Creator ownership is not resurrected after explicit teardown."""
    source = acquisition.source()
    source.close()
    with pytest.raises(RuntimeError, match="creator was already closed"):
        source.acquire(42, suite=False)
    assert len(acquisition.nodes) == 1
    assert not acquisition.nodes[0].path.exists()


@pytest.mark.parametrize("name", ["../input7", "input7/event9", "inputx", "input7\n"])
def test_kernel_identity_rejects_noncanonical_names_before_filesystem_access(
    acquisition: AcquisitionEnvironment, name: str
) -> None:
    """Kernel names cannot escape or broaden the confined input identity lookup."""
    with pytest.raises(RuntimeError, match="invalid kernel input identity"):
        broker.device_identity(name)
    assert acquisition.nodes == []


@pytest.mark.parametrize("layout", ["empty", "ambiguous", "parent-link", "event-link"])
def test_kernel_identity_refuses_missing_ambiguous_or_escaped_event_trees(
    acquisition: AcquisitionEnvironment, layout: str
) -> None:
    """Directory names alone do not authorize symlink targets or multiple events."""
    parent = acquisition.event.parent
    if layout == "empty":
        (acquisition.event / "dev").unlink()
        acquisition.event.rmdir()
    elif layout == "ambiguous":
        (parent / "event10").mkdir()
    else:
        target = acquisition.root / "foreign"
        if layout == "parent-link":
            parent.rename(target)
            parent.symlink_to(target, target_is_directory=True)
        else:
            acquisition.event.rename(target)
            acquisition.event.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match=r"expected one|unexpected kernel"):
        broker.device_identity("input7")
    assert acquisition.nodes == []


@pytest.mark.parametrize("number", ["13", "13:73:4", "-1:73", "13: 73", "13:73\nextra"])
def test_kernel_identity_refuses_malformed_character_device_numbers(
    acquisition: AcquisitionEnvironment, number: str
) -> None:
    """Malformed sysfs data cannot select a device node."""
    (acquisition.event / "dev").write_text(number, encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid kernel character device number"):
        broker.device_identity("input7")
    assert acquisition.nodes == []


@contextmanager
def bounded_child(command: list[str]) -> Iterator[subprocess.Popen[bytes]]:
    """Own one local child and terminate only its pinned pidfd during cleanup."""
    with subprocess.Popen(  # noqa: S603 - fixed local Python fixture argv.
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as child:
        descriptor = os.pidfd_open(child.pid)
        try:
            yield child
        finally:
            try:
                if child.poll() is None:
                    try:
                        child.communicate(input=b"x", timeout=5)
                    except subprocess.TimeoutExpired:
                        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                        child.wait(timeout=5)
            finally:
                os.close(descriptor)


def test_owned_process_duplicate_is_a_cloexec_descriptor_with_independent_lifetime(
    acquisition: AcquisitionEnvironment,
) -> None:
    """Releasing a transferred duplicate must leave its borrowed process/FD alive."""
    duplicate = acquisition.process.duplicate(19)
    try:
        assert fcntl.fcntl(duplicate, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
        assert os.read(duplicate, 1) == b""
    finally:
        os.close(duplicate)
    assert_closed([duplicate])
    os.fstat(acquisition.creator)
    assert acquisition.process.valid()


def test_owned_process_duplicate_refuses_stale_identity_without_syscall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already revoked process may not duplicate even a harmless descriptor."""
    process = broker.OwnedProcess(os.getpid())

    def forbidden(number: int, pidfd: int, descriptor: int, flags: int) -> int:
        del number, pidfd, descriptor, flags
        pytest.fail("revoked process reached pidfd_getfd")

    monkeypatch.setattr(broker.LIBC, "syscall", forbidden)
    try:
        process.start += 1
        with pytest.raises(ProcessLookupError):
            process.duplicate(19)
    finally:
        process.close()
    assert_closed([process.fd])


def test_owned_process_signals_only_its_live_pinned_child() -> None:
    """Pidfd signaling ends the owned child and becomes harmless after its exit."""
    command = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"]
    with bounded_child(command) as child:
        process = broker.OwnedProcess(child.pid)
        try:
            process.send(signal.SIGTERM)
            assert child.wait(timeout=5) == -signal.SIGTERM
            assert not process.valid()
            process.send(signal.SIGTERM)
        finally:
            process.close()
        assert_closed([process.fd])


@pytest.mark.parametrize("missing", ["cmdline", "exe"])
def test_process_command_disappearance_revokes_publication_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """A live pidfd does not excuse missing proc command or executable metadata."""
    command = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"]
    with bounded_child(command) as child:
        process = broker.OwnedProcess(child.pid)

        def path(value: str | os.PathLike[str]) -> Path:
            if str(value) == f"/proc/{child.pid}/{missing}":
                return tmp_path / "disappeared"
            return Path(value)

        monkeypatch.setattr(broker, "Path", path)
        try:
            assert not broker.process_command_matches(process, command)
            assert process.valid()
            assert child.poll() is None
        finally:
            process.close()


LEAF_COMMAND = "import sys; sys.stdin.buffer.read(1)"
GRANDCHILD_COMMAND = (
    "import os, subprocess, sys\n"
    f"with subprocess.Popen([sys.executable, '-c', {LEAF_COMMAND!r}], "
    "stdin=subprocess.PIPE) as child:\n"
    " print(str(os.getpid()) + ' ' + str(child.pid), flush=True)\n"
    " sys.stdin.buffer.read(1)\n"
    " child.communicate(input=b'x', timeout=5)\n"
)
TREE_COMMAND = (
    "import subprocess, sys\n"
    f"with subprocess.Popen([sys.executable, '-c', {GRANDCHILD_COMMAND!r}], "
    "stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True) as child:\n"
    " print(child.stdout.readline().decode().strip(), flush=True)\n"
    " sys.stdin.buffer.read(1)\n"
    " child.communicate(input=b'x', timeout=5)\n"
)


@contextmanager
def pidfd_close_failure(
    descriptor: int, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Raise after a real descriptor close to exercise remaining cleanup callbacks."""
    original_close = os.close

    def close(number: int) -> None:
        original_close(number)
        if number == descriptor:
            raise OSError(errno.EIO, "pidfd close failed")

    with monkeypatch.context() as boundary:
        boundary.setattr(os, "close", close)
        yield


@pytest.mark.parametrize("scenario", ["normal", "stale-snapshot", "close-error"])
def test_process_tree_admits_real_multigeneration_ancestry_not_foreign_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """A confined proc listing still uses actual pidfds, parentage and start ticks."""
    with bounded_child([sys.executable, "-c", TREE_COMMAND]) as child:
        assert child.stdout is not None
        assert select.select([child.stdout], [], [], 5)[0], "child did not become ready"
        descendant, leaf = map(int, child.stdout.readline().split())
        tree = broker.ProcessTree(child)
        opened: list[int] = []
        original_pidfd_open = os.pidfd_open

        def pidfd_open(pid: int, flags: int = 0) -> int:
            descriptor = original_pidfd_open(pid, flags)
            opened.append(descriptor)
            return descriptor

        monkeypatch.setattr(os, "pidfd_open", pidfd_open)
        try:
            for pid in (leaf, descendant, os.getpid()):
                (tmp_path / str(pid)).mkdir()
            original_stat = broker.process_stat
            sampled: set[int] = set()

            def snapshot(pid: int) -> tuple[int, int]:
                parent, start = original_stat(pid)
                if scenario == "stale-snapshot" and pid == leaf and pid not in sampled:
                    sampled.add(pid)
                    return parent, start + 1
                return parent, start

            def path(value: str | os.PathLike[str]) -> Path:
                return tmp_path if str(value) == "/proc" else Path(value)

            monkeypatch.setattr(broker, "Path", path)
            monkeypatch.setattr(broker, "process_stat", snapshot)
            tree.scan()
            assert descendant in tree.records
            assert (leaf in tree.records) is (scenario != "stale-snapshot")
            assert os.getpid() not in tree.records
            assert all(record.valid() for record in tree.records.values())
            descriptors = [record.fd for record in tree.records.values()]
        finally:
            try:
                if scenario == "close-error":
                    with (
                        pidfd_close_failure(tree.records[leaf].fd, monkeypatch),
                        pytest.raises(OSError, match="pidfd close failed"),
                    ):
                        tree.close()
                else:
                    tree.close()
            finally:
                child.communicate(input=b"x", timeout=5)
        assert child.returncode == 0
        assert tree.records == {}
        assert_closed([*descriptors, *opened])
