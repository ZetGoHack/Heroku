import io
import typing

from herokutl import Button
from herokutl.tl import types


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
            file.seek(0)

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

    async def delete_message(self, chat_id, message_id):
        return await self.client.delete_messages(chat_id, message_id)

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
        if inline_message_id:
            return await self.client.edit_message(
                inline_message_id,
                None,
                text,
                parse_mode="HTML",
                link_preview=not disable_web_page_preview,
                buttons=reply_markup,
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            text,
            parse_mode="HTML",
            link_preview=not disable_web_page_preview,
            buttons=reply_markup,
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
