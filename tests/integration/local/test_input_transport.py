"""Exercise installed process admission, inode ownership and pidfile boundaries."""

import contextlib
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from batocera_gow.runtime import input_transport as broker

EXPECTED_PID = 12345
PIDFILE_REJECTION_EXIT = 42


@pytest.fixture
def sleep_command() -> list[str]:
    """Resolve a harmless process whose lifetime each test explicitly owns."""
    executable = shutil.which("sleep")
    assert executable is not None
    return [executable, "60"]


@pytest.fixture
def start_process() -> Iterator[Callable[[list[str]], subprocess.Popen[bytes]]]:
    """Start real children and reap every successful allocation after the test."""
    with contextlib.ExitStack() as cleanup:

        def start(command: list[str]) -> subprocess.Popen[bytes]:
            """Allocate a readable child pipe and register immediate cleanup."""
            # Callers supply only fixture-owned Python or resolved sleep argv.
            child = subprocess.Popen(command, stdout=subprocess.PIPE)  # noqa: S603
            cleanup.callback(reap_process, child)
            return child

        yield start


def reap_process(child: subprocess.Popen[bytes]) -> None:
    """Kill and reap a fixture child, then close its captured output pipe."""
    try:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
    finally:
        if child.stdout is not None:
            child.stdout.close()


@pytest.mark.skipif(not hasattr(os, "pidfd_open"), reason="Linux pidfds are required")
class TestProcessBoundary:
    """Authorize actual descendants using pinned process identities, not PID alone."""

    def test_descendant_survives_setsid_but_unrelated_process_is_not_owned(
        self,
        start_process: Callable[[list[str]], subprocess.Popen[bytes]],
        sleep_command: list[str],
    ) -> None:
        """Find a detached descendant without admitting siblings or the test process."""
        unrelated = start_process(sleep_command)
        program = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen(sys.argv[1:],start_new_session=True); "
            "print(p.pid,flush=True); time.sleep(60)"
        )
        child = start_process([sys.executable, "-c", program, *sleep_command])
        assert child.stdout is not None
        descendant = int(child.stdout.readline())
        tree = broker.ProcessTree(child)
        try:
            tree.scan()
            assert descendant in tree.records
            assert unrelated.pid not in tree.records
            assert os.getpid() not in tree.records
            tree.records[descendant].send(signal.SIGTERM)
            assert unrelated.poll() is None
        finally:
            try:
                for record in tree.records.values():
                    record.send(signal.SIGKILL)
            finally:
                tree.close()

    def test_dead_pidfd_cannot_authorize_descriptor_access(
        self,
        start_process: Callable[[list[str]], subprocess.Popen[bytes]],
        sleep_command: list[str],
    ) -> None:
        """Refuse descriptor duplication after the pinned process has exited."""
        child = start_process(sleep_command)
        owned = broker.OwnedProcess(child.pid)
        try:
            child.terminate()
            child.wait(timeout=5)
            assert not owned.valid()
            with pytest.raises(ProcessLookupError):
                owned.duplicate(1)
        finally:
            owned.close()

    def test_start_identity_mismatch_refuses_live_numeric_pid(
        self,
        start_process: Callable[[list[str]], subprocess.Popen[bytes]],
        sleep_command: list[str],
    ) -> None:
        """Reject a live numeric PID whose start identity does not match its pin."""
        child = start_process(sleep_command)
        owned = broker.OwnedProcess(child.pid)
        try:
            owned.start += 1
            assert not owned.valid()
            with pytest.raises(ProcessLookupError):
                owned.duplicate(1)
            assert child.poll() is None
        finally:
            owned.close()

    def test_wrong_live_parent_does_not_authorize_a_sibling(
        self,
        start_process: Callable[[list[str]], subprocess.Popen[bytes]],
        sleep_command: list[str],
    ) -> None:
        """Refuse sibling admission while preserving both unrelated children."""
        first = start_process(sleep_command)
        second = start_process(sleep_command)
        parent = broker.OwnedProcess(first.pid)
        try:
            with pytest.raises(ProcessLookupError):
                broker.OwnedProcess(second.pid, parent)
            assert first.poll() is None
            assert second.poll() is None
        finally:
            parent.close()


class TestPublicationCreatorBoundary:
    """Require the live executable identity and exact argv before publication."""

    def test_only_exact_live_executable_and_arguments_match_publication_creator(
        self, start_process: Callable[[list[str]], subprocess.Popen[bytes]]
    ) -> None:
        """Reject changed arguments, executable, start identity and exited creators."""
        command = [sys.executable, "-c", "import time; time.sleep(60)"]
        child = start_process(command)
        owned = broker.OwnedProcess(child.pid)
        try:
            assert broker.process_command_matches(owned, command)
            assert not broker.process_command_matches(
                owned, [sys.executable, "-c", "other"]
            )
            assert not broker.process_command_matches(
                owned, ["/bin/true", *command[1:]]
            )
            owned.start += 1
            assert not broker.process_command_matches(owned, command)
            owned.start -= 1
            child.terminate()
            child.wait(timeout=5)
            assert not broker.process_command_matches(owned, command)
        finally:
            owned.close()

    def test_forged_argv_does_not_replace_actual_creator_executable_identity(
        self, sleep_command: list[str]
    ) -> None:
        """An argv impersonating Python cannot authorize a sleep executable."""
        sleeper = sleep_command[0]
        assert not Path(sys.executable).samefile(sleeper)
        command = [sys.executable, "60"]
        # Both forged argv and the resolved replacement executable are fixture data.
        child = subprocess.Popen(command, executable=sleeper)  # noqa: S603
        try:
            owned = broker.OwnedProcess(child.pid)
            try:
                assert Path(f"/proc/{child.pid}/cmdline").read_bytes() == b"".join(
                    os.fsencode(value) + b"\0" for value in command
                )
                assert Path(f"/proc/{child.pid}/exe").samefile(sleeper)
                assert not broker.process_command_matches(owned, command)
                assert child.poll() is None
            finally:
                owned.close()
        finally:
            reap_process(child)


