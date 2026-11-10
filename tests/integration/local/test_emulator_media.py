"""Exercise packaged media, input discovery and private termination evidence."""

import errno
import hashlib
import json
import os
import select as io_select
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.host.native_remote import record, sequence

FAILURE_EXIT = 2
PREREQUISITE_SKIP_EXIT = 77
PRIVATE_FILE_MODE = 0o600
PUBLIC_ERRNO_MAX = 4095
DIAGNOSTIC_BYTE_LIMIT = 65536
DIAGNOSTIC_LINE_LIMIT = 256
SMALL_PUBLIC_RECORD_LIMIT = 512
PUBLIC_RECORD_LIMIT = 1024
MIN_THREAD_GROUP_TASKS = 2
SHUTDOWN_WAIT_POLLS = 4
LEASE_FAILURE_POLL = 2
SDL_LOG_PRIORITY_CRITICAL = 5
HELPERS = Path(__file__).with_name("emulator_media_helpers")


@pytest.fixture
def stock_catalog(pytestconfig: pytest.Config) -> Path:
    """Locate the public catalog independently of test-module installation paths.

    Args:
        pytestconfig: Configuration containing pytest's explicit repository root.

    Returns:
        Absolute path of the pinned stock catalog fixture.
    """
    return pytestconfig.rootpath / "tests/assets/media/stock-es_systems.cfg"


