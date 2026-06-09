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

import asyncio
import functools
import io
import logging
from math import ceil

import orjson

from .. import loader, utils
from ..inline.types import BotInlineMessage, InlineCall
from ..types import Message

logger = logging.getLogger(__name__)


NUM_ROWS = 2

ROW_SIZE = 4

PRESETS = {
    "fun": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/aniquotes.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/artai.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/inline_ghoul.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/lovemagic.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/mindgame.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/moonlove.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/scrolller.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tictactoe.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/trashguy.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/truth_or_dare.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/sticks.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/premium_sticks.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/magictext.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/quotes.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/IrisLab.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/arts.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/Complements.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/Compliments.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/mazemod.py",
        "https://mods.codrago.life/randnum.py",
        "https://mods.codrago.life/DoxTool.py",
        "https://mods.codrago.life/randomizer.py",
        "https://mods.kok.gay/yg_quotes",
        "https://raw.githubusercontent.com/coddrago/modules/main/hardspam.py",
    ],
    "chat": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/activists.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/banstickers.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/inactive.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/keyword.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tagall.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/BanMedia.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/swmute.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/filter.py",
        "https://mods.codrago.life/id.py",
        "https://mods.codrago.life/autoclicker.py",
        "https://raw.githubusercontent.com/SenkoGuardian/SenModules/refs/heads/My-Modules/Gemini.py",
        "https://raw.githubusercontent.com/yummy1gay/modules/main/yg_checks.py",
        "https://raw.githubusercontent.com/coddrago/modules/main/chatmodule.py",
    ],
    "service": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/account_switcher.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/surl.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/httpsc.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/img2pdf.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/latex.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/pollplot.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/sticks.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/temp_chat.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/vtt.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/accounttime.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/searx.py",
        "https://raw.githubusercontent.com/Ruslan-Isaev/modules/refs/heads/main/whois.py",
        "https://raw.githubusercontent.com/radiocycle/Modules/refs/heads/master/Neofetch.py",
        "https://raw.githubusercontent.com/coddrago/modules/main/dbmod.py",
    ],
    "downloaders": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/uploader.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/web2file.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/instsave.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tikcock.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/downloader.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/dl_yt_previews.py",
        "https://raw.githubusercontent.com/TheKsenon/MyHikkaModules/main/kuploader.py",
    ],
}


