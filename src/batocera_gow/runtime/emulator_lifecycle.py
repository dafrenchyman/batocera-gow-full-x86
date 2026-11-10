"""Bounded stock-emulator exit assertions shared by packaged native cases."""

import math
import os
import re
import select
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Protocol

_LOGGING_BYTE_LIMIT = 8192
_LOGGING_LINE_LIMIT = 128
_LOGGING_MINIMUM_LINES = 4
_LOGGING_FRAME_LIMIT = 8
_MAX_ERRNO = 4095
_NORMAL_RECORD_COUNT = 2
_SIGNAL_RECORD_COUNT = 3
_PRIVATE_BYTE_LIMIT = 8 * 1024 * 1024
_SNAPSHOT_BYTE_LIMIT = 65536

# The inspected stock launcher logs its child's signal before normalizing the
# negative subprocess status to zero. No strace, ptrace or stock rewrite is used.
STOCK_LAUNCHER_SHA256 = (
    # pragma: allowlist nextline secret
    "73313380a3d40a44580c2e046eadf1f2b8c315cf475a0d56dd0a916e0b0a6a1f"
)

# Exact frame identities from the hash-checked public stock files. Unknown
# paths/functions/lines are never copied, including same-basename lookalikes.
_STDLIB_LOGGING = b"/usr/lib/python3.12/logging/__init__.py"
_STOCK_LOGGER = b"/usr/lib/python3.12/site-packages/configgen/utils/logger.py"
_STOCK_LAUNCHER = b"/usr/lib/python3.12/site-packages/configgen/emulatorlauncher.py"
_LOGGING_FRAMES = {
    (_STDLIB_LOGGING, b"emit", 1160): "stdlib-stream-emit",
    (_STDLIB_LOGGING, b"emit", 1163): "stdlib-stream-emit",
    (_STDLIB_LOGGING, b"emit", 1164): "stdlib-stream-emit",
    (_STDLIB_LOGGING, b"format", 999): "stdlib-handler-format",
    (_STDLIB_LOGGING, b"format", 703): "stdlib-message-format",
    (_STDLIB_LOGGING, b"getMessage", 392): "stdlib-message-interpolation",
    (_STDLIB_LOGGING, b"flush", 1144): "stdlib-stream-flush",
    (_STOCK_LOGGER, b"emit", 17): "stock-handler-emit",
    (_STOCK_LOGGER, b"flush", 27): "stock-handler-flush",
    (_STOCK_LOGGER, b"write", 47): "stock-stream-write",
    (_STOCK_LOGGER, b"flush", 57): "stock-stream-flush",
    (_STOCK_LAUNCHER, b"runCommand", 595): "stock-emulator-stdout-log",
    (_STOCK_LAUNCHER, b"runCommand", 596): "stock-emulator-stderr-log",
    (_STOCK_LAUNCHER, b"launch", 683): "stock-signal-log",
    (_STOCK_LAUNCHER, b"launch", 686): "stock-final-log",
}
_LOGGING_EXCEPTIONS = {
    name.encode("ascii"): name
    for name in (
        "TypeError",
        "ValueError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "UnicodeEncodeError",
        "UnicodeDecodeError",
        "UnicodeTranslateError",
        "OSError",
        "BrokenPipeError",
        "BlockingIOError",
        "PermissionError",
        "FileNotFoundError",
        "IsADirectoryError",
        "NotADirectoryError",
        "InterruptedError",
        "TimeoutError",
        "RuntimeError",
        "RecursionError",
    )
}
_OS_EXCEPTIONS = {
    "OSError",
    "BrokenPipeError",
    "BlockingIOError",
    "PermissionError",
    "FileNotFoundError",
    "IsADirectoryError",
    "NotADirectoryError",
    "InterruptedError",
    "TimeoutError",
}


