"""Case declarations and qualification transitions, not a native runner."""

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from batocera_gow.runtime.media_catalog import (
    CatalogError,
    array,
    load_catalog,
    object_record,
    text,
)

DEFAULT_CASES = Path("tests/assets/media/cases.json")
QualificationStatus = Literal["unqualified", "qualified", "failed", "invalidated"]


class QualificationError(ValueError):
    """A qualification claim lacks required permission or identity information."""


@dataclass(frozen=True)
class CaseIdentity:
    """Exact private qualification inputs. Public output must omit media details."""

    case: str
    system: str
    backend: str
    core: str
    variant: str
    catalog: str
    image: str
    source: str
    media: str
    profile: str
    assertions: str
    firmware: str

    def __post_init__(self) -> None:
        """Reject incomplete exact-input identities before evaluating any claim."""
        if any(
            not isinstance(getattr(self, field.name), str)
            or not getattr(self, field.name)
            for field in fields(self)
        ):
            msg = "Qualification requires complete input identity"
            raise QualificationError(msg)


@dataclass(frozen=True)
class NativeObservations:
    """Already-validated native evidence summaries supplied by the native owner.

    These are not produced by media selection. Native-device consumption is
    required for libretro; None means inapplicable only for other backends.
    The native coordinator must validate causal ordering and actual artifacts.
    Launcher completion means code zero, native input includes press/release and
    cleanup excludes test-sent signals or forced emulator teardown. Log-based
    natural-exit classification and frontend recovery are not qualification.
    """

    stock_launch_display: bool
    live_before_chord: bool
    native_guide_start: bool
    same_emulator_exited: bool
    launcher_completed: bool
    native_device_consumed: bool | None
    stock_integrity: bool
    evidence_retained: bool
    cleanup_complete: bool
    renderer_selected: str | None = None
    renderer_active: str | None = None


@dataclass(frozen=True)
class Qualification:
    """A result bound to exact inputs, preserving invalidated historical identity."""

    status: QualificationStatus
    identity: CaseIdentity | None = None

    def __post_init__(self) -> None:
        """Require a known disposition and its applicable historical identity."""
        if self.status not in {"unqualified", "qualified", "failed", "invalidated"}:
            msg = "Unknown qualification status"
            raise QualificationError(msg)
        if self.status != "unqualified" and self.identity is None:
            msg = "Qualification result requires exact identity"
            raise QualificationError(msg)


@dataclass(frozen=True)
class ExecutableCase:
    """Stock launch declaration plus honest research and prerequisite gaps."""

    identifier: str
    system: str
    backend: str
    core: str
    variant: str
    required: bool
    route: str
    formats: tuple[str, ...]
    rights: str
    firmware: str
    research: str
    gaps: tuple[str, ...]
    qualification: Qualification


def evaluate_qualification(  # noqa: PLR0913 - independent use/distribution permissions must remain explicit.
    identity: CaseIdentity,
    previous: Qualification,
    observations: NativeObservations | None,
    *,
    use_authorized: bool,
    distributed: bool,
    distribution_cleared: bool,
) -> Qualification:
    """Bind native results to inputs without promoting research or rights alone.

    Args:
        identity: Actual image, source, media, backend and assertion identities.
        previous: Existing claim, which is invalidated when inputs change.
        observations: Validated native evidence, or None for no execution.
        use_authorized: Operator permission for this media's actual use.
        distributed: Whether the project distributes this selected media.
        distribution_cleared: Actual source/binary/dependency/asset clearance.

    Returns:
        A new claim; missing native observations never create a qualified result.

    Raises:
        QualificationError: If use or applicable distribution permission is absent.
    """
    if not use_authorized:
        msg = "Media use permission is required"
        raise QualificationError(msg)
    if distributed and not distribution_cleared:
        msg = "Complete distribution clearance is required"
        raise QualificationError(msg)
    if observations is None:
        if previous.identity is not None and previous.identity != identity:
            return Qualification("invalidated", previous.identity)
        return previous
    required = [
        getattr(observations, field.name) is True
        for field in fields(observations)
        if field.name
        not in ("native_device_consumed", "renderer_selected", "renderer_active")
    ]
    device = observations.native_device_consumed
    device_ok = (
        device is True
        if identity.backend == "libretro"
        else device is True or device is None
    )
    renderer_ok = True
    if identity.backend == "duckstation":
        renderer = identity.variant.removeprefix("duckstation-qt/")
        renderer_ok = (
            identity.variant in ("duckstation-qt/OpenGL", "duckstation-qt/Vulkan")
            and observations.renderer_selected == renderer
            and observations.renderer_active
            in (("OpenGL", "OpenGLES") if renderer == "OpenGL" else ("Vulkan",))
        )
    return Qualification(
        "qualified" if all(required) and device_ok and renderer_ok else "failed",
        identity,
    )


