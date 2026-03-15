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

import getpass
import inspect
import logging
import os
import platform as lib_platform
import random
import time
import typing
from io import BytesIO

from pyrogram.types import Message, ReplyParameters, LinkPreviewOptions
from pyrogram.raw.types import InputMediaWebPage

from .. import loader, main, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

DEBUG_MODS_DIR = os.path.join(utils.get_base_dir(), "debug_modules")

if not os.path.isdir(DEBUG_MODS_DIR):
    os.mkdir(DEBUG_MODS_DIR, mode=0o755)

for mod in os.scandir(DEBUG_MODS_DIR):
    os.remove(mod.path)


@loader.tds
class TestMod(loader.Module):
    """Perform operations based on userbot self-testing"""

    strings = {
        "name": "Tester",
    }

    def __init__(self):
        self._memory = {}
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "force_send_all",
                False,
                (
                    "⚠️ Do not touch, if you don't know what it does!\nBy default, "
                    " Heroku will try to determine, which client caused logs. E.g. there"
                    " is a module TestModule installed on Client1 and TestModule2 on"
                    " Client2. By default, Client2 will get logs from TestModule2, and"
                    " Client1 will get logs from TestModule. If this option is enabled,"
                    " Heroku will send all logs to Client1 and Client2, even if it is"
                    " not the one that caused the log."
                ),
                validator=loader.validators.Boolean(),
                on_change=self._pass_config_to_logger,
            ),
            loader.ConfigValue(
                "tglog_level",
                "ERROR",
                (
                    "⚠️ Do not touch, if you don't know what it does!\n"
                    "Minimal loglevel for records to be sent in Telegram."
                ),
                validator=loader.validators.Choice(
                    ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "DISABLE"]
                ),
                on_change=self._pass_config_to_logger,
            ),
            loader.ConfigValue(
                "ignore_common",
                True,
                "Ignore common errors (e.g. 'TypeError' in telethon)",
                validator=loader.validators.Boolean(),
                on_change=self._pass_config_to_logger,
            ),
            loader.ConfigValue(
                "disable_internet_warn",
                False,
                "Ignore all internet errors",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "custom_message",
                "<tg-emoji emoji-id=5920515922505765329>⚡️</tg-emoji> <b>𝙿𝚒𝚗𝚐: </b><code>{ping}</code><b> 𝚖𝚜 </b>\n<tg-emoji emoji-id=5900104897885376843>🕓</tg-emoji><b> 𝚄𝚙𝚝𝚒𝚖𝚎: </b><code>{uptime}</code>",
                lambda: (
                    "<blockquote expandable>" + self.strings("configping") + "\n" + self.strings("configpingph").format(
                        utils.config_placeholders()
                    ) + "</blockquote>"
                ),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "hint",
                None,
                lambda: self.strings["hint"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "ping_emoji",
                "🪐",
                lambda: self.strings["ping_emoji"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "banner_url",
                None,
                lambda: self.strings["banner_url"],
                validator=loader.validators.RandomLink(),
            ),
            loader.ConfigValue(
                "quote_media",
                False,
                "Switch preview media to quote in ping",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "invert_media",
                False,
                "Switch preview invert media in ping",
                validator=loader.validators.Boolean(),
            ),
        )

    def _pass_config_to_logger(self):
        logging.getLogger().handlers[0].force_send_all = self.config["force_send_all"]
        logging.getLogger().handlers[0].tg_level = {
            "ALL": 0,
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
            "DISABLE": 50000,
        }[self.config["tglog_level"]]
        logging.getLogger().handlers[0].ignore_common = self.config["ignore_common"]

    @loader.command()
    async def clearlogs(self, message: Message):
        for handler in logging.getLogger().handlers:
            handler.buffer = []
            handler.handledbuffer = []
            handler.tg_buff = ""

        await utils.answer(message, self.strings("logs_cleared"))

    @loader.loop(interval=1, autostart=True)
    async def watchdog(self):
        if not os.path.isdir(DEBUG_MODS_DIR):
            return

        try:
            for module in os.scandir(DEBUG_MODS_DIR):
                last_modified = os.stat(module.path).st_mtime
                cls_ = module.path.split("/")[-1].split(".py")[0]

                if cls_ not in self._memory:
                    self._memory[cls_] = last_modified
                    continue

                if self._memory[cls_] == last_modified:
                    continue

                self._memory[cls_] = last_modified
                logger.debug("Reloading debug module %s", cls_)
                with open(module.path, "r") as f:
                    try:
                        await next(
                            module
                            for module in self.allmodules.modules
                            if module.__class__.__name__ == "LoaderMod"
                        ).load_module(
                            f.read(),
                            None,
                            save_fs=False,
                        )
                    except Exception:
                        logger.exception("Failed to reload module in watchdog")
        except Exception:
            logger.exception("Failed debugging watchdog")
            return

    @loader.command()
    async def logs(
        self,
        message: typing.Union[Message, InlineCall],
        force: bool = False,
        lvl: typing.Union[int, None] = None,
    ):
        if not isinstance(lvl, int):
            args = utils.get_args_raw(message)
            if args:
                try:
                    try:
                        lvl = int(args.split()[0])
                    except ValueError:
                        lvl = getattr(logging, args.split()[0].upper(), None)
                except IndexError:
                    lvl = None
            else:
                lvl = None

        if not isinstance(lvl, int):
            try:
                if self.inline.init_complete:
                    await utils.answer(
                        message,
                        self.strings("choose_loglevel"),
                        reply_markup=utils.chunks(
                            [
                                {
                                    "text": name,
                                "callback": self.logs,
                                    "args": (False, level),
                                }
                                for name, level in [
                                    ("🚫 Critical", 60),
                                    ("🚫 Error", 40),
                                    ("⚠️ Warning", 30),
                                    ("ℹ️ Info", 20),
                                    ("⚠️ Debug", 10),
                                    ("🧑‍💻 All", 0),
                                ]
                            ],
                            2,
                        )
                        + [[{"text": self.strings("cancel"), "action": "close"}]],
                )
                else: 
                    raise
            except Exception as e:
                await utils.answer(message, self.strings("set_loglevel") + f"\n{e}")

            return

        logs = "\n\n".join(
            [
                "\n".join(
                    handler.dumps(lvl, client_id=self._client.tg_id)
                    if "client_id" in inspect.signature(handler.dumps).parameters
                    else handler.dumps(lvl)
                )
                for handler in logging.getLogger().handlers
            ]
        )

        named_lvl = (
            lvl
            if lvl not in logging._levelToName
            else logging._levelToName[lvl]  # skipcq: PYL-W0212
        )

        if (
            lvl < logging.WARNING
            and not force
            and (
                not isinstance(message, Message)
                or "force_insecure" not in message.content.lower()
            )
        ):
            try:
                if not self.inline.init_complete:
                    raise

                cfg = {
                    "text": self.strings("confidential").format(named_lvl),
                    "reply_markup": [
                        {
                            "text": self.strings("send_anyway"),
                            "callback": self.logs,
                            "args": [True, lvl],
                        },
                        {"text": self.strings("cancel"), "action": "close"},
                    ],
                }
                if isinstance(message, Message):
                    if not await self.inline.form(**cfg, message=message):
                        raise
                else:
                    await message.edit(**cfg)
            except Exception:
                await utils.answer(
                    message,
                    self.strings("confidential_text").format(named_lvl),
                )

            return

        if len(logs) <= 2:
            back_button = {"text": self.strings["back"], "callback": self.logs}
            await utils.answer(message, self.strings("no_logs").format(named_lvl), reply_markup=back_button)
            return

        logs = self.lookup("evaluator").censor(logs)

        logs = BytesIO(logs.encode("utf-16"))
        logs.name = "heroku-logs.txt"

        ghash = utils.get_git_hash()

        other = (
            *main.__version__,
            (
                " <a"
                f' href="https://github.com/coddrago/Heroku/commit/{ghash}">@{ghash[:8]}</a>'
                if ghash
                else ""
            ),
        )

        if getattr(message, "out", True):
            await message.delete()

        if isinstance(message, Message):
            await utils.answer(
                message,
                logs,
                caption=self.strings("logs_caption").format(named_lvl, *other),
            )
        else:
            await self._client.send_document(
                message.form["chat"],
                logs,
                caption=self.strings("logs_caption").format(named_lvl, *other),
                reply_parameters=ReplyParameters(message_id=message.form["top_msg_id"]),
            )

    @loader.command()
    async def suspend(self, message: Message):
        try:
            time_sleep = float(utils.get_args_raw(message))
            await utils.answer(
                message,
                self.strings("suspended").format(time_sleep),
            )
            time.sleep(time_sleep)
        except ValueError:
            await utils.answer(message, self.strings("suspend_invalid_time"))

    @loader.command()
    async def ping(self, message: Message):
        """- Find out your userbot ping"""
        start = time.perf_counter_ns()
        message = await utils.answer(message, self.config["ping_emoji"])
        banner = str(self.config["banner_url"])
        
        if self.config["banner_url"] and self.config["quote_media"] is True:
            banner = LinkPreviewOptions(url=str(self.config["banner_url"]), is_disabled=False, show_above_text=not self.config["invert_media"])

        elif not self.config["banner_url"]:
            banner = None

        data = {
            "ping": round((time.perf_counter_ns() - start) / 10**6, 3),
            "uptime": utils.formatted_uptime(),
            "ping_hint": (
                (self.config["hint"]) if random.choice([0, 0, 1]) == 1 else ""
            ),
            "hostname": lib_platform.node(),
            "user": getpass.getuser(),
            "platform": utils.get_platform_name(),
        }
        data = await utils.get_placeholders(data, self.config["custom_message"])
        try:
            placeholders_msg = self.config["custom_message"].format(**data)
        except KeyError:
            logger.exception("Missing placeholder in custom_message")
            placeholders_msg = "<tg-emoji emoji-id=5210952531676504517>🚫</tg-emoji>"
        await utils.answer(
            message,
            placeholders_msg,
            link_preview_options = banner,
        )


    async def client_ready(self):
        self._content_channel_id = await utils.wait_for_content_channel(self._db)
        self.logchat = int(f"-100{str(self._content_channel_id).replace('-100', '')}")
        logging.getLogger().handlers[0].install_tg_log(self)
        logger.debug("Bot logging installed for %s", self.logchat)

        self._pass_config_to_logger()