@dataclass(frozen=True)
class LoggingErrorAttribution:
    """Describe only the first bounded logging envelope, never its private text.

    Frame roles are exact public-stock locations, not verified runtime stack
    provenance. This diagnostic cannot establish emulator death or natural exit.
    Additional errors are indicated, not parsed into an unbounded report.
    """

    status: str = "unknown"
    exception: str = "unknown"
    condition: str = "unknown"
    errno: int | None = None
    frames: tuple[tuple[str, int], ...] = ()
    unknown_frames: bool = False
    additional_markers: bool = False


def _logging_error(output: bytes) -> LoggingErrorAttribution:
    """Reduce one private error to allowlisted categories within 8 KiB/128 lines."""
    marker = b"--- Logging error ---"
    start = output.index(marker)
    end = output.find(marker, start + len(marker))
    additional = end != -1
    if end == -1:
        end = len(output)
    block = output[start : min(end, start + _LOGGING_BYTE_LIMIT + 1)]
    # Stop before Message/Arguments, even when either contains fake traceback.
    message_marker = b"\nMessage: "
    message = block.find(message_marker)
    if message != -1 and message + len(message_marker) <= _LOGGING_BYTE_LIMIT:
        block = block[:message]
    if len(block) > _LOGGING_BYTE_LIMIT:
        return LoggingErrorAttribution(
            status="truncated", additional_markers=additional
        )
    lines = block.splitlines()
    if len(lines) > _LOGGING_LINE_LIMIT:
        return LoggingErrorAttribution(
            status="truncated", additional_markers=additional
        )
    if (
        (start > 0 and output[start - 1 : start] != b"\n")
        or len(lines) < _LOGGING_MINIMUM_LINES
        or lines[0] != marker
        or lines[1] != b"Traceback (most recent call last):"
        or b"Call stack:" not in lines
        or message == -1
    ):
        return LoggingErrorAttribution(additional_markers=additional)
    return _attribute_logging_lines(lines, additional=additional)


def _logging_exception(line: bytes) -> tuple[str, str, int | None]:
    """Discard exception text after matching fixed public error categories."""
    name, separator, detail = line.partition(b": ")
    exception = _LOGGING_EXCEPTIONS.get(name, "unknown") if separator else "unknown"
    condition = "unknown"
    number = None
    if exception == "ValueError" and detail == b"I/O operation on closed file.":
        condition = "closed-stream"
    elif exception == "TypeError" and detail in (
        b"not all arguments converted during string formatting",
        b"not enough arguments for format string",
        b"format requires a mapping",
    ):
        condition = "format-arguments"
    elif exception in (
        "UnicodeEncodeError",
        "UnicodeDecodeError",
        "UnicodeTranslateError",
    ):
        condition = "encoding-error"
    elif exception in _OS_EXCEPTIONS:
        match = re.match(rb"\[Errno ([0-9]{1,4})\](?: |$)", detail)
        if match is not None and 1 <= int(match[1]) <= _MAX_ERRNO:
            condition = "os-error"
            number = int(match[1])
    return exception, condition, number


def _attribute_logging_lines(
    lines: list[bytes], *, additional: bool
) -> LoggingErrorAttribution:
    """Map bounded traceback locations without retaining private source text."""
    stack = lines.index(b"Call stack:")
    exception, condition, number = _logging_exception(lines[stack - 1])
    frames: list[tuple[str, int]] = []
    unknown_frames = False
    for line in lines[2:]:
        if not line.startswith(b'  File "'):
            continue
        match = re.fullmatch(
            rb'  File "([^"\r\n]+)", line ([0-9]{1,4}), in ([A-Za-z_][A-Za-z0-9_]*)',
            line,
        )
        role = None
        frame_line = 0
        if match is not None:
            frame_line = int(match[2])
            role = _LOGGING_FRAMES.get((match[1], match[3], frame_line))
        if role is None:
            unknown_frames = True
        elif len(frames) < _LOGGING_FRAME_LIMIT:
            frames.append((role, frame_line))
        else:
            return LoggingErrorAttribution(
                status="truncated", additional_markers=additional
            )
    return LoggingErrorAttribution(
        status="recognized" if exception != "unknown" else "unknown",
        exception=exception,
        condition=condition,
        errno=number,
        frames=tuple(frames),
        unknown_frames=unknown_frames,
        additional_markers=additional,
    )


