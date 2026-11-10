"""Native evidence claims remain separate from research and rights."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from batocera_gow.host.media_qualification import (
    DEFAULT_CASES,
    CaseIdentity,
    NativeObservations,
    Qualification,
    QualificationError,
    evaluate_qualification,
    load_cases,
)
from batocera_gow.runtime.media_catalog import CatalogError, array, object_record


def identity() -> CaseIdentity:
    """Return complete synthetic private qualification inputs.

    Returns:
        An independently chosen identity for a required libretro case.
    """
    return CaseIdentity(
        "nes-fceumm",
        "nes",
        "libretro",
        "fceumm",
        "packaged-version",
        "catalog-pin",
        "immutable-image",
        "source-fingerprint",
        "private-media-digest",
        "suite-profile-v1",
        "exit-assertions-v1",
        "firmware-profile-v1",
    )


def observations() -> NativeObservations:
    """Return a complete observed native exit and cleanup result.

    Returns:
        Evidence flags sufficient to qualify the synthetic libretro identity.
    """
    return NativeObservations(
        stock_launch_display=True,
        live_before_chord=True,
        native_guide_start=True,
        same_emulator_exited=True,
        launcher_completed=True,
        native_device_consumed=True,
        stock_integrity=True,
        evidence_retained=True,
        cleanup_complete=True,
    )


def test_all_required_cases_and_expanded_gaps_start_unqualified() -> None:
    """Required systems and expanded gaps have no implied native qualification."""
    cases = load_cases()
    assert {case.system for case in cases if case.required} == {
        "nes",
        "snes",
        "megadrive",
        "atari2600",
        "psx",
        "xbox",
    }
    assert {case.variant for case in cases if case.system == "psx"} == {
        "duckstation-qt/OpenGL",
        "duckstation-qt/Vulkan",
    }
    assert {case.system for case in cases if not case.required} == {"ps3", "xbox360"}
    assert all(case.qualification.status == "unqualified" for case in cases)
    assert all(case.qualification.identity is None for case in cases)


def test_research_or_distribution_rights_alone_cannot_qualify() -> None:
    """Neither research nor rights replaces native evidence and authorization."""
    result = evaluate_qualification(
        identity(),
        Qualification("unqualified"),
        None,
        use_authorized=True,
        distributed=False,
        distribution_cleared=True,
    )
    assert result.status == "unqualified"
    with pytest.raises(QualificationError, match="permission"):
        evaluate_qualification(
            identity(),
            Qualification("unqualified"),
            observations(),
            use_authorized=False,
            distributed=False,
            distribution_cleared=False,
        )
    with pytest.raises(QualificationError, match="distribution"):
        evaluate_qualification(
            identity(),
            Qualification("unqualified"),
            observations(),
            use_authorized=True,
            distributed=True,
            distribution_cleared=False,
        )


@pytest.mark.parametrize(
    "field",
    [
        "stock_launch_display",
        "live_before_chord",
        "native_guide_start",
        "same_emulator_exited",
        "launcher_completed",
        "native_device_consumed",
        "stock_integrity",
        "evidence_retained",
        "cleanup_complete",
    ],
)
def test_each_missing_native_observation_prevents_passing(field: str) -> None:
    """Every missing required native observation prevents a passing claim."""
    result = evaluate_qualification(
        identity(),
        Qualification("unqualified"),
        NativeObservations(
            stock_launch_display=field != "stock_launch_display",
            live_before_chord=field != "live_before_chord",
            native_guide_start=field != "native_guide_start",
            same_emulator_exited=field != "same_emulator_exited",
            launcher_completed=field != "launcher_completed",
            native_device_consumed=field != "native_device_consumed",
            stock_integrity=field != "stock_integrity",
            evidence_retained=field != "evidence_retained",
            cleanup_complete=field != "cleanup_complete",
        ),
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert result.status == "failed"


def test_private_authorized_native_case_can_qualify_without_public_source() -> None:
    """Private authorized media needs no public distribution clearance."""
    result = evaluate_qualification(
        identity(),
        Qualification("unqualified"),
        observations(),
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert result.status == "qualified"
    assert result.identity == identity()
    assert (
        evaluate_qualification(
            identity(),
            result,
            None,
            use_authorized=True,
            distributed=False,
            distribution_cleared=False,
        )
        == result
    )


@pytest.mark.parametrize(
    "field",
    [
        "case",
        "system",
        "variant",
        "catalog",
        "image",
        "source",
        "media",
        "profile",
        "assertions",
        "firmware",
        "backend",
        "core",
    ],
)
def test_changed_inputs_invalidate_previous_qualification(field: str) -> None:
    """Changing any qualification input preserves but invalidates old evidence."""
    previous = Qualification("qualified", identity())
    changed = replace(identity(), **{field: "changed"})
    result = evaluate_qualification(
        changed,
        previous,
        None,
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert result.status == "invalidated"
    assert result.identity == identity()
    requalified = evaluate_qualification(
        changed,
        result,
        observations(),
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert requalified.status == "qualified"
    assert requalified.identity == changed


def test_standalone_native_device_assertion_may_be_inapplicable_but_not_libretro() -> (
    None
):
    """Only standalone backends may omit native libretro device consumption."""
    observed = replace(
        observations(),
        native_device_consumed=None,
        renderer_selected="OpenGL",
        renderer_active="OpenGL",
    )
    standalone = replace(
        identity(),
        backend="duckstation",
        core="duckstation",
        variant="duckstation-qt/OpenGL",
    )
    result = evaluate_qualification(
        standalone,
        Qualification("unqualified"),
        observed,
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert result.status == "qualified"
    assert (
        evaluate_qualification(
            identity(),
            Qualification("unqualified"),
            observed,
            use_authorized=True,
            distributed=False,
            distribution_cleared=False,
        ).status
        == "failed"
    )


@pytest.mark.parametrize("selected", ["OpenGL", "Vulkan"])
@pytest.mark.parametrize("active", ["OpenGL", "OpenGLES", "Vulkan", None])
def test_renderer_qualification_cannot_be_borrowed(
    selected: str,
    active: str | None,
) -> None:
    """Each DuckStation renderer requires matching active renderer evidence."""
    claim = replace(
        identity(),
        case="psx-duckstation" + ("-vulkan" if selected == "Vulkan" else ""),
        system="psx",
        backend="duckstation",
        core="duckstation",
        variant="duckstation-qt/" + selected,
    )
    result = evaluate_qualification(
        claim,
        Qualification("unqualified"),
        replace(observations(), renderer_selected=selected, renderer_active=active),
        use_authorized=True,
        distributed=False,
        distribution_cleared=False,
    )
    assert result.status == (
        "qualified"
        if active in (("OpenGL", "OpenGLES") if selected == "OpenGL" else ("Vulkan",))
        else "failed"
    )


@pytest.mark.parametrize("removed", ["duckstation-qt/OpenGL", "duckstation-qt/Vulkan"])
def test_catalog_cannot_drop_one_duckstation_renderer_while_retaining_six_backends(
    tmp_path: Path,
    removed: str,
) -> None:
    """Required renderer coverage cannot hide behind the aggregate backend count."""
    document = object_record(json.loads(DEFAULT_CASES.read_text(encoding="utf-8")))
    document["cases"] = [
        case
        for case in array(document["cases"])
        if object_record(case)["variant"] != removed
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CatalogError, match="Both independent DuckStation"):
        load_cases(path)
