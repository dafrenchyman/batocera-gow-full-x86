"""Check shared-memory capacity and negotiated modes in an authorized Wolf app."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.wolf


@pytest.fixture(autouse=True)
def wolf_container() -> None:
    """Require explicit live-Wolf opt-in before touching session resources."""
    if (
        os.environ.get("GOW_WOLF_SESSION_TESTS") != "1"
        or not Path("/.dockerenv").exists()
        or not Path("/usr/bin/emulatorlauncher").is_file()
    ):
        pytest.skip("requires an explicitly authorized stock Wolf app container")


def test_private_shared_memory_holds_emulator_working_set() -> None:
    """Write every page of an emulator-sized private shared-memory allocation."""
    size = 256 * 1024 * 1024
    child = """
import json, mmap, os, resource, sys, tempfile
size = int(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
with tempfile.TemporaryFile(dir='/dev/shm') as stream:
    stream.truncate(size)
    with mmap.mmap(stream.fileno(), size) as memory:
        for offset in range(0, size, mmap.PAGESIZE):
            memory[offset] = (offset // mmap.PAGESIZE) % 251
        info = os.fstat(stream.fileno())
        print(json.dumps({'allocated': info.st_blocks * 512,
                          'checksum': sum(memory[::mmap.PAGESIZE]),
                          'pages': size // mmap.PAGESIZE}))
"""
    # Only the fixed page-writing program above runs in the authorized container.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", child, str(size)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"emulator-sized shared memory failed: {result.returncode}, {result.stderr}"
    )
    allocated = json.loads(result.stdout)
    assert allocated["allocated"] == size
    assert allocated["checksum"] == sum(i % 251 for i in range(allocated["pages"]))


@pytest.mark.skipif(
    not (
        os.environ.get("DISPLAY")
        and os.environ.get("GAMESCOPE_WIDTH")
        and os.environ.get("GAMESCOPE_HEIGHT")
    ),
    reason="requires actual Wolf X11 app environment",
)
def test_stock_mode_selection_keeps_negotiated_stream_size() -> None:
    """Keep the negotiated resolution when stock selects its maximum mode."""
    expected = (
        f"{int(os.environ['GAMESCOPE_WIDTH'])}x{int(os.environ['GAMESCOPE_HEIGHT'])}"
    )

    def current() -> str:
        return subprocess.check_output(
            ["/usr/bin/batocera-resolution", "currentResolution"],
            text=True,
            timeout=10,
        ).strip()

    assert current() == expected
    subprocess.run(
        ["/usr/bin/batocera-resolution", "minTomaxResolution"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert current() == expected
