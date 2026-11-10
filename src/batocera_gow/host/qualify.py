"""Installed full-image qualification command; help and imports are inert."""

import argparse
import json
import signal
import sys
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import NoReturn

from batocera_gow.host.common import docker_command
from batocera_gow.host.native_freshness import BuildSnapshot, DockerImages
from batocera_gow.host.native_integration import Artifacts
from batocera_gow.host.native_preparation import (
    open_native_session,
    require_authorization,
)
from batocera_gow.host.native_remote import NativeError
from batocera_gow.host.qualification import Qualification, preservation_evidence
from batocera_gow.host.qualification_checks import (
    LocalChecks,
    PackagedChecks,
    SystemProcesses,
)
from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SettingsError


def _interrupt(_number: int, _frame: FrameType | None) -> NoReturn:
    """Unwind bounded owned checks and publish failure on operator interruption."""
    message = "Image qualification interrupted"
    raise InterruptedError(message)


@contextmanager
def _signals() -> Iterator[None]:
    """Borrow signal handlers for the whole workflow, including local checks."""
    previous = {}
    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, _interrupt)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve settings once, refuse missing consent, then run the complete scope."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--build-manifest", type=Path)
    parser.add_argument("--stock-manifest", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--image", help="Optional exact immutable ID, never a tag")
    parser.add_argument("--authorize-native", action="store_true")
    parser.add_argument("--native-authorized-target")
    parser.add_argument("--native-authorized-root")
    args = parser.parse_args(argv)
    artifacts: Artifacts | None = None
    snapshot: BuildSnapshot | None = None
    try:
        settings = HostSettings.resolve(
            env_file=args.env_file,
            overrides={
                "BATOCERA_GOW_" + key: str(value)
                for key, value in (
                    ("BUILD_MANIFEST", args.build_manifest),
                    ("STOCK_MANIFEST", args.stock_manifest),
                    ("RUNTIME_ROOT", args.runtime_root),
                    ("OUTPUT", args.output),
                )
                if value is not None
            },
        )
        ssh = settings.ssh()
        require_authorization(
            enabled=args.authorize_native,
            target=ssh.target,
            authorized_target=args.native_authorized_target,
            host_root=settings.get("BATOCERA_GOW_HOST_ROOT", "/etc/wolf")
            or "/etc/wolf",
            authorized_root=args.native_authorized_root,
            workers=None,
            worker_environment=settings.values,
        )
        root = args.project_root.resolve()
        build = Path(
            settings.get("BATOCERA_GOW_BUILD_MANIFEST")
            or root / "output/gow-full-x86/build-manifest.json"
        )
        stock = Path(
            settings.get("BATOCERA_GOW_STOCK_MANIFEST")
            or root / "output/gow-full-x86/stock-manifest.json"
        )
        runtime = Path(
            settings.get("BATOCERA_GOW_RUNTIME_ROOT")
            or root / "output/gow-full-x86/runtime"
        )
        artifacts = Artifacts(
            Path(settings.get("BATOCERA_GOW_OUTPUT") or root / "output/qualification"),
            uuid.uuid4().hex,
        )
        docker = docker_command(settings.values)
        snapshot = BuildSnapshot.verify(root, build, runtime, DockerImages(docker))
        if args.image is not None and args.image != snapshot.image:
            message = "Selected image conflicts with verified immutable build"
            raise NativeError(message)  # noqa: TRY301 - command-level refusal report.
        # Derive only evidence/artifact selections, never reread configuration.
        native_settings = HostSettings(
            {
                **settings.values,
                "BATOCERA_GOW_BUILD_MANIFEST": str(build),
                "BATOCERA_GOW_STOCK_MANIFEST": str(stock),
                "BATOCERA_GOW_RUNTIME_ROOT": str(runtime),
                "BATOCERA_GOW_OUTPUT": str(artifacts.path / "native"),
            }
        )
        processes = SystemProcesses()
        qualification = Qualification(
            snapshot,
            lambda: preservation_evidence(snapshot, build, stock),
            LocalChecks(root, processes, settings.values),
            PackagedChecks(snapshot.image, docker, processes, settings.values),
            lambda: open_native_session(
                native_settings,
                project_root=root,
                authorized_target=args.native_authorized_target,
                authorized_root=args.native_authorized_root,
                enabled=args.authorize_native,
                worker_environment=settings.values,
            ),
            artifacts=artifacts,
        )
        with _signals():
            report = qualification.run()
        sys.stdout.write(
            "Image qualification "
            + str(report["status"])
            + "; private run "
            + artifacts.path.name
            + "\n"
        )
        return int(report["full_qualification"] is not True)
    except (NativeError, SettingsError, OSError, ValueError, InterruptedError):
        if (
            artifacts is not None
            and not (artifacts.path / "qualification-report.json").exists()
        ):
            artifacts.put(
                "qualification-report.json",
                json.dumps(
                    {
                        "schema": 1,
                        "status": "failed",
                        "full_qualification": False,
                        "image": snapshot.image if snapshot is not None else None,
                        "declared_inputs": snapshot.inputs
                        if snapshot is not None
                        else None,
                        "runtime_inputs": snapshot.runtime_inputs
                        if snapshot is not None
                        else None,
                        "drift": "not-checked",
                        "cleanup_complete": True,
                        "phases": {
                            "preservation": {"status": "failed"},
                            "local": {"status": "not-run"},
                            "packaged": {"status": "not-run"},
                            "native": {"status": "not-run"},
                        },
                    }
                ).encode()
                + b"\n",
            )
        sys.stderr.write(
            "Image qualification refused or failed; check explicit authorization "
            "and current normal build evidence.\n"
        )
        return 1
    finally:
        if artifacts is not None:
            artifacts.close()


if __name__ == "__main__":
    raise SystemExit(main())
