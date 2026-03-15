
# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import contextlib
import io
import orjson
import logging
import re
import typing

import grapheme
import pyrogram
from pyrogram.enums import ChatType, MessageMediaType
from pyrogram.parser.html import HTML
from pyrogram.types import InputMedia, Message, MessageEntity, LinkPreviewOptions, ReplyParameters
from pyrogram.raw.types import (
    Channel,
    Chat,
    InputDocument,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
)

from .other import _copy_tl
from .entity import get_chat_id, FormattingEntity

from ..inline.types import BotInlineCall, InlineCall, InlineMessage
from ..types import HerokuReplyMarkup, ListLike



emoji_pattern = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "]+",
    flags=re.UNICODE,
)

parser = HTML(None)
logger = logging.getLogger(__name__)

def get_topic(message: Message) -> typing.Optional[int]:
    """
    Get topic id of message
    :param message: Message to get topic of
    :return: int or None if not present
    """
    return (
        (message.reply_to_top_message_id or message.reply_to_message_id)
        if (
            isinstance(message, Message)
            and message.reply_to_top_message_id
        )
        else (
            message.form["top_msg_id"]
            if isinstance(message, (InlineCall, InlineMessage))
            else None
        )
    )

def mime_type(message: Message) -> str:
    """
    Get mime type of document in message
    :param message: Message with document
    :return: Mime type or empty string if not present
    """
    return (
        ""
        if not isinstance(message, Message) or not message.document
        else getattr(getattr(message, "document", False), "mime_type", False) or ""

    )

async def get_message_link(
    message: Message,
    chat: typing.Optional[typing.Union[Chat, Channel]] = None,
) -> str:
    """
    Get link to message
    :param message: Message to get link of
    :param chat: Chat, where message was sent
    :return: Link to message
    """
    if message.chat.type == ChatType.PRIVATE:
        return (
            f"tg://openmessage?user_id={get_chat_id(message)}&message_id={message.id}"
        )

    # if not chat and not (chat := message.chat):
        # chat = await message.get_chat()

    topic_affix = (
        f"?topic={message.reply_to_message_id}"
        if getattr(message, "reply_to_top_message_id", False)
        else ""
    )

    return (
        f"https://t.me/{chat.username}/{message.id}{topic_affix}"
        if getattr(chat, "username", False)
        else f"https://t.me/c/{chat.id}/{message.id}{topic_affix}"
    )


def smart_split(
    text: str = None,
    message: str = None,
    entities: typing.List[FormattingEntity] = None,
    length: int = 4096,
    split_on: ListLike = ("\n", " "),
    min_length: int = 1,
) -> typing.Iterator[str]:
    """
    Split the message into smaller messages.
    A grapheme will never be broken. Entities will be displaced to match the right location. No inputs will be mutated.
    The end of each message except the last one is stripped of characters from [split_on]
    :param text: the plain text input
    :param message: the plain text input (for backwards compatibility, will be ignored if `text` is provided)
    :param entities: the entities
    :param length: the maximum length of a single message
    :param split_on: characters (or strings) which are preferred for a message break
    :param min_length: ignore any matches on [split_on] strings before this number of characters into each message
    :return: iterator, which returns strings

    :example:
        >>> utils.smart_split(
            *pyrogram.extensions.html.parse(
                "<b>Hello, world!</b>"
            )
        )
        <<< ["<b>Hello, world!</b>"]
    """

    # Authored by @bsolute

    if not text:
        text = message

    _ent = entities.copy()
    entities = []
    for ent in _ent:
        if not isinstance(ent, MessageEntity):
            entities.append(MessageEntity._parse(None, ent, {}))

    encoded = text.encode("utf-16le")
    pending_entities = entities
    text_offset = 0
    bytes_offset = 0
    text_length = len(text)
    bytes_length = len(encoded)

    while text_offset < text_length:
        if bytes_offset + length * 2 >= bytes_length:
            yield parser.unparse(
                text[text_offset:],
                list(sorted(pending_entities, key=lambda x: (x.offset, -x.length))),
            )
            break

        codepoint_count = len(
            encoded[bytes_offset : bytes_offset + length * 2].decode(
                "utf-16le",
                errors="ignore",
            )
        )

        for search in split_on:
            search_index = text.rfind(
                search,
                text_offset + min_length,
                text_offset + codepoint_count,
            )
            if search_index != -1:
                break
        else:
            search_index = text_offset + codepoint_count

        split_index = grapheme.safe_split_index(text, search_index)

        split_offset_utf16 = (
            len(text[text_offset:split_index].encode("utf-16le"))
        ) // 2
        exclude = 0

        while (
            split_index + exclude < text_length
            and text[split_index + exclude] in split_on
        ):
            exclude += 1

        current_entities = []
        entities = pending_entities.copy()
        pending_entities = []

        for entity in entities:
            match True:
                case _ if (
                    entity.offset < split_offset_utf16
                    and entity.offset + entity.length > split_offset_utf16 + exclude
                ):
                    current_entities.append(
                        _copy_tl(
                            entity,
                            length=split_offset_utf16 - entity.offset,
                        )
                    )
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=0,
                            length=entity.offset
                            + entity.length
                            - split_offset_utf16
                            - exclude,
                        )
                    )
                case _ if entity.offset < split_offset_utf16 < entity.offset + entity.length:
                    current_entities.append(
                        _copy_tl(
                            entity,
                            length=split_offset_utf16 - entity.offset,
                        )
                    )
                case _ if entity.offset < split_offset_utf16:
                    current_entities.append(entity)
                case _ if (
                    entity.offset + entity.length
                    > split_offset_utf16 + exclude
                    > entity.offset
                ):
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=0,
                            length=entity.offset
                            + entity.length
                            - split_offset_utf16
                            - exclude,
                        )
                    )
                case _ if entity.offset + entity.length > split_offset_utf16 + exclude:
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=entity.offset - split_offset_utf16 - exclude,
                        )
                    )

        current_text = text[text_offset:split_index]
        yield parser.unparse(
            current_text,
            list(sorted(current_entities, key=lambda x: (x.offset, -x.length))),
        )

        text_offset = split_index + exclude
        bytes_offset += len(current_text.encode("utf-16le"))