def load_cases(
    path: Path = DEFAULT_CASES,
    *,
    catalog_path: Path = Path("tests/assets/media/stock-es_systems.cfg"),
) -> tuple[ExecutableCase, ...]:
    """Load maintained unqualified declarations and verify stock backend/format ties.

    This initial asset deliberately contains no native result or private identity.
    Actual run qualification records belong in owner-restricted run storage.

    Raises:
        CatalogError: If IDs, formats, mappings or initial dispositions disagree.
    """
    document = object_record(json.loads(path.read_text(encoding="utf-8")))
    catalog = load_catalog(catalog_path)
    if document.get("stock_catalog_sha256") != catalog.sha256:
        msg = "Case catalog provenance mismatch"
        raise CatalogError(msg)
    cases: list[ExecutableCase] = []
    for value in array(document.get("cases")):
        record = object_record(value)
        system = catalog.system(text(record.get("system")))
        backend, core = text(record.get("backend")), text(record.get("core"))
        formats = tuple(text(value) for value in array(record.get("formats")))
        if (
            (backend, core) not in system.backends
            or not set(formats).issubset(system.extensions)
            or not formats
        ):
            msg = "Case mapping/format is not stock-advertised"
            raise CatalogError(msg)
        if (
            record.get("qualification") != {"status": "unqualified", "identity": None}
            or type(record.get("required")) is not bool
        ):
            msg = "Initial case must remain explicitly unqualified"
            raise CatalogError(msg)
        cases.append(
            ExecutableCase(
                text(record.get("id")),
                system.system,
                backend,
                core,
                text(record.get("variant")),
                record.get("required") is True,
                text(record.get("route")),
                formats,
                text(record.get("rights")),
                text(record.get("firmware")),
                text(record.get("research")),
                tuple(text(gap) for gap in array(record.get("gaps"))),
                Qualification("unqualified"),
            )
        )
    if len({case.identifier for case in cases}) != len(cases):
        msg = "Duplicate executable case ID"
        raise CatalogError(msg)
    required = {
        (case.system, case.backend, case.core) for case in cases if case.required
    }
    if required != {
        ("nes", "libretro", "fceumm"),
        ("snes", "libretro", "snes9x"),
        ("megadrive", "libretro", "genesisplusgx"),
        ("atari2600", "libretro", "stella"),
        ("psx", "duckstation", "duckstation"),
        ("xbox", "xemu", "xemu"),
    }:
        msg = "Required six-backend matrix changed"
        raise CatalogError(msg)
    duckstation_variants = {
        (case.identifier, case.variant)
        for case in cases
        if case.required and case.backend == "duckstation"
    }
    if duckstation_variants != {
        ("psx-duckstation", "duckstation-qt/OpenGL"),
        ("psx-duckstation-vulkan", "duckstation-qt/Vulkan"),
    }:
        msg = "Both independent DuckStation renderer variants are required"
        raise CatalogError(msg)
    return tuple(cases)
