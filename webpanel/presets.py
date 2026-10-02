"""Ready-to-use API credentials presets.

.. warning::

    Official Telegram client credentials are published by Telegram and are
    intended to be used by Telegram's own clients. Using them for a
    third-party userbot violates Telegram's Terms of Service and may lead to
    account restrictions. Use them at your own risk.
"""

from __future__ import annotations

import typing


class ApiPreset(typing.TypedDict):
    id: str
    name: str
    api_id: int
    api_hash: str
    note: str


API_PRESETS: list[ApiPreset] = [
    {
        "id": "telegram-desktop",
        "name": "Telegram Desktop",
        "api_id": 2040,
        "api_hash": "b18441a1ff607e10a989891a5462e627",
        "note": "Official Telegram Desktop credentials",
    },
    {
        "id": "telegram-android",
        "name": "Telegram Android",
        "api_id": 6,
        "api_hash": "eb06d4abfb49dc3eeb1aeb98ae0f581e",
        "note": "Official Telegram Android credentials",
    },
    {
        "id": "telegram-ios",
        "name": "Telegram iOS",
        "api_id": 8,
        "api_hash": "7245de8e747a0d6fbe11f7cc14fcc0bb",
        "note": "Official Telegram iOS credentials",
    },
    {
        "id": "telegram-web",
        "name": "Telegram Web",
        "api_id": 2496,
        "api_hash": "8da85b0d5bfe62527ea62dad0f0c89ec",
        "note": "Official Telegram Web credentials",
    },
]

PRESETS_WARNING = (
    "Official Telegram credentials are meant for Telegram's own clients. "
    "Using them for a userbot violates the Terms of Service and may get the "
    "account restricted. Prefer your own credentials from https://my.telegram.org"
)


def find_preset(preset_id: str) -> ApiPreset | None:
    """Return a preset by its id, or `None` if it doesn't exist."""

    for preset in API_PRESETS:
        if preset["id"] == preset_id:
            return preset

    return None