def array_sum(
    array: typing.List[typing.List[typing.Any]], /
) -> typing.List[typing.Any]:
    """
    Performs basic sum operation on array
    :param array: Array to sum
    :return: Sum of array
    """
    result = []
    for item in array:
        result += item

    return result

async def answer(
    message: typing.Union[Message, InlineCall, InlineMessage],
    response: str,
    *,
    reply_markup: typing.Optional[HerokuReplyMarkup] = None,
    **kwargs,
) -> typing.Union[InlineCall, InlineMessage, Message]:
    """
    Use this to give the response to a command
    :param message: Message to answer to. Can be a tl message or heroku inline object
    :param response: Response to send
    :param reply_markup: Reply markup to send. If specified, inline form will be used
    :return: Message or inline object

    :example:
        >>> await utils.answer(message, "Hello world!")
        >>> await utils.answer(
            message,
            "https://some-url.com/photo.jpg",
            caption="Hello, this is your photo!",
            asfile=True,
        )
        >>> await utils.answer(
            message,
            "Hello world!",
            reply_markup={"text": "Hello!", "data": "world"},
            silent=True,
            disable_security=True,
        )
    """
    # Compatibility with FTG\GeekTG

    if isinstance(message, list) and message:
        message = message[0]

    if reply_markup is not None:
        if not isinstance(reply_markup, (list, dict)):
            raise ValueError("reply_markup must be a list or dict")

        if reply_markup:
            kwargs.pop("message", None)
            if isinstance(message, (InlineMessage, InlineCall, BotInlineCall)):
                await message.edit(response, reply_markup, **kwargs)
                return

            reply_markup = message._client.loader.inline._normalize_markup(reply_markup)
            result = await message._client.loader.inline.form(
                response,
                message=message if message.outgoing else get_chat_id(message),
                reply_markup=reply_markup,
                **kwargs,
            )
            return result

    if isinstance(message, (InlineMessage, InlineCall, BotInlineCall)):
        await message.edit(response)
        return message

    kwargs.setdefault("link_preview_options", LinkPreviewOptions(is_disabled=True))

    edit = (message.outgoing and not message.via_bot and not message.forward_origin)
    has_file = (
        isinstance(response, (bytes, io.IOBase, InputDocument))
        or (isinstance(response, str) and kwargs.get("asfile", False))
        or kwargs.get("file", None) is not None
    )
    if not edit:
            kwargs.setdefault(
                "reply_parameters",
                ReplyParameters(getattr(message, "reply_to_message_id", None)),
            )
    elif "reply_parameters" in kwargs:
            kwargs.pop("reply_parameters")

    if isinstance(response, str) and not kwargs.pop("asfile", False):
        text, entities = (await message._client.parser.parse(response)).values()
        entities = [MessageEntity._parse(message._client, ent, {}) for ent in (entities or [])]

        if len(text) >= 4096 and not hasattr(message, "heroku_grepped"):
            try:
                if not message._client.loader.inline.init_complete:
                    raise

                strings = list(smart_split(text, entities, 4096))

                if len(strings) > 10:
                    raise

                list_ = await message._client.loader.inline.list(
                    message=message,
                    strings=strings,
                )

                if not list_:
                    raise

                return list_
            except Exception:
                file = io.BytesIO(text.encode("utf-8"))
                file.name = "command_result.txt"

                result = await message._client.send_document(
                    message.chat.id,
                    file,
                    caption=message._client.loader.lookup("translations").strings(
                        "too_long"
                    ),
                    reply_parameters=kwargs.get("reply_parameters") or ReplyParameters(message_id=get_topic(message)),
                )

                if message.outgoing:
                    await message.delete()

                return result

        if edit:
            if kwargs.get("file", False) and (
                message.media is None or (
                    message.media is None or message.media in (
                        MessageMediaType.WEB_PAGE, MessageMediaType.PHOTO, MessageMediaType.DOCUMENT
                    )
                )
            ): # TODO
                result = await message.edit_media(
                    media=kwargs.pop("file"),
                    
                )
            else:
                kwargs.pop("file", None)
                result = await (message.edit_text if edit else message.answer)(
                    text,
                    entities=entities,
                    **kwargs,
                )
        else:
            result = await message.answer(
                text,
                entities=entities,
                **kwargs
            )
    elif isinstance(response, Message):
        if message.media is None and (
            response.media is None or response.media in (MessageMediaType.WEB_PAGE, MessageMediaType.PHOTO, MessageMediaType.DOCUMENT)
        ):
            if response.media:
                result = await message.edit_media(
                    media=InputMedia( # TODO
                        response.document,
                        response.content,
                        caption_entities=response.caption_entities
                    )
                )
            result = await message.edit(
                response.text,
                entities=response.entities,
                link_preview_options=LinkPreviewOptions(is_disabled=isinstance(response.media, MessageMediaWebPage)),
            )
        else:
            result = await message.answer(response, **kwargs)
    else:
        if isinstance(response, bytes):
            response = io.BytesIO(response)
        elif isinstance(response, str):
            response = io.BytesIO(response.encode("utf-8"))

        if name := kwargs.pop("filename", None):
            response.name = name

        if message.media is not None and edit: # TODO
            result = await message.edit_media(file=response, **kwargs)
        else:
            kwargs.setdefault(
                "reply_parameters",
                ReplyParameters(message_id=getattr(message, "reply_to_message_id", get_topic(message))),
            )
            result = await message._client.send_document(message.chat.id, response, **kwargs)
            if message.outgoing:
                await message.delete()

    return result


