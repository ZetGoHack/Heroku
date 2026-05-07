"""Responsible for web init and mandatory ops"""

#    Friendly Telegram (telegram userbot)
#    Copyright (C) 2018-2021 The Authors

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Heroku Userbot
# 🌐 https://github.com/hikariatama/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import base64
import contextlib
import hmac
import inspect
import logging
import os
import secrets
import subprocess

import aiohttp_jinja2
import jinja2
from aiohttp import web

from ..database import Database
from ..loader import Modules
from ..tl_cache import CustomTelegramClient
from . import proxypass, root

logger = logging.getLogger(__name__)


class Web(root.Web):
    def __init__(self, **kwargs):
        self.runner = None
        self.port = None
        self.running = asyncio.Event()
        self.ready = asyncio.Event()
        self.client_data = {}
        self.app = web.Application(client_max_size=1024 * 1024)
        self.proxypasser = None
        self._username = None
        self._password = None
        self._basic_auth = False
        aiohttp_jinja2.setup(
            self.app,
            filters={"getdoc": inspect.getdoc, "ascii": ascii},
            loader=jinja2.FileSystemLoader("web-resources"),
        )
        self.app["static_root_url"] = "/static"

        super().__init__(**kwargs)

        self._setup_basic_auth()
        self.app.router.add_get("/favicon.ico", self.favicon)
        self.app.router.add_static("/static/", "web-resources/static")

    def _setup_basic_auth(self):
        if not self.first_start:
            return

        self.app.middlewares.append(self._first_start_middleware)

    def _ensure_basic_auth_credentials(self):
        if self._username and self._password:
            return

        self._username = self._rand(12)
        self._password = self._rand(20)

        logger.debug(
            "First start. Starting web with %s username and %s password",
            self._username,
            self._password,
        )

    def _rand(self, length: int) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @web.middleware
    async def _first_start_middleware(self, request, handler):
        if not self.first_start or not self._basic_auth:
            return await handler(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return self._auth_required_resp()

        creds = auth_header.split(" ", 1)[1].strip()
        try:
            dec_creds = base64.b64decode(creds).decode("utf-8")
        except Exception:
            return self._auth_required_resp()

        username, _, password = dec_creds.partition(":")
        if not password:
            return self._auth_required_resp()
        if len(password) >= 1000 or len(username) >= 1000:
            return self._auth_required_resp()

        if not (
            hmac.compare_digest(username, self._username)
            and hmac.compare_digest(password, self._password)
        ):
            return self._auth_required_resp()

        return await handler(request)

    @staticmethod
    def _auth_required_resp() -> web.Response:
        return web.Response(
            status=401,
            text="Authorization required",
            headers={
                "WWW-Authenticate": 'Basic realm="Heroku Web Setup"',
                "Cache-Control": "no-store",
            },
        )

    async def start_if_ready(
        self,
        total_count: int,
        port: int,
        proxy_pass: bool = False,
    ):
        if total_count <= len(self.client_data):
            if not self.running.is_set():
                await self.start(port, proxy_pass=proxy_pass)

            self.ready.set()

    async def get_url(self, proxy_pass: bool) -> str:
        url = None

        if all(option in os.environ for option in {"LAVHOST", "USER", "SERVER"}):
            return f"https://{os.environ['USER']}.{os.environ['SERVER']}.lavhost.ml"

        if proxy_pass:
            with contextlib.suppress(Exception):
                url = await self.proxypasser.get_url(timeout=10)

        if not url:
            ip = (
                "127.0.0.1"
                if "DOCKER" not in os.environ
                else subprocess.run(
                    ["hostname", "-i"],
                    stdout=subprocess.PIPE,
                    check=True,
                    timeout=5,
                    stderr=subprocess.PIPE,
                )
                .stdout.decode("utf-8")
                .strip()
            )

            ip = os.environ.get("HEROKU_IP", ip)

            url = f"http://{ip}:{self.port}"

        self._basic_auth = self.first_start
        if self._basic_auth:
            self._ensure_basic_auth_credentials()

        self.url = url
        return url

    async def start(self, port: int, proxy_pass: bool = False):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.port = os.environ.get("PORT", port)
        site = web.TCPSite(self.runner, None, self.port)
        self.proxypasser = proxypass.ProxyPasser(port=self.port)
        await site.start()

        await self.get_url(proxy_pass)

        self.running.set()
        print(f"Heroku Userbot Web Interface running on {self.port}")

    async def stop(self):
        await self.runner.shutdown()
        await self.runner.cleanup()
        self.running.clear()
        self.ready.clear()

    async def add_loader(
        self,
        client: CustomTelegramClient,
        loader: Modules,
        db: Database,
    ):
        self.client_data[client.tg_id] = (loader, client, db)

    @staticmethod
    async def favicon(_):
        return web.Response(
            status=301,
            headers={"Location": "https://i.imgur.com/IRAiWBo.jpeg"},
        )
