"""Exercise renewable permission and immutable-input readers on owned files."""

import errno
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from io import BufferedReader
from pathlib import Path

import pytest

from batocera_gow.runtime import native_diagnostics as diagnostics
from batocera_gow.runtime.native_checks import digest


@pytest.fixture
def root_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Callable[[object], None]]:
    """Model only the root owner prerequisite; keep file I/O and metadata real."""
    lease = tmp_path / "input-lease.json"
    lease.write_bytes(b"{}")
    lease.chmod(0o600)
    identity = lease.stat().st_dev, lease.stat().st_ino
    original_fstat = os.fstat

    def owned_stat(descriptor: int) -> os.stat_result:
        info = original_fstat(descriptor)
        if (info.st_dev, info.st_ino) == identity:
            fields = list(info)
            fields[4] = 0
            return os.stat_result(fields)
        return info

    def renew(expiry: object) -> None:
        lease.write_text(json.dumps({"expires": expiry}), encoding="utf-8")

    monkeypatch.setattr(os, "fstat", owned_stat)
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    monkeypatch.setenv("GOW_NATIVE_LEASE", str(lease))
    return lease, renew


def test_permission_is_reread_after_renewal_expiry_and_revocation(
    root_lease: tuple[Path, Callable[[object], None]],
) -> None:
    """A prior permission does not authorize input after a later lease change."""
    lease, renew = root_lease
    identity = lease.stat().st_ino
    renew(101)
    diagnostics.input_permitted()
    renew(100)
    with pytest.raises(InterruptedError, match="permission unavailable") as expired:
        diagnostics.input_permitted()
    assert isinstance(expired.value.__cause__, InterruptedError)
    assert str(expired.value.__cause__) == (
        "Native input permission expired or was revoked"
    )
    renew(200.5)
    diagnostics.input_permitted()
    assert lease.stat().st_ino == identity
    assert json.loads(lease.read_text(encoding="utf-8")) == {"expires": 200.5}
    assert lease.stat().st_mode & 0o777 == 0o600
    lease.unlink()
    with pytest.raises(InterruptedError, match="permission unavailable"):
        diagnostics.input_permitted()


@pytest.mark.parametrize(
    "expiry", [True, None, "private-invalid-expiry", [], float("nan"), float("inf")]
)
def test_malformed_expiry_cannot_authorize_input_despite_trusted_owner(
    root_lease: tuple[Path, Callable[[object], None]], expiry: object
) -> None:
    """Reject malformed lifetimes at expiry, not an unrelated ownership check."""
    lease, renew = root_lease
    renew(expiry)
    original = lease.read_bytes()
    with pytest.raises(InterruptedError, match="permission unavailable") as refused:
        diagnostics.input_permitted()
    assert isinstance(refused.value.__cause__, InterruptedError)
    assert str(refused.value.__cause__) == (
        "Native input permission expired or was revoked"
    )
    assert "private-" not in str(refused.value)
    assert lease.read_bytes() == original


@pytest.mark.parametrize("damage", ["writable", "oversized", "non-object", "syntax"])
def test_unsafe_or_malformed_lease_is_preserved_and_refused(
    root_lease: tuple[Path, Callable[[object], None]], damage: str
) -> None:
    """Storage and schema failures cannot inherit previously valid permission."""
    lease, renew = root_lease
    renew(200)
    diagnostics.input_permitted()
    if damage == "writable":
        lease.chmod(0o622)
    elif damage == "oversized":
        lease.write_bytes(b" " * 4097)
    elif damage == "non-object":
        lease.write_bytes(b"[]")
    else:
        lease.write_bytes(b"{private-invalid-json")
    original = lease.read_bytes()
    with pytest.raises(InterruptedError, match="permission unavailable"):
        diagnostics.input_permitted()
    assert lease.read_bytes() == original


def test_native_digest_requires_a_nonempty_stable_regular_readonly_input(
    tmp_path: Path,
) -> None:
    """Hash actual bytes without admitting writable firmware or blocking on a FIFO."""
    path = tmp_path / "firmware.bin"
    payload = b"owned synthetic firmware bytes\x00\xff"
    path.write_bytes(payload)
    assert digest(path) == hashlib.sha256(payload).hexdigest()
    assert path.read_bytes() == payload
    with pytest.raises(ValueError, match="Writable native firmware"):
        digest(path, readonly=True)
    empty = tmp_path / "empty.bin"
    empty.touch()
    with pytest.raises(ValueError, match="Nonregular native input"):
        digest(empty)
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo, 0o600)
    # Fixed interpreter/code; the pytest-owned FIFO path is a separate argv value.
    process = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import sys; from pathlib import Path; "
                "from batocera_gow.runtime.native_checks import digest; "
                "digest(Path(sys.argv[1]))"
            ),
            str(fifo),
        ],
        text=True,
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert process.returncode == 1
    assert "ValueError: Nonregular native input" in process.stderr
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    with pytest.raises(OSError, match=r"\[Errno 40\]") as refused:
        digest(alias)
    assert refused.value.errno == errno.ELOOP
    assert path.read_bytes() == payload


def test_native_digest_rejects_real_input_mutation_during_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A concurrent byte-count change cannot publish an apparently stable identity."""
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"original firmware")
    original_digest = hashlib.file_digest

    def changed_digest(stream: BufferedReader, algorithm: str) -> object:
        result = original_digest(stream, algorithm)
        with path.open("ab") as writer:
            writer.write(b" appended during inspection")
        return result

    monkeypatch.setattr(hashlib, "file_digest", changed_digest)
    with pytest.raises(ValueError, match="changed during inspection"):
        digest(path)
    assert path.read_bytes() == b"original firmware appended during inspection"
