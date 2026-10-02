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
import secrets

import uvicorn

from .app import create_app
from .login import LoginManager

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

#: Environment variable holding the panel access token. When unset, a random
#: token is generated on every start and printed to the logs.
TOKEN_ENV = "WEBPANEL_TOKEN"

#: Public domain sources, in priority order. When neither is set, only the
#: access token is announced.
DOMAIN_ENVS = ("CTRLFREE_DOMAIN", "WEBPANEL_DOMAIN")

# Give uvicorn a moment to flush the final HTTP response before shutting down.
SHUTDOWN_GRACE = 0.5

#: Separator that makes the access link stand out in the console output.
BANNER = "====="


def _banner(label: str, value: str) -> str:
    """Surround a labelled ``value`` with ``=====`` lines and blank lines."""

    return f"\n\n{BANNER}\n\n{label}\n\n{value}\n\n{BANNER}\n\n"


def resolve_address(host: str | None, port: int | None) -> tuple[str, int]:
    host = host or os.environ.get("WEBPANEL_HOST", DEFAULT_HOST)
    port = port or int(
        os.environ.get("WEBPANEL_PORT") or os.environ.get("PORT", DEFAULT_PORT)
    )
    return host, port


def resolve_token() -> str:
    """Return the access token from ``WEBPANEL_TOKEN`` or a fresh random one."""

    return os.environ.get(TOKEN_ENV) or secrets.token_urlsafe(24)


def resolve_base_url() -> str | None:
    """Public base URL of the panel.

    Tries ``CTRLFREE_DOMAIN`` first, then ``WEBPANEL_DOMAIN``. Returns ``None``
    when neither is set, so only the access token is announced.
    """

    for name in DOMAIN_ENVS:
        domain = (os.environ.get(name) or "").strip()
        if not domain:
            continue
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        return domain.rstrip("/")

    return None


def _build_server(
    manager: LoginManager,
    host: str,
    port: int,
    token: str,
    log_level: str = "info",
) -> uvicorn.Server:
    config = uvicorn.Config(
        create_app(manager, token=token),
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
    token = resolve_token()
    manager = LoginManager(heroku)
    server = _build_server(manager, host, port, token)

    _announce(resolve_base_url(), token, host, port)
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
    token = resolve_token()
    manager = LoginManager(None)
    server = _build_server(manager, host, port, token)

    _announce(resolve_base_url(), token, host, port)
    await server.serve()


def _display_host(host: str) -> str:
    """Return a browser-friendly host for the announced link."""

    return "127.0.0.1" if host in ("", "0.0.0.0", "::") else host


def _announce(base_url: str | None, token: str, host: str, port: int) -> None:
    # Always show a usable link, even when no public domain is configured, so
    # the generated token can actually be used instead of the panel hanging.
    origin = base_url or f"http://{_display_host(host)}:{port}"
    url = f"{origin}/?token={token}"
    logger.info("Web login panel is available at %s", url)
    print(_banner("Web login panel:", url), end="")
    logger.info("Web panel access token: %s", token)
    print(_banner("Access token:", token), end="")