# Keep the selection and reproduction inputs explicit at the subprocess boundary.
def select(  # noqa: PLR0913
    output: Path,
    library: Path,
    reproduction: Path,
    *,
    catalog: Path,
    required: bool = False,
    case: str = "nes-fceumm",
) -> tuple[int, dict[str, object]]:
    """Select media through an installed probe in an isolated subprocess.

    Args:
        output: New private evidence directory created for this invocation.
        library: Read-only media view whose stock system folders are inspected.
        reproduction: Existing selection identity, or an absent path for selection.
        catalog: Pinned stock system and extension declarations.
        required: Whether absence of a reproduction record must fail.
        case: Public emulator case identifier.

    Returns:
        Process status and its public JSON selection or failure result.
    """
    output.mkdir(mode=0o700)
    completed = subprocess.run(  # noqa: S603  # Fixed probe; owned fixture argv.
        [
            sys.executable,
            "-I",
            str(HELPERS / "select_media.py"),
            str(output),
            str(library),
            str(catalog),
            str(reproduction),
            "yes" if required else "no",
            case,
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return completed.returncode, record(json.loads(completed.stdout))


@pytest.mark.parametrize("contents", ["absent", "empty", "unsupported"])
def test_absence_alone_skips_and_leaves_native_consumption_untested(
    tmp_path: Path, contents: str, stock_catalog: Path
) -> None:
    """Keep absent or unsupported media separate from native-consumption proof."""
    library = tmp_path / "library"
    library.mkdir()
    if contents != "absent":
        (library / "nes").mkdir()
    if contents == "unsupported":
        (library / "nes/notes.txt").write_text("Not media", encoding="utf-8")
    code, value = select(
        tmp_path / "output", library, tmp_path / "no-record", catalog=stock_catalog
    )
    report = record(value["report"])
    assert code == 0
    assert value["selected"] is False
    assert report["status"] == "skipped-no-media"
    assert report["reason"] == "Skipped: no compatible mounted media"
    assert record(report["native_device_consumption"])["status"] == "untested"
    assert not (tmp_path / "output/selection.json").exists()


def test_eligible_bytes_are_not_promoted_to_a_working_native_case(
    tmp_path: Path,
    stock_catalog: Path,
) -> None:
    """Retain private media identity without claiming the selected game works."""
    library = tmp_path / "library"
    (library / "nes").mkdir(parents=True)
    (library / "nes/private-title.nes").write_bytes(b"Synthetic non-ROM bytes")
    code, value = select(
        tmp_path / "first", library, tmp_path / "no-record", catalog=stock_catalog
    )
    assert code == 0
    assert value["selected"] is True
    report = record(value["report"])
    assert report["status"] == "failed"
    assert record(report["native_device_consumption"])["status"] == "untested"
    serialized = json.dumps(report)
    assert "private-title" not in serialized
    assert str(library) not in serialized
    selection = tmp_path / "first/selection.json"
    assert selection.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    code, reproduced = select(
        tmp_path / "second", library, selection, catalog=stock_catalog, required=True
    )
    assert code == 0
    assert reproduced["selected"] is True
    assert (tmp_path / "second/selection.json").read_bytes() == selection.read_bytes()


@pytest.mark.parametrize(
    ("case", "system", "filename"),
    [
        ("snes-snes9x", "snes", "selected.sfc"),
        ("megadrive-genesisplusgx", "megadrive", "selected.md"),
        ("atari2600-stella", "atari2600", "selected.a26"),
    ],
)
def test_remaining_libretro_packaged_selection_and_reproduction_are_case_local(
    tmp_path: Path, case: str, system: str, filename: str, stock_catalog: Path
) -> None:
    """Actual probe selection preserves stock route and private identity, not proof."""
    library = tmp_path / "library"
    folder = library / system
    folder.mkdir(parents=True)
    media = folder / filename
    media.write_bytes(b"Synthetic non-ROM bytes")
    code, value = select(
        tmp_path / "first",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case=case,
    )
    assert code == 0
    assert value["selected"] is True
    report = record(value["report"])
    assert report["case"] == case
    assert report["system"] == system
    assert report["status"] == "failed"
    assert record(report["native_device_consumption"])["status"] == "untested"
    assert filename not in json.dumps(report)
    original = tmp_path / "first/selection.json"
    selected = record(json.loads(original.read_bytes()))
    assert selected["system"] == system
    assert selected["entry"] == system + "/" + filename
    code, value = select(
        tmp_path / "reproduced",
        library,
        original,
        catalog=stock_catalog,
        case=case,
        required=True,
    )
    assert code == 0
    assert value["selected"] is True
    assert (
        tmp_path / "reproduced/selection.json"
    ).read_bytes() == original.read_bytes()
    media.unlink()
    code, value = select(
        tmp_path / "changed",
        library,
        original,
        catalog=stock_catalog,
        case=case,
        required=True,
    )
    assert code == FAILURE_EXIT
    assert "failure" in value
    code, value = select(
        tmp_path / "absent",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case=case,
    )
    assert code == 0
    assert value["selected"] is False
    absent = record(value["report"])
    assert absent["case"] == case
    assert absent["system"] == system
    assert absent["status"] == "skipped-no-media"
    assert record(absent["native_device_consumption"])["status"] == "untested"


@pytest.mark.parametrize(
    "case",
    ["snes-fceumm", "megadrive-picodrive", "atari2600-stella2014", "psx-pcsx_rearmed"],
)
def test_unsupported_packaged_case_cannot_select_media(
    tmp_path: Path, case: str, stock_catalog: Path
) -> None:
    """A stock-advertised alternative is not an implemented exit case."""
    library = tmp_path / "library"
    library.mkdir()
    code, value = select(
        tmp_path / "output",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case=case,
    )
    assert code == FAILURE_EXIT
    assert value == {"failure": "ValueError"}
    assert not (tmp_path / "output/selection.json").exists()


def test_nes_reproduction_cannot_skip_or_reroll_snes(
    tmp_path: Path, stock_catalog: Path
) -> None:
    """A valid other-system record fails even when the requested folder is empty."""
    library = tmp_path / "library"
    (library / "nes").mkdir(parents=True)
    (library / "nes/selected.nes").write_bytes(b"Synthetic non-ROM bytes")
    code, _ = select(
        tmp_path / "nes", library, tmp_path / "no-record", catalog=stock_catalog
    )
    assert code == 0
    (library / "snes").mkdir()
    code, value = select(
        tmp_path / "snes",
        library,
        tmp_path / "nes/selection.json",
        catalog=stock_catalog,
        case="snes-snes9x",
        required=True,
    )
    assert code == FAILURE_EXIT
    assert value["failure"] == "ProbeError"
    assert not (tmp_path / "snes/selection.json").exists()


@pytest.mark.parametrize("contents", ["absent", "unsupported"])
def test_duckstation_stock_disc_absence_stays_untested(
    tmp_path: Path, contents: str, stock_catalog: Path
) -> None:
    """A loose SDK executable is not stock PS1 disc media."""
    library = tmp_path / "library"
    library.mkdir()
    if contents == "unsupported":
        (library / "psx").mkdir()
        (library / "psx/private-title.psexe").write_bytes(b"Synthetic executable")
    code, value = select(
        tmp_path / "output",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case="psx-duckstation",
    )
    assert code == 0
    assert value["selected"] is False
    report = record(value["report"])
    assert report["case"] == "psx-duckstation"
    assert report["system"] == "psx"
    assert report["backend"] == "duckstation"
    assert report["status"] == "skipped-no-media"
    assert report["reason"] == "Skipped: no compatible mounted media"
    assert record(report["native_device_consumption"])["status"] == "untested"
    assert not (tmp_path / "output/selection.json").exists()


def assert_media_metadata_preserved(
    paths: tuple[Path, ...], before: dict[str, os.stat_result]
) -> None:
    """Check that selection and reproduction leave mounted-media metadata intact.

    Args:
        paths: Media entry and companion files observed before selection.
        before: Original inode, mode, size and modification-time observations.
    """
    for path in paths:
        original, observed = before[path.name], path.stat()
        assert observed.st_ino == original.st_ino
        assert observed.st_mode == original.st_mode
        assert observed.st_size == original.st_size
        assert observed.st_mtime_ns == original.st_mtime_ns


def assert_selected_disc(
    selection: Path, library: Path, report: dict[str, object]
) -> None:
    """Require private complete disc identity without public path disclosure."""
    assert report["case"] == "psx-duckstation"
    assert report["backend"] == "duckstation"
    assert report["status"] == "failed"
    assert record(report["native_device_consumption"])["status"] == "untested"
    assert "private-title" not in json.dumps(report)
    assert "private-track" not in json.dumps(report)
    assert str(library) not in json.dumps(report)
    assert selection.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    selected = record(json.loads(selection.read_bytes()))
    assert selected["entry"] == "psx/private-title.cue"
    assert {sequence(member)[0] for member in sequence(selected["members"])} == {
        "psx/private-title.cue",
        "psx/private-track.bin",
    }


@pytest.mark.parametrize("failure", ["changed-track", "missing-track", "symlink-track"])
def test_duckstation_cue_reproduction_rejects_changed_dependency_without_reroll(
    tmp_path: Path, failure: str, stock_catalog: Path
) -> None:
    """The actual probe preserves a disc's private identity, including its tracks."""
    library = tmp_path / "library"
    folder = library / "psx"
    folder.mkdir(parents=True)
    cue = folder / "private-title.cue"
    cue_bytes = b'FILE "private-track.bin" BINARY\n  TRACK 01 MODE2/2352\n'
    cue.write_bytes(cue_bytes)
    track = folder / "private-track.bin"
    track_bytes = b"Synthetic non-disc track"
    track.write_bytes(track_bytes)
    cue.chmod(0o444)
    track.chmod(0o444)
    before = {path.name: path.stat() for path in (cue, track)}
    code, value = select(
        tmp_path / "first",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case="psx-duckstation",
    )
    assert code == 0
    assert value["selected"] is True
    report = record(value["report"])
    selection = tmp_path / "first/selection.json"
    assert_selected_disc(selection, library, report)
    code, value = select(
        tmp_path / "reproduced",
        library,
        selection,
        catalog=stock_catalog,
        case="psx-duckstation",
        required=True,
    )
    assert code == 0
    assert value["selected"] is True
    assert (
        tmp_path / "reproduced/selection.json"
    ).read_bytes() == selection.read_bytes()
    assert cue.read_bytes() == cue_bytes
    assert track.read_bytes() == track_bytes
    assert_media_metadata_preserved((cue, track), before)
    track.unlink()
    if failure == "changed-track":
        track.write_bytes(b"Changed synthetic track")
    elif failure == "symlink-track":
        foreign = tmp_path / "foreign-track"
        foreign.write_bytes(track_bytes)
        track.symlink_to(foreign)
    (folder / "alternative.iso").write_bytes(b"Must not be selected after failure")
    code, value = select(
        tmp_path / "rejected",
        library,
        selection,
        catalog=stock_catalog,
        case="psx-duckstation",
        required=True,
    )
    assert code == FAILURE_EXIT
    assert "failure" in value
    assert "report" not in value
    assert not (tmp_path / "rejected/selection.json").exists()
    assert cue.read_bytes() == cue_bytes
    if failure == "symlink-track":
        assert track.is_symlink()
        assert track.read_bytes() == track_bytes


@pytest.mark.parametrize(
    "failure", ["catalog", "symlink", "changed", "missing-record", "unreadable"]
)
def test_media_errors_are_nonpassing_and_never_rerolled_or_skipped(
    tmp_path: Path, failure: str, stock_catalog: Path
) -> None:
    """Reject broken catalog, media or reproduction state without selecting again."""
    library = tmp_path / "library"
    system = library / "nes"
    system.mkdir(parents=True)
    media = system / "selected.nes"
    media.write_bytes(b"Synthetic non-ROM bytes")
    select(tmp_path / "first", library, tmp_path / "no-record", catalog=stock_catalog)
    reproduction = tmp_path / "first/selection.json"
    catalog = stock_catalog
    if failure == "catalog":
        catalog = tmp_path / "wrong-catalog"
        catalog.write_text("<systemList />", encoding="utf-8")
    elif failure == "symlink":
        media.unlink()
        media.symlink_to(tmp_path / "foreign")
    elif failure == "changed":
        media.write_bytes(b"Changed selected identity")
        (system / "other.nes").write_bytes(b"Alternative must not be selected")
    elif failure == "missing-record":
        reproduction = tmp_path / "missing-record"
    elif failure == "unreadable":
        media.chmod(0)
    code, value = select(
        tmp_path / "second", library, reproduction, catalog=catalog, required=True
    )
    assert code == FAILURE_EXIT
    assert "failure" in value
    assert "report" not in value
    assert not (tmp_path / "second/selection.json").exists()


def test_abrupt_probe_loss_keeps_exclusive_incomplete_boundary_not_final_proof(
    tmp_path: Path,
) -> None:
    """A real killed diagnostic cannot erase its completed private observation."""
    child = subprocess.Popen(  # noqa: S603  # Fixed probe; owned evidence directory.
        [sys.executable, "-I", str(HELPERS / "retain_boundary.py"), str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.stdout is not None
        assert io_select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline() == b"retained\n"
        path = tmp_path / "emulator-before-chord.json"
        data = path.read_bytes()
        observation = record(json.loads(data))
        assert observation["status"] == "incomplete"
        assert record(observation["probe"])["pid"] == child.pid
        assert observation["emulator"] is None
        assert observation["launcher"] is None
        assert (
            record(record(observation["observations"])["native_device_consumption"])[
                "status"
            ]
            == "untested"
        )
        child.kill()
        assert child.wait(timeout=5) < 0
        assert path.read_bytes() == data
        assert path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
        assert b"synthetic-private-exception-path" not in data
        assert not (tmp_path / "emulator-probe.json").exists()
        assert not path.with_name(path.name + ".partial").exists()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()


@pytest.mark.parametrize(
    ("variant", "kind", "status", "reason"),
    [
        ("normal", "exited", "classified", None),
        ("signal", "signaled", "classified", None),
        ("malformed", "unavailable", "rejected", "malformed-launcher-record"),
        ("trailing", "unavailable", "rejected", "trailing-output"),
        ("logging", "unavailable", "rejected", "logging-error"),
        ("no-eof", "unavailable", "stream-unavailable", None),
    ],
)
def test_termination_diagnostics_survive_final_and_incomplete_publication(
    tmp_path: Path, variant: str, kind: str, status: str, reason: str | None
) -> None:
    """Real pipes/pidfds distinguish rejected bytes from unavailable streams."""
    output = (
        b"2026-10-29 12:00:00,000 INFO (emulatorlauncher.py:624):launch "
        b"Batocera version: 43.1\n"
    )
    if variant == "signal":
        output += (
            b"2026-10-29 12:00:00,000 DEBUG (emulatorlauncher.py:683):launch "
            b"Emulator terminated by signal (Terminated: 15)\n"
        )
    elif variant == "malformed":
        output += b"private-title-secret emulatorlauncher.py malformed\n"
    output += (
        b"2026-10-29 12:00:00,000 DEBUG (emulatorlauncher.py:686):launch "
        b"Exiting configgen with status 0\n"
    )
    if variant == "trailing":
        output += b"private-title-secret trailing output\n"
    elif variant == "logging":
        output += (
            b"--- Logging error ---\nTraceback (most recent call last):\n"
            b'  File "/usr/lib/python3.12/logging/__init__.py", line 1160, in emit\n'
            b'  File "/usr/lib/python3.12/logging/__init__.py", line 999, in format\n'
            b'  File "/usr/lib/python3.12/logging/__init__.py", line 703, in format\n'
            b'  File "/usr/lib/python3.12/logging/__init__.py", '
            b"line 392, in getMessage\n"
            b"TypeError: not all arguments converted during string formatting\n"
            b"Call stack:\n"
            b'  File "/usr/lib/python3.12/site-packages/configgen/'
            b'emulatorlauncher.py", line 596, in runCommand\n'
            b"Message: 'private-title-secret'\nArguments: ('private-title-secret',)\n"
        )
    completed = subprocess.run(  # noqa: S603  # Fixed probe; synthetic log bytes.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_termination.py"),
            str(tmp_path),
            output.hex(),
            variant,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    final = record(json.loads((tmp_path / "emulator-probe.json").read_bytes()))
    termination = record(final["termination_observation"])
    ended = record(termination["emulator"])
    launcher = record(termination["launcher"])
    assert termination["mechanism"] == "pidfd-and-stock-launcher"
    assert ended["live"] is False
    pid, start = ended["pid"], ended["start"]
    assert isinstance(pid, int)
    assert pid > 1
    assert isinstance(start, int)
    assert start > 0
    assert launcher["pid"] != ended["pid"]
    assert launcher["code"] == 0
    assert final["status"] == "failed"
    assert termination["kind"] == kind
    classification = record(termination["classification"])
    assert classification["status"] == status
    assert classification["reason"] == reason
    if variant == "logging":
        assert classification["logging_error"] == {
            "status": "recognized",
            "exception": "TypeError",
            "condition": "format-arguments",
            "errno": None,
            "frames": [
                ["stdlib-stream-emit", 1160],
                ["stdlib-handler-format", 999],
                ["stdlib-message-format", 703],
                ["stdlib-message-interpolation", 392],
                ["stock-emulator-stderr-log", 596],
            ],
            "unknown_frames": False,
            "additional_markers": False,
        }
    assert termination["complete"] is (kind != "unavailable")
    stream = record(termination["private_output"])
    assert stream["overflow"] is False
    assert stream["read_failed"] is False
    assert stream["cancelled"] is False
    assert stream["eof"] is (variant != "no-eof")
    assert termination["log_sha256"] == (
        None if variant == "no-eof" else hashlib.sha256(output).hexdigest()
    )
    for name in ("launcher-exit", "cleanup-returned"):
        path = tmp_path / ("emulator-" + name + ".json")
        boundary = record(json.loads(path.read_bytes()))
        assert boundary["status"] == "incomplete"
        assert (
            record(boundary["observations"])["termination_observation"] == termination
        )
        assert path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    assert record(boundary["private_output"])["cancelled"] is True
    assert "transition" not in final
    assert "private-title-secret" not in json.dumps(final)
    assert "private-title-secret" not in path.read_text(encoding="utf-8")


# Public stock fixture provenance: bounded exact-member reads from stock-root.tar,
# assembly b48a2301452746b1ee77e951181bd7becde4fb975ed5d7988445fb3ee9e4f3d8.
# logger.py SHA256 322e6ea24d3ce5628d83b9a21ee66b83941ff04b8985535e02e8e05799b0918f
# defines the formatter at109. emulatorlauncher.py SHA256
# 73313380a3d40a44580c2e046eadf1f2b8c315cf475a0d56dd0a916e0b0a6a1f
# logs exactly "configgen exception: " at662/668 in launch, and calls main at660.
# duckstationGenerator.py SHA256
# 00751590cabf239f2cdab37e8edcbe3c7460373beda0b4a59fe60cd1a9e32536
# calls the controller DB writer at436 in generate. These synthetic tracebacks
# model those public locations, not the lost native exception or its cause.
STOCK_STARTUP_HEADER = (
    b"2026-10-30 12:00:00,000 ERROR (emulatorlauncher.py:668):launch "
    b"configgen exception: \n"
)
STOCK_STARTUP_FRAMES = (
    b'  File "/usr/lib/python3.12/site-packages/configgen/'
    b'emulatorlauncher.py", line 660, in launch\n'
    b"    private_source_echo(private_argument)\n"
    b'  File "/usr/lib/python3.12/site-packages/configgen/generators/'
    b'duckstation/duckstationGenerator.py", line 436, in generate\n'
    b"    private_environment_value\n"
)
STOCK_STARTUP_EXCEPTION = (
    STOCK_STARTUP_HEADER
    + b"Traceback (most recent call last):\n"
    + STOCK_STARTUP_FRAMES
    + b"PermissionError: [Errno 13] private_message: '/private_disc_path'\n"
)

# The public reducer admits only the following stock exception categories.
# Only PermissionError, FileNotFoundError, OSError, ValueError, RuntimeError,
# TypeError and KeyError are public categories; everything else is rejected.
# Frames are exact full-path/function/line matches reduced to public role/line.
# Rejections have no category, errno or frames. Reasons and flags are fixed enums
# and booleans. No raw hashes, messages, source echoes or argument fields exist.


def startup_diagnostic(output: bytes) -> dict[str, object]:
    """Reduce private stock-launch output through the installed public reducer.

    Args:
        output: Synthetic logger-framed traceback bytes, including hostile text.

    Returns:
        Bounded public exception categories and frame roles without source text.
    """
    completed = subprocess.run(  # noqa: S603  # Fixed reducer; input is bytes only.
        [sys.executable, "-I", str(HELPERS / "reduce_stock_startup.py")],
        input=output,
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    return record(json.loads(completed.stdout))


def test_startup_diagnostic_selects_stock_exception_without_private_text() -> None:
    """Arbitrary traceback-like output before the logger envelope is not authority."""
    value = startup_diagnostic(
        b"private_prefix\nTraceback (most recent call last):\n"
        b"RuntimeError: private_unframed_exception\n"
        + STOCK_STARTUP_EXCEPTION
        + b"2026-10-30 12:00:00,000 DEBUG (emulatorlauncher.py:686):launch "
        b"Exiting configgen with status 0\n"
    )
    assert value == {
        "status": "recognized",
        "reason": None,
        "exception": "PermissionError",
        "errno": 13,
        "frames": [
            ["stock-launch-main", 660],
            ["stock-duckstation-controller-db", 436],
        ],
        "unknown_frames": False,
        "frames_truncated": False,
        "additional_exceptions": False,
    }


@pytest.mark.parametrize("line", [662, 668])
@pytest.mark.parametrize("number", [1, 4095, 0, 4096, -1])
def test_startup_diagnostic_limits_errno_in_both_stock_handlers(
    line: int, number: int
) -> None:
    """Publish errno only in the supported Linux range for either stock handler."""
    output = (
        STOCK_STARTUP_HEADER.replace(b":668)", f":{line})".encode("ascii"))
        + b"Traceback (most recent call last):\n"
        + STOCK_STARTUP_FRAMES
        + f"OSError: [Errno {number}] private_message\n".encode("ascii")
    )
    value = startup_diagnostic(output)
    assert value["status"] == "recognized"
    assert value["exception"] == "OSError"
    assert value["errno"] == (number if 1 <= number <= PUBLIC_ERRNO_MAX else None)
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize(
    "frame",
    [
        b'  File "/private/emulatorlauncher.py", line 660, in launch\n',
        (
            b'  File "/usr/lib/python3.12/site-packages/configgen/'
            b'emulatorlauncher.py", line 661, in launch\n'
        ),
        (
            b'  File "/usr/lib/python3.12/site-packages/configgen/'
            b'emulatorlauncher.py", line 660, in private_function\n'
        ),
    ],
)
def test_startup_diagnostic_never_promotes_lookalike_frames(frame: bytes) -> None:
    """Reject private or near-match traceback paths without exporting frame text."""
    value = startup_diagnostic(
        STOCK_STARTUP_HEADER
        + b"Traceback (most recent call last):\n"
        + frame
        + b"    private_source_echo\n"
        + b"ValueError: private_message\n"
    )
    assert value["status"] == "recognized"
    assert value["exception"] == "ValueError"
    assert value["frames"] == []
    assert value["unknown_frames"] is True
    assert "private_" not in json.dumps(value)


def test_startup_diagnostic_caps_public_frames_without_copying_source_lines() -> None:
    """Bound reduced stock frames and discard echoed source and private arguments."""
    value = startup_diagnostic(
        STOCK_STARTUP_HEADER
        + b"Traceback (most recent call last):\n"
        + STOCK_STARTUP_FRAMES * 5
        + b"RuntimeError: private_message\n"
    )
    assert value["status"] == "recognized"
    assert (
        value["frames"]
        == [
            ["stock-launch-main", 660],
            ["stock-duckstation-controller-db", 436],
        ]
        * 4
    )
    assert value["frames_truncated"] is True
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("unknown-category", "unknown-exception"),
        ("truncated", "malformed-envelope"),
        ("bytes", "oversized-envelope"),
        ("lines", "oversized-envelope"),
        ("chained", "additional-exceptions"),
        ("second-envelope", "additional-exceptions"),
    ],
)
def test_startup_diagnostic_rejects_unsafe_envelopes_without_text(
    variant: str, reason: str
) -> None:
    """Reject ambiguous, clipped and chained envelopes without leaking their bytes."""
    output = STOCK_STARTUP_EXCEPTION
    if variant == "unknown-category":
        output = output.replace(b"PermissionError:", b"PrivateExceptionName:")
    elif variant == "truncated":
        output = output.rsplit(b"PermissionError:", 1)[0]
    elif variant == "bytes":
        output = output.replace(b"private_message", b"x" * 8192)
    elif variant == "lines":
        output = output.replace(b"    private_environment_value\n", b"    x\n" * 129)
    elif variant == "chained":
        output += (
            b"\nDuring handling of the above exception, another exception occurred:\n\n"
            b"Traceback (most recent call last):\n"
            + STOCK_STARTUP_FRAMES
            + b"TypeError: private_second_message\n"
        )
    elif variant == "second-envelope":
        output += STOCK_STARTUP_EXCEPTION.replace(b"PermissionError:", b"TypeError:")
    value = startup_diagnostic(output)
    assert value["status"] == "rejected"
    assert value["reason"] == reason
    assert value["exception"] is None
    assert value["errno"] is None
    assert value["frames"] == []
    assert value["additional_exceptions"] is (variant in ("chained", "second-envelope"))
    assert len(json.dumps(value)) < PUBLIC_RECORD_LIMIT
    assert "private" not in json.dumps(value).lower()


@pytest.mark.parametrize("variant", ["unframed", "wrong-emitter", "logging-arguments"])
def test_startup_diagnostic_does_not_search_arbitrary_messages_for_exceptions(
    variant: str,
) -> None:
    """Require the stock logger envelope instead of searching arbitrary output."""
    output = STOCK_STARTUP_EXCEPTION
    if variant == "unframed":
        output = output[len(STOCK_STARTUP_HEADER) :]
    elif variant == "wrong-emitter":
        output = output.replace(b":668):launch", b":596):runCommand")
    else:
        output = (
            b"--- Logging error ---\n"
            b"Message: "
            + repr(STOCK_STARTUP_EXCEPTION).encode("ascii")
            + b"\nArguments: ('private_argument',)\n"
        )
    value = startup_diagnostic(output)
    assert value["status"] == "not-found"
    assert value["exception"] is None
    assert value["errno"] is None
    assert value["frames"] == []
    assert "private" not in json.dumps(value).lower()


@pytest.mark.parametrize("variant", ["complete", "no-eof", "overflow"])
def test_startup_diagnostic_survives_early_unpinned_launcher_and_reader_cleanup(
    tmp_path: Path, variant: str
) -> None:
    """The real failure boundary retains a reduction before the only reader closes."""
    completed = subprocess.run(  # noqa: S603  # Fixed probe; owned fixture argv.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_startup.py"),
            str(tmp_path),
            variant,
        ],
        input=STOCK_STARTUP_EXCEPTION,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    final = record(json.loads((tmp_path / "emulator-probe.json").read_bytes()))
    diagnostic = record(final["launch_failure_diagnostic"])
    assert diagnostic["launcher_code"] == 0
    exception = record(diagnostic["exception_observation"])
    stream = record(diagnostic["private_output"])
    assert stream["cancelled"] is False
    assert stream["eof"] is (variant != "no-eof")
    assert stream["overflow"] is (variant == "overflow")
    if variant == "complete":
        assert exception["status"] == "recognized"
        assert exception["exception"] == "PermissionError"
        assert exception["errno"] == errno.EACCES
        assert exception["frames"] == [
            ["stock-launch-main", 660],
            ["stock-duckstation-controller-db", 436],
        ]
    else:
        assert exception["status"] == "stream-unavailable"
        assert exception["exception"] is None
        assert exception["errno"] is None
        assert exception["frames"] == []
    assert final["status"] == "failed"
    assert "chord" not in final
    assert "transition" not in final
    assert "termination_observation" not in final
    confidential_markers = (
        "private_source_echo",
        "private_argument",
        "private_environment_value",
        "private_message",
        "/private_disc_path",
    )
    for name in ("failure", "cleanup-returned"):
        path = tmp_path / ("emulator-" + name + ".json")
        boundary = record(json.loads(path.read_bytes()))
        assert boundary["status"] == "incomplete"
        assert boundary["emulator"] is None
        assert (
            record(boundary["observations"])["launch_failure_diagnostic"] == diagnostic
        )
        assert path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
        assert all(
            marker not in json.dumps(boundary) for marker in confidential_markers
        )
    cleared = record(boundary["private_output"])
    assert cleared["retained_bytes"] == 0
    assert cleared["cancelled"] is True
    assert all(marker not in json.dumps(final) for marker in confidential_markers)


# Public protocol and limits are sourced in research/duckstation-startup-failure.md.
# These are observations, not authenticated causes or shortcut acceptance.
DUCKSTATION_STDERR_HEADER = (
    b"2026-10-30 12:00:00,000 ERROR (emulatorlauncher.py:596):runCommand "
)
DUCKSTATION_RENDERER_FAILURE = (
    b"[    0.1250] \x1b[1;31mE(CreateGPU): "
    b"Failed to create fallback software renderer.\x1b[0m\n"
)
DUCKSTATION_QT_DISPLAY_FAILURE = (
    b"qt.qpa.xcb: could not connect to display private_display_value\n"
)
DUCKSTATION_SBI_WARNING = (
    b"[    0.1250] \x1b[1;33mW(CheckForSBIFile): "
    b"SBI file missing but required for private_serial (private_title)\x1b[0m\n"
)
DUCKSTATION_GPU_DEVICE_FAILURE = (
    b"[    0.1250] \x1b[1;31mE(CreateGPUDevice): "
    b"Failed to create GPU device: eglInitialize() failed: 12289 (0x3001)\x1b[0m\n"
)


def duckstation_startup_observation(output: bytes | None) -> dict[str, object]:
    """Reduce synthetic output without running DuckStation or reading private logs.

    Args:
        output: Stock-framed stderr bytes, or None when the stream is unavailable.

    Returns:
        Fixed diagnostic roles with bounded scan counts and availability flags.
    """
    completed = subprocess.run(  # noqa: S603  # Fixed reducer; input is bytes only.
        [
            sys.executable,
            "-I",
            str(HELPERS / "reduce_duckstation_startup.py"),
            "unavailable" if output is None else "available",
        ],
        input=output or b"",
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    return record(json.loads(completed.stdout))


@pytest.mark.parametrize(
    ("line", "role"),
    [
        (
            DUCKSTATION_QT_DISPLAY_FAILURE,
            "qt-xcb-display-connect-failed",
        ),
        (
            (
                b"qt.qpa.plugin: Could not load the Qt platform plugin "
                b'"private_plugin" '
                b'in "/private_plugin_path" even though it was found.\n'
            ),
            "qt-platform-plugin-load-failed",
        ),
        (
            (
                b"This application failed to start because no Qt platform plugin "
                b"could be initialized. Reinstalling the application may fix "
                b"this problem.\n"
            ),
            "qt-platform-initialization-failed",
        ),
        (
            DUCKSTATION_RENDERER_FAILURE,
            "duckstation-software-renderer-create-failed",
        ),
        (
            (
                b"\x1b[1;31mE(CreateGPU): Failed to create fallback software renderer."
                b"\x1b[0m\n"
            ),
            "duckstation-software-renderer-create-failed",
        ),
        (
            DUCKSTATION_SBI_WARNING,
            "duckstation-required-sbi-missing",
        ),
        (
            DUCKSTATION_GPU_DEVICE_FAILURE,
            "duckstation-egl-initialize-failed",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"eglGetDisplay() failed: 12291 (0x3003)\n"
            ),
            "duckstation-egl-display-failed",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"Loading GLAD EGL functions failed\n"
            ),
            "duckstation-glad-egl-load-failed",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"Failed to load GL functions for GLAD\n"
            ),
            "duckstation-glad-gl-load-failed",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"Failed to load GLES functions for GLAD\n"
            ),
            "duckstation-glad-gl-load-failed",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"Failed to create any context versions\n"
            ),
            "duckstation-gl-context-versions-exhausted",
        ),
        (
            (
                b"E(CreateGPUDevice): Failed to create GPU device: "
                b"Failed to create device.\n"
            ),
            "duckstation-gpu-device-create-failed",
        ),
        (
            (
                b"E(LoadEGL): Failed to load EGL: "
                b"/private/driver.so: undefined symbol: private_symbol\n"
            ),
            "duckstation-egl-load-failed",
        ),
        (
            b"E(CreateDevice): Failed to create any GL context\n",
            "duckstation-gl-context-create-failed",
        ),
        (
            b"E(CreateContext): eglChooseConfig() failed: 0x3001\n",
            "duckstation-egl-context-attempt-failed",
        ),
        (
            b"E(CreateContext): eglBindAPI(EGL_OPENGL_API) failed\n",
            "duckstation-egl-context-attempt-failed",
        ),
        (
            b"E(CreateContext): eglBindAPI(EGL_OPENGL_ES_API) failed\n",
            "duckstation-egl-context-attempt-failed",
        ),
        (
            b"E(CreateContext): eglCreateContext() failed: 0x3009\n",
            "duckstation-egl-context-attempt-failed",
        ),
        (
            b"E(CreateContextAndSurface): eglMakeCurrent() failed: 0x3009\n",
            "duckstation-egl-make-current-failed",
        ),
        (
            (
                b"E(TryGetPlatformDisplay): "
                b"eglGetPlatformDisplayEXT() failed: 12291 (0x3003)\n"
            ),
            "duckstation-egl-platform-display-failed",
        ),
        (
            b"*************** Unhandled SIGSEGV at 0x12345678 ***************\n",
            "duckstation-crash-handler-sigsegv",
        ),
        (
            b"*************** Unhandled SIGBUS at 0x12345678 ***************\n",
            "duckstation-crash-handler-sigbus",
        ),
        (
            b"Aborting application.\n",
            "duckstation-crash-handler-aborting",
        ),
    ],
)
def test_duckstation_startup_observation_reduces_exact_public_roles(
    line: bytes, role: str
) -> None:
    """Only fixed roles survive the exact stock stderr and upstream envelopes."""
    output = DUCKSTATION_STDERR_HEADER + line
    value = duckstation_startup_observation(output)
    assert value == {
        "status": "matched",
        "roles": [role],
        "bytes_scanned": len(output),
        "lines_scanned": 1,
        "truncated": False,
        "partial_line": False,
    }
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize(
    ("message", "role"),
    [
        (
            "Cannot authenticate to the current X11 display",
            "duckstation-wrapper-x11-authentication-failed",
        ),
        (
            "Cannot initialize EGL on the current X11 display",
            "duckstation-wrapper-egl-initialize-failed",
        ),
        ("EGL config enumeration failed", "duckstation-wrapper-egl-enumeration-failed"),
        (
            "EGL config count exceeds discovery bound",
            "duckstation-wrapper-egl-count-exceeded",
        ),
        (
            "EGL config enumeration changed beyond its bound",
            "duckstation-wrapper-egl-enumeration-changed",
        ),
        (
            "EGL config attribute unavailable",
            "duckstation-wrapper-egl-attribute-missing",
        ),
        (
            "Cannot release the discovery EGL context",
            "duckstation-wrapper-egl-context-release-failed",
        ),
        (
            "Chosen EGL config has no native X11 visual",
            "duckstation-wrapper-egl-visual-missing",
        ),
        (
            "Chosen EGL visual is not valid on the current X11 screen",
            "duckstation-wrapper-x11-visual-invalid",
        ),
        (
            "No supported DuckStation EGL context/config for this X11 session",
            "duckstation-wrapper-egl-context-unavailable",
        ),
        (
            "Cannot load or query live EGL/X11 for automatic visual discovery",
            "duckstation-wrapper-discovery-unavailable",
        ),
        (
            "Discovery returned an invalid native X11 visual",
            "duckstation-wrapper-discovery-result-invalid",
        ),
    ],
)
def test_duckstation_wrapper_refusals_reduce_only_fixed_public_messages(
    message: str, role: str
) -> None:
    """Keep emitted refusal roles distinguishable without private text."""
    line = (
        b"DuckStation compatibility wrapper: OpenGL launch refused: "
        + message.encode("ascii")
        + b". No uncorrected or renderer fallback was attempted.\n"
    )
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER + b"private_unmatched_diagnostic\n" + line
    )
    assert value["status"] == "matched"
    assert value["roles"] == [role]
    expected_lines = 2
    assert value["lines_scanned"] == expected_lines
    assert message not in json.dumps(value)
    assert "private_unmatched_diagnostic" not in json.dumps(value)


