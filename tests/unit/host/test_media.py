"""Exercise the installed local-media boundary without SSH or real media."""

import json
import os
from pathlib import Path

import pytest

from batocera_gow.host.media import main


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove only synthetic invocation settings for deterministic local tests."""
    for key in tuple(os.environ):
        if key.startswith("BATOCERA_GOW_"):
            monkeypatch.delenv(key)


def test_explicit_file_environment_and_cli_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resolve CLI over exported values over the selected file without exporting."""
    selected = tmp_path / "selected.env"
    selected.write_text(
        "BATOCERA_GOW_ROMS_ROOT=/file/roms\nBATOCERA_GOW_BIOS_ROOT=/file/bios\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BATOCERA_GOW_ROMS_ROOT", "/exported/roms")
    before = dict(os.environ)
    assert main(["--env-file", str(selected), "mounts"]) == 0
    assert json.loads(capsys.readouterr().out) == [
        "/exported/roms:/home/retro/userdata/roms:ro",
        "/file/bios:/home/retro/userdata/bios:ro",
    ]
    assert (
        main(["--env-file", str(selected), "--roms-root", "/cli/roms", "mounts"]) == 0
    )
    assert json.loads(capsys.readouterr().out) == [
        "/cli/roms:/home/retro/userdata/roms:ro",
        "/file/bios:/home/retro/userdata/bios:ro",
    ]
    assert dict(os.environ) == before


def test_local_mounts_never_discover_dotenv_or_require_ssh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A neighboring dotenv is ignored while explicit local settings need no SSH."""
    (tmp_path / ".env").write_text(
        "BATOCERA_GOW_ROMS_ROOT=/implicit/roms\nBATOCERA_GOW_BIOS_ROOT=/implicit/bios\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["mounts"]) == 2
    capsys.readouterr()
    assert (
        main(["--roms-root", "/local/roms", "--bios-root", "/local/bios", "mounts"])
        == 0
    )
    assert json.loads(capsys.readouterr().out) == [
        "/local/roms:/home/retro/userdata/roms:ro",
        "/local/bios:/home/retro/userdata/bios:ro",
    ]


def test_empty_cli_value_refuses_file_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An explicit invalid value cannot silently restore lower-priority settings."""
    selected = tmp_path / "selected.env"
    selected.write_text(
        "BATOCERA_GOW_ROMS_ROOT=/file/roms\nBATOCERA_GOW_BIOS_ROOT=/file/bios\n",
        encoding="utf-8",
    )
    assert main(["--env-file", str(selected), "--roms-root", "", "mounts"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_selected_file_failure_does_not_disclose_private_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing explicitly selected file fails closed with a public diagnostic."""
    selected = tmp_path / "private-operator-config.env"
    assert main(["--env-file", str(selected), "mounts"]) == 2
    output = capsys.readouterr().out
    assert str(selected) not in output
    assert (
        json.loads(output)["reason"]
        == "Cannot read the explicitly selected environment file"
    )


def test_missing_declared_catalog_points_to_explicit_resource_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing configured assets fail locally with guidance and no private path."""
    assert main(["--project-root", str(tmp_path), "catalog"]) == 2
    output = capsys.readouterr().out
    assert str(tmp_path) not in output
    assert "--project-root" in json.loads(output)["reason"]
