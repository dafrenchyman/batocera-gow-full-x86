"""Own qualification descendants in a dedicated Linux child subreaper.

Only this short-lived process enables subreaping. Its direct children, including
kernel-adopted orphans, cannot disappear or have their PIDs reused before waitpid.
No host-wide ancestry search or process-group membership establishes ownership.
"""

import ctypes
import json
import os
import select
import signal
import socket
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _Child:
    """Retain the target's wait status while reaping adopted descendants."""

    pid: int
    returncode: int | None = None
    observation_failed: bool = False


def _adopt_descendants() -> None:
    """Enable Linux orphan adoption before any target can fork or exit."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "Owned descendant boundary unavailable")


def _reap(child: _Child) -> bool:
    """Reap only this isolated supervisor's children; ECHILD proves absence."""
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        except OSError:
            child.observation_failed = True
            return False
        if pid == 0:
            return False
        if pid == child.pid:
            child.returncode = os.waitstatus_to_exitcode(status)


def _signal_children(number: int) -> bool:
    """Signal unreaped direct children; adoption closes fast intermediate exits.

    No wait occurs between reading and signaling. A dead child remains a zombie,
    so a numeric PID here cannot be recycled into an unrelated process.
    """
    complete = True
    try:
        children = Path(f"/proc/self/task/{os.getpid()}/children").read_text(
            encoding="ascii"
        )
        for text in children.split():
            try:
                os.kill(int(text), number)
            except ProcessLookupError:
                pass
            except OSError:
                complete = False
    except (OSError, ValueError):
        return False
    return complete


def _cleanup(child: _Child) -> bool:
    """Escalate only owned children and require the kernel's no-child result."""
    complete = True
    for number in (signal.SIGTERM, signal.SIGKILL):
        deadline = time.monotonic() + 2
        while True:
            if _reap(child):
                return complete and not child.observation_failed
            complete = _signal_children(number) and complete
            if time.monotonic() >= deadline:
                break
            time.sleep(0.02)
    return _reap(child) and complete and not child.observation_failed


def _supervise(control: socket.socket, command: list[str]) -> None:
    """Execute trusted argv, preserving stdio while retaining orphan ownership."""
    child: _Child | None = None
    error: int | None = None
    complete = True
    try:
        # SIG_IGN survives exec and auto-reaps children, invalidating PID ownership.
        # Reset it only in this dedicated supervisor before it creates children.
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        _adopt_descendants()
        control.set_inheritable(False)
        child = _Child(
            os.posix_spawnp(
                command[0],
                command,
                os.environ,
                setsid=True,
                setsigdef=(signal.SIGPIPE, signal.SIGXFSZ),
            )
        )
        while child.returncode is None and not _reap(child):
            readable, _, _ = select.select([control], [], [], 0.02)
            if readable and not control.recv(1):
                break
    except OSError as failure:
        error = failure.errno
    finally:
        if child is not None:
            complete = _cleanup(child)
        outcome = {
            "cleanup_complete": complete,
            "returncode": child.returncode if child is not None else None,
            "errno": error,
        }
        with suppress(OSError):
            control.send(json.dumps(outcome).encode())
        # If signaling or observation failed, do not orphan known descendants by
        # exiting. The caller reports this supervisor's PID for deliberate recovery.
        if child is not None:
            while not _reap(child):
                time.sleep(0.1)


def main() -> None:
    """Use a private inherited status/control socket, never target stdout/stderr."""
    with socket.socket(fileno=int(sys.argv[1])) as control:
        _supervise(control, sys.argv[2:])


if __name__ == "__main__":
    main()
