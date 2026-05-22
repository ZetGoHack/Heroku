"""Inline buttons, galleries and other Telethon bot stuff"""

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

from herokutl import TelegramClient, events
from herokutl.errors.rpcerrorlist import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    AuthKeyUnregisteredError,
    InputUserDeactivatedError,
    YouBlockedUserError,
)
from herokutl.sessions import MemorySession
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
from .tl import TelethonBot, web_document
from .token_obtainment import TokenObtainment
from .utils import Utils

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from ..loader import Modules


def _make_handler_wrapper(
    handler: typing.Callable, update_type: str
) -> typing.Callable:
    async def wrapper(*args, **kwargs):
        update = args[0] if args else next(iter(kwargs.values()), None)
        return await handler(update)

    return wrapper


_BOT_UPDATE_EVENTS = {
    "message": events.NewMessage,
    "edited_message": events.MessageEdited,
    "channel_post": events.NewMessage,
    "edited_channel_post": events.MessageEdited,
    "inline_query": events.InlineQuery,
    "callback_query": events.CallbackQuery,
    "chosen_inline_result": events.Raw,
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
    Inline buttons, galleries and other Telethon bot stuff
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
        self._bot_client: TelegramClient = None
        self._task: asyncio.Future = None
        self._cleaner_task: asyncio.Future = None
        self.bot: TelethonBot = None
        self.bot_id: int = None
        self.bot_username: str = None

        self._bot_update_handlers: typing.Dict[
            str, typing.Tuple[str, typing.Callable]
        ] = {}
        self._bot_handler_refs: typing.Dict[
            str, typing.Tuple[typing.Callable, object]
        ] = {}

    async def _cleaner(self):
        """Cleans outdated inline units"""
        while True:
            for unit_id, unit in self._units.copy().items():
                if (unit.get("ttl") or (time.time() + self._markup_ttl)) < time.time():
                    del self._units[unit_id]

            await asyncio.sleep(5)

    @staticmethod
    def _web_document(url: typing.Optional[str], **kwargs):
        return web_document(url, **kwargs)

    def _register_bot_handler(
        self,
        handler: typing.Callable,
        event_builder,
        *,
        handler_id: typing.Optional[str] = None,
    ):
        self._bot_client.add_event_handler(handler, event_builder)
        if handler_id:
            self._bot_handler_refs[handler_id] = (handler, event_builder)

    def _register_builtin_handlers(self):
        self._register_bot_handler(self._inline_handler, events.InlineQuery())
        self._register_bot_handler(self._callback_query_handler, events.CallbackQuery())
        self._register_bot_handler(self._chosen_inline_handler, events.Raw())
        self._register_bot_handler(self._message_handler, events.NewMessage())

        for handler_id, (update_type, handler) in self._bot_update_handlers.items():
            self._attach_custom_handler(handler_id, update_type, handler)

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

        self._bot_client = TelegramClient(
            MemorySession(),
            self._client.api_id,
            self._client.api_hash,
            receive_updates=True,
        )

        try:
            await self._bot_client.start(bot_token=self._token)
            self.bot = TelethonBot(self._bot_client)
            self._bot = self.bot
            self._register_builtin_handlers()
            bot_me = await self._bot_client.get_me()
            self.bot_username = bot_me.username
            self.bot_id = bot_me.id
        except (
            AccessTokenExpiredError,
            AccessTokenInvalidError,
            AuthKeyUnregisteredError,
        ):
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

        self._cleaner_task = asyncio.ensure_future(self._cleaner())

    async def _stop(self):
        """Stop the bot"""
        if self._task:
            self._task.cancel()
        if self._bot_client:
            await self._bot_client.disconnect()
        if self._cleaner_task:
            self._cleaner_task.cancel()

    async def _restart_polling(self):
        """Kept for API compatibility; Telethon handlers are updated in-place."""
        return

    def _attach_custom_handler(
        self,
        handler_id: str,
        update_type: str,
        handler: typing.Callable,
    ):
        event_cls = _BOT_UPDATE_EVENTS.get(update_type)
        if not event_cls or not self._bot_client:
            return

        event_builder = event_cls()
        self._register_bot_handler(handler, event_builder, handler_id=handler_id)

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
        if update_type not in _BOT_UPDATE_EVENTS:
            logger.warning(
                "Unsupported bot update type: %s (handler_id=%s)",
                update_type,
                handler_id,
            )
            return

        self._bot_update_handlers[handler_id] = (
            update_type,
            _make_handler_wrapper(handler, update_type),
        )
        logger.debug(
            "Registered bot update handler %s for update type %s",
            handler_id,
            update_type,
        )

        if self.init_complete and self._bot_client:
            self._attach_custom_handler(handler_id, update_type, handler)

    def unregister_bot_update_handler(self, handler_id: str):
        """
        Unregister a bot update handler and rebuild dispatcher
        :param handler_id: Handler ID to remove
        """
        if handler_id not in self._bot_update_handlers:
            return

        del self._bot_update_handlers[handler_id]
        if handler_id in self._bot_handler_refs and self._bot_client:
            handler, event_builder = self._bot_handler_refs.pop(handler_id)
            self._bot_client.remove_event_handler(handler, event_builder)
        logger.debug("Unregistered bot update handler %s", handler_id)

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
