"""Exercise qualification barriers through actual local and native consumers."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import textwrap
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest

from batocera_gow.host import native_preparation
from batocera_gow.host.native_freshness import BuildSnapshot
from batocera_gow.host.native_integration import Artifacts
from batocera_gow.host.native_preparation import NativeSession
from batocera_gow.host.native_remote import NativeError, record
from batocera_gow.host.qualification import Qualification, preservation_evidence
from batocera_gow.host.qualification_checks import (
    LocalChecks,
    PackagedChecks,
    SystemProcesses,
)
from batocera_gow.provenance import (
    INPUT_FILES,
    declared_inputs,
    file_sha256,
    tree_source,
)
from tests.integration.local.test_native_integration import matrix_config
from tests.integration.local.test_native_transfer import Images, SessionWorld

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("completion", ["normal", "timeout", "interruption"])
@pytest.mark.parametrize("child_signal", ["default", "ignored"])
def test_fast_intermediate_exit_cannot_leak_detached_descendants(
    tmp_path: Path, completion: str, child_signal: str
) -> None:
    """Use a separate subreaper guardian so even a regressed owner cannot orphan."""
    marker = tmp_path / "started.json"
    target = tmp_path / "target.py"
    target.write_text(
        "import json, os, pathlib, signal, sys, time\n"
        "assert sys.stdin.readline() == 'go\\n'\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "root = os.getpid()\n"
        "if os.fork():\n"
        + (
            "    while not marker.exists(): time.sleep(0.001)\n    os._exit(23)\n"
            if completion == "normal"
            else "    time.sleep(60)\n"
        )
        + "middle = os.getpid()\n"
        "if os.fork(): os._exit(0)\n"
        "os.setsid()\n"
        "null = os.open(os.devnull, os.O_RDWR)\n"
        "for number in (0, 1, 2): os.dup2(null, number)\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "temporary = marker.with_suffix('.tmp')\n"
        "temporary.write_text(json.dumps([root, middle, os.getpid()]))\n"
        "temporary.replace(marker)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    target.chmod(0o600)
    guardian = tmp_path / "guardian.py"
    guardian.write_text(_guardian_program(), encoding="utf-8")
    guardian.chmod(0o600)
    output = tmp_path / "guardian.json"
    errors = tmp_path / "guardian-errors"
    pid = os.posix_spawn(
        sys.executable,
        [
            sys.executable,
            str(guardian),
            str(target),
            str(marker),
            completion,
            child_signal,
        ],
        os.environ,
        setsid=True,
        file_actions=[
            (os.POSIX_SPAWN_OPEN, 1, str(output), os.O_WRONLY | os.O_CREAT, 0o600),
            (os.POSIX_SPAWN_OPEN, 2, str(errors), os.O_WRONLY | os.O_CREAT, 0o600),
        ],
    )
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0, errors.read_text(encoding="utf-8")
    observed = json.loads(output.read_bytes())
    assert observed["outcome"] == (
        "returned-23" if completion == "normal" else completion
    )
    assert observed["owned_processes_absent"] is True
    assert observed["unrelated_guard_survived"] is True
    assert observed["guardian_children_remaining"] == []


def _guardian_program() -> str:
    """Run the public owner in an independent process with unconditional rescue."""
    return textwrap.dedent(
        """\
        import ctypes, json, os, pathlib, signal, sys, threading, time
        from batocera_gow.host.qualification_checks import SystemProcesses
        import subprocess

        target, marker, completion, child_signal = sys.argv[1:]
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'guardian subreaper unavailable')
        def children():
            return [int(pid) for pid in pathlib.Path(
                f'/proc/self/task/{os.getpid()}/children').read_text().split()]
        def interrupt(number, frame):
            raise KeyboardInterrupt('private interruption detail')
        def deadline(number, frame):
            raise TimeoutError('guardian deadline')
        def send_interruption():
            limit = time.monotonic() + 5
            while not pathlib.Path(marker).exists() and time.monotonic() < limit:
                time.sleep(0.01)
            if pathlib.Path(marker).exists():
                os.kill(os.getpid(), signal.SIGUSR1)
        def absent(pid):
            try: os.kill(pid, 0)
            except ProcessLookupError: return True
            return False
        signal.signal(signal.SIGALRM, deadline)
        signal.signal(signal.SIGUSR1, interrupt)
        signal.alarm(12)
        guard = os.fork()
        if guard == 0:
            os.setsid()
            os.execl(
                sys.executable, sys.executable, '-c', 'import time; time.sleep(60)')
        trigger = threading.Thread(target=send_interruption)
        observed = {}
        try:
            if child_signal == 'ignored':
                signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            if completion == 'interruption': trigger.start()
            try:
                result = SystemProcesses().run(
                    [sys.executable, target], cwd=pathlib.Path(target).parent,
                    environment=os.environ,
                    timeout=0.5 if completion == 'timeout' else 8,
                    data='go\\n')
                observed['outcome'] = 'returned-' + str(result.returncode)
            except subprocess.TimeoutExpired:
                observed['outcome'] = 'timeout'
            except KeyboardInterrupt:
                observed['outcome'] = 'interruption'
            pids = json.loads(pathlib.Path(marker).read_text())
            observed['owned_processes_absent'] = all(absent(pid) for pid in pids)
            observed['unrelated_guard_survived'] = not absent(guard)
        finally:
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            if trigger.is_alive(): trigger.join(timeout=5)
            signal.signal(signal.SIGUSR1, signal.SIG_IGN)
            limit = time.monotonic() + 3
            while time.monotonic() < limit:
                for pid in children():
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                try: pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError: break
                if not pid: time.sleep(0.01)
            observed['guardian_children_remaining'] = children()
            signal.alarm(0)
        print(json.dumps(observed))
        """
    )


@pytest.mark.parametrize("exit_code", [37, -signal.SIGTERM])
def test_owned_supervision_preserves_command_io_settings_and_exit(
    tmp_path: Path, exit_code: int
) -> None:
    """The private status channel must not consume stdin or mix with target output."""
    script = (
        "import os, signal, sys\n"
        "assert sys.stdin.read() == 'private stdin\\n'\n"
        "assert os.getcwd() == os.environ['EXPECTED_DIRECTORY']\n"
        "sys.stdout.buffer.write(b'out\\xff\\n'); sys.stdout.flush()\n"
        "sys.stderr.buffer.write(b'err\\xfe\\n'); sys.stderr.flush()\n"
        + (
            "os.kill(os.getpid(), signal.SIGTERM)\n"
            if exit_code < 0
            else "raise SystemExit(37)\n"
        )
    )
    environment = dict(os.environ, EXPECTED_DIRECTORY=str(tmp_path))
    result = SystemProcesses().run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        environment=environment,
        timeout=3,
        data="private stdin\n",
    )
    assert result.returncode == exit_code
    assert result.stdout == "out\ufffd\n"
    assert result.stderr == "err\ufffd\n"


def test_owned_command_restores_exec_signal_defaults(tmp_path: Path) -> None:
    """An external shell must not inherit Python's ignored broken-pipe signal."""
    shell = shutil.which("sh")
    assert shell is not None
    result = SystemProcesses().run(
        [shell, "-c", "kill -PIPE $$; exit 37"],
        cwd=tmp_path,
        environment=os.environ,
        timeout=3,
    )
    assert result.returncode == -signal.SIGPIPE


