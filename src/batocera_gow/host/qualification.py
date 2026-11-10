"""Qualify one normal immutable image without building or changing deployment."""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from batocera_gow.host.native_freshness import BuildSnapshot
from batocera_gow.host.native_integration import Artifacts
from batocera_gow.host.native_matrix import RECEIVER_CASES
from batocera_gow.host.native_preparation import NativeSession
from batocera_gow.host.native_remote import NativeError, record
from batocera_gow.provenance import file_sha256
from batocera_gow.runtime.media_catalog import EMULATOR_CASES


class CheckPhase(Protocol):
    """A bounded check returning only sanitized evidence and actual outcomes."""

    def run(self, artifacts: Artifacts) -> dict[str, object]:
        """Retain evidence in the borrowed private directory, never delete history."""
        ...


def preservation_evidence(
    snapshot: BuildSnapshot, manifest: Path, stock: Path
) -> dict[str, object]:
    """Validate retained normal-build preservation bytes, not another inventory run.

    Legacy manifests without image-bound complete evidence require an explicit
    normal build. Giant saved TARs are not required after verified inventory.
    """
    build = record(json.loads(manifest.read_text(encoding="utf-8")))
    preservation = record(build.get("preservation"))
    relative = Path(str(preservation.get("report", "")))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        message = "Normal build preservation reference is invalid"
        raise NativeError(message)
    report = manifest.parent / relative
    if report.is_symlink() or not report.resolve().is_relative_to(
        manifest.parent.resolve()
    ):
        message = "Normal build preservation reference escapes its output"
        raise NativeError(message)
    result = record(json.loads(report.read_text(encoding="utf-8")))
    count = result.get("verified_stock_paths")
    additions = result.get("added_paths")
    if (
        preservation.get("schema") != 1
        or preservation.get("image") != snapshot.image
        or preservation.get("declared_inputs_sha256") != snapshot.inputs["sha256"]
        or preservation.get("report_sha256") != file_sha256(report)
        or preservation.get("stock_sha256") != file_sha256(stock)
        or preservation.get("result") != result
        or type(count) is not int
        or count <= 0
        or type(additions) is not int
        or additions < 0
        or build.get("diagnostic_only", False) is not False
    ):
        message = "Complete normal image-bound preservation evidence required"
        raise NativeError(message)
    return {
        "status": "passed",
        "reused": True,
        "inventory_executed": False,
        "image": snapshot.image,
        "build_manifest_sha256": file_sha256(manifest),
        "report_sha256": preservation["report_sha256"],
        "stock_sha256": preservation["stock_sha256"],
        "result": result,
    }


def _continue_case(observed: dict[str, object], name: str) -> bool:
    """Continue only after complete cleanup and a pass or explicit media skip."""
    if (
        observed.get("evidence_complete") is not True
        or observed.get("cleanup_complete") is not True
        or observed.get("diagnostic_only") is True
        or observed.get("interruption")
    ):
        return False
    if observed.get("status") in ("passed", "skipped-no-media"):
        return True
    rows = observed.get("cases")
    return isinstance(rows, list) and any(
        record(row).get("name") == name
        and record(row).get("status") == "skipped-no-media"
        for row in rows
    )


