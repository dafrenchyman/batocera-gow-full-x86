"""Host-only native selection and complete backend coverage accounting.

The coordinator validates native observations and retained captures. This module
aggregates those validated dispositions; it never supplies native proof itself.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from batocera_gow.host.media_qualification import CaseIdentity, load_cases
from batocera_gow.runtime.media_catalog import (
    EMULATOR_CASES,
    STOCK_SHA256,
    emulator_case,
    load_catalog,
)

RECEIVER_CASES = (
    "stock_combo_exit_held_and_pointer_reset",
    "stock_context_pointer_button",
    "context_switch_without_semantic_leakage",
    "held_graceful_source_removal_and_recreation",
    "stock_command_once_per_stock_release",
)
OUTCOMES = (
    "passed",
    "failed",
    "skipped-no-media",
    "blocked",
    "interrupted",
    "not-run",
)
NO_MEDIA = "Skipped: no compatible mounted media"


def outcome_counts(rows: Sequence[dict[str, object]]) -> dict[str, int]:
    """Count dispositions without conflating eligibility with passing coverage."""
    return {
        status: sum(row.get("status") == status for row in rows) for status in OUTCOMES
    }


def aggregate_regression(
    cases: Sequence[dict[str, object]],
    receivers: Sequence[dict[str, object]],
    *,
    evidence_complete: bool,
    cleanup_complete: bool,
    interrupted: bool = False,
) -> dict[str, object]:
    """Evaluate all six exact backend rows, including both DuckStation modes.

    Args:
        cases: Coordinator-validated dispositions, including frontend/receivers.
        receivers: Independently validated receiver assertions, not emulator proof.
        evidence_complete: Run-level publication and transfer acceptance.
        cleanup_complete: Independent owned-resource cleanup acceptance.
        interrupted: Whether isolation/discovery or operator interruption occurred.

    Returns:
        Gate outcome, six rows, separate case/backend counts and exit coverage.
        Missing, duplicate, unknown or unexplained skipped rows fail closed.
    """
    required_receivers = set(RECEIVER_CASES)
    expected = ["frontend", "receivers", *(case.identifier for case in EMULATOR_CASES)]
    errors: list[str] = []
    indexed: dict[str, dict[str, object]] = {}
    for row in cases:
        name = row.get("name")
        if not isinstance(name, str) or name not in expected or name in indexed:
            errors.append("Unknown or duplicate case disposition")
            continue
        indexed[name] = row
        if row.get("status") not in OUTCOMES:
            errors.append("Unknown case outcome: " + name)
        if row.get("status") == "skipped-no-media" and (
            name in ("frontend", "receivers") or row.get("reason") != NO_MEDIA
        ):
            errors.append("Unexplained or non-media skip: " + name)
    for name in expected:
        if name not in indexed:
            errors.append("Missing required case: " + name)
            indexed[name] = {
                "name": name,
                "status": "not-run",
                "reason": "Missing required case disposition",
            }
    receiver_names = [row.get("name") for row in receivers]
    receiver_ok = (
        len(receiver_names) == len(required_receivers)
        and all(isinstance(name, str) for name in receiver_names)
        and set(receiver_names) == required_receivers
        and all(row.get("status") == "passed" for row in receivers)
    )
    matrix: list[dict[str, object]] = []
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for case in EMULATOR_CASES:
        groups.setdefault((case.system, case.backend, case.core), []).append(
            indexed[case.identifier]
        )
    for (system, backend, core), variants in groups.items():
        statuses = [row.get("status") for row in variants]
        status = (
            "passed"
            if all(value == "passed" for value in statuses)
            else "skipped-no-media"
            if all(value == "skipped-no-media" for value in statuses)
            else next(
                (
                    value
                    for value in ("failed", "interrupted", "blocked", "not-run")
                    if value in statuses
                ),
                "failed",
            )
        )
        matrix.append(
            {
                "system": system,
                "backend": backend,
                "core": core,
                "status": status,
                "variants": variants,
                "reason": NO_MEDIA
                if status == "skipped-no-media"
                else "See independent variant observations",
            }
        )
    ordered = [indexed[name] for name in expected]
    passing_emulators = [
        case.identifier
        for case in EMULATOR_CASES
        if indexed[case.identifier].get("status") == "passed"
    ]
    passed = (
        not errors
        and not interrupted
        and evidence_complete
        and cleanup_complete
        and receiver_ok
        and all(
            indexed[name].get("status") == "passed"
            for name in ("frontend", "receivers")
        )
        and all(row.get("status") in ("passed", "skipped-no-media") for row in matrix)
    )
    return {
        "status": "passed" if passed else "failed",
        "full_regression_gate": passed,
        "regression_matrix": matrix,
        "counts": outcome_counts(ordered),
        "backend_counts": outcome_counts(matrix),
        "aggregation_errors": errors,
        "evidence_complete": evidence_complete,
        "cleanup_complete": cleanup_complete,
        "emulator_exit_cases": passing_emulators,
        "emulator_exit_coverage": (
            "Native Guide+Start observed exit: " + ", ".join(passing_emulators)
            if passing_emulators
            else "No emulator exit coverage"
        ),
    }


@dataclass(frozen=True)
class QualifiedInput:
    """A privately retained, validated exact-input qualification and replay record."""

    identity: CaseIdentity
    selection: dict[str, object]
    probe: dict[str, object]
    proof_sha256: str


def canonical_identity(value: object) -> str:
    """Serialize an exact backend or prerequisite identity deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def case_identity(
    name: str, probe: Mapping[str, object], image: str, source: str
) -> CaseIdentity:
    """Derive private qualification identity from already-validated native evidence.

    Args:
        name: Exact implemented backend/renderer case.
        probe: Validated final emulator report, never a public case template.
        image: Inspected immutable image ID.
        source: Its actual packaged source identity, not current host source.

    Returns:
        Identity compatible with the retained selected-run qualification format.
    """
    case = emulator_case(name)
    profile = probe.get("profile")
    media = probe.get("media")
    prerequisites = probe.get("prerequisites")
    if not isinstance(profile, dict) or not isinstance(media, dict):
        msg = "Validated profile/media identity required"
        raise TypeError(msg)
    if case.backend == "duckstation":
        if not isinstance(prerequisites, dict) or not isinstance(
            prerequisites.get("bios"), dict
        ):
            msg = "Validated BIOS identity required"
            raise TypeError(msg)
        firmware = str(prerequisites["bios"]["identity"])
        variant = "duckstation-qt/" + case.renderer
    else:
        firmware = (
            hashlib.sha256(canonical_identity(prerequisites).encode()).hexdigest()
            if case.backend == "xemu"
            else "stock-"
            + case.system
            + "-cartridge-route-no-external-firmware-declared"
        )
        variant = canonical_identity(probe.get("backend_identity"))
    return CaseIdentity(
        name,
        case.system,
        case.backend,
        case.core,
        variant,
        str(media.get("catalog_sha256")),
        image,
        source,
        str(media.get("identity")),
        str(profile.get("sha256")),
        str(probe.get("assertions")),
        firmware,
    )


