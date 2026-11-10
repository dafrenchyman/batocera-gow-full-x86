"""Pinned advertised stock systems, distinct from installed or qualified support."""

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# pragma: allowlist nextline secret
STOCK_SHA256 = "401638d6cbc26e574456f36a4b59007b823b576b35422f519640be9bfd3efc23"
# pragma: allowlist nextline secret
STOCK_REVISION = "155c2d8d304cbb53db52e9479dcf683392821d5c"
DEFAULT_CATALOG = Path("tests/assets/media/stock-es_systems.cfg")

# The recipe identifies source, not the executable's blank compiled SCM strings.
DUCKSTATION_PACKAGE_SOURCE = {
    "version": "v0.1-7294",
    # pragma: allowlist nextline secret
    "revision": "3a08ad18406efc1ddc4927a59bea715961bb63fa",
    "recipe": "https://github.com/batocera-linux/batocera.linux/blob/"
    + STOCK_REVISION
    + "/package/batocera/emulators/duckstation/duckstation.mk",
}

XEMU_PACKAGE_SOURCE = {
    "version": "v0.8.134",
    # pragma: allowlist nextline secret
    "revision": "fc9980d2962cbec656253106ea2e121fab1e68d4",
    "recipe": "https://github.com/batocera-linux/batocera.linux/blob/"
    + STOCK_REVISION
    + "/package/batocera/emulators/xemu/xemu.mk",
}
XEMU_SDL = "/usr/lib/libSDL3.so.0.4.2"
XEMU_HDD = "/usr/share/xemu/data/xbox_hdd.qcow2"
# pragma: allowlist nextline secret
XEMU_HDD_SHA256 = "eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed"
XEMU_HDD_USE = "unchanged-stock-private-disposable-use"


@dataclass(frozen=True)
class EmulatorCase:
    """An implemented exit case, not a replacement for stock media declarations."""

    system: str
    core: str
    library: str
    label: str
    backend: str = "libretro"
    renderer: str = ""

    @property
    def executable(self) -> str:
        """Return the exact installed consumer selected by the stock generator."""
        return {
            "libretro": "/usr/bin/retroarch",
            "duckstation": "/usr/bin/duckstation-qt",
            "xemu": "/usr/bin/xemu",
        }[self.backend]

    @property
    def inventory_paths(self) -> tuple[str, ...]:
        """Return backend-specific mandatory stock inventory members."""
        if self.backend == "libretro":
            return self.executable, self.core_path, self.info_path
        if self.backend == "xemu":
            return (
                self.executable,
                XEMU_SDL,
                XEMU_HDD,
                *(
                    "/usr/lib/python3.12/site-packages/configgen/generators/xemu/"
                    + name
                    for name in ("xemuGenerator.py", "xemuConfig.py", "xemuPaths.py")
                ),
            )
        return (
            self.executable,
            "/usr/lib/python3.12/site-packages/configgen/generators/duckstation/duckstationGenerator.py",
        )

    @property
    def identifier(self) -> str:
        """Return the separately reported system/core identity."""
        suffix = "-vulkan" if self.renderer == "Vulkan" else ""
        return self.system + "-" + self.core + suffix

    @property
    def tier(self) -> str:
        """Return the explicit native subset selector."""
        suffix = "-vulkan" if self.renderer == "Vulkan" else ""
        return self.system + suffix + "-smoke"

    @property
    def core_path(self) -> str:
        """Return the exact packaged core, never a similarly named variant."""
        return "/usr/lib/libretro/" + self.core + "_libretro.so"

    @property
    def info_path(self) -> str:
        """Return the regular stock metadata file hashed by the inventory."""
        # Stock aliases genesisplusgx metadata, but not its core library name.
        info_core = "genesis_plus_gx" if self.core == "genesisplusgx" else self.core
        return "/usr/share/libretro/info/" + info_core + "_libretro.info"


EMULATOR_CASES = (
    EmulatorCase("nes", "fceumm", "FCEUmm", "NES/FCEUmm"),
    EmulatorCase("snes", "snes9x", "Snes9x", "SNES/Snes9x"),
    EmulatorCase(
        "megadrive", "genesisplusgx", "Genesis Plus GX", "Mega Drive/Genesis Plus GX"
    ),
    EmulatorCase("atari2600", "stella", "Stella", "Atari 2600/Stella"),
    EmulatorCase(
        "psx", "duckstation", "", "PS1/DuckStation OpenGL", "duckstation", "OpenGL"
    ),
    EmulatorCase(
        "psx", "duckstation", "", "PS1/DuckStation Vulkan", "duckstation", "Vulkan"
    ),
    EmulatorCase("xbox", "xemu", "", "Xbox/xemu", "xemu"),
)


def emulator_case(identifier: str) -> EmulatorCase:
    """Resolve only an implemented exact case.

    Raises:
        ValueError: If the case is unsupported or substitutes another core.
    """
    for case in EMULATOR_CASES:
        if case.identifier == identifier:
            return case
    msg = "Unsupported native emulator case"
    raise ValueError(msg)


def emulator_tier(tier: str) -> EmulatorCase | None:
    """Return the implemented case for a tier, or None for non-emulator tiers."""
    return next((case for case in EMULATOR_CASES if case.tier == tier), None)


class CatalogError(ValueError):
    """The advertised catalog or its provenance is inconsistent."""