class Qualification:
    """Sequence failure barriers and retain one image-bound private aggregate."""

    def __init__(  # noqa: PLR0913 - independent borrowed phase and native boundaries.
        self,
        snapshot: BuildSnapshot,
        preservation: Callable[[], dict[str, object]],
        local: CheckPhase,
        packaged: CheckPhase,
        native: Callable[[], AbstractContextManager[NativeSession]],
        *,
        artifacts: Artifacts,
    ) -> None:
        """Borrow verified inputs/checks; native factory must have no eager effects."""
        self.snapshot = snapshot
        self.verify_preservation = preservation
        self.preservation = preservation()
        self.local = local
        self.packaged = packaged
        self.native = native
        self.artifacts = artifacts

    def _assert_current(self) -> None:
        """Recheck source/stage and retained preservation bytes between phases."""
        self.snapshot.assert_current()
        if self.verify_preservation() != self.preservation:
            message = "Image preservation evidence drift detected"
            raise NativeError(message)

    def run(self) -> dict[str, object]:
        """Stop on failure or drift, unwind owned native resources and report truth."""
        phases: dict[str, object] = {
            "preservation": self.preservation,
            "local": {"status": "not-run"},
            "packaged": {"status": "not-run"},
            "native": {"status": "not-run"},
        }
        report: dict[str, object] = {
            "schema": 1,
            "status": "failed",
            "full_qualification": False,
            "image": self.snapshot.image,
            "declared_inputs": self.snapshot.inputs,
            "runtime_inputs": self.snapshot.runtime_inputs,
            "phases": phases,
            "drift": "not-checked",
            "cleanup_complete": True,
            "limits": [
                "Server-side only; client video/audio and physical input unobserved",
                "Only eligible mounted media; no all-catalog or gameplay qualification",
                "No deployment, registration, configuration change or service restart",
            ],
        }
        active = "local"
        try:
            self._assert_current()
            self.artifacts.put(
                "preservation-reuse.json",
                json.dumps(self.preservation, sort_keys=True).encode() + b"\n",
            )
            phases["preservation"] = {
                **self.preservation,
                "evidence": "preservation-reuse.json",
            }
            for name, check in (("local", self.local), ("packaged", self.packaged)):
                active = name
                phases[name] = {"status": "running"}
                if name == "packaged":
                    report["cleanup_complete"] = False
                result = check.run(self.artifacts)
                phases[name] = result
                report["cleanup_complete"] = result.get("cleanup_complete") is True
                if result.get("status") != "passed" or not report["cleanup_complete"]:
                    return report
                self._assert_current()
            active = "native"
            phases["native"] = {"status": "running"}
            report["cleanup_complete"] = False
            with self.native() as session:
                for name in (
                    "frontend",
                    *RECEIVER_CASES,
                    *(case.identifier for case in EMULATOR_CASES),
                ):
                    observed = session.run(name)
                    if not _continue_case(observed, name):
                        break
            aggregate = self._native_evidence()
            phases["native"] = aggregate
            report["cleanup_complete"] = aggregate.get("cleanup_complete") is True
            self._assert_current()
            report["drift"] = "unchanged"
            if (
                aggregate.get("full_regression_gate") is True
                and aggregate.get("evidence_complete") is True
                and report["cleanup_complete"] is True
            ):
                report.update(status="passed", full_qualification=True)
        except (
            NativeError,
            OSError,
            ValueError,
            InterruptedError,
            KeyboardInterrupt,
        ) as error:
            # Never persist arbitrary exception messages, argv, paths or settings.
            if active == "native":
                phases[active] = self._native_evidence()
                report["cleanup_complete"] = (
                    record(phases[active]).get("cleanup_complete") is True
                )
            else:
                previous = record(phases[active])
                phases[active] = {
                    **previous,
                    "status": previous["status"]
                    if previous.get("status") == "passed"
                    else "failed",
                    "barrier_failure": type(error).__name__,
                }
            report["failure"] = type(error).__name__
        finally:
            try:
                self._assert_current()
                report["drift"] = "unchanged"
            except (NativeError, OSError, ValueError):
                report.update(
                    drift="detected", status="failed", full_qualification=False
                )
            self.artifacts.put(
                "qualification-report.json",
                json.dumps(report, indent=2, sort_keys=True).encode() + b"\n",
            )
        return report

    def _native_evidence(self) -> dict[str, object]:
        """Read the maintained session's published result, including setup failure."""
        reports = list((self.artifacts.path / "native").glob("*/session-report.json"))
        if len(reports) != 1:
            return {
                "status": "failed",
                "cleanup_complete": False,
                "failure": "missing-native-aggregate",
            }
        path = reports[0]
        try:
            return self._read_native_evidence(path)
        except (NativeError, OSError, ValueError):
            return {
                "status": "failed",
                "cleanup_complete": False,
                "failure": "invalid-native-aggregate",
            }

    def _read_native_evidence(self, path: Path) -> dict[str, object]:
        """Bind one valid published native result to this immutable source snapshot."""
        aggregate = record(json.loads(path.read_text(encoding="utf-8")))
        retained: dict[str, object] = {
            key: aggregate[key]
            for key in (
                "status",
                "full_regression_gate",
                "full_frontend_receiver_gate",
                "evidence_complete",
                "cleanup_complete",
                "regression_matrix",
                "counts",
                "backend_counts",
                "emulator_exit_coverage",
                "selected_cases",
                "drift",
                "preparation",
            )
            if key in aggregate
        }
        retained.update(
            evidence=path.relative_to(self.artifacts.path).as_posix(),
            evidence_sha256=file_sha256(path),
        )
        if (
            aggregate.get("image") != self.snapshot.image
            or aggregate.get("declared_inputs") != self.snapshot.inputs
            or aggregate.get("runtime_inputs") != self.snapshot.runtime_inputs
            or aggregate.get("diagnostic_only") is True
            or any(
                record(value).get("diagnostic_only") is True
                for value in record(aggregate.get("reports")).values()
            )
        ):
            retained.update(status="failed", full_regression_gate=False)
        return retained
