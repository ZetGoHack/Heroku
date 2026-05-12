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


import ast
import asyncio
import collections
import contextlib
import copy
import importlib
import importlib.machinery
import importlib.util
import inspect
import logging
import os
import re
import sys
import time
import typing
from dataclasses import dataclass, field
from importlib.abc import SourceLoader

import requests
from herokutl.hints import EntityLike
from herokutl.tl.functions.account import UpdateNotifySettingsRequest
from herokutl.tl.types import (
    Channel,
    ChannelForbidden,
    ChannelFull,
    InputPeerNotifySettings,
    Message,
    UserFull,
)

from . import version
from ._reference_finder import replace_all_refs
from .inline.types import (
    BotInlineCall,
    BotInlineMessage,
    BotMessage,
    HerokuReplyMarkup,
    InlineCall,
    InlineMessage,
    InlineQuery,
    InlineUnit,
)
from .pointers import PointerDict, PointerList

if typing.TYPE_CHECKING:
    from .loader import Modules

__all__ = [
    "JSONSerializable",
    "HerokuReplyMarkup",
    "ListLike",
    "Command",
    "StringLoader",
    "Module",
    "get_commands",
    "get_inline_handlers",
    "get_callback_handlers",
    "BotInlineCall",
    "BotMessage",
    "InlineCall",
    "InlineMessage",
    "InlineQuery",
    "InlineUnit",
    "BotInlineMessage",
    "PointerDict",
    "PointerList",
    "SafeClientProxy",
    "SafeDatabaseProxy",
    "SafeInlineProxy",
    "SafeAllModulesProxy",
]

logger = logging.getLogger(__name__)


def _is_external_origin(origin: str) -> bool:
    if not origin:
        return False
    return not origin.startswith("<core")


def _make_safe_client_proxy():
    import random
    import weakref
    from . import utils

    _client_map = weakref.WeakKeyDictionary()
    _origin_map = weakref.WeakKeyDictionary()
    _module_map = weakref.WeakKeyDictionary()
    _inline_map = weakref.WeakKeyDictionary()
    _user_id_map = weakref.WeakKeyDictionary()

    _PROTECTED_REQUESTS = {
        "GetStarGiftsRequest",
        "GetSavedStarGiftRequest",
        "GetResaleStarGiftsRequest",
        "GetUniqueStarGiftRequest",
        "GetUniqueStarGiftValueInfoRequest",
        "GetStarGiftUpgradePreviewRequest",
        "GetStarGiftWithdrawalUrlRequest",
        "UpgradeStarGiftRequest",
        "TransferStarGiftRequest",
        "CreateStarGiftCollectionRequest",
        "SendStarsFormRequest",
        "GetStarsGiftOptionsRequest",
        "GetStarsTransactionsRequest",
        "RefundStarsChargeRequest",
    }

    _PAID_REQUESTS = {
        "SendMessageRequest",
        "SendMediaRequest",
        "ForwardMessagesRequest",
        "SearchPostsRequest",
    }

    class SafeClientProxy:
        __slots__ = ("__weakref__",)

        _BLOCKED_ATTRS = {
            "session",
            "_sender",
            "_connection",
            "_transport",
            "_auth_key",
            "_log",
            "_mtproto",
            "_updates_handle",
            "_keepalive_handle",
        }

        _BLOCKED_MAGIC = {
            "__class__",
            "__dict__",
            "__getattribute__",
            "__setattr__",
            "__weakref__",
            "__reduce__",
            "__reduce_ex__",
            "__getstate__",
            "__setstate__",
        }

        def __init__(self, client, origin: str):
            _client_map[self] = client
            _origin_map[self] = origin

        def __getattribute__(self, name: str):
            if name in SafeClientProxy._BLOCKED_MAGIC:
                raise AttributeError("Access denied")
            if name in type(self).__dict__:
                return object.__getattribute__(self, name)
            if name in SafeClientProxy._BLOCKED_ATTRS:
                logger.warning(
                    "Blocked access to client.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Access to client attribute is blocked")
            return getattr(_client_map[self], name)

        def __setattr__(self, name: str, value):
            if (
                name in SafeClientProxy._BLOCKED_MAGIC
                or name in SafeClientProxy._BLOCKED_ATTRS
            ):
                logger.warning(
                    "Blocked write to client.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Write to client attribute is blocked")
            setattr(_client_map[self], name, value)

        def _set_module_info(self, module_object, inline_object, user_id: int):
            _module_map[self] = module_object
            _inline_map[self] = inline_object
            _user_id_map[self] = user_id

        def _send_permission_request(self, request_name: str, module, star_count=None):
            async def _async_send():
                user_id = _user_id_map.get(self)
                if not user_id:
                    return

                star_text = f" with {star_count} stars" if star_count else ""
                message_text = f"<b>{module.__class__.__name__}</b> wants to use <code>{request_name}</code>{star_text}, allow?"

                yes_callback_id = utils.rand(24)
                no_callback_id = utils.rand(24)

                buttons = [
                    [
                        {
                            "text": "✅",
                            "callback": yes_callback_id,
                        },
                        {
                            "text": "❌",
                            "callback": no_callback_id,
                        },
                    ]
                ]

                if random.choice([True, False]):
                    buttons[0].reverse()

                try:
                    await _client_map[self].send_message(
                        user_id,
                        message_text,
                        buttons=buttons,
                    )
                except Exception as e:
                    logger.debug("Failed to send permission request: %s", e)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_async_send())
                else:
                    loop.run_until_complete(_async_send())
            except Exception:
                logger.debug("Failed to schedule permission request")

        def __call__(self, *args, **kwargs):
            client = _client_map[self]

            if args and hasattr(args[0], "__class__"):
                request_name = args[0].__class__.__name__
                module = _module_map.get(self)

                if request_name in _PROTECTED_REQUESTS and module:
                    star_count = getattr(args[0], "stars", None)
                    self._send_permission_request(request_name, module, star_count)

                elif request_name in _PAID_REQUESTS and module:
                    allow_paid = getattr(module, "allow_paid_stars", None)
                    if allow_paid is False:
                        raise PermissionError(
                            f"Module {module.__class__.__name__} denies paid requests like {request_name}"
                        )

                    if allow_paid is None:
                        self._send_permission_request(request_name, module)

            return client(*args, **kwargs)

        def __repr__(self) -> str:
            return "<SafeClientProxy>"

    return SafeClientProxy


