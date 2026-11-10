"""Run actual maintained frontend, receiver and six-backend native assertions."""

import pytest

from batocera_gow.host.native_matrix import RECEIVER_CASES
from batocera_gow.host.native_preparation import NativeSession
from batocera_gow.host.native_remote import record, sequence
from batocera_gow.runtime.media_catalog import EMULATOR_CASES

pytestmark = pytest.mark.wolf


def test_frontend(native_session: NativeSession) -> None:
    """Normal frontend readiness includes actual final-input transport evidence."""
    report = native_session.run("frontend")
    assert report["status"] == "passed"
    assert report["evidence_complete"] is True
    assert report["cleanup_complete"] is True


@pytest.mark.parametrize("receiver", RECEIVER_CASES)
def test_receiver(native_session: NativeSession, receiver: str) -> None:
    """Each independently owned receiver retains its real assertion and capture."""
    report = native_session.run(receiver)
    rows = [record(value) for value in sequence(report["receiver_checks"])]
    selected = next(row for row in rows if row["name"] == receiver)
    assert selected["status"] == "passed"
    assert report["status"] == "passed"
    assert report["evidence_complete"] is True
    assert report["cleanup_complete"] is True


@pytest.mark.parametrize("case", [case.identifier for case in EMULATOR_CASES])
def test_backend(native_session: NativeSession, case: str) -> None:
    """Eligible exact backends exercise stock launch and observed native chord exit."""
    report = native_session.run(case)
    rows = [record(value) for value in sequence(report["cases"])]
    selected = next(row for row in rows if row["name"] == case)
    assert report["evidence_complete"] is True
    assert report["cleanup_complete"] is True
    if selected["status"] == "skipped-no-media":
        assert selected["reason"] == "Skipped: no compatible mounted media"
        pytest.skip("Skipped: no compatible mounted media. No emulator exit coverage.")
    assert selected["status"] == "passed"
    assert report["status"] == "passed"
    assert report["emulator_exit_coverage"] != "No emulator exit coverage"
