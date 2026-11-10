"""Run the mount-capable runtime suite in one owned, networkless container."""

import argparse
import os
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

from batocera_gow.host.common import docker_command


def stock_archive(root: Path, environment: Mapping[str, str]) -> Path:
    """Select the explicit stock archive or the sole existing assembly archive.

    Args:
        root: Explicit project root containing existing assembly outputs.
        environment: Invocation settings, without implicit dotenv discovery.

    Returns:
        Canonical path to the existing stock-root tar file.

    Raises:
        ValueError: If selection is ambiguous or names a non-file.
        OSError: If the selected archive cannot be resolved.
    """
    setting = environment.get("GOW_STOCK_ROOT_TAR")
    if setting:
        selected = Path(setting)
    else:
        archives = sorted(
            (root / "output/gow-full-x86").glob("assembly-*/stock-root.tar"),
        )
        if len(archives) != 1:
            message = "Set GOW_STOCK_ROOT_TAR to the pinned stock-root.tar."
            raise ValueError(message)
        selected = archives[0]
    selected = selected.resolve(strict=True)
    if not selected.is_file():
        message = "GOW_STOCK_ROOT_TAR must name a stock archive file."
        raise ValueError(message)
    return selected


def fixture_command(
    root: Path,
    output: Path,
    archive: Path,
    run_id: str,
    environment: Mapping[str, str],
) -> list[str]:
    """Build fixture-only Docker argv without host devices, state or sockets.

    Args:
        root: Explicit project root supplying readonly tests and runtime assets.
        output: Newly created run-owned output directory.
        archive: Existing stock archive, mounted readonly.
        run_id: Unique suffix shared by this run's output and container name.
        environment: Invocation settings selecting Docker and the builder image.

    Returns:
        Docker argv using the installed builder test interpreter and package.

    Raises:
        ValueError: If the requested image is outside the experimental namespace.
    """
    image = environment.get(
        "GOW_BUILDER_IMAGE",
        "batocera-gow-full-experiment-builder:trixie",
    )
    if not image.startswith("batocera-gow-full-experiment-builder:"):
        message = "Fixture builder must use the isolated experimental image prefix."
        raise ValueError(message)
    readonly = (
        (root / "tests", "/project/tests"),
        (root / "build-assets/runtime", "/project/build-assets/runtime"),
        (root / "pyproject.toml", "/project/pyproject.toml"),
        (archive, "/stock-root.tar"),
    )
    command = [
        *docker_command(environment),
        "run",
        "--rm",
        "--name",
        f"batocera-gow-full-experiment-runtime-fixture-{run_id}",
        "--network",
        "none",
        # These permissions create real readonly binds only inside the fixture.
        "--cap-add",
        "SYS_ADMIN",
        "--security-opt",
        "apparmor=unconfined",
    ]
    for source, destination in readonly:
        command.extend(
            ["--mount", f"type=bind,src={source},dst={destination},readonly"],
        )
    command.extend(
        [
            "--mount",
            f"type=bind,src={output},dst=/output",
            "--tmpfs",
            "/tmp:rw,exec",  # noqa: S108  # Container-private tmpfs, not host /tmp.
            "-e",
            "TMPDIR=/tmp",
            "-e",
            "GOW_RUNTIME_FIXTURE=1",
            "--entrypoint",
            "/opt/batocera-gow-tests/bin/python",
            image,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "/project/tests/integration/runtime/runtime_container_tests.py",
            "/project/tests/integration/local/test_runtime.py",
            "/project/tests/unit/runtime",
        ],
    )
    return command


def main(arguments: Sequence[str] | None = None) -> int:
    """Run explicitly selected fixture inputs and retain this run's own output.

    Args:
        arguments: CLI arguments, or the process arguments when omitted.

    Returns:
        The container's pytest exit status. Invalid input fails before execution.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    options = parser.parse_args(arguments)
    root = Path(options.project_root).resolve(strict=True)
    archive = stock_archive(root, os.environ)
    run_id = uuid.uuid4().hex
    output = root / "output/gow-full-x86/runtime-tests" / run_id
    command = fixture_command(root, output, archive, run_id, os.environ)
    output.mkdir(parents=True, exist_ok=False)
    # The command is an argv vector assembled above; no shell or host binds.
    return subprocess.run(command, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