SafeClientProxy = _make_safe_client_proxy()


def _make_safe_db_proxy():
    import weakref

    _db_map = weakref.WeakKeyDictionary()
    _origin_map = weakref.WeakKeyDictionary()

    class SafeDatabaseProxy:
        __slots__ = ("__weakref__",)

        _BLOCKED_ATTRS = {
            "_client",
            "_redis",
            "_content_channel_id",
            "_assets_topic",
            "_me",
            "_db_file",
            "_saving_task",
            "_revisions",
            "_next_revision_call",
            "redis_init",
            "remote_force_save",
            "_redis_save",
            "_redis_save_sync",
        }

        _BLOCKED_MAGIC = {
            "__class__",
            "__dict__",
            "__getattribute__",
            "__setattr__",
            "__weakref__",
            "__reduce__",
            "__reduce_ex__",
            "__getstate__",
            "__setstate__",
        }

        def __init__(self, db, origin: str):
            _db_map[self] = db
            _origin_map[self] = origin

        def __getattribute__(self, name: str):
            if name in SafeDatabaseProxy._BLOCKED_MAGIC:
                raise AttributeError("Access denied")
            if name in SafeDatabaseProxy._BLOCKED_ATTRS:
                logger.warning(
                    "Blocked access to db.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Access to db attribute is blocked")
            return getattr(_db_map[self], name)

        def __setattr__(self, name: str, value):
            if (
                name in SafeDatabaseProxy._BLOCKED_MAGIC
                or name in SafeDatabaseProxy._BLOCKED_ATTRS
            ):
                logger.warning(
                    "Blocked write to db.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Write to db attribute is blocked")
            setattr(_db_map[self], name, value)

        def __getitem__(self, key):
            return _db_map[self][key]

        def __setitem__(self, key, value):
            _db_map[self][key] = value

        def __delitem__(self, key):
            del _db_map[self][key]

        def __contains__(self, key):
            return key in _db_map[self]

        def __repr__(self) -> str:
            return "<SafeDatabaseProxy>"

    return SafeDatabaseProxy


SafeDatabaseProxy = _make_safe_db_proxy()


def _make_safe_inline_proxy():
    import weakref

    _inline_map = weakref.WeakKeyDictionary()
    _origin_map = weakref.WeakKeyDictionary()

    class SafeInlineProxy:
        __slots__ = ("__weakref__",)

        _BLOCKED_ATTRS = {
            "_client",
            "_db",
            "_allmodules",
            "_token",
            "_bot",
            "_dp",
        }

        _BLOCKED_MAGIC = {
            "__class__",
            "__dict__",
            "__getattribute__",
            "__setattr__",
            "__weakref__",
            "__reduce__",
            "__reduce_ex__",
            "__getstate__",
            "__setstate__",
        }

        def __init__(self, inline, origin: str):
            _inline_map[self] = inline
            _origin_map[self] = origin

        def __getattribute__(self, name: str):
            if name in SafeInlineProxy._BLOCKED_MAGIC:
                raise AttributeError("Access denied")
            if name in SafeInlineProxy._BLOCKED_ATTRS:
                logger.warning(
                    "Blocked access to inline.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Access to inline attribute is blocked")
            return getattr(_inline_map[self], name)

        def __setattr__(self, name: str, value):
            if (
                name in SafeInlineProxy._BLOCKED_MAGIC
                or name in SafeInlineProxy._BLOCKED_ATTRS
            ):
                logger.warning(
                    "Blocked write to inline.%s from %s",
                    name,
                    _origin_map.get(self, "<unknown>"),
                )
                raise AttributeError("Write to inline attribute is blocked")
            setattr(_inline_map[self], name, value)

        def __repr__(self) -> str:
            return "<SafeInlineProxy>"

    return SafeInlineProxy


SafeInlineProxy = _make_safe_inline_proxy()


