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
import contextlib
import logging
import os
import re
import time
import typing
import signal

import herokutl

from .. import loader, utils

logger = logging.getLogger(__name__)

BANNER_OK = "https://x0.at/grz4.jpg"
BANNER_BAD = "https://x0.at/4AAH.jpg"


def hash_msg(message):
    return f"{str(utils.get_chat_id(message))}/{str(message.id)}"


async def read_stream(func: callable, stream, delay: float):
    last_task = None
    data = b""
    while True:
        dat = await stream.read(1)

        if not dat:
            # EOF
            if last_task:
                # Send all pending data
                last_task.cancel()
                await func(data.decode())
                # If there is no last task there is inherently no data, so theres no point sending a blank string
            break

        data += dat

        if last_task:
            last_task.cancel()

        last_task = asyncio.ensure_future(sleep_for_task(func, data, delay))


async def sleep_for_task(func: callable, data: bytes, delay: float):
    await asyncio.sleep(delay)
    await func(data.decode())


class MessageEditor:
    def __init__(
        self,
        message: herokutl.tl.types.Message,
        command: str,
        config,
        strings,
        request_message,
    ):
        self.message = message
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.redraws = 0
        self.config = config
        self.strings = strings
        self.request_message = request_message
        self.start_time = time.time()

    async def update_stdout(self, stdout):
        self.stdout = stdout
        await self.redraw()

    async def update_stderr(self, stderr):
        self.stderr = stderr
        await self.redraw()

    async def redraw(self):
        text = self.strings("running").format(utils.escape_html(self.command))  # fmt: skip

        if self.rc is not None:
            text += self.strings("finished").format(utils.escape_html(str(self.rc)))

        text += self.strings("stdout")
        text += utils.escape_html(self.stdout[max(len(self.stdout) - 2048, 0) :])
        stderr = utils.escape_html(self.stderr[max(len(self.stderr) - 1024, 0) :])
        text += (self.strings("stderr") + stderr) if stderr else ""
        text += self.strings("end")

        if self.rc is not None:
            exec_time = time.time() - self.start_time
            text += self.strings["time_exec"].format(round(exec_time, 2))

        with contextlib.suppress(herokutl.errors.rpcerrorlist.MessageNotModifiedError):
            try:
                self.message = await utils.answer(self.message, text)
            except herokutl.errors.rpcerrorlist.MessageTooLongError as e:
                logger.error(e)
                logger.error(text)
        # The message is never empty due to the template header

    async def cmd_ended(self, rc):
        self.rc = rc
        self.state = 4
        await self.redraw()

    def update_process(self, process):
        pass


