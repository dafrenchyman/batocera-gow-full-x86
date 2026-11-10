"""Deliver ephemeral checked source for owned Wolf deployment operations."""

import argparse
import base64
import io
import json
import re
import shlex
import sys
import tomllib
import urllib.request
import zipfile
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from batocera_gow.host.common import ProjectPaths
from batocera_gow.host.publish import (
    CommandRunner,
    DeliveryError,
    SystemRunner,
    atomic_json,
    read_json,
)
from batocera_gow.host.registration import (
    RegistrationError,
    transform_config,
    without_experiment,
)
from batocera_gow.host.remote_payload.activation import source_hash
from batocera_gow.host.remote_payload.contracts import (
    NATIVE_HOME,
    PROFILE,
    REPOSITORY,
    RUNNER,
    TITLE,
    UI_REVISION,
)
from batocera_gow.host.remote_payload.json_data import (
    Json,
    decode,
    record,
    sequence,
    text,
)
from batocera_gow.host.remote_payload.privacy import sanitize
from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SettingsError, SSHConfig
from batocera_gow.runtime.mounted_media import ContentRoots


class Transport(Protocol):
    """Borrowed JSON request boundary, independently replaceable in local tests."""

    def __call__(self, request: dict[str, Json]) -> dict[str, Json]:
        """Return a checked response without retaining private request bytes."""
        ...


def payload_archive() -> bytes:
    """Package only checked stdlib source, never settings, secrets or request data."""
    source = files("batocera_gow.host.remote_payload")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for package in (
            "batocera_gow",
            "batocera_gow/host",
            "batocera_gow/host/remote_payload",
        ):
            archive.writestr(package + "/__init__.py", "")
        for name in (
            "activation.py",
            "activity.py",
            "contracts.py",
            "json_data.py",
            "privacy.py",
            "operations.py",
        ):
            archive.writestr(
                "batocera_gow/host/remote_payload/" + name,
                source.joinpath(name).read_bytes(),
            )
        archive.writestr("__main__.py", source.joinpath("launcher.py").read_bytes())
    return buffer.getvalue()


class SSHTransport:
    """Execute checked source ephemerally; stdin is the sole private request channel."""

    def __init__(
        self,
        config: SSHConfig,
        paths: ProjectPaths,
        deployment_root: str,
        runner: CommandRunner,
    ) -> None:
        """Borrow target/process settings and an explicitly owned remote root."""
        paths.assert_remote(deployment_root)
        paths.assert_remote(NATIVE_HOME, native_home=True)
        self.config, self.paths, self.deployment_root, self.runner = (
            config,
            paths,
            deployment_root,
            runner,
        )

    def __call__(self, request: dict[str, Json]) -> dict[str, Json]:
        """Send one bounded-memory JSON request and discard arbitrary failure output."""
        self.paths.assert_remote(self.deployment_root)
        bootstrap = (
            files("batocera_gow.host.remote_payload")
            .joinpath("bootstrap.py")
            .read_text(encoding="utf-8")
        )
        archive = base64.b64encode(payload_archive()).decode("ascii")
        command = (
            "sudo -n python3 -I -c "
            + shlex.quote(bootstrap)
            + " "
            + shlex.quote(archive)
        )
        result = self.runner(
            [*self.config.argv(), command],
            stdin=json.dumps({**request, "deployment_root": self.deployment_root}),
            check=False,
        )
        if result.returncode:
            message = (
                "SSH or remote operation failed; check configured resources "
                "and prerequisites"
            )
            raise DeliveryError(message)
        try:
            response = record(decode(result.stdout))
            result_value = record(response.get("result"))
        except (TypeError, ValueError) as error:
            message = "invalid or unsuccessful remote response"
            raise DeliveryError(message) from error
        if response.get("ok") is not True:
            message = "remote operation refused"
            raise DeliveryError(message)
        return result_value


def build_artifact(output: Path) -> dict[str, Json]:
    """Require the verified immutable committed or worktree build manifest."""
    value = read_json(output / "build-manifest.json")
    revision = text(value.get("adapter_revision", ""))
    source_kind = value.get("source_kind", "git")
    if source_kind == "worktree":
        digest = text(value.get("source_sha256", ""))
        source_valid = (
            bool(re.fullmatch("[0-9a-f]{64}", digest))
            and revision == "worktree-sha256:" + digest
        )
        expected_tag = "worktree-" + digest
    else:
        source_valid = source_kind == "git" and bool(
            re.fullmatch("[0-9a-f]{40}", revision)
        )
        expected_tag = "sha-" + revision
    if (
        value.get("status") != "success"
        or value.get("inventory_verified") is not True
        or value.get("release") != "43.1"
        or not source_valid
        or not re.fullmatch("sha256:[0-9a-f]{64}", text(value.get("image_id", "")))
        or value.get("local_image") != "batocera-gow-full-experiment:" + expected_tag
    ):
        message = (
            "a verified experimental build manifest is required for local deployment"
        )
        raise DeliveryError(message)
    return value


