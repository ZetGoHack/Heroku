"""Telegram login state machine used by the web panel.

The manager owns a single temporary :class:`~heroku.tl_cache.CustomTelegramClient`
backed by a :class:`~herokutl.sessions.MemorySession`. It walks through the
steps ``credentials -> phone -> code -> (password) -> done`` and signals
completion through :attr:`LoginManager.logged_in`.

All :mod:`herokutl` exceptions are translated into :class:`LoginError`, which
carries the HTTP status code and a machine-readable error code so the API layer
stays thin.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import re
import string
import struct
import typing
from datetime import datetime, timezone

from herokutl.errors import (
    FloodWaitError,
    ForbiddenError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    SessionPasswordNeededError,
)
from herokutl.sessions import MemorySession
from herokutl.tl import functions as tl_functions
from herokutl.tl.functions.account import GetPasswordRequest
from herokutl.tl.functions.auth import SendCodeRequest
from herokutl.tl.tlobject import TLRequest
from herokutl.tl.types import CodeSettings
from herokutl.utils import parse_phone

from heroku.qr import ERROR_CORRECT_Q, QRCode
from heroku.tl_cache import CustomTelegramClient
from heroku.version import __version__

if typing.TYPE_CHECKING:
    from heroku.main import Heroku

logger = logging.getLogger(__name__)

# RECAPTCHA_CHECK_<action>__<sitekey>
RECAPTCHA_RE = re.compile(r"RECAPTCHA_CHECK_([A-Za-z0-9_]+?)__([A-Za-z0-9_-]+)")


class _InvokeWithReCaptchaRequest(TLRequest):
    """Fallback for ``functions.InvokeWithReCaptchaRequest``.

    ``invokeWithReCaptcha`` is a generic wrapper: its ``{X:Type}`` marker is
    not serialized, so the payload is just the token plus the wrapped query.
    Used only if the bundled TL layer lacks the generated class.
    """

    CONSTRUCTOR_ID = 0xADBB0F94
    SUBCLASS_OF_ID = 0x00000000

    def __init__(self, token: str, query):
        self.token = token
        self.query = query

    def to_dict(self) -> dict:
        return {
            "_": "InvokeWithReCaptchaRequest",
            "token": self.token,
            "query": self.query.to_dict() if self.query is not None else None,
        }

    def __bytes__(self) -> bytes:
        return b"".join(
            (
                struct.pack("<I", self.CONSTRUCTOR_ID),
                self.serialize_bytes(self.token),
                bytes(self.query),
            )
        )

    @classmethod
    def from_reader(cls, reader):
        return cls(reader.tgread_string(), reader.tgread_object())


InvokeWithReCaptchaRequest = getattr(
    tl_functions,
    "InvokeWithReCaptchaRequest",
    _InvokeWithReCaptchaRequest,
)


class LoginError(Exception):
    """Login failure with an HTTP status and a machine-readable code."""

    def __init__(self, code: str, status: int = 400, **extra: typing.Any):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra

    def as_dict(self) -> dict:
        return {"ok": False, "error": self.code, **self.extra}


class LoginManager:
    """Holds the temporary login client and drives the login flow."""

    def __init__(self, heroku: "Heroku | None" = None):
        self.heroku = heroku
        self.client: CustomTelegramClient | None = None
        self.api_id: int | None = None
        self.api_hash: str | None = None
        self.phone: str | None = None
        self.password_hint: str | None = None
        self.me: typing.Any = None
        self.avatar: str | None = None
        self.step = "credentials"
        self.logged_in = asyncio.Event()
        self._lock = asyncio.Lock()
        self._recaptcha: dict | None = None
        self._pending_send_code: typing.Any = None
        self._qr: typing.Any = None
        self._qr_task: asyncio.Task | None = None
        self._qr_error: str | None = None

        api_token = getattr(heroku, "api_token", None) if heroku is not None else None
        if api_token is not None:
            try:
                self.api_id = int(api_token.ID)
                self.api_hash = str(api_token.HASH)
            except Exception:
                logger.debug("Failed to read prefilled API credentials", exc_info=True)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    @property
    def has_credentials(self) -> bool:
        return self.api_id is not None and self.api_hash is not None

    def state(self) -> dict:
        return {
            "ok": True,
            "step": self.step,
            "has_credentials": self.has_credentials,
            "api_id": self.api_id,
            "phone": self.phone,
            "password_hint": self.password_hint,
            "recaptcha": dict(self._recaptcha) if self._recaptcha else None,
            "qr": self.qr_info(),
            "account": self._account(),
        }

    def _account(self) -> dict | None:
        if self.me is None:
            return None

        return {
            "id": self.me.id,
            "username": getattr(self.me, "username", None),
            "first_name": getattr(self.me, "first_name", None),
            "last_name": getattr(self.me, "last_name", None),
            "avatar": self.avatar,
        }

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------
    def _build_client(self) -> CustomTelegramClient:
        heroku = self.heroku
        connection = getattr(heroku, "conn", None) if heroku is not None else None
        proxy = getattr(heroku, "proxy", None) if heroku is not None else None
        device_model = "Heroku Web"
        system_version = "Windows 10"

        if heroku is not None:
            try:
                from heroku.main import generate_random_system_version, get_app_name

                device_model = get_app_name()
                system_version = generate_random_system_version()
            except Exception:
                logger.debug("Failed to build device fingerprint", exc_info=True)

        kwargs: dict[str, typing.Any] = {
            "connection_retries": None,
            "device_model": device_model,
            "system_version": system_version,
            "app_version": ".".join(map(str, __version__)) + " x64",
            "lang_code": "en",
            "system_lang_code": "en-US",
        }
        if connection is not None:
            kwargs["connection"] = connection
        if proxy is not None:
            kwargs["proxy"] = proxy

        return CustomTelegramClient(
            MemorySession(),
            self.api_id,
            self.api_hash,
            **kwargs,
        )

    def _ensure_client(self) -> CustomTelegramClient:
        if not self.has_credentials:
            raise LoginError("credentials_required", 400)

        if self.client is None:
            self.client = self._build_client()

        return self.client

    async def _reset_client(self) -> None:
        await self._cancel_qr()

        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                logger.debug("Failed to disconnect stale client", exc_info=True)

        self.client = None
        self.phone = None
        self.password_hint = None
        self.avatar = None
        self._reset_recaptcha()

    async def close(self) -> None:
        """Disconnect the temporary client and reset transient state."""

        async with self._lock:
            await self._reset_client()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    async def configure(
        self,
        api_id: int | None,
        api_hash: str | None,
    ) -> None:
        """Validate and persist API credentials, then move to the phone step."""

        if not isinstance(api_id, int) or isinstance(api_id, bool) or api_id <= 0:
            raise LoginError("invalid_api_id", 400)

        api_hash = (api_hash or "").strip().lower()
        if len(api_hash) != 32 or any(c not in string.hexdigits for c in api_hash):
            raise LoginError("invalid_api_hash", 400)

        async with self._lock:
            if (api_id, api_hash) != (self.api_id, self.api_hash):
                await self._reset_client()
                self.api_id = api_id
                self.api_hash = api_hash
                if self.heroku is not None:
                    try:
                        from heroku import main

                        main.save_config_key("api_id", int(api_id))
                        main.save_config_key("api_hash", api_hash)
                    except Exception:
                        logger.exception("Failed to persist API credentials")

            self.step = "phone"

    @staticmethod
    def _parse_recaptcha(error: BaseException) -> dict | None:
        message = getattr(error, "message", None) or str(error)
        match = RECAPTCHA_RE.search(message or "")
        if not match:
            return None
        return {"action": match.group(1), "sitekey": match.group(2)}

    def _reset_recaptcha(self) -> None:
        self._recaptcha = None
        self._pending_send_code = None

    def _build_send_code_request(self, phone: str):
        # Mirrors Telethon's send_code_request, which uses empty CodeSettings.
        return SendCodeRequest(phone, self.api_id, self.api_hash, CodeSettings())

    def _apply_sent_code(self, phone: str, result) -> None:
        if self.client is None:
            return

        hashes = getattr(self.client, "_phone_code_hash", None)
        if isinstance(hashes, dict) and getattr(result, "phone_code_hash", None):
            hashes[phone] = result.phone_code_hash

        self.client._phone = phone

    async def send_code(self, phone: str) -> str:
        """Request a login code for the given phone number."""

        async with self._lock:
            parsed = parse_phone(phone)

            if not parsed:
                raise LoginError("invalid_phone", 400)

            client = self._ensure_client()
            request = self._build_send_code_request(parsed)

            try:
                await client.connect()
                result = await client(request)
            except FloodWaitError as e:
                raise LoginError("flood_wait", 429, seconds=e.seconds)
            except PhoneNumberInvalidError:
                raise LoginError("invalid_phone", 400)
            except (ForbiddenError, RPCError) as e:
                recaptcha = self._parse_recaptcha(e)
                if recaptcha:
                    self._recaptcha = recaptcha
                    self._pending_send_code = request
                    self.phone = parsed
                    self.step = "recaptcha"
                    raise LoginError(
                        "recaptcha_required",
                        403,
                        action=recaptcha["action"],
                        sitekey=recaptcha["sitekey"],
                    )
                raise LoginError("send_code_failed", 502)
            except LoginError:
                raise
            except Exception:
                logger.exception("Failed to send login code")
                raise LoginError("send_code_failed", 502)

            self._reset_recaptcha()
            self._apply_sent_code(parsed, result)
            self.phone = parsed
            self.step = "code"
            return parsed

    async def send_code_with_recaptcha(self, token: str) -> str:
        """Retry ``auth.sendCode`` wrapped in ``invokeWithReCaptcha``."""

        async with self._lock:
            if (
                self.client is None
                or self.phone is None
                or self._pending_send_code is None
            ):
                raise LoginError("recaptcha_not_pending", 400)

            token = (token or "").strip()
            if not token:
                raise LoginError("recaptcha_token_required", 400)

            wrapped = InvokeWithReCaptchaRequest(
                token=token,
                query=self._pending_send_code,
            )

            try:
                result = await self.client(wrapped)
            except FloodWaitError as e:
                raise LoginError("flood_wait", 429, seconds=e.seconds)
            except (ForbiddenError, RPCError) as e:
                if self._parse_recaptcha(e):
                    raise LoginError("recaptcha_failed", 403)
                raise LoginError("sign_in_failed", 502)
            except Exception:
                logger.exception("Failed to complete reCAPTCHA")
                raise LoginError("sign_in_failed", 502)

            phone = self.phone
            self._reset_recaptcha()
            self._apply_sent_code(phone, result)
            self.step = "code"
            return phone

    # ------------------------------------------------------------------
    # QR login (avoids auth.sendCode and its reCAPTCHA)
    # ------------------------------------------------------------------
    def qr_info(self) -> dict | None:
        if self._qr is None:
            return None

        expires_in = None
        try:
            expires = self._qr.expires
            if isinstance(expires, datetime):
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                expires_in = max(
                    0,
                    int((expires - datetime.now(timezone.utc)).total_seconds()),
                )
        except Exception:
            expires_in = None

        return {
            "url": self._qr.url,
            "expires_in": expires_in,
            "error": self._qr_error,
        }

    def qr_svg(self) -> str | None:
        if self._qr is None:
            return None

        code = QRCode(border=2, error_correction=ERROR_CORRECT_Q)
        code.add_data(self._qr.url)
        code.make()
        matrix = code.get_matrix()
        size = len(matrix)
        cells = "".join(
            f'<rect x="{x}" y="{y}" width="1" height="1" rx="0.34"/>'
            for y, row in enumerate(matrix)
            for x, cell in enumerate(row)
            if cell
        )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'shape-rendering="geometricPrecision">'
            f'<rect width="{size}" height="{size}" fill="#ffffff"/>'
            f'<g fill="#6c60cf">{cells}</g></svg>'
        )

    async def _cancel_qr(self) -> None:
        task = self._qr_task
        self._qr_task = None
        self._qr = None
        self._qr_error = None

        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def cancel_qr(self) -> None:
        async with self._lock:
            await self._cancel_qr()
            if self.step == "qr":
                self.step = "phone"

    async def start_qr(self) -> dict:
        async with self._lock:
            client = self._ensure_client()

            if self._qr_task is not None and not self._qr_task.done():
                return self.qr_info()

            try:
                await client.connect()
                self._qr = await client.qr_login()
            except FloodWaitError as e:
                raise LoginError("flood_wait", 429, seconds=e.seconds)
            except (ForbiddenError, RPCError) as e:
                recaptcha = self._parse_recaptcha(e)
                if recaptcha:
                    self._recaptcha = recaptcha
                    self.step = "recaptcha"
                    raise LoginError(
                        "recaptcha_required",
                        403,
                        action=recaptcha["action"],
                        sitekey=recaptcha["sitekey"],
                    )
                raise LoginError("qr_failed", 502)
            except LoginError:
                raise
            except Exception:
                logger.exception("Failed to start QR login")
                raise LoginError("qr_failed", 502)

            self._qr_error = None
            self.phone = None
            self._reset_recaptcha()
            self.step = "qr"
            self._qr_task = asyncio.create_task(self._qr_loop())
            return self.qr_info()

    async def _qr_loop(self) -> None:
        try:
            while self.client is not None and not self.logged_in.is_set():
                try:
                    user = await self._qr.wait()
                except asyncio.TimeoutError:
                    try:
                        await self._qr.recreate()
                    except Exception:
                        logger.exception("Failed to refresh QR login token")
                        self._qr_error = "qr_expired"
                        return
                    continue
                except SessionPasswordNeededError:
                    self.step = "password"
                    self.password_hint = await self._fetch_password_hint()
                    return
                except Exception:
                    logger.exception("QR login failed")
                    self._qr_error = "qr_failed"
                    return

                if user is not None:
                    await self._complete(user)
                    return
        except asyncio.CancelledError:
            raise

    async def resend(self) -> str:
        """Re-request a login code for the phone number used previously."""

        if not self.phone:
            raise LoginError("phone_required", 400)

        return await self.send_code(self.phone)

    async def sign_in(self, code: str) -> None:
        """Complete login using the code. Raises 2FA error if password needed."""

        async with self._lock:
            if self.client is None or self.phone is None:
                raise LoginError("phone_required", 400)

            code = "".join((code or "").split())
            if not code or any(c not in string.digits for c in code):
                raise LoginError("invalid_code", 403)

            try:
                user = await self.client.sign_in(self.phone, code=code)
            except SessionPasswordNeededError:
                self.step = "password"
                self.password_hint = await self._fetch_password_hint()
                raise LoginError("2fa_required", 401, hint=self.password_hint)
            except PhoneCodeInvalidError:
                raise LoginError("invalid_code", 403)
            except PhoneCodeExpiredError:
                raise LoginError("code_expired", 404)
            except FloodWaitError as e:
                raise LoginError("flood_wait", 429, seconds=e.seconds)
            except Exception:
                logger.exception("Failed to sign in with code")
                raise LoginError("sign_in_failed", 502)

            await self._complete(user)

    async def sign_in_password(self, password: str) -> None:
        """Complete a 2FA-protected login."""

        async with self._lock:
            if self.client is None:
                raise LoginError("phone_required", 400)

            if not password:
                raise LoginError("invalid_password", 403)

            try:
                if self.phone:
                    user = await self.client.sign_in(self.phone, password=password)
                else:
                    user = await self.client.sign_in(password=password)
            except PasswordHashInvalidError:
                raise LoginError("invalid_password", 403)
            except FloodWaitError as e:
                raise LoginError("flood_wait", 429, seconds=e.seconds)
            except Exception:
                logger.exception("Failed to sign in with password")
                raise LoginError("sign_in_failed", 502)

            await self._complete(user)

    async def _fetch_password_hint(self) -> str | None:
        try:
            password = await self.client(GetPasswordRequest())
            return password.hint or None
        except Exception:
            logger.debug("Failed to fetch 2FA hint", exc_info=True)
            return None

    async def _fetch_avatar(self, user: typing.Any) -> str | None:
        if self.client is None or user is None or not getattr(user, "photo", None):
            return None

        try:
            data = await self.client.download_profile_photo(user, file=bytes)
        except Exception:
            logger.debug("Failed to download profile photo", exc_info=True)
            return None

        if isinstance(data, (bytes, bytearray)) and data:
            return "data:image/jpeg;base64," + base64.b64encode(data).decode()

        return None

    async def _complete(self, user: typing.Any) -> None:
        if user is None and self.client is not None:
            user = await self.client.get_me()

        self.me = user

        if user is not None and self.client is not None:
            self.client._tg_id = user.id
            self.client.tg_id = user.id
            self.client.hikka_me = user
            self.client.heroku_me = user
            self.avatar = await self._fetch_avatar(user)

        self.step = "done"
        self.logged_in.set()