class SudoMessageEditor(MessageEditor):
    PASS_REQ = ["[sudo] password for", "[sudo] пароль для"]
    WRONG_PASS = [
        r"\[sudo\] password for (.*): Sorry, try again\.",
        r"\[sudo\] пароль для (.*): Попробуйте еще раз.\.",
    ]
    TOO_MANY_TRIES = [r"\[sudo\] password for (.*): sudo: [0-9]+ incorrect password attempts", r"\[sudo\] пароль для (.*): sudo: [0-9]+ неверные попытки ввода пароля"]  # fmt: skip

    def __init__(self, message, command, config, strings, request_message):
        super().__init__(message, command, config, strings, request_message)
        self.process = None
        self.state = 0
        self.authmsg = None

    def update_process(self, process):
        logger.debug("got sproc obj %s", process)
        self.process = process

    async def update_stderr(self, stderr):
        logger.debug("stderr update " + stderr)
        self.stderr = stderr
        lines = stderr.strip().split("\n")
        lastline = lines[-1]
        lastlines = lastline.rsplit(" ", 1)
        handled = False

        if (
            len(lines) > 1
            and any(re.fullmatch(i, lines[-2]) for i in self.WRONG_PASS)
            and any(lastlines[0] == i for i in self.PASS_REQ)
            and self.state == 1
        ):
            logger.debug("switching state to 0")
            await utils.answer(self.message, self.strings("auth_fail"))

            self.state = 0
            handled = True
            await asyncio.sleep(2)
            if self.authmsg:
                await self.authmsg.delete()

        if any(lastlines[0] == i for i in self.PASS_REQ) and self.state == 0:
            logger.debug("Success to find sudo log!")
            text = self.strings("auth_needed").format(self.message.client.heroku_me.id)

            try:
                await utils.answer(self.message, text)
            except herokutl.errors.rpcerrorlist.MessageNotModifiedError as e:
                logger.debug(e)

            logger.debug("edited message with link to self")
            command = "<code>" + utils.escape_html(self.command) + "</code>"
            user = utils.escape_html(lastlines[1][:-1])

            self.authmsg = await self.message.client.send_message(
                "me",
                self.strings("auth_msg").format(command, user),
            )
            logger.debug("sent message to self")

            self.message.client.remove_event_handler(self.on_message_edited)
            self.message.client.add_event_handler(
                self.on_message_edited,
                herokutl.events.messageedited.MessageEdited(chats=["me"]),
            )

            logger.debug("registered handler")
            handled = True

        if len(lines) > 1 and (
            any(re.fullmatch(i, lastline) for i in self.TOO_MANY_TRIES)
            and self.state in {1, 3, 4}
        ):
            logger.debug("password wrong lots of times")
            await utils.answer(self.message, self.strings("auth_locked"))
            await self.authmsg.delete()
            self.state = 2
            handled = True

        if not handled:
            logger.debug("Didn't find sudo log.")
            if self.authmsg is not None:
                await self.authmsg.delete()
                self.authmsg = None
            self.state = 2
            await self.redraw()

        logger.debug(self.state)

    async def update_stdout(self, stdout):
        self.stdout = stdout

        if self.state != 2:
            self.state = 3  # Means that we got stdout only

        if self.authmsg is not None:
            await self.authmsg.delete()
            self.authmsg = None

        await self.redraw()

    async def on_message_edited(self, message):
        # Message contains sensitive information.
        if self.authmsg is None:
            return

        logger.debug("got message edit update in self %s", str(message.id))

        if hash_msg(message) == hash_msg(self.authmsg):
            # The user has provided interactive authentication. Send password to stdin for sudo.
            try:
                self.authmsg = await utils.answer(message, self.strings("auth_ongoing"))
            except herokutl.errors.rpcerrorlist.MessageNotModifiedError:
                # Try to clear personal info if the edit fails
                await message.delete()

            self.state = 1
            self.process.stdin.write(
                message.message.message.split("\n", 1)[0].encode() + b"\n"
            )


class RawMessageEditor(SudoMessageEditor):
    def __init__(
        self,
        message,
        command,
        config,
        strings,
        request_message,
        show_done=False,
    ):
        super().__init__(message, command, config, strings, request_message)
        self.show_done = show_done

    async def redraw(self):
        logger.debug(self.rc)

        match self.rc:
            case None:
                text = (
                    "<code>"
                    + utils.escape_html(self.stdout[max(len(self.stdout) - 4095, 0) :])
                    + "</code>"
                )
            case 0:
                text = (
                    "<code>"
                    + utils.escape_html(self.stdout[max(len(self.stdout) - 4090, 0) :])
                    + "</code>"
                )
            case _:
                text = (
                    "<code>"
                    + utils.escape_html(self.stderr[max(len(self.stderr) - 4095, 0) :])
                    + "</code>"
                )

        if self.rc is not None and self.show_done:
            text += "\n" + self.strings("done")

        logger.debug(text)

        with contextlib.suppress(
            herokutl.errors.rpcerrorlist.MessageNotModifiedError,
            herokutl.errors.rpcerrorlist.MessageEmptyError,
            ValueError,
        ):
            try:
                await utils.answer(self.message, text)
            except herokutl.errors.rpcerrorlist.MessageTooLongError as e:
                logger.error(e)
                logger.error(text)


