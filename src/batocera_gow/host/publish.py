"""Publish a verified committed adapter image, immutable tag before latest."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from batocera_gow.host.common import ProjectPaths, docker_command, isolated_environment
from batocera_gow.host.remote_payload.contracts import REPOSITORY
from batocera_gow.host.remote_payload.json_data import Json, decode, record, text
from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SettingsError


class DeliveryError(RuntimeError):
    """Report a nonsecret delivery failure without relaying external stderr."""


class CommandRunner(Protocol):
    """Run argv at the external process boundary, retaining captured output."""

    def __call__(
        self, args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Return a completed command or raise a sanitized delivery failure."""
        ...


class SystemRunner:
    """Run commands within explicitly configured project-owned paths."""

    def __init__(self, paths: ProjectPaths, environment: Mapping[str, str]) -> None:
        """Freeze process configuration against later ambient environment edits."""
        self.paths = paths
        self.environment = isolated_environment(paths, environment)
        self.docker = docker_command(environment)

    def __call__(
        self, args: Sequence[str], *, stdin: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Capture external output and refuse to expose credential-bearing stderr."""
        command = [*self.docker, *args[1:]] if args[0] == "docker" else list(args)
        # Command selection is configured once; arguments never pass through a shell.
        result = subprocess.run(  # noqa: S603
            command,
            cwd=self.paths.root,
            input=stdin,
            text=True,
            capture_output=True,
            env=self.environment,
            check=False,
        )
        if check and result.returncode:
            message = f"{args[0]} operation failed (exit {result.returncode})"
            raise DeliveryError(message)
        return result


def read_json(path: Path) -> dict[str, Json]:
    """Read a required object artifact, reporting only its nonsecret filename."""
    try:
        return record(decode(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError) as error:
        message = f"missing or invalid artifact: {path.name}"
        raise DeliveryError(message) from error


def atomic_json(paths: ProjectPaths, path: Path, value: Json) -> None:
    """Atomically write owner-only JSON to a validated project destination."""
    paths.assert_local(path)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def registry_digest(reference: str, runner: CommandRunner) -> str | None:
    """Resolve a manifest; only explicit absent-tag errors mean absence."""
    result = runner(
        ["docker", "manifest", "inspect", "--verbose", reference], check=False
    )
    if result.returncode:
        if (
            "manifest unknown" in result.stderr.lower()
            or "no such manifest" in result.stderr.lower()
        ):
            return None
        message = (
            "cannot inspect registry manifest; check configured Docker credentials "
            "and registry access"
        )
        raise DeliveryError(message)
    try:
        digest = text(record(record(decode(result.stdout))["Descriptor"])["digest"])
    except (ValueError, KeyError, TypeError) as error:
        message = "registry returned no unambiguous manifest digest"
        raise DeliveryError(message) from error
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        message = "registry returned no unambiguous manifest digest"
        raise DeliveryError(message)
    return digest


def validate_build(
    paths: ProjectPaths, output: Path, runner: CommandRunner
) -> dict[str, Json]:
    """Require stock verification, matching clean Git source and exact local image."""
    for name in (
        "build-manifest.json",
        "stock-manifest.json",
        "publication-manifest.json",
    ):
        paths.assert_local(output / name)
    manifest = read_json(output / "build-manifest.json")
    if (
        manifest.get("status") != "success"
        or manifest.get("inventory_verified") is not True
    ):
        message = (
            "build and stock inventory verification must succeed before publication"
        )
        raise DeliveryError(message)
    if not (output / "stock-manifest.json").is_file():
        message = "stock-manifest.json is missing"
        raise DeliveryError(message)
    sha = text(manifest.get("adapter_revision", ""))
    if not re.fullmatch("[0-9a-f]{40}", sha):
        message = "build must identify a full adapter Git SHA"
        raise DeliveryError(message)
    if manifest.get("release") != "43.1":
        message = "unexpected Batocera release"
        raise DeliveryError(message)
    expected = f"batocera-gow-full-experiment:sha-{sha}"
    if manifest.get("local_image") != expected:
        message = "build image is not the independent experimental SHA tag"
        raise DeliveryError(message)
    if runner(["git", "rev-parse", "HEAD"]).stdout.strip() != sha:
        message = "source revision no longer matches build"
        raise DeliveryError(message)
    if runner(
        ["git", "status", "--porcelain", "--untracked-files=normal"]
    ).stdout.strip():
        message = "source is dirty; commit adapter source and rebuild"
        raise DeliveryError(message)
    image_id = runner(
        ["docker", "image", "inspect", "--format", "{{.Id}}", expected]
    ).stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) or image_id != manifest.get(
        "image_id"
    ):
        message = "local image does not match build manifest"
        raise DeliveryError(message)
    return manifest


class Publisher:
    """Sequence registry mutations with an explicitly borrowed command runner."""

    def __init__(
        self, paths: ProjectPaths, output: Path, runner: CommandRunner
    ) -> None:
        """Borrow configured paths and runner without taking resource ownership."""
        self.paths, self.output, self.run = paths, output, runner

    def _publish_latest(
        self, image_id: str, sha_ref: str, latest_ref: str, digest: str
    ) -> None:
        """Update latest only after immutable publication and check both digests."""
        self.run(["docker", "tag", image_id, latest_ref])
        self.run(["docker", "push", latest_ref])
        if (
            registry_digest(sha_ref, self.run) != digest
            or registry_digest(latest_ref, self.run) != digest
        ):
            message = "published tags do not resolve to the same manifest digest"
            raise DeliveryError(message)

    def publish(
        self, *, dry_run: bool = False, repository: str = REPOSITORY
    ) -> dict[str, Json] | None:
        """Publish immutable-first, recording success only after both digests agree."""
        if repository != REPOSITORY:
            message = "only the dedicated project repository is allowed"
            raise DeliveryError(message)
        manifest = validate_build(self.paths, self.output, self.run)
        sha_ref = f"{repository}:sha-{manifest['adapter_revision']}"
        latest_ref = f"{repository}:latest"
        sys.stdout.write(sha_ref + "\n" + latest_ref + "\n")
        if dry_run:
            return None
        success = self.output / "publication-manifest.json"
        success.unlink(missing_ok=True)
        existing = registry_digest(sha_ref, self.run)
        image_id = text(manifest["image_id"])
        if existing:
            self.run(["docker", "pull", sha_ref])
            remote_id = self.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", sha_ref]
            ).stdout.strip()
            if remote_id != image_id:
                message = "immutable SHA tag already contains a different image"
                raise DeliveryError(message)
            digest = existing
        else:
            self.run(["docker", "tag", image_id, sha_ref])
            self.run(["docker", "push", sha_ref])
            pushed_digest = registry_digest(sha_ref, self.run)
            if pushed_digest is None:
                message = "SHA push did not produce a readable registry manifest"
                raise DeliveryError(message)
            digest = pushed_digest
        try:
            self._publish_latest(image_id, sha_ref, latest_ref, digest)
        except DeliveryError as error:
            message = (
                f"SHA published as {sha_ref}@{digest}; latest publication incomplete"
            )
            raise DeliveryError(message) from error
        result: dict[str, Json] = {
            "status": "success",
            "adapter_revision": manifest["adapter_revision"],
            "image_id": image_id,
            "sha_reference": sha_ref,
            "latest_reference": latest_ref,
            "digest": digest,
        }
        atomic_json(self.paths, success, result)
        return result


def main() -> int:
    """Assemble explicit local dependencies; publication never needs SSH settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        settings = HostSettings.resolve(env_file=args.env_file)
        paths = ProjectPaths(args.project_root)
        Publisher(
            paths,
            paths.root / "output/gow-full-x86",
            SystemRunner(paths, settings.values),
        ).publish(dry_run=args.dry_run, repository=args.repository)
    except (DeliveryError, SettingsError) as error:
        sys.stderr.write(f"publication refused: {error}\n")
        return 1
    except (OSError, TypeError, ValueError):
        sys.stderr.write(
            "publication refused: check build artifacts, source "
            "and configured resources\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
