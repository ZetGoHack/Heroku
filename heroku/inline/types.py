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

import logging

from aiogram.types import CallbackQuery
from aiogram.types import InlineQuery as AiogramInlineQuery
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from aiogram.types import Message as AiogramMessage
from pydantic import ConfigDict

from .. import utils

logger = logging.getLogger(__name__)


class InlineMessage:
    """Aiogram message, sent via inline bot"""

    def __init__(
        self,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: str,
        inline_message_id: str,
    ):
        self.inline_message_id = inline_message_id
        self.unit_id = unit_id
        self.inline_manager = inline_manager
        self._units = inline_manager._units
        self.form = (
            {"id": unit_id, **self._units[unit_id]} if unit_id in self._units else {}
        )

    async def edit(self, *args, **kwargs) -> "InlineMessage":
        if "unit_id" in kwargs:
            kwargs.pop("unit_id")

        if "inline_message_id" in kwargs:
            kwargs.pop("inline_message_id")

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            inline_message_id=self.inline_message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.inline_manager._delete_unit_message(
            self,
            unit_id=self.unit_id,
        )

    async def unload(self) -> bool:
        return await self.inline_manager._unload_unit(unit_id=self.unit_id)


class BotInlineMessage:
    """Aiogram message, sent through inline bot itself"""

    def __init__(
        self,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: str,
        chat_id: int,
        message_id: int,
    ):
        self.chat_id = chat_id
        self.unit_id = unit_id
        self.inline_manager = inline_manager
        self.message_id = message_id
        self._units = inline_manager._units
        self.form = (
            {"id": unit_id, **self._units[unit_id]} if unit_id in self._units else {}
        )

    async def edit(self, *args, **kwargs) -> "BotMessage":
        if "unit_id" in kwargs:
            kwargs.pop("unit_id")

        if "message_id" in kwargs:
            kwargs.pop("message_id")

        if "chat_id" in kwargs:
            kwargs.pop("chat_id")

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.inline_manager._delete_unit_message(
            self,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
        )

    async def unload(self, *args, **kwargs) -> bool:
        if "unit_id" in kwargs:
            kwargs.pop("unit_id")

        return await self.inline_manager._unload_unit(
            *args,
            unit_id=self.unit_id,
            **kwargs,
        )


class InlineCall(CallbackQuery, InlineMessage):
    """Modified version of classic aiogram `CallbackQuery`"""
    model_config = ConfigDict(frozen=False)

    def __init__(
        self,
        call: CallbackQuery,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: str,
    ):
        dump = call.model_dump()
        if "result_id" in dump:  # tryung to avoid ValidationError
            dump["id"] = dump.pop("result_id")
        dump["chat_instance"] = ""
        CallbackQuery.__init__(self, **dump)

        self.as_(inline_manager.bot)

        self.original_call = call

        InlineMessage.__init__(
            self,
            inline_manager,
            unit_id,
            call.inline_message_id,
        )


class BotInlineCall(CallbackQuery, BotInlineMessage):
    """Modified version of classic aiogram `CallbackQuery`"""
    model_config = ConfigDict(frozen=False)

    def __init__(
        self,
        call: CallbackQuery,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: str,
    ):
        CallbackQuery.__init__(self, **call.model_dump())

        self.original_call = call

        BotInlineMessage.__init__(
            self,
            inline_manager,
            unit_id,
            call.message.chat.id,
            call.message.message_id,
        )


class InlineUnit:
    """InlineManager extension type. For internal use only"""

    def __init__(self):
        """Made just for type specification"""


class BotMessage(AiogramMessage):
    """Modified version of original Aiogram Message"""

    def __init__(self):
        super().__init__()


class InlineQuery(AiogramInlineQuery):
    """Modified version of original Aiogram InlineQuery"""

    model_config = ConfigDict(frozen=False)

    def __init__(self, inline_query: AiogramInlineQuery):
        super().__init__(**inline_query.model_dump())

        self.inline_query = inline_query
        self.args = (
            self.inline_query.query.split(maxsplit=1)[1]
            if len(self.inline_query.query.split()) > 1
            else ""
        )

    @staticmethod
    def _get_res(title: str, description: str, thumbnail_url: str) -> list:
        return [
            InlineQueryResultArticle(
                id=utils.rand(20),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text="😶‍🌫️ <i>There is nothing here...</i>",
                    parse_mode="HTML",
                ),
                thumbnail_url=thumbnail_url,
                thumb_width=128,
                thumb_height=128,
            )
        ]

    async def e400(self):
        await self.answer(
            self._get_res(
                title="🚫 400",
                description=(
                    "Bad request. You need to pass right arguments, follow module's"
                    " documentation"
                ),
                thumbnail_url="https://img.icons8.com/color/344/swearing-male--v1.png",
            ),
            cache_time=0,
        )

    async def e403(self):
        await self.answer(
            self._get_res(
                title="🚫 403",
                description="You have no permissions to access this result",
                thumbnail_url="https://img.icons8.com/external-wanicon-flat-wanicon/344/external-forbidden-new-normal-wanicon-flat-wanicon.png",
            ),
            cache_time=0,
        )

    async def e404(self):
        await self.answer(
            self._get_res(
                title="🚫 404",
                description="No results found",
                thumbnail_url="https://img.icons8.com/external-justicon-flat-justicon/344/external-404-error-responsive-web-design-justicon-flat-justicon.png",
            ),
            cache_time=0,
        )

    async def e426(self):
        await self.answer(
            self._get_res(
                title="🚫 426",
                description="You need to update Heroku before sending this request",
                thumbnail_url="https://img.icons8.com/fluency/344/approve-and-update.png",
            ),
            cache_time=0,
        )

    async def e500(self):
        await self.answer(
            self._get_res(
                title="🚫 500",
                description="Internal userbot error while processing request. More info in logs",
                thumbnail_url="https://img.icons8.com/external-vitaliy-gorbachev-flat-vitaly-gorbachev/344/external-error-internet-security-vitaliy-gorbachev-flat-vitaly-gorbachev.png",
            ),
            cache_time=0,
        )
