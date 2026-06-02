# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import typing

custom_placeholders = {}


def register_placeholder(
    placeholder: str,
    callback: typing.Callable,
    description: typing.Optional[str] = None,
):
    """
    Register placeholder
    """
    module_name = callback.__self__.__class__.__name__
    module_instance = callback.__self__
    custom_placeholders[placeholder] = {
        "module_name": module_name,
        "module_instance": module_instance,
        "callback": callback,
        "description": description,
        "placeholder_name": placeholder,
    }
    return True


async def get_placeholder(placeholder: str, data: dict | None = None):
    """
    Returns placeholder data
    """
    callback = custom_placeholders[placeholder]["callback"]
    try:
        callback_data = str(await callback(data))
    except:
        callback_data = str(await callback())
    return callback_data


async def get_placeholders(data, custom_message):
    """
    Returns placeholders if it is in custom_message
    """
    if custom_message is None:
        return data
    for placeholder in custom_placeholders.values():
        if f"{{{placeholder['placeholder_name']}}}" in custom_message:
            data[placeholder["placeholder_name"]] = await get_placeholder(
                placeholder["placeholder_name"], data
            )
    return data


def unregister_placeholders(module_name: str) -> int:
    """
    Removes placeholders by module_name
    """
    placeholders_to_remove = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            placeholders_to_remove.append(placeholder_name)
    for placeholder_name in placeholders_to_remove:
        del custom_placeholders[placeholder_name]
    return True


def config_placeholders():
    """
    Return placeholders list for config
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        result.append(
            f"{{{placeholder_name}}} - {placeholder_data.get('description') if placeholder_data.get('description') is not None else 'No docs'}"
        )
    if result == []:
        return None
    else:
        return "\n".join(result)


def help_placeholders(module_name, self):
    """
    Return placeholders list for help
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            if placeholder_data.get("description") is not None:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - {placeholder_data.get('description')}"
                )
            else:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - No docs"
                )
    return result


def debug_placeholders():
    """
    Just for debug purposes
    """
    return custom_placeholders
