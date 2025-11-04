# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2025
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import logging
import os
import string
import typing

from herokutl.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from herokutl.sessions import MemorySession
from herokutl.utils import parse_phone
from herokutl.tl.types import Message, User

from .. import loader, main, utils
from .._internal import restart
from ..inline.types import InlineCall
from ..tl_cache import CustomTelegramClient
from ..version import __version__
from ..web import core

logger = logging.getLogger(__name__)


@loader.tds
class HerokuWebMod(loader.Module):
    """Web/Inline mode add account"""

    strings = {"name": "HerokuWeb"}


    @loader.command()
    async def weburl(self, message: Message, force: bool = False):

        if "SHARKHOST" in os.environ or "HIKKAHOST" in os.environ or "JAMHOST" in os.environ:
            await utils.answer(message, self.strings["host_denied"])
        else:
        
            if "LAVHOST" in os.environ:
                form = await self.inline.form(
                    self.strings("lavhost_web"),
                    message=message,
                    reply_markup={
                       "text": self.strings("web_btn"),
                       "url": await main.heroku.web.get_url(proxy_pass=False),
                    },
                    photo="https://imgur.com/a/yOoHsa2.png",
                )
                return

            if (
                not force
                and not message.is_private
                and "force_insecure" not in message.raw_text.lower()
            ):
                try:
                    if not await self.inline.form(
                        self.strings("privacy_leak_nowarn").format(self._client.tg_id),
                        message=message,
                        reply_markup=[
                            {
                                "text": self.strings("btn_yes"),
                                "callback": self.weburl,
                                "args": (True,),
                            },
                            {"text": self.strings("btn_no"), "action": "close"},
                        ],
                        photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/web_interface.png",
                    ):
                        raise Exception
                except Exception:
                    await utils.answer(
                        message,
                        self.strings("privacy_leak").format(
                            self._client.tg_id,
                            utils.escape_html(self.get_prefix()),
                        ),
                    )

                return

            if not main.heroku.web:
                main.heroku.web = core.Web(
                    data_root=main.BASE_DIR,
                    api_token=main.heroku.api_token,
                    proxy=main.heroku.proxy,
                    connection=main.heroku.conn,
                )
                await main.heroku.web.add_loader(self._client, self.allmodules, self._db)
                await main.heroku.web.start_if_ready(
                    len(self.allclients),
                    main.heroku.arguments.port,
                    proxy_pass=main.heroku.arguments.proxy_pass,
                )

            if force:
                form = message
                await form.edit(
                    self.strings("opening_tunnel"),
                    reply_markup={"text": "🕔 Wait...", "data": "empty"},
                    photo=(
                        "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/opening_tunnel.png"
                    ),
                )
            else:
                form = await self.inline.form(
                    self.strings("opening_tunnel"),
                    message=message,
                    reply_markup={"text": "🕔 Wait...", "data": "empty"},
                    photo=(
                        "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/opening_tunnel.png"
                    ),
                )

            url = await main.heroku.web.get_url(proxy_pass=True)

            await form.edit(
                self.strings("tunnel_opened"),
                reply_markup={"text": self.strings("web_btn"), "url": url},
                photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/tunnel_opened.png",
            )

    @loader.command()
    async def addacc(self, message: Message):

        if "JAMHOST" in os.environ or "HIKKAHOST" in os.environ or "LAVHOST" in os.environ or "SHARKHOST" in os.environ:
            await utils.answer(message, self.strings["host_denied"])
        else:

            id = utils.get_args(message)
            if not id:
                reply = await message.get_reply_message()
                id = reply.sender_id if reply else None
            else:
                id = id[0]
        
            user = None
            if id:
                try:
                    id = int(id)
                except ValueError:
                    pass

                try:
                    user = await self._client.get_entity(id)
                except Exception as e:
                    logger.error(f"Error while fetching user: {e}")

            if not user or not isinstance(user, User) or user.bot:
                await utils.answer(
                    message,
                    self.strings("invalid_target")
                )
                return
        
            if user.id == self._client.tg_id:
                await utils.answer(
                    message,
                    self.strings("cant_add_self")
                )
                return
        
            if "force_insecure" in message.text.lower():
                await self._inline_login(message, user)
        
            try:
                if not await self.inline.form(
                        self.strings("add_user_confirm").format(
                            utils.escape_html(user.first_name),
                            user.id,
                        ),
                        message=message,
                        reply_markup=[
                            {
                                "text": self.strings("btn_yes"),
                                "callback": self._inline_login,
                                "args": (user,),
                            },
                            {"text": self.strings("btn_no"), "action": "close"},
                        ],
                        photo="",
                    ):
                    raise Exception
            except Exception:
                await utils.answer(
                    message,
                    self.strings("add_user_insecure").format(
                        utils.escape_html(user.first_name),
                        user.id,
                        utils.escape_html(self.get_prefix()),
                        user.id,
                    )
                )
            return
        
    async def _inline_login(self, call: typing.Union[Message, InlineCall], user: User, after_fail: bool = False):
        reply_markup = [
            {"text": self.strings("enter_number"), "input": self.strings("your_phone_number"), "handler": self.inline_phone_handler, "args": (user,)}
        ]

        fail = self.strings("incorrect_number") if after_fail else ""

        await utils.answer(
            call,
            fail + self.strings("enter_number_format"),
            reply_markup=reply_markup,
            always_allow=[user.id]
        )


    def _get_client(self) -> CustomTelegramClient:
        return CustomTelegramClient(
            MemorySession(),
            main.heroku.api_token.ID,
            main.heroku.api_token.HASH,
            connection=main.heroku.conn,
            proxy=main.heroku.proxy,
            connection_retries=None,
            device_model=main.get_app_name(),
            system_version="Windows 10",
            app_version=".".join(map(str, __version__)) + " x64",
            lang_code="en",
            system_lang_code="en-US",
        )
    
    async def schedule_restart(self, call, client):
        await utils.answer(
            call,
            self.strings("login_successful")
        )
        # Yeah-yeah, ikr, but it's the only way to restart
        await asyncio.sleep(1)
        await main.heroku.save_client_session(client, delay_restart=False)
        restart()

    async def inline_phone_handler(self, call, data, user):
        if not (phone := parse_phone(data)):
            await self._inline_login(call, user, after_fail=True)
            return
        
        client = self._get_client()

        await client.connect()
        try:
            await client.send_code_request(phone)
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings("floodwait_error").format(e.seconds),
                reply_markup={"text": self.strings("btn_no"), "action": "close"},
            )
            return
        except PhoneNumberInvalidError:
            await self._inline_login(call, user, after_fail=True)
            return
        
        reply_markup = {"text": self.strings("enter_code"), "input": self.strings("login_code"), "handler": self.inline_code_handler, "args": (client, phone, user,)}
        
        await utils.answer(
            call,
            self.strings("code_sent"),
            reply_markup=reply_markup,
            always_allow=[user.id]
        )
        
    async def inline_code_handler(self, call, data, client, phone, user):
        _code_markup = {"text": self.strings("enter_code"), "input": self.strings("login_code"), "handler": self.inline_code_handler, "args": (client, phone, user,)}
        if not data or len(data) != 5:
            await utils.answer(
                call,
                self.strings("invalid_code"),
                reply_markup=_code_markup,
                always_allow=[user.id]
            )
            return
        
        if any(c not in string.digits for c in data):
            await utils.answer(
                call,
                "Код должен состоять только из цифр. Повторите попытку.",
                reply_markup=_code_markup,
                always_allow=[user.id]
            )
            return
        
        try:
            await client.sign_in(phone, code=data)
        except SessionPasswordNeededError:
            reply_markup = [
                {"text": self.strings("enter_2fa"), "input": self.strings("your_2fa"), "handler": self.inline_2fa_handler, "args": (client, phone, user,)},
            ]
            await utils.answer(
                call,
                self.strings("2fa_enabled"),
                reply_markup=reply_markup,
                always_allow=[user.id]
            )
            return 
        except PhoneCodeExpiredError:
            reply_markup = [
                {"text": self.strings("request_code"), "callback": self.inline_phone_handler, "args": (phone, user)}
            ]
            await utils.answer(
                call,
                self.strings("code_expired"),
                reply_markup=reply_markup,
                always_allow=[user.id],
            )
            return 
        except PhoneCodeInvalidError:
            await utils.answer(
                call,
                self.strings("invalid_code"),
                reply_markup=_code_markup,
                always_allow=[user.id]
            )
            return 
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings("floodwait_error").format(e.seconds),
                reply_markup={"text": self.strings("btn_no"), "action": "close"},
            )
            return
        
        asyncio.ensure_future(self.schedule_restart(call, client))


    async def inline_2fa_handler(self, call, data, client, phone, user):
        _2fa_markup = {"text": self.strings("enter_2fa"), "input": self.strings("your_2fa"), "handler": self.inline_2fa_handler, "args": (client, phone, user,)}
        if not data:
            await utils.answer(
                call,
                self.strings("invalid_password"),
                reply_markup=_2fa_markup,
                always_allow=[user.id]
            )
            return
        
        try:
            await client.sign_in(phone, password=data)
        except PasswordHashInvalidError:
            await utils.answer(
                call,
                self.strings("invalid_password"),
                reply_markup=_2fa_markup,
                always_allow=[user.id]
            )
            return 
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings("floodwait_error").format(e.seconds),
                reply_markup={"text": self.strings("btn_no"), "action": "close"},
            )
            return
        
        asyncio.ensure_future(self.schedule_restart(call, client))