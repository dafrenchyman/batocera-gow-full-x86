"""Behavioral stock-exit transitions, not native emulator qualification."""

import dataclasses
import errno
import math
import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.runtime.emulator_lifecycle import (
    EmulatorLifecycle,
    ExitBudgets,
    Observation,
    PrivateOutput,
    ProcessIdentity,
    TransitionError,
    stock_termination,
)


class Clock:
    """Advance deterministic monotonic time without wall-clock sleeps."""

    def __init__(self) -> None:
        """Start the monotonic fixture at zero seconds."""
        self.value = 0.0

    def now(self) -> float:
        """Return controlled monotonic seconds for lifecycle deadlines."""
        return self.value

    def sleep(self, seconds: float) -> None:
        """Advance fixture time by the requested polling interval."""
        self.value += seconds


class Runtime:
    """Model independent process, display and input boundaries with failure knobs."""

    def __init__(self) -> None:
        """Start one pinned emulator with independent failure controls."""
        self.emulator = ProcessIdentity(41, 100)
        self.stage = "playing"
        self.effects: list[str] = []
        self.failure = "none"
        self.observations = 0
        self.chord_at: int | None = None

    def permission(self) -> None:
        """Revoke the simulated input lease only after the configured transition."""
        if self.failure == "lease-lost" and self.stage != "playing":
            message = "Input permission revoked"
            raise InterruptedError(message)

    def observe(self) -> Observation:
        """Sample process state without treating diagnostics as exit proof."""
        self.observations += 1
        playing = self.stage == "playing"
        alive = playing or self.failure == "ineffective-exit"
        identity = self.emulator
        if self.failure == "wrong-pid" and self.stage != "playing":
            identity = ProcessIdentity(42, 101)
        if self.failure == "pid-reuse" and self.stage != "playing":
            identity = ProcessIdentity(41, 101)
        code = None if alive else 0
        if self.failure == "launcher-error":
            code = 2
        if self.failure == "post-launcher-error" and not playing:
            code = 2
        if self.failure == "launcher-pending":
            code = None
        if self.failure == "live-launcher-zero" and not playing:
            alive, code = True, 0
        if self.failure in ("pre-crash", "self-exit") and self.observations >= 2:
            alive, code = False, -11 if self.failure == "pre-crash" else 0
        termination = None
        if not alive and self.failure != "missing-termination":
            termination = (
                "signaled" if self.failure == "signaled-after-chord" else "exited"
            )
        return Observation(
            identity,
            alive,
            code,
            self.emulator.pid,
            self.failure != "wrong-core",
            self.failure != "blank-output",
            self.failure != "withheld-readiness",
            self.failure == "forced-teardown" and not playing,
            emulator_termination=termination,
        )

    def checkpoint(self, name: str) -> dict[str, object]:
        """Record a capture boundary or fail without fabricating evidence."""
        self.effects.append(name)
        if self.failure == "capture-lost":
            message = "Owned capture unavailable"
            raise OSError(message)
        if self.failure == "death-during-capture" and self.stage == "playing":
            self.failure = "self-exit"
        return {"path": name + ".png"}

    def guide_start(self) -> bool:
        """Send owned exit input and record its causal barrier."""
        if self.failure == "withhold-chord":
            return False
        self.effects.append("native-guide-start")
        self.chord_at = self.observations
        self.stage = "chord"
        return True


def exercise(runtime: Runtime) -> dict[str, object]:
    """Run the public transition against controlled external observations."""
    return EmulatorLifecycle(
        runtime,
        Clock(),
        ExitBudgets(startup=1, before_chord=0.2, exit=1, poll=0.05),
    ).run()


def test_chord_follows_live_output_barrier_and_observes_same_emulator_exit() -> None:
    """Require continuous live output before input and report the pinned exit."""
    runtime = Runtime()
    result = exercise(runtime)
    assert runtime.effects == ["emulator-before-exit", "native-guide-start"]
    minimum_observations = 5
    assert runtime.chord_at is not None
    assert runtime.chord_at >= minimum_observations
    assert result["emulator"] == {"pid": 41, "start": 100}
    assert result["same_emulator_exited"] is True
    assert result["launcher_code"] == 0


