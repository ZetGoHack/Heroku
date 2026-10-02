"""FastAPI application exposing the web login API and its frontend.

JSON endpoints live under ``/api/*``; the vanilla HTML/CSS/JS panel is served
from :data:`STATIC_DIR` at ``/`` and ``/static/*``.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .login import LoginError, LoginManager

STATIC_DIR = Path(__file__).parent / "static"


class CredentialsPayload(BaseModel):
    api_id: int | None = None
    api_hash: str | None = None


class PhonePayload(BaseModel):
    phone: str


class CodePayload(BaseModel):
    code: str


class PasswordPayload(BaseModel):
    password: str


def create_app(manager: LoginManager) -> FastAPI:
    """Build a FastAPI app bound to the given :class:`LoginManager`."""

    app = FastAPI(title="Heroku Web Panel", version="1.0.0")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(LoginError)
    async def _login_error_handler(_: Request, exc: LoginError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.as_dict())

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "step": manager.step}

    @app.get("/api/state")
    async def state() -> dict:
        data = manager.state()
        data["platform"] = os.environ.get("HEROKU_PLATFORM") or "Heroku"
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