@dataclass(frozen=True)
class TerminationClassification:
    """Retain a diagnostic stock-log classification or fixed rejection category.

    A reason describes a parser predicate, not the emulator's cause of death.
    No field contains launcher messages, paths or private exception text.
    """

    kind: str | None
    reason: str | None
    logging_error: LoggingErrorAttribution | None = None


def stock_termination(output: bytes) -> TerminationClassification:
    """Classify bounded private stock output for diagnostics, never acceptance.

    The caller binds the stream to the pinned launcher's child and verifies the
    source hash. Missing, truncated, exceptional or ambiguous records leave the
    mechanism unknown without vetoing independently observed shortcut exit.
    Raw output can contain private configuration and is never exported.

    Args:
        output: Complete private bytes from the hash-verified stock launcher.

    Returns:
        An exited/signaled classification, or no kind with the first fixed
        rejection category. Only complete bounded private bytes may be supplied.
    """
    if not output.endswith(b"\n"):
        return TerminationClassification(None, "unterminated-output")
    if b"--- Logging error ---" in output:
        return TerminationClassification(None, "logging-error", _logging_error(output))
    lines = output.splitlines()
    records, reason = _launch_records(lines)
    if reason is not None:
        return TerminationClassification(None, reason)
    return _classify_launch_records(records, lines)


def _launch_records(
    lines: list[bytes],
) -> tuple[list[tuple[bytes, bytes]], str | None]:
    """Collect scoped launcher records while rejecting damaged or stray markers."""
    records: list[tuple[bytes, bytes]] = []
    for line in lines:
        match = re.fullmatch(
            rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} "
            rb"([A-Z]+) \(emulatorlauncher.py:[0-9]+\):([A-Za-z_][A-Za-z0-9_]*) (.*)",
            line,
        )
        if match is not None and match[2] == b"launch":
            records.append((match[1], match[3]))
        elif match is None and b"emulatorlauncher.py" in line:
            # Emulator stdout/stderr may prefix or damage a launcher record.
            return records, "malformed-launcher-record"
        elif any(
            marker in line
            for marker in (
                b"Emulator terminated by signal",
                b"configgen exception",
                b"Traceback (most recent call last):",
            )
        ):
            return records, "unscoped-termination-marker"
    return records, None


def _launch_record_rejection(
    records: list[tuple[bytes, bytes]], lines: list[bytes]
) -> str | None:
    """Check bounded launch envelope ordering before indexing its middle record."""
    if len(records) not in (_NORMAL_RECORD_COUNT, _SIGNAL_RECORD_COUNT):
        return "launch-record-count"
    if records[0][0] != b"INFO" or not records[0][1].startswith(b"Batocera version: "):
        return "invalid-version-record"
    if records[-1] != (b"DEBUG", b"Exiting configgen with status 0"):
        return "invalid-final-record"
    if not lines[-1].endswith(b"):launch Exiting configgen with status 0"):
        return "trailing-output"
    return None


def _classify_launch_records(
    records: list[tuple[bytes, bytes]], lines: list[bytes]
) -> TerminationClassification:
    """Classify a validated stock envelope without treating it as exit proof."""
    reason = _launch_record_rejection(records, lines)
    if reason is not None:
        return TerminationClassification(None, reason)
    if len(records) == _NORMAL_RECORD_COUNT:
        return TerminationClassification("exited", None)
    if records[1][0] == b"DEBUG" and re.fullmatch(
        rb"Emulator terminated by signal \([^\r\n]+\)", records[1][1]
    ):
        return TerminationClassification("signaled", None)
    if b"configgen exception" in records[1][1]:
        return TerminationClassification(None, "exception-record")
    return TerminationClassification(None, "unrecognized-launch-record")