@loader.tds
class Presets(loader.Module):
    """Suggests new Heroku users a packs of modules to load"""

    strings = {"name": "Presets"}

    async def client_ready(self):
        self._markup_gen = functools.partial(
            utils.chunks,
            [
                {
                    "text": self.strings[f"_{preset}_title"],
                    "callback": self._preset,
                    "args": (preset,),
                }
                for preset in PRESETS
            ],
            1,
        )

        if self.get("sent"):
            return

        self.set("sent", True)
        await self._menu()

    async def _menu(self):
        await self.inline.bot.send_photo(
            self._client.tg_id,
            "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/presets_cmd.png",
            caption=self.strings["welcome"],
            reply_markup=self.inline.generate_markup(self._markup_gen()),
        )

    async def _back(self, call: InlineCall):
        await call.edit(self.strings["welcome"], reply_markup=self._markup_gen())

    async def _choose_menu(
        self,
        call: InlineCall,
        page: int = 0,
        preset: str = "",
        to_remove: list | None = None,
    ):
        if not preset:
            return
        to_remove = to_remove or []
        to_buttons = [
            (indx, link)
            for indx, link in enumerate(PRESETS[preset])
            if not self._is_installed(link)
        ]
        to_install = PRESETS[preset].copy()
        for index in sorted(to_remove, reverse=True):
            to_install.pop(index)

        kb = []
        for mod_row in utils.chunks(
            to_buttons[page * NUM_ROWS * ROW_SIZE : (page + 1) * NUM_ROWS * ROW_SIZE],
            2,
        ):
            row = []
            for index, link in mod_row:
                text = (
                    f"{('✅ ' if link in to_install else '❌ ')}"
                    f"{link.rsplit('/', maxsplit=1)[1].split('.')[0]}"
                )
                row.append(
                    {
                        "text": text,
                        "callback": self._switch,
                        "args": (page, preset, index, to_remove),
                    }
                )
            kb += [row]

        if len(to_buttons) > NUM_ROWS * ROW_SIZE:
            kb += self.inline.build_pagination(
                callback=functools.partial(
                    self._choose_menu, preset=preset, to_remove=to_remove
                ),
                total_pages=ceil(len(to_buttons) / (NUM_ROWS * ROW_SIZE)),
                current_page=page + 1,
            )

        kb += [
            [
                {"text": self.strings["back"], "callback": self._back},
                {
                    "text": self.strings["install"],
                    "callback": self._install,
                    "args": (preset, to_install),
                },
            ]
        ]

        await call.edit(
            self.strings["preset"].format(
                self.strings[f"_{preset}_title"],
                self.strings[f"_{preset}_desc"],
                "\n".join(
                    map(
                        lambda x: x[0],
                        sorted(
                            [
                                (
                                    "{} <b>{}</b>".format(
                                        (
                                            self.strings["already_installed"]
                                            if self._is_installed(link)
                                            else "▫️"
                                        ),
                                        (
                                            f"<s>{link.rsplit('/', maxsplit=1)[1].split('.')[0]}</s>"
                                            if link not in to_install
                                            else link.rsplit("/", maxsplit=1)[1].split(
                                                "."
                                            )[0]
                                        ),
                                    ),
                                    int(self._is_installed(link)),
                                )
                                for link in PRESETS[preset]
                            ],
                            key=lambda x: x[1],
                            reverse=True,
                        ),
                    )
                ),
            ),
            reply_markup=kb,
        )

    async def _switch(
        self,
        call: InlineCall,
        page: int,
        preset: str,
        index_of_module: int,
        to_remove: list,
    ):
        if index_of_module in to_remove:
            to_remove.remove(index_of_module)
        else:
            to_remove.append(index_of_module)

        await self._choose_menu(call, page, preset, to_remove)

    async def _install(
        self,
        call: InlineCall,
        preset: str,
        modules: list,
        origin: bool = True,
        chat: int | None = None,
    ):
        await call.delete()
        m = await self._client.send_message(
            chat if chat else self.inline.bot_id,
            self.strings["installing"].format(preset),
        )
        for i, module in enumerate(modules):
            await m.edit(
                self.strings["installing_module"].format(
                    preset,
                    i,
                    len(modules),
                    module,
                )
            )
            try:
                await self.lookup("LoaderMod").download_and_install(module, None)
            except Exception:
                logger.exception("Failed to install module %s", module)

            await asyncio.sleep(1)

        if self.lookup("LoaderMod").fully_loaded:
            self.lookup("LoaderMod").update_modules_in_db()

        await m.edit(self.strings["installed"].format(preset))
        if origin:
            await self._menu()

    def _is_installed(self, link: str) -> bool:
        return any(
            link.strip().lower() == installed.strip().lower()
            for installed in self.lookup("LoaderMod").get("loaded_modules", {}).values()
        )

    async def _preset(self, call: InlineCall, preset: str):
        await call.edit(
            self.strings["preset"].format(
                self.strings[f"_{preset}_title"],
                self.strings[f"_{preset}_desc"],
                "\n".join(
                    map(
                        lambda x: x[0],
                        sorted(
                            [
                                (
                                    "{} <b>{}</b>".format(
                                        (
                                            self.strings["already_installed"]
                                            if self._is_installed(link)
                                            else "▫️"
                                        ),
                                        link.rsplit("/", maxsplit=1)[1].split(".")[0],
                                    ),
                                    int(self._is_installed(link)),
                                )
                                for link in PRESETS[preset]
                            ],
                            key=lambda x: x[1],
                            reverse=True,
                        ),
                    )
                ),
            ),
            reply_markup=[
                {"text": self.strings["back"], "callback": self._back},
                {
                    "text": self.strings["install"],
                    "callback": self._choose_menu,
                    "args": (
                        0,
                        preset,
                    ),
                },
            ],
        )

    async def bot_watcher(self, message: BotInlineMessage):
        if message.text != "/presets" or message.from_user.id != self._client.tg_id:
            return

        await self._menu()

    async def get_folders(self):
        return self.db.get("presets", "folders")

    @loader.command(
        ru_doc="| Пакеты модулей для загрузки",
        ua_doc="| Пакети модулів для завантаження",
        de_doc="| Pakete mit Modulen zum Laden",
    )
    async def presets(self, message: Message):
        """| Packs of modules to load"""
        await self.inline.form(
            message=message,
            photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/presets_cmd.png",
            text=self.strings["welcome"].replace(
                "/presets", self.get_prefix() + "presets"
            ),
            reply_markup=self._markup_gen(),
        )

    @loader.command(alias="lp")
    async def loadpreset(self, message: Message):
        """Custom preset loader. Reply to a file or send a file with the command."""
        msg = message if message.file else (await message.get_reply_message())
        if not msg or not msg.file:
            await message.edit(self.lookup("LoaderMod").strings["no_file"])
            return
        try:
            data = orjson.loads(await msg.download_media(bytes))
        except Exception:
            await message.edit(self.lookup("LoaderMod").strings["load_failed"])
            logger.exception("Failed to load preset from file")
            return

        if (
            not isinstance(data, dict)
            or "name" not in data
            or "modules" not in data
            or not isinstance(data["modules"], list)
        ):
            await message.edit(self.lookup("LoaderMod").strings["load_failed"])
            logger.error("Invalid preset format")
            return

        chat = message.chat_id
        await message.delete()
        try:
            description = data["description"]
        except Exception:
            description = self.lookup("help").strings["undoc"]

        modules_list = []
        for link in data["modules"]:
            module_name = (
                link.rsplit("/", maxsplit=1)[1].split(".")[0] if "/" in link else link
            )
            if self._is_installed(link):
                modules_list.append(
                    f"<b>{module_name}</b> {self.strings['already_installed']}"
                )
            else:
                modules_list.append(f"▫️ <b>{module_name}</b>")

        modules = "\n".join(modules_list)

        await self.inline.form(
            message=message,
            text=self.strings["preset"].format(data["name"], description, modules),
            reply_markup=[
                {
                    "text": self.strings["install"],
                    "callback": self._install,
                    "args": (data["name"], data["modules"], False, chat),
                },
                {
                    "text": self.lookup("settings").strings["cancel"],
                    "callback": lambda call: call.delete(),
                },
            ],
        )

    @loader.command(alias="af")
    async def addtofolder(self, message: Message):
        """Add module to custom folder to see its config faster and send via preset."""
        args = utils.get_args(message)
        if self.db.get("presets", "folders") is None:
            self.db.set("presets", "folders", {})
        FOLDERS = self.db.get("presets", "folders")
        if len(args) < 2:
            await message.edit(
                self.strings["add_to_folder_usage"].format(prefix=self.get_prefix())
            )
            return
        folder_name = args[0]
        module_name = args[1]
        if folder_name in FOLDERS and module_name.lower() in [
            m.lower() for m in FOLDERS[folder_name]
        ]:
            await message.edit(self.strings["already_in_folder"].format(folder_name))
            return
        for mod in self.allmodules.modules:
            if mod.__class__.__name__.lower() == module_name.lower():
                if folder_name not in FOLDERS:
                    FOLDERS[folder_name] = []
                FOLDERS[folder_name].append(module_name)
                self.db.set("presets", "folders", FOLDERS)
                await message.edit(
                    self.strings["added_to_folder"].format(module_name, folder_name)
                )
                return
        await message.edit(self.strings["module_not_found"].format(module_name))

    @loader.command(alias="fl")
    async def folderload(self, message: Message):
        """send folder via file"""
        args = utils.get_args(message)
        if self.db.get("presets", "folders") is None:
            self.db.set("presets", "folders", {})
        FOLDERS = self.db.get("presets", "folders")
        if len(args) < 1:
            await message.edit(
                self.strings["folder_load_usage"].format(prefix=self.get_prefix())
            )
            return
        folder_name = args[0]
        if folder_name not in FOLDERS:
            await message.edit(self.strings["folder_not_found"].format(folder_name))
            return
        modules = []
        for module_name in FOLDERS[folder_name]:
            for mod in self.allmodules.modules:
                if mod.__class__.__name__.lower() == module_name.lower():
                    origin = getattr(mod, "__origin__", "")
                    if origin not in ("<core>", "<file>"):
                        modules.append(origin)
                    break
        if not modules:
            await message.edit(self.strings["no_modules_in_folder"].format(folder_name))
            return
        file = io.BytesIO(
            orjson.dumps(
                {"name": folder_name, "description": folder_name, "modules": modules}
            )
        )
        file.name = f"{folder_name}.json"
        await utils.answer(
            message,
            self.strings["folder"].format(folder_name, prefix=self.get_prefix()),
            file=file,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command(alias="rff")
    async def removefromfolder(self, message: Message):
        """Remove module from custom folder."""
        args = utils.get_args(message)
        if self.db.get("presets", "folders") is None:
            self.db.set("presets", "folders", {})
        FOLDERS = self.db.get("presets", "folders")
        if len(args) < 2:
            await message.edit(
                self.strings["remove_from_folder_usage"].format(
                    prefix=self.get_prefix()
                )
            )
            return
        folder_name = args[0]
        module_name = args[1]
        if folder_name not in FOLDERS:
            await message.edit(self.strings["folder_not_found"].format(folder_name))
            return
        if module_name.lower() not in [m.lower() for m in FOLDERS[folder_name]]:
            await message.edit(
                self.strings["module_not_in_folder"].format(module_name, folder_name)
            )
            return
        FOLDERS[folder_name].remove(module_name)
        if FOLDERS[folder_name] == []:
            del FOLDERS[folder_name]
        self.db.set("presets", "folders", FOLDERS)
        await message.edit(
            self.strings["removed_from_folder"].format(module_name, folder_name)
        )

    @loader.command(alias="la")
    async def loadaliases(self, message: Message):
        """Load aliases from file. Send a file with the command or reply to a file."""
        msg = message if message.file else (await message.get_reply_message())
        if not msg or not msg.file:
            await message.edit(self.lookup("LoaderMod").strings["no_file"])
            return
        try:
            data = orjson.loads(await msg.download_media(bytes))
        except Exception:
            await message.edit(self.lookup("LoaderMod").strings["load_failed"])
            logger.exception("Failed to load aliases from file")
            return
        if not isinstance(data, list) or not all(
            isinstance(item, dict) and "alias" in item and "command" in item
            for item in data
        ):
            await message.edit(self.lookup("LoaderMod").strings["load_failed"])
            logger.error("Invalid aliases format")
            return

        loaded = []
        for item in data:
            alias = item["alias"]
            cmd_str = item["command"]
            parts = cmd_str.split(maxsplit=1)
            cmd = parts[0]
            rest = parts[1] if len(parts) > 1 else None
            if self.allmodules.add_alias(alias, cmd, rest):
                self.lookup("Presets").set(
                    "aliases",
                    {
                        **self.lookup("Presets").get("aliases", {}),
                        alias: f"{cmd} {rest}" if rest else cmd,
                    },
                )
                loaded.append(alias)

            else:
                logger.error("Falied to load alias %s", alias)

        await utils.answer(
            message,
            self.lookup("settings")
            .strings("aliases_list")
            .format("\n".join(f"{alias}" for alias in loaded)),
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command(alias="al")
    async def aliasload(self, message: Message):
        """send aliases via file"""
        aliases = self.allmodules.aliases.items()
        if not aliases:
            await message.edit(self.lookup("settings").strings("no_aliases"))
            return
        file = io.BytesIO(
            orjson.dumps([{"alias": alias, "command": cmd} for alias, cmd in aliases])
        )
        file.name = "aliases.json"
        await utils.answer(
            message,
            self.lookup("settings")
            .strings("aliases_file")
            .format(prefix=self.get_prefix()),
            file=file,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )
