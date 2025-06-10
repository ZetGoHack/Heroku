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

import re
import difflib
import inspect
import logging

from herokutl.extensions.html import CUSTOM_EMOJIS
from herokutl.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class Help(loader.Module):
    """Shows help for modules and commands"""

    strings = {"name": "Help"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "core_emoji",
                "<emoji document_id=4974681956907221809>▪️</emoji>",
                lambda: "Core module bullet",
            ),
            loader.ConfigValue(
                "plain_emoji",
                "<emoji document_id=4974508259839836856>▪️</emoji>",
                lambda: "Plain module bullet",
            ),
            loader.ConfigValue(
                "empty_emoji",
                "<emoji document_id=5100652175172830068>🟠</emoji>",
                lambda: "Empty modules bullet",
            ),
            loader.ConfigValue(
                "desc_icon",
                "<emoji document_id=5188377234380954537>🪐</emoji>",
                lambda: "Desc emoji",
            ),
            loader.ConfigValue(
                "command_emoji",
                "<emoji document_id=5197195523794157505>▫️</emoji>",
                lambda: "Emoji for command",
            ),
        )

    @loader.command(ru_doc="[args] | Спрячет ваши модули", ua_doc="[args] | Сховає ваші модулі", de_doc="[args] | Versteckt Ihre Module")
    async def helphide(self, message: Message):
        """[args] | hide your modules"""
        if not (modules := utils.get_args(message)):
            await utils.answer(message, self.strings("no_mod"))
            return

        currently_hidden = self.get("hide", [])
        hidden, shown = [], []
        for module in filter(lambda module: self.lookup(module), modules):
            module = self.lookup(module)
            module = module.__class__.__name__
            if module in currently_hidden:
                currently_hidden.remove(module)
                shown += [module]
            else:
                currently_hidden += [module]
                hidden += [module]

        self.set("hide", currently_hidden)

        await utils.answer(
            message,
            self.strings("hidden_shown").format(
                len(hidden),
                len(shown),
                "\n".join([f"👁‍🗨 <i>{m}</i>" for m in hidden]),
                "\n".join([f"👁 <i>{m}</i>" for m in shown]),
            ),
        )

    def find_aliases(self, command: str) -> list:
        """Find aliases for command"""
        aliases = []
        _command = self.allmodules.commands[command]
        if getattr(_command, "alias", None) and not (
            aliases := getattr(_command, "aliases", None)
        ):
            aliases = [_command.alias]

        return aliases or []

    async def modhelp(self, message: Message, args: str):
        exact = True
        if not (module := self.lookup(args)):
            if method := self.allmodules.dispatch(
                args.lower().strip(self.get_prefix())
            )[1]:
                module = method.__self__
            else:
                module = self.lookup(
                    next(
                        (
                            reversed(
                                sorted(
                                    [
                                        module.strings["name"]
                                        for module in self.allmodules.modules
                                    ],
                                    key=lambda x: difflib.SequenceMatcher(
                                        None,
                                        args.lower(),
                                        x,
                                    ).ratio(),
                                )
                            )
                        ),
                        None,
                    )
                )

                exact = False

        try:
            name = module.strings("name")
        except (KeyError, AttributeError):
            name = getattr(module, "name", "ERROR")

        _name = (
            "{} (v{}.{}.{})".format(
                utils.escape_html(name),
                module.__version__[0],
                module.__version__[1],
                module.__version__[2],
            )
            if hasattr(module, "__version__")
            else utils.escape_html(name)
        )

        reply = "{} <b>{}</b>:".format(
            "<emoji document_id=5134452506935427991>🪐</emoji>",
            _name,
            ""
        )
        if module.__doc__:
            reply += (
                "\n<i><emoji document_id=5879813604068298387>ℹ️</emoji> "
                + utils.escape_html(inspect.getdoc(module))
                + "\n</i>"
            )

        commands = {
            name: func
            for name, func in module.commands.items()
            if await self.allmodules.check_security(message, func)
        }

        if hasattr(module, "inline_handlers"):
            for name, fun in module.inline_handlers.items():
                reply += (
                    "\n<emoji document_id=5372981976804366741>🤖</emoji>"
                    " <code>{}</code> {}".format(
                        f"@{self.inline.bot_username} {name}",
                        (
                            utils.escape_html(inspect.getdoc(fun))
                            if fun.__doc__
                            else self.strings("undoc")
                        ),
                    )
                )

        for name, fun in commands.items():
            reply += (
                f'\n{self.config["command_emoji"]}'
                " <code>{}{}</code>{} {}".format(
                    utils.escape_html(self.get_prefix()),
                    name,
                    (
                        " ({})".format(
                            ", ".join(
                                "<code>{}{}</code>".format(
                                    utils.escape_html(self.get_prefix()),
                                    alias,
                                )
                                for alias in self.find_aliases(name)
                            )
                        )
                        if self.find_aliases(name)
                        else ""
                    ),
                    (
                        utils.escape_html(inspect.getdoc(fun))
                        if fun.__doc__
                        else self.strings("undoc")
                    ),
                )
            )

        await utils.answer(
            message,
            reply
            + (f"\n\n{self.strings('not_exact')}" if not exact else "")
            + (
                f"\n\n{self.strings('core_notice')}"
                if module.__origin__.startswith("<core")
                else ""
            ),
        )

    @loader.command(ru_doc="[args] | Помощь с вашими модулями!", ua_doc="[args] | допоможіть з вашими модулями!", de_doc="[args] | Hilfe mit deinen Modulen!")
    async def help(self, message: Message):
        """[args] | help with your modules!"""
        args = utils.get_args_raw(message)
        force = False
        if "-f" in args:
            args = args.replace(" -f", "").replace("-f", "")
            force = True

        if args:
            await self.modhelp(message, args)
            return

        hidden = self.get("hide", [])

        reply = self.strings("all_header").format(
            len(self.allmodules.modules),
            (
                0
                if force
                else sum(
                    module.__class__.__name__ in hidden
                    for module in self.allmodules.modules
                )
            ),
        )
        shown_warn = False

        plain_ = []
        core_ = []
        no_commands_ = []

        for mod in self.allmodules.modules:
            if not hasattr(mod, "commands"):
                logger.debug("Module %s is not inited yet", mod.__class__.__name__)
                continue

            if mod.__class__.__name__ in self.get("hide", []) and not force:
                continue

            tmp = ""

            try:
                name = mod.strings["name"]
            except KeyError:
                name = getattr(mod, "name", "ERROR")

            if (
                not getattr(mod, "commands", None)
                and not getattr(mod, "inline_handlers", None)
                and not getattr(mod, "callback_handlers", None)
            ):
                no_commands_ += [
                    "\n{} <code>{}</code>".format(self.config["empty_emoji"], name)
                ]
                continue

            core = mod.__origin__.startswith("<core")
            tmp += "\n{} <code>{}</code>".format(
                self.config["core_emoji"] if core else self.config["plain_emoji"], name
            )
            first = True

            commands = [
                name
                for name, func in mod.commands.items()
                if await self.allmodules.check_security(message, func) or force
            ]

            for cmd in commands:
                if first:
                    tmp += f": ( {cmd}"
                    first = False
                else:
                    tmp += f" | {cmd}"

            icommands = [
                name
                for name, func in mod.inline_handlers.items()
                if await self.inline.check_inline_security(
                    func=func,
                    user=message.sender_id,
                )
                or force
            ]

            for cmd in icommands:
                if first:
                    tmp += f": ( 🤖 {cmd}"
                    first = False
                else:
                    tmp += f" | 🤖 {cmd}"

            if commands or icommands:
                tmp += " )"
                if core:
                    core_ += [tmp]
                else:
                    plain_ += [tmp]
            elif not shown_warn and (mod.commands or mod.inline_handlers):
                reply = (
                    "<i>You have permissions to execute only these"
                    f" commands</i>\n{reply}"
                )
                shown_warn = True

        def extract_name(line):
            match = re.search(r'[\U0001F300-\U0001FAFF\U0001F900-\U0001F9FF]*\s*(name.*)', line)
            return match.group(1) if match else line

        plain_.sort(key=extract_name)
        core_.sort(key=extract_name)
        no_commands_.sort(key=extract_name)

        await utils.answer(
            message,
            (self.config["desc_icon"] + " {}\n <blockquote exp>{}</blockquote><blockquote exp>{}</blockquote><blockquote exp>{}</blockquote>").format(
                reply,
                "".join(core_),
                "".join(plain_ + (no_commands_ if force else [])),
                (
                    ""
                    if self.lookup("Loader").fully_loaded
                    else f"\n\n{self.strings('partial_load')}"
                ),
            ),
        )

    @loader.command(ru_doc="| Ссылка на чат помощи", ua_doc="| посилання для чату служби підтримки", de_doc="| Link zum Support-Chat")
    async def support(self, message):
        """| link for support chat"""
       
        await utils.answer(
            message,
            self.strings("support").format(
                (
                    utils.get_platform_emoji()
                    if self._client.heroku_me.premium and CUSTOM_EMOJIS
                    else "🪐"
                )
            ),
        )