def publication(output: Path) -> dict[str, Json]:
    """Require complete immutable/latest publication evidence."""
    value = read_json(output / "publication-manifest.json")
    sha, digest = text(value.get("adapter_revision", "")), text(value.get("digest", ""))
    if (
        value.get("status") != "success"
        or not re.fullmatch("[0-9a-f]{40}", sha)
        or not re.fullmatch("sha256:[0-9a-f]{64}", digest)
        or value.get("sha_reference") != f"{REPOSITORY}:sha-{sha}"
        or value.get("latest_reference") != f"{REPOSITORY}:latest"
    ):
        message = "a verified complete publication manifest is required"
        raise DeliveryError(message)
    return value


class Remote:
    """Coordinate delivery with explicitly configured borrowed transport and runner."""

    def __init__(
        self,
        transport: Transport,
        paths: ProjectPaths,
        runner: CommandRunner,
        content_roots: ContentRoots,
        *,
        local: bool = False,
    ) -> None:
        """Borrow invocation collaborators without constructing hidden defaults."""
        self.transport, self.paths, self.run, self.content_roots = (
            transport,
            paths,
            runner,
            content_roots,
        )
        self.output = paths.root / "output/gow-full-x86"
        self.local = local

    def build_artifact(self) -> dict[str, Json]:
        """Read this invocation's configured local build artifact."""
        return build_artifact(self.output)

    def image(self) -> str:
        """Resolve the exact selected local or published immutable image."""
        return (
            text(self.build_artifact()["image_id"])
            if self.local
            else f"{REPOSITORY}@{self.publication()['digest']}"
        )

    def publication(self) -> dict[str, Json]:
        """Read this invocation's configured publication artifact."""
        return publication(self.output)

    def request(self, action: str, **fields: Json) -> dict[str, Json]:
        """Send selected immutable identity and already validated content roots."""
        if self.local:
            fields.update(
                local=True, adapter_revision=self.build_artifact()["adapter_revision"]
            )
        return self.transport(
            {
                "action": action,
                "image": self.image(),
                "roms_root": self.content_roots.roms,
                "bios_root": self.content_roots.bios,
                **fields,
            }
        )

    @staticmethod
    def confirm_ui(revision: str) -> None:
        """Require a reviewed native-home formula when the installed UI changes."""
        if revision == UI_REVISION:
            return
        if not re.fullmatch("[0-9a-f]{40}", revision):
            message = "unrecognized installed Wolf UI revision"
            raise DeliveryError(message)
        url = f"https://raw.githubusercontent.com/games-on-whales/wolf-ui/{revision}/src/Scenes/Main/Body/Apps/App.cs"
        with urllib.request.urlopen(url, timeout=20) as response:
            source = response.read().decode()
        if not re.search(
            r'RunnerStateFolder\s*=\s*\$"profile-data/'
            r'\{WolfApi\.ActiveProfile\.Id\}/\{Runner\.Name\}"',
            source,
        ):
            message = (
                "Wolf UI native-home formula changed; review required, "
                "no mount override permitted"
            )
            raise DeliveryError(message)

    def prepare(self) -> None:
        """Verify image prerequisites remotely and record only sanitized preparation."""
        artifact = self.build_artifact() if self.local else self.publication()
        size = int(
            self.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "{{.Size}}",
                    text(artifact["image_id"]),
                ]
            ).stdout.strip()
        )
        references: dict[str, Json] = (
            {}
            if self.local
            else {
                "sha_reference": artifact["sha_reference"],
                "latest_reference": artifact["latest_reference"],
            }
        )
        result = self.request(
            "prepare",
            image_id=artifact["image_id"],
            required_bytes=2 * size + 1024**3,
            **references,
        )
        self.confirm_ui(text(result["ui_revision"]))
        atomic_json(self.paths, self.output / "remote-preparation.json", result)
        sys.stdout.write(
            "Prepared verified image; native userdata initializes only through Wolf.\n"
        )

    def register(self) -> None:
        """Activate one owned app and verify unrelated config/API preservation."""
        prepared = self.request("read-registration")
        self.confirm_ui(text(prepared["ui_revision"]))
        image, before = self.image(), text(prepared["config"])
        transformed = transform_config(
            before,
            image,
            mounts=self.content_roots.wolf_mounts(),
            owned=prepared["owned"] is True,
            expected_hash=source_hash(before),
        )
        result = self.request(
            "activate",
            config=transformed,
            expected_hash=source_hash(before),
            ui_revision=prepared["ui_revision"],
        )
        if tomllib.loads(text(result["config"])) != tomllib.loads(transformed):
            message = "remote configuration changed during activation"
            raise DeliveryError(message)
        profiles = result["profiles"]
        profiles = profiles.get("profiles") if isinstance(profiles, dict) else profiles
        baseline = prepared["profiles"]
        baseline = baseline.get("profiles") if isinstance(baseline, dict) else baseline
        if (
            not isinstance(profiles, list)
            or not isinstance(baseline, list)
            or without_experiment({"profiles": baseline})
            != without_experiment({"profiles": profiles})
        ):
            message = "Wolf API preexisting profiles/apps changed during restart"
            raise DeliveryError(message)
        users = [
            record(profile)
            for profile in profiles
            if record(profile).get("id") == PROFILE
        ]
        apps = [
            record(app)
            for profile in users
            for app in sequence(profile.get("apps", []))
            if record(app).get("title") == TITLE
        ]
        if len(users) != 1 or len(apps) != 1:
            message = "Wolf API does not expose exactly one experiment under user"
            raise DeliveryError(message)
        app, runner = apps[0], record(apps[0].get("runner", {}))
        if (
            not app.get("start_virtual_compositor")
            or app.get("start_audio_server", True) is not True
            or runner.get("image") != image
            or runner.get("name") != RUNNER
        ):
            message = "Wolf API experiment identity/compositor mismatch"
            raise DeliveryError(message)
        atomic_json(
            self.paths,
            self.output / "remote-registration.json",
            {
                "registered": True,
                "image": image,
                "native_home": NATIVE_HOME,
                "ui_revision": prepared["ui_revision"],
                "residual_race": (
                    "A new session may start between final idle check and restart."
                ),
            },
        )
        sys.stdout.write(
            "Registered Batocera full x86 experiment under User. "
            "Launch it through Wolf UI.\n"
            "Activation retains a concurrent-new-session race; "
            "no atomic idle reservation exists.\n"
        )

    def inspect(self, *, logs: bool = False) -> None:
        """Persist recursively sanitized diagnostics at local and owned remote paths."""
        result = record(sanitize(self.request("logs" if logs else "inspect")))
        filename = "remote-logs.json" if logs else "remote-session.json"
        atomic_json(self.paths, self.output / filename, result)
        self.request("write-diagnostics", filename=filename, diagnostics=result)
        sys.stdout.write(json.dumps(result, indent=2) + "\n")


