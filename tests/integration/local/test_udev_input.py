"""Protect stock input classification and inode-scoped metadata teardown."""

import contextlib
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from batocera_gow.runtime import input_transport as broker
from batocera_gow.runtime import udev_input as udev


@pytest.fixture
def record_content() -> bytes:
    """Return the exact stock keyboard metadata bytes used for publication."""
    return b"E:ID_INPUT=1\nE:ID_INPUT_KEY=1\n"


@pytest.fixture
def record_cleanup() -> Iterator[contextlib.ExitStack]:
    """Release pinned directories if a record assertion fails before close."""
    with contextlib.ExitStack() as cleanup:
        yield cleanup


class TestClassificationBoundary:
    """Accept only unambiguous stock properties for the requested input class."""

    def test_shortcut_keyboard_does_not_gain_an_invented_full_keyboard_class(
        self,
    ) -> None:
        """Keep shortcut keys distinct from a full keyboard classification."""
        assert udev.input_properties(
            "ID_INPUT=1\nID_INPUT_KEY=1\n", "ID_INPUT_KEY"
        ) == {"ID_INPUT": "1", "ID_INPUT_KEY": "1"}

    @pytest.mark.parametrize(
        "output",
        [
            "ID_INPUT=1\nID_INPUT_MOUSE=1\n",
            "ID_INPUT=1\nID_INPUT_KEY=1\nID_INPUT_KEY=1\n",
            "ID_INPUT=1\nID_INPUT_KEY=1\nE:ID_INPUT_JOYSTICK=1\n",
            # pragma: allowlist nextline secret
            "ID_INPUT=1\nID_INPUT_KEY=1\nDEVNAME=/dev/input/event0\n",
            "ID_INPUT=1\nID_INPUT_KEY=1\x00ACTION=remove\n",
            "ID_INPUT=1\nID_INPUT_KEY=1\n" + "x" * 4096,
        ],
    )
    def test_non_keyboard_or_injected_record_properties_are_refused(
        self, output: str
    ) -> None:
        """Reject conflicting, duplicate, injected and oversized classifier output."""
        with pytest.raises(RuntimeError):
            udev.input_properties(output, "ID_INPUT_KEY")

    def test_stock_gamepad_class_is_preserved_without_keyboard_invention(
        self,
    ) -> None:
        """Publish the stock joystick class without adding keyboard properties."""
        assert udev.input_properties(
            "ID_INPUT=1\nID_INPUT_JOYSTICK=1\n", "ID_INPUT_JOYSTICK"
        ) == {"ID_INPUT": "1", "ID_INPUT_JOYSTICK": "1"}

    @pytest.mark.parametrize(
        "output",
        [
            "ID_INPUT=1\nID_INPUT_KEY=1\n",
            "ID_INPUT_JOYSTICK=1\n",
            "ID_INPUT=1\nID_INPUT_JOYSTICK=0\n",
            "ID_INPUT=1\nID_INPUT_JOYSTICK=1\nID_INPUT_JOYSTICK=1\n",
            # pragma: allowlist nextline secret
            "ID_INPUT=1\nID_INPUT_JOYSTICK=1\nDEVNAME=/dev/input/event0\n",
        ],
    )
    def test_keyboard_or_ambiguous_classifier_cannot_authorize_gamepad_publication(
        self, output: str
    ) -> None:
        """Require a unique affirmative joystick and general input classification."""
        with pytest.raises(RuntimeError):
            udev.input_properties(output, "ID_INPUT_JOYSTICK")