@pytest.mark.parametrize("failure", ["visual", "settings"])
def test_actual_wrapper_refusal_reaches_startup_diagnostic(
    tmp_path: Path, failure: str
) -> None:
    """Actual wrapper stderr and exit one are observed without starting an emulator."""
    settings = tmp_path / "settings.ini"
    settings.write_text("[GPU]\nRenderer=OpenGL\n", encoding="utf-8")
    completed = subprocess.run(  # noqa: S603  # Fixed wrapper; owned settings path.
        [
            sys.executable,
            "-I",
            str(HELPERS / "wrapper_refusal.py"),
            str(settings),
            failure,
        ],
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 1
    assert completed.stdout == b""
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER + completed.stderr + b"\n"
    )
    assert value["roles"] == [
        "duckstation-wrapper-egl-initialize-failed"
        if failure == "visual"
        else "duckstation-wrapper-launch-refused"
    ]
    assert "private_absent_settings.ini" not in json.dumps(value)


@pytest.mark.parametrize(
    "variant",
    ["unknown-message", "private-suffix", "prefix", "partial", "unframed", "echo"],
)
def test_duckstation_wrapper_private_or_incomplete_messages_stay_unmatched(
    variant: str,
) -> None:
    """A wrapper prefix alone never admits arbitrary exception text or quoted output."""
    line = (
        b"DuckStation compatibility wrapper: OpenGL launch refused: "
        b"Cannot initialize EGL on the current X11 display. "
        b"No uncorrected or renderer fallback was attempted.\n"
    )
    if variant == "unknown-message":
        line = line.replace(
            b"Cannot initialize EGL on the current X11 display",
            b"private_exception_value /private/driver.so",
        )
    elif variant == "private-suffix":
        line = line[:-1] + b" private_exception_value\n"
    elif variant == "prefix":
        line = b"private_command: " + line
    elif variant == "partial":
        line = line[:-1]
    elif variant == "echo":
        line = b"Message: " + repr(line).encode("ascii") + b"\n"
    output = line if variant == "unframed" else DUCKSTATION_STDERR_HEADER + line
    value = duckstation_startup_observation(output)
    assert value["status"] == "unmatched"
    assert value["roles"] == []
    assert "private_exception_value" not in json.dumps(value)
    assert "/private/driver.so" not in json.dumps(value)