@pytest.mark.parametrize(
    "failure",
    [
        "launcher-error",
        "pre-crash",
        "self-exit",
        "withheld-readiness",
        "wrong-core",
        "blank-output",
        "capture-lost",
        "death-during-capture",
    ],
)
def test_prechord_failure_never_injects(failure: str) -> None:
    """Leave native input untouched when any pre-chord observation fails."""
    runtime = Runtime()
    runtime.failure = failure
    with pytest.raises((TransitionError, OSError)):
        exercise(runtime)
    assert "native-guide-start" not in runtime.effects


@pytest.mark.parametrize(
    "failure",
    [
        "ineffective-exit",
        "wrong-pid",
        "pid-reuse",
        "forced-teardown",
        "lease-lost",
        "post-launcher-error",
        "launcher-pending",
        "live-launcher-zero",
        "withhold-chord",
    ],
)
def test_incomplete_same_process_exit_fails(failure: str) -> None:
    """Reject incomplete input, lost ownership or an unobserved pinned exit."""
    runtime = Runtime()
    runtime.failure = failure
    with pytest.raises((TransitionError, InterruptedError)):
        exercise(runtime)
    assert runtime.effects == (
        ["emulator-before-exit"]
        if failure == "withhold-chord"
        else ["emulator-before-exit", "native-guide-start"]
    )


@pytest.mark.parametrize("diagnostic", ["signaled-after-chord", "missing-termination"])
def test_diagnostic_classification_does_not_veto_observed_exit(diagnostic: str) -> None:
    """Keep diagnostic rejection independent of observed shortcut acceptance."""
    runtime = Runtime()
    runtime.failure = diagnostic
    result = exercise(runtime)
    assert result["same_emulator_exited"] is True
    assert result["launcher_code"] == 0
    assert "emulator_termination" not in result
    assert runtime.effects == ["emulator-before-exit", "native-guide-start"]


def test_prechord_readiness_recovery_requires_a_new_continuous_interval() -> None:
    """An earlier live/output sample cannot survive a later pre-chord gap."""
    clock = Clock()

    class InterruptedReadiness(Runtime):
        """Lose and recover readiness within the continuous pre-chord interval."""

        def __init__(self) -> None:
            """Retain the observed gap and actual input-delivery time."""
            super().__init__()
            self.gap_observed = False
            self.chord_time: float | None = None

        def observe(self) -> Observation:
            """Expose a temporary readiness gap without changing process identity."""
            row = super().observe()
            gap_start, gap_end = 0.1, 0.25
            if self.stage == "playing" and gap_start <= clock.now() < gap_end:
                self.gap_observed = True
                return dataclasses.replace(row, core_loaded=False)
            return row

        def guide_start(self) -> bool:
            """Record the actual chord time after readiness has recovered."""
            self.chord_time = clock.now()
            return super().guide_start()

    runtime = InterruptedReadiness()
    result = EmulatorLifecycle(
        runtime,
        clock,
        ExitBudgets(startup=1, before_chord=0.2, exit=1, poll=0.05),
    ).run()
    assert runtime.gap_observed is True
    earliest_chord = 0.45
    assert runtime.chord_time is not None
    assert runtime.chord_time >= earliest_chord
    assert result["same_emulator_exited"] is True


@pytest.mark.parametrize("value", [0, -1, math.inf, math.nan])
def test_unbounded_or_nonpositive_deadlines_are_rejected(value: float) -> None:
    """Refuse deadlines that cannot bound an owned lifecycle operation."""
    with pytest.raises(ValueError, match=r"\S"):
        ExitBudgets(exit=value)


class ProcessRuntime(Runtime):
    """Use real pidfds and filesystem readiness at the same public boundary."""

    def __init__(self, child: subprocess.Popen[bytes], ready: Path) -> None:
        """Pin the owned child with a pidfd and borrow its readiness path."""
        super().__init__()
        self.child, self.ready = child, ready
        self.descriptor = os.pidfd_open(child.pid)
        self.emulator = ProcessIdentity(child.pid, 1)
        self.sent = False

    def observe(self) -> Observation:
        """Observe real pidfd liveness and launcher completion independently."""
        row = super().observe()
        alive = not bool(select.select([self.descriptor], [], [], 0)[0])
        code = self.child.poll()
        termination = None
        if code is not None:
            termination = "signaled" if code < 0 else "exited"
        return dataclasses.replace(
            row,
            alive=alive,
            launcher_code=code,
            rendered_content=self.ready.is_file(),
            emulator_termination=termination,
        )

    def guide_start(self) -> bool:
        """Send the exit request through the owned child's input pipe."""
        # This is a host process seam, not synthetic native input proof.
        super().guide_start()
        stream = self.child.stdin
        if stream is None:
            message = "Process fixture has no owned input channel"
            raise RuntimeError(message)
        stream.write(b"exit\n")
        stream.flush()
        self.child.wait(timeout=2)
        return True