def test_unstartable_owned_command_has_fixed_private_error(tmp_path: Path) -> None:
    """Failure to exec cannot echo private argv and still preserves OS error type."""
    with pytest.raises(FileNotFoundError, match="Owned local command could not start"):
        SystemProcesses().run(
            [str(tmp_path / "private-missing-command")],
            cwd=tmp_path,
            environment=os.environ,
            timeout=3,
        )


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[BuildSnapshot, Path, Path]:
    """Build small actual inputs with independently retained inventory evidence."""
    root = tmp_path / "checkout"
    for relative in (
        "src/batocera_gow/runtime",
        "build-assets/runtime",
        "tests/assets/input",
    ):
        (root / relative).mkdir(parents=True)
    for name in INPUT_FILES:
        (root / name).write_text("fixture", encoding="utf-8")
    (root / "src/batocera_gow/__init__.py").write_text("", encoding="utf-8")
    (root / "src/batocera_gow/application.py").write_text(
        "answer = 42\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths=["tests/safe"]\n'
        'addopts=["--cov", "--cov-branch"]\nfilterwarnings=["error"]\n'
        '[tool.coverage.run]\nbranch=true\nsource=["src/batocera_gow"]\nrelative_files=true\n'
        "[tool.coverage.report]\nexclude_lines=[]\n"
        "[tool.batocera-gow.coverage]\nminimum=80\n",
        encoding="utf-8",
    )
    (root / "tests/safe").mkdir()
    (root / "tests/safe/test_application.py").write_text(
        "import runpy\ndef test_answer():\n"
        '    observed = runpy.run_path("src/batocera_gow/application.py")\n'
        '    assert observed["answer"] == 42\n',
        encoding="utf-8",
    )
    (root / "scripts").mkdir()
    shutil.copyfile(ROOT / "conftest.py", root / "conftest.py")
    shutil.copyfile(
        ROOT / "scripts/check_python_coverage.py",
        root / "scripts/check_python_coverage.py",
    )
    stage = root / "output/runtime"
    stage.mkdir(parents=True)
    stock = root / "output/stock.json"
    stock.write_text(
        '{"schema":1,"entries":{"/stock":{"sha256":"fixture"}}}', encoding="utf-8"
    )
    report = root / "output/inventory.json"
    report.write_text(
        '{"verified_stock_paths":112729,"added_paths":21786}', encoding="utf-8"
    )
    inputs = declared_inputs(root)
    image = "sha256:" + "a" * 64
    manifest = root / "output/build.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "success",
                "inventory_verified": True,
                "release": "43.1",
                "image_id": image,
                "adapter_revision": "b" * 40,
                "input_sha256": "c" * 64,
                "declared_inputs": inputs,
                "runtime_inputs": tree_source(stage),
                "preservation": {
                    "schema": 1,
                    "image": image,
                    "declared_inputs_sha256": inputs["sha256"],
                    "stock_sha256": file_sha256(stock),
                    "report": "inventory.json",
                    "report_sha256": file_sha256(report),
                    "result": {"verified_stock_paths": 112729, "added_paths": 21786},
                },
            }
        ),
        encoding="utf-8",
    )
    return (
        BuildSnapshot.verify(root, manifest, stage, Images(inputs["sha256"])),
        manifest,
        stock,
    )


