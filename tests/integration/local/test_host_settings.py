"""Selected-file settings snapshots and host SSH argv/privacy boundaries."""

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from batocera_gow.host import publish, remote
from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.publish import DeliveryError
from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SettingsError, SSHConfig


def test_explicit_precedence_and_immutable_invocation_snapshot(tmp_path: Path) -> None:
    """CLI wins over environment, then the selected file, then absent-only defaults."""
    path = tmp_path / "selected.env"
    path.write_text(
        "A=file\nB=file\nC=file\nBATOCERA_GOW_SSH_TARGET=wolf-file\n", encoding="utf-8"
    )
    before = dict(os.environ)
    environment = {"A": "environment", "B": "environment"}
    settings = HostSettings.resolve(
        env_file=path,
        environ=environment,
        overrides={"A": "command"},
        defaults={"D": "default"},
    )
    assert dict(settings.values) == {
        "A": "command",
        "B": "environment",
        "C": "file",
        "D": "default",
        "BATOCERA_GOW_SSH_TARGET": "wolf-file",
    }
    environment["B"] = "changed"
    path.write_text("C=changed\nBATOCERA_GOW_SSH_TARGET=wolf-new\n", encoding="utf-8")
    assert settings.get("B") == "environment"
    assert settings.ssh().target == "wolf-file"
    assert (
        HostSettings.resolve(env_file=path, environ=environment).ssh().target
        == "wolf-new"
    )
    assert dict(os.environ) == before


def test_unselected_dotenv_is_never_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local .env must not select a target without the explicit file interface."""
    (tmp_path / ".env").write_text(
        "BATOCERA_GOW_SSH_TARGET=unexpected\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    settings = HostSettings.resolve(environ={})
    assert settings.get("BATOCERA_GOW_SSH_TARGET") is None
    with pytest.raises(SettingsError):
        settings.ssh()


@pytest.mark.parametrize("directory", [False, True])
def test_missing_or_unreadable_selected_file_has_nonsecret_failure(
    tmp_path: Path, *, directory: bool
) -> None:
    """An explicit file selection cannot silently fall back to environment values."""
    selected = tmp_path / "private-value-do-not-echo.env"
    if directory:
        selected.mkdir()
    with pytest.raises(SettingsError) as caught:
        HostSettings.resolve(
            env_file=selected, environ={"BATOCERA_GOW_SSH_TARGET": "fallback"}
        )
    assert "private-value-do-not-echo" not in str(caught.value)
    assert "fallback" not in str(caught.value)


def test_empty_supplied_target_never_falls_back(tmp_path: Path) -> None:
    """An invalid higher-priority value refuses instead of selecting another target."""
    path = tmp_path / "selected.env"
    path.write_text("BATOCERA_GOW_SSH_TARGET=wolf-file\n", encoding="utf-8")
    settings = HostSettings.resolve(
        env_file=path, environ={"BATOCERA_GOW_SSH_TARGET": ""}
    )
    with pytest.raises(SettingsError):
        settings.ssh()


@pytest.mark.parametrize(
    "target",
    ["tester@192.0.2.10", "tester@host.example", "wolf-test", "tester@[2001:db8::1]"],
)
def test_ssh_targets_keep_agent_auth_and_host_verification(target: str) -> None:
    """Direct targets and aliases use normal config/agent without a key override."""
    argv = SSHConfig(target).argv()
    assert argv[-2:] == ["--", target]
    assert "BatchMode=yes" in argv
    assert "StrictHostKeyChecking=yes" in argv
    assert "-i" not in argv


def test_optional_identity_is_literal_argv_not_key_contents() -> None:
    """A path containing spaces remains one argv element; no file is read."""
    argv = SSHConfig("wolf-test", "/not-read/private key").argv()
    assert argv[argv.index("-i") + 1] == "/not-read/private key"


@pytest.mark.parametrize(
    "target",
    [
        "",
        "-oProxyCommand=bad",
        "host;touch /tmp/bad",
        "host command",
        "$(command)",
        "a@b@c",
        "user@",
        "@host",
        "host\nsecret",
    ],
)
def test_invalid_ssh_target_refuses_injection_without_echo(target: str) -> None:
    """Destination data can neither become an SSH option nor a shell command."""
    with pytest.raises(SettingsError) as caught:
        SSHConfig(target)
    if target:
        assert target not in str(caught.value)


@pytest.mark.parametrize("failure", ["exit", "json", "remote"])
def test_ssh_boundary_never_echoes_untrusted_failure_output(
    tmp_path: Path, failure: str
) -> None:
    """SSH stderr and malformed or failed JSON cannot disclose private bytes."""
    (tmp_path / ".git").mkdir()
    paths = ProjectPaths(tmp_path, deployment_root="/srv/owned-deployment")

    def runner(
        args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert list(args)[-2] == "wolf-test"
        assert stdin is not None
        assert check is False
        assert json.loads(stdin)["deployment_root"] == "/srv/owned-deployment"
        output = (
            "private-config"
            if failure == "json"
            else json.dumps({"ok": False, "error": "private-config"})
        )
        return subprocess.CompletedProcess(
            args, 1 if failure == "exit" else 0, output, "private-config"
        )

    transport = remote.SSHTransport(
        SSHConfig("wolf-test"), paths, "/srv/owned-deployment", runner
    )
    with pytest.raises(DeliveryError) as caught:
        transport({"action": "inspect"})
    assert "private-config" not in str(caught.value)


def test_local_remote_dry_run_needs_no_ssh_or_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine local plan cannot resolve or contact a remote target."""
    (tmp_path / ".git").mkdir()
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    (output / "build-manifest.json").write_text(
        json.dumps(
            {
                "status": "success",
                "inventory_verified": True,
                "release": "43.1",
                "adapter_revision": "a" * 40,
                "image_id": "sha256:" + "b" * 64,
                "local_image": "batocera-gow-full-experiment:sha-" + "a" * 40,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gow-remote",
            "--prepare",
            "--local",
            "--dry-run",
            "--project-root",
            str(tmp_path),
        ],
    )
    monkeypatch.delenv("BATOCERA_GOW_SSH_TARGET", raising=False)
    monkeypatch.delenv("BATOCERA_GOW_ROMS_ROOT", raising=False)
    assert remote.main() == 0


def test_publish_cli_can_select_dotenv_without_ssh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The publish entry point has explicit portable root/file options, no SSH need."""
    (tmp_path / ".git").mkdir()
    path = tmp_path / "selected.env"
    path.write_text("BATOCERA_GOW_SSH_TARGET=invalid target\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gow-publish",
            "--dry-run",
            "--project-root",
            str(tmp_path),
            "--env-file",
            str(path),
        ],
    )
    # A missing build fails locally rather than attempting SSH configuration.
    assert publish.main() == 1