def test_real_process_exit_requires_readiness_and_owned_input(tmp_path: Path) -> None:
    """Observe a real pidfd exit only after readiness and owned pipe input."""
    ready = tmp_path / "ready"
    child = subprocess.Popen(  # noqa: S603 - Run only the controlled readiness/exit fixture.
        [
            sys.executable,
            "-c",
            (
                "import pathlib,sys; pathlib.Path(sys.argv[1]).touch(); "
                "print('ready', flush=True); sys.stdin.buffer.readline()"
            ),
            str(ready),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    runtime = ProcessRuntime(child, ready)
    try:
        output = child.stdout
        assert output is not None
        assert select.select([output], [], [], 2)[0], "Process readiness timed out"
        assert output.readline() == b"ready\n"
        assert ready.is_file()
        result = exercise(runtime)
        assert child.returncode == 0
        assert result["emulator"] == {"pid": child.pid, "start": 1}
        assert runtime.effects == ["emulator-before-exit", "native-guide-start"]
    finally:
        os.close(runtime.descriptor)
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=2)
        if child.stdin is not None:
            child.stdin.close()
        if child.stdout is not None:
            child.stdout.close()


class DiagnosticProcessRuntime(ProcessRuntime):
    """Keep real process exit independent of rejected private diagnostics."""

    def __init__(
        self, child: subprocess.Popen[bytes], ready: Path, output: PrivateOutput
    ) -> None:
        """Borrow the private output consumer alongside the pinned child."""
        super().__init__(child, ready)
        self.output = output

    def observe(self) -> Observation:
        """Attach only complete private diagnostics to actual process state."""
        row = super().observe()
        complete = (
            self.output.read_complete(timeout=2)
            if row.launcher_code is not None
            else None
        )
        return dataclasses.replace(
            row,
            emulator_termination=(
                stock_termination(complete).kind if complete is not None else None
            ),
        )


def test_observed_process_exit_passes_with_logging_error_and_no_frontend(
    tmp_path: Path,
) -> None:
    """Exercise exit acceptance, not native input, graceful shutdown or recovery."""
    ready = tmp_path / "ready"
    child = subprocess.Popen(  # noqa: S603 - Run only the controlled logging-error fixture.
        [
            sys.executable,
            "-c",
            (
                "import logging,pathlib,sys; "
                "pathlib.Path(sys.argv[1]).touch(); "
                "print('ready', flush=True); "
                "sys.stdin.buffer.readline(); "
                "logging.error('private diagnostic', 'private argument')"
            ),
            str(ready),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream = child.stderr
    assert stream is not None
    retained = PrivateOutput(stream)
    runtime = DiagnosticProcessRuntime(child, ready, retained)
    try:
        output = child.stdout
        assert output is not None
        assert select.select([output], [], [], 2)[0], "Process readiness timed out"
        assert output.readline() == b"ready\n"
        assert runtime.observe().alive is True
        result = exercise(runtime)
        assert child.returncode == 0
        assert runtime.observe().alive is False
        complete = retained.read_complete(timeout=2)
        assert complete is not None
        classification = stock_termination(complete)
        assert classification.kind is None
        assert classification.reason == "logging-error"
        assert result["emulator"] == {"pid": child.pid, "start": 1}
        assert result["same_emulator_exited"] is True
        assert result["launcher_code"] == 0
        assert result.get("emulator_termination") is None
        assert result.get("frontend_ready") is not True
        assert runtime.effects == ["emulator-before-exit", "native-guide-start"]
        minimum_observations = 5
        assert runtime.chord_at is not None
        assert runtime.chord_at >= minimum_observations
    finally:
        os.close(runtime.descriptor)
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=2)
        retained.close()
        if child.stdin is not None:
            child.stdin.close()
        if child.stdout is not None:
            child.stdout.close()


def stock_log(*messages: bytes) -> bytes:
    """Use the inspected stock logger envelope, without native-proof claims."""
    return b"".join(
        b"2026-10-29 12:00:00,000 " + message + b"\n" for message in messages
    )


@pytest.mark.parametrize(
    ("output", "expected", "reason"),
    [
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            "exited",
            None,
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:808):launch "
                    b"Emulator terminated by signal (Terminated: 15)"
                ),
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            "signaled",
            None,
        ),
        (b"", None, "unterminated-output"),
        (
            stock_log(
                b"DEBUG (emulatorlauncher.py:810):launch "
                b"Exiting configgen with status 0"
            ),
            None,
            "launch-record-count",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                b"ERROR (emulatorlauncher.py:780):launch configgen exception: ",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            None,
            "exception-record",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            )[:-1],
            None,
            "unterminated-output",
        ),
        (b"--- Logging error ---\n", None, "logging-error"),
        (
            b"private prefix emulatorlauncher.py malformed\n",
            None,
            "malformed-launcher-record",
        ),
        (
            b"private prefix Traceback (most recent call last):\n",
            None,
            "unscoped-termination-marker",
        ),
        (
            stock_log(
                b"DEBUG (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            None,
            "invalid-version-record",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 1"
                ),
            ),
            None,
            "invalid-final-record",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            )
            + b"private trailing output\n",
            None,
            "trailing-output",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                b"WARNING (emulatorlauncher.py:808):launch private unknown record",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            None,
            "unrecognized-launch-record",
        ),
        (
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ),
            None,
            "launch-record-count",
        ),
    ],
)
def test_stock_termination_requires_complete_unambiguous_launcher_records(
    output: bytes, expected: str | None, reason: str | None
) -> None:
    """Classify only bounded complete stock bytes and retain fixed rejection reasons."""
    classification = stock_termination(output)
    assert classification.kind == expected
    assert classification.reason == reason


