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
import contextlib
import datetime
import io
import json
import logging
import os
import re 
import time
import zipfile
from pathlib import Path

from aiogram.types import BufferedInputFile
from herokutl.tl.types import Message

from .. import loader, utils
from ..inline.types import BotInlineCall

logger = logging.getLogger(__name__)

@loader.tds
class HerokuBackupMod(loader.Module):
    """Handles database and modules backups"""

    strings = {"name": "HerokuBackup"}

    async def client_ready(self):
        if not self.get("period"):
            await self.inline.bot.send_photo(
                self.tg_id,
                photo="https://imgur.com/a/wfiqkDa.png",
                caption=self.strings("period"),
                reply_markup=self.inline.generate_markup(
                    utils.chunks(
                        [
                            {
                                "text": f"🕰 {i} h",
                                "callback": self._set_backup_period,
                                "args": (i,),
                            }
                            for i in [1, 2, 4, 6, 8, 12, 24, 48, 168]
                        ],
                        3,
                    )
                    + [
                        [
                            {
                                "text": "🚫 Never",
                                "callback": self._set_backup_period,
                                "args": (0,),
                            }
                        ]
                    ]
                ),
            )

        self._backup_channel, _ = await utils.asset_channel(
            self._client,
            "heroku-backups",
            "📼 Your database backups will appear here",
            silent=True,
            archive=True,
            avatar="https://raw.githubusercontent.com/coddrago/Heroku/dev-test/assets/heroku-backups.png",
            _folder="heroku",
            invite_bot=True,
        )

    async def _set_backup_period(self, call: BotInlineCall, value: int):
        if not value:
            self.set("period", "disabled")
            await self.inline.bot(call.answer(self.strings("never"), show_alert=True))
            await call.delete()
            return

        self.set("period", value * 60 * 60)
        self.set("last_backup", round(time.time()))

        await self.inline.bot(call.answer(self.strings("saved"), show_alert=True))
        await call.delete()

    @loader.command()
    async def set_backup_period(self, message: Message):
        """[time] | set your backup bd period"""
        if (
            not (args := utils.get_args_raw(message))
            or not args.isdigit()
            or int(args) not in range(200)
        ):
            await utils.answer(message, self.strings("invalid_args"))
            return

        if not int(args):
            self.set("period", "disabled")
            await utils.answer(message, f"<b>{self.strings('never').format(prefix=self.get_prefix())}</b>")
            return

        period = int(args) * 60 * 60
        self.set("period", period)
        self.set("last_backup", round(time.time()))
        await utils.answer(message, f"<b>{self.strings('saved').format(prefix=self.get_prefix())}</b>")

    @loader.loop(interval=1, autostart=True)
    async def handler(self):
        try:
            if self.get("period") == "disabled":
                raise loader.StopLoop

            if not self.get("period"):
                await asyncio.sleep(3)
                return

            if not self.get("last_backup"):
                self.set("last_backup", round(time.time()))
                await asyncio.sleep(self.get("period"))
                return

            await asyncio.sleep(
                self.get("last_backup") + self.get("period") - time.time()
            )

            db = io.BytesIO(json.dumps(self._db).encode())
            db.name = "db.json"

            mods = io.BytesIO()
            with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                    for file in files:
                        if file.endswith(f"{self.tg_id}.py"):
                            with open(os.path.join(root, file), "rb") as f:
                                zipf.writestr(file, f.read())
                zipf.writestr("db_mods.json", json.dumps(self.lookup("Loader").get("loaded_modules", {})))

            mods.seek(0)
            mods.name = "mods.zip"

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("db.json", db.getvalue())
                z.writestr("mods.zip", mods.getvalue())

            archive.name = f"backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.zip"
            archive.seek(0)

            await self.inline.bot.send_document(
                int(f"-100{self._backup_channel.id}"),
                BufferedInputFile(archive.getvalue(), filename=archive.name),
                reply_markup=self.inline.generate_markup(
                    [
                        [
                            {
                                "text": "↪️ Restore this",
                                "data": "heroku/backupall/restore/confirm",
                            }
                        ]
                    ]
                ),
            )

            self.set("last_backup", round(time.time()))
        except loader.StopLoop:
            raise
        except Exception:
            logger.exception("HerokuBackup failed")
            await asyncio.sleep(60)

    @loader.callback_handler()
    async def restore(self, call: BotInlineCall):
        if not call.data.startswith("heroku/backupall/restore"):
            return

        if call.data == "heroku/backupall/restore/confirm":
            await utils.answer(
                call,
                "❓ <b>Are you sure?</b>",
                reply_markup={
                    "text": "✅ Yes",
                    "data": "heroku/backupall/restore",
                },
            )
            return

        try:
            file = await (
                await self._client.get_messages(
                    self._backup_channel, call.message.message_id
                )
            )[0].download_media(bytes)

            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    db_data = json.loads(f.read().decode())

                with contextlib.suppress(KeyError):
                    db_data["heroku.inline"].pop("bot_token")

                if not self._db.process_db_autofix(db_data):
                    raise RuntimeError("Attempted to restore broken database")

                self._db.clear()
                self._db.update(**db_data)
                self._db.save()

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        with modzip.open("db_mods.json", "r") as modules:
                            db_mods = json.loads(modules.read().decode())
                            if isinstance(db_mods, dict):
                                self.lookup("Loader").set("loaded_modules", db_mods)

                        for name in modzip.namelist():
                            if name == "db_mods.json":
                                continue
                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())

            await call.answer(self.strings("all_restored"), show_alert=True)
            await self.invoke("restart", "-f", peer=call.message.peer_id)
        except Exception:
            logger.exception("Restore from backupall failed")
            await call.answer(self.strings("reply_to_file"), show_alert=True)

    def _convert(self, backup):
        fixed = re.sub(r'(hikka\.)(\S+\":)', lambda m: 'heroku.' + m.group(2), backup)
        txt = io.BytesIO(fixed.encode())
        txt.name = f"db-converted-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"
        return txt

    async def convert(self, call: BotInlineCall, ans, file):
        if ans == "y":
            await utils.answer(
                call,
                self.strings["converting_db"]
            )
            backup = self._convert(file)
            await utils.answer_file(
                call,
                backup,
                caption=self.strings("backup_caption").format(
                    prefix=utils.escape_html(self.get_prefix())
                ),
            )
        else:
            await utils.answer(
                call,
                self.strings["advice_converting"],
                reply_markup=
                    [
                        [
                            {
                                "text": "🔻 Close",
                                "action": "close"
                            }
                        ]
                    ]
                )

    @loader.command()
    async def backupdb(self, message: Message):
        txt = io.BytesIO(json.dumps(self._db).encode())
        txt.name = f"db-backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"
        await self._client.send_file(
            "me",
            txt,
            caption=self.strings("backup_caption").format(
                prefix=utils.escape_html(self.get_prefix())
            ),
        )
        await utils.answer(message, self.strings("backup_sent"))

    @loader.command()
    async def restoredb(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(
                message,
                self.strings("reply_to_file"),
            )
            return

        file = await reply.download_media(bytes)
        decoded_text = json.loads(file.decode())
        if re.search(r'"(hikka\.)(\S+\":)', file.decode()):
            await utils.answer(message,
                               self.strings["db_warning"],
                               reply_markup=
                                    [
                                       {
                                           "text": "❌",
                                           "callback": self.convert,
                                           "args": ("n", file.decode(),),
                                       },
                                       {
                                           "text": "✅",
                                           "callback": self.convert,
                                           "args": ("y", file.decode(),),
                                       }
                                    ]
                                )
            return

        with contextlib.suppress(KeyError):
            decoded_text["heroku.inline"].pop("bot_token")

        if not self._db.process_db_autofix(decoded_text):
            raise RuntimeError("Attempted to restore broken database")

        self._db.clear()
        self._db.update(**decoded_text)
        self._db.save()

        await utils.answer(message, self.strings("db_restored"))
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupmods(self, message: Message):
        mods_quantity = len(self.lookup("Loader").get("loaded_modules", {}))

        result = io.BytesIO()
        result.name = "mods.zip"

        db_mods = json.dumps(self.lookup("Loader").get("loaded_modules", {})).encode()

        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
                            mods_quantity += 1

            zipf.writestr("db_mods.json", db_mods)

        archive = io.BytesIO(result.getvalue())
        archive.name = f"mods-{datetime.datetime.now():%d-%m-%Y-%H-%M}.zip"

        await utils.answer_file(
            message,
            archive,
            caption=self.strings("modules_backup").format(
                mods_quantity,
                utils.escape_html(self.get_prefix()),
            ),
        )

    @loader.command()
    async def restoremods(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings("reply_to_file"))
            return

        file = await reply.download_media(bytes)
        try:
            decoded_text = json.loads(file.decode())
        except Exception:
            try:
                file = io.BytesIO(file)
                file.name = "mods.zip"

                with zipfile.ZipFile(file) as zf:
                    with zf.open("db_mods.json", "r") as modules:
                        db_mods = json.loads(modules.read().decode())
                        if isinstance(db_mods, dict) and all(
                            (
                                isinstance(key, str)
                                and isinstance(value, str)
                                and utils.check_url(value)
                            )
                            for key, value in db_mods.items()
                        ):
                            self.lookup("Loader").set("loaded_modules", db_mods)

                    for name in zf.namelist():
                        if name == "db_mods.json":
                            continue

                        path = loader.LOADED_MODULES_PATH / Path(name).name
                        with zf.open(name, "r") as module:
                            path.write_bytes(module.read())
            except Exception:
                logger.exception("Unable to restore modules")
                await utils.answer(message, self.strings("reply_to_file"))
                return
        else:
            if not isinstance(decoded_text, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in decoded_text.items()
            ):
                raise RuntimeError("Invalid backup")

            self.lookup("Loader").set("loaded_modules", decoded_text)

        await utils.answer(message, self.strings("mods_restored"))
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupall(self, message: Message):
        db = io.BytesIO(json.dumps(self._db).encode())
        db.name = "db.json"

        mods = io.BytesIO()
        with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
            zipf.writestr("db_mods.json", json.dumps(self.lookup("Loader").get("loaded_modules", {})))

        mods.seek(0)
        mods.name = "mods.zip"

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("db.json", db.getvalue())
            z.writestr("mods.zip", mods.getvalue())

        archive.name = f"backup-all-{datetime.datetime.now():%d-%m-%Y-%H-%M}.zip"
        archive.seek(0)

        await self._client.send_file(
            "me",
            archive,
            caption=self.strings("backupall_info").format(
                prefix=utils.escape_html(self.get_prefix())
            ),
        )
        await utils.answer(message, self.strings("backupall_sent"))

    @loader.command()
    async def restoreall(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings("reply_to_file"))
            return

        file = await reply.download_media(bytes)
        try:
            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    db_data = json.loads(f.read().decode())

                with contextlib.suppress(KeyError):
                    db_data["heroku.inline"].pop("bot_token")

                if not self._db.process_db_autofix(db_data):
                    raise RuntimeError("Attempted to restore broken database")

                self._db.clear()
                self._db.update(**db_data)
                self._db.save()

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        with modzip.open("db_mods.json", "r") as modules:
                            db_mods = json.loads(modules.read().decode())
                            if isinstance(db_mods, dict):
                                self.lookup("Loader").set("loaded_modules", db_mods)

                        for name in modzip.namelist():
                            if name == "db_mods.json":
                                continue
                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())
        except Exception as e:
            logger.exception("Restore all failed")
            await utils.answer(message, self.strings["reply_to_file"])
            return

        await utils.answer(message, self.strings["all_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)