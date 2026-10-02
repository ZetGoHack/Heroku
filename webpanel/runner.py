"""Uvicorn lifecycle for the web login panel.

The panel must never live side by side with the userbot: once login succeeds the
session is saved and the process is replaced by the userbot (``execve`` via
:func:`heroku._internal.restart`). The web server is shut down right before
that.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import uvicorn

from .app import create_app
from .login import LoginManager

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

# Give uvicorn a moment to flush the final HTTP response before shutting down.
SHUTDOWN_GRACE = 0.5


def resolve_address(host: str | None, port: int | None) -> tuple[str, int]:
    host = host or os.environ.get("WEBPANEL_HOST", DEFAULT_HOST)
    port = port or int(
        os.environ.get("WEBPANEL_PORT") or os.environ.get("PORT", DEFAULT_PORT)
    )
    return host, port


def _build_server(
    manager: LoginManager,
    host: str,
    port: int,
    log_level: str = "info",
) -> uvicorn.Server:
    config = uvicorn.Config(
        create_app(manager),
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )
    server = uvicorn.Server(config)

    # uvicorn would otherwise hijack SIGINT/SIGTERM from the userbot process.
    server.install_signal_handlers = lambda: None

    return server


async def run_web_login(
    heroku,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Run the web login panel until the user logs in and the session is saved.

    On success this calls :meth:`heroku.main.Heroku.save_client_session`, which
    disconnects the temporary client and restarts the process via ``execve``.
    """

    host, port = resolve_address(host, port)
    manager = LoginManager(heroku)
    server = _build_server(manager, host, port)

    _announce(host, port)
    task = asyncio.create_task(server.serve())

    try:
        await manager.logged_in.wait()
        # Let the successful HTTP response reach the browser.
        await asyncio.sleep(SHUTDOWN_GRACE)
    finally:
        server.should_exit = True
        with contextlib.suppress(Exception):
            await task

        if not manager.logged_in.is_set():
            with contextlib.suppress(Exception):
                await manager.close()

    if manager.client is None:
        logger.error("Login finished without a client, aborting")
        return

    if heroku is None:
        logger.warning("Standalone mode: session is authenticated but not persisted")
        return

    logger.info("Login successful, saving session and restarting the userbot")
    try:
        await heroku.save_client_session(manager.client)
    except Exception:
        logger.exception("Failed to save session after web login")


async def serve_standalone(
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Run the panel without the userbot (useful to develop the frontend)."""

    host, port = resolve_address(host, port)
    manager = LoginManager(None)
    server = _build_server(manager, host, port)

    _announce(host, port)
    await server.serve()


def _announce(host: str, port: int) -> None:
    logger.info("Web login panel is available at http://%s:%s", host, port)
    print(f"\033[0;96mWeb login panel: http://{host}:{port}\033[0m")
