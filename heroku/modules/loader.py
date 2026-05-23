"""Loads and registers modules"""

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

import ast
import asyncio
import contextlib
import difflib
import functools
import importlib
import inspect
import io
import logging
import os
import re
import shutil
import sys
import time
import typing
import uuid
from collections import ChainMap
from importlib.machinery import ModuleSpec
from urllib.parse import urlparse

import requests
from herokutl.errors.common import ScamDetectionError
from herokutl.errors.rpcerrorlist import MediaCaptionTooLongError
from herokutl.tl.functions.channels import JoinChannelRequest
from herokutl.tl.types import Channel, InputMediaWebPage, Message

from .. import loader, main, utils
from .._local_storage import RemoteStorage
from ..compat import geek
from ..inline.types import InlineCall
from ..types import CoreOverwriteError, CoreUnloadError

logger = logging.getLogger(__name__)


class FakeOne:
    def __eq__(self, other):
        return other == -1 or isinstance(other, FakeOne)

    def __bool__(self):
        return False


MODULE_LOADING_FORBIDDEN = FakeOne()
MODULE_LOADING_FAILED = 0
MODULE_LOADING_SUCCESS = 1


class ModuleInstallError(RuntimeError):
    """Raised when an external module install fails after download."""


def _find_forbidden_external_api_usage(code: str) -> typing.Optional[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    sys_aliases = {"sys"}

    def _static_string(node: ast.AST) -> typing.Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = _static_string(node.left)
            right = _static_string(node.right)
            if left is not None and right is not None:
                return left + right

        if isinstance(node, ast.JoinedStr):
            parts: typing.List[str] = []
            for value in node.values:
                if not isinstance(value, ast.Constant) or not isinstance(
                    value.value, str
                ):
                    return None
                parts.append(value.value)
            return "".join(parts)

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and not node.keywords
            and len(node.args) == 1
        ):
            separator = _static_string(node.func.value)
            if separator is None or not isinstance(node.args[0], (ast.List, ast.Tuple)):
                return None

            pieces: typing.List[str] = []
            for elt in node.args[0].elts:
                piece = _static_string(elt)
                if piece is None:
                    return None
                pieces.append(piece)

            return separator.join(pieces)

        return None

    def _static_forbidden_name(node: ast.AST) -> typing.Optional[str]:
        name = _static_string(node)
        if name is None:
            return None

        return {
            "_getframe": "sys._getframe",
            "allmodules": "allmodules",
        }.get(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    sys_aliases.add(alias.asname or alias.name)
                if alias.name == "allmodules":
                    return "allmodules"
            continue

        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if node.module == "sys" and alias.name == "_getframe":
                    return "sys._getframe"
                if alias.name == "allmodules":
                    return "allmodules"

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "allmodules":
            return "allmodules"

        if isinstance(node, ast.Attribute) and node.attr == "allmodules":
            return "allmodules"

        if isinstance(node, ast.Attribute) and node.attr == "_getframe":
            if not isinstance(node.value, ast.Name) or node.value.id in sys_aliases:
                return "sys._getframe"

        func = node.func if isinstance(node, ast.Call) else None

        if isinstance(node, ast.Call):
            if (
                isinstance(func, ast.Name)
                and func.id == "getattr"
                or isinstance(func, ast.Attribute)
                and func.attr == "getattr"
            ) and len(node.args) >= 2:
                forbidden_name = _static_forbidden_name(node.args[1])
                if forbidden_name:
                    return forbidden_name

            if (
                isinstance(func, ast.Name)
                and func.id == "attrgetter"
                or isinstance(func, ast.Attribute)
                and func.attr == "attrgetter"
            ) and node.args:
                for arg in node.args:
                    forbidden_name = _static_forbidden_name(arg)
                    if forbidden_name:
                        return forbidden_name

            if (
                isinstance(func, ast.Attribute)
                and func.attr in {"__getattribute__", "__getattr__"}
                and node.args
            ):
                attr_args = (
                    node.args[:2] if func.attr == "__getattribute__" else node.args[:1]
                )
                for attr_arg in attr_args:
                    forbidden_name = _static_forbidden_name(attr_arg)
                    if forbidden_name:
                        return forbidden_name

            if (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and node.args
                and (
                    isinstance(func.value, ast.Attribute)
                    and func.value.attr == "__dict__"
                    or isinstance(func.value, ast.Call)
                    and isinstance(func.value.func, ast.Name)
                    and func.value.func.id == "vars"
                )
            ):
                forbidden_name = _static_forbidden_name(node.args[0])
                if forbidden_name:
                    return forbidden_name

        if isinstance(func, ast.Attribute) and func.attr == "_getframe":
            if not isinstance(func.value, ast.Name) or func.value.id in sys_aliases:
                return "sys._getframe"

        if isinstance(func, ast.Name) and func.id == "_getframe":
            return "sys._getframe"

        if isinstance(node, ast.Subscript):
            forbidden_name = _static_forbidden_name(node.slice)
            if not forbidden_name:
                continue

            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == "__dict__":
                return forbidden_name

            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "vars"
                and value.args
            ):
                return forbidden_name

    return None


