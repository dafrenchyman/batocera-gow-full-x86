"""Opt-in local CLI smoke using temporary synthetic non-ROM bytes only."""

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path


def _invoke_cli(  # noqa: PLR0913 - subprocess configuration and independent privacy/status expectations belong at this fixture boundary.
    arguments: tuple[str, ...],
    *,
    project_root: Path,
    directory: Path,
    environment: Mapping[str, str],
    private_root: Path,
    expected_code: int,
) -> dict[str, object]:
    """Run the installed command and reject private-path or title disclosure.

    Args:
        arguments: Public command/options plus explicit fixture paths.
        project_root: Declared source/assets root, independent of subprocess cwd.
        directory: Foreign working directory containing the ignored dotenv trap.
        environment: Deliberately scrubbed invocation configuration.
        private_root: Synthetic library whose path must not reach public JSON.
        expected_code: Required subprocess status for this scenario.

    Returns:
        The public JSON result object.

    Raises:
        RuntimeError: If status or privacy checks fail.
        TypeError: If the response is not an object.
    """
    # The module and interpreter are fixed; fixture options remain separate argv.
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "batocera_gow.host.media",
            "--project-root",
            str(project_root),
            *arguments,
        ],
        cwd=directory,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != expected_code:
        message = f"CLI smoke returned unexpected status {result.returncode}"
        raise RuntimeError(message)
    value: object = json.loads(result.stdout)
    if not isinstance(value, dict):
        message = "CLI smoke did not return a JSON object"
        raise TypeError(message)
    if str(private_root) in result.stdout or "synthetic-private-title" in result.stdout:
        message = "CLI exposed private selection details"
        raise RuntimeError(message)
    return dict(value)


def main() -> None:
    """Exercise actual subprocess entrypoints without any SSH or media library."""
    project_root = Path.cwd()
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("BATOCERA_GOW_")
    }
    with tempfile.TemporaryDirectory(prefix="mounted-media-smoke-") as temporary:
        base = Path(temporary)
        root = base / "synthetic-library"
        (root / "nes").mkdir(parents=True)
        private = base / "private"
        private.mkdir(mode=0o700)
        record = private / "selection.json"
        # An intentionally synthetic dotenv must not be loaded implicitly.
        (base / ".env").write_text(
            "BATOCERA_GOW_ROMS_ROOT=/must-not-load\nBATOCERA_GOW_BIOS_ROOT=/must-not-load\n",
            encoding="utf-8",
        )

        def invoke(*arguments: str, expected_code: int = 0) -> dict[str, object]:
            """Invoke the public CLI using only this owned fixture's resources."""
            return _invoke_cli(
                arguments,
                project_root=project_root,
                directory=base,
                environment=environment,
                private_root=root,
                expected_code=expected_code,
            )

        counts = invoke("catalog")
        if counts.get("counts") != [253, 98, 233, 477]:
            message = "Catalog reconciliation counts disagree"
            raise RuntimeError(message)
        declared = invoke("catalog", "--system", "nes")
        if declared.get("directory") != "/userdata/roms/nes" or declared.get(
            "backends"
        ) != [["libretro", "fceumm"], ["libretro", "mesen"], ["libretro", "nestopia"]]:
            message = "System catalog lookup lost its stock declarations"
            raise RuntimeError(message)
        invoke("mounts", expected_code=2)
        common = ("--roms-view", str(root), "--record", str(record))
        absent = invoke("select", "--system", "nes", *common)
        if (
            absent.get("status") != "Skipped: no compatible mounted media"
            or record.exists()
        ):
            message = "Missing media did not remain an untested skip"
            raise RuntimeError(message)
        media = root / "nes/synthetic-private-title.nes"
        media.write_bytes(b"Synthetic text bytes only. This is not a console ROM.")
        if (
            invoke("select", "--system", "nes", *common).get("status")
            != "selected privately"
        ):
            message = "CLI did not select synthetic entry"
            raise RuntimeError(message)
        if record.stat().st_mode & 0o777 != 0o600:
            message = "Private record mode is not 0600"
            raise RuntimeError(message)
        if invoke("reproduce", *common).get("status") != "private identity reproduced":
            message = "CLI did not reproduce chosen identity"
            raise RuntimeError(message)
        invoke("select", "--system", "nes", *common, expected_code=2)
        media.write_bytes(b"Changed synthetic bytes, not a retry candidate.")
        invoke("reproduce", *common, expected_code=2)
        missing = invoke("select", "--system", "xbox", *common)
        if missing.get("status") != "Skipped: no compatible mounted media":
            message = "Absent stock Xbox folder did not skip"
            raise RuntimeError(message)
        message = (
            "Local CLI smoke passed: catalog, no dotenv, absence, private selection, "
            "reproduction, overwrite refusal and changed-input refusal. "
            "No native coverage."
        )
        sys.stdout.write(message + "\n")


if __name__ == "__main__":
    main()
