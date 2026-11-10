"""Filesystem destination guards protect checkout and deployed state ownership."""

import os
import shutil
from pathlib import Path

import pytest

from batocera_gow.host.build import Build
from batocera_gow.host.common import ProjectPaths, isolated_environment


@pytest.fixture
def paths(tmp_path: Path) -> ProjectPaths:
    """Provide independent synthetic metadata without initializing a Git repository."""
    (tmp_path / ".git").mkdir()
    return ProjectPaths(tmp_path, "/srv/batocera-gow")


def test_owned_destination_succeeds_and_ancestors_are_refused(
    paths: ProjectPaths,
) -> None:
    """Only owned descendants may receive generated output."""
    assert paths.assert_local("output/test") == paths.root / "output/test"
    for candidate in (
        paths.root,
        paths.root.parent,
        paths.root.parent / "elsewhere",
        paths.root / ".git",
    ):
        with pytest.raises(ValueError, match="owned project"):
            paths.assert_local(candidate)


def test_symlink_ancestor_cannot_escape(paths: ProjectPaths, tmp_path: Path) -> None:
    """Resolved containment rejects a lexical child pointing outside the project."""
    link = tmp_path / "escape"
    link.symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="owned project"):
        paths.assert_local(link / "new-file")


def test_remote_destinations_require_explicit_owned_root(paths: ProjectPaths) -> None:
    """Remote lexical guards reject neighboring state before transport effects."""
    assert (
        paths.assert_remote("/srv/batocera-gow/diagnostics")
        == "/srv/batocera-gow/diagnostics"
    )
    home = "/etc/wolf/profile-data/user/WolfExperimental"
    assert (
        paths.assert_remote(home + "/userdata", native_home=True) == home + "/userdata"
    )
    for candidate, reason in (
        ("/etc/wolf", "Protected Batocera"),
        ("/srv", "owned tree"),
        ("/srv/other", "owned tree"),
        (home, "owned tree"),
        ("/srv/batocera-gow/../other", "normalized absolute"),
    ):
        with pytest.raises(ValueError, match=reason):
            paths.assert_remote(candidate)
    with pytest.raises(ValueError, match="root explicitly"):
        ProjectPaths(paths.root).assert_remote("/srv/batocera-gow")
    with pytest.raises(ValueError, match="Protected Batocera"):
        paths.assert_remote("/etc/wolf/profile-data/user/Batocera", native_home=True)


def test_shared_git_metadata_is_refused(tmp_path: Path) -> None:
    """An alternates file cannot make source ownership depend on another checkout."""
    metadata = tmp_path / ".git/objects/info"
    metadata.mkdir(parents=True)
    (metadata / "alternates").write_text("/foreign/objects\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Shared Git metadata"):
        ProjectPaths(tmp_path)


def test_isolation_returns_snapshot_without_mutating_caller(
    paths: ProjectPaths,
) -> None:
    """Invocation configuration is explicit and leaves caller environment borrowed."""
    source = {"KEEP": "unchanged"}
    environment = isolated_environment(paths, source)
    assert source == {"KEEP": "unchanged"}
    assert environment["KEEP"] == "unchanged"
    assert environment["TMPDIR"] == str(paths.root / "output/tmp")


def test_runtime_staging_retains_executable_launchers_without_host_dependencies(
    paths: ProjectPaths, pytestconfig: pytest.Config
) -> None:
    """Actual staging preserves callable launchers and only the runtime package."""
    source = pytestconfig.rootpath
    for directory in (
        "build-assets/runtime",
        "src/batocera_gow/runtime",
        "tests/assets/input",
    ):
        shutil.copytree(source / directory, paths.root / directory)
    shutil.copyfile(
        source / "src/batocera_gow/__init__.py",
        paths.root / "src/batocera_gow/__init__.py",
    )
    shutil.copyfile(source / "LICENSE", paths.root / "LICENSE")
    output = paths.root / "output/gow-full-x86"
    output.mkdir(parents=True)
    (output / "bridge.env").write_text("GOW_FIXTURE=1\n", encoding="utf-8")
    staged = Build(paths, [], {}).stage_runtime()
    for name in (
        "check-runtime.sh",
        "entrypoint.sh",
        "frontend.sh",
        "init-state.sh",
        "session.sh",
        "emulator-wrappers/duckstation-qt",
    ):
        assert os.access(staged / name, os.X_OK), name
    assert (staged / "batocera_gow/runtime/input_worker.py").is_file()
    assert (staged / "batocera_gow/runtime/emulator_probe.py").is_file()
    assert not (staged / "batocera_gow/host").exists()
    assert not (staged / "batocera_gow/builder").exists()
    assert not (staged / ".venv").exists()
