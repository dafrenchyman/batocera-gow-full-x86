"""Host-only stock catalog and mount configuration behavior."""

import json
from pathlib import Path

import pytest

from batocera_gow.runtime.media_catalog import (
    DEFAULT_CATALOG,
    CatalogError,
    array,
    load_catalog,
    object_record,
    reconcile_inventory,
)
from batocera_gow.runtime.mounted_media import ContentRoots, EffectiveMount, MediaError

RESEARCH = Path("docs/completed/epics/repository-maturation/research/artifacts")


def test_catalog_reconciles_all_advertised_mappings_and_actual_directories() -> None:
    """Retained research and stock declarations agree on every mapping."""
    catalog = load_catalog()
    inventory = json.loads(
        (RESEARCH / "packaged-system-inventory.json").read_text(encoding="utf-8")
    )
    candidates = json.loads(
        (RESEARCH / "fixture-candidate-catalog.json").read_text(encoding="utf-8")
    )
    reconcile_inventory(catalog, inventory, candidates)
    assert catalog.counts() == (253, 98, 233, 477)
    assert catalog.system("megadrive").directory == "/userdata/roms/megadrive"
    assert catalog.system("imageviewer").directory == "/userdata/screenshots"
    assert not catalog.system("imageviewer").rom_relative_directory
    with pytest.raises(CatalogError, match="Unknown system"):
        catalog.system("not-a-stock-system")


def test_lost_mapping_and_wrong_provenance_are_rejected() -> None:
    """Removed backends and altered provenance cannot pass reconciliation."""
    catalog = load_catalog()
    inventory = object_record(
        json.loads(
            (RESEARCH / "packaged-system-inventory.json").read_text(encoding="utf-8"),
        ),
    )
    candidates = object_record(
        json.loads(
            (RESEARCH / "fixture-candidate-catalog.json").read_text(encoding="utf-8"),
        ),
    )
    systems = array(inventory["systems"])
    damaged = object_record(systems[0])
    damaged["emulators"] = []
    systems[0] = damaged
    inventory["systems"] = systems
    with pytest.raises(CatalogError, match="mapping"):
        reconcile_inventory(catalog, inventory, candidates)
    candidates["stock_catalog_sha256"] = "0" * 64
    with pytest.raises(CatalogError, match="provenance"):
        reconcile_inventory(catalog, inventory, candidates)


def test_mount_configuration_does_not_require_local_host_paths_or_ssh() -> None:
    """Remote mount declarations are validated without contacting their host."""
    config = ContentRoots.from_environment(
        {
            "BATOCERA_GOW_ROMS_ROOT": "/srv/remote-library",
            "BATOCERA_GOW_BIOS_ROOT": "/srv/remote-firmware",
        }
    )
    assert config.wolf_mounts() == [
        "/srv/remote-library:/home/retro/userdata/roms:ro",
        "/srv/remote-firmware:/home/retro/userdata/bios:ro",
    ]
    observed = [
        EffectiveMount(
            "/srv/remote-library", "/home/retro/userdata/roms", writable=False
        ),
        EffectiveMount(
            "/srv/remote-firmware", "/home/retro/userdata/bios", writable=False
        ),
    ]
    config.validate_mounts(observed)
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts([*observed, observed[0]])
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts(
            [
                EffectiveMount(
                    observed[0].source, observed[0].destination, writable=True
                ),
                observed[1],
            ]
        )
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts(
            [
                EffectiveMount("/wrong", observed[0].destination, writable=False),
                observed[1],
            ]
        )
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts(observed[:1])


@pytest.mark.parametrize(
    "bad",
    [
        "relative",
        "/srv/../private",
        "/srv/library:rw",
        "${ROMS}",
        "",
        "/srv/line\nbreak",
    ],
)
def test_invalid_mount_sources_fail_without_filesystem_discovery(bad: str) -> None:
    """Unsafe mount source syntax fails before any filesystem discovery."""
    with pytest.raises(MediaError):
        ContentRoots.from_environment(
            {"BATOCERA_GOW_ROMS_ROOT": bad, "BATOCERA_GOW_BIOS_ROOT": "/bios"}
        )


def test_modified_original_catalog_cannot_claim_approved_pin(tmp_path: Path) -> None:
    """Changing a stock directory invalidates the approved catalog digest."""
    modified = tmp_path / "es_systems.cfg"
    modified.write_bytes(
        DEFAULT_CATALOG.read_bytes().replace(
            b"/userdata/roms/nes", b"/userdata/roms/foreign"
        )
    )
    with pytest.raises(CatalogError, match="provenance"):
        load_catalog(modified)


def test_effective_mount_inspection_rejects_unknown_writable_and_shadowing() -> None:
    """Unknown access modes, nested shadowing and non-bind mounts are refused."""
    config = ContentRoots("/srv/roms", "/srv/bios")
    inspected = [
        EffectiveMount.from_docker(
            {
                "Type": "bind",
                "Source": "/srv/roms",
                "Destination": "/home/retro/userdata/roms",
                "RW": False,
            }
        ),
        EffectiveMount.from_docker(
            {
                "Type": "bind",
                "Source": "/srv/bios",
                "Destination": "/home/retro/userdata/bios",
                "RW": False,
            }
        ),
    ]
    config.validate_mounts(inspected)
    with pytest.raises(MediaError, match="mount"):
        EffectiveMount.from_docker(
            {
                "Source": "/srv/roms",
                "Destination": "/home/retro/userdata/roms",
                "RW": "false",
            }
        )
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts(
            [
                *inspected,
                EffectiveMount(
                    "/foreign", "/home/retro/userdata/roms/nes", writable=False
                ),
            ]
        )
    with pytest.raises(MediaError, match="mount"):
        config.validate_mounts(
            [
                EffectiveMount(
                    "/srv/roms",
                    "/home/retro/userdata/roms",
                    writable=False,
                    kind="volume",
                ),
                inspected[1],
            ]
        )