def object_record(value: object) -> dict[str, object]:
    """Validate a JSON object without permitting untyped values downstream."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        msg = "Expected a JSON object"
        raise CatalogError(msg)
    return dict(value)


def array(value: object) -> list[object]:
    """Validate a JSON array at the data boundary."""
    if not isinstance(value, list):
        msg = "Expected a JSON array"
        raise CatalogError(msg)
    return list(value)


def text(value: object) -> str:
    """Require nonempty JSON text."""
    if not isinstance(value, str) or not value:
        msg = "Expected nonempty text"
        raise CatalogError(msg)
    return value


@dataclass(frozen=True)
class SystemRecord:
    """A stock declaration, not a claim of executable compatibility."""

    system: str
    fullname: str
    directory: str
    extensions: tuple[str, ...]
    backends: tuple[tuple[str, str], ...]
    command: str

    @property
    def rom_relative_directory(self) -> str | None:
        """Return the exact directory beneath the existing ROM mount, if any."""
        path = PurePosixPath(self.directory)
        root = PurePosixPath("/userdata/roms")
        if ".." in path.parts or not path.is_relative_to(root) or path == root:
            return None
        return str(path.relative_to(root))


@dataclass(frozen=True)
class Catalog:
    """Immutable pinned declarations used by selection and qualification."""

    systems: tuple[SystemRecord, ...]
    sha256: str
    revision: str

    def system(self, identifier: str) -> SystemRecord:
        """Find one stock ID, raising CatalogError rather than guessing a folder."""
        for system in self.systems:
            if system.system == identifier:
                return system
        msg = "Unknown system ID"
        raise CatalogError(msg)

    def counts(self) -> tuple[int, int, int, int]:
        """Return system, emulator, backend/core and complete mapping counts."""
        pairs = {pair for system in self.systems for pair in system.backends}
        return (
            len(self.systems),
            len({pair[0] for pair in pairs}),
            len(pairs),
            sum(len(system.backends) for system in self.systems),
        )


def _backends(value: object) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for raw in array(value):
        record = object_record(raw)
        name = text(record.get("name"))
        cores = array(record.get("cores"))
        pairs.extend((name, text(core)) for core in cores)
        if not cores:
            pairs.append((name, ""))
    if len(pairs) != len(set(pairs)):
        msg = "Duplicate backend/core mapping"
        raise CatalogError(msg)
    return tuple(pairs)


def load_catalog(path: Path = DEFAULT_CATALOG) -> Catalog:
    """Read maintained declarations and enforce their approved pin and totals.

    Args:
        path: Original-byte stock XML catalog, not operator configuration.

    Raises:
        CatalogError: If provenance, declarations or catalog totals disagree.
        OSError: If the catalog cannot be read.
    """
    original = path.read_bytes()
    if hashlib.sha256(original).hexdigest() != STOCK_SHA256:
        msg = "Stock catalog provenance mismatch"
        raise CatalogError(msg)
    # Exact original bytes were authenticated against the maintained stock pin.
    document = ET.fromstring(original)  # noqa: S314 - untrusted XML is rejected above.
    systems: list[SystemRecord] = []
    for entry in document.findall("system"):
        backends: list[tuple[str, str]] = []
        for emulator in entry.findall("emulators/emulator"):
            name = text(emulator.get("name"))
            cores = emulator.findall("cores/core")
            backends.extend((name, text(core.text)) for core in cores)
            if not cores:
                backends.append((name, ""))
        systems.append(
            SystemRecord(
                text(entry.findtext("name")),
                text(entry.findtext("fullname")),
                text(entry.findtext("path")),
                tuple(text(entry.findtext("extension")).split()),
                tuple(backends),
                text(entry.findtext("command")),
            )
        )
    catalog = Catalog(tuple(systems), STOCK_SHA256, STOCK_REVISION)
    if len({system.system for system in systems}) != len(systems):
        msg = "Duplicate system ID"
        raise CatalogError(msg)
    if catalog.counts() != (253, 98, 233, 477):
        msg = "Stock catalog mapping totals disagree"
        raise CatalogError(msg)
    return catalog


def reconcile_inventory(
    catalog: Catalog, inventory: object, candidates: object
) -> None:
    """Require exact equality to both retained research inventories.

    Raises:
        CatalogError: If provenance, IDs, extensions or mappings changed.
    """
    records = (object_record(inventory), object_record(candidates))
    if (
        records[0].get("source_sha256") != catalog.sha256
        or records[1].get("stock_catalog_sha256") != catalog.sha256
        or any(
            record.get("upstream_revision") != catalog.revision for record in records
        )
    ):
        msg = "Research provenance mismatch"
        raise CatalogError(msg)
    expected = {
        system.system: (system.extensions, system.backends)
        for system in catalog.systems
    }
    for record, ext_key, backend_key in (
        (records[0], "extensions", "emulators"),
        (records[1], "advertised_extensions", "advertised_emulators"),
    ):
        found: dict[str, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]] = {}
        for value in array(record.get("systems")):
            entry = object_record(value)
            identifier = text(entry.get("system"))
            if identifier in found:
                msg = "Duplicate research ID"
                raise CatalogError(msg)
            found[identifier] = (
                tuple(text(ext) for ext in array(entry.get(ext_key))),
                _backends(entry.get(backend_key)),
            )
        if found != expected:
            msg = "Research ID/extension/backend mapping mismatch"
            raise CatalogError(msg)