class OutputPipe(Protocol):
    """Owned output pipe operations required by the private consumer."""

    def fileno(self) -> int:
        """Return the descriptor owned by this pipe."""
        ...

    def close(self) -> None:
        """Close the owned descriptor."""
        ...


class PrivateOutput:
    """Drain an owned child's pipe while retaining at most 8 MiB in memory.

    Excess bytes are discarded, not written to disk. Oversize, read failure
    and cancellation make bytes unavailable. Complete reads also require EOF;
    nonblocking snapshots can expose a bounded, incomplete stream.
    The caller owns process deadlines and must close this sink during cleanup.
    Raw bytes are private and must never be exported as diagnostic artifacts.
    """

    def __init__(self, stream: OutputPipe) -> None:
        """Take ownership of the pipe and start its bounded background reader.

        Args:
            stream: Child output pipe whose ownership transfers to this sink.
        """
        self._stream = stream
        self._buffer = bytearray()
        self._overflow = False
        self._eof = False
        self._failed = False
        self._lock = Lock()
        self._stop = Event()
        self._thread = Thread(target=self._drain, daemon=True)
        self._thread.start()

    @property
    def retained_bytes(self) -> int:
        """Return retained size without copying or disclosing private bytes."""
        with self._lock:
            return len(self._buffer)

    def observation(self) -> dict[str, object]:
        """Expose bounded consumer state, never raw bytes or termination proof."""
        with self._lock:
            return self._observation()

    def _observation(self) -> dict[str, object]:
        """Capture consumer metadata while the caller holds the buffer lock."""
        return {
            "retained_bytes": len(self._buffer),
            "overflow": self._overflow,
            "eof": self._eof,
            "read_failed": self._failed,
            "cancelled": self._stop.is_set(),
            "draining": self._thread.is_alive(),
        }

    def snapshot_available(self) -> tuple[bytes | None, dict[str, object]]:
        """Copy the latest available 64 KiB without waiting for the reader.

        Returns:
            Detached private bytes and metadata captured under the same lock.
            A clipped first physical line is discarded and clipping remains
            explicit even if this leaves a shorter window. Overflow, read
            failure or cancellation returns None with zero snapshot bytes.
            EOF is not required. The caller must discard these ephemeral bytes
            after reduction, never publish them or a digest of their contents.
        """
        with self._lock:
            state = self._observation()
            start = max(0, len(self._buffer) - _SNAPSHOT_BYTE_LIMIT)
            truncated = start > 0
            available = not (self._overflow or self._failed or self._stop.is_set())
            output = None
            if available:
                if start and self._buffer[start - 1] != ord("\n"):
                    end = self._buffer.find(b"\n", start)
                    start = end + 1 if end != -1 else len(self._buffer)
                with memoryview(self._buffer) as view:
                    output = bytes(view[start:])
            state.update(
                available=available,
                snapshot_bytes=len(output) if output is not None else 0,
                truncated=truncated,
            )
            return output, state

    def _drain(self) -> None:
        """Drain readable chunks, recording failure without exposing output."""
        try:
            descriptor = self._stream.fileno()
            while not self._stop.is_set():
                if not select.select([descriptor], [], [], 0.05)[0]:
                    continue
                chunk = os.read(descriptor, _SNAPSHOT_BYTE_LIMIT)
                if not chunk:
                    with self._lock:
                        self._eof = True
                    return
                with self._lock:
                    remaining = _PRIVATE_BYTE_LIMIT - len(self._buffer)
                    if len(chunk) > remaining:
                        self._overflow = True
                    if remaining:
                        self._buffer.extend(chunk[:remaining])
        except (OSError, ValueError):
            with self._lock:
                self._failed = True

    def read_complete(self, *, timeout: float) -> bytes | None:
        """Return complete bounded bytes only after EOF within finite seconds.

        Args:
            timeout: Positive finite seconds to wait for the reader.

        Returns:
            Private bytes, or None if completion or bounded retention failed.

        Raises:
            ValueError: If timeout is not positive and finite.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            message = "Private output completion requires a finite timeout"
            raise ValueError(message)
        self._thread.join(timeout=timeout)
        with self._lock:
            if (
                self._thread.is_alive()
                or not self._eof
                or self._overflow
                or self._failed
                or self._stop.is_set()
            ):
                return None
            return bytes(self._buffer)

    def close(self) -> None:
        """Cancel draining and close the owned pipe within one second.

        Raises:
            RuntimeError: If the reader does not stop within the deadline.
        """
        with self._lock:
            self._stop.set()
        self._thread.join(timeout=1)
        if self._thread.is_alive():
            message = "Private output consumer did not stop"
            raise RuntimeError(message)
        try:
            self._stream.close()
        finally:
            with self._lock:
                self._buffer.clear()


class TransitionError(RuntimeError):
    """A stock launch, native chord or pinned-process exit observation failed."""


@dataclass(frozen=True)
class ProcessIdentity:
    """A process identity pinned by a live pidfd, not a numeric PID alone."""

    pid: int
    start: int


@dataclass(frozen=True)
class Observation:
    """Independent runtime observations at a single monotonic instant."""

    emulator: ProcessIdentity | None
    alive: bool
    launcher_code: int | None
    active_pid: int | None
    core_loaded: bool
    rendered_content: bool
    transport_ready: bool = False
    forced_teardown: bool = False
    emulator_termination: str | None = None
    backend_display: dict[str, object] | None = None


class Runtime(Protocol):
    """Borrowed native operations; no final-key or exit-command operation exists."""

    def observe(self) -> Observation:
        """Observe actual processes, display, core and stock readiness."""
        ...

    def checkpoint(self, name: str) -> dict[str, object]:
        """Capture the authenticated owned display, or raise."""
        ...

    def guide_start(self) -> bool:
        """Press/release owned native controls; return whether both completed."""
        ...

    def permission(self) -> None:
        """Require the coordinator's current inspection/discovery lease."""
        ...


