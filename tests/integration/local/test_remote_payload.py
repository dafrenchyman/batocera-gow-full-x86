"""Execute actual delivered source in isolated Python without host dependencies."""

import base64
import io
import json
import stat
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

from batocera_gow.host.remote import payload_archive
from batocera_gow.host.remote_payload.activation import source_hash
from batocera_gow.host.remote_payload.json_data import Json, decode, record

IMAGE = "sha256:" + "b" * 64
HOME = "/etc/wolf/profile-data/user/WolfExperimental"


def execute_payload(
    payload_request: str, directory: Path, *, archive: bytes | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the production bootstrap with only stdlib and its source-only archive."""
    bootstrap = (
        files("batocera_gow.host.remote_payload")
        .joinpath("bootstrap.py")
        .read_text(encoding="utf-8")
    )
    return subprocess.run(  # noqa: S603  # Isolated interpreter executes checked payload source.
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            bootstrap,
            base64.b64encode(payload_archive() if archive is None else archive).decode(
                "ascii"
            ),
        ],
        input=payload_request,
        text=True,
        capture_output=True,
        cwd=directory,
        check=False,
    )


def owned_deployment(path: Path) -> None:
    """Create a disposable deployment ownership record, never a production home."""
    path.mkdir()
    (path / "deployment.json").write_text(
        json.dumps(
            {
                "owner": "batocera-gow-full-experiment",
                "native_home": HOME,
                "registered": False,
                "prepared_image": IMAGE,
            }
        ),
        encoding="utf-8",
    )


def test_payload_diagnostics_are_owned_atomic_and_redacted(tmp_path: Path) -> None:
    """Standalone source writes sanitized mode0600 JSON without host imports."""
    root = tmp_path / "deployment"
    owned_deployment(root)
    request: dict[str, Json] = {
        "action": "write-diagnostics",
        "deployment_root": str(root),
        "image": IMAGE,
        "local": True,
        "filename": "remote-logs.json",
        "diagnostics": {
            "logs": "ready\nAES_key=private-value\ncontroller ready",
            "access_token": "private-value",
        },
    }
    result = execute_payload(json.dumps(request), tmp_path)
    assert result.returncode == 0, result.stderr
    assert record(decode(result.stdout)) == {"ok": True, "result": {"saved": True}}
    diagnostic = root / "remote-logs.json"
    saved = diagnostic.read_text(encoding="utf-8")
    assert "private-value" not in saved
    assert "access_token" not in saved
    assert "controller ready" in saved
    assert stat.S_IMODE(diagnostic.stat().st_mode) == 0o600
    assert sorted(path.name for path in root.iterdir()) == [
        "deployment.json",
        "remote-logs.json",
    ]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["deployment"]


@pytest.mark.parametrize(
    "payload_request",
    [
        '{"private-config":',
        "[]",
        '{"action":"unknown","deployment_root":"/","private":"secret-data"}',
    ],
)
def test_malformed_and_failed_requests_have_sanitized_json_errors(
    tmp_path: Path, payload_request: str
) -> None:
    """Malformed JSON, shapes and unsafe destinations fail without raw exceptions."""
    result = execute_payload(payload_request, tmp_path)
    assert result.returncode != 0
    response = record(decode(result.stdout))
    assert response["ok"] is False
    assert "secret-data" not in result.stdout + result.stderr
    assert "private-config" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_payload_refuses_foreign_and_symlinked_destinations(tmp_path: Path) -> None:
    """On-host resolution refuses a symlink escape and an unowned occupied root."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    sentinel = foreign / "keep"
    sentinel.write_text("foreign state", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(foreign, target_is_directory=True)
    for root in (foreign, linked):
        result = execute_payload(
            json.dumps(
                {
                    "action": "write-diagnostics",
                    "deployment_root": str(root),
                    "image": IMAGE,
                    "local": True,
                    "filename": "remote-logs.json",
                    "diagnostics": {"logs": "safe"},
                }
            ),
            tmp_path,
        )
        assert result.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "foreign state"
    assert list(foreign.iterdir()) == [sentinel]


def test_payload_refuses_arbitrary_diagnostics_filename(tmp_path: Path) -> None:
    """Even an owned deployment cannot be used to overwrite arbitrary remote files."""
    root = tmp_path / "deployment"
    owned_deployment(root)
    result = execute_payload(
        json.dumps(
            {
                "action": "write-diagnostics",
                "deployment_root": str(root),
                "image": IMAGE,
                "local": True,
                "filename": "../private-file",
                "diagnostics": {},
            }
        ),
        tmp_path,
    )
    assert result.returncode != 0
    assert [path.name for path in root.iterdir()] == ["deployment.json"]


def test_delivered_shared_activation_preserves_failed_restart_state(
    tmp_path: Path,
) -> None:
    """Only delivered stdlib source performs the metadata-preserving transaction."""
    config = tmp_path / "config.toml"
    config.write_text("old\n", encoding="utf-8")
    config.chmod(0o640)
    program = """import json, pathlib, sys
from batocera_gow.host.remote_payload.activation import activate_config
request = json.load(sys.stdin)
path = pathlib.Path(request["path"])
owned = []
def broken():
    raise RuntimeError("restart failed")
try:
    activate_config(path, request["hash"], "new\\n", lambda: None, broken, owned.append)
except RuntimeError:
    pass
print(json.dumps({
    "owned": owned, "text": path.read_text(),
    "mode": path.stat().st_mode & 0o777,
}))
"""
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(payload_archive())) as original,
        zipfile.ZipFile(buffer, "w") as isolated,
    ):
        for member in original.infolist():
            if member.filename != "__main__.py":
                isolated.writestr(member, original.read(member.filename))
        isolated.writestr("__main__.py", program)
    result = execute_payload(
        json.dumps({"path": str(config), "hash": source_hash("old\n")}),
        tmp_path,
        archive=buffer.getvalue(),
    )
    assert result.returncode == 0, result.stderr
    assert record(decode(result.stdout)) == {
        "owned": [False],
        "text": "new\n",
        "mode": 0o640,
    }
    assert sorted(path.name for path in tmp_path.iterdir()) == ["config.toml"]
    with zipfile.ZipFile(io.BytesIO(payload_archive())) as source:
        assert not any(
            name.endswith(("settings.py", "ssh_config.py", ".env"))
            for name in source.namelist()
        )