def _make_safe_allmodules_proxy():
    import weakref

    _allmodules_map = weakref.WeakKeyDictionary()
    _safe_client_map = weakref.WeakKeyDictionary()
    _safe_allclients_map = weakref.WeakKeyDictionary()
    _safe_db_map = weakref.WeakKeyDictionary()
    _safe_inline_map = weakref.WeakKeyDictionary()

    class SafeAllModulesProxy:
        __slots__ = ("__weakref__",)

        _BLOCKED_ATTRS = {
            "modules",
            "watchers",
            "inline",
            "client",
            "allclients",
            "db",
            "_db",
            "_client",
        }

        _BLOCKED_MAGIC = {
            "__class__",
            "__dict__",
            "__getattribute__",
            "__setattr__",
            "__weakref__",
            "__reduce__",
            "__reduce_ex__",
            "__getstate__",
            "__setstate__",
        }

        def __init__(
            self, allmodules, safe_client, safe_allclients, safe_db, safe_inline
        ):
            _allmodules_map[self] = allmodules
            _safe_client_map[self] = safe_client
            _safe_allclients_map[self] = safe_allclients
            _safe_db_map[self] = safe_db
            _safe_inline_map[self] = safe_inline

        @property
        def client(self):
            return _safe_client_map[self]

        @property
        def allclients(self):
            return _safe_allclients_map[self]

        @property
        def db(self):
            return _safe_db_map[self]

        @property
        def _db(self):
            return _safe_db_map[self]

        @property
        def inline(self):
            return _safe_inline_map[self]

        def __getattribute__(self, name: str):
            if name in SafeAllModulesProxy._BLOCKED_MAGIC:
                raise AttributeError("Access denied")
            return object.__getattribute__(self, name)

        def __getattr__(self, name: str):
            if name in SafeAllModulesProxy._BLOCKED_ATTRS:
                raise AttributeError("Access to allmodules attribute is blocked")
            return getattr(_allmodules_map[self], name)

        def __setattr__(self, name: str, value):
            if (
                name in SafeAllModulesProxy._BLOCKED_MAGIC
                or name in SafeAllModulesProxy._BLOCKED_ATTRS
            ):
                raise AttributeError("Write to allmodules attribute is blocked")
            setattr(_allmodules_map[self], name, value)

        def __delattr__(self, name: str):
            if (
                name in SafeAllModulesProxy._BLOCKED_MAGIC
                or name in SafeAllModulesProxy._BLOCKED_ATTRS
            ):
                raise AttributeError("Delete of allmodules attribute is blocked")
            delattr(_allmodules_map[self], name)

        def __repr__(self) -> str:
            return "<SafeAllModulesProxy>"

        def _get_real_allmodules(self):
            for frame_info in inspect.stack():
                mod = frame_info.frame.f_globals.get("__name__", None)
                if not mod or mod == __name__:
                    continue
                spec = frame_info.frame.f_globals.get("__spec__", None)
                origin = getattr(spec, "origin", None) if spec else None
                if not origin:
                    origin = frame_info.frame.f_globals.get("__file__", "")
                if origin and _is_external_origin(origin):
                    raise AttributeError("Access denied")
                break
            return _allmodules_map[self]

    return SafeAllModulesProxy


SafeAllModulesProxy = _make_safe_allmodules_proxy()


JSONSerializable = typing.Union[str, int, float, bool, list, dict, None]
ListLike = typing.Union[list, set, tuple]
Command = typing.Callable[..., typing.Awaitable[typing.Any]]


class StringLoader(SourceLoader):
    """Load a python module/file from a string"""

    def __init__(self, data: str, origin: str):
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.origin = origin

    def get_source(self, _=None) -> str:
        return self.data.decode("utf-8")

    def get_code(self, fullname: str) -> bytes:
        return (
            compile(source, self.origin, "exec", dont_inherit=True)
            if (source := self.get_data(fullname))
            else None
        )

    def get_filename(self, *args, **kwargs) -> str:
        return self.origin

    def get_data(self, *args, **kwargs) -> bytes:
        return self.data


