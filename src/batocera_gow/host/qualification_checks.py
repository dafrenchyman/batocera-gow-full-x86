"""Host-local measurement and owned exact-image production check boundaries."""

import json
import re
import select
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from batocera_gow.host.native_integration import Artifacts
from batocera_gow.host.native_remote import NativeError, record, sequence
from batocera_gow.provenance import file_sha256


class Processes(Protocol):
    """External process boundary; argv and captured output never enter reports."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout: float,
        data: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run bounded trusted argv with explicit borrowed settings and stdin."""
        ...


class ProcessCleanupError(NativeError):
    """Report an unresolved owned supervisor without raw argv or diagnostics."""

    def __init__(self, group: int) -> None:
        """Retain its owned session identifier for deliberate descendant recovery."""
        self.group = group
        super().__init__("Owned local process cleanup unresolved")


def _status(control: socket.socket, *, peek: bool = False) -> dict[str, object]:
    """Read one bounded private supervisor packet, independently of target output."""
    try:
        return record(json.loads(control.recv(4096, socket.MSG_PEEK if peek else 0)))
    except (OSError, ValueError, NativeError):
        return {}


def _communicate(
    child: subprocess.Popen[bytes],
    control: socket.socket,
    data: str | None,
    timeout: float,
) -> tuple[bytes, bytes]:
    """Communicate normally; detect explicit unresolved cleanup without waiting out."""
    deadline = time.monotonic() + timeout
    pending = data.encode() if data is not None else None
    while True:
        try:
            return child.communicate(
                input=pending, timeout=max(0, min(0.1, deadline - time.monotonic()))
            )
        except subprocess.TimeoutExpired:
            pending = None
            if select.select([control], [], [], 0)[0] and (
                _status(control, peek=True).get("cleanup_complete") is not True
            ):
                raise ProcessCleanupError(child.pid) from None
            if time.monotonic() >= deadline:
                raise


class SystemProcesses:
    """Execute finite children without shell expansion or raw diagnostics."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout: float,
        data: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run under a private subreaper, proving every owned descendant reaped."""
        control, inherited = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with control, inherited:
            child = subprocess.Popen(  # noqa: S603 - checked host helper, trusted argv.
                [
                    sys.executable,
                    "-m",
                    "batocera_gow.host.qualification_process",
                    str(inherited.fileno()),
                    *command,
                ],
                cwd=cwd,
                env=environment,
                start_new_session=True,
                pass_fds=(inherited.fileno(),),
                stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                umask=0o077,
            )
            inherited.close()
            outcome: dict[str, object] = {}
            try:
                stdout, stderr = _communicate(child, control, data, timeout)
            except subprocess.TimeoutExpired as error:
                raise subprocess.TimeoutExpired(
                    command, timeout, output=error.output, stderr=error.stderr
                ) from None
            finally:
                # EOF requests cleanup even if interruption preceded helper startup.
                with suppress(OSError):
                    control.shutdown(socket.SHUT_WR)
                try:
                    child.wait(timeout=5)
                    if select.select([control], [], [], 0)[0]:
                        outcome = _status(control)
                except (OSError, subprocess.SubprocessError):
                    pass
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
                if outcome.get("cleanup_complete") is not True:
                    raise ProcessCleanupError(child.pid)
            errno = outcome.get("errno")
            if isinstance(errno, int):
                raise OSError(errno, "Owned local command could not start")
            returncode = outcome.get("returncode")
            if not isinstance(returncode, int) or child.returncode != 0:
                raise ProcessCleanupError(child.pid)
            return subprocess.CompletedProcess(
                command,
                returncode,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )


