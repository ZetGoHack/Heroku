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
import logging

from deep_translator import GoogleTranslator
from herokutl.tl.custom import Message

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class Translator(loader.Module):
    """Translates text"""

    strings = {
        "name": "Translator",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "only_text",
                False,
                "only translated text in .tr",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "provider",
                "telegram",
                "Translation provider to use",
                validator=loader.validators.Choice(["telegram", "google"]),
            ),
        )

    async def _translate_external(self, text: str, target_lang: str) -> str:

        provider = self.config["provider"]

        def do_translate():
            if provider == "google":
                return GoogleTranslator(source="auto", target=target_lang).translate(
                    text
                )

            return text

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, do_translate)

    @loader.command()
    async def tr(self, message: Message):
        """[lang] <text> - Translate text or reply to a message"""
        if not (args := utils.get_args_raw(message.raw_text)):
            text = None
            lang = self.strings["language"]
        else:
            lang = args.split(maxsplit=1)[0]
            if len(lang) != 2:
                text = args
                lang = self.strings["language"]
            else:
                try:
                    text = args.split(maxsplit=1)[1]
                except IndexError:
                    text = None

        if not text:
            if not (reply := await message.get_reply_message()):
                await utils.answer(message, self.strings["no_args"])
                return

            text = reply.raw_text
            entities = reply.entities
        else:
            entities = []

        provider = self.config["provider"]

        try:
            if provider == "telegram":
                tr_text = await self._client.translate(
                    message.peer_id, message, lang, raw_text=text, entities=entities
                )
            else:
                tr_text = await self._translate_external(text, lang)

            if self.config["only_text"]:
                await utils.answer(message, tr_text)
            else:
                await utils.answer(
                    message, self.strings["translated_text"].format(tr_text=tr_text)
                )

        except Exception:
            logger.exception("Unable to translate text")
            await utils.answer(message, self.strings["error"])