def advertised_coverage(
    qualified: Sequence[str],
    selected: Sequence[str],
    *,
    project_root: Path = Path(),
) -> dict[str, object]:
    """Expose advertised mappings without inflating qualification.

    Args:
        qualified: Exact definitions with validated current-input proof.
        selected: Definitions selected for this run, not passing results.
        project_root: Explicit root containing the declared catalog and case assets.

    Returns:
        All stock systems/mappings, declared variants, rights/prerequisite gaps
        and independent inventory/selection counts. No private identity is emitted.
    """
    catalog_path = project_root / "tests/assets/media/stock-es_systems.cfg"
    catalog = load_catalog(catalog_path)
    definitions = load_cases(
        project_root / "tests/assets/media/cases.json", catalog_path=catalog_path
    )
    mappings: list[dict[str, object]] = []
    systems: list[dict[str, object]] = []
    for system in catalog.systems:
        systems.append(
            {
                "system": system.system,
                "directory": system.directory,
                "formats": list(system.extensions),
                "mapping_count": len(system.backends),
                "disposition": "advertised-not-native-proof"
                if system.backends
                else "non-ROM-category",
            }
        )
        for backend, core in system.backends:
            cases = [
                case
                for case in definitions
                if (case.system, case.backend, case.core)
                == (system.system, backend, core)
            ]
            mappings.append(
                {
                    "system": system.system,
                    "backend": backend,
                    "core": core,
                    "status": "qualified-selected"
                    if any(
                        case.identifier in qualified and case.identifier in selected
                        for case in cases
                    )
                    else "qualified-not-selected"
                    if any(case.identifier in qualified for case in cases)
                    else "unqualified"
                    if cases
                    else "no-executable-definition",
                    "definitions": [
                        {
                            "case": case.identifier,
                            "variant": case.variant,
                            "required": case.required,
                            "route": case.route,
                            "rights": case.rights,
                            "prerequisites": case.firmware,
                            "gaps": list(case.gaps),
                            "qualification": "qualified-exact-input"
                            if case.identifier in qualified
                            else "unqualified",
                            "selected": case.identifier in selected,
                        }
                        for case in cases
                    ],
                }
            )
    return {
        "catalog_sha256": STOCK_SHA256,
        "inventory_counts": dict(
            zip(
                ("systems", "emulators", "backend_core_pairs", "mappings"),
                catalog.counts(),
                strict=True,
            )
        ),
        "qualified_definition_count": len(qualified),
        "selected_definition_count": len(selected),
        "unqualified_mapping_count": sum(
            row["status"] in ("unqualified", "no-executable-definition")
            for row in mappings
        ),
        "systems": systems,
        "mappings": mappings,
    }
