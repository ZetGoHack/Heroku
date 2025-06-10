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

import asyncio
import logging

from .. import loader, utils
from ..inline.types import BotInlineMessage, InlineCall
from ..types import Message

logger = logging.getLogger(__name__)


PRESETS = {
    "fun": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/aniquotes.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/artai.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/inline_ghoul.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/lovemagic.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/mindgame.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/moonlove.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/neko.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/purr.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/rpmod.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/scrolller.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tictactoe.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/trashguy.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/truth_or_dare.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/sticks.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/premium_sticks.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/magictext.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/quotes.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/spam.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/IrisLab.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/arts.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/Complements.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/Compliments.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/mazemod.py",
        "https://mods.codrago.life/randnum.py",
        "https://mods.codrago.life/loli.py",
        "https://mods.codrago.life/DoxTool.py",
        "https://mods.codrago.life/randomizer.py",
    ],
    "chat": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/activists.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/banstickers.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/hikarichat.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/inactive.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/keyword.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tagall.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/voicechat.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/vtt.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/BanMedia.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/swmute.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/filter.py",
        "https://mods.codrago.life/id.py",
        "https://mods.codrago.life/clickon.py",
        "https://mods.codrago.life/autoclicker.py",
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
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/swmute.py",
        "https://mods.codrago.life/modlist.py",
    ],
    "downloaders": [
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/uploader.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/porn.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/web2file.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/instsave.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/tikcock.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/InlineYouTube.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/InlineSpotifyDownloader.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/downloader.py",
        "https://github.com/amm1edev/ame_repo/raw/refs/heads/main/dl_yt_previews.py",
    ],
}


@loader.tds
class Presets(loader.Module):
    """Suggests new Heroku users a packs of modules to load"""

    strings = {"name": "Presets"}

    async def client_ready(self):
        self._markup = utils.chunks(
            [
                {
                    "text": self.strings(f"_{preset}_title"),
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
            'https://imgur.com/a/7xwuOEt.png',
            caption=self.strings('welcome'),
            reply_markup=self.inline.generate_markup(self._markup),
        )

    async def _back(self, call: InlineCall):
        await call.edit(self.strings("welcome"), reply_markup=self._markup)

    async def _install(self, call: InlineCall, preset: str):
        await call.delete()
        m = await self._client.send_message(
            self.inline.bot_id,
            self.strings("installing").format(preset),
        )
        for i, module in enumerate(PRESETS[preset]):
            await m.edit(
                self.strings("installing_module").format(
                    preset,
                    i,
                    len(PRESETS[preset]),
                    module,
                )
            )
            try:
                await self.lookup("loader").download_and_install(module, None)
            except Exception:
                logger.exception("Failed to install module %s", module)

            await asyncio.sleep(1)

        if self.lookup("loader").fully_loaded:
            self.lookup("loader").update_modules_in_db()

        await m.edit(self.strings("installed").format(preset))
        await self._menu()

    def _is_installed(self, link: str) -> bool:
        return any(
            link.strip().lower() == installed.strip().lower()
            for installed in self.lookup("loader").get("loaded_modules", {}).values()
        )

    async def _preset(self, call: InlineCall, preset: str):
        await call.edit(
            self.strings("preset").format(
                self.strings(f"_{preset}_title"),
                self.strings(f"_{preset}_desc"),
                "\n".join(
                    map(
                        lambda x: x[0],
                        sorted(
                            [
                                (
                                    "{} <b>{}</b>".format(
                                        (
                                            self.strings("already_installed")
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
                {"text": self.strings("back"), "callback": self._back},
                {
                    "text": self.strings("install"),
                    "callback": self._install,
                    "args": (preset,),
                },
            ],
        )

    async def aiogram_watcher(self, message: BotInlineMessage):
        if message.text != "/presets" or message.from_user.id != self._client.tg_id:
            return

        await self._menu()

    @loader.command(ru_doc='| Пакеты модулей для загрузки', ua_doc='| Пакети модулів для завантаження', de_doc='| Pakete mit Modulen zum Laden')
    async def presets(self, message: Message):
        """| Packs of modules to load"""
        await self.inline.form(
            message=message,
            photo='https://imgur.com/a/SF0MPmQ.png',
            text=self.strings('welcome').replace('/presets', self.get_prefix() + 'presets'),
            reply_markup=self._markup,
        )
