"""Inline buttons, galleries and other Telegram-Bot-API stuff"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import contextlib
import logging
import time
import typing

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from herokutl.errors.rpcerrorlist import InputUserDeactivatedError, YouBlockedUserError
from herokutl.tl.functions.contacts import UnblockRequest
from herokutl.tl.functions.messages import (
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest,
)
from herokutl.tl.types import DialogFilter, InputPeerUser, Message
from herokutl.utils import get_display_name

from .. import utils
from ..database import Database
from ..tl_cache import CustomTelegramClient
from ..translations import Translator
from .bot_pm import BotPM
from .events import Events
from .form import Form
from .gallery import Gallery
from .list import List
from .query_gallery import QueryGallery
from .token_obtainment import TokenObtainment
from .utils import Utils

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from ..loader import Modules



def _make_handler_wrapper(handler: typing.Callable, update_type: str) -> typing.Callable:
    async def wrapper(*args, **kwargs):
        update = args[0] if args else next(iter(kwargs.values()), None)
        return await handler(update)
    return wrapper



_BOT_UPDATE_TYPE_REGISTERS = {
    "message": lambda dp, handler: dp.message.register(handler, lambda *_: True),
    "edited_message": lambda dp, handler: dp.edited_message.register(handler, lambda *_: True),
    "channel_post": lambda dp, handler: dp.channel_post.register(handler, lambda *_: True),
    "edited_channel_post": lambda dp, handler: dp.edited_channel_post.register(handler, lambda *_: True),
    "inline_query": lambda dp, handler: dp.inline_query.register(handler, lambda _: True),
    "chosen_inline_result": lambda dp, handler: dp.chosen_inline_result.register(handler, lambda _: True),
    "callback_query": lambda dp, handler: dp.callback_query.register(handler, lambda _: True),
    "shipping_query": lambda dp, handler: dp.shipping_query.register(handler, lambda _: True),
    "pre_checkout_query": lambda dp, handler: dp.pre_checkout_query.register(handler, lambda _: True),
    "poll": lambda dp, handler: dp.poll.register(handler, lambda _: True),
    "poll_answer": lambda dp, handler: dp.poll_answer.register(handler, lambda _: True),
    "my_chat_member": lambda dp, handler: dp.my_chat_member.register(handler, lambda _: True),
    "chat_member": lambda dp, handler: dp.chat_member.register(handler, lambda _: True),
    "chat_join_request": lambda dp, handler: dp.chat_join_request.register(handler, lambda _: True),
    "message_reaction": lambda dp, handler: dp.message_reaction.register(handler, lambda _: True),
    "message_reaction_count": lambda dp, handler: dp.message_reaction_count.register(handler, lambda _: True),
    "chat_boost": lambda dp, handler: dp.chat_boost.register(handler, lambda _: True),
    "removed_chat_boost": lambda dp, handler: dp.removed_chat_boost.register(handler, lambda _: True),
}


class InlineManager(
    Utils,
    Events,
    TokenObtainment,
    Form,
    Gallery,
    QueryGallery,
    List,
    BotPM,
):
    """
    Inline buttons, galleries and other Telegram-Bot-API stuff
    :param client: Telegram client
    :param db: Database instance
    :param allmodules: All modules
    :type client: heroku.tl_cache.CustomTelegramClient
    :type db: heroku.database.Database
    :type allmodules: heroku.loader.Modules
    """

    def __init__(
        self,
        client: CustomTelegramClient,
        db: Database,
        allmodules: "Modules",  # type: ignore  # noqa: F821
    ):
        """Initialize InlineManager to create forms"""
        self._client = client
        self._db = db
        self._allmodules = allmodules
        self.translator: Translator = allmodules.translator

        self._units: typing.Dict[str, dict] = {}
        self._custom_map: typing.Dict[str, callable] = {}
        self.fsm: typing.Dict[str, str] = {}
        self._error_events: typing.Dict[str, asyncio.Event] = {}

        self._markup_ttl = 60 * 60 * 24
        self.init_complete = False

        self._token = db.get("heroku.inline", "bot_token", False)

        self._me: int = None
        self._name: str = None
        self._dp: Dispatcher = None
        self._task: asyncio.Future = None
        self._cleaner_task: asyncio.Future = None
        self.bot: Bot = None
        self.bot_id: int = None
        self.bot_username: str = None

        self._bot_update_handlers: typing.Dict[
            str, typing.Tuple[str, typing.Callable]
        ] = {}

    async def _cleaner(self):
        """Cleans outdated inline units"""
        while True:
            for unit_id, unit in self._units.copy().items():
                if (unit.get("ttl") or (time.time() + self._markup_ttl)) < time.time():
                    del self._units[unit_id]

            await asyncio.sleep(5)

    def _build_dp(self) -> Dispatcher:
        dp = Dispatcher()

        for handler_id, (update_type, handler) in self._bot_update_handlers.items():
            register_fn = _BOT_UPDATE_TYPE_REGISTERS.get(update_type)
            if register_fn:
                try:
                    register_fn(dp, handler)
                except Exception:
                    logger.exception(
                        "Failed to re-register bot update handler %s for update type %s",
                        handler_id,
                        update_type,
                    )

        dp.inline_query.register(
            self._inline_handler,
            lambda _: True,
        )

        dp.callback_query.register(
            self._callback_query_handler,
            lambda _: True,
        )

        dp.chosen_inline_result.register(
            self._chosen_inline_handler,
            lambda _: True,
        )

        dp.message.register(
            self._message_handler,
            lambda *_: True,
        )

        return dp

    async def register_manager(
        self,
        after_break: bool = False,
        ignore_token_checks: bool = False,
    ):
        """
        Register manager
        :param after_break: Loop marker
        :param ignore_token_checks: If `True`, will not check for token
        :type after_break: bool
        :type ignore_token_checks: bool
        :return: None
        :rtype: None
        """
        self._me = self._client.tg_id
        self._name = get_display_name(self._client.heroku_me)

        if not ignore_token_checks:
            is_token_asserted = await self._assert_token()
            if not is_token_asserted:
                self.init_complete = False
                return

        self.init_complete = True

        self.bot = Bot(
            token=self._token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self._bot = self.bot
        self._dp = self._build_dp()

        try:
            bot_me = await self.bot.get_me()
            self.bot_username = bot_me.username
            self.bot_id = bot_me.id
        except TelegramUnauthorizedError:
            logger.critical("Token expired, revoking...")
            return await self._dp_revoke_token(False)

        try:
            m = await self._client.send_message(self.bot_username, "/start heroku init")
        except (InputUserDeactivatedError, ValueError):
            self._db.set("heroku.inline", "bot_token", None)
            self._token = False

            if not after_break:
                return await self.register_manager(True)

            self.init_complete = False
            return False
        except YouBlockedUserError:
            await self._client(UnblockRequest(id=self.bot_username))
            try:
                m = await self._client.send_message(
                    self.bot_username, "/start heroku init"
                )
            except Exception:
                logger.critical("Can't unblock users bot", exc_info=True)
                return False
        except Exception:
            self.init_complete = False
            logger.critical("Initialization of inline manager failed!", exc_info=True)
            return False

        _folders = await self._client(GetDialogFiltersRequest())
        for folder in _folders.filters:
            if getattr(folder, "title", None) == "Heroku":
                if any(
                    [
                        isinstance(peer, InputPeerUser) and peer.user_id == self.bot_id
                        for peer in folder.include_peer
                    ]
                ):
                    break

                pinned = [await self._client.get_input_entity(self.bot_id)]
                include = folder.include_peers
                exclude = folder.exclude_peers
                emoticon = folder.emoticon
                color = folder.color

                await self._client(
                    UpdateDialogFilterRequest(
                        folder.id,
                        DialogFilter(
                            folder.id,
                            pinned_peers=pinned,
                            include_peers=include,
                            exclude_peers=exclude,
                            emoticon=emoticon,
                            color=color,
                        ),
                    )
                )
                break

        await self._client.delete_messages(self.bot_username, m)

        old = self.bot.get_updates
        revoke = self._dp_revoke_token

        async def new(*args, **kwargs):
            nonlocal revoke, old
            try:
                return await old(*args, **kwargs)
            except TelegramConflictError:
                await revoke()
            except TelegramUnauthorizedError:
                logger.critical("Got Unauthorized")
                await self._stop()

        self.bot.get_updates = new

        self._task = asyncio.ensure_future(
            self._dp.start_polling(self._bot, handle_signals=False)
        )
        self._cleaner_task = asyncio.ensure_future(self._cleaner())

    async def _stop(self):
        """Stop the bot"""
        self._task.cancel()
        await self._dp.stop_polling()
        self._cleaner_task.cancel()

    async def _restart_polling(self):
        """Rebuild dispatcher and restart polling with current handler set"""
        if self._task:
            self._task.cancel()
        with contextlib.suppress(Exception):
            await self._dp.stop_polling()

        self._dp = self._build_dp()

        old = self.bot.get_updates
        revoke = self._dp_revoke_token

        async def new(*args, **kwargs):
            nonlocal revoke, old
            try:
                return await old(*args, **kwargs)
            except TelegramConflictError:
                await revoke()
            except TelegramUnauthorizedError:
                logger.critical("Got Unauthorized")
                await self._stop()

        self.bot.get_updates = new

        self._task = asyncio.ensure_future(
            self._dp.start_polling(self._bot, handle_signals=False)
        )

    def register_bot_update_handler(
        self,
        handler_id: str,
        update_type: str,
        handler: typing.Callable,
    ):
        """
        Register a bot update handler from a module
        :param handler_id: Unique handler ID (use uuid4)
        :param update_type: One of the supported Telegram update types
        :param handler: Async callable to handle the update
        """
        if update_type not in _BOT_UPDATE_TYPE_REGISTERS:
            logger.warning(
                "Unsupported bot update type: %s (handler_id=%s)",
                update_type,
                handler_id,
            )
            return

        self._bot_update_handlers[handler_id] = (update_type, _make_handler_wrapper(handler, update_type))
        logger.debug(
            "Registered bot update handler %s for update type %s",
            handler_id,
            update_type,
        )

        if self.init_complete and self._dp:
            asyncio.ensure_future(self._restart_polling())

    def unregister_bot_update_handler(self, handler_id: str):
        """
        Unregister a bot update handler and rebuild dispatcher
        :param handler_id: Handler ID to remove
        """
        if handler_id not in self._bot_update_handlers:
            return

        del self._bot_update_handlers[handler_id]
        logger.debug("Unregistered bot update handler %s", handler_id)

        if self.init_complete and self._dp:
            asyncio.ensure_future(self._restart_polling())

    async def _invoke_unit(self, unit_id: str, message: Message) -> Message:
        event = asyncio.Event()
        self._error_events[unit_id] = event

        q: "InlineResults" = None  # type: ignore  # noqa: F821
        exception: Exception = None

        async def result_getter():
            nonlocal unit_id, q
            with contextlib.suppress(Exception):
                q = await self._client.inline_query(self.bot_username, unit_id)

        async def event_poller():
            nonlocal exception
            await asyncio.wait_for(event.wait(), timeout=10)
            if self._error_events.get(unit_id):
                exception = self._error_events[unit_id]

        result_getter_task = asyncio.ensure_future(result_getter())
        event_poller_task = asyncio.ensure_future(event_poller())

        _, pending = await asyncio.wait(
            [result_getter_task, event_poller_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        self._error_events.pop(unit_id, None)

        if exception:
            raise exception  # skipcq: PYL-E0702

        if not q:
            raise Exception("No query results")

        return await q[0].click(
            utils.get_chat_id(message) if isinstance(message, Message) else message,
            reply_to=(
                message.reply_to_msg_id if isinstance(message, Message) else None
            ),
        )