class LocalChecks:
    """Run the full configured selection and the canonical independent line gate."""

    def __init__(
        self, root: Path, processes: Processes, environment: Mapping[str, str]
    ) -> None:
        """Borrow one settings snapshot and process boundary, never synchronize uv."""
        self.root = root
        self.processes = processes
        self.environment = dict(environment)

    def run(self, artifacts: Artifacts) -> dict[str, object]:
        """Use fresh isolated measurement files; preserve historical root reports."""
        measurement = artifacts.path / "measurement"
        measurement.mkdir(mode=0o700)
        # A parent coverage session must not inject historical/root measurement.
        environment = {
            key: value
            for key, value in self.environment.items()
            if not key.startswith(("COVERAGE_", "COV_CORE_"))
        }
        environment.update(
            COVERAGE_FILE=str(measurement / ".coverage"), UV_PYTHON_DOWNLOADS="never"
        )
        environment.pop("PYTEST_ADDOPTS", None)
        result: dict[str, object] = {
            "status": "failed",
            "evidence_directory": "measurement",
            "cleanup_complete": True,
            "pytest": {"status": "not-run"},
            "line_gate": {"status": "not-run"},
        }
        active = "pytest"
        result[active] = {"status": "running"}
        try:
            suite = self.processes.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--coverage-evidence-dir=" + str(measurement),
                    "--cov-report=json:" + str(measurement / "coverage.json"),
                    "--cov-report=term:skip-covered",
                ],
                cwd=self.root,
                environment=environment,
                timeout=1800,
            )
            result["pytest"] = {
                "status": "passed" if suite.returncode == 0 else "failed",
                "exit_code": suite.returncode,
            }
            if suite.returncode:
                return result
            active = "line_gate"
            result[active] = {"status": "running"}
            gate = self.processes.run(
                [
                    sys.executable,
                    str(self.root / "scripts/check_python_coverage.py"),
                    "--report",
                    str(measurement / "coverage.json"),
                    "--receipt",
                    str(measurement / "coverage-run.json"),
                    "--data",
                    str(measurement / ".coverage"),
                ],
                cwd=self.root,
                environment=environment,
                timeout=120,
            )
            result["line_gate"] = {
                "status": "passed" if gate.returncode == 0 else "failed",
                "exit_code": gate.returncode,
            }
            if gate.returncode:
                return result
            result.update(
                status="passed",
                evidence={
                    name: file_sha256(measurement / name)
                    for name in ("coverage.json", "coverage-run.json", ".coverage")
                },
            )
        except ProcessCleanupError as error:
            result[active] = {"status": "failed", "failure": "cleanup-unresolved"}
            result.update(
                failure="owned-local-process-cleanup-unresolved",
                cleanup_complete=False,
                owned_process_group=error.group,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result[active] = {"status": "failed", "failure": type(error).__name__}
            result["failure"] = "bounded-local-check-failed"
        finally:
            # Child-created evidence must remain private even after failed pytest.
            for path in measurement.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    path.chmod(0o600)
                elif path.is_dir() and not path.is_symlink():
                    path.chmod(0o700)
        return result


def _owned_container(document: str, image: str, owner: str) -> str:
    """Pin only one positively owned exact-image networkless check container."""
    rows = sequence(json.loads(document))
    if len(rows) != 1:
        message = "Packaged container inspection incomplete"
        raise NativeError(message)
    container = record(rows[0])
    config = record(container.get("Config"))
    if (
        record(config.get("Labels")).get("io.gow.qualify.owner") != owner
        or container.get("Image") != image
        or record(container.get("HostConfig")).get("NetworkMode") != "none"
        or re.fullmatch(r"[a-f0-9]{64}", str(container.get("Id"))) is None
    ):
        message = "Packaged container ownership or image differs"
        raise NativeError(message)
    return str(container["Id"])


class PackagedChecks:
    """Own one networkless disposable container pinned to the selected image."""

    def __init__(
        self,
        image: str,
        docker: Sequence[str],
        processes: Processes,
        environment: Mapping[str, str],
    ) -> None:
        """Borrow trusted Docker argv, immutable image and the invocation snapshot."""
        self.image = image
        self.docker = tuple(docker)
        self.processes = processes
        self.environment = dict(environment)

    def run(self, artifacts: Artifacts) -> dict[str, object]:
        """Create, inspect, execute checked stdin source, then verify owned absence."""
        owner = uuid.uuid4().hex
        name = "batocera-gow-qualify-" + owner
        result: dict[str, object] = {
            "status": "failed",
            "image": self.image,
            "cleanup_complete": False,
            "evidence": "packaged-check.json",
            "owner": owner,
            "container_name": name,
        }
        pinned: str | None = None
        create_completed = False
        process_cleanup_complete = True

        def command(
            arguments: list[str], data: str | None = None
        ) -> subprocess.CompletedProcess[str]:
            return self.processes.run(
                [*self.docker, *arguments],
                cwd=artifacts.path,
                environment=self.environment,
                timeout=120,
                data=data,
            )

        try:
            created = command(
                [
                    "create",
                    "--name",
                    name,
                    "--label",
                    "io.gow.qualify.owner=" + owner,
                    "--network",
                    "none",
                    "--pull",
                    "never",
                    "--interactive",
                    "--workdir",
                    "/opt/gow-full-x86",
                    "--entrypoint",
                    "python3",
                    self.image,
                    "-",
                ]
            )
            create_completed = created.returncode == 0
            inspected = command(["container", "inspect", name])
            if inspected.returncode:
                message = "Packaged container creation unresolved"
                raise NativeError(message)  # noqa: TRY301 - inspect before owned cleanup.
            pinned = _owned_container(inspected.stdout, self.image, owner)
            result["container_id"] = pinned
            if created.returncode:
                message = "Packaged container create failed"
                raise NativeError(message)  # noqa: TRY301 - report failed create after pin.
            source = (
                files("batocera_gow.host")
                .joinpath("packaged_check.py")
                .read_text(encoding="utf-8")
            )
            checked = command(["start", "--attach", "--interactive", pinned], source)
            observed = record(json.loads(checked.stdout))
            if checked.returncode == 0 and observed.get("status") == "passed":
                result.update(status="passed", checks=observed)
        except ProcessCleanupError as error:
            process_cleanup_complete = False
            result.update(
                failure="owned-docker-process-cleanup-unresolved",
                owned_process_group=error.group,
            )
        except (NativeError, OSError, ValueError, subprocess.SubprocessError):
            result["failure"] = "packaged-check-failed"
        finally:
            result["cleanup_complete"] = self._cleanup(
                command,
                name=name,
                owner=owner,
                creation_completed=create_completed,
                result=result,
            )
            result["cleanup_complete"] = (
                result["cleanup_complete"] is True and process_cleanup_complete
            )
            if result["cleanup_complete"] is not True:
                result["status"] = "failed"
            artifacts.put(
                "packaged-check.json",
                json.dumps(result, sort_keys=True).encode() + b"\n",
            )
        return result

    def _cleanup(
        self,
        command: Callable[[list[str]], subprocess.CompletedProcess[str]],
        *,
        name: str,
        owner: str,
        creation_completed: bool,
        result: dict[str, object],
    ) -> bool:
        """Remove only positively owned state and independently observe its absence."""
        pinned = str(result["container_id"]) if "container_id" in result else None
        try:
            if pinned is None:
                recovered = command(["container", "inspect", name])
                if recovered.returncode == 0:
                    pinned = _owned_container(recovered.stdout, self.image, owner)
                    result["container_id"] = pinned
                else:
                    absent = command(
                        [
                            "container",
                            "ls",
                            "--all",
                            "--filter",
                            "name=^/" + name + "$",
                            "--format",
                            "{{.ID}}",
                        ]
                    )
                    return (
                        creation_completed
                        and absent.returncode == 0
                        and not absent.stdout.strip()
                    )
            removed = command(["rm", "--force", pinned])
            absent = command(
                [
                    "container",
                    "ls",
                    "--all",
                    "--no-trunc",
                    "--filter",
                    "id=" + pinned,
                    "--format",
                    "{{.ID}}",
                ]
            )
        except ProcessCleanupError as error:
            result["owned_process_group"] = error.group
            return False
        except (NativeError, OSError, ValueError, subprocess.SubprocessError):
            return False
        return (
            removed.returncode == 0
            and absent.returncode == 0
            and not absent.stdout.strip()
        )
