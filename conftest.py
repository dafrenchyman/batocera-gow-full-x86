"""Bind coverage receipts to successful pytest and lossless real combination."""

import hashlib
import json
import os
import runpy
import sqlite3
import tempfile
import time
from collections.abc import Callable, Generator, Iterable
from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

import coverage.control
import pytest
from coverage import CoverageData
from coverage.data import combinable_files, combine_parallel_data
from coverage.exceptions import CoverageException
from coverage.files import PathAliases
from coverage.sqldata import SCHEMA_VERSION

_ROOT = Path(__file__).resolve().parent
_RECEIPT_VERSION = 2
_STARTED = pytest.StashKey[int]()
_INPUTS = pytest.StashKey[dict[str, str]]()
_EVIDENCE = pytest.StashKey[Path]()
_COMBINATION = pytest.StashKey["Combination"]()
_PATCH = pytest.StashKey[pytest.MonkeyPatch]()


@dataclass
class Combination:
    """Retain counts and failure state, never filenames or warning payloads."""

    calls: int = 0
    completed: int = 0
    fragments: int = 0
    validated: int = 0
    complete: bool = True


def digest(path: Path) -> str:
    """Hash a report or data file without importing application source."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_identity(root: Path) -> dict[str, str]:
    """Load canonical tooling without sys.path changes or a measured child process.

    The checker is an executable repository script, not an installed application
    module. Console pytest's importlib mode need not put the repository on its
    import path. Execute that exact tool with its CLI main guard inactive.
    """
    namespace = runpy.run_path(str(root / "scripts/check_python_coverage.py"))
    snapshot = namespace["input_identity"]
    if not callable(snapshot):
        message = "Coverage input snapshot is not callable."
        raise TypeError(message)
    value: object = snapshot(root)
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        message = "Coverage input snapshot must map relative paths to hashes."
        raise TypeError(message)
    return dict(value)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Select receipt output; COVERAGE_FILE and the JSON report must agree."""
    parser.addoption(
        "--coverage-evidence-dir",
        type=Path,
        help="Private receipt directory, paired with COVERAGE_FILE and JSON report.",
    )


def contribution_survives(expected: CoverageData, actual: CoverageData) -> bool:
    """Require every admitted file, line and branch from the combination inputs."""
    if not expected.measured_files() <= actual.measured_files():
        return False
    if not expected.measured_contexts() <= actual.measured_contexts():
        return False
    return all(
        set(expected.arcs(name) or []) <= set(actual.arcs(name) or [])
        and set(expected.lines(name) or []) <= set(actual.lines(name) or [])
        for name in expected.measured_files()
    )


@contextmanager
def include_fragment(
    expected: CoverageData, path: Path, aliases: PathAliases | None
) -> Generator[tuple[str, str]]:
    """Audit and retain the exact private bytes that the real combine may consume.

    CoverageData.read may initialize an empty SQLite database. Require its actual
    schema first through immutable read-only SQLite, then let Coverage interpret
    only the disposable copy. The caller keeps that 0600 snapshot alive until
    combination finishes. Original paths are never passed to Coverage.
    """
    with tempfile.NamedTemporaryFile() as snapshot:
        contents = path.read_bytes()
        snapshot.write(contents)
        snapshot.flush()
        uri = Path(snapshot.name).as_uri() + "?mode=ro&immutable=1"
        with closing(sqlite3.connect(uri, uri=True)) as database:
            if database.execute("SELECT version FROM coverage_schema").fetchall() != [
                (SCHEMA_VERSION,)
            ]:
                message = "Invalid contributing coverage schema."
                raise CoverageException(message)
        fragment = CoverageData(snapshot.name)
        try:
            fragment.read()
            if not fragment.has_arcs():
                message = "Contributing coverage must retain branch measurement."
                raise CoverageException(message)
            expected.update(fragment, map_path=aliases.map if aliases else None)
        finally:
            fragment.close(force=True)
        yield snapshot.name, hashlib.sha256(contents).hexdigest()


def retire_fragments(audited: dict[Path, tuple[str, str]], *, keep: bool) -> bool:
    """Refuse changed originals before deleting any successfully combined inputs."""
    if any(digest(path) != fingerprint for path, (_, fingerprint) in audited.items()):
        return False
    if not keep:
        for path in audited:
            path.unlink()
    return True


