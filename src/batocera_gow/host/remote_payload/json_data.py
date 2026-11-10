"""Checked recursive JSON values for the stdlib remote and host boundaries."""

import json

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


def checked(value: object) -> Json:
    """Reject non-JSON objects instead of allowing untyped boundary data inward."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [checked(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Json] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                message = "JSON object keys must be strings"
                raise TypeError(message)
            result[key] = checked(item)
        return result
    message = "Expected JSON data"
    raise TypeError(message)


def decode(text: str) -> Json:
    """Decode text and validate its entire JSON data shape."""
    return checked(json.loads(text))


def record(value: object) -> dict[str, Json]:
    """Require an object, with checked nested values."""
    result = checked(value)
    if not isinstance(result, dict):
        message = "Expected JSON object"
        raise TypeError(message)
    return result


def sequence(value: object) -> list[Json]:
    """Require an array, with checked nested values."""
    result = checked(value)
    if not isinstance(result, list):
        message = "Expected JSON array"
        raise TypeError(message)
    return result


def text(value: object) -> str:
    """Require a string without coercing arbitrary objects."""
    if not isinstance(value, str):
        message = "Expected JSON string"
        raise TypeError(message)
    return value
