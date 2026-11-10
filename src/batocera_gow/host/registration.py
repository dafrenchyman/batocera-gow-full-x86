"""Formatting-preserving ownership-gated Wolf profile registration."""

import json
import re
import tomllib
from collections.abc import Sequence

import tomlkit
from tomlkit.items import AoT, Table

from batocera_gow.host.remote_payload.activation import source_hash
from batocera_gow.host.remote_payload.contracts import (
    PROFILE,
    REPOSITORY,
    RUNNER,
    TITLE,
)
from batocera_gow.host.remote_payload.json_data import Json, record, sequence


class RegistrationError(RuntimeError):
    """Refuse unsafe ownership, configuration or activity observations."""


def app_value(image: str, mounts: Sequence[str]) -> dict[str, Json]:
    """Build only the owned application with an immutable image and read-only binds."""
    if not (
        re.fullmatch(re.escape(REPOSITORY) + r"@sha256:[0-9a-f]{64}", image)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image)
    ):
        message = (
            "registration requires a verified experimental registry digest "
            "or local image ID"
        )
        raise RegistrationError(message)
    return {
        "title": TITLE,
        "start_virtual_compositor": True,
        "start_audio_server": True,
        "runner": {
            "type": "docker",
            "name": RUNNER,
            "image": image,
            "mounts": list(mounts),
            "devices": ["/dev/uinput:/dev/uinput:rwm"],
            "env": [],
            "ports": [],
            "base_create_json": json.dumps(
                {
                    "HostConfig": {
                        "IpcMode": "private",
                        "Privileged": False,
                        "ShmSize": 2 * 1024**3,
                        "NetworkMode": "bridge",
                        "CapAdd": ["NET_ADMIN", "SYS_NICE", "SYS_PTRACE"],
                    }
                },
                separators=(",", ":"),
            ),
        },
    }


def experiment(app: object) -> bool:
    """Identify reserved title or runner collisions across all profiles."""
    value = record(app)
    return (
        value.get("title") == TITLE
        or record(value.get("runner", {})).get("name") == RUNNER
    )


def without_experiment(value: object) -> dict[str, Json]:
    """Copy profile data while removing only the owned user's experiment."""
    result = record(value)
    profiles: list[Json] = []
    for item in sequence(result.get("profiles", [])):
        profile = record(item)
        if profile.get("id") == PROFILE:
            profile["apps"] = [
                app for app in sequence(profile.get("apps", [])) if not experiment(app)
            ]
        profiles.append(profile)
    result["profiles"] = profiles
    return result


def _application_tables(profile: Table) -> AoT:
    """Require application tables before modifying a profile's app collection."""
    apps = profile.get("apps")
    if not isinstance(apps, AoT):
        message = "expected application tables"
        raise RegistrationError(message)
    return apps


def _replace_owned_app(
    profile: Table, index: int, old: dict[str, Json], wanted: dict[str, Json]
) -> bool:
    """Replace a matching owned identity, or report an identical existing app."""
    if old.get("title") != TITLE or record(old.get("runner", {})).get("name") != RUNNER:
        message = "owned identity no longer matches"
        raise RegistrationError(message)
    if old == wanted:
        return False
    replacement = tomlkit.item(wanted)
    if not isinstance(replacement, Table):
        message = "invalid application table"
        raise RegistrationError(message)
    _application_tables(profile)[index] = replacement
    return True


def _append_app(profile: Table, wanted: dict[str, Json]) -> None:
    """Append the first owned app without rewriting unrelated TOML tables."""
    if "apps" not in profile:
        profile["apps"] = tomlkit.aot()
    table = tomlkit.table()
    for key, value in wanted.items():
        table.add(key, value)
    _application_tables(profile).append(table)


def transform_config(
    text: str,
    image: str,
    *,
    mounts: Sequence[str],
    owned: bool = False,
    expected_hash: str | None = None,
) -> str:
    """Insert or replace one owned app, preserving unrelated TOML bytes and values.

    Raises:
        RegistrationError: If source, profile or reserved identities are unsafe.
        ValueError: If input TOML is malformed.
    """
    if expected_hash is not None and source_hash(text) != expected_hash:
        message = "source config changed; refusing overwrite"
        raise RegistrationError(message)
    original = record(tomllib.loads(text))
    profiles = [record(item) for item in sequence(original.get("profiles", []))]
    matches = [
        index for index, profile in enumerate(profiles) if profile.get("id") == PROFILE
    ]
    if len(matches) != 1:
        message = "expected exactly one user profile"
        raise RegistrationError(message)
    wanted = app_value(image, mounts)
    collisions = [
        (profile_index, app_index, record(app))
        for profile_index, profile in enumerate(profiles)
        for app_index, app in enumerate(sequence(profile.get("apps", [])))
        if experiment(app)
    ]
    document = tomlkit.parse(text)
    tables = document.get("profiles")
    if not isinstance(tables, AoT):
        message = "expected profile tables"
        raise RegistrationError(message)
    selected = tables[matches[0]]
    if collisions:
        if not owned or len(collisions) != 1 or collisions[0][0] != matches[0]:
            message = (
                "experiment title or runner is occupied without matching ownership"
            )
            raise RegistrationError(message)
        _, app_index, old = collisions[0]
        if not _replace_owned_app(selected, app_index, old, wanted):
            return text
    else:
        _append_app(selected, wanted)
    result = tomlkit.dumps(document)
    if without_experiment(original) != without_experiment(tomllib.loads(result)):
        message = "transformation changed preexisting configuration"
        raise RegistrationError(message)
    return result