class InlineMessageEditor:
    """Streams command output into an inline form via form.edit()"""

    def __init__(self, form, command: str, strings, config, reply_markup=None):
        self.form = form
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.strings = strings
        self.config = config
        self.reply_markup = reply_markup
        self.start_time = time.time()
        self.process = None

    def reset(self, command: str):
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.start_time = time.time()
        self.process = None

    def update_process(self, process):
        self.process = process

    async def update_stdout(self, stdout):
        self.stdout = stdout
        await self.redraw()

    async def update_stderr(self, stderr):
        self.stderr = stderr
        await self.redraw()

    async def redraw(self):
        text = self.strings("running").format(utils.escape_html(self.command))

        if self.rc is not None:
            text += self.strings("finished").format(utils.escape_html(str(self.rc)))

        text += self.strings("stdout")
        text += utils.escape_html(self.stdout[max(len(self.stdout) - 2048, 0) :])
        stderr = utils.escape_html(self.stderr[max(len(self.stderr) - 1024, 0) :])
        text += (self.strings("stderr") + stderr) if stderr else ""
        text += self.strings("end")

        if self.rc is not None:
            exec_time = time.time() - self.start_time
            text += self.strings["time_exec"].format(round(exec_time, 2))

        reply_markup = (
            self.reply_markup(self)
            if callable(self.reply_markup)
            else self.reply_markup
        )

        with contextlib.suppress(Exception):
            await self.form.edit(text, reply_markup=reply_markup)

    async def cmd_ended(self, rc):
        self.rc = rc
        await self.redraw()


