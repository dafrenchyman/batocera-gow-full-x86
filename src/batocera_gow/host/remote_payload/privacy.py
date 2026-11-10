"""Remove credential-bearing diagnostic fields and log lines before persistence."""

import re

from batocera_gow.host.remote_payload.json_data import Json

_FORBIDDEN = re.compile(
    r"(?i)(authorization|bearer\s|access[_ -]?token|password|pairing|"
    r"aes[_ -]?key|client_secret|gh[pousr]_[A-Za-z0-9]+)"
)


def sanitize(value: Json) -> Json:
    """Recursively discard sensitive keys and replace complete sensitive log lines."""
    if isinstance(value, str):
        return "\n".join(
            "[redacted sensitive log line]" if _FORBIDDEN.search(line) else line
            for line in value.splitlines()
        )
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize(item)
            for key, item in value.items()
            if not _FORBIDDEN.search(key)
        }
    return value