class Module:
    strings = {"name": "Unknown"}

    """There is no help for this module"""

    def config_complete(self):
        """Called when module.config is populated"""

    async def client_ready(self):
        """Called after client is ready (after config_loaded)"""

    def internal_init(self):
        """Called after the class is initialized in order to pass the client and db. Do not call it yourself"""
        self.allmodules: "Modules"

        origin = getattr(self, "__origin__", "")
        is_external = _is_external_origin(origin)
        if getattr(self, "__force_internal__", False):
            is_external = False

        self.db = self.allmodules.db
        self._db = self.allmodules.db
        self.is_external = is_external

        if is_external:
            safe_client = SafeClientProxy(self.allmodules.client, origin)
            safe_allclients = [
                SafeClientProxy(c, origin) for c in self.allmodules.allclients
            ]
            safe_db = SafeDatabaseProxy(self.allmodules.db, origin)
            safe_inline = SafeInlineProxy(self.allmodules.inline, origin)

            try:
                user_id = self.allmodules.client.tg_id
                safe_client._set_module_info(self, self.allmodules.inline, user_id)
                for client in safe_allclients:
                    client._set_module_info(self, self.allmodules.inline, user_id)
            except Exception as e:
                logger.debug("Failed to set module info for request checking: %s", e)

            self.allmodules = SafeAllModulesProxy(
                self.allmodules,
                safe_client,
                safe_allclients,
                safe_db,
                safe_inline,
            )
            self.client = safe_client
            self._client = safe_client
            self.allclients = safe_allclients
            self.db = safe_db
            self._db = safe_db
        else:
            self.client = self.allmodules.client
            self._client = self.allmodules.client
            self.allclients = self.allmodules.allclients

        self.lookup = self.allmodules.lookup
        self.get_prefix = self.allmodules.get_prefix
        self.get_prefixes = self.allmodules.get_prefixes
        self.inline = self.allmodules.inline
        self.tg_id: int = self._client.tg_id
        self._tg_id: int = self._client.tg_id

    async def on_unload(self):
        """Called after unloading / reloading module"""

    async def on_dlmod(self):
        """
        Called after the module is first time loaded with .dlmod or .loadmod

        Possible use-cases:
        - Send reaction to author's channel message
        - Create asset folder
        - ...

        ⚠️ Note, that any error there will not interrupt module load, and will just
        send a message to logs with verbosity INFO and exception traceback
        """

    async def invoke(
        self,
        command: str,
        args: typing.Optional[str] = None,
        peer: typing.Optional[EntityLike] = None,
        message: typing.Optional[Message] = None,
        edit: bool = False,
    ) -> Message:
        """
        Invoke another command
        :param command: Command to invoke
        :param args: Arguments to pass to command
        :param peer: Peer to send the command to. If not specified, will send to the current chat
        :param edit: Whether to edit the message
        :returns Message:
        """
        if command not in self.allmodules.commands:
            raise ValueError(f"Command {command} not found")

        if not message and not peer:
            raise ValueError("Either peer or message must be specified")

        cmd = f"{self.get_prefix()}{command} {args or ''}".strip()

        message = (
            (await self._client.send_message(peer, cmd))
            if peer
            else (await (message.edit if edit else message.respond)(cmd))
        )
        await self.allmodules.commands[command](message)
        return message

    @property
    def commands(self) -> typing.Dict[str, Command]:
        """List of commands that module supports"""
        return get_commands(self)

    @property
    def heroku_commands(self) -> typing.Dict[str, Command]:
        """List of commands that module supports"""
        return get_commands(self)

    @property
    def inline_handlers(self) -> typing.Dict[str, Command]:
        """List of inline handlers that module supports"""
        return get_inline_handlers(self)

    @property
    def heroku_inline_handlers(self) -> typing.Dict[str, Command]:
        """List of inline handlers that module supports"""
        return get_inline_handlers(self)

    @property
    def callback_handlers(self) -> typing.Dict[str, Command]:
        """List of callback handlers that module supports"""
        return get_callback_handlers(self)

    @property
    def heroku_callback_handlers(self) -> typing.Dict[str, Command]:
        """List of callback handlers that module supports"""
        return get_callback_handlers(self)

    @property
    def watchers(self) -> typing.Dict[str, Command]:
        """List of watchers that module supports"""
        return get_watchers(self)

    @property
    def heroku_watchers(self) -> typing.Dict[str, Command]:
        """List of watchers that module supports"""
        return get_watchers(self)

    @commands.setter
    def commands(self, _):
        pass

    @heroku_commands.setter
    def heroku_commands(self, _):
        pass

    @inline_handlers.setter
    def inline_handlers(self, _):
        pass

    @heroku_inline_handlers.setter
    def heroku_inline_handlers(self, _):
        pass

    @callback_handlers.setter
    def callback_handlers(self, _):
        pass

    @heroku_callback_handlers.setter
    def heroku_callback_handlers(self, _):
        pass

    @watchers.setter
    def watchers(self, _):
        pass

    @heroku_watchers.setter
    def heroku_watchers(self, _):
        pass

    async def animate(
        self,
        message: typing.Union[Message, InlineMessage],
        frames: typing.List[str],
        interval: typing.Union[float, int],
        *,
        inline: bool = False,
    ) -> None:
        """
        Animate message
        :param message: Message to animate
        :param frames: A List of strings which are the frames of animation
        :param interval: Animation delay
        :param inline: Whether to use inline bot for animation
        :returns message:

        Please, note that if you set `inline=True`, first frame will be shown with an empty
        button due to the limitations of Telegram API
        """
        from . import utils

        with contextlib.suppress(AttributeError):
            _heroku_client_id_logging_tag = copy.copy(self.client.tg_id)  # noqa: F841

        if interval < 0.1:
            logger.warning(
                "Resetting animation interval to 0.1s, because it may get you in"
                " floodwaits"
            )
            interval = 0.1

        for frame in frames:
            match message:
                case Message() if inline:
                    message = await self.inline.form(
                        message=message,
                        text=frame,
                        reply_markup={"text": "\u0020\u2800", "data": "empty"},
                    )
                case Message():
                    message = await utils.answer(message, frame)
                case InlineMessage() if inline:
                    await message.edit(frame)

            await asyncio.sleep(interval)

        return message

    def get(
        self,
        key: str,
        default: typing.Optional[JSONSerializable] = None,
    ) -> JSONSerializable:
        return self._db.get(self.__class__.__name__, key, default)

    def set(self, key: str, value: JSONSerializable) -> bool:
        self._db.set(self.__class__.__name__, key, value)

    def pointer(
        self,
        key: str,
        default: typing.Optional[JSONSerializable] = None,
        item_type: typing.Optional[typing.Any] = None,
    ) -> typing.Union[JSONSerializable, PointerList, PointerDict]:
        return self._db.pointer(self.__class__.__name__, key, default, item_type)

    async def _decline(
        self,
        call: InlineCall,
        channel: EntityLike,
        event: asyncio.Event,
    ):
        from . import utils

        self._db.set(
            "heroku.main",
            "declined_joins",
            list(set(self._db.get("heroku.main", "declined_joins", []) + [channel.id])),
        )
        event.status = False
        event.set()
        await call.edit(
            (
                "✖️ <b>Declined joining <a"
                f' href="https://t.me/{channel.username}">{utils.escape_html(channel.title)}</a></b>'
            ),
            photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/declined_jr.png",
        )

    async def request_join(
        self,
        peer: EntityLike,
        reason: str,
        assure_joined: typing.Optional[bool] = False,
    ) -> bool:
        """
        Request to join a channel.
        :param peer: The channel to join.
        :param reason: The reason for joining.
        :param assure_joined: If set, module will not be loaded unless the required channel is joined.
                              ⚠️ Works only in `client_ready`!
                              ⚠️ If user declines to join channel, he will not be asked to
                              join again, so unless he joins it manually, module will not be loaded
                              ever.
        :return: Status of the request.
        :rtype: bool
        :notice: This method will block module loading until the request is approved or declined.
        """
        from . import utils

        channel = await self.client.get_entity(peer)

        match channel:
            case ChannelForbidden():
                if assure_joined:
                    raise LoadError(
                        f"You need to join {channel.title} (@{peer}) in order to use this module, "
                        "but you have been banned there"
                    )
                return False

            case _ if channel.id in self._db.get("heroku.main", "declined_joins", []):
                if assure_joined:
                    raise LoadError(
                        f"You need to join @{channel.username} in order to use this module"
                    )
                return False

            case Channel():
                pass

            case _:
                raise TypeError("`peer` field must be a channel")

        if getattr(channel, "left", True):
            channel = await self.client.force_get_entity(peer)

        if not getattr(channel, "left", True):
            return True

        event = asyncio.Event()
        await self.client(
            UpdateNotifySettingsRequest(
                peer=self.inline.bot_username,
                settings=InputPeerNotifySettings(show_previews=False, silent=False),
            )
        )

        await self.inline.bot.send_photo(
            self.tg_id,
            "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/join_request.png",
            caption=(
                self._client.loader.lookup("translations")
                .strings("requested_join")
                .format(
                    self.__class__.__name__,
                    channel.username,
                    utils.escape_html(channel.title),
                    utils.escape_html(reason),
                )
            ),
            reply_markup=self.inline.generate_markup(
                [
                    {
                        "text": "💫 Approve",
                        "callback": self.lookup("loader").approve_internal,
                        "args": (channel, event),
                    },
                    {
                        "text": "✖️ Decline",
                        "callback": self._decline,
                        "args": (channel, event),
                    },
                ]
            ),
        )

        self.heroku_wait_channel_approve = (
            self.__class__.__name__,
            channel,
            reason,
        )
        event.status = False
        await event.wait()

        with contextlib.suppress(AttributeError):
            delattr(self, "heroku_wait_channel_approve")

        if assure_joined and not event.status:
            raise LoadError(
                f"You need to join @{channel.username} in order to use this module"
            )

        return event.status

    async def import_lib(
        self,
        url: str,
        *,
        suspend_on_error: typing.Optional[bool] = False,
        _did_requirements: bool = False,
    ) -> "Library":
        """
        Import library from url and register it in :obj:`Modules`
        :param url: Url to import
        :param suspend_on_error: Will raise :obj:`loader.SelfSuspend` if library can't be loaded
        :return: :obj:`Library`
        :raise: SelfUnload if :attr:`suspend_on_error` is True and error occurred
        :raise: HTTPError if library is not found
        :raise: ImportError if library doesn't have any class which is a subclass of :obj:`loader.Library`
        :raise: ImportError if library name doesn't end with `Lib`
        :raise: RuntimeError if library throws in :method:`init`
        :raise: RuntimeError if library classname exists in :obj:`Modules`.libraries
        """

        from . import utils  # Avoiding circular import
        from .loader import USER_INSTALL, VALID_PIP_PACKAGES
        from .translations import Strings

        def _raise(e: Exception):
            if suspend_on_error:
                raise SelfSuspend("Required library is not available or is corrupted.")

            raise e

        if not utils.check_url(url):
            _raise(ValueError("Invalid url for library"))

        code = await utils.run_sync(requests.get, url)
        code.raise_for_status()
        code = code.text

        if re.search(r"# ?scope: ?heroku_min", code):
            ver = tuple(
                map(
                    int,
                    re.search(r"# ?scope: ?heroku_min ((\d+\.){2}\d+)", code)[1].split(
                        "."
                    ),
                )
            )

            if version.__version__ < ver:
                _raise(
                    RuntimeError(
                        f"Library requires Heroku version {'{}.{}.{}'.format(*ver)}+"
                    )
                )

        module = f"heroku.libraries.{url.replace('%', '%%').replace('.', '%d')}"
        origin = f"<library {url}>"

        spec = importlib.machinery.ModuleSpec(
            module,
            StringLoader(code, origin),
            origin=origin,
        )
        try:
            instance = importlib.util.module_from_spec(spec)
            sys.modules[module] = instance
            spec.loader.exec_module(instance)
        except ImportError as e:
            logger.info(
                "Library loading failed, attemping dependency installation (%s)",
                e.name,
            )
            # Let's try to reinstall dependencies
            try:
                requirements = list(
                    filter(
                        lambda x: not x.startswith(("-", "_", ".")),
                        map(
                            str.strip,
                            VALID_PIP_PACKAGES.search(code)[1].split(),
                        ),
                    )
                )
            except TypeError:
                logger.warning(
                    "No valid pip packages specified in code, attemping"
                    " installation from error"
                )
                requirements = [e.name]

            logger.debug("Installing requirements: %s", requirements)

            if not requirements or _did_requirements:
                _raise(e)

            pip = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-q",
                "--disable-pip-version-check",
                "--no-warn-script-location",
                *["--user"] if USER_INSTALL else [],
                *requirements,
            )

            rc = await pip.wait()

            if rc != 0:
                _raise(e)

            importlib.invalidate_caches()

            kwargs = utils.get_kwargs()
            kwargs["_did_requirements"] = True

            return await self.import_lib(**kwargs)  # Try again

        lib_obj = next(
            (
                value()
                for value in vars(instance).values()
                if inspect.isclass(value) and issubclass(value, Library)
            ),
            None,
        )

        if not lib_obj:
            _raise(ImportError("Invalid library. No class found"))

        if not lib_obj.__class__.__name__.endswith("Lib"):
            _raise(
                ImportError(
                    "Invalid library. Classname {} does not end with 'Lib'".format(
                        lib_obj.__class__.__name__
                    )
                )
            )

        if (
            all(
                line.replace(" ", "") != "#scope:no_stats" for line in code.splitlines()
            )
            and self._db.get("heroku.main", "stats", True)
            and url is not None
            and utils.check_url(url)
        ):
            with contextlib.suppress(Exception):
                await self.lookup("loader")._send_stats(url)

        lib_obj.source_url = url.strip("/")
        lib_obj.allmodules = self.allmodules
        lib_obj.internal_init()

        for old_lib in self.allmodules.libraries:
            if old_lib.name == lib_obj.name and (
                not isinstance(getattr(old_lib, "version", None), tuple)
                and not isinstance(getattr(lib_obj, "version", None), tuple)
                or old_lib.version >= lib_obj.version
            ):
                logger.debug("Using existing instance of library %s", old_lib.name)
                return old_lib

        if hasattr(lib_obj, "init"):
            if not callable(lib_obj.init):
                _raise(ValueError("Library init() must be callable"))

            try:
                await lib_obj.init()
            except Exception:
                _raise(RuntimeError("Library init() failed"))

        if hasattr(lib_obj, "config"):
            if not isinstance(lib_obj.config, LibraryConfig):
                _raise(
                    RuntimeError("Library config must be a `LibraryConfig` instance")
                )

            libcfg = lib_obj.db.get(
                lib_obj.__class__.__name__,
                "__config__",
                {},
            )

            for conf in lib_obj.config:
                with contextlib.suppress(Exception):
                    lib_obj.config.set_no_raise(
                        conf,
                        (
                            libcfg[conf]
                            if conf in libcfg
                            else os.environ.get(f"{lib_obj.__class__.__name__}.{conf}")
                            or lib_obj.config.getdef(conf)
                        ),
                    )

        if hasattr(lib_obj, "strings"):
            lib_obj.strings = Strings(lib_obj, self.translator)

        lib_obj.translator = self.translator

        for old_lib in self.allmodules.libraries:
            if old_lib.name == lib_obj.name:
                if hasattr(old_lib, "on_lib_update") and callable(
                    old_lib.on_lib_update
                ):
                    await old_lib.on_lib_update(lib_obj)

                replace_all_refs(old_lib, lib_obj)
                logger.debug(
                    "Replacing existing instance of library %s with updated object",
                    lib_obj.name,
                )
                return lib_obj

        self.allmodules.libraries += [lib_obj]
        return lib_obj


