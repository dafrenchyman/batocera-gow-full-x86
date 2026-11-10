"""Ephemeral stock-image checker executed through stock Python stdin."""

import importlib
import importlib.util
import json
import os
import pkgutil
import subprocess
import sys
from pathlib import Path


def _runtime_modules(root: Path) -> list[str]:
    """Import every installed runtime module without a host implementation."""
    package = importlib.import_module("batocera_gow.runtime")
    imported = []
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        loaded = importlib.import_module(module.name)
        origin = Path(str(loaded.__file__)).resolve()
        if not origin.is_relative_to(root / "batocera_gow/runtime"):
            message = "Nonpackaged runtime import"
            raise RuntimeError(message)
        imported.append(module.name)
    importlib.import_module("batocera_gow.runtime.runtime").initialize_library_cache()
    return imported


def _stock_dependencies() -> tuple[str, ...]:
    """Resolve required production imports only from the stock Python installation."""
    dependencies = (
        "PIL.Image",
        "evdev",
        "pyudev",
        "configgen.emulatorlauncher",
        "evmapy",
        "sdl2",
    )
    for name in dependencies:
        loaded = importlib.import_module(name)
        if not Path(str(loaded.__file__)).resolve().is_relative_to(Path("/usr")):
            message = "Nonstock production dependency"
            raise RuntimeError(message)
    return dependencies


def check() -> dict[str, object]:
    """Check actual production resources and supported commands, never fake help."""
    root = Path("/opt/gow-full-x86")
    if (
        Path.cwd() != root
        or sys.version_info[:2] != (3, 12)
        or os.environ.get("PYTHONPATH")
    ):
        message = "Stock packaged interpreter context required"
        raise RuntimeError(message)
    imported = _runtime_modules(root)
    dependencies = _stock_dependencies()
    resources = (
        "alsa.conf",
        "bridge.env",
        "stock-share.tar",
        "suite-gamepad.json",
        "suite-es-input.cfg",
        "es_systems_gow_duckstation.cfg",
        "emulator-wrappers/duckstation-qt",
        "check-runtime.sh",
        "runtime.py",
    )
    for name in resources:
        path = root / name
        info = path.stat()
        if not path.is_file() or info.st_uid != 0 or info.st_mode & 0o022:
            message = "Missing or writable production resource"
            raise RuntimeError(message)
    for command in (
        [sys.executable, str(root / "runtime.py"), "--help"],
        [str(root / "check-runtime.sh")],
    ):
        subprocess.run(  # noqa: S603 - fixed packaged executables, no shell or operator command.
            command,
            check=True,
            timeout=60,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return {
        "status": "passed",
        "runtime_modules": imported,
        "stock_dependencies": list(dependencies),
        "resources": list(resources),
        "supported_smoke": ["runtime-help", "check-runtime"],
        "python": ".".join(str(value) for value in sys.version_info[:3]),
    }


def main() -> int:
    """Emit fixed sanitized outcomes without import errors or private paths."""
    try:
        result = check()
    except (ImportError, OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        sys.stdout.write(json.dumps({"status": "failed"}) + "\n")
        return 1
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
