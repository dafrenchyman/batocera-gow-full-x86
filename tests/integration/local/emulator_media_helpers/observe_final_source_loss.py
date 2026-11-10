"""Observe loss of the final input source while its pinned emulator stays live."""

import json
import os
import select
import stat
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from batocera_gow.runtime import emulator_probe as module
from batocera_gow.runtime.emulator_lifecycle import ProcessIdentity
from batocera_gow.runtime.input_transport import live, process_stat


def main() -> None:
    """Own fixture patches while observing real emulator and input-source lifetimes."""
    with ExitStack() as patches:
        observe_source_loss(patches)


def observe_source_loss(patches: ExitStack) -> None:  # noqa: C901, PLR0912, PLR0915  # Keep both real child lifetimes and their shared cleanup together.
    """Drive real source death and retain role-specific process evidence."""
    probe = module.EmulatorProbe(Path(sys.argv[1]), case="xbox-xemu")
    children: list[subprocess.Popen[bytes]] = []
    node = "/dev/input/owned-host-fixture"
    actual_stat = os.stat

    def node_stat(
        path: int | str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        """Replace only the owned event node's metadata, forwarding every other stat."""
        if not isinstance(path, int) and os.fspath(path) == node:
            return os.stat_result(
                (stat.S_IFCHR | 0o600, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                {"st_rdev": os.makedev(13, 123)},
            )
        return actual_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    try:
        for index in range(2):
            child = subprocess.Popen(  # noqa: S603  # Fixed checked source-lifetime script and controlled role argv.
                [
                    sys.executable,
                    str(Path(__file__).with_name("consumer_final_source_loss.py")),
                    sys.argv[2] if index == 1 else "emulator",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            children.append(child)
            assert child.stdin is not None
            assert child.stdout is not None
            if not select.select([child.stdout], [], [], 2)[0]:
                message = "Owned process readiness timed out"
                raise RuntimeError(message)
            if child.stdout.readline() != b"ready\n":
                message = "Unexpected owned process readiness"
                raise RuntimeError(message)
        emulator, source = children
        assert source.stdin is not None
        probe.launcher = emulator
        probe.emulator_fd = os.pidfd_open(emulator.pid)
        probe.emulator_identity = ProcessIdentity(
            emulator.pid, process_stat(emulator.pid)[1]
        )
        ready: dict[str, object] = {
            "app_uid": os.getuid(),
            "approved_process_ids": [source.pid],
            "final": {
                "source_pid": source.pid,
                "sysname": "owned-fixture",
                "node": node,
            },
        }
        patches.enter_context(patch.object(os, "stat", node_stat))
        # Only event-node metadata is synthetic; process lifetimes remain real.
        probe.pin_final(ready)
        assert probe.final_fd is not None
        assert probe.final_identity is not None
        patches.enter_context(
            patch.object(module, "transport_ready", lambda _path: ready)
        )
        probe.result["chord"] = {"pressed": True, "released": True}
        source.stdin.write(b"exit\n")
        source.stdin.flush()
        tasks = None
        if sys.argv[2] == "thread-zombie":
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                fields = (
                    Path(f"/proc/{source.pid}/stat")
                    .read_bytes()
                    .rpartition(b") ")[2]
                    .split()
                )
                if fields[0] == b"Z":
                    tasks = len(tuple(Path(f"/proc/{source.pid}/task").iterdir()))
                    if tasks < 2 or not live(probe.final_fd):
                        message = "Owned source lost its held worker"
                        raise RuntimeError(message)
                    break
                select.select([probe.final_fd], [], [], 0.001)
            else:
                message = "Owned source leader did not become zombie"
                raise RuntimeError(message)
        else:
            if not select.select([probe.final_fd], [], [], 2)[0]:
                message = "Owned final source exit timed out"
                raise RuntimeError(message)
            os.waitid(os.P_PID, source.pid, os.WEXITED | os.WNOWAIT)
            if sys.argv[2] == "reaped":
                source.wait(timeout=2)
        failure = None
        try:
            probe.observe()
        except OSError as error:
            failure = type(error).__name__
        sys.stdout.write(
            json.dumps(
                {
                    "failure": failure,
                    "process_failure": probe.process_observation_failure,
                    "emulator_live": live(probe.emulator_fd),
                    "source": {"pid": source.pid, "start": probe.final_identity[1]},
                    "termination": probe.result.get("termination_observation"),
                    "source_tasks": tasks,
                }
            )
            + "\n"
        )
    finally:
        patches.close()
        for descriptor in (probe.emulator_fd, probe.final_fd):
            if descriptor is not None:
                os.close(descriptor)
        for child in children:
            assert child.stdin is not None
            assert child.stdout is not None
            if child.poll() is None:
                child.stdin.write(b"exit\nexit\n")
                child.stdin.flush()
                child.wait(timeout=2)
            child.stdin.close()
            child.stdout.close()


if __name__ == "__main__":
    main()
