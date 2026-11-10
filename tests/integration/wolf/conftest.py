"""Adapt explicit pytest authorization to the maintained native session service."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from batocera_gow.host.native_preparation import NativeSession, open_native_session
from batocera_gow.host.settings import HostSettings


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register inert options without resolving settings or contacting Wolf."""
    group = parser.getgroup("native Wolf")
    group.addoption("--authorize-native", action="store_true", default=False)
    group.addoption("--native-authorized-target", default=None)
    group.addoption("--native-authorized-root", default=None)
    group.addoption("--native-project-root", type=Path, default=None)
    group.addoption("--native-env-file", type=Path, default=None)


@pytest.fixture(scope="session")
def native_session(pytestconfig: pytest.Config) -> Iterator[NativeSession]:
    """Resolve shared settings only after deliberate native execution opt-in."""
    if not pytestconfig.getoption("authorize_native"):
        pytest.fail(
            "Native execution requires explicit --authorize-native", pytrace=False
        )
    env_file: Path | None = pytestconfig.getoption("native_env_file")
    project_root: Path | None = pytestconfig.getoption("native_project_root")
    settings = HostSettings.resolve(env_file=env_file)
    workers: object = pytestconfig.getoption("numprocesses", default=None)
    worker_count = str(workers) if workers is not None else None
    with open_native_session(
        settings,
        project_root=project_root or pytestconfig.rootpath,
        authorized_target=pytestconfig.getoption("native_authorized_target"),
        authorized_root=pytestconfig.getoption("native_authorized_root"),
        enabled=True,
        workers=worker_count,
        worker_environment=os.environ,
    ) as session:
        yield session