def tracked_node(path: Path, *, created: bool = True) -> broker.EventNode:
    """Model a pinned inode without requiring privileged character-device creation.

    Args:
        path: Existing fixture inode to pin for open and cleanup checks.
        created: Whether ownership of this inode was acquired by the broker.

    Returns:
        A real EventNode whose filesystem lifecycle methods operate on the fixture.
    """
    node = broker.EventNode.__new__(broker.EventNode)
    node.path = path
    node.created = created
    node.identity = broker.node_identity(path.lstat())
    return node


class TestNodeBoundary:
    """Confine open and unlink operations to the recorded owned inode."""

    def test_cleanup_removes_only_the_recorded_inode(self, tmp_path: Path) -> None:
        """Retain both a foreign replacement and a renamed original."""
        path = tmp_path / "owned-node"
        path.write_bytes(b"owned")
        node = tracked_node(path)
        original = path.with_name("original")
        path.rename(original)
        path.write_bytes(b"replacement")
        node.close()
        assert path.read_bytes() == b"replacement"
        assert original.read_bytes() == b"owned"

    def test_cleanup_never_removes_preexisting_node_or_replacement_symlink(
        self, tmp_path: Path
    ) -> None:
        """Neither preexisting nodes nor symlink replacements transfer ownership."""
        path = tmp_path / "node"
        path.write_bytes(b"preexisting")
        tracked_node(path, created=False).close()
        assert path.read_bytes() == b"preexisting"
        owned = tracked_node(path)
        target = path.with_name("foreign")
        path.rename(target)
        path.symlink_to(target)
        owned.close()
        assert path.is_symlink()
        assert target.read_bytes() == b"preexisting"

    def test_open_rejects_replacement_before_any_read(self, tmp_path: Path) -> None:
        """Reject a replacement inode without consuming its content."""
        path = tmp_path / "node"
        path.write_bytes(b"original")
        node = tracked_node(path)
        path.rename(path.with_name("retained"))
        path.write_bytes(b"foreign")
        with pytest.raises(RuntimeError, match="changed during open"):
            node.open()
        assert path.read_bytes() == b"foreign"

    def test_cleanup_is_idempotent_for_owned_identity(self, tmp_path: Path) -> None:
        """Repeated cleanup safely removes one owned inode only once."""
        path = tmp_path / "node"
        path.write_bytes(b"owned")
        node = tracked_node(path)
        node.close()
        node.close()
        assert not path.exists()


class TestPidfileBoundary:
    """Read bounded regular pidfiles without following links or blocking on FIFOs."""

    def test_empty_writer_is_pending_but_finished_pid_is_read(
        self, tmp_path: Path
    ) -> None:
        """Distinguish an unfinished writer from a completed decimal PID."""
        path = tmp_path / "hotkeygen.pid"
        path.touch(mode=0o600)
        assert broker.read_pidfile(path, os.getuid()) is None
        path.write_text("12345", encoding="utf-8")
        assert broker.read_pidfile(path, os.getuid()) == EXPECTED_PID

    def test_symlink_and_oversized_file_are_refused(self, tmp_path: Path) -> None:
        """Refuse aliases and oversized data while preserving the target bytes."""
        target = tmp_path / "target"
        target.write_text("12345", encoding="utf-8")
        path = target.with_name("hotkeygen.pid")
        path.symlink_to(target)
        with pytest.raises(OSError, match="Too many levels of symbolic links"):
            broker.read_pidfile(path, os.getuid())
        path.unlink()
        path.write_text("1" * 33, encoding="utf-8")
        with pytest.raises(RuntimeError):
            broker.read_pidfile(path, os.getuid())
        assert target.read_text(encoding="utf-8") == "12345"

    def test_fifo_is_rejected_without_waiting_for_a_writer(
        self, tmp_path: Path
    ) -> None:
        """Bound real FIFO rejection in an installed-package subprocess."""
        path = tmp_path / "hotkeygen.pid"
        os.mkfifo(path, 0o600)
        program = (
            "import os,sys; from pathlib import Path; "
            "from batocera_gow.runtime import input_transport as broker\n"
            "try: broker.read_pidfile(Path(sys.argv[1]),os.getuid())\n"
            "except RuntimeError: raise SystemExit(42)\n"
        )
        # Python executes fixed test code with a pytest-owned FIFO pathname.
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", program, str(path)], timeout=3, check=False
        )
        assert result.returncode == PIDFILE_REJECTION_EXIT