def _configured_remote(settings: HostSettings, root: Path, *, local: bool) -> Remote:
    """Assemble only remote operations, refusing missing explicit deployment roots."""
    deployment = settings.get("BATOCERA_GOW_DEPLOYMENT_ROOT")
    if not deployment:
        message = "BATOCERA_GOW_DEPLOYMENT_ROOT is required for remote operations"
        raise DeliveryError(message)
    paths = ProjectPaths(root, deployment_root=deployment)
    runner = SystemRunner(paths, settings.values)
    return Remote(
        SSHTransport(settings.ssh(), paths, deployment, runner),
        paths,
        runner,
        ContentRoots.from_environment(settings.values),
        local=local,
    )


def main() -> int:
    """Resolve one invocation; local plans never require remote settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "register", "inspect-session", "collect-logs"):
        group.add_argument("--" + action, action="store_true")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use an already loaded verified image, without GHCR.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate local image evidence only, without SSH.",
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--deployment-root")
    parser.add_argument("--ssh-target")
    parser.add_argument("--ssh-identity-file")
    args = parser.parse_args()
    overrides = {
        key: value
        for key, value in {
            "BATOCERA_GOW_SSH_TARGET": args.ssh_target,
            "BATOCERA_GOW_SSH_IDENTITY_FILE": args.ssh_identity_file,
            "BATOCERA_GOW_DEPLOYMENT_ROOT": args.deployment_root,
        }.items()
        if value is not None
    }
    try:
        settings = HostSettings.resolve(env_file=args.env_file, overrides=overrides)
        paths = ProjectPaths(args.project_root)
        # Local planning reads only public artifacts; it never resolves SSH or media.
        if args.dry_run:
            output = paths.root / "output/gow-full-x86"
            if args.local:
                build_artifact(output)
            else:
                publication(output)
            sys.stdout.write(
                "Local delivery plan only; no SSH or remote mutation performed.\n"
            )
            return 0
        remote = _configured_remote(settings, args.project_root, local=args.local)
        if args.prepare:
            remote.prepare()
        elif args.register:
            remote.register()
        else:
            remote.inspect(logs=args.collect_logs)
    except (DeliveryError, RegistrationError, SettingsError) as error:
        sys.stderr.write(f"remote operation refused: {error}\n")
        return 1
    except (OSError, TypeError, ValueError):
        sys.stderr.write(
            "remote operation refused: check configuration, owned paths "
            "and image evidence\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