class TestRecordBoundary:
    """Keep publication and cleanup confined to bytes and inodes we own."""

    name = "c13:200"

    def test_owned_record_is_removed_without_removing_unrelated_wolf_state(
        self,
        tmp_path: Path,
        record_content: bytes,
        record_cleanup: contextlib.ExitStack,
    ) -> None:
        """Remove our record exactly once while retaining another Wolf record."""
        foreign = tmp_path / "c13:199"
        foreign.write_bytes(b"Wolf state")
        record = udev.OwnedRecord(tmp_path, self.name, record_content)
        record_cleanup.callback(record.close)
        assert (tmp_path / self.name).read_bytes() == record_content
        assert record.close()
        assert not (tmp_path / self.name).exists()
        assert foreign.read_bytes() == b"Wolf state"
        assert not record.close()

    def test_existing_wolf_record_is_not_truncated_or_adopted(
        self, tmp_path: Path, record_content: bytes
    ) -> None:
        """Refuse publication over an existing record without altering its bytes."""
        path = tmp_path / self.name
        path.write_bytes(b"original Wolf record")
        with pytest.raises(FileExistsError):
            udev.OwnedRecord(tmp_path, self.name, record_content)
        assert path.read_bytes() == b"original Wolf record"
        assert set(tmp_path.iterdir()) == {path}

    def test_replaced_inode_is_foreign_even_when_contents_match(
        self,
        tmp_path: Path,
        record_content: bytes,
        record_cleanup: contextlib.ExitStack,
    ) -> None:
        """Matching bytes cannot authorize deleting a replacement inode."""
        record = udev.OwnedRecord(tmp_path, self.name, record_content)
        record_cleanup.callback(record.close)
        path = tmp_path / self.name
        original = tmp_path / "retained-original"
        path.rename(original)
        path.write_bytes(record_content)
        assert not record.close()
        assert path.read_bytes() == record_content
        assert original.read_bytes() == record_content

    def test_in_place_rewritten_record_is_foreign_even_when_inode_matches(
        self,
        tmp_path: Path,
        record_content: bytes,
        record_cleanup: contextlib.ExitStack,
    ) -> None:
        """An inode match cannot authorize removing another publisher's bytes."""
        path = tmp_path / self.name
        record = udev.OwnedRecord(tmp_path, self.name, record_content)
        record_cleanup.callback(record.close)
        path.write_bytes(b"E:ID_INPUT_JOYSTICK=1\n")
        assert not record.close()
        assert path.read_bytes() == b"E:ID_INPUT_JOYSTICK=1\n"

    def test_replaced_symlink_is_not_followed_or_removed(
        self,
        tmp_path: Path,
        record_content: bytes,
        record_cleanup: contextlib.ExitStack,
    ) -> None:
        """Leave replacement symlinks and their targets untouched."""
        record = udev.OwnedRecord(tmp_path, self.name, record_content)
        record_cleanup.callback(record.close)
        path = tmp_path / self.name
        path.unlink()
        foreign = tmp_path / "foreign"
        foreign.write_bytes(record_content)
        path.symlink_to(foreign)
        assert not record.close()
        assert path.is_symlink()
        assert foreign.read_bytes() == record_content

    def test_directory_replacement_does_not_redirect_cleanup(
        self,
        tmp_path: Path,
        record_content: bytes,
        record_cleanup: contextlib.ExitStack,
    ) -> None:
        """Clean through the pinned directory rather than a replacement pathname."""
        directory = tmp_path / "data"
        directory.mkdir(mode=0o700)
        record = udev.OwnedRecord(directory, self.name, record_content)
        record_cleanup.callback(record.close)
        retained = tmp_path / "retained"
        directory.rename(retained)
        directory.mkdir(mode=0o700)
        replacement = directory / self.name
        replacement.write_bytes(b"new Wolf record")
        assert record.close()
        assert not (retained / self.name).exists()
        assert replacement.read_bytes() == b"new Wolf record"

    def test_writable_or_symlinked_directory_cannot_authorize_publication(
        self, tmp_path: Path, record_content: bytes
    ) -> None:
        """Refuse writable directories and aliases before creating records."""
        directory = tmp_path / "data"
        directory.mkdir(mode=0o700)
        directory.chmod(0o777)
        with pytest.raises(RuntimeError):
            udev.OwnedRecord(directory, self.name, record_content)
        directory.chmod(0o700)
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        with pytest.raises(NotADirectoryError):
            udev.OwnedRecord(alias, self.name, record_content)
        assert not (directory / self.name).exists()


class FailingPublisher(udev.UdevPublisher):
    """Inject a sender failure without bypassing real record cleanup."""

    # Adopt an existing fixture record instead of allocating/publishing another.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, record: udev.OwnedRecord, message: str
    ) -> None:
        """Adopt one fixture record and report the selected notification failure."""
        self.record = record
        self.advertised = True
        self.message = message

    def notify(self, action: str) -> None:
        """Fail the external sender boundary after the owned record is revoked."""
        assert action == "remove"
        raise RuntimeError(self.message)


def test_notification_failure_does_not_abandon_other_owned_resources(
    tmp_path: Path, record_content: bytes
) -> None:
    """Continue removing nodes and closing pins after each sender failure."""
    foreign = tmp_path / "c13:199"
    foreign.write_bytes(b"Wolf record")
    sources: list[broker.Source] = []
    descriptors: list[int] = []
    with contextlib.ExitStack() as cleanup:
        for minor, message in (
            (200, "first remove failure"),
            (201, "second remove failure"),
        ):
            record = udev.OwnedRecord(tmp_path, f"c13:{minor}", record_content)
            cleanup.callback(record.close)
            source = broker.Source.__new__(broker.Source)
            source.udev = FailingPublisher(record, message)
            source.node = broker.EventNode.__new__(broker.EventNode)
            source.node.path = tmp_path / f"event{minor}"
            source.node.path.touch()
            source.node.created = True
            source.node.identity = broker.node_identity(source.node.path.lstat())
            cleanup.callback(source.node.close)
            source.reader = os.open(os.devnull, os.O_RDONLY)
            source.creator = None
            sources.append(source)
            cleanup.callback(close_source_after_failure, source)
            source.creator = os.open(os.devnull, os.O_RDONLY)
            descriptors.extend((source.reader, source.creator))
        supervisor = broker.Broker(
            [],
            (os.getuid(), os.getgid()),
            broker.start_process,
            time.monotonic,
            time.sleep,
        )
        supervisor.sources = {
            str(index): source for index, source in enumerate(sources)
        }
        supervisor.acknowledged = {"0", "1"}
        failure = supervisor.close_sources()
        assert isinstance(failure, RuntimeError)
        assert str(failure) == "first remove failure"
        assert supervisor.sources == {}
        assert supervisor.acknowledged == set()
        assert set(tmp_path.iterdir()) == {foreign}
        assert foreign.read_bytes() == b"Wolf record"
        for descriptor in descriptors:
            with pytest.raises(OSError, match="Bad file descriptor"):
                os.fstat(descriptor)


def close_source_after_failure(source: broker.Source) -> None:
    """Complete fixture cleanup while accepting only the injected sender fault."""
    with contextlib.suppress(RuntimeError):
        source.close()
