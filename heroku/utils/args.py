# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import inspect
import logging
import shlex
import typing

import herokutl
import herokutl.extensions
import herokutl.extensions.html
from herokutl.tl.custom.message import Message

from .entity import escape_html, relocate_entities

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)


def iter_attrs(obj: typing.Any, /) -> typing.List[typing.Tuple[str, typing.Any]]:
    """
    Returns list of attributes of object
    :param obj: Object to iterate over
    :return: List of attributes and their values
    """
    return ((attr, getattr(obj, attr)) for attr in dir(obj))


def validate_html(html: str) -> str:
    """
    Removes broken tags from html
    :param html: HTML to validate
    :return: Valid HTML
    """
    text, entities = herokutl.extensions.html.parse(html)
    return herokutl.extensions.html.unparse(escape_html(text), entities)


def get_kwargs() -> typing.Dict[str, typing.Any]:
    """
    Get kwargs of function, in which is called
    :return: kwargs
    """
    # https://stackoverflow.com/a/65927265/19170642
    keys, _, _, values = inspect.getargvalues(inspect.currentframe().f_back)
    return {key: values[key] for key in keys if key != "self"}


def get_args(message: typing.Union[Message, str]) -> typing.List[str]:
    """
    Get arguments from message
    :param message: Message or string to get arguments from
    :return: List of arguments
    """
    if not (message := getattr(message, "message", message)):
        return False

    if len(message := message.split(maxsplit=1)) <= 1:
        return []

    message = message[1]

    try:
        split = shlex.split(message)
    except ValueError:
        return message  # Cannot split, let's assume that it's just one long message

    return list(filter(lambda x: len(x) > 0, split))


def get_args_raw(message: typing.Union[Message, str]) -> str:
    """
    Get the parameters to the command as a raw string (not split)
    :param message: Message or string to get arguments from
    :return: Raw string of arguments
    """
    if not (message := getattr(message, "message", message)):
        return False

    return args[1] if len(args := message.split(maxsplit=1)) > 1 else ""


def get_args_html(message: Message) -> str:
    """
    Get the parameters to the command as string with HTML (not split)
    :param message: Message to get arguments from
    :return: String with HTML arguments
    """
    prefix = message.client.loader.get_prefix()

    if not (message := message.text):
        return False

    if prefix not in message:
        return message

    raw_text, entities = parser.parse(message)

    raw_text = parser._add_surrogate(raw_text)

    try:
        command = raw_text[
            raw_text.index(prefix) : raw_text.index(" ", raw_text.index(prefix) + 1)
        ]
    except ValueError:
        return ""

    command_len = len(command) + 1

    return parser.unparse(
        parser._del_surrogate(raw_text[command_len:]),
        relocate_entities(entities, -command_len, raw_text[command_len:]),
    )


def get_args_split_by(
    message: typing.Union[Message, str],
    separator: str,
) -> typing.List[str]:
    """
    Split args with a specific separator
    :param message: Message or string to get arguments from
    :param separator: Separator to split by
    :return: List of arguments
    """

    args = get_args_raw(message)
    if isinstance(separator, str):
        sections = args.split(separator)
    else:
        sections = [args]
        for sep in separator:
            new_section = []
            for section in sections:
                new_section.extend(section.split(sep))
            sections = new_section
    return [section.strip() for section in sections if section.strip()]


def get_args_int(message: typing.Union[Message, str]) -> typing.List[int]:
    """
    Get arguments as integers
    :param message: Message or string to get arguments from
    :return: List of integers
    """
    args = get_args(message)
    result = []
    for arg in args:
        try:
            result.append(int(arg))
        except ValueError:
            continue
    return result


def get_args_bool(message: typing.Union[Message, str]) -> typing.List[bool]:
    """
    Get arguments as booleans (true/false, yes/no, 1/0)
    :param message: Message or string to get arguments from
    :return: List of booleans
    """
    args = get_args(message)
    result = []
    for arg in args:
        lower_arg = arg.lower()
        if lower_arg in ["true", "yes", "1", "on"]:
            result.append(True)
        elif lower_arg in ["false", "no", "0", "off"]:
            result.append(False)
    return result