@pytest.mark.parametrize(
    "variant",
    [
        "unframed",
        "wrong-stock-line",
        "wrong-stock-level",
        "wrong-stock-function",
        "private-command-echo",
        "logging-arguments",
        "wrong-engine-function",
        "wrong-engine-level",
        "wrong-qt-category",
        "near-miss-message",
        "following-stock-record",
        "unlogged-boot-errors",
        "wrong-sbi-function",
        "sbi-private-echo",
        "sbi-warning-near-miss",
    ],
)
def test_duckstation_startup_observation_rejects_near_misses_and_private_echoes(
    variant: str,
) -> None:
    """Source-shaped substrings and dialog-only errors are not emitted records."""
    renderer_output = DUCKSTATION_STDERR_HEADER + DUCKSTATION_RENDERER_FAILURE
    outputs = {
        "unframed": DUCKSTATION_RENDERER_FAILURE,
        "wrong-stock-line": renderer_output.replace(b":596)", b":595)"),
        "wrong-stock-level": renderer_output.replace(b" ERROR ", b" DEBUG "),
        "wrong-stock-function": renderer_output.replace(b":runCommand ", b":launch "),
        "private-command-echo": (
            DUCKSTATION_STDERR_HEADER
            + b"env: {'private_environment_value': "
            + repr(DUCKSTATION_RENDERER_FAILURE).encode("ascii")
            + b"}\n"
        ),
        "logging-arguments": (
            b"--- Logging error ---\nMessage: "
            + repr(renderer_output).encode("ascii")
            + b"\nArguments: ('private_argument_value',)\n"
        ),
        "wrong-engine-function": renderer_output.replace(
            b"E(CreateGPU):", b"E(BootSystem):"
        ),
        "wrong-engine-level": renderer_output.replace(
            b"E(CreateGPU):", b"I(CreateGPU):"
        ),
        "wrong-qt-category": (
            DUCKSTATION_STDERR_HEADER
            + DUCKSTATION_QT_DISPLAY_FAILURE.replace(
                b"qt.qpa.xcb:", b"private.qt.qpa.xcb:"
            )
        ),
        "near-miss-message": renderer_output.replace(
            b"renderer.", b"renderer recovered."
        ),
        "following-stock-record": (
            DUCKSTATION_STDERR_HEADER
            + b"private_unmatched_line\n"
            + b"2026-10-30 12:00:00,001 DEBUG (emulatorlauncher.py:595):runCommand \n"
            + DUCKSTATION_RENDERER_FAILURE
        ),
        "unlogged-boot-errors": (
            DUCKSTATION_STDERR_HEADER
            + b"Failed to boot system: Failed to open CD image 'private_disc':\n"
            + b"No BIOS image found for NTSC-U region.\n"
        ),
        "wrong-sbi-function": (
            DUCKSTATION_STDERR_HEADER
            + DUCKSTATION_SBI_WARNING.replace(b"W(CheckForSBIFile):", b"W(BootSystem):")
        ),
        "sbi-private-echo": (
            DUCKSTATION_STDERR_HEADER
            + b"Message: "
            + repr(DUCKSTATION_SBI_WARNING).encode("ascii")
            + b"\n"
        ),
        "sbi-warning-near-miss": (
            DUCKSTATION_STDERR_HEADER
            + DUCKSTATION_SBI_WARNING.replace(
                b"missing but required", b"found and not required"
            )
        ),
    }
    output = outputs[variant]
    value = duckstation_startup_observation(output)
    assert value["status"] == "unmatched"
    assert value["roles"] == []
    assert set(value) == {
        "status",
        "roles",
        "bytes_scanned",
        "lines_scanned",
        "truncated",
        "partial_line",
    }
    assert len(json.dumps(value)) < SMALL_PUBLIC_RECORD_LIMIT
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize(
    "line",
    [
        DUCKSTATION_GPU_DEVICE_FAILURE,
        b"*************** Unhandled SIGSEGV at 0x12345678 ***************\n",
        (
            b"DuckStation compatibility wrapper: OpenGL launch refused: "
            b"Cannot initialize EGL on the current X11 display. "
            b"No uncorrected or renderer fallback was attempted.\n"
        ),
        (
            b"DuckStation compatibility wrapper: launch refused. "
            b"Cannot read final generated GPU/Renderer or exec the absolute "
            b"stock emulator. No fallback was attempted.\n"
        ),
    ],
)
@pytest.mark.parametrize(
    "boundary",
    ["prelude", "wrong-record", "following-record", "partial", "line-cap", "byte-cap"],
)
def test_duckstation_failure_roles_require_complete_selected_payload(
    line: bytes, boundary: str
) -> None:
    """Emulator and wrapper failures retain the same bounded stock-record isolation."""
    if boundary == "prelude":
        output = line + DUCKSTATION_STDERR_HEADER + b"private_unmatched\n"
    elif boundary == "wrong-record":
        output = DUCKSTATION_STDERR_HEADER.replace(b":596)", b":595)") + line
    elif boundary == "following-record":
        output = (
            DUCKSTATION_STDERR_HEADER
            + b"private_unmatched\n"
            + b"2026-10-30 12:00:00,001 INFO (emulatorlauncher.py:600):runCommand "
            + line
        )
    elif boundary == "partial":
        output = DUCKSTATION_STDERR_HEADER + line[:-1]
    elif boundary == "byte-cap":
        output = DUCKSTATION_STDERR_HEADER + b"x" * 65536 + b"\n" + line
    else:
        output = DUCKSTATION_STDERR_HEADER + b"private_unmatched\n" * 256 + line
    value = duckstation_startup_observation(output)
    assert value["status"] == "unmatched"
    assert value["roles"] == []
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize(
    "line",
    [
        b"eglInitialize() failed: 12289 (0x3001)\n",
        b"Failed to load GL functions for GLAD\n",
        (
            b"E(Initialize): Failed to create GPU device: "
            b"Loading GLAD EGL functions failed\n"
        ),
        (
            b"I(CreateGPUDevice): Failed to create GPU device: "
            b"Loading GLAD EGL functions failed\n"
        ),
        b"*************** Unhandled SIGABRT at 0x12345678 ***************\n",
    ],
)
def test_duckstation_unemitted_graphics_and_crash_envelopes_stay_unmatched(
    line: bytes,
) -> None:
    """Error values and unsupported signal headers are not guessed emitted logs."""
    value = duckstation_startup_observation(DUCKSTATION_STDERR_HEADER + line)
    assert value["status"] == "unmatched"
    assert value["roles"] == []


def test_duckstation_repeated_nested_gpu_error_keeps_only_specific_role() -> None:
    """A duplicate nested failure must not fall through to generic device failure."""
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER + DUCKSTATION_GPU_DEVICE_FAILURE * 2
    )
    assert value["roles"] == ["duckstation-egl-initialize-failed"]
    expected_lines = 2
    assert value["lines_scanned"] == expected_lines


