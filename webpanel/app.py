"""FastAPI application exposing the web login API and its frontend.

JSON endpoints live under ``/api/*``; the vanilla HTML/CSS/JS panel is served
from :data:`STATIC_DIR` at ``/`` and ``/static/*``.
"""

from __future__ import annotations

import html
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .login import LoginError, LoginManager

STATIC_DIR = Path(__file__).parent / "static"

#: Environment variable holding the custom platform name shown in the footer.
PLATFORM_ENV = "HEROKU_PLATFORM"

#: Marker replaced with the platform footer when the panel HTML is served. The
#: platform name is exposed via a data attribute and rendered client-side with
#: the shared locales (``hosted``), so no user-facing text lives in the backend.
HOSTED_MARKER = '<span id="hosted"></span>'


def custom_platform() -> str | None:
    """Return the platform from ``HEROKU_PLATFORM``, or ``None`` when unset."""

    return (os.environ.get(PLATFORM_ENV) or "").strip() or None


class CredentialsPayload(BaseModel):
    api_id: int | None = None
    api_hash: str | None = None


class PhonePayload(BaseModel):
    phone: str


class CodePayload(BaseModel):
    code: str


class PasswordPayload(BaseModel):
    password: str


class AccessDenied(Exception):
    """Raised when the panel access token is missing or invalid."""


def create_app(manager: LoginManager, token: str) -> FastAPI:
    """Build a FastAPI app bound to the given :class:`LoginManager`.

    Every route requires ``token`` as a ``?token=`` query parameter. Static
    assets are served without a token so the "access denied" page can load its
    styles.
    """

    async def guard(access_token: str | None = Query(default=None, alias="token")):
        if access_token and secrets.compare_digest(
            access_token.encode("utf-8"), token.encode("utf-8")
        ):
            return
        raise AccessDenied

    app = FastAPI(
        title="Heroku Web Panel",
        version="1.0.0",
        dependencies=[Depends(guard)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.token = token

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    platform = custom_platform()
    host_attr = f' data-platform="{html.escape(platform)}"' if platform else ""
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace(
        HOSTED_MARKER, f'<span id="hosted"{host_attr}></span>'
    )

    @app.exception_handler(AccessDenied)
    async def _access_denied_handler(request: Request, _: AccessDenied):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "unauthorized"},
            )
        return FileResponse(STATIC_DIR / "denied.html", status_code=403)

    @app.exception_handler(LoginError)
    async def _login_error_handler(_: Request, exc: LoginError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.as_dict())

    @app.get("/", include_in_schema=False)
    async def index():
        return HTMLResponse(index_html)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "step": manager.step}

    @app.get("/api/state")
    async def state() -> dict:
        data = manager.state()
        data["platform"] = custom_platform()
        return data

    @app.post("/api/credentials")
    async def credentials(payload: CredentialsPayload) -> dict:
        await manager.configure(payload.api_id, payload.api_hash)
        return manager.state()

    @app.post("/api/send_code")
    async def send_code(payload: PhonePayload) -> dict:
        phone = await manager.send_code(payload.phone)
        return {"ok": True, "step": manager.step, "phone": phone}

    @app.post("/api/resend")
    async def resend() -> dict:
        phone = await manager.resend()
        return {"ok": True, "step": manager.step, "phone": phone}

    @app.post("/api/qr/start")
    async def qr_start() -> dict:
        qr = await manager.start_qr()
        return {"ok": True, "step": manager.step, "qr": qr}

    @app.get("/api/qr/status")
    async def qr_status() -> dict:
        state = manager.state()
        return {
            "ok": True,
            "step": state["step"],
            "qr": state["qr"],
            "password_hint": state["password_hint"],
            "account": state["account"],
        }

    @app.get("/api/qr/image")
    async def qr_image() -> Response:
        svg = manager.qr_svg()
        if svg is None:
            raise LoginError("qr_not_started", 404)
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.post("/api/qr/cancel")
    async def qr_cancel() -> dict:
        await manager.cancel_qr()
        return {"ok": True, "step": manager.step}

    @app.post("/api/sign_in")
    async def sign_in(payload: CodePayload) -> dict:
        await manager.sign_in(payload.code)
        return {
            "ok": True,
            "step": manager.step,
            "account": manager.state()["account"],
        }

    @app.post("/api/2fa")
    async def two_factor(payload: PasswordPayload) -> dict:
        await manager.sign_in_password(payload.password)
        return {
            "ok": True,
            "step": manager.step,
            "account": manager.state()["account"],
        }

    @app.post("/api/cancel")
    async def cancel() -> dict:
        await manager.close()
        return manager.state()

    return app
