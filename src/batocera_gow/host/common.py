"""Explicit project roots and ownership-preserving destination guards."""

import os
import shlex
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

NATIVE_HOME = "/etc/wolf/profile-data/user/WolfExperimental"
PROTECTED_HOME = "/etc/wolf/profile-data/user/Batocera"


def overlaps(first: Path, second: Path) -> bool:
    """Return whether either resolved tree contains the other."""
    return first == second or first in second.parents or second in first.parents


class ProjectPaths:
    """Guard destinations within an explicitly selected independent checkout.

    The original Batocera checkout is neither an input nor a required location.
    Git metadata must be private to this checkout, not a worktree indirection.
    Remote checks here are lexical; delivered code must additionally canonicalize
    and validate ownership on the host immediately before writing.
    """

    def __init__(self, root: Path, deployment_root: str | None = None) -> None:
        """Validate the selected root without running or modifying Git."""
        self.root = root.resolve(strict=True)
        metadata = self.root / ".git"
        if metadata.is_symlink() or not metadata.is_dir():
            message = "Select an independent project root with private .git metadata"
            raise ValueError(message)
        if (metadata / "objects/info/alternates").exists() or (
            metadata / "commondir"
        ).exists():
            message = "Shared Git metadata is forbidden"
            raise ValueError(message)
        self.deployment_root = deployment_root
        if deployment_root is not None:
            self._remote_path(deployment_root)

    def assert_local(self, path: str | Path) -> Path:
        """Accept only a descendant of the selected project after symlink resolution.

        The project root and ancestors are never owned disposable destinations.
        Git metadata is protected even though it lies inside the checkout.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        if self.root not in candidate.parents or overlaps(
            candidate, self.root / ".git"
        ):
            message = "Local destination escapes the owned project tree"
            raise ValueError(message)
        return candidate

    @staticmethod
    def _remote_path(path: str) -> PurePosixPath:
        candidate = PurePosixPath(path)
        if (
            not candidate.is_absolute()
            or str(candidate) != path
            or ".." in candidate.parts
            or candidate == PurePosixPath("/")
            or any(ord(character) < ord(" ") for character in path)
        ):
            message = "Remote destination must be a normalized absolute pathname"
            raise ValueError(message)
        protected = Path(PROTECTED_HOME)
        if overlaps(Path(path), protected):
            message = "Protected Batocera state is not an owned destination"
            raise ValueError(message)
        return candidate

    def assert_remote(self, path: str, *, native_home: bool = False) -> str:
        """Accept only the stable native home or an explicitly configured deployment."""
        candidate = self._remote_path(path)
        root = NATIVE_HOME if native_home else self.deployment_root
        if root is None:
            message = "Configure the owned remote deployment root explicitly"
            raise ValueError(message)
        allowed = self._remote_path(root)
        if candidate != allowed and allowed not in candidate.parents:
            message = "Remote destination escapes the owned tree"
            raise ValueError(message)
        return str(candidate)


def docker_command(values: Mapping[str, str] | None = None) -> list[str]:
    """Select Docker argv at a command boundary without changing host permissions."""
    environment = os.environ if values is None else values
    configured = environment.get("DOCKER")
    if configured is not None:
        result = shlex.split(configured)
        if not result:
            message = "DOCKER must name a command"
            raise ValueError(message)
        return result
    if os.access("/var/run/docker.sock", os.R_OK | os.W_OK):
        return ["docker"]
    return ["sudo", "-n", "docker"]


def isolated_environment(
    paths: ProjectPaths,
    values: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return invocation-owned cache/scratch settings without changing os.environ."""
    environment = dict(os.environ if values is None else values)
    environment["TMPDIR"] = str(paths.assert_local("output/tmp"))
    environment["XDG_CACHE_HOME"] = str(paths.assert_local("cache"))
    environment["PIP_CACHE_DIR"] = str(paths.assert_local("cache/pip"))
    return environment