@loader.tds
class LoaderMod(loader.Module):
    """Loads modules"""

    strings = {
        "name": "Loader",
    }

    def __init__(self):
        self.fully_loaded = False
        self._links_cache = {}
        self._storage: RemoteStorage = None

        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "MODULES_REPO",
                "https://raw.githubusercontent.com/coddrago/modules/main",
                lambda: self.strings["repo_config_doc"],
                validator=loader.validators.Link(),
            ),
            loader.ConfigValue(
                "ADDITIONAL_REPOS",
                [],
                lambda: self.strings["add_repo_config_doc"],
                validator=loader.validators.Series(validator=loader.validators.Link()),
            ),
            loader.ConfigValue(
                "share_link",
                doc=lambda: self.strings["share_link_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "basic_auth",
                None,
                lambda: self.strings["basic_auth_doc"],
                validator=loader.validators.Hidden(
                    loader.validators.RegExp(r"^.*:.*$")
                ),
            ),
            loader.ConfigValue(
                "command_emoji",
                "<tg-emoji emoji-id=5197195523794157505>▫️</tg-emoji>",
                lambda: "Emoji for command",
            ),
            loader.ConfigValue(
                "show_banner",
                True,
                lambda: self.strings["show_banner_doc"],
                validator=loader.validators.Boolean(),
            ),
        )

    async def _async_init(self):
        modules = list(
            filter(
                lambda x: not x.startswith(
                    "https://raw.githubusercontent.com/coddrago/modules/main"
                ),
                utils.array_sum(
                    map(
                        lambda x: list(x.values()),
                        (await self.get_repo_list()).values(),
                    )
                ),
            )
        )
        logger.debug("Modules: %s", modules)
        asyncio.ensure_future(self._storage.preload(modules))

    async def client_ready(self):
        while not (settings := self.lookup("settings")):
            await asyncio.sleep(0.5)

        self._storage = RemoteStorage(self._client)

        self.allmodules.add_aliases(settings.get("aliases", {}))

        main.heroku.ready.set()

        asyncio.ensure_future(self._update_modules())
        asyncio.ensure_future(self._async_init())

    @loader.loop(interval=3, wait_before=True, autostart=True)
    async def _config_autosaver(self):
        for mod in self.allmodules.modules:
            if (
                not hasattr(mod, "config")
                or not mod.config
                or not isinstance(mod.config, loader.ModuleConfig)
            ):
                continue

            for option, config in mod.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(mod.config._config[option], "_save_marker")
                mod.pointer("__config__", {})[option] = config.value

        for lib in self.allmodules.libraries:
            if (
                not hasattr(lib, "config")
                or not lib.config
                or not isinstance(lib.config, loader.ModuleConfig)
            ):
                continue

            for option, config in lib.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(lib.config._config[option], "_save_marker")
                lib._lib_pointer("__config__", {})[option] = config.value

        self._db.save()

    def update_modules_in_db(self):
        if self.allmodules.secure_boot:
            return

        self.set(
            "loaded_modules",
            {
                **{
                    module.__class__.__name__: module.__origin__
                    for module in self.allmodules.modules
                    if module.__origin__.startswith("http")
                },
            },
        )

    def _get_banner_url(self, doc: str) -> typing.Optional[str]:
        match = re.search(r"# ?meta banner: ?(.+)", doc)
        return match.group(1).strip() if match else None

    def _repo_to_label(self, repo: str) -> str:
        parsed = urlparse(repo)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return repo

    @loader.command(alias="dlm")
    async def dlmod(self, message: Message, force_pm: bool = False):

        if args := utils.get_args(message):
            match args:
                case [single]:
                    args = single
                    await utils.answer(message, self.strings["finding_module_in_repos"])
                    if (
                        await self.download_and_install(args, message, force_pm)
                        == MODULE_LOADING_FORBIDDEN
                    ):
                        return

                    if self.fully_loaded:
                        self.update_modules_in_db()
                case _:
                    not_installed = []

                    await utils.answer(
                        message, "Installing {} modules...".format(len(args))
                    )

                    for arg in args:
                        result = await self.download_and_install(arg)

                        if result == MODULE_LOADING_FAILED:
                            not_installed.append(arg)
                    await utils.answer(
                        message,
                        "{} modules was installed.\n\nModules <code>{}</code> cannot be installed because they are not available in the repo".format(
                            len(args) - len(not_installed),
                            "</code>, <code>".join(not_installed),
                        ),
                    )

                    if self.fully_loaded:
                        self.update_modules_in_db()
        else:
            await self.inline.list(
                message,
                [
                    self.strings["avail_header"]
                    + f"\n☁️ {repo.strip('/')}\n\n"
                    + "\n".join(
                        [
                            " | ".join(chunk)
                            for chunk in utils.chunks(
                                [
                                    f"<code>{i}</code>"
                                    for i in sorted(
                                        [
                                            utils.escape_html(
                                                i.split("/")[-1].split(".")[0]
                                            )
                                            for i in mods.values()
                                        ]
                                    )
                                ],
                                5,
                            )
                        ]
                    )
                    for repo, mods in (await self.get_repo_list()).items()
                ],
            )

    @loader.command()
    async def dlmall(self, message: Message):
        repos = [self.config["MODULES_REPO"]] + self.config["ADDITIONAL_REPOS"]
        repos = [r for r in repos if r.startswith("http")]
        buttons = [
            [
                {
                    "text": self._repo_to_label(repo),
                    "callback": self._inline__install_all_from_repo,
                    "args": (repo,),
                }
            ]
            for repo in repos
        ]
        await self.inline.form(
            self.strings["choose_repo"],
            message,
            reply_markup=buttons,
        )

    async def _inline__install_all_from_repo(
        self,
        call: InlineCall,
        repo: str,
    ):
        await call.edit(self.strings["installing_all_from_repo"])

        links = await self._get_repo(repo)

        if not links:
            await call.edit(self.strings["dlm_all_from_repo_error_nomods"])
            return

        not_installed = []

        for link in links:
            full_url = f"{repo.strip('/')}/{link}.py"
            result = await self.download_and_install(full_url)
            if result != MODULE_LOADING_SUCCESS:
                not_installed.append(link.split("/")[-1])

        installed_count = len(links) - len(not_installed)

        if installed_count == 0:
            await call.edit(self.strings["dlm_all_from_repo_error_nomods"])
        elif not_installed:
            failed_list = "\n".join(not_installed)
            await call.edit(
                self.strings["dlm_all_from_repo_error_somemods"]
                + "<blockquote expandable>"
                + failed_list
                + "</blockquote>"
            )
        else:
            await call.edit(self.strings["installed_all_from_repo"])

        if self.fully_loaded:
            self.update_modules_in_db()

    async def _get_modules_to_load(self):
        todo = self.get("loaded_modules", {})
        logger.debug("Loading modules: %s", todo)
        return todo

    async def _get_repo(self, repo: str) -> str:
        repo = repo.strip("/")

        if self._links_cache.get(repo, {}).get("exp", 0) >= time.time():
            return self._links_cache[repo]["data"]

        res = await utils.run_sync(
            requests.get,
            f"{repo}/full.txt",
            auth=(
                tuple(self.config["basic_auth"].split(":", 1))
                if self.config["basic_auth"]
                else None
            ),
        )

        if not str(res.status_code).startswith("2"):
            logger.debug(
                "Can't load repo %s contents because of %s status code",
                repo,
                res.status_code,
            )
            return []

        self._links_cache[repo] = {
            "exp": time.time() + 5 * 60,
            "data": [link for link in res.text.strip().splitlines() if link],
        }

        return self._links_cache[repo]["data"]

    async def get_repo_list(
        self,
        only_primary: bool = False,
    ) -> dict:
        return {
            repo: {
                f"Mod/{repo_id}/{i}": f'{repo.strip("/")}/{link}.py'
                for i, link in enumerate(set(await self._get_repo(repo)))
            }
            for repo_id, repo in enumerate(
                [self.config["MODULES_REPO"]]
                + ([] if only_primary else self.config["ADDITIONAL_REPOS"])
            )
            if repo.startswith("http")
        }

    async def get_links_list(self) -> typing.List[str]:
        links = await self.get_repo_list()
        main_repo = list(links.pop(self.config["MODULES_REPO"]).values())
        return main_repo + list(dict(ChainMap(*list(links.values()))).values())

    async def _find_link(self, module_name: str) -> typing.Union[str, bool]:
        return next(
            filter(
                lambda link: link.lower().endswith(f"/{module_name.lower()}.py"),
                await self.get_links_list(),
            ),
            False,
        )

    async def download_and_install(
        self,
        module_name: str,
        message: typing.Optional[Message] = None,
        force_pm: bool = False,
    ) -> int:
        try:
            blob_link = False
            module_name = module_name.strip()
            if urlparse(module_name).netloc:
                url = module_name
                if re.match(
                    r"^(https:\/\/github\.com\/.*?\/.*?\/blob\/.*\.py)|"
                    r"(https:\/\/gitlab\.com\/.*?\/.*?\/-\/blob\/.*\.py)$",
                    url,
                ):
                    url = url.replace("/blob/", "/raw/")
                    blob_link = True
            else:
                url = await self._find_link(module_name)

                if not url:
                    logger.warning(
                        "Module %s was not found in configured repos", module_name
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["no_module"])

                    return MODULE_LOADING_FAILED

            if message:
                message = await utils.answer(
                    message,
                    self.strings["installing"].format(module_name),
                )

            try:
                r = await self._storage.fetch(url, auth=self.config["basic_auth"])
            except requests.exceptions.HTTPError as e:
                logger.warning(
                    "Failed to download module %s from %s: %s",
                    module_name,
                    url,
                    e,
                )
                if message is not None:
                    await utils.answer(message, self.strings["no_module"])

                return MODULE_LOADING_FAILED

            installed = await self.load_module(
                r,
                message,
                module_name,
                url,
                blob_link=blob_link,
                _raise_install_errors=True,
            )

            if not installed:
                raise ModuleInstallError(f"Module {module_name} was not installed")

            return MODULE_LOADING_SUCCESS
        except Exception:
            logger.exception("Failed to install external module %s", module_name)
            return MODULE_LOADING_FAILED

    async def _inline__load(
        self,
        call: InlineCall,
        doc: str,
        path_: str,
        mode: str,
    ):

        await self.load_module(doc, call, origin=path_ or "<string>", save_fs=True)

    @loader.command(alias="lm")
    async def loadmod(self, message: Message):
        args = utils.get_args_raw(message)

        msg = message if message.file else (await message.get_reply_message())

        if msg is None or msg.media is None:
            await utils.answer(message, self.strings["provide_module"])
            return

        await utils.answer(message, self.strings["loading_module_via_file"])

        path_ = None
        doc = await msg.download_media(bytes)

        try:
            doc = doc.decode()
        except UnicodeDecodeError:
            await utils.answer(message, self.strings["bad_unicode"])
            return

        if path_ is not None:
            await self.load_module(doc, message, origin=path_, save_fs=True)
        else:
            await self.load_module(doc, message, save_fs=True)

    async def approve_internal(
        self,
        call: InlineCall,
        channel: "hints.EntityLike",  # type: ignore  # noqa
        event: asyncio.Event,
    ):
        """
        Don't you dare call it externally
        """
        await self._client(JoinChannelRequest(channel))
        event.status = True
        event.set()

        await call.edit(
            (
                "💫 <b>Joined <a"
                f' href="https://t.me/{channel.username}">{utils.escape_html(channel.title)}</a></b>'
            ),
            photo="https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/joined_jr.png",
        )

    async def install_requirements(self, requirements: list):
        is_venv = hasattr(sys, "real_prefix") or sys.prefix != getattr(
            sys, "base_prefix", sys.prefix
        )
        need_user_flag = loader.USER_INSTALL and not is_venv

        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-q",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            *(["--user"] if need_user_flag else []),
            *requirements,
        ]

        try:
            pip = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            out, err = await pip.communicate()
        except Exception:
            logger.exception("Pip requirements install failed to start: %s", cmd)
            return False

        if pip.returncode != 0:
            logger.error(
                "Pip requirements install failed (%s) with exit code %s: %s",
                " ".join(cmd),
                pip.returncode,
                (err or out).decode(errors="ignore").strip() or "<no output>",
            )
            return False

        return True

    async def install_packages(self, packages: list):
        try:
            is_root = os.geteuid() == 0

            def _which(names):
                for n in names:
                    p = shutil.which(n)
                    if p:
                        return p
                return None

            pm = None
            if _which(["apt", "apt-get"]):
                pm = "apt"
            elif _which(["apk"]):
                pm = "apk"
            elif _which(["dnf"]):
                pm = "dnf"
            elif _which(["yum"]):
                pm = "yum"
            elif _which(["pacman"]):
                pm = "pacman"
            elif _which(["brew"]):
                pm = "brew"

            if not pm:
                logger.error(
                    "Can't install system packages %s: no supported package manager found",
                    packages,
                )
                return False

            cmd = []
            if pm == "apt":
                tool = _which(["apt", "apt-get"])
                cmd = [tool, "install", "-y", *packages]
            elif pm == "apk":
                cmd = ["apk", "add", "--no-cache", *packages]
            elif pm == "dnf":
                cmd = ["dnf", "install", "-y", *packages]
            elif pm == "yum":
                cmd = ["yum", "install", "-y", *packages]
            elif pm == "pacman":
                cmd = ["pacman", "-Syu", "--noconfirm", *packages]
            elif pm == "brew":
                cmd = ["brew", "install", *packages]

            if not is_root and shutil.which("sudo"):
                cmd = ["sudo", *cmd]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            out, err = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "System package install failed (%s) with exit code %s: %s",
                    " ".join(cmd),
                    proc.returncode,
                    err.decode(errors="ignore") if err else out.decode(errors="ignore"),
                )
                return False

            return True
        except Exception:
            logger.exception("install_packages failed")
            return False

    async def load_module(
        self,
        doc: str,
        message: Message,
        name: typing.Optional[str] = None,
        origin: str = "<string>",
        did_requirements: bool = False,
        save_fs: bool = True,
        blob_link: bool = False,
        did_requires: bool = False,
        did_packages: bool = False,
        _raise_install_errors: bool = False,
    ) -> bool:
        module_label = name or origin

        def fail_install(message: str, *args: object) -> None:
            rendered = message % args if args else message
            if _raise_install_errors:
                raise ModuleInstallError(rendered)

            logger.error(message, *args)

        forbidden_api = _find_forbidden_external_api_usage(doc)
        if forbidden_api:
            forbidden_api_msg = self.strings["forbidden_api"].format(
                utils.escape_html(forbidden_api)
            )
            if isinstance(message, InlineCall):
                await message.edit(forbidden_api_msg)
            elif message is not None:
                await utils.answer(message, forbidden_api_msg)
            fail_install(
                "Module %s uses forbidden method: %s",
                module_label,
                forbidden_api,
            )
            return False

        if any(
            line.replace(" ", "") == "#scope:ffmpeg" for line in doc.splitlines()
        ) and os.system("ffmpeg -version 1>/dev/null 2>/dev/null"):
            logger.error(
                "Module %s requires ffmpeg, but ffmpeg is not installed",
                module_label,
            )
            if isinstance(message, Message):
                await utils.answer(message, self.strings["ffmpeg_required"])
            return False

        if (
            any(line.replace(" ", "") == "#scope:inline" for line in doc.splitlines())
            and not self.inline.init_complete
        ):
            logger.error(
                "Module %s requires inline mode, but inline initialization failed",
                module_label,
            )
            if isinstance(message, Message):
                await utils.answer(message, self.strings["inline_init_failed"])
            return False

        if re.search(r"# ?scope: ?heroku_min", doc):
            ver = re.search(r"# ?scope: ?heroku_min ((?:\d+\.){2}\d+)", doc).group(1)
            ver_ = tuple(map(int, ver.split(".")))
            if main.__version__ < ver_:
                logger.error(
                    "Module %s requires Heroku %s, current version is %s",
                    module_label,
                    ver,
                    ".".join(map(str, main.__version__)),
                )
                if isinstance(message, Message):
                    if getattr(message, "file", None):
                        m = utils.get_chat_id(message)
                        await message.edit("")
                    else:
                        m = message

                    await self.inline.form(
                        self.strings["version_incompatible"].format(ver),
                        m,
                        reply_markup=[
                            {
                                "text": self.lookup("updater").strings("btn_update"),
                                "callback": self.lookup("updater").inline_update,
                            },
                            {
                                "text": self.lookup("updater").strings("cancel"),
                                "action": "close",
                            },
                        ],
                    )
                return False

        developer = re.search(r"# ?meta developer: ?(.+)", doc)
        developer = developer.group(1) if developer else False

        if not did_requires:
            requirements = []
            try:
                requirements = list(
                    filter(
                        lambda x: not x.startswith(("-", "_", ".")),
                        map(
                            str.strip,
                            loader.VALID_PIP_PACKAGES.search(doc)[1].split(),
                        ),
                    )
                )
            except TypeError:
                pass

            if requirements:
                result = await self.install_requirements(requirements)
                if not result:
                    logger.error(
                        "Module %s requirements from #scope:requires failed to install: %s",
                        module_label,
                        requirements,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])

                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_requires"] = True

                return await self.load_module(**kwargs)  # Try again

        if not did_packages:
            packages = []
            try:
                packages = list(
                    filter(
                        lambda x: not x.startswith(("-", "_", ".")),
                        map(
                            str.strip,
                            loader.VALID_APT_PACKAGES.search(doc)[1].split(),
                        ),
                    )
                )
            except TypeError:
                pass

            if packages:
                result = await self.install_packages(packages)

                if not result:
                    logger.error(
                        "Module %s system packages from #scope:packages failed to install: %s",
                        module_label,
                        packages,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])
                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_packages"] = True

                return await self.load_module(**kwargs)

        blob_link = self.strings["blob_link"] if blob_link else ""

        if name is None:
            try:
                node = ast.parse(doc)
                uid = next(
                    n.name
                    for n in node.body
                    if isinstance(n, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Attribute)
                        and base.value.id == "Module"
                        or isinstance(base, ast.Name)
                        and base.id == "Module"
                        for base in n.bases
                    )
                )
            except Exception:
                logger.debug(
                    "Can't parse classname from code, using legacy uid instead",
                    exc_info=True,
                )
                uid = "__extmod_" + str(uuid.uuid4())
        else:
            if name.startswith(self.config["MODULES_REPO"]):
                name = name.split("/")[-1].split(".py")[0]

            uid = name.replace("%", "%%").replace(".", "%d")

        module_name = f"heroku.modules.{uid}"
        doc = geek.compat(doc)

        async def restart_inline(call: InlineCall):
            await call.edit(self.strings["requirements_restarted"])
            await self.invoke("restart", "-f", message=message)

        async def core_overwrite(e: CoreOverwriteError):
            nonlocal message

            with contextlib.suppress(Exception):
                self.allmodules.modules.remove(instance)

            if not message:
                return

            await utils.answer(
                message,
                self.strings[f"overwrite_{e.type}"].format(
                    *(
                        (e.target,)
                        if e.type == "module"
                        else (utils.escape_html(self.get_prefix()), e.target)
                    )
                ),
            )

        try:
            try:
                spec = ModuleSpec(
                    module_name,
                    loader.StringLoader(doc, f"<external {module_name}>"),
                    origin=f"<external {module_name}>",
                )
                instance = await self.allmodules.register_module(
                    spec,
                    module_name,
                    origin,
                    save_fs=save_fs,
                )
            except ImportError as e:
                logger.info(
                    "Module loading failed, attemping dependency installation (%s)",
                    e.name,
                )
                requirements = [
                    {
                        "sklearn": "scikit-learn",
                        "pil": "Pillow",
                        "herokutl": "Heroku-TL-New",
                    }.get(e.name.lower(), e.name)
                ]

                if not requirements:
                    raise Exception("Nothing to install") from e

                logger.debug("Installing requirements: %s", requirements)

                if did_requirements:
                    logger.error(
                        "Module %s still requires missing dependency %s after installation",
                        module_label,
                        e.name,
                    )
                    if message is not None:
                        await self.inline.form(
                            message=message,
                            text=self.strings["requirements_restart"].format(e.name),
                            reply_markup=[
                                {"text": "🚀 Restart", "callback": restart_inline}
                            ],
                        )

                    return False

                if message is not None:
                    await utils.answer(
                        message,
                        self.strings["requirements_installing"].format(
                            "\n".join(
                                f"{self.config['command_emoji']}" f" {req}"
                                for req in requirements
                            )
                        ),
                    )

                result = await self.install_requirements(requirements)
                if not result:
                    logger.error(
                        "Module %s dependency installation failed: %s",
                        module_label,
                        requirements,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])

                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_requirements"] = True

                return await self.load_module(**kwargs)  # Try again
            except CoreOverwriteError as e:
                logger.error(
                    "Module %s tried to overwrite core %s %s",
                    module_label,
                    e.type,
                    e.target,
                )
                await core_overwrite(e)
                return False
            except (loader.LoadError, ScamDetectionError) as e:
                logger.error("Module %s failed security checks: %s", module_label, e)
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    if isinstance(e, loader.LoadError):
                        await utils.answer(
                            message,
                            (
                                "<tg-emoji emoji-id=5454225457916420314>😖</tg-emoji>"
                                f" <b>{utils.escape_html(str(e))}</b>"
                            ),
                        )
                    elif isinstance(e, ScamDetectionError):
                        await utils.answer(
                            message,
                            (
                                self.strings["scam_module"].format(
                                    name=instance.__class__.__name__,
                                    prefix=self.get_prefix(),
                                )
                            ),
                        )
                return False
        except Exception as e:
            logger.exception("Loading external module failed due to %s", e)

            if message is not None:
                await utils.answer(message, self.strings["load_failed"])

            return False

        if hasattr(instance, "__version__") and isinstance(instance.__version__, tuple):
            version = (
                "<b><i>"
                f" (v{'.'.join(list(map(str, list(instance.__version__))))})</i></b>"
            )
        else:
            version = ""

        try:
            try:
                self.allmodules.send_config_one(instance)

                async def inner_proxy():
                    nonlocal instance, message
                    while True:
                        if hasattr(instance, "heroku_wait_channel_approve"):
                            if message:
                                (
                                    module,
                                    channel,
                                    reason,
                                ) = instance.heroku_wait_channel_approve
                                message = await utils.answer(
                                    message,
                                    self.strings["wait_channel_approve"].format(
                                        module,
                                        channel.username,
                                        utils.escape_html(channel.title),
                                        utils.escape_html(reason),
                                        self.inline.bot_username,
                                    ),
                                )
                                return

                        await asyncio.sleep(0.1)

                task = asyncio.ensure_future(inner_proxy())
                await self.allmodules.send_ready_one(
                    instance,
                    no_self_unload=True,
                    from_dlmod=bool(message),
                )
                task.cancel()
            except CoreOverwriteError as e:
                logger.error(
                    "Module %s tried to overwrite core %s %s during ready stage",
                    module_label,
                    e.type,
                    e.target,
                )
                await core_overwrite(e)
                return False
            except (loader.LoadError, ScamDetectionError) as e:
                logger.error(
                    "Module %s failed during ready security checks: %s",
                    module_label,
                    e,
                )
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    if isinstance(e, loader.LoadError):
                        await utils.answer(
                            message,
                            (
                                "<tg-emoji emoji-id=5454225457916420314>😖</tg-emoji>"
                                f" <b>{utils.escape_html(str(e))}</b>"
                            ),
                        )
                    elif isinstance(e, ScamDetectionError):
                        await utils.answer(
                            message,
                            (
                                self.strings["scam_module"].format(
                                    name=instance.__class__.__name__,
                                    prefix=self.get_prefix(),
                                )
                            ),
                        )
                return False
            except loader.SelfUnload as e:
                logger.warning(
                    "Module %s unloaded itself during installation: %s",
                    module_label,
                    e,
                )
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    await utils.answer(
                        message,
                        (
                            "<tg-emoji emoji-id=5454225457916420314>😖</tg-emoji>"
                            f" <b>{utils.escape_html(str(e))}</b>"
                        ),
                    )
                return False
            except loader.SelfSuspend as e:
                logger.warning(
                    "Module %s suspended itself during installation: %s",
                    module_label,
                    e,
                )
                if message:
                    await utils.answer(
                        message,
                        (
                            "🥶 <b>Module suspended itself\nReason:"
                            f" {utils.escape_html(str(e))}</b>"
                        ),
                    )
                return False
        except Exception as e:
            logger.exception("Module threw because of %s", e)

            if message is not None:
                await utils.answer(message, self.strings["load_failed"])

            return False

        instance.heroku_meta_pic = next(
            (
                line.replace(" ", "").split("#metapic:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#metapic:")
            ),
            None,
        )

        pack_url = next(
            (
                line.replace(" ", "").split("#packurl:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#packurl:")
            ),
            None,
        )

        if pack_url and (
            transations := await self.allmodules.translator.load_module_translations(
                pack_url,
                loader.MODULES_LANGPACKS_PATH
                / f"{self.client.tg_id}_{instance.__class__.__name__}.yml",
            )
        ):
            instance.strings.external_strings = transations

        for alias, cmd in self.lookup("settings").get("aliases", {}).items():
            _cmd = cmd.split(maxsplit=1)
            if _cmd[0] in instance.commands:
                self.allmodules.add_alias(alias, *_cmd)

        try:
            modname = instance.strings("name")
        except (KeyError, AttributeError):
            modname = getattr(instance, "name", instance.__class__.__name__)

        try:
            developer_entity = await (
                self._client.force_get_entity
                if (
                    developer in self._client.heroku_entity_cache
                    and getattr(
                        await self._client.get_entity(developer),
                        "left",
                        True,
                    )
                )
                else self._client.get_entity
            )(developer)
        except Exception:
            developer_entity = None

        if not isinstance(developer_entity, Channel):
            developer_entity = None

        if message is None:
            return True

        modhelp = []
        mod_doc = ""

        if instance.__doc__:
            mod_doc += (
                "<i>\n<tg-emoji emoji-id=5879813604068298387>ℹ️</tg-emoji>"
                f" {utils.escape_html(inspect.getdoc(instance))}</i>\n\n"
            )

        subscribe = ""
        subscribe_markup = None

        depends_from = []
        for key in dir(instance):
            value = getattr(instance, key)
            if isinstance(value, loader.Library):
                depends_from.append(
                    "<tg-emoji emoji-id=5197195523794157505>▫️</tg-emoji>"
                    " <code>{}</code> <b>{}</b> <code>{}</code>".format(
                        value.__class__.__name__,
                        self.strings["by"],
                        (
                            value.developer
                            if isinstance(getattr(value, "developer", None), str)
                            else "Unknown"
                        ),
                    )
                )
        placeholders = utils.help_placeholders(
            getattr(getattr(instance, "__class__"), "__name__"), self
        )

        depends_from = (
            self.strings["depends_from"].format("\n".join(depends_from))
            if depends_from
            else ""
        )

        def loaded_msg(use_subscribe: bool = True):
            nonlocal modname, version, mod_doc, modhelp, placeholders, developer, origin, subscribe, blob_link, depends_from
            return self.strings["loaded"].format(
                modname.strip(),
                version,
                utils.ascii_face(),
                mod_doc if mod_doc else "",
                "<blockquote expandable>{}</blockquote>".format("\n".join(modhelp)),
                "\n<blockquote expandable>{}</blockquote>".format(
                    "\n".join(placeholders)
                ),
                developer if not subscribe or not use_subscribe else "",
                depends_from,
                (
                    self.strings["modlink"].format(origin)
                    if origin != "<string>" and self.config["share_link"]
                    else ""
                ),
                blob_link,
                subscribe if use_subscribe else "",
            )

        if developer:
            if developer.startswith("@") and developer not in self.get(
                "do_not_subscribe", []
            ):
                if (
                    developer_entity
                    and getattr(developer_entity, "left", True)
                    and self._db.get(main.__name__, "suggest_subscribe", True)
                ):
                    subscribe = self.strings["suggest_subscribe"].format(
                        f"@{utils.escape_html(developer_entity.username)}"
                    )
                    subscribe_markup = [
                        {
                            "text": self.strings["subscribe"],
                            "callback": self._inline__subscribe,
                            "args": (
                                developer_entity.id,
                                functools.partial(loaded_msg, use_subscribe=False),
                                True,
                            ),
                        },
                        {
                            "text": self.strings["no_subscribe"],
                            "callback": self._inline__subscribe,
                            "args": (
                                developer,
                                functools.partial(loaded_msg, use_subscribe=False),
                                False,
                            ),
                        },
                    ]

            developer = self.strings["developer"].format(utils.escape_html(developer))
        else:
            developer = ""

        banner_kwargs = {}
        if self.config["show_banner"] and not subscribe_markup:
            try:
                banner_url = self._get_banner_url(doc)
                if banner_url:
                    banner_kwargs = {
                        "file": InputMediaWebPage(banner_url, optional=True),
                        "invert_media": True,
                    }
            except Exception:
                pass

        if any(
            line.replace(" ", "") == "#scope:disable_onload_docs"
            for line in doc.splitlines()
        ):
            await utils.answer(
                message,
                loaded_msg(),
                reply_markup=subscribe_markup,
                **banner_kwargs,
            )
            return True

        for _name, fun in sorted(
            instance.commands.items(),
            key=lambda x: x[0],
        ):
            modhelp.append(
                "{} <code>{}{}</code> {}".format(
                    f"{self.config['command_emoji']}",
                    utils.escape_html(self.get_prefix()),
                    _name,
                    (
                        utils.escape_html(inspect.getdoc(fun))
                        if fun.__doc__
                        else self.strings["undoc"]
                    ),
                )
            )

        if self.inline.init_complete:
            for _name, fun in sorted(
                instance.inline_handlers.items(),
                key=lambda x: x[0],
            ):
                modhelp.append(
                    self.strings["ihandler"].format(
                        f"@{self.inline.bot_username} {_name}",
                        (
                            utils.escape_html(inspect.getdoc(fun))
                            if fun.__doc__
                            else self.strings["undoc"]
                        ),
                    )
                )

        try:
            await utils.answer(
                message,
                loaded_msg(),
                reply_markup=subscribe_markup,
                **banner_kwargs,
            )
        except MediaCaptionTooLongError:
            await message.reply(loaded_msg(False))

        return True

    async def _inline__subscribe(
        self,
        call: InlineCall,
        entity: int,
        msg: typing.Callable[[], str],
        subscribe: bool,
    ):
        if not subscribe:
            self.set("do_not_subscribe", self.get("do_not_subscribe", []) + [entity])
            await utils.answer(call, msg())
            await call.answer(self.strings["not_subscribed"])
            return

        await self._client(JoinChannelRequest(entity))
        await utils.answer(call, msg())
        await call.answer(self.strings["subscribed"])

    @loader.command(alias="ulm")
    async def unloadmod(self, message: Message):
        if not (raw_args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_class"])
            return

        args = raw_args
        force = False
        first_line = args.split("\n", 1)[0].strip()
        if first_line == "-f":
            force = True
            rest = args.split("\n", 1)
            args = rest[1].strip() if len(rest) > 1 else ""
        elif args.startswith("-f "):
            force = True
            args = args[3:].strip()

        if not args:
            await utils.answer(message, self.strings["no_class"])
            return

        raw_list = re.split(r"[,\n]", args)
        modules = [m.strip() for m in raw_list if m.strip()]

        if len(modules) == 1:
            if not self.lookup(modules[0]):
                suggestions = self._get_unload_suggestions(modules[0])
                if suggestions:
                    form = await self.inline.form(
                        "<tg-emoji emoji-id=5134452506935427991>🪐</tg-emoji>",
                        message,
                        silent=True,
                    )
                    if form:
                        await form.edit(
                            self.strings["unload_suggestions"].format(
                                utils.escape_html(modules[0])
                            ),
                            reply_markup=[
                                [
                                    {
                                        "text": label,
                                        "callback": self._inline__unload_suggested,
                                        "args": (classname, force),
                                    }
                                ]
                                for classname, label in suggestions
                            ]
                            + [
                                [
                                    {
                                        "text": self.strings["cancel"].replace(
                                            "🚫", "❌"
                                        ),
                                        "action": "close",
                                    }
                                ]
                            ],
                        )
                    return

            msg = await self.unload_module(modules[0], force=force)
        else:
            success = []
            errors = []
            msg = ""
            for module in modules:
                status = await self.unload_module(module)
                if "❌" in status or "🚫" in status or "😖" in status:
                    if "💡" in status:
                        status = status.split("<code>")[0]

                    errors.append(f"<code>{module}</code> — {status}")
                else:
                    success.append(f"<code>{module}</code>")

            if success:
                msg += self.strings["modules_unloaded"].format(
                    unloaded_num=len(success), unloaded=", ".join(success)
                )
            if errors:
                msg += "\n" + self.strings["modules_not_unloaded"].format(
                    not_unloaded=len(errors),
                    errors="\n".join(errors),
                )

        await utils.answer(message, msg)

    def _get_unload_suggestions(
        self,
        query: str,
        limit: int = 3,
    ) -> list[tuple[str, str]]:
        query = query.lower()
        scored = []

        for module in self.allmodules.modules:
            if self._is_core_module(module):
                continue

            classname = module.__class__.__name__
            public_name = str(getattr(module, "name", "") or module.strings["name"])
            names = {
                classname,
                classname[:-3] if classname.endswith("Mod") else classname,
                public_name,
            }
            score = max(
                difflib.SequenceMatcher(None, query, name.lower()).ratio()
                for name in names
                if name
            )
            label = public_name
            scored.append((score, classname.lower(), classname, label))

        return [
            (classname, label)
            for _, _, classname, label in sorted(scored, reverse=True)[:limit]
        ]

    def _is_core_module(self, module) -> bool:
        module_name = getattr(module.__class__, "__module__", "")
        if not module_name.startswith("heroku.modules."):
            return False

        module_file = module_name.rsplit(".", 1)[-1]
        return os.path.isfile(
            os.path.join(utils.get_base_dir(), "modules", f"{module_file}.py")
        )

    async def _inline__unload_suggested(
        self,
        call: InlineCall,
        module: str,
        force: bool = False,
    ):
        await call.edit(await self.unload_module(module, force=force))

    async def unload_module(self, module: str, force: bool = False) -> str:
        instance = self.lookup(module)

        if instance and self._is_core_module(instance):
            return self.strings["unload_core"].format(module)

        if instance and issubclass(instance.__class__, loader.Library):
            return self.strings["cannot_unload_lib"]

        try:
            worked = await self.allmodules.unload_module(module)
        except CoreUnloadError as e:
            return self.strings["unload_core"].format(module)

        if not self.allmodules.secure_boot:
            self.set(
                "loaded_modules",
                {
                    mod: link
                    for mod, link in self.get("loaded_modules", {}).items()
                    if mod not in worked
                },
            )

        msg = (
            self.strings["unloaded"].format(
                "<tg-emoji emoji-id=5784993237412351403>✅</tg-emoji>",
                ", ".join(
                    [(mod[:-3] if mod.endswith("Mod") else mod) for mod in worked]
                ),
            )
            if worked
            else self.strings["not_unloaded"]
        )
        for mod_name in worked:
            utils.unregister_placeholders(mod_name)

        if force and worked:
            try:
                for key in list(self._db.keys()):
                    if not isinstance(key, str):
                        continue
                    low = key.lower()
                    for mod_name in worked:
                        base = mod_name[:-3] if mod_name.endswith("Mod") else mod_name
                        candidates = {mod_name.lower(), base.lower()}
                        if any(
                            low == c
                            or low.startswith(c + ".")
                            or low.startswith(c + "_")
                            or c in low
                            for c in candidates
                        ):
                            try:
                                del self._db[key]
                            except Exception:
                                pass

                try:
                    self._db.save()
                except Exception:
                    logger.debug(
                        "Failed to save DB after force-unload cleanup", exc_info=True
                    )
            except Exception:
                logger.exception("Failed to cleanup DB for force unload")

        return msg

    @loader.command()
    async def clearmodules(self, message: Message):
        await self.inline.form(
            self.strings["confirm_clearmodules"],
            message,
            reply_markup=[
                {
                    "text": self.strings["clearmodules"],
                    "callback": self._inline__clearmodules,
                },
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
            ],
        )

    @loader.command()
    async def addrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or (
            not utils.check_url(args) and not utils.check_url(f"https://{args}")
        ):
            await utils.answer(message, self.strings["no_repo"])
            return

        if args.endswith("/"):
            args = args[:-1]

        if not args.startswith("https://") and not args.startswith("http://"):
            args = f"https://{args}"

        try:
            r = await utils.run_sync(
                requests.get,
                f"{args}/full.txt",
                auth=(
                    tuple(self.config["basic_auth"].split(":", 1))
                    if self.config["basic_auth"]
                    else None
                ),
            )
            r.raise_for_status()
            if not r.text.strip():
                raise ValueError
        except Exception:
            await utils.answer(message, self.strings["no_repo"])
            return

        if args in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings["repo_exists"].format(args))
            return

        self.config["ADDITIONAL_REPOS"] += [args]

        await utils.answer(message, self.strings["repo_added"].format(args))

    @loader.command()
    async def delrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or not utils.check_url(args):
            await utils.answer(message, self.strings["no_repo"])
            return

        if args.endswith("/"):
            args = args[:-1]

        if args not in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings["repo_not_exists"])
            return

        self.config["ADDITIONAL_REPOS"].remove(args)

        await utils.answer(message, self.strings["repo_deleted"].format(args))

    async def _inline__clearmodules(self, call: InlineCall):
        self.set("loaded_modules", {})

        for file in os.scandir(loader.LOADED_MODULES_DIR):
            try:
                os.remove(file.path)
            except Exception:
                logger.debug("Failed to remove %s", file.path, exc_info=True)

        await utils.answer(call, self.strings["all_modules_deleted"])
        await self.lookup("Updater").restart_common(call)

    async def _update_modules(self):
        todo = await self._get_modules_to_load()

        self._secure_boot = False

        if self._db.get(loader.__name__, "secure_boot", False):
            self._db.set(loader.__name__, "secure_boot", False)
            self._secure_boot = True
        else:
            for mod in todo.values():
                await self.download_and_install(mod)

            self.update_modules_in_db()

            aliases = {
                alias: cmd
                for alias, cmd in self.lookup("settings").get("aliases", {}).items()
                if self.allmodules.add_alias(alias, *cmd.split(maxsplit=1))
            }

            self.lookup("settings").set("aliases", aliases)

        self.fully_loaded = True

        with contextlib.suppress(AttributeError):
            await self.lookup("Updater").full_restart_complete(self._secure_boot)

    def flush_cache(self) -> int:
        """Flush the cache of links to modules"""
        count = sum(map(len, self._links_cache.values()))
        self._links_cache = {}
        return count

    def inspect_cache(self) -> int:
        """Inspect the cache of links to modules"""
        return sum(map(len, self._links_cache.values()))

    async def reload_core(self) -> int:
        """Forcefully reload all core modules"""
        self.fully_loaded = False

        if self._secure_boot:
            self._db.set(loader.__name__, "secure_boot", True)

        if not self._db.get(main.__name__, "remove_core_protection", False):
            for module in self.allmodules.modules:
                if module.__origin__.startswith("<core"):
                    module.__origin__ = "<reload-core>"

        loaded = await self.allmodules.register_all(no_external=True)
        for instance in loaded:
            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(
                instance,
                no_self_unload=False,
                from_dlmod=False,
            )

        self.fully_loaded = True
        return len(loaded)

    @loader.command()
    async def mlcmd(self, message: Message):
        """| send module via file"""
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["args"])
            return

        await utils.answer(message, self.strings["ml_load_module"])

        exact = True
        if not (
            class_name := next(
                (
                    module.strings("name")
                    for module in self.allmodules.modules
                    if args.lower()
                    in {
                        module.strings("name").lower(),
                        module.__class__.__name__.lower(),
                    }
                ),
                None,
            )
        ):
            if not (
                class_name := next(
                    reversed(
                        sorted(
                            [
                                module.strings["name"].lower()
                                for module in self.allmodules.modules
                            ]
                            + [
                                module.__class__.__name__.lower()
                                for module in self.allmodules.modules
                            ],
                            key=lambda x: difflib.SequenceMatcher(
                                None,
                                args.lower(),
                                x,
                            ).ratio(),
                        )
                    ),
                    None,
                )
            ):
                await utils.answer(message, self.strings["404"])
                return

            exact = False

        try:
            module = self.lookup(class_name)
            sys_module = inspect.getmodule(module)
        except Exception:
            await utils.answer(message, self.strings["404"])
            return

        module_data = sys_module.__loader__.data
        if isinstance(module_data, str):
            module_data = module_data.encode("utf-8")

        module_doc = (
            module_data.decode("utf-8", errors="ignore")
            if isinstance(module_data, (bytes, bytearray))
            else str(module_data)
        )

        if any(
            line.replace(" ", "") == "#scope:no_ml" for line in module_doc.splitlines()
        ):
            await utils.answer(
                message,
                self.strings["no_ml"].format(utils.escape_html(class_name)),
            )
            return

        link = module.__origin__

        text = (
            f"<b>🧳 {utils.escape_html(class_name)}</b>"
            if not utils.check_url(link)
            else (
                f'📼 <b><a href="{link}">Link</a> for'
                f" {utils.escape_html(class_name)}:</b>"
                f' <code>{link}</code>\n\n{self.strings["not_exact"] if not exact else ""}'
            )
        )

        text = (
            self.strings["link"].format(
                class_name=utils.escape_html(class_name),
                url=link,
                not_exact=self.strings["not_exact"] if not exact else "",
                prefix=utils.escape_html(self.get_prefix()),
            )
            if utils.check_url(link)
            else self.strings["file"].format(
                class_name=utils.escape_html(class_name),
                not_exact=self.strings["not_exact"] if not exact else "",
                prefix=utils.escape_html(self.get_prefix()),
            )
        )

        file = io.BytesIO(module_data)
        file.name = f"{class_name}.py"
        file.seek(0)

        await utils.answer(
            message,
            text,
            file=file,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    def _format_result(
        self,
        result: dict,
        query: str,
        no_translate: bool = False,
    ) -> str:
        commands = "\n".join(
            [
                f"▫️ <code>{utils.escape_html(self.get_prefix())}{utils.escape_html(cmd)}</code>:"
                f" <b>{utils.escape_html(cmd_doc)}</b>"
                for cmd, cmd_doc in result["module"]["commands"].items()
            ]
        )

        kwargs = {
            "name": utils.escape_html(result["module"]["name"]),
            "dev": utils.escape_html(result["module"]["dev"]),
            "commands": commands,
            "cls_doc": utils.escape_html(result["module"]["cls_doc"]),
            "mhash": result["module"]["hash"],
            "query": utils.escape_html(query),
            "prefix": utils.escape_html(self.get_prefix()),
        }

        strings = (
            self.strings.get("result", "en")
            if self.config["translate"] and not no_translate
            else self.strings["result"]
        )

        text = strings.format(**kwargs)

        if len(text) > 1980:
            kwargs["commands"] = "..."
            text = strings.format(**kwargs)

        return text