class Clock(Protocol):
    """Inject monotonic seconds and bounded observation intervals."""

    def now(self) -> float:
        """Return monotonic seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Wait for the requested bounded interval in seconds."""
        ...


@dataclass(frozen=True)
class ExitBudgets:
    """Finite seconds for startup, no-exit observation and shortcut exit."""

    startup: float = 40
    before_chord: float = 2
    exit: float = 15
    poll: float = 0.05

    def __post_init__(self) -> None:
        """Reject budgets that cannot enforce positive finite deadlines.

        Raises:
            ValueError: If any interval is nonpositive or nonfinite.
        """
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                self.startup,
                self.before_chord,
                self.exit,
                self.poll,
            )
        ):
            message = "Exit deadlines must be positive finite seconds"
            raise ValueError(message)


class EmulatorLifecycle:
    """Require live output, a native chord and observed same-process exit.

    Runtime owns and pins resources; this class never terminates a process.
    A caller must independently release input and clean up on every outcome.
    """

    def __init__(self, runtime: Runtime, clock: Clock, budgets: ExitBudgets) -> None:
        """Borrow runtime operations and a clock for the supplied exit budgets.

        Args:
            runtime: Pinned-process observations and owned native input operations.
            clock: Monotonic time and waiting operations.
            budgets: Positive finite transition limits, in seconds.
        """
        self.runtime, self.clock, self.budgets = runtime, clock, budgets

    def _wait_for_output(self) -> ProcessIdentity:
        """Pin one emulator and require continuously live output before capture."""
        runtime, clock, budgets = self.runtime, self.clock, self.budgets
        deadline = clock.now() + budgets.startup
        pinned: ProcessIdentity | None = None
        ready_since: float | None = None
        while True:
            runtime.permission()
            row = runtime.observe()
            if row.forced_teardown or row.launcher_code is not None:
                message = "Launcher exited before native chord"
                raise TransitionError(message)
            if row.emulator is not None:
                if pinned is None:
                    pinned = row.emulator
                if row.emulator != pinned or not row.alive:
                    message = "Pinned emulator changed or died before chord"
                    raise TransitionError(message)
            output = (
                pinned is not None
                and row.alive
                and row.active_pid == pinned.pid
                and row.core_loaded
                and row.rendered_content
                and row.transport_ready
            )
            if output:
                if ready_since is None:
                    ready_since = clock.now()
                if clock.now() - ready_since >= budgets.before_chord:
                    break
            else:
                ready_since = None
            self.pause(deadline)
        if pinned is None:
            message = "Emulator identity missing at output barrier"
            raise TransitionError(message)
        return pinned

    def _capture_live_output(
        self, pinned: ProcessIdentity
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Capture then recheck the same live emulator at the input boundary."""
        runtime = self.runtime
        before = runtime.checkpoint("emulator-before-exit")
        # Capture may block or race an exit. Re-observe at the injection boundary.
        row = runtime.observe()
        if (
            row.emulator != pinned
            or not row.alive
            or row.launcher_code is not None
            or row.active_pid != pinned.pid
            or not row.core_loaded
            or not row.rendered_content
            or not row.transport_ready
            or row.forced_teardown
        ):
            message = "Emulator lost live/output barrier during capture"
            raise TransitionError(message)
        # Retain the final pre-chord sample, not output observed during shutdown.
        display: dict[str, object] = {
            "active_pid": pinned.pid,
            "exact_core_loaded": True,
            "rendered_content": True,
            "live": True,
            **(row.backend_display or {}),
        }
        return before, display

    def _wait_for_exit(self, pinned: ProcessIdentity) -> None:
        """Observe bounded same-process death without forcing teardown."""
        runtime, clock, budgets = self.runtime, self.clock, self.budgets
        deadline = clock.now() + budgets.exit
        while True:
            runtime.permission()
            row = runtime.observe()
            if row.emulator != pinned or row.forced_teardown:
                message = "Exit process identity changed or was forcibly torn down"
                raise TransitionError(message)
            if row.launcher_code is not None and row.launcher_code != 0:
                message = "Stock launcher failed after chord"
                raise TransitionError(message)
            if not row.alive and row.launcher_code == 0:
                break
            if row.launcher_code == 0 and row.alive:
                message = "Launcher completed while pinned emulator remained live"
                raise TransitionError(message)
            self.pause(deadline)

    def run(self) -> dict[str, object]:
        """Require live output, one native chord and the pinned emulator's exit.

        Returns:
            Nonprivate process, display, input and capture evidence.

        Raises:
            TransitionError: If readiness, input or exit proof fails.
        """
        pinned = self._wait_for_output()
        before, display = self._capture_live_output(pinned)
        self.runtime.permission()
        if self.runtime.guide_start() is not True:
            message = "Native Guide+Start press/release incomplete"
            raise TransitionError(message)
        self._wait_for_exit(pinned)
        return {
            "emulator": {"pid": pinned.pid, "start": pinned.start},
            "stock_launch_display": display,
            "live_before_chord_seconds": self.budgets.before_chord,
            "native_guide_start": True,
            "same_emulator_exited": True,
            "launcher_code": 0,
            "forced_teardown": False,
            "captures": [before],
        }

    def pause(self, deadline: float) -> None:
        """Wait one poll interval without crossing an expired deadline.

        Args:
            deadline: Absolute monotonic transition deadline, in seconds.

        Raises:
            TransitionError: If the deadline expires before or during the wait.
        """
        remaining = deadline - self.clock.now()
        if remaining <= 0:
            message = "Emulator transition deadline expired"
            raise TransitionError(message)
        self.clock.sleep(min(self.budgets.poll, remaining))
        if self.clock.now() >= deadline:
            message = "Emulator transition deadline expired"
            raise TransitionError(message)