class Library:
    """All external libraries must have a class-inheritant from this class"""

    def internal_init(self):
        self.name = self.__class__.__name__
        self.db = self.allmodules.db
        self._db = self.allmodules.db
        self.client = self.allmodules.client
        self._client = self.allmodules.client
        self.tg_id = self._client.tg_id
        self._tg_id = self._client.tg_id
        self.lookup = self.allmodules.lookup
        self.get_prefix = self.allmodules.get_prefix
        self.get_prefixes = self.allmodules.get_prefixes
        self.inline = self.allmodules.inline
        self.allclients = self.allmodules.allclients

    def _lib_get(
        self,
        key: str,
        default: typing.Optional[JSONSerializable] = None,
    ) -> JSONSerializable:
        return self._db.get(self.__class__.__name__, key, default)

    def _lib_set(self, key: str, value: JSONSerializable) -> bool:
        self._db.set(self.__class__.__name__, key, value)

    def _lib_pointer(
        self,
        key: str,
        default: typing.Optional[JSONSerializable] = None,
    ) -> typing.Union[JSONSerializable, PointerDict, PointerList]:
        return self._db.pointer(self.__class__.__name__, key, default)


class LoadError(Exception):
    """Tells user, why your module can't be loaded, if raised in `client_ready`"""

    def __init__(self, error_message: str):  # skipcq: PYL-W0231
        self._error = error_message

    def __str__(self) -> str:
        return self._error


