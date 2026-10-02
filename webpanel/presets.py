"""API credential presets for the web login panel.

The list is intentionally empty.

Telegram's own sample API ids (the ones bundled with the open-source
clients, e.g. ``2040`` for Desktop, ``6`` for Android, ``8`` for iOS and
``2496`` for Web) are limited server-side and are **not** meant for
third-party apps released to users:

    "This API id is limited on the server side and is not suitable for
     apps released to end-users — using it for anything but testing
     purposes will result in the API_ID_PUBLISHED_FLOOD error for your
     users."
    — https://core.telegram.org/api/obtaining_api_id

Using them also puts the account under observation and can lead to bans.
Every user must supply their own api_id / api_hash from
https://my.telegram.org instead.
"""

from __future__ import annotations

import typing


class ApiPreset(typing.TypedDict):
    id: str
    name: str
    api_id: int
    api_hash: str
    note: str


API_PRESETS: list[ApiPreset] = []

PRESETS_WARNING = (
    "Use your own api_id and api_hash from https://my.telegram.org. "
    "Telegram's bundled sample keys are rate-limited and trigger "
    "API_ID_PUBLISHED_FLOOD."
)


def find_preset(preset_id: str) -> ApiPreset | None:
    """Return a preset by its id, or `None` if it doesn't exist."""

    for preset in API_PRESETS:
        if preset["id"] == preset_id:
            return preset

    return None
