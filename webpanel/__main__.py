"""Run the web panel standalone: ``python -m webpanel``.

Without the userbot there is no session to persist, so this is only useful to
develop and test the API/frontend.
"""

import asyncio

from .runner import serve_standalone


def main() -> None:
    try:
        asyncio.run(serve_standalone())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
