"""Canonical, stdlib-only identities for declared build inputs.

Builds and native preflight use the same content and mode records. Generated
output, bytecode and unrelated documentation cannot alter this identity.
"""

import hashlib
import json
import stat
from pathlib import Path
from typing import TypedDict

DEFINITION = "batocera-gow-declared-inputs-v1"
INPUT_ROOTS = ("src", "build-assets", "tests/assets")
INPUT_FILES = (
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".dockerignore",
    "LICENSE",
)


class InputEntry(TypedDict):
    """A declared file or directory, with its permission bits and content hash."""

    mode: int
    type: str
    sha256: str | None


class InputManifest(TypedDict):
    """Versioned content identity, independent of Git and Docker identities."""

    schema: int
    definition: str
    entries: dict[str, InputEntry]
    sha256: str


def file_sha256(path: Path) -> str:
    """Hash a file in bounded memory without interpreting its bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _entry(path: Path) -> InputEntry:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        message = "Build input symlinks are not supported"
        raise ValueError(message)
    if stat.S_ISDIR(info.st_mode):
        return {"mode": stat.S_IMODE(info.st_mode), "type": "directory", "sha256": None}
    if not stat.S_ISREG(info.st_mode):
        message = "Build inputs must be regular files or directories"
        raise ValueError(message)
    digest = file_sha256(path)
    after = path.lstat()
    if (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    ):
        message = "Build input changed while computing provenance"
        raise ValueError(message)
    return {"mode": stat.S_IMODE(info.st_mode), "type": "file", "sha256": digest}


def _manifest(entries: dict[str, InputEntry], definition: str) -> InputManifest:
    content = {"schema": 1, "definition": definition, "entries": entries}
    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"schema": 1, "definition": definition, "entries": entries, "sha256": digest}


def tree_source(directory: Path) -> InputManifest:
    """Identify a supplied tree, refusing symlink/special inputs and ignoring bytecode.

    Args:
        directory: Explicit input tree, not a source-file ancestry guess.

    Returns:
        Deterministic paths, modes and SHA-256 identity for all maintained inputs.

    Raises:
        ValueError: An input is symlinked, special or changed during hashing.
        OSError: An input cannot be read.
    """
    root_entry = _entry(directory)
    if root_entry["type"] != "directory":
        message = "Input tree must be a real directory"
        raise ValueError(message)
    entries: dict[str, InputEntry] = {".": root_entry}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        entries[relative.as_posix()] = _entry(path)
    return _manifest(entries, "batocera-gow-tree-v1")


def declared_inputs(root: Path) -> InputManifest:
    """Identify the complete installed-source, asset and dependency input set.

    Missing required roots/files refuse old or incomplete layouts. Both committed
    and dirty builds use this definition; a Git revision cannot replace it.

    Args:
        root: Explicit independent project/build-input root.

    Returns:
        A versioned manifest comparable by build and native setup consumers.

    Raises:
        ValueError: Required inputs are missing, symlinked or of the wrong type.
        OSError: Input inspection or reading fails.
    """
    entries: dict[str, InputEntry] = {}
    for name in INPUT_ROOTS:
        directory = root / name
        for parent in directory.parents:
            if parent == root:
                break
            _entry(parent)
        entry = _entry(directory)
        if entry["type"] != "directory":
            message = "Declared build-input root must be a real directory"
            raise ValueError(message)
        entries[name] = entry
        tree = tree_source(directory)
        entries.update(
            {f"{name}/{path}": value for path, value in tree["entries"].items()}
        )
    for name in INPUT_FILES:
        entry = _entry(root / name)
        if entry["type"] != "file":
            message = "Declared build configuration must be a regular file"
            raise ValueError(message)
        entries[name] = entry
    return _manifest(entries, DEFINITION)


def project_mounts(root: Path) -> list[str]:
    """Expose only declared builder inputs, never private checkout/cache files.

    Args:
        root: Explicit independent build-input root.

    Returns:
        Docker argument-vector elements mounting inputs read-only under /project.

    Raises:
        ValueError: A source pathname cannot be represented safely by Docker's
            comma-separated mount interface.
    """
    arguments: list[str] = []
    for name in (*INPUT_ROOTS, *INPUT_FILES):
        source = root / name
        if "," in str(source):
            message = "Build-input paths cannot contain Docker mount separators"
            raise ValueError(message)
        arguments.extend(
            ["--mount", f"type=bind,src={source},dst=/project/{name},readonly"]
        )
    return arguments
