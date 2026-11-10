"""Observe the interpreter-to-stock-ELF transition and exact Qt argument gate."""

import json
import os
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from batocera_gow.runtime import emulator_probe as module
from batocera_gow.runtime.emulator_probe import EmulatorProbe
from batocera_gow.runtime.transport_probe import ProbeError


def main() -> None:
    """Own the temporary identity and launcher collaborators for this observation."""
    with ExitStack() as patches:
        observe_wrapper(patches)


def observe_wrapper(patches: ExitStack) -> None:
    """Hold the wrapper before exec, then attempt pinning with unchanged argv."""
    executable, wrapper = map(Path, sys.argv[1:3])
    renderer, mode = sys.argv[3:5]
    arguments = ["-batch", "-nogui", "--", "selected.chd"]
    if renderer == "OpenGL" and mode != "missing-visual":
        arguments = ["-visual", "0x125", *arguments]
    if mode == "vulkan-visual":
        arguments = ["-visual", "0x125", *arguments]
    elif mode == "extra-arg":
        arguments = ["-unsupported", *arguments]
    elif mode == "duplicate-visual":
        arguments = ["-visual", "0x225", *arguments]
    elif mode == "bad-visual":
        arguments[1] = "not-a-visual"
    child = subprocess.Popen(  # noqa: S603  # Owned copied wrapper, with intentionally varied Qt argv.
        [str(wrapper), *arguments], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    probe = EmulatorProbe(executable.parent, case="psx-duckstation")
    patches.enter_context(
        patch.object(
            probe,
            "case",
            SimpleNamespace(
                backend="duckstation",
                renderer=renderer,
                executable=str(executable),
            ),
        )
    )
    patches.enter_context(
        patch.object(probe, "launcher", SimpleNamespace(pid=os.getpid()))
    )
    patches.enter_context(
        patch.object(module, "duckstation_identity", lambda: {"fixture": True})
    )
    assert child.stdout is not None
    assert child.stdin is not None
    try:
        assert child.stdout.readline() == b"interpreter\n"
        assert Path(f"/proc/{child.pid}/comm").read_text().strip() == "duckstation-qt"
        probe.pin_emulator()
        assert probe.emulator_fd is None, (
            "interpreter must never be pinned as stock ELF"
        )
        child.stdin.write(b"go\n")
        child.stdin.flush()
        assert child.stdout.readline() == b"elf\n"
        try:
            probe.pin_emulator()
            assert probe.emulator_identity is not None
            outcome: dict[str, object] = {
                "pinned": probe.emulator_fd is not None,
                "pid": probe.emulator_identity.pid,
            }
        except ProbeError:
            outcome = {"pinned": False}
        sys.stdout.write(json.dumps(outcome) + "\n")
    finally:
        if probe.emulator_fd is not None:
            os.close(probe.emulator_fd)
        child.kill()
        child.wait(timeout=2)


if __name__ == "__main__":
    main()
