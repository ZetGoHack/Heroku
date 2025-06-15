#   █▀▀ ▄▀█   █▀▄▀█ █▀█ █▀▄ █▀
#   █▀░ █▀█   █░▀░█ █▄█ █▄▀ ▄█

#   https://t.me/famods

# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: Executor
# Description: Выполнение python кода
# meta developer: @FAmods
# meta banner: https://github.com/FajoX1/FAmods/blob/main/assets/banners/executor.png?raw=true
# -------------------------------------------------------------------------------—

import sys
import traceback
import html
import time
import herokutl
import asyncio
import logging

from meval import meval
from io import StringIO

from .. import loader, utils
from ..log import HerokuException

logger = logging.getLogger(__name__)

@loader.tds
class Executor(loader.Module):
    """Выполнение python кода"""

    strings = {
        "name": "Executor"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "hide_phone",
                True,
                lambda: self.strings["no_phone"],
                validator=loader.validators.Boolean()
            ),
        )


    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    async def cexecute(self, code, message, reply):
        client = self.client
        me = await client.get_me()
        reply = await message.get_reply_message()
        functions = {
            "message": message,
            "client": self._client,
            "reply": reply,
            "r": reply,
            "event": message,
            "chat": message.to_id,
            "me": me,
            "herokutl": herokutl,
            "telethon": herokutl,
            "utils": utils,
            "loader": loader,
            "f": herokutl.tl.functions,
            "c": self._client,
            "m": message,
            "lookup": self.lookup,
            "self": self,
            "db": self.db,
        }
        result = sys.stdout = StringIO()
        try:
            res = await meval(
                code,
                globals(),
                **functions,
            )
        except:
            return traceback.format_exc().strip(), None, True
        return result.getvalue().strip(), res, False

    @loader.command()
    async def execcmd(self, message):
        """Выполнить python код"""

        code = utils.get_args_raw(message)
        if not code:
            return await utils.answer(message, self.strings["no_code"].format(self.get_prefix()))

        await utils.answer(message, self.strings["executing"])

        reply = await message.get_reply_message()

        start_time = time.perf_counter()
        result, res, cerr = await self.cexecute(code, message, reply)
        stop_time = time.perf_counter()

        me = await self.client.get_me()

        result = str(result)
        res = str(res)

        if self.config['hide_phone']:
            t_h = "never gonna give you up"

            if result:
                result = result.replace("+"+me.phone, t_h).replace(me.phone, t_h)
            if res:
                res = res.replace("+"+me.phone, t_h).replace(me.phone, t_h)

        if result:
            if not cerr:
                result = self.strings["result_no_error"].format(result=result)
            else:
                result = self.strings["result_error"].format(result=result)

        if res or res == 0 or res == False and res is not None:
            result += self.strings["res_return"].format(res=res)

        return await utils.answer(message, self.strings["result"].format(code=code, result=result, time=round(stop_time - start_time, 5)))