def observe_combination(config: pytest.Config, data_path: Path) -> None:
    """Observe Coverage 7.17's actual combine routine, including swallowed loss.

    pytest-cov 7.1 finishes in pytest_runtestloop, not sessionfinish. Coverage's
    routine warns and skips unreadable files, and deduplicates by filename hash.
    Independently audit every candidate and pass only retained byte snapshots to
    that routine, then reconcile its mapped contribution. Refuse changed originals
    before removal. New paths remain untouched for the final completeness check.
    """
    state = Combination()
    config.stash[_COMBINATION] = state
    original = combine_parallel_data

    # Coverage 7.17 calls this adapter with its six defined API parameters.
    def combine(  # noqa: PLR0913
        data: CoverageData,
        *,
        aliases: PathAliases | None = None,
        data_paths: Iterable[str] | None = None,
        strict: bool = False,
        keep: bool = False,
        message: Callable[[str], None] | None = None,
    ) -> None:
        if Path(data.base_filename()).resolve() != data_path:
            original(
                data,
                aliases=aliases,
                data_paths=data_paths,
                strict=strict,
                keep=keep,
                message=message,
            )
            return
        state.calls += 1
        paths = list(data_paths) if data_paths is not None else None
        expected = CoverageData(no_disk=True)
        candidates = combinable_files(data.base_filename(), paths)
        with ExitStack() as snapshots:
            audited: dict[Path, tuple[str, str]] = {}
            for name in candidates:
                if name == data.data_filename():
                    continue
                state.fragments += 1
                path = Path(name)
                try:
                    audited[path] = snapshots.enter_context(
                        include_fragment(expected, path, aliases)
                    )
                    if path.stat().st_mtime_ns < config.stash[_STARTED]:
                        state.complete = False
                    state.validated += 1
                except (OSError, sqlite3.DatabaseError, CoverageException):
                    state.complete = False
            # An empty explicit list would make Coverage enumerate directories again.
            if not audited:
                state.complete = False
            if not state.complete:
                failure = (
                    "Coverage contribution audit failed; measurement is incomplete."
                )
                raise pytest.UsageError(failure)
            try:
                original(
                    data,
                    aliases=aliases,
                    data_paths=[snapshot for snapshot, _ in audited.values()],
                    strict=strict,
                    keep=True,
                    message=message,
                )
                state.completed += 1
                state.complete = contribution_survives(
                    expected, data
                ) and retire_fragments(audited, keep=keep)
            except (OSError, CoverageException):
                state.complete = False
                raise

    patch = pytest.MonkeyPatch()
    patch.setattr(coverage.control, "combine_parallel_data", combine)
    config.stash[_PATCH] = patch


def pytest_sessionstart(session: pytest.Session) -> None:
    """Invalidate only selected acceptance and observe the real combine lifecycle."""
    config = session.config
    selected = config.getoption("coverage_evidence_dir")
    directory = _ROOT if selected is None else Path(selected).resolve()
    if selected is not None:
        selected_data = Path(os.environ.get("COVERAGE_FILE", "")).resolve()
        if selected_data != directory / ".coverage":
            message = "Set COVERAGE_FILE to the private evidence directory's .coverage."
            raise pytest.UsageError(message)
        reports = getattr(config.option, "cov_report", {})
        if (
            reports.get("json") is None
            or Path(reports["json"]).resolve() != directory / "coverage.json"
        ):
            message = "Select the private evidence directory's JSON coverage report."
            raise pytest.UsageError(message)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
    config.stash[_EVIDENCE] = directory
    (directory / "coverage-run.json").unlink(missing_ok=True)
    config.stash[_STARTED] = time.time_ns()
    observe_combination(config, directory / ".coverage")
    config.stash[_INPUTS] = input_identity(_ROOT)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> Generator[None]:
    """Publish only after reporting, input reconciliation and lossless combination."""
    try:
        yield
    finally:
        patch = session.config.stash.get(_PATCH, None)
        if patch is not None:
            patch.undo()
    config = session.config
    directory = config.stash[_EVIDENCE]
    report = directory / "coverage.json"
    data = directory / ".coverage"
    started = config.stash[_STARTED]
    remaining = combinable_files(str(data))
    for path in [report, data, *(Path(name) for name in remaining)]:
        if path.is_file() and path.stat().st_mtime_ns >= started:
            path.chmod(0o600)
    combination = config.stash[_COMBINATION]
    complete = (
        combination.complete
        and combination.calls > 0
        and combination.completed == combination.calls
        and combination.fragments > 0
        and combination.fragments == combination.validated
        and not remaining
    )
    if (
        not complete
        and not getattr(config.option, "no_cov", False)
        and not config.option.collectonly
    ):
        session.exitstatus = pytest.ExitCode.INTERRUPTED
    if (
        exitstatus != 0
        or int(session.exitstatus) != 0
        or not complete
        or getattr(config.option, "cov_append", False)
        or config.option.collectonly
        or session.testscollected == 0
        or not report.is_file()
        or not data.is_file()
        or report.stat().st_mtime_ns < started
        or data.stat().st_mtime_ns < started
        or config.stash[_INPUTS] != input_identity(_ROOT)
    ):
        return
    record = {
        "version": _RECEIPT_VERSION,
        "started_ns": started,
        "finished_ns": time.time_ns(),
        "exitstatus": int(exitstatus),
        "tests_collected": session.testscollected,
        "invocation": "pytest",
        "combination": {
            "calls": combination.calls,
            "completed": combination.completed,
            "fragments": combination.fragments,
            "validated": combination.validated,
            "complete": complete,
        },
        "inputs": config.stash[_INPUTS],
        "report_sha256": digest(report),
        "data_sha256": digest(data),
    }
    receipt = directory / "coverage-run.json"
    # Path.open has no opener argument; set private mode at creation, not afterward.
    with open(
        receipt,
        "x",
        encoding="utf-8",
        opener=lambda path, flags: os.open(path, flags, 0o600),
    ) as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
