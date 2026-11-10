"""Execute a source-only zip from memory-supplied bytes and remove it on exit."""

import base64
import runpy
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Materialize only checked source, never stdin requests, in temporary storage."""
    archive = base64.b64decode(sys.argv[1], validate=True)
    with tempfile.TemporaryDirectory(prefix="gow-remote-") as directory:
        path = Path(directory) / "source.zip"
        path.write_bytes(archive)
        sys.path.insert(0, str(path))
        runpy.run_path(str(path), run_name="__main__")


if __name__ == "__main__":
    main()