@loader.tds
class TerminalMod(loader.Module):
    """Runs commands"""

    strings = {"name": "Terminal"}

    DANGEROUS_COMMANDS = [
        r"rm\s+.*\s+\/\s*\*?",
        r"rm\s+.*\s+\/etc\/",
        r"rm\s+.*\s+\/dev\/",
        r"rm\s+.*\s+\/boot\/",
        r"rm\s+.*\s+\/root\/",
        r"rm\s+.*\s+\/sys\/",
        r"rm\s+.*\s+\/proc\/",
        r"dd\s+.*if=.*of=/dev/",
        r"mkfs\.",
        r"fdisk\s+\/dev/",
        r"\\x72\\x6d\\x20\\x2d\\x72\\x66\\x20\\x2f",
        r"which\s+rm",
        r"chmod\s+.*000\s+.*\/",
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:",
        r"cat\s+.*\/dev\/urandom\s+>\s+\/dev\/[hsv]d[a-z]",
        r"ln\s+.*-s\s+\/\s+\/dev\/null",
        r"echo\s+[\"']?[A-Za-z0-9+/=]{20,}[\"']?\s*\|\s*base64\s+-d\s*\|\s*(sh|bash|zsh)",
        r"base64\s+-d\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"echo\s+.+\|\s*base64\s+--decode\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"curl\s+.*\|\s*(sh|bash|zsh|dash|ksh)",
        r"wget\s+.*-O\s*-\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"curl\s+.*-o\s*/etc/",
        r"wget\s+.*-O\s*/etc/",
        r"mv\s+.*\s+/etc/passwd",
        r"mv\s+.*\s+/etc/shadow",
        r">\s*/etc/passwd",
        r">\s*/etc/shadow",
        r"nc\s+.*-e\s+(sh|bash|zsh)",
        r"ncat\s+.*-e\s+(sh|bash|zsh)",
        r"python[23]?\s+-c\s+[\"']import\s+os",
        r"python[23]?\s+-c\s+[\"']import\s+socket",
        r"perl\s+-e\s+[\"']use\s+Socket",
        r"php\s+-r\s+[\"'].*exec\(",
        r"openssl\s+s_client.*\|\s*(sh|bash)",
        r"socat\s+.*exec:",
        r"chmod\s+[0-9]*[s][0-9]*\s+",
        r"chown\s+root\s+",
        r"sudo\s+su\b",
        r"sudo\s+-s\b",
        r"passwd\s+root",
        r"userdel\s+",
        r"usermod\s+.*-G\s+.*sudo",
        r"visudo",
        r"systemctl\s+disable\s+",
        r"systemctl\s+stop\s+",
        r"init\s+0",
        r"init\s+6",
        r"shutdown",
        r"reboot",
        r"halt",
        r"poweroff",
        r"killall\s+-9",
        r"kill\s+-9\s+1\b",
        r"truncate\s+-s\s+0\s+/etc/",
        r"shred\s+",
        r"wipe\s+",
    ]

    def _is_dangerous(self, cmd: str) -> bool:
        """Return True if the command matches any banned pattern."""
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "FLOOD_WAIT_PROTECT",
                2,
                lambda: self.strings("fw_protect"),
                validator=loader.validators.Integer(minimum=0),
            ),
        )
        self.activecmds = {}
        self._inline_pending: typing.Dict[str, str] = {}
        self._inline_sessions: typing.Dict[str, InlineMessageEditor] = {}

    def _build_inline_exec_markup(
        self,
        uid: typing.Optional[str] = None,
    ) -> typing.List[typing.List[typing.Dict[str, str]]]:
        if not uid:
            return []

        return [
            [
                {
                    "text": self.strings("btn_execute"),
                    "data": f"terminal/exec/{uid}",
                }
            ]
        ]

    def _build_inline_continue_markup(
        self,
        editor: InlineMessageEditor,
        session_uid: str,
    ) -> typing.List[typing.List[typing.Dict[str, typing.Any]]]:
        if editor.rc is None:
            return []

        return [
            [
                {
                    "text": self.strings("btn_continue"),
                    "input": self.strings("btn_continue"),
                    "handler": self.inline__continue_input,
                    "args": (session_uid,),
                }
            ]
        ]

    def _register_inline_session(self, session_uid: str, inline_message_id: str):
        self.inline._units[session_uid] = {
            "type": "form",
            "text": self.strings("exec_running"),
            "buttons": [],
            "caller": None,
            "chat": None,
            "message_id": None,
            "top_msg_id": None,
            "uid": session_uid,
            "inline_message_id": inline_message_id,
        }

    @loader.command(alias="exec")
    async def terminalcmd(self, message):
        user_command = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not user_command and reply and reply.text:
            user_command = reply.message

        if self._is_dangerous(user_command):
            await utils.answer(
                message,
                self.strings("dangerous_command").format(
                    utils.escape_html(user_command)
                ),
            )
            return

        await self.run_command(message, user_command)

    @loader.inline_handler()
    async def exec_inline_handler(self, query):
        """Execute terminal command via inline"""
        from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

        raw = query.query.strip()
        if raw.lower().startswith("exec"):
            raw = raw[4:].strip()

        # Truncate command preview to 15 characters for display
        def short_cmd(cmd: str) -> str:
            return cmd[:15] + "..." if len(cmd) > 15 else cmd

        if not raw:
            await self.inline.bot.answer_inline_query(
                inline_query_id=query.id,
                results=[
                    InlineQueryResultArticle(
                        id="hint",
                        title=self.strings("inline_hint"),
                        description=self.strings("inline_hint_desc"),
                        input_message_content=InputTextMessageContent(
                            message_text=self.strings("inline_hint"),
                            parse_mode="HTML",
                        ),
                        thumbnail_url=BANNER_OK,
                        thumbnail_width=640,
                        thumbnail_height=640,
                    )
                ],
                cache_time=0,
                is_personal=True,
            )
            return

        if self._is_dangerous(raw):
            await self.inline.bot.answer_inline_query(
                inline_query_id=query.id,
                results=[
                    InlineQueryResultArticle(
                        id="dangerous",
                        title=self.strings("inline_hint"),
                        description=short_cmd(raw),
                        input_message_content=InputTextMessageContent(
                            message_text=self.strings("dangerous_command").format(
                                utils.escape_html(raw)
                            ),
                            parse_mode="HTML",
                        ),
                        thumbnail_url=BANNER_BAD,
                        thumbnail_width=640,
                        thumbnail_height=640,
                    )
                ],
                cache_time=0,
                is_personal=True,
            )
            return

        uid = utils.rand(8)
        self._inline_pending[uid] = raw

        await self.inline.bot.answer_inline_query(
            inline_query_id=query.id,
            results=[
                InlineQueryResultArticle(
                    id=uid,
                    title=self.strings("inline_hint"),
                    description=short_cmd(raw),
                    input_message_content=InputTextMessageContent(
                        message_text=self.strings("exec_confirm").format(
                            utils.escape_html(raw)
                        ),
                        parse_mode="HTML",
                    ),
                    thumbnail_url=BANNER_OK,
                    thumbnail_width=640,
                    thumbnail_height=640,
                    reply_markup=self.inline.generate_markup(
                        self._build_inline_exec_markup(uid)
                    ),
                )
            ],
            cache_time=0,
            is_personal=True,
        )

    @loader.callback_handler()
    async def exec_callback(self, call):
        if not call.data.startswith("terminal/exec/"):
            return

        uid = call.data.split("/")[2]
        cmd = self._inline_pending.pop(uid, None)

        if not cmd:
            await call.answer("Command not found or already executed", show_alert=True)
            return

        if self._is_dangerous(cmd):
            await call.answer(
                self.strings("dangerous_command").format(cmd),
                show_alert=True,
            )
            return

        self._register_inline_session(uid, call.inline_message_id)

        from ..inline.types import InlineMessage

        form = InlineMessage(
            inline_manager=self.inline,
            unit_id=uid,
            inline_message_id=call.inline_message_id,
        )

        await form.edit(self.strings("exec_running"))

        editor = InlineMessageEditor(
            form=form,
            command=cmd,
            strings=self.strings,
            config=self.config,
            reply_markup=lambda current_editor: self._build_inline_continue_markup(
                current_editor,
                uid,
            ),
        )
        self._inline_sessions[uid] = editor

        asyncio.ensure_future(self._run_inline(cmd, editor))

    async def inline__continue_input(self, call, query: str, session_uid: str):
        editor = self._inline_sessions.get(session_uid)

        if not editor:
            return

        query = query.strip()
        if not query:
            return

        cmd = f"{editor.command} {query}".strip()

        if self._is_dangerous(cmd):
            await editor.form.edit(
                self.strings("dangerous_command").format(utils.escape_html(cmd)),
                reply_markup=self._build_inline_continue_markup(editor, session_uid),
            )
            return

        editor.reset(cmd)
        await editor.form.edit(self.strings("exec_running"))
        asyncio.ensure_future(self._run_inline(cmd, editor))

    async def _run_inline(self, cmd: str, editor: InlineMessageEditor):
        shell = os.environ.get("SHELL", "/bin/sh")

        try:
            sproc = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=utils.get_base_dir(),
                preexec_fn=os.setsid,
            )
        except Exception as e:
            with contextlib.suppress(Exception):
                await editor.form.edit(
                    self.strings("exec_error").format(utils.escape_html(str(e)))
                )
            return

        editor.update_process(sproc)
        await editor.redraw()

        await asyncio.gather(
            read_stream(
                editor.update_stdout,
                sproc.stdout,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
            read_stream(
                editor.update_stderr,
                sproc.stderr,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
        )

        await editor.cmd_ended(await sproc.wait())

    async def run_command(
        self,
        message: herokutl.tl.types.Message,
        cmd: str,
        editor: typing.Optional[MessageEditor] = None,
    ):

        if self._is_dangerous(cmd):
            await utils.answer(
                message,
                self.strings("dangerous_command").format(utils.escape_html(cmd)),
            )
            return

        shell = os.environ.get("SHELL", "/bin/sh")

        try:
            sproc = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=utils.get_base_dir(),
                preexec_fn=os.setsid,
            )
        except Exception as e:
            await utils.answer(
                message,
                self.strings("exec_error").format(utils.escape_html(str(e))),
            )
            return

        if editor is None:
            editor = SudoMessageEditor(message, cmd, self.config, self.strings, message)

        editor.update_process(sproc)

        self.activecmds[hash_msg(message)] = sproc

        await editor.redraw()

        await asyncio.gather(
            read_stream(
                editor.update_stdout,
                sproc.stdout,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
            read_stream(
                editor.update_stderr,
                sproc.stderr,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
        )

        await editor.cmd_ended(await sproc.wait())
        del self.activecmds[hash_msg(message)]

    @loader.command()
    async def terminatecmd(self, message):
        if not message.is_reply:
            await utils.answer(message, self.strings("what_to_kill"))
            return

        if hash_msg(await message.get_reply_message()) in self.activecmds:
            try:
                kill_pids = self.activecmds[hash_msg(await message.get_reply_message())]
                if "-f" not in utils.get_args_raw(message):
                    os.killpg(kill_pids.pid, signal.SIGTERM)
                else:
                    os.killpg(kill_pids.pid, signal.SIGKILL)
            except Exception:
                logger.exception("Killing process failed")
                await utils.answer(message, self.strings("kill_fail"))
            else:
                await utils.answer(message, self.strings("killed"))
        else:
            await utils.answer(message, self.strings("no_cmd"))
