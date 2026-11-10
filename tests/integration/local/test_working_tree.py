"""Declared-input identities include transitive source, assets and permissions."""

from pathlib import Path

import pytest

from batocera_gow.host.build import Build
from batocera_gow.host.common import ProjectPaths
from batocera_gow.provenance import (
    INPUT_FILES,
    INPUT_ROOTS,
    declared_inputs,
    tree_source,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a complete minimal build-input fixture, not a production checkout."""
    for name in INPUT_ROOTS:
        (tmp_path / name).mkdir(parents=True)
    for name in INPUT_FILES:
        (tmp_path / name).write_text("fixture\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "name",
    [
        "src/helper.py",
        "build-assets/launcher.sh",
        "tests/assets/input/pad.json",
        "uv.lock",
        "pyproject.toml",
        ".python-version",
        "LICENSE",
    ],
)
def test_consumed_changes_invalidate_identity(project: Path, name: str) -> None:
    """Every source/resource/dependency boundary participates in the same identity."""
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("before\n", encoding="utf-8")
    before = declared_inputs(project)["sha256"]
    path.write_text("after\n", encoding="utf-8")
    changed = declared_inputs(project)["sha256"]
    assert changed != before
    path.chmod(path.stat().st_mode ^ 0o100)
    assert declared_inputs(project)["sha256"] != changed


def test_added_deleted_helpers_and_bytecode_have_correct_effect(project: Path) -> None:
    """Bytecode cannot change provenance; new and removed maintained helpers do."""
    before = declared_inputs(project)["sha256"]
    cache = project / "src/__pycache__"
    cache.mkdir()
    (cache / "helper.pyc").write_bytes(b"transient")
    (project / "src/helper.pyc").write_bytes(b"transient")
    assert declared_inputs(project)["sha256"] == before
    helper = project / "src/helper.py"
    helper.write_text("new\n", encoding="utf-8")
    assert declared_inputs(project)["sha256"] != before
    helper.unlink()
    assert declared_inputs(project)["sha256"] == before


def test_symlink_cannot_import_unhashed_inputs(project: Path) -> None:
    """A declared source symlink is refused rather than following external bytes."""
    (project / "src/outside").symlink_to("/etc/hosts")
    with pytest.raises(ValueError, match="symlink"):
        declared_inputs(project)


def test_incomplete_layout_refuses_provenance(project: Path) -> None:
    """Old manifests cannot silently invent missing dependency inputs."""
    (project / "uv.lock").unlink()
    with pytest.raises(FileNotFoundError):
        declared_inputs(project)


def test_tree_snapshot_covers_runtime_asset_modes(tmp_path: Path) -> None:
    """Staged runtime identity detects executable permission changes."""
    launcher = tmp_path / "entrypoint.sh"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    before = tree_source(tmp_path)["sha256"]
    launcher.chmod(0o755)
    assert tree_source(tmp_path)["sha256"] != before


def test_changed_inputs_refuse_build_promotion(project: Path) -> None:
    """Build consumers refuse a source changed after the recorded snapshot."""
    (project / ".git").mkdir()
    (project / "output/gow-full-x86").mkdir(parents=True)
    build = Build(ProjectPaths(project), ["docker"], {}, working_tree=True)
    source = build.source_identity()
    build.verify_source(source)
    (project / "src/new-helper.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="candidate not promoted"):
        build.verify_source(source)
