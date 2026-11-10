"""Run local media commands through one explicit, immutable host configuration."""

import argparse
import json
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from batocera_gow.host.settings import HostSettings
from batocera_gow.host.ssh_config import SettingsError
from batocera_gow.runtime.media_catalog import CatalogError, load_catalog
from batocera_gow.runtime.mounted_media import (
    ContentRoots,
    MediaError,
    inspect_media,
    read_selection,
    select_media,
    write_selection,
)


def _write_json(value: object) -> None:
    """Emit exactly one public JSON result line, never private record contents."""
    sys.stdout.write(json.dumps(value) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Run local catalog/selection operations without SSH or implicit dotenv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--roms-root")
    parser.add_argument("--bios-root")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    catalog_command = subcommands.add_parser(
        "catalog", help="Print nonprivate stock counts or one system declaration"
    )
    catalog_command.add_argument("--system")
    subcommands.add_parser(
        "mounts", help="Print desired binds from explicit environment"
    )
    select = subcommands.add_parser(
        "select", help="Select synthetic or authorized mounted media locally"
    )
    select.add_argument("--system", required=True)
    select.add_argument("--roms-view", type=Path, required=True)
    select.add_argument("--record", type=Path, required=True)
    reproduce = subcommands.add_parser(
        "reproduce", help="Recheck one private selection, without rerolling"
    )
    reproduce.add_argument("--roms-view", type=Path, required=True)
    reproduce.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        overrides = {
            key: value
            for key, value in {
                "BATOCERA_GOW_ROMS_ROOT": args.roms_root,
                "BATOCERA_GOW_BIOS_ROOT": args.bios_root,
            }.items()
            if value is not None
        }
        settings = HostSettings.resolve(env_file=args.env_file, overrides=overrides)
        if args.operation == "catalog":
            catalog = load_catalog(
                args.project_root / "tests/assets/media/stock-es_systems.cfg"
            )
            if args.system:
                system = catalog.system(args.system)
                _write_json(
                    {
                        "system": system.system,
                        "directory": system.directory,
                        "extensions": system.extensions,
                        "backends": system.backends,
                        "stock_sha256": catalog.sha256,
                    }
                )
            else:
                _write_json(
                    {
                        "counts": catalog.counts(),
                        "stock_sha256": catalog.sha256,
                        "native_qualified": 0,
                    }
                )
        elif args.operation == "mounts":
            _write_json(ContentRoots.from_environment(settings.values).wolf_mounts())
        elif args.operation == "select":
            catalog = load_catalog(
                args.project_root / "tests/assets/media/stock-es_systems.cfg"
            )
            eligible = inspect_media(catalog.system(args.system), args.roms_view)
            if not eligible.candidates:
                _write_json(
                    {
                        "status": eligible.disposition,
                        "rejected_incomplete": eligible.rejected,
                        "native_executed": False,
                    }
                )
            else:
                write_selection(args.record, select_media(eligible, secrets.randbelow))
                _write_json({"status": "selected privately", "native_executed": False})
        else:
            read_selection(
                args.record,
                args.roms_view,
                catalog_path=args.project_root
                / "tests/assets/media/stock-es_systems.cfg",
            )
            _write_json(
                {"status": "private identity reproduced", "native_executed": False}
            )
    except (
        MediaError,
        CatalogError,
        SettingsError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        # OSError text and descriptor contents can contain private paths.
        message = (
            str(error)
            if isinstance(error, (MediaError, CatalogError, SettingsError))
            else (
                "Local media operation failed; verify --project-root "
                "and explicitly selected local paths"
            )
        )
        _write_json({"status": "error", "reason": message})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