@pytest.mark.parametrize(
    ("exception", "category", "condition", "number"),
    [
        (
            b"TypeError: not all arguments converted during string formatting",
            "TypeError",
            "format-arguments",
            None,
        ),
        (
            b"ValueError: I/O operation on closed file.",
            "ValueError",
            "closed-stream",
            None,
        ),
        (
            b"UnicodeEncodeError: private-title-secret",
            "UnicodeEncodeError",
            "encoding-error",
            None,
        ),
        (
            b"BrokenPipeError: [Errno 32] private-title-secret",
            "BrokenPipeError",
            "os-error",
            32,
        ),
        (b"OSError: [Errno 5] private-title-secret", "OSError", "os-error", 5),
        (b"OSError: [Errno 99999] private-title-secret", "OSError", "unknown", None),
        (b"OSError: [Errno 0] private-title-secret", "OSError", "unknown", None),
        (b"TypeError: private-title-secret", "TypeError", "unknown", None),
        (b"ValueError: private-title-secret", "ValueError", "unknown", None),
        (b"PrivateError: private-title-secret", "unknown", "unknown", None),
    ],
)
def test_logging_error_retains_only_fixed_categories_and_pinned_frames(
    exception: bytes, category: str, condition: str, number: int | None
) -> None:
    """Exception messages and unknown frame identities cannot cross the parser."""
    output = (
        b"--- Logging error ---\nTraceback (most recent call last):\n"
        b'  File "/usr/lib/python3.12/logging/__init__.py", line 1163, in emit\n'
        b"    private-title-secret\n"
        b'  File "/private-title-secret", line 123, in private_function\n'
        + exception
        + (
            b"\nCall stack:\n"
            b'  File "/usr/lib/python3.12/site-packages/configgen/utils/'
            b'logger.py", line 47, in write\n'
            b"Message: 'private-title-secret'\nArguments: ('private-title-secret',)\n"
        )
    )
    decision = stock_termination(output)
    assert decision.kind is None
    assert decision.reason == "logging-error"
    evidence = decision.logging_error
    assert evidence is not None
    assert evidence.exception == category
    assert evidence.condition == condition
    assert evidence.errno == number
    assert evidence.frames == (("stdlib-stream-emit", 1163), ("stock-stream-write", 47))
    assert evidence.unknown_frames is True
    assert "private-title-secret" not in repr(dataclasses.asdict(decision))
    assert "private_function" not in repr(dataclasses.asdict(decision))


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (b"Traceback (most recent call last):\nTypeError: private\n", "unknown"),
        (b"x" * 8193, "truncated"),
        (b"\n" * 129, "truncated"),
        (
            (
                b"Traceback (most recent call last):\nTypeError: private\n"
                b"Call stack:\nMessage: private\n"
            ),
            "recognized",
        ),
    ],
)
def test_logging_error_bounds_and_missing_envelope_never_supply_exit(
    body: bytes, status: str
) -> None:
    """Missing boundaries and oversized diagnostics stay explicitly incomplete."""
    decision = stock_termination(b"--- Logging error ---\n" + body + b"\n")
    assert decision.kind is None
    assert decision.reason == "logging-error"
    assert decision.logging_error is not None
    assert decision.logging_error.status == status


