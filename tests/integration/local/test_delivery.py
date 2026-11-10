"""Immutable-first publication and nonsecret process/diagnostic boundaries."""

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from batocera_gow.host import publish
from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.remote_payload.contracts import REPOSITORY
from batocera_gow.host.remote_payload.json_data import Json, record
from batocera_gow.host.remote_payload.privacy import sanitize

SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64
DIGEST = "sha256:" + "c" * 64
SHA_REF = REPOSITORY + ":sha-" + SHA
LATEST = REPOSITORY + ":latest"


class RegistryFixture:
    """Content-addressed external registry model with deliberate failure points."""

    def __init__(self) -> None:
        """Start with an empty registry and no injected process failures."""
        self.calls: list[tuple[str, ...]] = []
        self.tags: dict[str, str] = {}
        self.registry: dict[str, str] = {}
        self.dirty = False
        self.fail_push: str | None = None
        self.wrong_latest = False

    def __call__(
        self, args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Model registry/Git process output without touching either real service."""
        assert stdin is None
        del (
            check
        )  # The fixture models failures explicitly rather than subprocess policy.
        self.calls.append(tuple(args))
        command = list(args)
        value = ""
        if command[:2] == ["git", "rev-parse"]:
            value = SHA
        elif command[:2] == ["git", "status"]:
            value = " M source.py" if self.dirty else ""
        elif command[:3] == ["docker", "image", "inspect"]:
            value = self.tags.get(command[-1], IMAGE_ID)
        elif command[:3] == ["docker", "manifest", "inspect"]:
            if command[-1] not in self.registry:
                return subprocess.CompletedProcess(command, 1, "", "manifest unknown")
            value = json.dumps({"Descriptor": {"digest": self.registry[command[-1]]}})
        elif command[:2] == ["docker", "tag"]:
            self.tags[command[-1]] = command[-2]
        elif command[:2] == ["docker", "push"]:
            if command[-1] == self.fail_push:
                message = "push failed"
                raise publish.DeliveryError(message)
            self.registry[command[-1]] = (
                "sha256:" + "d" * 64
                if command[-1] == LATEST and self.wrong_latest
                else DIGEST
            )
        elif command[:2] != ["docker", "pull"]:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, value, "")


@pytest.fixture
def publication(tmp_path: Path) -> tuple[publish.Publisher, RegistryFixture, Path]:
    """Supply real owned artifacts and a replaceable external process boundary."""
    (tmp_path / ".git").mkdir()
    output = tmp_path / "output/gow-full-x86"
    output.mkdir(parents=True)
    manifest: dict[str, Json] = {
        "status": "success",
        "adapter_revision": SHA,
        "local_image": "batocera-gow-full-experiment:sha-" + SHA,
        "image_id": IMAGE_ID,
        "inventory_verified": True,
        "release": "43.1",
    }
    (output / "build-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (output / "stock-manifest.json").write_text("{}", encoding="utf-8")
    registry = RegistryFixture()
    return publish.Publisher(ProjectPaths(tmp_path), output, registry), registry, output


def test_publication_is_immutable_first_and_records_matching_digests(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
) -> None:
    """Both tags select the verified image and success follows digest agreement."""
    publisher, registry, output = publication
    result = publisher.publish()
    assert [call[-1] for call in registry.calls if call[:2] == ("docker", "push")] == [
        SHA_REF,
        LATEST,
    ]
    assert all(
        call[-2] == IMAGE_ID for call in registry.calls if call[:2] == ("docker", "tag")
    )
    assert registry.registry[SHA_REF] == registry.registry[LATEST]
    assert result is not None
    assert result["digest"] == DIGEST
    assert (
        json.loads((output / "publication-manifest.json").read_text(encoding="utf-8"))
        == result
    )


@pytest.mark.parametrize(
    "repository",
    [
        "ghcr.io/dafrenchyman/batocera-gow",
        "ghcr.io/dafrenchyman/batocera-gow-full-experiment",
    ],
)
def test_old_repository_refused_before_external_commands(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
    repository: str,
) -> None:
    """An operator override cannot publish into either former repository."""
    publisher, registry, _ = publication
    with pytest.raises(publish.DeliveryError):
        publisher.publish(repository=repository)
    assert registry.calls == []


def test_missing_stock_artifact_or_dirty_source_cannot_publish(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
) -> None:
    """Both required build evidence and matching clean source gate any push."""
    publisher, registry, output = publication
    (output / "stock-manifest.json").unlink()
    with pytest.raises(publish.DeliveryError):
        publisher.publish()
    (output / "stock-manifest.json").write_text("{}", encoding="utf-8")
    registry.dirty = True
    with pytest.raises(publish.DeliveryError):
        publisher.publish()
    assert not any(call[:2] == ("docker", "push") for call in registry.calls)


def test_immutable_conflict_never_mutates_tags(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
) -> None:
    """An existing SHA with different config identity refuses even latest changes."""
    publisher, registry, _ = publication
    registry.registry[SHA_REF], registry.tags[SHA_REF] = DIGEST, "sha256:" + "e" * 64
    with pytest.raises(publish.DeliveryError):
        publisher.publish()
    assert not any(
        call[:2] in {("docker", "push"), ("docker", "tag")} for call in registry.calls
    )


def test_identical_immutable_tag_is_reused(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
) -> None:
    """An existing matching immutable tag is not repushed."""
    publisher, registry, _ = publication
    registry.registry[SHA_REF], registry.tags[SHA_REF] = DIGEST, IMAGE_ID
    publisher.publish()
    assert [call[-1] for call in registry.calls if call[:2] == ("docker", "push")] == [
        LATEST
    ]


@pytest.mark.parametrize("failure", ["sha", "latest", "digest"])
def test_partial_failure_never_records_false_success(
    publication: tuple[publish.Publisher, RegistryFixture, Path], failure: str
) -> None:
    """Failed SHA, latest push and differing digest remain incomplete publication."""
    publisher, registry, output = publication
    registry.fail_push = (
        SHA_REF if failure == "sha" else LATEST if failure == "latest" else None
    )
    registry.wrong_latest = failure == "digest"
    with pytest.raises(publish.DeliveryError):
        publisher.publish()
    if failure == "sha":
        assert LATEST not in registry.tags
    else:
        assert SHA_REF in registry.registry
    assert not (output / "publication-manifest.json").exists()


def test_dry_run_has_no_mutation_or_credentials(
    publication: tuple[publish.Publisher, RegistryFixture, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Local planning prints references only and performs no registry writes."""
    publisher, registry, output = publication
    monkeypatch.setenv("GH_TOKEN", "secret-token-value")
    publisher.publish(dry_run=True)
    printed = capsys.readouterr().out
    assert printed.splitlines() == [SHA_REF, LATEST]
    assert "secret-token-value" not in printed
    assert not any(
        call[:2] in {("docker", "tag"), ("docker", "push"), ("docker", "login")}
        for call in registry.calls
    )
    assert registry.registry == {}
    assert not (output / "publication-manifest.json").exists()


def test_registry_authentication_failure_is_not_absence() -> None:
    """Authentication failures cannot authorize replacing an immutable tag."""

    def unavailable(
        args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert stdin is None
        assert check is False
        return subprocess.CompletedProcess(args, 1, "", "unauthorized TOKEN=secret")

    with pytest.raises(publish.DeliveryError) as caught:
        publish.registry_digest(SHA_REF, unavailable)
    assert "secret" not in str(caught.value)


def test_diagnostics_redact_secrets_but_retain_safe_lines() -> None:
    """Sensitive keys and complete sensitive lines never reach persisted diagnostics."""
    value = record(
        sanitize(
            {
                "logs": (
                    "frontend started\nAES_key=secret\n"
                    "Authorization: Bearer private\ncontroller ready"
                ),
                "access_token": "private",
            }
        )
    )
    assert "access_token" not in value
    assert "secret" not in str(value["logs"])
    assert "private" not in str(value["logs"])
    assert "controller ready" in str(value["logs"])
