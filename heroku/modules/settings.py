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

import contextlib
import herokutl
from herokutl.tl.types import Message, User

from .. import loader, main, utils, version
from ..inline.types import InlineCall


@loader.tds
class CoreMod(loader.Module):
    """Control core userbot settings"""

    strings = {"name": "Settings"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "allow_nonstandart_prefixes",
                False,
                "Allow non-standard prefixes like premium emojis or multi-symbol prefixes",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "alias_emoji",
                "<tg-emoji emoji-id=4974259868996207180>▪️</tg-emoji>",
                "just emoji in .aliases",
            ),
        )

    async def client_ready(self):
        self._markup = utils.chunks(
            [
                {
                    "text": self.strings[platform],
                    "callback": self._inline__choose__installation,
                    "args": (platform,),
                }
                for platform in [
                    "vds",
                    "wsl",
                    "userland",
                    "hikkahost",
                    "lavhost",
                ]
            ],
            2,
        )

    async def blacklistcommon(self, message: Message):
        args = utils.get_args(message)

        if len(args) > 2:
            await utils.answer(message, self.strings["too_many_args"])
            return

        chatid = None
        module = None

        if args:
            try:
                chatid = int(args[0])
            except ValueError:
                module = args[0]

        if len(args) == 2:
            module = args[1]

        if chatid is None:
            chatid = utils.get_chat_id(message)

        module = self.allmodules.get_classname(module)
        return f"{str(chatid)}.{module}" if module else chatid

    @loader.command(
        ru_doc="Информация о Хероку",
        en_doc="Information of Heroku",
        ua_doc="Інформація про Хероку",
        de_doc="Informationen über Heroku",
    )
    async def herokucmd(self, message: Message):

        branch_text = ""
        if version.branch == "master":
            branch_text = ""
        elif version.branch == "beta" or self.tg_id in [
            1714120111,
            1226061708,
            5717135725,
        ]:
            branch_text = self.strings["happy_beta"].format(version.branch)
        else:
            branch_text = self.strings["unstable"].format(version.branch)

        await utils.answer(
            message,
            self.strings["heroku"].format(
                (
                    utils.get_platform_emoji()
                    if self._client.heroku_me.premium
                    else "🪐 <b>Heroku userbot</b>"
                ),
                *version.__version__,
                utils.get_commit_url(),
                f"{herokutl.__version__} #{herokutl.tl.alltlobjects.LAYER}",
            )
            + (branch_text),
            file="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/heroku_cmd.png",
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command()
    async def blacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            self._db.get(main.__name__, "blacklist_chats", []) + [chatid],
        )

        await utils.answer(message, self.strings["blacklisted"].format(chatid))

    @loader.command()
    async def unblacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            list(set(self._db.get(main.__name__, "blacklist_chats", [])) - {chatid}),
        )

        await utils.answer(message, self.strings["unblacklisted"].format(chatid))

    async def getuser(self, message: Message):
        try:
            return int(utils.get_args(message)[0])
        except (ValueError, IndexError):
            if reply := await message.get_reply_message():
                return reply.sender_id

            return message.to_id.user_id if message.is_private else False

    @loader.command()
    async def blacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_blacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            self._db.get(main.__name__, "blacklist_users", []) + [user],
        )

        await utils.answer(message, self.strings["user_blacklisted"].format(user))

    @loader.command()
    async def unblacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_unblacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            list(set(self._db.get(main.__name__, "blacklist_users", [])) - {user}),
        )

        await utils.answer(
            message,
            self.strings["user_unblacklisted"].format(user),
        )

    @loader.command()
    async def setprefix(self, message: Message):
        if not (args := utils.get_args(message)):
            await utils.answer(message, self.strings["what_prefix"])
            return

        if len(args[0]) != 1 and self.config.get("allow_nonstandart_prefixes") is False:
            await utils.answer(message, self.strings["prefix_incorrect"])
            return

        if args[0] == "s":
            await utils.answer(message, self.strings["prefix_incorrect"])
            return

        if len(args) == 2:
            if args[1].isdigit():
                args[1] = int(args[1])
            try:
                entity = await self.client.get_entity(args[1])
            except:
                return await utils.answer(
                    message, self.strings["invalid_id_or_username"]
                )

            if not isinstance(entity, User):
                return await utils.answer(
                    message, self.strings["not_a_user"].format(args[1])
                )

            if entity.id != self.tg_id:
                sgroup_users = []
                for g in self._client.dispatcher.security._sgroups.values():
                    for u in g.users:
                        sgroup_users.append(u)

                tsec_users = [
                    rule["target"]
                    for rule in self._client.dispatcher.security._tsec_user
                ]
                ub_owners = self._client.dispatcher.security.owner.copy()

                all_users = sgroup_users + tsec_users + ub_owners

                if entity.id not in all_users:
                    return await utils.answer(
                        message, self.strings["id_not_found_scgroup"]
                    )

                oldprefix = utils.escape_html(self.get_prefix(entity.id))
                all_prefixes = self._db.get(
                    main.__name__,
                    "command_prefixes",
                    {},
                )

                all_prefixes[str(entity.id)] = args[0]

                self._db.set(
                    main.__name__,
                    "command_prefixes",
                    all_prefixes,
                )
                return await utils.answer(
                    message,
                    self.strings["entity_prefix_set"].format(
                        "<tg-emoji emoji-id=5197474765387864959>👍</tg-emoji>",
                        entity_name=utils.escape_html(entity.first_name),
                        newprefix=utils.escape_html(args[0]),
                        oldprefix=utils.escape_html(oldprefix),
                        entity_id=args[1],
                    ),
                )

        oldprefix = utils.escape_html(self.get_prefix())

        self._db.set(
            main.__name__,
            "command_prefix",
            args[0],
        )
        await utils.answer(
            message,
            self.strings["prefix_set"].format(
                "<tg-emoji emoji-id=5197474765387864959>👍</tg-emoji>",
                newprefix=utils.escape_html(args[0]),
                oldprefix=utils.escape_html(oldprefix),
            ),
        )

    @loader.command()
    async def aliases(self, message: Message):
        await utils.answer(
            message,
            self.strings["aliases"]
            + "<blockquote expandable>"
            + "\n".join(
                [
                    (self.config["alias_emoji"] + f" <code>{i}</code> &lt;- {y}")
                    for i, y in self.allmodules.aliases.items()
                ]
            )
            + "</blockquote>",
        )

    @loader.command()
    async def addalias(self, message: Message):

        args_raw = utils.get_args_raw(message)
        if not args_raw:
            await utils.answer(message, self.strings["alias_args"])
            return

        alias_lines = []
        for line in args_raw.splitlines():
            line = line.strip()
            if not line:
                continue

            if "," in line:
                parts = [part.strip() for part in line.split(",")]
                last = parts[-1].split(maxsplit=1)
                if len(last) < 2:
                    await utils.answer(message, self.strings["alias_args"])
                    return

                aliases = [part.lower() for part in parts[:-1] if part]
                aliases.append(last[0].lower())
                command = last[1]
            else:
                args = line.split(maxsplit=1)
                if len(args) < 2:
                    await utils.answer(message, self.strings["alias_args"])
                    return

                aliases = [args[0].lower()]
                command = args[1]

            command_parts = command.split(maxsplit=1)
            cmd = command_parts[0]
            rest = command_parts[1] if len(command_parts) > 1 else None

            if cmd not in self.allmodules.commands:
                await utils.answer(
                    message,
                    self.strings["no_command"].format(utils.escape_html(cmd)),
                )
                return

            alias_lines.append((aliases, cmd, rest))

        if not alias_lines:
            await utils.answer(message, self.strings["alias_args"])
            return

        added_lines = []
        skipped_lines = []
        planned_aliases = {}
        stored_aliases = {**self.get("aliases", {})}

        for aliases, cmd, rest in alias_lines:
            target = f"{cmd} {rest}" if rest else cmd
            added_aliases = []

            for alias in aliases:
                if alias in self.allmodules.aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(self.allmodules.aliases[alias]),
                        )
                    )
                    continue

                if alias in planned_aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(planned_aliases[alias]),
                        )
                    )
                    continue

                if not self.allmodules.add_alias(alias, cmd, rest):
                    await utils.answer(
                        message,
                        self.strings["no_command"].format(utils.escape_html(cmd)),
                    )
                    return

                stored_aliases[alias] = target
                planned_aliases[alias] = target
                added_aliases.append(alias)

            if added_aliases:
                added_lines.append((added_aliases, target))

        if added_lines:
            self.set("aliases", stored_aliases)

        if len(added_lines) == 1 and len(added_lines[0][0]) == 1 and not skipped_lines:
            await utils.answer(
                message,
                self.strings["alias_created"].format(
                    utils.escape_html(added_lines[0][0][0])
                ),
            )
            return

        added_count = sum(len(aliases) for aliases, _ in added_lines)
        response = []

        if added_lines:
            response.append(
                self.strings["aliases_created"].format(
                    count=added_count,
                    aliases="\n".join(
                        self.strings["aliases_created_line"].format(
                            aliases=utils.escape_html(", ".join(aliases)),
                            command=utils.escape_html(target),
                        )
                        for aliases, target in added_lines
                    ),
                )
            )

        response.extend(skipped_lines)

        await utils.answer(message, "\n\n".join(response))

    @loader.command()
    async def delalias(self, message: Message):
        args_raw = utils.get_args_raw(message)

        if not args_raw:
            await utils.answer(message, self.strings["delalias_args"])
            return

        if args_raw.strip() in {"-c", "--clear"}:
            self.allmodules.aliases.clear()
            self.set("aliases", {})
            await utils.answer(message, self.strings["aliases_cleared"])
            return

        aliases = []
        seen_aliases = set()
        for line in args_raw.splitlines():
            for alias in line.split(","):
                alias = alias.lower().strip()
                if alias and alias not in seen_aliases:
                    aliases.append(alias)
                    seen_aliases.add(alias)

        if not aliases:
            await utils.answer(message, self.strings["delalias_args"])
            return

        current = self.get("aliases", {})
        removed_aliases = []
        missed_aliases = []

        for alias in aliases:
            if not self.allmodules.remove_alias(alias):
                missed_aliases.append(alias)
                continue

            current.pop(alias, None)
            removed_aliases.append(alias)

        if removed_aliases:
            self.set("aliases", current)

        if len(removed_aliases) == 1 and not missed_aliases:
            await utils.answer(
                message,
                self.strings["alias_removed"].format(
                    utils.escape_html(removed_aliases[0])
                ),
            )
            return

        response = []
        if removed_aliases:
            response.append(
                self.strings["aliases_removed"].format(
                    count=len(removed_aliases),
                    aliases=utils.escape_html(", ".join(removed_aliases)),
                )
            )

        response.extend(
            self.strings["no_alias"].format(utils.escape_html(alias))
            for alias in missed_aliases
        )

        await utils.answer(
            message,
            "\n\n".join(response),
        )

    @loader.command()
    async def cleardb(self, message: Message):
        await self.inline.form(
            self.strings["confirm_cleardb"],
            message,
            reply_markup=[
                {
                    "text": self.strings["cleardb_confirm"],
                    "callback": self._inline__cleardb,
                },
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
            ],
        )

    async def _inline__cleardb(self, call: InlineCall):
        self._db.clear()
        self._db.save()
        await utils.answer(call, self.strings["db_cleared"])

    @loader.command()
    async def togglecmdcmd(self, message: Message):
        """Toggle disable specific command of a module: togglecmd <module> <command> or togglecmd <command>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tcc"])

        if args and len(args) >= 2:
            mod_arg, cmd = args[0], args[1]
            mod_inst = self.allmodules.lookup(mod_arg)
            if not mod_inst:
                await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        current = [x for x in disabled_commands.get(module_key, [])]

        if cmd.lower() not in [c.lower() for c in mod_inst.heroku_commands.keys()]:
            await utils.answer(message, self.strings["cmd404"])

        if any(c.lower() == cmd.lower() for c in current):
            current = [c for c in current if c.lower() != cmd.lower()]
            if current:
                disabled_commands[module_key] = current
            else:
                disabled_commands.pop(module_key, None)

            self._db.set(main.__name__, "disabled_commands", disabled_commands)
            try:
                self.allmodules.register_commands(mod_inst)
            except Exception:
                pass

            await utils.answer(
                message, self.strings["cmd_enabled"].format(cmd, module_key)
            )
        else:
            current.append(cmd)
            disabled_commands[module_key] = current
            self._db.set(main.__name__, "disabled_commands", disabled_commands)

            try:
                self.allmodules.commands.pop(cmd.lower(), None)
            except Exception:
                pass

            for alias, target in list(self.allmodules.aliases.items()):
                if target.split()[0].lower() == cmd.lower():
                    self.allmodules.aliases.pop(alias, None)

            await utils.answer(
                message, self.strings["cmd_disabled"].format(cmd, module_key)
            )

    @loader.command()
    async def togglemod(self, message: Message):
        """Toggle disable entire module: togglemod <module>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if not mod_inst:
            await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__
        disabled = self._db.get(main.__name__, "disabled_modules", [])

        if module_key in disabled:
            disabled = [m for m in disabled if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.register_commands(mod_inst)
                self.allmodules.register_watchers(mod_inst)
                self.allmodules.register_raw_handlers(mod_inst)
                self.allmodules.register_inline_stuff(mod_inst)
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_enabled"].format(module_key))
        else:
            disabled += [module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.unregister_commands(mod_inst, "disable")
                self.allmodules.unregister_watchers(mod_inst, "disable")
                self.allmodules.unregister_raw_handlers(mod_inst, "disable")
                self.allmodules.unregister_inline_stuff(mod_inst, "disable")
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_disabled"].format(module_key))

    @loader.command()
    async def clearmodule(self, message: Message):
        """Clear all DB entries for module: clearmodule <module>"""
        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["wrong_usage_cmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if mod_inst:
            module_key = mod_inst.__class__.__name__
        else:
            module_key = mod_arg

        if module_key in self._db:
            try:
                del self._db[module_key]
                self._db.save()
            except Exception:
                pass

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        disabled_commands.pop(module_key, None)
        self._db.set(main.__name__, "disabled_commands", disabled_commands)

        disabled_modules = self._db.get(main.__name__, "disabled_modules", [])
        if module_key in disabled_modules:
            disabled_modules = [m for m in disabled_modules if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled_modules)

        await utils.answer(message, self.strings["cmc_done"].format(mod_arg))

    async def installationcmd(self, message: Message):
        """| Guide of installation"""

        args = utils.get_args_raw(message)

        if (
            not args or args not in {"-vds", "-wsl", "-ul", "-jh", "-hh", "-lh"}
        ) and not (
            await self.inline.form(
                self.strings["choose_installation"],
                message,
                reply_markup=self._markup,
                photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/heroku_installation.png",
            )
        ):

            await self.client.send_file(
                message.peer_id,
                "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/heroku_installation.png",
                caption=self.strings["vds_install"],
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
        match True:
            case _ if "-vds" in args:
                await utils.answer(message, self.strings["vds_install"])
            case _ if "-wsl" in args:
                await utils.answer(message, self.strings["wsl_install"])
            case _ if "-ul" in args:
                await utils.answer(message, self.strings["userland_install"])
            case _ if "-hh" in args:
                await utils.answer(message, self.strings["hikkahost_install"])
            case _ if "-lh" in args:
                await utils.answer(message, self.strings["lavhost_install"])

    async def _inline__choose__installation(self, call: InlineCall, platform: str):
        with contextlib.suppress(Exception):
            await utils.answer(
                call,
                self.strings[f"{platform}_install"],
                reply_markup=self._markup,
            )