def test_duckstation_crash_frames_never_export_symbols_paths_or_module_claims() -> None:
    """Linux libbacktrace emits source filenames, not authenticated module names."""
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER
        + b"*************** Unhandled SIGSEGV at 0x12345678 ***************\n"
        + b"  0x00000012345678 private_symbol [/private/libEGL_nvidia.so:123]\n"
        + b"*******************************************************************\n"
        + b"Aborting application.\n"
    )
    assert value["roles"] == [
        "duckstation-crash-handler-sigsegv",
        "duckstation-crash-handler-aborting",
    ]
    expected_lines = 4
    assert value["lines_scanned"] == expected_lines
    public = json.dumps(value)
    assert all(
        marker not in public
        for marker in (
            "12345678",
            "private_symbol",
            "/private",
            "libEGL_nvidia",
            "123]",
        )
    )


def test_duckstation_startup_observation_matches_complete_continuation_lines_once() -> (
    None
):
    """The stock logger frames a whole stderr block, not each individual line."""
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER
        + b"private_unmatched_line\n"
        + DUCKSTATION_RENDERER_FAILURE * 3
        + DUCKSTATION_QT_DISPLAY_FAILURE
        + b"private_incomplete_value"
    )
    assert value["status"] == "matched"
    assert value["roles"] == [
        "duckstation-software-renderer-create-failed",
        "qt-xcb-display-connect-failed",
    ]
    expected_lines = 5
    assert value["lines_scanned"] == expected_lines
    assert value["partial_line"] is True
    assert value["truncated"] is False
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize("bound", ["partial", "bytes", "lines"])
def test_duckstation_startup_observation_bounds_work_and_never_matches_cut_lines(
    bound: str,
) -> None:
    """Clipped framing, capped payload lines and unterminated lines never match."""
    if bound == "partial":
        output = DUCKSTATION_STDERR_HEADER + DUCKSTATION_QT_DISPLAY_FAILURE[:-1]
    elif bound == "bytes":
        output = (
            DUCKSTATION_STDERR_HEADER
            + b"x" * 65536
            + b"\n"
            + DUCKSTATION_RENDERER_FAILURE
        )
    else:
        output = (
            DUCKSTATION_STDERR_HEADER
            + b"private_unmatched_line\n" * 256
            + DUCKSTATION_RENDERER_FAILURE
        )
    value = duckstation_startup_observation(output)
    assert value["status"] == "unmatched"
    assert value["roles"] == []
    bytes_scanned, lines_scanned = value["bytes_scanned"], value["lines_scanned"]
    assert isinstance(bytes_scanned, int)
    assert 0 <= bytes_scanned <= DIAGNOSTIC_BYTE_LIMIT
    assert isinstance(lines_scanned, int)
    assert 0 <= lines_scanned <= DIAGNOSTIC_LINE_LIMIT
    assert value["truncated"] is (bound != "partial")
    assert value["partial_line"] is (bound != "lines")
    assert len(json.dumps(value)) < SMALL_PUBLIC_RECORD_LIMIT
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize("bound", ["bytes", "lines"])
def test_duckstation_startup_observation_keeps_latest_role_with_unrelated_preamble(
    bound: str,
) -> None:
    """Configgen prelude does not consume the selected stderr payload-line budget."""
    preamble = (
        b"private_configgen_prelude\n" * 3000 + b"x" * 65536 + b"\n"
        if bound == "bytes"
        else b"private_configgen_prelude\n" * 300
    )
    value = duckstation_startup_observation(
        preamble + DUCKSTATION_STDERR_HEADER + DUCKSTATION_SBI_WARNING
    )
    assert value["status"] == "matched"
    assert value["roles"] == ["duckstation-required-sbi-missing"]
    assert value["lines_scanned"] == 1
    assert value["truncated"] is (bound == "bytes")
    assert value["partial_line"] is (bound == "bytes")
    bytes_scanned = value["bytes_scanned"]
    assert isinstance(bytes_scanned, int)
    assert 0 < bytes_scanned <= DIAGNOSTIC_BYTE_LIMIT
    assert "private_" not in json.dumps(value)


def test_duckstation_startup_observation_skips_cut_first_source_shaped_line() -> None:
    """A byte-window cut cannot manufacture a complete stock stderr envelope."""
    apparent_record = DUCKSTATION_STDERR_HEADER + DUCKSTATION_RENDERER_FAILURE
    output = b"x" * 65536 + apparent_record
    # The latest window begins within the unterminated x prefix. Its first
    # physical line includes the apparent header and must be discarded whole.
    value = duckstation_startup_observation(output)
    assert value["status"] == "unmatched"
    assert value["roles"] == []
    assert value["truncated"] is True
    assert value["partial_line"] is True
    bytes_scanned, lines_scanned = value["bytes_scanned"], value["lines_scanned"]
    assert isinstance(bytes_scanned, int)
    assert bytes_scanned <= DIAGNOSTIC_BYTE_LIMIT
    assert isinstance(lines_scanned, int)
    assert lines_scanned <= DIAGNOSTIC_LINE_LIMIT


def test_duckstation_startup_observation_keeps_prior_role_at_payload_line_cap() -> None:
    """Keep the last complete known role when the selected payload reaches its cap."""
    value = duckstation_startup_observation(
        DUCKSTATION_STDERR_HEADER
        + DUCKSTATION_SBI_WARNING
        + b"private_unmatched_line\n" * 256
    )
    assert value["roles"] == ["duckstation-required-sbi-missing"]
    assert value["lines_scanned"] == DIAGNOSTIC_LINE_LIMIT
    assert value["truncated"] is True
    assert "private_" not in json.dumps(value)


@pytest.mark.parametrize("output", [None, b""])
def test_duckstation_startup_observation_distinguishes_unavailable_from_unmatched(
    output: bytes | None,
) -> None:
    """Distinguish missing output from an available stream containing no records."""
    assert duckstation_startup_observation(output) == {
        "status": "unavailable" if output is None else "unmatched",
        "roles": [],
        "bytes_scanned": 0,
        "lines_scanned": 0,
        "truncated": False,
        "partial_line": False,
    }


@pytest.mark.parametrize(
    "variant", ["small", "limit", "oversize", "overflow", "read-error"]
)
def test_private_output_available_snapshot_is_bounded_detached_and_needs_no_eof(
    variant: str,
) -> None:
    """A real open pipe supplies a bounded snapshot, then cleanup revokes access."""
    completed = subprocess.run(  # noqa: S603  # Fixed pipe-observation fixture.
        [sys.executable, "-I", str(HELPERS / "snapshot_output.py"), variant],
        capture_output=True,
        check=False,
        timeout=8,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    value = record(json.loads(completed.stdout))
    state = record(value["state"])
    available = variant not in ("overflow", "read-error")
    assert state["available"] is available
    assert state["eof"] is False
    assert state["cancelled"] is False
    assert state["overflow"] is (variant == "overflow")
    assert state["read_failed"] is (variant == "read-error")
    assert state["truncated"] is (variant in ("oversize", "overflow"))
    expected_size = {
        "small": 73,
        "limit": 65536,
        "oversize": 23,
        "overflow": 0,
        "read-error": 0,
    }[variant]
    assert state["snapshot_bytes"] == expected_size
    assert value["data_size"] == (state["snapshot_bytes"] if available else None)
    assert value["detached"] is True
    assert value["cleared"] is True
    closed = record(value["closed"])
    assert closed["available"] is False
    assert closed["snapshot_bytes"] == 0
    assert closed["cancelled"] is True
    assert closed["retained_bytes"] == 0
    assert b"private_snapshot_value" not in completed.stdout
    assert b"late_private_value" not in completed.stdout


def assert_frozen_startup_stream(
    diagnostic: dict[str, object], variant: str, expected_size: int
) -> None:
    """Check the public diagnostic frozen while a failed launcher's pipe is open.

    Args:
        diagnostic: Private report's reduced startup observation.
        variant: Fixture stream condition at the failure boundary.
        expected_size: Payload bytes retained after unrelated prelude clipping.
    """
    assert set(diagnostic) == {"launcher_code", "private_output", "log_observation"}
    assert diagnostic["launcher_code"] is None
    stream = record(diagnostic["private_output"])
    reduced = record(diagnostic["log_observation"])
    if variant == "unavailable":
        assert stream["available"] is False
        assert reduced["status"] == "unavailable"
        assert reduced["roles"] == []
    elif variant == "withheld":
        assert stream["available"] is True
        assert stream["snapshot_bytes"] == 0
        assert stream["eof"] is False
        assert reduced["status"] == "unmatched"
        assert reduced["roles"] == []
    else:
        assert stream["available"] is True
        assert stream["snapshot_bytes"] == expected_size
        assert stream["truncated"] is (variant == "preamble")
        assert stream["eof"] is (variant == "eof")
        assert stream["cancelled"] is False
        assert stream["overflow"] is False
        assert reduced["status"] == "matched"
        assert reduced["roles"] == ["duckstation-software-renderer-create-failed"]
        assert reduced["partial_line"] is True
        assert reduced["truncated"] is False


@pytest.mark.parametrize("trigger", ["observe", "boundary"])
@pytest.mark.parametrize(
    "variant",
    ["pending", "delayed", "withheld", "preamble", "eof", "unavailable", "post-chord"],
)
def test_duckstation_failure_diagnostic_freezes_before_reader_cleanup(
    tmp_path: Path, variant: str, trigger: str
) -> None:
    """A dead pinned child cannot pass; its one reader need not finish to diagnose."""
    private_line = b"private_disc_path private_environment_value private_source_echo\n"
    preamble = (
        b"private_configgen_prelude\n" * 300 + b"x" * 65536 + b"\n"
        if variant == "preamble"
        else b""
    )
    output = (
        preamble
        + DUCKSTATION_STDERR_HEADER
        + DUCKSTATION_RENDERER_FAILURE
        + private_line
        + b"private_incomplete_value"
    )
    completed = subprocess.run(  # noqa: S603  # Fixed probe; synthetic log bytes.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_duckstation_failure.py"),
            str(tmp_path),
            variant,
            trigger,
        ],
        input=output,
        capture_output=True,
        check=False,
        timeout=12,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    observed = record(json.loads(completed.stdout))
    assert observed["failure"] == "TransitionError"
    assert observed["launcher_pending"] is True
    assert observed["forced"] is False
    final_path = tmp_path / "emulator-probe.json"
    final = record(json.loads(final_path.read_bytes()))
    assert final["status"] == "failed"
    assert "transition" not in final
    assert "termination_observation" not in final
    if variant == "post-chord":
        assert observed["before_cleanup"] is None
        assert "startup_failure_diagnostic" not in final
        return
    assert "chord" not in final
    diagnostic = record(final["startup_failure_diagnostic"])
    assert observed["before_cleanup"] == diagnostic
    if trigger == "boundary":
        assert observed["at_failure_boundary"] == diagnostic
    assert_frozen_startup_stream(diagnostic, variant, len(output) - len(preamble))
    retained_values = [final, diagnostic, observed]
    for name in ("failure", "cleanup-start", "cleanup-returned"):
        path = tmp_path / ("emulator-" + name + ".json")
        boundary = record(json.loads(path.read_bytes()))
        retained_values.append(boundary)
        assert boundary["status"] == "incomplete"
        assert record(boundary["emulator"])["live"] is False
        assert record(boundary["launcher"])["code"] is None
        assert (
            record(boundary["observations"])["startup_failure_diagnostic"] == diagnostic
        )
        assert path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    cleared = record(boundary["private_output"])
    assert cleared["cancelled"] is True
    assert cleared["retained_bytes"] == 0
    assert final_path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    for retained in retained_values:
        text = json.dumps(retained)
        assert "private_configgen_prelude" not in text
        assert all(
            marker not in text
            for marker in (
                "private_disc_path",
                "private_environment_value",
                "private_source_echo",
                "private_incomplete_value",
                "late_private_value",
                hashlib.sha256(output).hexdigest(),
                output.hex(),
            )
        )


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            (
                "RetroArch - Frontend for libretro\n"
                "Version: 1.22.2 May 29 2026\n"
                "Compiler: GCC (13.3.0) 64-bit\n"
            ),
            "1.22.2",
        ),
        ("Version: 1.23.0 Jun 1 2027\n", "1.23.0"),
        ("Compiler: GCC (13.3.0) 64-bit\nMay 29 2026\n", None),
        ("RetroArch v1.22.2\n", None),
        ("Version: \n", None),
        ("Version: 1.22 May 29 2026\n", None),
        ("Version: 1.22.2junk May 29 2026\n", None),
        ("Version: 1.22.2 May 29 2026 unexpected\n", None),
        ("diagnostic Version: 1.22.2 May 29 2026\n", None),
        (
            "Version: 1.22.2 May 29 2026\nVersion: 1.23.0 Jun 1 2027\n",
            None,
        ),
        (
            "Version: 1.22.2 May 29 2026\nVersion: 1.22.2 May 29 2026\n",
            None,
        ),
        ("Version: 1.22.2 May 29 2026\nVersion: malformed\n", None),
        ("", None),
    ],
)
def test_stock_version_metadata_is_explicit_unique_and_not_compiler_or_date(
    metadata: str, expected: str | None
) -> None:
    """Parse observed stock output without invoking RetroArch or loading a core."""
    completed = subprocess.run(  # noqa: S603  # Fixed parser; metadata is argv data.
        [sys.executable, "-I", str(HELPERS / "parse_retroarch_version.py"), metadata],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if expected is None:
        assert completed.returncode == FAILURE_EXIT, completed.stderr
        assert json.loads(completed.stdout) == {"status": "nonpassing"}
    else:
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"version": expected}