@pytest.mark.parametrize(
    "damage", ["legacy", "image", "report", "stock", "diagnostic", "escape"]
)
def test_preservation_requires_actual_normal_image_bound_bytes(
    checkout: tuple[BuildSnapshot, Path, Path],
    damage: str,
) -> None:
    """A success flag, stale report or diagnostic result cannot become reuse proof."""
    snapshot, manifest, stock = checkout
    document = json.loads(manifest.read_bytes())
    if damage == "legacy":
        del document["preservation"]
    elif damage == "image":
        document["preservation"]["image"] = "sha256:" + "e" * 64
    elif damage == "report":
        (manifest.parent / "inventory.json").write_bytes(b"{}")
    elif damage == "stock":
        stock.write_bytes(b"{}")
    elif damage == "diagnostic":
        document["diagnostic_only"] = True
    else:
        document["preservation"]["report"] = "../inventory.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises((NativeError, OSError)):
        preservation_evidence(snapshot, manifest, stock)


@pytest.mark.parametrize("authorization", ["missing", "wrong-target", "wrong-root"])
def test_installed_consumer_refuses_permission_before_docker_or_ssh(
    tmp_path: Path,
    authorization: str,
) -> None:
    """Configured target knowledge cannot grant effects, even with selected dotenv."""
    marker = tmp_path / "contacted"
    executable = tmp_path / "must-not-run"
    executable.write_text(
        '#!/bin/sh\ntouch "' + str(marker) + '"\nexit 99\n', encoding="utf-8"
    )
    executable.chmod(0o700)
    settings = tmp_path / "settings.env"
    settings.write_text(
        "BATOCERA_GOW_SSH_TARGET=wolf-test\nBATOCERA_GOW_HOST_ROOT=/etc/wolf\n"
        "DOCKER=" + str(executable) + "\n",
        encoding="utf-8",
    )
    arguments = (
        []
        if authorization == "missing"
        else [
            "--authorize-native",
            "--native-authorized-target",
            "different" if authorization == "wrong-target" else "wolf-test",
            "--native-authorized-root",
            "/different" if authorization == "wrong-root" else "/etc/wolf",
        ]
    )
    result = subprocess.run(  # noqa: S603 - actual installed module with owned fixture data.
        [
            sys.executable,
            "-m",
            "batocera_gow.host.qualify",
            "--env-file",
            str(settings),
            *arguments,
        ],
        env={**os.environ, "PATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 1
    assert not marker.exists()
    assert "wolf-test" not in result.stderr
    assert str(tmp_path) not in result.stderr


@pytest.mark.parametrize("damage", ["source", "conflicting-image"])
def test_command_rejects_stale_or_conflicting_image_before_packaged_or_native(
    checkout: tuple[BuildSnapshot, Path, Path],
    tmp_path: Path,
    damage: str,
) -> None:
    """Use a real Docker process consumer and require an untouched remote boundary."""
    snapshot, manifest, stock = checkout
    observed = tmp_path / "docker-observation"
    executable = tmp_path / "docker-process.py"
    local = Images(snapshot.inputs["sha256"]).inspect(snapshot.image)
    executable.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(observed)!r}).write_text('inspected')\n"
        "assert sys.argv[1:3] == ['image', 'inspect']\n"
        f"print({json.dumps([local])!r})\n",
        encoding="utf-8",
    )
    if damage == "source":
        (snapshot.root / "uv.lock").write_text("changed source", encoding="utf-8")
    output = tmp_path / "qualification"
    result = subprocess.run(  # noqa: S603 - installed consumer and owned external process fixture.
        [
            sys.executable,
            "-m",
            "batocera_gow.host.qualify",
            "--project-root",
            str(snapshot.root),
            "--build-manifest",
            str(manifest),
            "--stock-manifest",
            str(stock),
            "--runtime-root",
            str(snapshot.runtime),
            "--output",
            str(output),
            "--authorize-native",
            "--native-authorized-target",
            "wolf-test",
            "--native-authorized-root",
            "/etc/wolf",
            "--image",
            "sha256:" + "e" * 64,
        ],
        env={
            **os.environ,
            "DOCKER": shlex.join([sys.executable, str(executable)]),
            "BATOCERA_GOW_SSH_TARGET": "wolf-test",
            "BATOCERA_GOW_HOST_ROOT": "/etc/wolf",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 1
    assert observed.exists() is (damage == "conflicting-image")
    reports = list(output.glob("*/qualification-report.json"))
    assert len(reports) == 1
    aggregate = json.loads(reports[0].read_bytes())
    assert aggregate["full_qualification"] is False
    assert aggregate["phases"]["local"]["status"] == "not-run"
    assert aggregate["phases"]["packaged"]["status"] == "not-run"
    assert aggregate["phases"]["native"]["status"] == "not-run"
    assert str(tmp_path) not in reports[0].read_text(encoding="utf-8")


def test_independent_numeric_gate_fails_after_successful_real_pytest(
    checkout: tuple[BuildSnapshot, Path, Path],
    tmp_path: Path,
) -> None:
    """Successful tests cannot waive uncovered application lines."""
    snapshot, _, _ = checkout
    (snapshot.root / "src/batocera_gow/application.py").write_text(
        "answer = 42\n"
        "if answer == 0:\n"
        "    never_run = 1\n"
        "    never_run += 1\n"
        "    never_run += 1\n",
        encoding="utf-8",
    )
    artifacts = Artifacts(tmp_path / "results", uuid.uuid4().hex)
    try:
        environment = {
            **os.environ,
            "COV_CORE_DATAFILE": str(snapshot.root / ".coverage"),
            "COVERAGE_RCFILE": "/missing-parent-coverage-config",
        }
        result = LocalChecks(snapshot.root, SystemProcesses(), environment).run(
            artifacts
        )
        assert result["status"] == "failed"
        assert record(result["pytest"]) == {"status": "passed", "exit_code": 0}
        assert record(result["line_gate"]) == {"status": "failed", "exit_code": 1}
        assert (artifacts.path / "measurement/coverage-run.json").is_file()
        assert not (snapshot.root / "coverage.json").exists()
        assert not (snapshot.root / ".coverage").exists()
    finally:
        artifacts.close()


class ContainerBoundary:
    """Model Docker state independently; execute local measurement children for real."""

    def __init__(self, *, failure: str = "none", drift: Path | None = None) -> None:
        """Choose an external fault, never manufacture application/native outcomes."""
        self.system = SystemProcesses()
        self.failure = failure
        self.drift = drift
        self.container: dict[str, object] | None = None
        self.started = 0
        self.removed = 0

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout: float,
        data: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Interpret Docker state; execute other commands as real children."""
        if command[0] != "fixture-docker":
            return self.system.run(
                command, cwd=cwd, environment=environment, timeout=timeout, data=data
            )
        arguments = list(command[1:])
        code, output = 0, ""
        if arguments[0] == "create":
            self._create(arguments, command, timeout)
        elif arguments[:2] == ["container", "inspect"]:
            code, output = (
                (0, json.dumps([self.container])) if self.container else (1, "")
            )
        elif arguments[0] == "start":
            assert arguments[-1] == "d" * 64
            assert data is not None
            self.started += 1
            if self.drift is not None:
                self.drift.write_text("changed during packaged phase", encoding="utf-8")
            # This is a Docker process response, not evidence of stock compatibility.
            code = 17 if self.failure == "check" else 0
            output = json.dumps({"status": "failed" if code else "passed"})
        elif arguments[0] == "rm":
            assert arguments[-1] == "d" * 64
            self.removed += 1
            if self.failure == "cleanup":
                code = 1
            else:
                self.container = None
        elif arguments[:2] == ["container", "ls"]:
            output = "d" * 64 if self.container else ""
        else:
            pytest.fail("Unexpected Docker operation")
        return subprocess.CompletedProcess(
            command, code, output, "private stderr must not persist"
        )

    def _create(
        self, arguments: list[str], command: Sequence[str], timeout: float
    ) -> None:
        """Allocate independent state before a possible lost creation response."""
        assert arguments[arguments.index("--network") + 1] == "none"
        assert arguments[arguments.index("--pull") + 1] == "never"
        assert arguments[-2] == "sha256:" + "a" * 64
        assert "--mount" not in arguments
        assert "--volume" not in arguments
        owner = arguments[arguments.index("--label") + 1].split("=", 1)[1]
        self.container = {
            "Id": "d" * 64,
            "Image": arguments[-2],
            "Config": {"Labels": {"io.gow.qualify.owner": owner}},
            "HostConfig": {"NetworkMode": "none"},
        }
        if self.failure == "foreign":
            self.container["Config"] = {"Labels": {"io.gow.qualify.owner": "foreign"}}
        if self.failure == "late-create":
            self.container = None
            raise subprocess.TimeoutExpired(command, timeout)
        if self.failure == "lost-create":
            raise subprocess.TimeoutExpired(command, timeout)


@pytest.mark.parametrize(
    "failure", ["none", "check", "cleanup", "foreign", "lost-create", "late-create"]
)
def test_packaged_consumer_pins_owned_image_and_unwinds_partial_creation(
    tmp_path: Path,
    failure: str,
) -> None:
    """Preserve foreign state and remove owned state after a lost create response."""
    boundary = ContainerBoundary(failure=failure)
    artifacts = Artifacts(tmp_path / "results", uuid.uuid4().hex)
    try:
        result = PackagedChecks(
            "sha256:" + "a" * 64, ["fixture-docker"], boundary, {}
        ).run(artifacts)
        assert result["status"] == ("passed" if failure == "none" else "failed")
        assert result["cleanup_complete"] is (
            failure not in ("cleanup", "foreign", "late-create")
        )
        assert boundary.removed == (0 if failure in ("foreign", "late-create") else 1)
        assert boundary.started == (
            0 if failure in ("foreign", "lost-create", "late-create") else 1
        )
        assert result["owner"]
        assert result["container_name"]
        assert "private stderr" not in (
            artifacts.path / "packaged-check.json"
        ).read_text(encoding="utf-8")
    finally:
        artifacts.close()


class InterruptedWorld(SessionWorld):
    """Raise one interruption at the remote collection boundary after allocation."""

    def __init__(self) -> None:
        """Keep later cleanup observations available after the first interruption."""
        super().__init__()
        self.interrupted = False

    def request(self, value: dict[str, object], timeout: float) -> dict[str, object]:
        """Interrupt actual coordinator execution, not a mocked session result."""
        if value["action"] == "collect" and not self.interrupted:
            self.interrupted = True
            message = "private interruption detail"
            raise InterruptedError(message)
        return super().request(value, timeout)


def assert_phase_progress(
    phases: dict[str, object],
    boundary: ContainerBoundary,
    world: SessionWorld,
    failure: str,
) -> None:
    """Require the intended fault's phase, not an earlier accidental failure."""
    local = record(phases["local"])
    expected = {"local": ("failed", 1, "not-run", 0)}.get(
        failure, ("passed", 0, "passed", 1)
    )
    assert local["status"] == expected[0]
    assert record(local["pytest"])["exit_code"] == expected[1]
    assert record(local["line_gate"])["status"] == expected[2]
    assert boundary.started == expected[3]
    if failure in ("interrupted", "native-cleanup", "none"):
        assert record(phases["packaged"])["status"] == "passed"
        assert world.allocations
    if failure == "interrupted":
        assert isinstance(world, InterruptedWorld)
        assert world.interrupted is True


@pytest.mark.parametrize(
    "failure", ["local", "packaged", "drift", "interrupted", "native-cleanup", "none"]
)
def test_qualification_runs_real_local_gate_and_maintained_native_service(
    checkout: tuple[BuildSnapshot, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """Phase barriers and native no-media/cleanup survive one complete consumer flow."""
    snapshot, manifest, stock = checkout
    if failure == "local":
        (snapshot.root / "tests/safe/test_application.py").write_text(
            "def test_failure():\n    assert False\n",
            encoding="utf-8",
        )
    boundary = ContainerBoundary(
        failure="check" if failure == "packaged" else "none",
        drift=snapshot.root / "uv.lock" if failure == "drift" else None,
    )
    world = InterruptedWorld() if failure == "interrupted" else SessionWorld()
    world.absent = True
    if failure == "native-cleanup":
        world.cleanup_failure_case = "frontend"
    monkeypatch.setattr(native_preparation, "SystemClock", lambda: world.clock)
    artifacts = Artifacts(tmp_path / "results", uuid.uuid4().hex)

    @contextmanager
    def native() -> Iterator[NativeSession]:
        owned = Artifacts(artifacts.path / "native", uuid.uuid4().hex)
        try:
            with NativeSession(
                snapshot,
                matrix_config(),
                world,
                Images(snapshot.inputs["sha256"]),
                owned,
            ) as session:
                yield session
        finally:
            owned.close()

    try:
        result = Qualification(
            snapshot,
            lambda: preservation_evidence(snapshot, manifest, stock),
            LocalChecks(snapshot.root, boundary, os.environ),
            PackagedChecks(snapshot.image, ["fixture-docker"], boundary, {}),
            native,
            artifacts=artifacts,
        ).run()
        assert result["full_qualification"] is (failure == "none")
        assert result["status"] == ("passed" if failure == "none" else "failed")
        phases = record(result["phases"])
        assert_phase_progress(phases, boundary, world, failure)
        if failure in ("local", "packaged", "drift"):
            assert record(phases["native"])["status"] == "not-run"
            assert world.allocations == []
        if failure == "local":
            assert record(phases["packaged"])["status"] == "not-run"
            assert boundary.started == 0
        if failure == "drift":
            assert result["drift"] == "detected"
        if failure == "native-cleanup":
            assert result["cleanup_complete"] is False
        if failure == "none":
            assert len(world.allocations) == len(world.removals) == 13
            native_result = record(phases["native"])
            assert native_result["full_regression_gate"] is True
            assert record(native_result["backend_counts"])["skipped-no-media"] == 6
            assert (
                native_result["emulator_exit_coverage"] == "No emulator exit coverage"
            )
        saved = (artifacts.path / "qualification-report.json").read_text(
            encoding="utf-8"
        )
        assert "private interruption detail" not in saved
        assert str(tmp_path) not in saved
        assert (artifacts.path.stat().st_mode & 0o777) == 0o700
        assert (
            (artifacts.path / "qualification-report.json").stat().st_mode & 0o777
        ) == 0o600
    finally:
        artifacts.close()