class CoreOverwriteError(LoadError):
    """Is being raised when core module or command is overwritten"""

    def __init__(
        self,
        module: typing.Optional[str] = None,
        command: typing.Optional[str] = None,
    ):
        self.type = "module" if module else "command"
        self.target = module or command
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"{'Module' if self.type == 'module' else 'command'} {self.target} will not"
            " be overwritten, because it's core"
        )


class CoreUnloadError(Exception):
    """Is being raised when user tries to unload core module"""

    def __init__(self, module: str):
        self.module = module
        super().__init__()

    def __str__(self) -> str:
        return f"Module {self.module} will not be unloaded, because it's core"


class SelfUnload(Exception):
    """Silently unloads module, if raised in `client_ready`"""

    def __init__(self, error_message: str = ""):
        super().__init__()
        self._error = error_message

    def __str__(self) -> str:
        return self._error


class SelfSuspend(Exception):
    """
    Silently suspends module, if raised in `client_ready`
    Commands and watcher will not be registered if raised
    Module won't be unloaded from db and will be unfreezed after restart, unless
    the exception is raised again
    """

    def __init__(self, error_message: str = ""):
        super().__init__()
        self._error = error_message

    def __str__(self) -> str:
        return self._error


class StopLoop(Exception):
    """Stops the loop, in which is raised"""