async def answer_file(
    message: typing.Union[Message, InlineCall, InlineMessage],
    file: typing.Union[str, bytes, io.IOBase, InputDocument],
    caption: typing.Optional[str] = None,
    **kwargs,
):
    """
    Use this to answer a message with a document
    :param message: Message to answer
    :param file: File to send - url, path or bytes
    :param caption: Caption to send
    :param kwargs: Extra kwargs to pass to `send_document`
    :return: Sent message

    :example:
        >>> await utils.answer_file(message, "test.txt")
        >>> await utils.answer_file(
            message,
            "https://mods.hikariatama.ru/badges/artai.jpg",
            "This is the cool module, check it out!",
        )
    """
    if isinstance(message, (InlineCall, InlineMessage)):
        message = message.form["caller"]

    if topic := get_topic(message):
        kwargs.setdefault("reply_parameters", ReplyParameters(topic))

    try:
        response = await message._client.send_document(
            message.chat.id,
            file,
            caption=caption,
            **kwargs,
        )
    except Exception:
        if caption:
            logger.warning(
                "Failed to send file, sending plain text instead", exc_info=True
            )
            return await answer(message, caption, **kwargs)

        raise

    with contextlib.suppress(Exception):
        await message.delete()

    return response

def censor(
    obj: typing.Any,
    to_censor: typing.Optional[typing.Iterable[str]] = None,
    replace_with: str = "redacted_{count}_chars",
):
    """
    May modify the original object, but don't rely on it
    :param obj: Object to censor, preferrably telethon
    :param to_censor: Iterable of strings to censor
    :param replace_with: String to replace with, {count} will be replaced with the number of characters
    :return: Censored object
    """
    if to_censor is None:
        to_censor = ["phone"]

    for k, v in vars(obj).items():
        if k in to_censor:
            setattr(obj, k, replace_with.format(count=len(v)))
        elif k[0] != "_" and hasattr(v, "__dict__"):
            setattr(obj, k, censor(v, to_censor, replace_with))

    return obj

def msg_censor(
    obj: Message,
):
    """Replace message user's phone"""
    if obj.from_user:
        user_raw = obj.from_user.raw
        user_raw.phone = "&lt;phone&gt;"
        obj.from_user = obj.from_user._parse(obj._client, user_raw)
    
    return obj

def is_serializable(x: typing.Any, /) -> bool:
    """
    Checks if object is JSON-serializable
    :param x: Object to check
    :return: True if object is JSON-serializable, False otherwise
    """
    try:
        orjson.dumps(x)
        return True
    except Exception:
        return False


def extract_urls(text: str) -> typing.List[str]:
    """
    Extract all URLs from text
    :param text: Text to extract URLs from
    :return: List of URLs
    """
    url_regex = re.compile(r'https?://[^\s]+')
    return url_regex.findall(text)


def has_media(message: Message) -> bool:
    """
    Check if message contains media
    :param message: Message to check
    :return: True if message has media, False otherwise
    """
    return isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage))