DUCKSTATION_RETAINED_STDERR = (
    'Detected locale "C" with character encoding "ANSI_X3.4-1968", '
    "which is not UTF-8.\n"
    "Qt depends on a UTF-8 locale, but has failed to switch to one.\n"
    "If this causes problems, reconfigure your locale. See the locale(1) manual\n"
    "for more information.\n"
    "DuckStation Version  ()\n"
    "https://github.com/stenzek/duckstation\n\n"
)


@pytest.mark.parametrize(
    ("metadata", "code", "expected"),
    [
        ("DuckStation Version  ()\n", 1, ("DuckStation Version  ()", "", "")),
        (
            DUCKSTATION_RETAINED_STDERR,
            1,
            ("DuckStation Version  ()", "", ""),
        ),
        (
            (
                "diagnostic before\nDuckStation Version v0.1-7294 (synthetic)\n"
                "https://github.com/stenzek/duckstation\n"
            ),
            1,
            ("DuckStation Version v0.1-7294 (synthetic)", "v0.1-7294", "synthetic"),
        ),
        ("DuckStation Version  ()\n", 0, None),
        ("DuckStation Version  ()\n", 2, None),
        ("", 1, None),
        ("Qt diagnostic\nhttps://github.com/stenzek/duckstation\n", 1, None),
        ("DuckStation Version v0.1-7294\n", 1, None),
        ("DuckStation Version  () unexpected\n", 1, None),
        ("diagnostic DuckStation Version  ()\n", 1, None),
        ("DuckStation Version  ()\nDuckStation Version  ()\n", 1, None),
        (
            "DuckStation Version  ()\nDuckStation Version v0.1-7294 (synthetic)\n",
            1,
            None,
        ),
        ("DuckStation Version  ()\nDuckStation Version malformed\n", 1, None),
        ("DuckStation Version malformed\nDuckStation Version  ()\n", 1, None),
        (" DuckStation Version  ()\n", 1, None),
        ("DuckStation Version  ()\n DuckStation Version malformed\n", 1, None),
    ],
)
def test_duckstation_reports_real_blank_scm_without_package_version_fallback(
    metadata: str, code: int, expected: tuple[str, str, str] | None
) -> None:
    """Exercise parser truth without running Qt or mistaking informational exit1."""
    completed = subprocess.run(  # noqa: S603  # Fixed parser; metadata is argv data.
        [
            sys.executable,
            "-I",
            str(HELPERS / "parse_duckstation_version.py"),
            metadata,
            str(code),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    expected_exit = 0 if expected is not None else FAILURE_EXIT
    assert completed.returncode == expected_exit, completed.stderr
    observed = record(json.loads(completed.stdout))
    if expected is not None:
        output, tag, branch = expected
        assert observed == {
            "argument": "-version",
            "exit_code": 1,
            "output": output,
            "tag": tag,
            "branch": branch,
        }
    else:
        assert observed == {"status": "nonpassing"}


@pytest.mark.parametrize(
    ("stdout", "stderr", "valid"),
    [
        ("", DUCKSTATION_RETAINED_STDERR, True),
        ("DuckStation Version  ()", "Qt diagnostic", True),
        ("DuckStation Version ", " ()\n", False),
        ("DuckStation Version  (", ")\n", False),
        ("DuckStation Version  ()", "DuckStation Version malformed\n", False),
        ("DuckStation Version  ()", "DuckStation Version  ()\n", False),
    ],
)
def test_duckstation_identity_keeps_stream_boundaries_and_only_safe_metadata(
    stdout: str, stderr: str, *, valid: bool
) -> None:
    """Preserve stream boundaries and safe metadata through the identity caller."""
    completed = subprocess.run(  # noqa: S603  # Fixed identity-observation fixture.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_duckstation_identity.py"),
            stdout,
            stderr,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == (0 if valid else FAILURE_EXIT), completed.stderr
    observed = record(json.loads(completed.stdout))
    if valid:
        assert observed["variant"] == "duckstation-qt"
        assert observed["executable"] == "/usr/bin/duckstation-qt"
        assert observed["executable_sha256"] == "a" * 64
        assert observed["reported_version"] == {
            "argument": "-version",
            "exit_code": 1,
            "output": "DuckStation Version  ()",
            "tag": "",
            "branch": "",
        }
        assert isinstance(observed["package_source"], dict)
        assert "Qt" not in completed.stdout
        assert "ANSI_X3.4" not in completed.stdout
    else:
        assert observed == {"status": "nonpassing"}


def discover(
    tmp_path: Path,
    polls: list[list[str | None]],
    *,
    metadata: bytes | None = None,
    node: str = "/dev/null",
) -> dict[str, object]:
    """Observe real device and metadata identities through the installed probe.

    Args:
        tmp_path: Owned directory in which this helper creates private metadata.
        polls: Ordered synthetic SDL path observations, one list per poll.
        metadata: Optional udev bytes for the real /dev/null device identity.
        node: Existing character node whose identity the probe should inspect.

    Returns:
        Discovery matches and privacy-reduced SDL and device evidence.
    """
    data = tmp_path / "udev-data"
    data.mkdir()
    device = Path("/dev/null").stat().st_rdev
    if metadata is not None:
        (data / f"c{os.major(device)}:{os.minor(device)}").write_bytes(metadata)
    return observe_discovery(data, polls, node=node)


def observe_discovery(
    data: Path, polls: list[list[str | None]], *, node: str = "/dev/null"
) -> dict[str, object]:
    """Invoke discovery without creating or altering its device and metadata inputs.

    Args:
        data: Directory containing synthetic app-local udev records.
        polls: Ordered SDL path observations to feed to the actual observer.
        node: Existing character node to compare with the expected device.

    Returns:
        Public matches and bounded first and latest discovery evidence.
    """
    completed = subprocess.run(  # noqa: S603  # Fixed observer; owned metadata.
        [
            sys.executable,
            "-I",
            str(HELPERS / "discover_input.py"),
            json.dumps(
                {"paths": [], "polls": polls, "node": node, "udev_data": str(data)}
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return record(json.loads(completed.stdout))


def test_forwarded_readable_device_without_metadata_is_not_sdl_discovery(
    tmp_path: Path,
) -> None:
    """Require actual SDL discovery even when the event node itself is readable."""
    value = discover(tmp_path, [[], ["/dev/zero", None], ["/dev/null"]])
    assert value["matches"] == [None, None, 1]
    device = record(value["device"])
    assert device["node"] == {"status": "opened", "identity_matches": True}
    assert device["udev"] == {"status": "missing"}
    sdl = record(value["sdl"])
    expected_polls = 3
    assert sdl["polls"] == expected_polls
    assert record(sdl["first"])["joysticks"] == 0
    assert record(sdl["latest"])["matching_index"] == 0
    assert "private SDL diagnostic" not in json.dumps(value)


def test_discovery_failure_keeps_only_bounded_first_and_latest_observations(
    tmp_path: Path,
) -> None:
    """Retain bounded first and latest discovery evidence without exporting paths."""
    missing = str(tmp_path / "private-path-must-not-be-exported")
    polls: list[list[str | None]] = [[None]] * 250
    polls.append([missing])
    value = discover(tmp_path, polls)
    assert value["matches"] == [None] * 250 + ["os-error"]
    evidence = record(value["sdl"])
    assert evidence["polls"] == len(polls)
    assert set(evidence) == {"polls", "first", "latest"}
    assert record(evidence["first"])["pathless"] == 1
    assert record(evidence["latest"])["path_stat_errno"] == errno.ENOENT
    assert "private-path" not in json.dumps(value)
    assert len(json.dumps(evidence)) < PUBLIC_RECORD_LIMIT


def test_udev_observation_exports_only_exact_classification_flags(
    tmp_path: Path,
) -> None:
    """Export only fixed udev classifications, never arbitrary property values."""
    value = discover(
        tmp_path,
        [[]],
        metadata=(
            b"E:ID_INPUT=1\nE:ID_INPUT_JOYSTICK=1\n"
            b"E:ID_INPUT_KEY=private-value\nE:PRIVATE=private-value\n"
            b"E:ID_CLASS=joystick\n"
        ),
    )
    metadata = record(record(value["device"])["udev"])
    assert metadata["status"] == "read"
    properties = record(metadata["properties"])
    assert properties["ID_INPUT"] == "1"
    assert properties["ID_INPUT_JOYSTICK"] == "1"
    assert properties["ID_INPUT_KEY"] == "other"
    assert properties["ID_INPUT_KEYBOARD"] == "absent"
    assert properties["ID_CLASS"] == "joystick"
    assert value["matches"] == [None]
    assert "private-value" not in json.dumps(value)


@pytest.mark.parametrize("failure", ["oversize", "duplicate", "symlink", "wrong-node"])
def test_metadata_and_node_observations_do_not_authorize_a_discovery_match(
    tmp_path: Path, failure: str
) -> None:
    """Keep unsafe metadata and mismatched node identities from authorizing input."""
    metadata = {
        "oversize": b"E:ID_INPUT_JOYSTICK=1\n" + b"x" * 4096,
        "duplicate": b"E:ID_INPUT_JOYSTICK=1\nE:ID_INPUT_JOYSTICK=1\n",
        "symlink": b"E:ID_INPUT_JOYSTICK=1\n",
        "wrong-node": b"E:ID_INPUT_JOYSTICK=1\n",
    }[failure]
    value = discover(
        tmp_path,
        [[]],
        metadata=metadata,
        node="/dev/zero" if failure == "wrong-node" else "/dev/null",
    )
    device = record(value["device"])
    if failure == "oversize":
        assert device["udev"] == {"status": "oversize"}
    elif failure == "duplicate":
        properties = record(record(device["udev"])["properties"])
        assert properties["ID_INPUT_JOYSTICK"] == "ambiguous"
    elif failure == "wrong-node":
        assert record(device["node"])["identity_matches"] is False
    else:
        data = tmp_path / "udev-data"
        identifier = Path("/dev/null").stat().st_rdev
        path = data / f"c{os.major(identifier)}:{os.minor(identifier)}"
        target = tmp_path / "private-foreign-record"
        path.rename(target)
        path.symlink_to(target)
        observed = observe_discovery(data, [[]])
        assert record(record(observed["device"])["udev"])["status"] == "unavailable"
        assert target.read_bytes() == metadata
        assert path.is_symlink()
    assert value["matches"] == [None]


@pytest.mark.parametrize("candidate", ["actual", "other", "symlink"])
def test_function_mapping_not_version_or_filename_establishes_loaded_provenance(
    tmp_path: Path, candidate: str
) -> None:
    """An actual loaded C function must map the hashed file, not a lookalike."""
    other = tmp_path / "libc.so.6"
    other.write_bytes(b"private lookalike library")
    if candidate == "symlink":
        link = tmp_path / "alias.so"
        link.symlink_to(other)
        other = link
    completed = subprocess.run(  # noqa: S603  # Fixed native-library observer.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_loaded_library.py"),
            candidate,
            str(other),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    value = record(json.loads(completed.stdout))
    observed = record(value["observation"])
    if candidate == "actual":
        assert observed["status"] == "mapped"
        assert observed["sha256"] == value["actual_sha256"]
    else:
        assert observed["status"] == (
            "unavailable" if candidate == "symlink" else "different-object"
        )
        assert "sha256" not in observed
    assert "private" not in completed.stdout
    assert str(tmp_path) not in completed.stdout


def test_stock_discovery_log_observer_is_bounded_private_and_restores_logger() -> None:
    """Real SDL logging distinguishes category/priority and restores borrowed state."""
    completed = subprocess.run(  # noqa: S603  # Fixed host SDL logging fixture.
        [sys.executable, "-I", str(HELPERS / "observe_sdl_log.py")],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode == PREREQUISITE_SKIP_EXIT:
        pytest.skip("Host SDL shared library is unavailable")
    assert completed.returncode == 0, completed.stderr
    value = record(json.loads(completed.stdout))
    assert value["observed"] == {"udev_selected": True}
    assert value["forwarded"] == [[7, 5], [0, 2]]
    assert value["restored"] is True
    assert value["priority"] == SDL_LOG_PRIORITY_CRITICAL
    assert "private" not in completed.stdout
    assert len(completed.stdout) < SMALL_PUBLIC_RECORD_LIMIT


XEMU_METADATA = (
    "xemu_version: 0.8.134\n"
    "xemu_commit: fc9980d2962cbec656253106ea2e121fab1e68d4\n"
    "xemu_date: Fri May 29 06:08:30 AM UTC 2026\n"
)


@pytest.mark.parametrize(
    ("output", "code", "valid"),
    [
        (XEMU_METADATA, 0, True),
        (
            "SDL diagnostic\n" + XEMU_METADATA + "QEMU emulator version 10.0.2\n",
            0,
            True,
        ),
        (XEMU_METADATA, 1, False),
        ("QEMU emulator version 10.0.2\n", 0, False),
        ("", 0, False),
        (XEMU_METADATA.replace("0.8.134", "v0.8.134"), 0, False),
        (
            XEMU_METADATA.replace(
                # pragma: allowlist nextline secret
                "fc9980d2962cbec656253106ea2e121fab1e68d4",
                "unknown",
            ),
            0,
            False,
        ),
        (XEMU_METADATA.replace("Fri May", "private date"), 0, False),
        (XEMU_METADATA + "xemu_version: 0.8.134\n", 0, False),
        (XEMU_METADATA + "xemu_commit: malformed\n", 0, False),
        (" " + XEMU_METADATA, 0, False),
        ("private prefix " + XEMU_METADATA, 0, False),
        (XEMU_METADATA + "xemu_date: malformed\n", 0, False),
        ("x" * 65536 + "\n" + XEMU_METADATA, 0, False),
    ],
)
def test_xemu_metadata_requires_successful_unique_bounded_runtime_records(
    output: str, code: int, *, valid: bool
) -> None:
    """The real headless identity records are not a successful helper observation."""
    completed = subprocess.run(  # noqa: S603  # Fixed parser; metadata is argv data.
        [
            sys.executable,
            "-I",
            str(HELPERS / "parse_xemu_version.py"),
            output,
            str(code),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    observed = record(json.loads(completed.stdout))
    if valid:
        assert completed.returncode == 0
        assert observed == {
            "argument": "-version",
            "exit_code": 0,
            "disposable_config": True,
            "version": "0.8.134",
            # pragma: allowlist nextline secret
            "revision": "fc9980d2962cbec656253106ea2e121fab1e68d4",
            "date": "Fri May 29 06:08:30 AM UTC 2026",
        }
    else:
        assert completed.returncode == FAILURE_EXIT
        assert observed == {"status": "nonpassing"}


def test_xemu_packaged_selection_preserves_private_disc_and_absence(
    tmp_path: Path,
    stock_catalog: Path,
) -> None:
    """Real stock-format selection/reproduction never asserts boot or guest input."""
    library = tmp_path / "library"
    folder = library / "xbox"
    folder.mkdir(parents=True)
    (folder / "default.xbe").write_bytes(b"Not a supported stock launch format")
    code, value = select(
        tmp_path / "absent",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case="xbox-xemu",
    )
    assert code == 0
    assert value["selected"] is False
    assert record(value["report"])["status"] == "skipped-no-media"
    media = folder / "selected.iso"
    media.write_bytes(b"Synthetic selection bytes, not an XISO or native proof")
    code, value = select(
        tmp_path / "first",
        library,
        tmp_path / "no-record",
        catalog=stock_catalog,
        case="xbox-xemu",
    )
    assert code == 0
    assert value["selected"] is True
    report = record(value["report"])
    assert report["case"] == "xbox-xemu"
    assert report["backend"] == "xemu"
    assert report["status"] == "failed"
    assert "selected.iso" not in json.dumps(report)
    selection = tmp_path / "first/selection.json"
    code, value = select(
        tmp_path / "second",
        library,
        selection,
        catalog=stock_catalog,
        required=True,
        case="xbox-xemu",
    )
    assert code == 0
    assert value["selected"] is True
    assert (tmp_path / "second/selection.json").read_bytes() == selection.read_bytes()
    media.write_bytes(b"Changed content must not be rerolled")
    code, value = select(
        tmp_path / "changed",
        library,
        selection,
        catalog=stock_catalog,
        required=True,
        case="xbox-xemu",
    )
    assert code == FAILURE_EXIT
    assert value["failure"] == "MediaError"


@pytest.mark.parametrize(
    "condition",
    [
        "missing-seed",
        "wrong-seed",
        "symlink-save",
        "existing-hdd",
        "existing-eeprom",
        "existing-config",
    ],
)
def test_xemu_hdd_refuses_unqualified_inputs_and_existing_or_escaped_state(
    tmp_path: Path, condition: str
) -> None:
    """Actual filesystem refusals preserve foreign state and never seed from it."""
    userdata = tmp_path / "userdata"
    occupied: Path | None = None
    userdata.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    sentinel = foreign / "keep"
    sentinel.write_bytes(b"Unrelated state must survive")
    seed = tmp_path / "seed.qcow2"
    if condition != "missing-seed":
        seed.write_bytes(b"Unqualified seed")
    if condition == "symlink-save":
        (userdata / "saves").symlink_to(foreign, target_is_directory=True)
    elif condition in ("existing-hdd", "existing-eeprom", "existing-config"):
        relative = {
            "existing-hdd": "saves/xbox/xbox_hdd.qcow2",
            "existing-eeprom": "saves/xbox/xemu_eeprom.bin",
            "existing-config": "system/configs/xemu/xemu.toml",
        }[condition]
        occupied = userdata / relative
        occupied.parent.mkdir(parents=True)
        occupied.write_bytes(b"Preexisting state must not be overwritten")
    original_seed = seed.read_bytes() if seed.exists() else None
    completed = subprocess.run(  # noqa: S603  # Fixed probe; owned userdata and seed.
        [
            sys.executable,
            "-I",
            str(HELPERS / "prepare_xemu_hdd.py"),
            str(userdata),
            str(seed),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == FAILURE_EXIT
    assert "failure" in record(json.loads(completed.stdout))
    assert sentinel.read_bytes() == b"Unrelated state must survive"
    if original_seed is not None:
        assert seed.read_bytes() == original_seed
    if occupied is not None:
        assert occupied.read_bytes() == b"Preexisting state must not be overwritten"
    else:
        assert not (userdata / "saves/xbox/xbox_hdd.qcow2").exists()


def standalone_launch(directory: Path, case: str, loss: str) -> dict[str, object]:
    """Exercise real process lifetime evidence with controlled native boundaries.

    Args:
        directory: Owned directory for synthetic selected media and evidence.
        case: Public standalone emulator case to exercise.
        loss: Fixture-controlled readiness loss, exit race or identity failure.

    Returns:
        Lifecycle transition or failure, process identity and chord evidence.
    """
    environment = os.environ.copy()
    environment.pop("GOW_NATIVE_LEASE", None)
    completed = subprocess.run(  # noqa: S603  # Fixed lifecycle; owned child state.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_standalone_launch.py"),
            str(directory),
            case,
            loss,
        ],
        env=environment,
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    return record(json.loads(completed.stdout))


@pytest.mark.parametrize("case", ["psx-duckstation", "xbox-xemu"])
def test_standalone_launch_evidence_survives_live_child_shutdown(
    tmp_path: Path, case: str
) -> None:
    """Host FD/output transitions are not native rendering or gamepad proof."""
    observed = standalone_launch(tmp_path, case, "shutdown")
    transition = record(observed["transition"])
    display = record(transition["stock_launch_display"])
    assert observed["failure"] is None
    assert display["selected_disc_open"] is True
    assert display["render_window"] is True
    assert display["non_dialog"] is True
    latest_display = record(observed["latest_display"])
    assert latest_display["selected_disc_open"] is False
    assert latest_display["render_window"] is False
    stage = record(observed["stage"])
    assert stage["shutdown_live"] is True
    assert stage["pressed"] is True
    assert stage["released"] is True
    assert record(observed["chord"])["released"] is True
    assert transition["emulator"] == observed["identity"]
    assert transition["same_emulator_exited"] is True
    assert transition["launcher_code"] == 0
    assert observed["child_code"] == 0
    assert observed["forced"] is False
    # This successful host shortcut has no startup exception diagnostic. Its
    # absence cannot become another veto on the required transition evidence.
    assert observed["launch_failure_diagnostic"] is None
    assert (
        (tmp_path / "emulator-before-exit.png")
        .read_bytes()
        .startswith(b"\x89PNG\r\n\x1a\n")
    )


@pytest.mark.parametrize("case", ["psx-duckstation", "xbox-xemu"])
@pytest.mark.parametrize(
    "loss", ["interval-disc", "interval-window", "capture-disc", "capture-window"]
)
def test_standalone_prechord_readiness_loss_never_injects(
    tmp_path: Path, case: str, loss: str
) -> None:
    """Refuse native input when selected-disc or render-window readiness is lost."""
    observed = standalone_launch(tmp_path, case, loss)
    assert observed["transition"] is None
    assert observed["failure"] == "TransitionError"
    assert observed["chord"] is None
    assert observed["child_code"] is None
    assert observed["forced"] is False
    stage = record(observed["stage"])
    assert stage["lost"] is True
    assert stage["pressed"] is False


@pytest.mark.parametrize("loss", ["race-zombie", "race-reaped"])
def test_pinned_exit_between_pidfd_sample_and_proc_stat_survives(
    tmp_path: Path, loss: str
) -> None:
    """Actual child death, not a mocked missing PID, must complete the transition."""
    observed = standalone_launch(tmp_path, "xbox-xemu", loss)
    stage = record(observed["stage"])
    assert stage["pidfd_live_before_stat"] is True
    assert stage["pidfd_live_after_exit"] is False
    assert stage["actual_stat_error"] == (
        "ProcessLookupError" if loss == "race-zombie" else "FileNotFoundError"
    )
    assert stage["actual_stat_errno"] == (
        None if loss == "race-zombie" else errno.ENOENT
    )
    assert observed["failure"] is None
    assert observed["process_failure"] is None
    transition = record(observed["transition"])
    assert transition["emulator"] == observed["identity"]
    assert transition["same_emulator_exited"] is True
    assert transition["launcher_code"] == 0
    assert observed["child_code"] == 0
    assert transition["forced_teardown"] is False
    assert observed["forced"] is False
    assert record(observed["chord"])["released"] is True
    termination = record(
        record(json.loads((tmp_path / "emulator-launcher-exit.json").read_bytes()))[
            "observations"
        ]
    )
    assert record(termination["termination_observation"])["emulator"] == {
        **record(observed["identity"]),
        "live": False,
    }


@pytest.mark.parametrize(
    ("loss", "failure", "error_number"),
    [
        ("stat-missing-live", "FileNotFoundError", errno.ENOENT),
        ("stat-lookup-live", "ProcessLookupError", None),
        ("stat-denied", "PermissionError", errno.EACCES),
        ("stat-denied-after-exit", "PermissionError", errno.EACCES),
        ("wrong-start", "ProbeError", None),
        ("wrong-pid", "TransitionError", None),
        ("pre-chord-death", "TransitionError", None),
        ("launcher-error", "TransitionError", None),
        ("forced-teardown", "TransitionError", None),
    ],
)
def test_proc_race_recovery_preserves_identity_errors_and_exit_gates(
    tmp_path: Path, loss: str, failure: str, error_number: int | None
) -> None:
    """A live pidfd, unrelated error or rejected lifecycle never becomes exit proof."""
    observed = standalone_launch(tmp_path, "xbox-xemu", loss)
    assert observed["transition"] is None
    assert observed["failure"] == failure
    assert observed["failure_errno"] == error_number
    if loss.startswith("stat-"):
        attribution = record(observed["process_failure"])
        assert attribution["role"] == "emulator"
        assert attribution["pid"] == record(observed["identity"])["pid"]
        assert attribution["expected_start"] == record(observed["identity"])["start"]
        assert attribution["errno"] == error_number
        assert attribution["pidfd_live"] is (loss != "stat-denied-after-exit")
        assert attribution["proc_state"] in (
            ("Z",) if loss == "stat-denied-after-exit" else ("R", "S")
        )
    if loss == "pre-chord-death":
        assert observed["chord"] is None
    if loss == "launcher-error":
        assert observed["child_code"] == FAILURE_EXIT
    if loss == "forced-teardown":
        assert observed["forced"] is True


def test_zombie_leader_waits_for_real_thread_group_completion(tmp_path: Path) -> None:
    """A real exited main thread is not process death while its worker is held."""
    observed = standalone_launch(tmp_path, "xbox-xemu", "thread-completes")
    stage = record(observed["stage"])
    zombie = record(stage["zombie"])
    assert zombie["state"] == "Z"
    assert zombie["pidfd_live"] is True
    tasks = zombie["tasks"]
    assert isinstance(tasks, int)
    assert tasks >= MIN_THREAD_GROUP_TASKS
    assert zombie["start"] == record(observed["identity"])["start"]
    assert zombie["launcher_code"] is None
    assert stage["waiting_polls"] == SHUTDOWN_WAIT_POLLS
    assert stage["waiting_live"] is True
    assert stage["premature_termination"] is False
    assert (
        stage["live_group_observations"] == [{"alive": True, "launcher_code": None}] * 4
    )
    assert observed["failure"] is None
    assert observed["process_failure"] is None
    transition = record(observed["transition"])
    assert transition["emulator"] == observed["identity"]
    assert transition["same_emulator_exited"] is True
    assert transition["launcher_code"] == 0
    assert observed["child_code"] == 0
    assert transition["forced_teardown"] is False
    assert observed["forced"] is False
    assert record(observed["chord"])["pressed"] is True
    assert record(observed["chord"])["released"] is True


@pytest.mark.parametrize(
    ("loss", "failure"),
    [
        ("thread-pre-chord", "ProcessLookupError"),
        ("thread-incomplete-press", "ProcessLookupError"),
        ("thread-incomplete-release", "ProcessLookupError"),
        ("thread-wrong-identity", "ProbeError"),
        ("thread-stat-denied", "PermissionError"),
        ("thread-metadata-denied", "PermissionError"),
        ("thread-metadata-missing", "FileNotFoundError"),
        ("thread-metadata-wrong-pid", "ProbeError"),
        ("thread-metadata-wrong-start", "ProbeError"),
        ("thread-metadata-not-zombie", "ProcessLookupError"),
        ("thread-metadata-malformed", "ProbeError"),
        ("thread-metadata-oversized", "ProbeError"),
        ("thread-timeout", "TransitionError"),
        ("thread-lease-loss", "RuntimeError"),
        ("thread-launcher-error", "TransitionError"),
    ],
)
def test_zombie_leader_recovery_preserves_failure_barriers(
    tmp_path: Path, loss: str, failure: str
) -> None:
    """Actual live workers cannot waive identity, metadata, chord or exit gates."""
    observed = standalone_launch(tmp_path, "xbox-xemu", loss)
    assert observed["transition"] is None
    assert observed["failure"] == failure
    stage = record(observed["stage"])
    zombie = record(stage["zombie"])
    assert zombie["state"] == "Z"
    assert zombie["pidfd_live"] is True
    assert zombie["start"] == record(observed["identity"])["start"]
    if loss == "thread-pre-chord":
        assert observed["chord"] is None
    elif loss == "thread-incomplete-release":
        assert record(observed["chord"])["released"] is False
    else:
        assert record(observed["chord"])["released"] is True
    if loss == "thread-incomplete-press":
        assert record(observed["chord"])["pressed"] is False
    if loss == "thread-timeout":
        assert observed["child_code"] is None
        waiting_polls = stage["waiting_polls"]
        assert isinstance(waiting_polls, int)
        assert waiting_polls >= SHUTDOWN_WAIT_POLLS
        assert stage["waiting_live"] is True
        assert stage["premature_termination"] is False
    elif loss == "thread-lease-loss":
        assert stage["waiting_polls"] == LEASE_FAILURE_POLL
        assert stage["waiting_live"] is True
        assert observed["child_code"] is None
        assert stage["premature_termination"] is False
    if loss in ("thread-timeout", "thread-lease-loss"):
        rows = stage["live_group_observations"]
        assert isinstance(rows, list)
        assert len(rows) >= MIN_THREAD_GROUP_TASKS
        assert all(row == {"alive": True, "launcher_code": None} for row in rows)
    elif loss == "thread-launcher-error":
        assert observed["child_code"] == FAILURE_EXIT
    else:
        attribution = record(observed["process_failure"])
        assert attribution["role"] == "emulator"
        assert attribution["pidfd_live"] is True
        assert attribution["proc_state"] == "Z"
    assert observed["forced"] is False


@pytest.mark.parametrize("state", ["zombie", "reaped", "thread-zombie"])
def test_final_source_loss_stays_failed_when_the_emulator_is_live(
    tmp_path: Path, state: str
) -> None:
    """Final-source death or a zombie leader still fails, even after the chord."""
    completed = subprocess.run(  # noqa: S603  # Fixed process-lifetime fixture.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_final_source_loss.py"),
            str(tmp_path),
            state,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    observed = record(json.loads(completed.stdout))
    assert observed["failure"] == (
        "FileNotFoundError" if state == "reaped" else "ProcessLookupError"
    )
    assert observed["emulator_live"] is True
    assert observed["termination"] is None
    attribution = record(observed["process_failure"])
    source = record(observed["source"])
    assert attribution["role"] == "final-source"
    assert attribution["pid"] == source["pid"]
    assert attribution["expected_start"] == source["start"]
    assert attribution["pidfd_live"] is (state == "thread-zombie")
    assert attribution["proc_state"] == ("unavailable" if state == "reaped" else "Z")
    assert attribution["current_start"] == (
        None if state == "reaped" else source["start"]
    )
    if state == "thread-zombie":
        tasks = observed["source_tasks"]
        assert isinstance(tasks, int)
        assert tasks >= MIN_THREAD_GROUP_TASKS


@pytest.mark.parametrize(
    ("renderer", "mode", "accepted"),
    [
        ("OpenGL", "normal", True),
        ("Vulkan", "normal", True),
        ("OpenGL", "missing-visual", False),
        ("Vulkan", "vulkan-visual", False),
        ("OpenGL", "duplicate-visual", False),
        ("OpenGL", "bad-visual", False),
        ("OpenGL", "extra-arg", False),
    ],
)
def test_native_pin_waits_for_stock_elf_and_keeps_exact_qt_argument_gate(
    tmp_path: Path,
    renderer: str,
    mode: str,
    *,
    accepted: bool,
) -> None:
    """Wait through wrapper exec and accept only the selected stock Qt argument set."""
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("Native identity control requires a host C compiler")
    executable = tmp_path / "duckstation-qt"
    source = tmp_path / "consumer.c"
    source.write_text(
        "#include <stdio.h>\n#include <unistd.h>\n"
        'int main(void) { puts("elf"); fflush(stdout); char c; '
        "return read(0, &c, 1) < 0; }\n",
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603  # Resolved host compiler; owned synthetic source.
        [compiler, str(source), "-o", str(executable)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    wrapper = tmp_path / "wrapper" / "duckstation-qt"
    wrapper.parent.mkdir()
    wrapper.write_text(
        "#!"
        + sys.executable
        + "\n"
        + (HELPERS / "consumer_interpreter_wrapper.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    completed = subprocess.run(  # noqa: S603  # Fixed observer; owned compiled ELF.
        [
            sys.executable,
            "-I",
            str(HELPERS / "pin_wrapper.py"),
            str(executable),
            str(wrapper),
            renderer,
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert record(json.loads(completed.stdout))["pinned"] is accepted


@pytest.mark.parametrize("renderer", ["OpenGL", "Vulkan"])
@pytest.mark.parametrize(
    "mode", ["normal", "unopened", "wrong-selected", "wrong-active", "symlink"]
)
def test_native_renderer_observation_requires_generated_mode_and_pinned_open_log(
    tmp_path: Path,
    renderer: str,
    mode: str,
) -> None:
    """Bind renderer evidence to generated settings and the emulator's open log."""
    other = "OpenGL" if renderer == "Vulkan" else "Vulkan"
    selected = other if mode == "wrong-selected" else renderer
    active = other if mode == "wrong-active" else renderer
    (tmp_path / "settings.ini").write_text(
        "[GPU]\nRenderer=" + selected + "\n", encoding="utf-8"
    )
    log = "[    0.0100] I/Host: Trying to create a " + active + " GPU device...\n"
    if active == "OpenGL":
        log += "[    0.0200] I/OpenGLContext: Created an OpenGL context\n"
    log += "[    0.0300] I/GPU_HW: Created HW framebuffer of 1024x512\n"
    log += "[    0.0400] I/System: private-media-marker-and-path\n"
    (tmp_path / "other.log").write_text(log, encoding="utf-8")
    if mode == "symlink":
        (tmp_path / "duckstation.log").symlink_to(tmp_path / "other.log")
    else:
        (tmp_path / "duckstation.log").write_text(log, encoding="utf-8")
    completed = subprocess.run(  # noqa: S603  # Fixed observer; owned log/settings.
        [
            sys.executable,
            "-I",
            str(HELPERS / "observe_renderer.py"),
            str(tmp_path),
            mode,
            renderer,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    observed = record(json.loads(completed.stdout))
    assert observed["passed"] is (mode == "normal")
    assert "private-media-marker" not in json.dumps(observed)
    if mode == "normal":
        assert observed["empty_alive"] is True
        assert record(observed["renderer"])["active"] == renderer