class ModuleConfig(dict):
    """Stores config for modules and apparently libraries"""

    def __init__(self, *entries: typing.Union[str, "ConfigValue", "ConfigCategory"]):
        self._option_categories: dict[str, str] = dict()
        self._categories: dict[str, "ConfigCategory"] = dict()

        if all(isinstance(entry, (ConfigValue, ConfigCategory)) for entry in entries):
            # New config format processing
            self._config = {}
            for entry in entries:
                if isinstance(entry, ConfigCategory):
                    self._categories[entry.name] = entry
                    for cv in entry:
                        self._config[cv.option] = cv
                        self._option_categories[cv.option] = entry.name
                else:
                    self._config[entry.option] = entry
        else:
            # Legacy config processing
            keys = []
            values = []
            defaults = []
            docstrings = []
            for i, entry in enumerate(entries):
                if i % 3 == 0:
                    keys += [entry]
                elif i % 3 == 1:
                    values += [entry]
                    defaults += [entry]
                else:
                    docstrings += [entry]

            self._config = {
                key: ConfigValue(option=key, default=default, doc=doc)
                for key, default, doc in zip(keys, defaults, docstrings)
            }

        super().__init__(
            {option: config.value for option, config in self._config.items()}
        )

    def getdoc(self, key: str, message: typing.Optional[Message] = None) -> str:
        """Get the documentation by key"""
        ret = self._config[key].doc

        if callable(ret):
            try:
                # Compatibility tweak
                # does nothing in Heroku
                ret = ret(message)
            except Exception:
                ret = ret()

        return ret

    def getdef(self, key: str) -> str:
        """Get the default value by key"""
        return self._config[key].default

    def get_category(self, key: str) -> typing.Optional["ConfigCategory"]:
        cat_name = self._option_categories.get(key)
        return self._categories.get(cat_name) if cat_name else None

    def grouped_options(
        self,
    ) -> "collections.OrderedDict[str | None, list[str]]":
        result = (
            collections.OrderedDict()
        )
        for option in self._config:
            cat = self._option_categories.get(option)
            result.setdefault(cat, []).append(option)
        return result

    def __setitem__(self, key: str, value: typing.Any):
        self._config[key].value = value
        super().__setitem__(key, value)

    def set_no_raise(self, key: str, value: typing.Any):
        self._config[key].set_no_raise(value)
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> typing.Any:
        try:
            return self._config[key].value
        except KeyError:
            return None

    def reload(self):
        for key in self._config:
            super().__setitem__(key, self._config[key].value)

    def change_validator(
        self,
        key: str,
        validator: typing.Callable[[JSONSerializable], JSONSerializable],
    ):
        self._config[key].validator = validator


LibraryConfig = ModuleConfig


class _Placeholder:
    """Placeholder to determine if the default value is going to be set"""


async def wrap(func: typing.Callable[[], typing.Awaitable]) -> typing.Any:
    with contextlib.suppress(Exception):
        return await func()


def syncwrap(func: typing.Callable[[], typing.Any]) -> typing.Any:
    with contextlib.suppress(Exception):
        return func()


@dataclass(repr=True)
class ConfigValue:
    option: str
    default: typing.Any = None
    doc: typing.Union[typing.Callable[[], str], str] = "No description"
    value: typing.Any = field(default_factory=_Placeholder)
    validator: typing.Optional[
        typing.Callable[[JSONSerializable], JSONSerializable]
    ] = None
    on_change: typing.Optional[
        typing.Union[typing.Callable[[], typing.Awaitable], typing.Callable]
    ] = None
    folder: typing.Optional[str] = None

    def __post_init__(self):
        if isinstance(self.value, _Placeholder):
            self.value = self.default

    def set_no_raise(self, value: typing.Any) -> bool:
        """
        Sets the config value w/o ValidationError being raised
        Should not be used uninternally
        """
        return self.__setattr__("value", value, ignore_validation=True)

    def __setattr__(
        self,
        key: str,
        value: typing.Any,
        *,
        ignore_validation: bool = False,
    ):
        if key == "value":
            try:
                value = ast.literal_eval(value)
            except Exception:
                pass

            # Convert value to list if it's tuple just not to mess up
            # with json convertations
            if isinstance(value, (set, tuple)):
                value = list(value)

            if isinstance(value, list):
                value = [
                    item.strip() if isinstance(item, str) else item for item in value
                ]

            if self.validator is not None:
                if value is not None:
                    from . import validators

                    try:
                        value = self.validator.validate(value)
                    except validators.ValidationError as e:
                        if not ignore_validation:
                            raise e

                        logger.debug(
                            "Config value was broken (%s), so it was reset to %s",
                            value,
                            self.default,
                        )

                        value = self.default
                else:
                    match self.validator.internal_id:
                        case "String":
                            default_val = ""
                        case "Integer":
                            default_val = 0
                        case "Boolean":
                            default_val = False
                        case "Series":
                            default_val = []
                        case "Float":
                            default_val = 0.0
                        case _:
                            default_val = None

                    if default_val is not None:
                        logger.debug(
                            "Config value was None, so it was reset to %s",
                            default_val,
                        )
                        value = default_val

            # This attribute will tell the `Loader` to save this value in db
            self._save_marker = True

        object.__setattr__(self, key, value)

        if key == "value" and not ignore_validation and callable(self.on_change):
            if inspect.iscoroutinefunction(self.on_change):
                asyncio.ensure_future(wrap(self.on_change))
            else:
                syncwrap(self.on_change)


