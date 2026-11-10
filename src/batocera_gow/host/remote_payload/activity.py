"""Fail-closed Wolf idle rules shared by local tests and remote activation."""

import re
from collections.abc import Sequence

from batocera_gow.host.remote_payload.json_data import Json, record, sequence, text


class ActivityError(RuntimeError):
    """Refuse activation when activity is present or cannot be established."""


def list_payload(value: object, key: str) -> list[Json]:
    """Require a recognized successful API collection; unknown never means idle."""
    if isinstance(value, list):
        return sequence(value)
    if isinstance(value, dict):
        payload = record(value)
        if payload.get("success") is not False and isinstance(payload.get(key), list):
            return sequence(payload[key])
    message = "unrecognized or failed activity response; cannot prove idle"
    raise ActivityError(message)


def require_idle(
    sessions: object, lobbies: object, containers: Sequence[object]
) -> None:
    """Refuse sessions, lobbies and running or paused numeric/UUID app runners."""
    if list_payload(sessions, "sessions") or list_payload(lobbies, "lobbies"):
        message = "activation deferred: active or paused Wolf sessions or lobbies"
        raise ActivityError(message)
    for item in containers:
        container = record(item)
        state = record(container.get("State", {}))
        name = text(container.get("Name", "")).lstrip("/")
        if (state.get("Running") or state.get("Paused")) and re.search(
            r"_(?:[0-9]+|[0-9a-fA-F-]{36})$", name
        ):
            message = "activation deferred: running Wolf app"
            raise ActivityError(message)