def test_logging_error_does_not_read_message_arguments_as_traceback() -> None:
    """A second error or private payload cannot become the first exception."""
    decision = stock_termination(
        b"--- Logging error ---\nTraceback (most recent call last):\n"
        b"PrivateError: private\nCall stack:\nMessage: private\n"
        b"TypeError: not all arguments converted during string formatting\n"
        b"--- Logging error ---\nValueError: I/O operation on closed file.\n"
    )
    assert decision.logging_error is not None
    assert decision.logging_error.exception == "unknown"
    assert decision.logging_error.condition == "unknown"
    assert decision.logging_error.additional_markers is True


@pytest.mark.parametrize(("count", "status"), [(8, "recognized"), (9, "truncated")])
def test_logging_error_bounds_known_frames(count: int, status: str) -> None:
    """Even repeated recognized frames cannot grow the published record."""
    output = (
        b"--- Logging error ---\nTraceback (most recent call last):\n"
        + b'  File "/usr/lib/python3.12/logging/__init__.py", line 1163, in emit\n'
        * count
        + b"OSError: [Errno 5] private\nCall stack:\nMessage: private\n"
    )
    decision = stock_termination(output)
    assert decision.kind is None
    evidence = decision.logging_error
    assert evidence is not None
    assert evidence.status == status
    maximum_frames = 8
    assert len(evidence.frames) == (maximum_frames if count == maximum_frames else 0)


@pytest.mark.parametrize(
    "frame",
    [
        b'  File "/private/logging/__init__.py", line 1163, in emit',
        b'  File "/usr/lib/python3.12/logging/__init__.py", line 1162, in emit',
        (
            b'  File "/usr/lib/python3.12/logging/__init__.py", '
            b"line 1163, in private_function"
        ),
    ],
)
def test_logging_error_rejects_public_frame_lookalikes(frame: bytes) -> None:
    """A basename, line or function match alone cannot identify a stock frame."""
    decision = stock_termination(
        b"--- Logging error ---\nTraceback (most recent call last):\n"
        + frame
        + b"\nValueError: private\nCall stack:\nMessage: private\n"
    )
    evidence = decision.logging_error
    assert evidence is not None
    assert evidence.frames == ()
    assert evidence.unknown_frames is True


@pytest.mark.parametrize(
    ("size", "status"), [(8192, "recognized"), (8193, "truncated")]
)
def test_logging_error_byte_boundary_includes_message_delimiter(
    size: int, status: str
) -> None:
    """The envelope limit accepts its boundary, not one extra private byte."""
    prefix = b"--- Logging error ---\nTraceback (most recent call last):\n"
    suffix = b"\nTypeError: private\nCall stack:\nMessage: "
    output = (
        prefix
        + b" " * (size - len(prefix) - len(suffix))
        + suffix
        + b"private-title-secret\n"
    )
    decision = stock_termination(output)
    evidence = decision.logging_error
    assert decision.kind is None
    assert evidence is not None
    assert evidence.status == status
    assert "private-title-secret" not in repr(dataclasses.asdict(decision))


@pytest.mark.parametrize(("count", "status"), [(128, "recognized"), (129, "truncated")])
def test_logging_error_line_boundary_is_finite(count: int, status: str) -> None:
    """Short-line diagnostics obey the line limit independently of byte size."""
    output = (
        b"--- Logging error ---\nTraceback (most recent call last):\n"
        + b" \n" * (count - 4)
        + b"TypeError: private\nCall stack:\nMessage: private\n"
    )
    decision = stock_termination(output)
    assert decision.kind is None
    assert decision.logging_error is not None
    assert decision.logging_error.status == status