class ConfigCategory(list):
    def __init__(
        self,
        name: str,
        *config_values: ConfigValue,
        doc: typing.Callable[[], str] | str | "ConfigValue" = "No description",
    ):
        super().__init__(config_values)
        self.name = str(name)
        self.doc = doc

    def getdoc(self) -> str:
        if callable(self.doc):
            try:
                return self.doc()
            except Exception:
                return "No description"
        return self.doc

    @property
    def _config_values(self) -> tuple[ConfigValue, ...]:
        return tuple(self)


def _get_members(
    mod: Module,
    ending: str,
    attribute: typing.Optional[str] = None,
    strict: bool = False,
) -> dict:
    """Get method of module, which end with ending"""
    return {
        (
            method_name.rsplit(ending, maxsplit=1)[0]
            if (method_name == ending if strict else method_name.endswith(ending))
            else method_name
        ).lower(): getattr(mod, method_name)
        for method_name in dir(mod)
        if not isinstance(getattr(type(mod), method_name, None), property)
        and callable(getattr(mod, method_name))
        and (
            (method_name == ending if strict else method_name.endswith(ending))
            or attribute
            and getattr(getattr(mod, method_name), attribute, False)
        )
    }


class CacheRecordEntity:
    def __init__(
        self,
        hashable_entity: "Hashable",  # type: ignore  # noqa: F821
        resolved_entity: EntityLike,
        exp: int,
    ):
        self.entity = copy.deepcopy(resolved_entity)
        self._hashable_entity = copy.deepcopy(hashable_entity)
        self._exp = round(time.time() + exp)
        self.ts = time.time()

    @property
    def expired(self) -> bool:
        return self._exp < time.time()

    def __eq__(self, record: "CacheRecordEntity") -> bool:
        return hash(record) == hash(self)

    def __hash__(self) -> int:
        return hash(self._hashable_entity)

    def __str__(self) -> str:
        return f"CacheRecordEntity of {self.entity}"

    def __repr__(self) -> str:
        return (
            f"CacheRecordEntity(entity={type(self.entity).__name__}(...),"
            f" exp={self._exp})"
        )


class CacheRecordPerms:
    def __init__(
        self,
        hashable_entity: "Hashable",  # type: ignore  # noqa: F821
        hashable_user: "Hashable",  # type: ignore  # noqa: F821
        resolved_perms: EntityLike,
        exp: int,
    ):
        self.perms = copy.deepcopy(resolved_perms)
        self._hashable_entity = copy.deepcopy(hashable_entity)
        self._hashable_user = copy.deepcopy(hashable_user)
        self._exp = round(time.time() + exp)
        self.ts = time.time()

    @property
    def expired(self) -> bool:
        return self._exp < time.time()

    def __eq__(self, record: "CacheRecordPerms") -> bool:
        return hash(record) == hash(self)

    def __hash__(self) -> int:
        return hash((self._hashable_entity, self._hashable_user))

    def __str__(self) -> str:
        return f"CacheRecordPerms of {self.perms}"

    def __repr__(self) -> str:
        return (
            f"CacheRecordPerms(perms={type(self.perms).__name__}(...), exp={self._exp})"
        )


class CacheRecordFullChannel:
    def __init__(self, channel_id: int, full_channel: ChannelFull, exp: int):
        self.channel_id = channel_id
        self.full_channel = full_channel
        self._exp = round(time.time() + exp)
        self.ts = time.time()

    @property
    def expired(self) -> bool:
        return self._exp < time.time()

    def __eq__(self, record: "CacheRecordFullChannel") -> bool:
        return hash(record) == hash(self)

    def __hash__(self) -> int:
        return hash((self._hashable_entity, self._hashable_user))

    def __str__(self) -> str:
        return f"CacheRecordFullChannel of {self.channel_id}"

    def __repr__(self) -> str:
        return (
            f"CacheRecordFullChannel(channel_id={self.channel_id}(...),"
            f" exp={self._exp})"
        )


class CacheRecordFullUser:
    def __init__(self, user_id: int, full_user: UserFull, exp: int):
        self.user_id = user_id
        self.full_user = full_user
        self._exp = round(time.time() + exp)
        self.ts = time.time()

    @property
    def expired(self) -> bool:
        return self._exp < time.time()

    def __eq__(self, record: "CacheRecordFullUser") -> bool:
        return hash(record) == hash(self)

    def __hash__(self) -> int:
        return hash((self._hashable_entity, self._hashable_user))

    def __str__(self) -> str:
        return f"CacheRecordFullUser of {self.user_id}"

    def __repr__(self) -> str:
        return f"CacheRecordFullUser(channel_id={self.user_id}(...), exp={self._exp})"


def get_commands(mod: Module) -> dict:
    """Introspect the module to get its commands"""
    return _get_members(mod, "cmd", "is_command")


def get_inline_handlers(mod: Module) -> dict:
    """Introspect the module to get its inline handlers"""
    return _get_members(mod, "_inline_handler", "is_inline_handler")


def get_callback_handlers(mod: Module) -> dict:
    """Introspect the module to get its callback handlers"""
    return _get_members(mod, "_callback_handler", "is_callback_handler")


def get_watchers(mod: Module) -> dict:
    """Introspect the module to get its watchers"""
    return _get_members(
        mod,
        "watcher",
        "is_watcher",
        strict=True,
    )
