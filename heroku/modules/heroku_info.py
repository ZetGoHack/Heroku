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

import git
import time
import git
import psutil
import os
import glob
import requests
import re
import emoji

from bs4 import BeautifulSoup
from typing import Optional
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from herokutl.tl.types import Message
from herokutl.utils import get_display_name
from .. import loader, utils, version
import platform as lib_platform
import getpass

@loader.tds
class HerokuInfoMod(loader.Module):
    """Show userbot info"""

    strings = {"name": "HerokuInfo"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "custom_message",
                doc=lambda: self.strings("_cfg_cst_msg"),
            ),

            loader.ConfigValue(
                "banner_url",
                "https://imgur.com/a/7LBPJiq.png",
                lambda: self.strings("_cfg_banner"),
            ),

            loader.ConfigValue(
                "show_heroku",
                True,
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "ping_emoji",
                "🪐",
                lambda: self.strings["ping_emoji"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "switchInfo",
                False,
                "Switch info to mode photo",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "imgSettings",
                ["Лапокапканот", 30, '#000', '0|0', "mm", 0, '#000'],
                "Image settings\n1. Дополнительный ник (если прежний ник не отображается)\n2. Размер шрифта\n3. Цвет шрифта в HEX формате '#000'\n4. Координаты текста '100|100', по умолчания в центре фотографии\n5. Якорь текста -> https://pillow.readthedocs.io/en/stable/_images/anchor_horizontal.svg\n6. Размер обводки, по умолчанию 0\n7. Цвет обводки в HEX формате '#000'",
                validator=loader.validators.Series(
                    fixed_len=7,
                ),
            ),
        )

    def _get_os_name(self):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME"):
                        return line.split("=")[1].strip().strip('"')
        except FileNotFoundError:
            return self.strings['non_detectable']
        
    def remove_emoji_and_html(self, text: str) -> str:
        reg = r'<[^<]+?>'
        text = f"{re.sub(reg, '', text)}"
        allchars = [str for str in text]
        emoji_list = [c for c in allchars if c in emoji.EMOJI_DATA]
        clean_text = ''.join([str for str in text if not any(i in str for i in emoji_list)])
        return clean_text
    
    def imgurpidor(self, url: str) -> str:
        page = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        soup = BeautifulSoup(page.text, 'html.parser')
        metatag = soup.find("meta", property="og:image")
        return metatag['content']

    def _render_info(self, start: float) -> str:
        try:
            repo = git.Repo(search_parent_directories=True)
            diff = repo.git.log([f"HEAD..origin/{version.branch}", "--oneline"])
            upd = (
                self.strings("update_required").format(prefix=self.get_prefix()) if diff else self.strings("up-to-date")
            )
        except Exception:
            upd = ""

        me = self.config['imgSettings'][0] if (self.config['imgSettings'][0] != "Лапокапканот") and self.config['switchInfo'] else '<b><a href="tg://user?id={}">{}</a></b>'.format(
            self._client.heroku_me.id,
            utils.escape_html(get_display_name(self._client.heroku_me)),
        ).replace('{', '').replace('}', '')
        build = utils.get_commit_url()
        _version = f'<i>{".".join(list(map(str, list(version.__version__))))}</i>'
        prefix = f"«<code>{utils.escape_html(self.get_prefix())}</code>»"

        platform = utils.get_named_platform()

        for emoji, icon in [
            ("🍊", "<emoji document_id=5449599833973203438>🧡</emoji>"),
            ("🍇", "<emoji document_id=5449468596952507859>💜</emoji>"),
            ("😶‍🌫️", "<emoji document_id=5370547013815376328>😶‍🌫️</emoji>"),
            ("❓", "<emoji document_id=5407025283456835913>📱</emoji>"),
            ("🍀", "<emoji document_id=5395325195542078574>🍀</emoji>"),
            ("🦾", "<emoji document_id=5386766919154016047>🦾</emoji>"),
            ("🚂", "<emoji document_id=5359595190807962128>🚂</emoji>"),
            ("🐳", "<emoji document_id=5431815452437257407>🐳</emoji>"),
            ("🕶", "<emoji document_id=5407025283456835913>📱</emoji>"),
            ("🐈‍⬛", "<emoji document_id=6334750507294262724>🐈‍⬛</emoji>"),
            ("✌️", "<emoji document_id=5469986291380657759>✌️</emoji>"),
            ("💎", "<emoji document_id=5471952986970267163>💎</emoji>"),
            ("🛡", "<emoji document_id=5282731554135615450>🌩</emoji>"),
            ("🌼", "<emoji document_id=5224219153077914783>❤️</emoji>"),
            ("🎡", "<emoji document_id=5226711870492126219>🎡</emoji>"),
            ("🐧", "<emoji document_id=5361541227604878624>🐧</emoji>"),
            ("🧃", "<emoji document_id=5422884965593397853>🧃</emoji>"),
            ("💻", "<emoji document_id=5469825590884310445>💻</emoji>"),
            ("🍏", "<emoji document_id=5372908412604525258>🍏</emoji>")
        ]:
            platform = platform.replace(emoji, icon)
        return (
            (
                "🪐 Heroku\n"
                if self.config["show_heroku"]
                else ""
            )
            + self.config["custom_message"].format(
                me=me,
                version=_version,
                build=build,
                prefix=prefix,
                platform=platform,
                upd=upd,
                uptime=utils.formatted_uptime(),
                cpu_usage=utils.get_cpu_usage(),
                ram_usage=f"{utils.get_ram_usage()} MB",
                branch=version.branch,
                hostname=lib_platform.node(),
                user=getpass.getuser(),
                os=self._get_os_name() or self.strings('non_detectable'),
                kernel=lib_platform.release(),
                cpu=f"{psutil.cpu_count(logical=False)} ({psutil.cpu_count()}) core(-s); {psutil.cpu_percent()}% total",
                ping=round((time.perf_counter_ns() - start) / 10**6, 3)
            )
            if self.config["custom_message"]
            else (
                f'<b>{{}}</b>\n\n<b>{{}} {self.strings("owner")}:</b> {me}\n\n<b>{{}}'
                f' {self.strings("version")}:</b> {_version} {build}\n<b>{{}}'
                f' {self.strings("branch")}:'
                f"</b> <code>{version.branch}</code>\n{upd}\n\n<b>{{}}"
                f' {self.strings("prefix")}:</b> {prefix}\n<b>{{}}'
                f' {self.strings("uptime")}:'
                f"</b> {utils.formatted_uptime()}\n\n<b>{{}}"
                f' {self.strings("cpu_usage")}:'
                f"</b> <i>~{utils.get_cpu_usage()} %</i>\n<b>{{}}"
                f' {self.strings("ram_usage")}:'
                f"</b> <i>~{utils.get_ram_usage()} MB</i>\n<b>{{}}</b>"
            ).format(
                (
                    utils.get_platform_emoji()
                    if self._client.heroku_me.premium and self.config["show_heroku"]
                    else ""
                ),
                "<emoji document_id=5373141891321699086>😎</emoji>",
                "<emoji document_id=5469741319330996757>💫</emoji>",
                "<emoji document_id=5449918202718985124>🌳</emoji>",
                "<emoji document_id=5472111548572900003>⌨️</emoji>",
                "<emoji document_id=5451646226975955576>⌛️</emoji>",
                "<emoji document_id=5431449001532594346>⚡️</emoji>",
                "<emoji document_id=5359785904535774578>💼</emoji>",
                platform,
            )
        )
    
    def _get_info_photo(self, start: float) -> Optional[Path]:
        imgform = self.config['banner_url'].split('.')[-1]
        imgset = self.config['imgSettings']
        if imgform in ['jpg', 'jpeg', 'png', 'bmp', 'webp']:
            response = requests.get(self.config['banner_url'] if not self.config['banner_url'].startswith('https://imgur') else self.imgurpidor(self.config['banner_url']), stream=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
            img = Image.open(BytesIO(response.content))
            font = ImageFont.truetype(
                glob.glob(f'{os.getcwd()}/assets/font.*')[0], 
                size=int(imgset[1]), 
                encoding='unic'
            )
            w, h = img.size
            draw = ImageDraw.Draw(img)
            draw.text(
                (int(w/2), int(h/2)) if imgset[3] == '0|0' else tuple([int(i) for i in imgset[3].split('|')]),
                f'{utils.remove_html(self._render_info(start))}', 
                anchor=imgset[4],
                font=font,
                fill=imgset[2] if imgset[2].startswith('#') else '#000',
                stroke_width=int(imgset[5]),
                stroke_fill=imgset[6] if imgset[6].startswith('#') else '#000',
                embedded_color=True
            )
            path = f'{os.getcwd()}/assets/imginfo.{imgform}'
            img.save(path)
            return Path(path).absolute()
        return None
    
    @loader.command()
    async def insfont(self, message: Message):
        "<Url|Reply to font> - Install font"
        if message.is_reply:
            reply = await message.get_reply_message()
            fontform = reply.document.mime_type.split("/")[1]
            if not fontform in ['ttf', 'otf']:
                await utils.answer(
                    message,
                    self.strings["incorrect_format_font"]
                )
                return
            origpath = glob.glob(f'{os.getcwd()}/assets/font.*')[0]
            ptf = f'{os.getcwd()}/font.{fontform}'
            os.rename(origpath, ptf)
            photo = await reply.download_media(origpath)
            if photo is None:
                os.rename(ptf, origpath)
                await utils.answer(
                    message,
                    self.strings["no_font"]
                )
                return
            os.remove(ptf)
        elif utils.check_url(utils.get_args_raw(message)):
            fontform = utils.get_args_raw(message).split('.')[-1]
            if not fontform in ['ttf', 'otf']:
                await utils.answer(
                    message,
                    self.strings["incorrect_format_font"]
                )
                return
            response = requests.get(utils.get_args_raw(message), stream=True)
            os.remove(glob.glob(f'{os.getcwd()}/assets/font.*')[0])
            with open(f'{os.getcwd()}/assets/font.{fontform}', 'wb') as file:
                file.write(response.content)
        else:
            await utils.answer(
                message,
                self.strings["no_font"]
            )
            return
        await utils.answer(
            message,
            self.strings["font_installed"]
        )

    @loader.command()
    async def infocmd(self, message: Message):
        start = time.perf_counter_ns()
        if self.config['switchInfo']:
            if self._get_info_photo(start) is None:
                await utils.answer(
                    message, 
                    self.strings["incorrect_img_format"]
                )
                return
           
            await utils.answer_file(
                message,
                self._get_info_photo(start),
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
        elif self.config["custom_message"] is None:
            await utils.answer_file(
                message,
                self.config["banner_url"],
                self._render_info(start),
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
        else:
            if '{ping}' in self.config["custom_message"]:
                message = await utils.answer(message, self.config["ping_emoji"])
            await utils.answer_file(
                message,
                self.config["banner_url"],
                self._render_info(start),
                reply_to=getattr(message, "reply_to_msg_id", None),
            )

    @loader.command()
    async def herokuinfo(self, message: Message):
        await utils.answer(message, self.strings("desc"))

    @loader.command()
    async def setinfo(self, message: Message):
        if not (args := utils.get_args_html(message)):
            return await utils.answer(message, self.strings("setinfo_no_args"))

        self.config["custom_message"] = args
        await utils.answer(message, self.strings("setinfo_success"))