@pytest.mark.parametrize("prefix", [b"", b"emulator diagnostic without newline"])
@pytest.mark.parametrize(
    "negative",
    [
        (
            b"DEBUG (emulatorlauncher.py:808):launch "
            b"Emulator terminated by signal (SIGTERM)"
        ),
        (b"ERROR (emulatorlauncher.py:780):launch configgen exception: failure"),
        b"WARNING (emulatorlauncher.py:808):launch ambiguous termination",
        (b"DEBUG (emulatorlauncher.py:808):launch Emulator terminated by signal ("),
        b"DEBUG (emulatorlauncher.py:808:launch incomplete termination",
    ],
)
def test_unterminated_stock_records_remain_diagnostic_not_natural_exit_proof(
    prefix: bytes, negative: bytes
) -> None:
    """Reject negative stock records even when adjacent writes lack a newline."""
    output = (
        stock_log(b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1")
        + prefix
        + stock_log(negative)
        + stock_log(
            b"DEBUG (emulatorlauncher.py:810):launch Exiting configgen with status 0"
        )
    )
    assert stock_termination(output).kind != "exited"


@pytest.mark.parametrize("negative", [False, True])
def test_real_merged_stream_preserves_split_stock_records(*, negative: bool) -> None:
    """Separate writes and stderr preserve bounded diagnostic classification."""
    output = stock_log(b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1")
    if negative:
        output += b"emulator diagnostic without newline" + stock_log(
            b"DEBUG (emulatorlauncher.py:808):launch "
            b"Emulator terminated by signal (SIGTERM)"
        )
    output += stock_log(
        b"DEBUG (emulatorlauncher.py:810):launch Exiting configgen with status 0"
    )
    child = subprocess.Popen(  # noqa: S603 - Run only controlled split byte writes.
        [
            sys.executable,
            "-c",
            (
                "import os,sys; data=bytes.fromhex(sys.argv[1]); "
                "[os.write(1 if n % 2 else 2, data[n:n+7]) "
                "for n in range(0, len(data), 7)]"
            ),
            output.hex(),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stream = child.stdout
    assert stream is not None
    retained = PrivateOutput(stream)
    try:
        assert child.wait(timeout=5) == 0
        complete = retained.read_complete(timeout=2)
        assert complete is not None
        assert complete == output
        decision = stock_termination(complete)
        assert decision.kind == (None if negative else "exited")
        assert decision.reason == ("malformed-launcher-record" if negative else None)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
        retained.close()


def test_complete_private_stream_at_retention_limit_can_classify_stock_logs() -> None:
    """Exactly 8 MiB remains complete and available for diagnostic parsing."""
    version = stock_log(b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1")
    final = stock_log(
        b"DEBUG (emulatorlauncher.py:810):launch Exiting configgen with status 0"
    )
    child = subprocess.Popen(  # noqa: S603 - Run only the controlled retention-limit fixture.
        [
            sys.executable,
            "-c",
            (
                "import sys; start,end=map(bytes.fromhex, sys.argv[1:]); "
                "fill=8*1024*1024-len(start)-len(end); "
                "sys.stdout.buffer.write(start + b'x'*(fill-1) + b'\\n' + end)"
            ),
            version.hex(),
            final.hex(),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stream = child.stdout
    assert stream is not None
    retained = PrivateOutput(stream)
    try:
        assert child.wait(timeout=5) == 0
        complete = retained.read_complete(timeout=2)
        assert complete is not None
        assert len(complete) == 8 * 1024 * 1024
        decision = stock_termination(complete)
        assert decision.kind == "exited"
        assert decision.reason is None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
        retained.close()


def test_oversized_private_stream_drains_while_child_remains_live() -> None:
    """Exceed pipe capacity and the retention cap before waiting for owned input."""
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import os,sys; "
                "[os.write(1, b'x' * 65536) for _ in range(192)]; "
                "print('drained', file=sys.stderr, flush=True); "
                "sys.stdin.buffer.readline()"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream, ready, commands = child.stdout, child.stderr, child.stdin
    assert stream is not None
    assert ready is not None
    assert commands is not None
    retained = PrivateOutput(stream)
    try:
        assert select.select([ready], [], [], 5)[0], "Oversize writer blocked"
        assert ready.readline() == b"drained\n"
        assert child.poll() is None
        assert retained.retained_bytes == 8 * 1024 * 1024
        assert retained.read_complete(timeout=0.01) is None
        observation = retained.observation()
        assert observation["overflow"] is True
        assert observation["eof"] is False
        assert observation["read_failed"] is False
        commands.write(b"exit\n")
        commands.flush()
        assert child.wait(timeout=5) == 0
        assert retained.read_complete(timeout=2) is None
        assert retained.observation()["eof"] is True
        assert retained.retained_bytes == 8 * 1024 * 1024
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
        retained.close()
        commands.close()
        ready.close()


def test_private_stream_close_failure_still_discards_retained_bytes() -> None:
    """A failed pipe close cannot leave private output retained after cleanup."""
    reader, writer = os.pipe()
    with os.fdopen(writer, "wb", buffering=0) as sink:
        sink.write(b"private emulator output\n")
    with os.fdopen(reader, "rb", buffering=0) as stream:
        retained = PrivateOutput(stream)
        try:
            assert retained.read_complete(timeout=2) == b"private emulator output\n"
            os.close(stream.fileno())
            with pytest.raises(OSError, check=lambda error: error.errno == errno.EBADF):
                retained.close()
            assert retained.retained_bytes == 0
            assert retained.read_complete(timeout=0.01) is None
        finally:
            retained.close()


def test_launcher_completion_without_stream_eof_keeps_classification_unavailable() -> (
    None
):
    """An inherited writer cannot supply complete diagnostic stream bytes."""
    reader, writer = os.pipe()
    retained = PrivateOutput(os.fdopen(reader, "rb", buffering=0))
    child = subprocess.Popen(  # noqa: S603 - Run only the controlled inherited-writer fixture.
        [
            sys.executable,
            "-c",
            "import os,sys; os.write(1, bytes.fromhex(sys.argv[1]))",
            stock_log(
                b"INFO (emulatorlauncher.py:700):launch Batocera version: 43.1",
                (
                    b"DEBUG (emulatorlauncher.py:810):launch "
                    b"Exiting configgen with status 0"
                ),
            ).hex(),
        ],
        stdout=writer,
        stderr=subprocess.STDOUT,
    )
    try:
        assert child.wait(timeout=5) == 0
        # Keep the extra writer open, as a surviving stock descendant could.
        assert retained.read_complete(timeout=0.05) is None
        observation = retained.observation()
        assert observation["eof"] is False
        assert observation["overflow"] is False
        assert observation["read_failed"] is False
        retained.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
        os.close(writer)
        retained.close()


class SignaledProcessRuntime(ProcessRuntime):
    """Track a test-sent signal even when the launcher normalizes its status."""

    def observe(self) -> Observation:
        """Keep teardown attribution even when the launcher normalizes status."""
        row = super().observe()
        return dataclasses.replace(
            row,
            launcher_code=0 if not row.alive else None,
            forced_teardown=self.sent,
        )

    def guide_start(self) -> bool:
        """Terminate only the pinned child and record the forced teardown."""
        Runtime.guide_start(self)
        self.sent = True
        signal.pidfd_send_signal(self.descriptor, signal.SIGTERM)
        self.child.wait(timeout=2)
        return True


def test_sent_signal_cannot_pass_even_with_normalized_launcher_zero(
    tmp_path: Path,
) -> None:
    """Reject teardown-induced death despite a normalized zero launcher status."""
    ready = tmp_path / "ready"
    child = subprocess.Popen(  # noqa: S603 - Run only the controlled owned-signal fixture.
        [
            sys.executable,
            "-c",
            (
                "import pathlib,sys; pathlib.Path(sys.argv[1]).touch(); "
                "print('ready', flush=True); sys.stdin.buffer.readline()"
            ),
            str(ready),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    runtime = SignaledProcessRuntime(child, ready)
    try:
        output = child.stdout
        assert output is not None
        assert select.select([output], [], [], 2)[0], "Process readiness timed out"
        assert output.readline() == b"ready\n"
        with pytest.raises(TransitionError):
            exercise(runtime)
        assert child.returncode == -signal.SIGTERM
        assert runtime.observe().launcher_code == 0
        assert runtime.effects == ["emulator-before-exit", "native-guide-start"]
    finally:
        os.close(runtime.descriptor)
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=2)
        if child.stdin is not None:
            child.stdin.close()
        if child.stdout is not None:
            child.stdout.close()
