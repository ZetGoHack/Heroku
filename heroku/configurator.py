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

import re
import string
import sys
import typing


def tty_print(text: str, tty: bool):
    """
    Print text to terminal if tty is True,
    otherwise removes all ANSI escape sequences
    """
    print(text if tty else re.sub(r"\033\[[0-9;]*m", "", text))


def tty_input(text: str, tty: bool) -> str:
    """
    Print text to terminal if tty is True,
    otherwise removes all ANSI escape sequences
    """
    return input(text if tty else re.sub(r"\033\[[0-9;]*m", "", text))


def api_config(tty: typing.Optional[bool] = None):
    """Request API config from user and set"""
    from . import main
    from ._internal import print_banner

    if tty is None:
        print("\033[1;38;2;255;120;0mThe quick brown fox jumps over the lazy dog\033[0m")
        tty = input("Is the text above colored? [y/N]").lower() == "y"

    if tty:
        print_banner("banner.txt")

    tty_print("\033[38;2;255;165;0mWelcome to Heroku Userbot!\033[0m", tty)
    tty_print("\033[38;2;255;120;0m1. Go to https://my.telegram.org and login\033[0m", tty)
    tty_print("\033[38;2;255;120;0m2. Click on \033[1;38;2;255;120;0mAPI development tools\033[0m", tty)
    tty_print(
        (
            "\033[38;2;255;120;0m3. Create a new application, by entering the required"
            " details\033[0m"
        ),
        tty,
    )
    tty_print(
        (
            "\033[38;2;255;120;0m4. Copy your \033[1;38;2;255;120;0mAPI ID\033[38;2;255;120;0m and"
            " \033[1;38;2;255;120;0mAPI hash\033[0m"
        ),
        tty,
    )

    while api_id := tty_input("\033[38;2;255;165;0mEnter API ID: \033[0m", tty):
        if api_id.isdigit():
            break

        tty_print("\033[38;2;255;165;0mInvalid ID\033[0m", tty)

    if not api_id:
        tty_print("\033[0;91mCancelled\033[0m", tty)
        sys.exit(0)

    while api_hash := tty_input("\033[38;2;255;165;0mEnter API hash: \033[0m", tty):
        if len(api_hash) == 32 and all(
            symbol in string.hexdigits for symbol in api_hash
        ):
            break

        tty_print("\033[0;91mInvalid hash\033[0m", tty)

    if not api_hash:
        tty_print("\033[0;91mCancelled\033[0m", tty)
        sys.exit(0)

    main.save_config_key("api_id", int(api_id))
    main.save_config_key("api_hash", api_hash)
    tty_print("\033[1;92mAPI config saved\033[0m", tty)
