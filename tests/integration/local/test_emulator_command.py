"""Exercise emulator command admission through real proc-style cmdline files."""

from pathlib import Path

import pytest

from batocera_gow.runtime.emulator_probe import EmulatorProbe
from batocera_gow.runtime.transport_probe import ProbeError


@pytest.mark.parametrize(
    "cmdline",
    [
        b"retroarch\0private-game.nes\0-L",
        b"retroarch\0private-game.nes\0-L\0",
        b"retroarch\0private-game.nes\0",
        b"retroarch\0-L\0/foreign/core.so\0private-game.nes\0",
        b"retroarch\0-L\0/usr/lib/libretro/fceumm_libretro.so\0-L",
    ],
)
def test_truncated_libretro_core_option_is_controlled_failure(
    tmp_path: Path, cmdline: bytes
) -> None:
    """Refuse a final core option before admitting a candidate process."""
    process_view = tmp_path / "proc"
    process_view.mkdir()
    (process_view / "cmdline").write_bytes(cmdline)
    probe = EmulatorProbe(tmp_path)

    with pytest.raises(ProbeError) as refused:
        probe.validate_emulator_command(process_view)

    assert "private-game" not in str(refused.value)
    assert probe.emulator_identity is None
    assert probe.emulator_fd is None
    assert probe.result["status"] == "failed"


def test_stock_libretro_command_is_admitted_without_pinning(tmp_path: Path) -> None:
    """Keep the normal stock core and media arguments accepted."""
    process_view = tmp_path / "proc"
    process_view.mkdir()
    (process_view / "cmdline").write_bytes(
        b"/usr/bin/retroarch\0-L\0/usr/lib/libretro/fceumm_libretro.so\0"
        b"private-game.nes\0"
    )
    probe = EmulatorProbe(tmp_path)

    probe.validate_emulator_command(process_view)

    assert probe.emulator_identity is None
    assert probe.emulator_fd is None
    assert probe.result["status"] == "failed"
