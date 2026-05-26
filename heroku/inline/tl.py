import io
import typing

from herokutl import Button
from herokutl import utils as tl_utils
from herokutl.tl import types
from herokutl.tl.functions.messages import (
    EditInlineBotMessageRequest,
    SetInlineBotResultsRequest,
)
from herokutl.tl.types import DocumentAttributeAudio


class TelethonBot:
    def __init__(self, client):
        self.client = client

    async def __call__(self, value):
        if hasattr(value, "__await__"):
            return await value
        return value

    def __getattr__(self, item: str):
        return getattr(self.client, item)

    @staticmethod
    def _normalise_file(file):
        if isinstance(file, bytes):
            media = io.BytesIO(file)
            media.name = "file"
            return media

        if hasattr(file, "data"):
            media = io.BytesIO(file.data)
            media.name = getattr(file, "filename", "file")
            return media

        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass

        return file

    @staticmethod
    def _thread_kwargs(message_thread_id: typing.Optional[int]) -> dict:
        return {"reply_to": message_thread_id} if message_thread_id else {}

    @staticmethod
    def _with_message_id_alias(message):
        if (
            message is not None
            and not hasattr(message, "message_id")
            and hasattr(message, "id")
        ):
            try:
                message.message_id = message.id
            except Exception:
                pass

        return message

    def _build_reply_markup(self, reply_markup):
        if reply_markup is None:
            return None
        if isinstance(
            reply_markup,
            (
                types.ReplyInlineMarkup,
                types.ReplyKeyboardMarkup,
                types.ReplyKeyboardHide,
                types.ReplyKeyboardForceReply,
            ),
        ):
            return reply_markup
        return self.client.build_reply_markup(reply_markup)

    @staticmethod
    def _peer_owner_id(peer) -> int:
        if isinstance(peer, types.PeerUser):
            return peer.user_id
        if isinstance(peer, types.PeerChannel):
            return peer.channel_id
        if isinstance(peer, types.PeerChat):
            return peer.chat_id
        raise TypeError(f"Unsupported inline peer type: {type(peer)!r}")

    @classmethod
    def _coerce_inline_message_id(cls, inline_message_id):
        if inline_message_id is None:
            return None

        if isinstance(
            inline_message_id,
            (types.InputBotInlineMessageID, types.InputBotInlineMessageID64),
        ):
            return inline_message_id

        if not isinstance(inline_message_id, str):
            raise TypeError(
                "inline_message_id must be str or InputBotInlineMessageID/64, "
                f"got {type(inline_message_id)!r}"
            )

        message_id, peer, dc_id, access_hash = tl_utils.resolve_inline_message_id(
            inline_message_id
        )

        if peer is None:
            raise ValueError(f"Invalid inline_message_id: {inline_message_id!r}")

        return types.InputBotInlineMessageID64(
            dc_id=dc_id,
            owner_id=cls._peer_owner_id(peer),
            id=message_id,
            access_hash=access_hash,
        )

    @staticmethod
    def _coerce_input_media(media):
        if media is None:
            return None

        if isinstance(
            media,
            (
                types.InputMediaDocument,
                types.InputMediaPhoto,
                types.InputMediaUploadedDocument,
                types.InputMediaUploadedPhoto,
                types.InputMediaWebPage,
                types.InputMediaEmpty,
            ),
        ):
            return media

        try:
            return tl_utils.get_input_media(media)
        except TypeError as e:
            raise TypeError(
                "For inline media edits pass a TL InputMedia object "
                "(InputMediaDocument, InputMediaPhoto, etc.), not raw bytes/path."
            ) from e

    async def get_me(self):
        return await self.client.get_me()

    async def send_message(
        self,
        chat_id,
        text: str = "",
        *,
        reply_markup=None,
        message_thread_id: typing.Optional[int] = None,
        disable_notification: typing.Optional[bool] = None,
        **kwargs,
    ):
        return self._with_message_id_alias(
            await self.client.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                buttons=reply_markup,
                silent=(
                    disable_notification
                    if disable_notification is not None
                    else kwargs.get("disable_notification")
                ),
                link_preview=not kwargs.get("disable_web_page_preview", False),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def send_document(
        self,
        chat_id,
        document,
        *,
        caption: typing.Optional[str] = None,
        reply_markup=None,
        message_thread_id: typing.Optional[int] = None,
        **kwargs,
    ):
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(document),
                caption=caption,
                parse_mode="HTML",
                force_document=True,
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def send_photo(
        self,
        chat_id,
        photo,
        *,
        caption: typing.Optional[str] = None,
        reply_markup=None,
        message_thread_id: typing.Optional[int] = None,
        **kwargs,
    ):
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(photo),
                caption=caption,
                parse_mode="HTML",
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def send_audio(
        self,
        chat_id,
        audio,
        *,
        title: typing.Optional[str] = None,
        performer: typing.Optional[str] = None,
        duration: typing.Optional[int] = None,
        thumbnail=None,
        reply_markup=None,
        message_thread_id: typing.Optional[int] = None,
        **kwargs,
    ):
        attributes = [
            DocumentAttributeAudio(
                duration=duration or 0,
                title=title,
                performer=performer,
            )
        ]
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(audio),
                attributes=attributes,
                thumb=self._normalise_file(thumbnail) if thumbnail is not None else None,
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def delete_message(self, chat_id, message_id):
        return await self.client.delete_messages(chat_id, message_id)

    async def answer_inline_query(
        self,
        inline_query_id: int,
        results: list,
        *,
        cache_time: int = 0,
        is_personal: bool = False,
        next_offset: typing.Optional[str] = None,
        **kwargs,
    ):
        prepared = []
        for item in results:
            if hasattr(item, "__await__"):
                item = await item
            prepared.append(item)

        return await self.client(
            SetInlineBotResultsRequest(
                query_id=inline_query_id,
                results=prepared,
                cache_time=cache_time,
                private=is_personal,
                next_offset=next_offset or "",
                gallery=kwargs.get("gallery", False),
            )
        )

    async def edit_message_media(
        self,
        *,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        media=None,
        reply_markup: typing.Any = None,
        **kwargs,
    ):
        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            input_media = self._coerce_input_media(media)
            markup = self._build_reply_markup(reply_markup)
            return await self.client(
                EditInlineBotMessageRequest(
                    id=inline_id,
                    media=input_media,
                    reply_markup=markup,
                )
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            file=media,
            buttons=reply_markup,
        )

    async def edit_message_text(
        self,
        *,
        text: str,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        reply_markup: typing.Any = None,
        disable_web_page_preview: bool = True,
        **kwargs: typing.Any,
    ) -> typing.Any:
        markup = self._build_reply_markup(reply_markup)

        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            return await self.client.edit_message(
                inline_id,
                text,
                parse_mode="HTML",
                link_preview=not disable_web_page_preview,
                buttons=markup,
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            text,
            parse_mode="HTML",
            link_preview=not disable_web_page_preview,
            buttons=markup,
        )

    async def edit_message_reply_markup(
        self,
        *,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        reply_markup: typing.Any = None,
    ):
        markup = self._build_reply_markup(reply_markup)

        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            return await self.client(
                EditInlineBotMessageRequest(
                    id=inline_id,
                    reply_markup=markup,
                )
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            buttons=markup,
        )


def web_document(
    url: typing.Optional[str],
    *,
    mime_type: str = "image/jpeg",
    width: int = 128,
    height: int = 128,
) -> typing.Optional[types.InputWebDocument]:
    if not url:
        return None

    return types.InputWebDocument(
        url=url,
        size=0,
        mime_type=mime_type,
        attributes=[
            types.DocumentAttributeImageSize(
                w=width,
                h=height,
            )
        ],
    )


def make_button(
    *,
    text: str,
    style: typing.Optional[str] = None,
    icon: typing.Optional[str] = None,
    url: typing.Optional[str] = None,
    data: typing.Optional[typing.Union[str, bytes]] = None,
    switch_inline_query_current_chat: typing.Optional[str] = None,
    switch_inline_query: typing.Optional[str] = None,
    web_app: typing.Optional[typing.Union[str, dict]] = None,
    copy_text: typing.Optional[str] = None,
):
    if url is not None:
        return Button.url(text, url, style=style, icon=icon)

    if data is not None:
        return Button.inline(text, data, style=style, icon=icon)

    if switch_inline_query_current_chat is not None:
        return Button.switch_inline(
            text,
            switch_inline_query_current_chat,
            same_peer=True,
            style=style,
            icon=icon,
        )

    if switch_inline_query is not None:
        return Button.switch_inline(
            text,
            switch_inline_query,
            same_peer=False,
            style=style,
            icon=icon,
        )

    if web_app is not None:
        app_url = web_app if isinstance(web_app, str) else web_app["url"]
        return types.KeyboardButtonWebView(text, app_url)

    if copy_text is not None:
        return types.KeyboardButtonCopy(text, copy_text)

    return Button.inline(text, text, style=style, icon=icon)
