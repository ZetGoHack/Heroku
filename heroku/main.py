"""Main script, where all the fun starts"""

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

import argparse
import asyncio
import collections
import contextlib
import importlib
import json
import logging
import os
import random
import signal
import socket
import sqlite3
import sys
import typing
import string
from getpass import getpass
from pathlib import Path

import aiohttp
import pyrogram
from herokutl import events
from pyrogram import Client, filters, handlers
from pyrogram.qrlogin import QRLogin
from pyrogram.errors import (
    ApiIdInvalid,
    AuthKeyDuplicated,
    BadRequest,
    FloodWait,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
    YouBlockedUser,
)
from herokutl.sessions import MemorySession, SQLiteSession
from pyrogram.enums import ParseMode
from pyrogram.methods.utilities import idle
from pyrogram.raw.functions.account import GetPassword
from pyrogram.raw.functions.auth import CheckPassword
from pyrogram.raw.functions.contacts import Unblock

from . import database, loader, utils, version
from ._internal import print_banner, restart
from .dispatcher import CommandDispatcher
from .inline.utils import Utils as inutils
from .inline.token_obtainment import TokenObtainment
from .qr import QRCode
from .types import SQLiteStringStorage
from .tl_cache import CustomClient
from .translations import Translator
from .version import __version__

try:
    from .web import core
except ImportError:
    web_available = False
    logging.exception("Unable to import web")
else:
    web_available = True

BASE_DIR = (
    "/data"
    if "DOCKER" in os.environ
    else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

BASE_PATH = Path(BASE_DIR)
CONFIG_PATH = BASE_PATH / "config.json"

# fmt: off
LATIN_MOCK = [
    "Amor", "Arbor", "Astra", "Aurum", "Bellum", "Caelum",
    "Calor", "Candor", "Carpe", "Celer", "Certo", "Cibus",
    "Civis", "Clemens", "Coetus", "Cogito", "Conexus",
    "Consilium", "Cresco", "Cura", "Cursus", "Decus",
    "Deus", "Dies", "Digitus", "Discipulus", "Dominus",
    "Donum", "Dulcis", "Durus", "Elementum", "Emendo",
    "Ensis", "Equus", "Espero", "Fidelis", "Fides",
    "Finis", "Flamma", "Flos", "Fortis", "Frater", "Fuga",
    "Fulgeo", "Genius", "Gloria", "Gratia", "Gravis",
    "Habitus", "Honor", "Hora", "Ignis", "Imago",
    "Imperium", "Inceptum", "Infinitus", "Ingenium",
    "Initium", "Intra", "Iunctus", "Iustitia", "Labor",
    "Laurus", "Lectus", "Legio", "Liberi", "Libertas",
    "Lumen", "Lux", "Magister", "Magnus", "Manus",
    "Memoria", "Mens", "Mors", "Mundo", "Natura",
    "Nexus", "Nobilis", "Nomen", "Novus", "Nox",
    "Oculus", "Omnis", "Opus", "Orbis", "Ordo", "Os",
    "Pax", "Perpetuus", "Persona", "Petra", "Pietas",
    "Pons", "Populus", "Potentia", "Primus", "Proelium",
    "Pulcher", "Purus", "Quaero", "Quies", "Ratio",
    "Regnum", "Sanguis", "Sapientia", "Sensus", "Serenus",
    "Sermo", "Signum", "Sol", "Solus", "Sors", "Spes",
    "Spiritus", "Stella", "Summus", "Teneo", "Terra",
    "Tigris", "Trans", "Tribuo", "Tristis", "Ultimus",
    "Unitas", "Universus", "Uterque", "Valde", "Vates",
    "Veritas", "Verus", "Vester", "Via", "Victoria",
    "Vita", "Vox", "Vultus", "Zephyrus", "Bimbalas", "Nywuctuu",
    "Anyone", "Draher", "Hackimo", "Silvyr", 

]
# fmt: on


def generate_app_name() -> str:
    """
    Generate random app name
    :return: Random app name
    :example: "Cresco Cibus Consilium"
    """
    return " ".join(random.choices(LATIN_MOCK, k=3))


def get_app_name() -> str:
    """
    Generates random app name or gets the saved one of present
    :return: App name
    :example: "Cresco Cibus Consilium"
    """
    if not (app_name := get_config_key("app_name")):
        app_name = generate_app_name()
        save_config_key("app_name", app_name)

    return app_name


def generate_random_system_version():
    """
    Generates a random system version string similar to those used by Windows or Linux.

    This function generates a random version string that follows the format used by operating systems
    like Windows or Linux. The version string includes the major version, minor version, patch number,
    and build number, each of which is randomly generated within specified ranges. Additionally, it
    includes a random operating system name and version.

    :return: A randomly generated system version string.
    :example: "Windows 10.0.19042.1234" or "Ubuntu 20.04.19042.1234"
    """
    os_choices = [
        ("Windows", "3.1"),
        ("Windows", "95"),
        ("Windows", "98"),
        ("Windows", "ME"),
        ("Windows", "NT 4.0"),
        ("Windows", "2000"),
        ("Windows", "XP"),
        ("Windows", "Server 2003"),
        ("Windows", "Vista"),
        ("Windows", "7"),
        ("Windows", "8"),
        ("Windows", "8.1"),
        ("Windows", "10"),
        ("Windows", "11"),
        ("Windows", "Server 2016"),
        ("Windows", "Server 2019"),
        ("Windows", "Server 2022"),
        ("macOS", "10.9 Mavericks"),
        ("macOS", "10.10 Yosemite"),
        ("macOS", "10.11 El Capitan"),
        ("macOS", "10.12 Sierra"),
        ("macOS", "10.13 High Sierra"),
        ("macOS", "10.14 Mojave"),
        ("macOS", "10.15 Catalina"),
        ("macOS", "11 Big Sur"),
        ("macOS", "12 Monterey"),
        ("macOS", "13 Ventura"),
        ("macOS", "14 Sonoma"),
        ("iOS", "12.5.7"),
        ("iOS", "13.7"),
        ("iOS", "14.8"),
        ("iOS", "15.7"),
        ("iOS", "16.6"),
        ("iOS", "17.4"),
        ("iPadOS", "16.4"),
        ("Android", "4.4 KitKat"),
        ("Android", "5.0 Lollipop"),
        ("Android", "6.0 Marshmallow"),
        ("Android", "7.0 Nougat"),
        ("Android", "8.0 Oreo"),
        ("Android", "9 Pie"),
        ("Android", "10"),
        ("Android", "11"),
        ("Android", "12"),
        ("Android", "13"),
        ("Android", "14"),
        ("Android", "15"),
        ("Android", "16"),
        ("ChromeOS", "89"),
        ("ChromeOS", "96"),
        ("ChromeOS", "100"),
        ("ChromeOS", "110"),
        ("Ubuntu", "14.04"),
        ("Ubuntu", "16.04"),
        ("Ubuntu", "18.04"),
        ("Ubuntu", "19.10"),
        ("Ubuntu", "20.04"),
        ("Ubuntu", "21.04"),
        ("Ubuntu", "21.10"),
        ("Ubuntu", "22.04"),
        ("Ubuntu", "22.10"),
        ("Ubuntu", "23.04"),
        ("Ubuntu", "23.10"),
        ("Ubuntu", "24.04"),
        ("Debian", "7 wheezy"),
        ("Debian", "8 jessie"),
        ("Debian", "9 stretch"),
        ("Debian", "10 buster"),
        ("Debian", "11 bullseye"),
        ("Debian", "12 bookworm"),
        ("Fedora", "28"),
        ("Fedora", "29"),
        ("Fedora", "30"),
        ("Fedora", "31"),
        ("Fedora", "32"),
        ("Fedora", "33"),
        ("Fedora", "34"),
        ("Fedora", "35"),
        ("Fedora", "36"),
        ("Fedora", "37"),
        ("Fedora", "38"),
        ("Fedora", "39"),
        ("CentOS", "6"),
        ("CentOS", "7"),
        ("CentOS", "8"),
        ("CentOS Stream", "8"),
        ("CentOS Stream", "9"),
        ("AlmaLinux", "8.6"),
        ("AlmaLinux", "9.1"),
        ("Rocky Linux", "8.6"),
        ("Rocky Linux", "9.0"),
        ("Arch Linux", "rolling-2021.05.01"),
        ("Arch Linux", "rolling-2022.11.01"),
        ("Manjaro", "21.0"),
        ("Manjaro", "22.0"),
        ("Linux Mint", "18 Sarah"),
        ("Linux Mint", "19 Tara"),
        ("Linux Mint", "20 Ulyana"),
        ("Linux Mint", "21 Vanessa"),
        ("elementary OS", "5 Hera"),
        ("elementary OS", "6 Odin"),
        ("Pop!_OS", "20.04"),
        ("Pop!_OS", "22.04"),
        ("openSUSE Leap", "15.0"),
        ("openSUSE Leap", "15.3"),
        ("SUSE Enterprise", "15 SP1"),
        ("FreeBSD", "11.4"),
        ("FreeBSD", "12.3"),
        ("FreeBSD", "13.0"),
        ("FreeBSD", "14.0"),
        ("OpenBSD", "6.7"),
        ("OpenBSD", "7.0"),
        ("NetBSD", "9.2"),
        ("Solaris", "10"),
        ("Solaris", "11.4"),
        ("Haiku", "R1/beta3"),
        ("BeOS", "R5"),
        ("MorphOS", "3.18"),
        ("AROS", "2019"),
        ("ReactOS", "0.4.13"),
        ("QNX", "7.0"),
        ("Tizen", "5.5"),
        ("HarmonyOS", "2.0"),
        ("KaiOS", "2.5"),
        ("Raspberry Pi OS", "9 stretch"),
        ("Raspberry Pi OS", "10 buster"),
        ("Raspberry Pi OS", "11 bullseye"),
        ("Puppy Linux", "9.5"),
        ("Alpine Linux", "3.18.0"),
        ("Gentoo", "2023.0"),
        ("Slackware", "14.2"),
        ("TV OS", "Samsung Tizen 6"),
        ("Amazon Fire OS", "7"),
        ("MS-DOS", "6.22"),
        ("AmigaOS", "3.1"),
        ("Commodore", "64 OS"),
    ]
    os_name, os_version = random.choice(os_choices)

    version = f"{os_name} {os_version}"
    return version


def run_config():
    """Load configurator.py"""
    from . import configurator

    return configurator.api_config(None)


def get_config_key(key: str) -> typing.Union[str, bool]:
    """
    Parse and return key from config
    :param key: Key name in config
    :return: Value of config key or `False`, if it doesn't exist
    """
    try:
        return json.loads(CONFIG_PATH.read_text()).get(key, False)
    except FileNotFoundError:
        return False


def save_config_key(key: str, value: str) -> bool:
    """
    Save `key` with `value` to config
    :param key: Key name in config
    :param value: Desired value in config
    :return: `True` on success, otherwise `False`
    """
    try:
        # Try to open our newly created json config
        config = json.loads(CONFIG_PATH.read_text())
    except FileNotFoundError:
        # If it doesn't exist, just default config to none
        # It won't cause problems, bc after new save
        # we will create new one
        config = {}

    # Assign config value
    config[key] = value
    # And save config
    CONFIG_PATH.write_text(json.dumps(config, indent=4))
    return True


def gen_port(cfg: str = "port", no8080: bool = False) -> int:
    """
    Generates random free port in case of VDS.
    In case of Docker, also return 8080, as it's already exposed by default.
    :returns: Integer value of generated port
    """
    if "DOCKER" in os.environ and not no8080:
        return 8080

    # But for own server we generate new free port, and assign to it
    if port := get_config_key(cfg):
        return port

    # If we didn't get port from config, generate new one
    # First, try to randomly get port
    while port := random.randint(1024, 65536):
        if socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(
            ("localhost", port)
        ):
            break

    return port


def parse_arguments():
    """
    Parses the arguments
    :returns: Dictionary with arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        dest="port",
        action="store",
        default=gen_port(),
        type=int,
    )
    parser.add_argument("--phone", "-p", action="append")
    parser.add_argument("--no-web", dest="disable_web", action="store_true")
    parser.add_argument(
        "--qr-login",
        dest="qr_login",
        action="store_true",
        help=(
            "Use QR code login instead of phone number (will only work if scanned from"
            " another device)"
        ),
    )
    parser.add_argument(
        "--data-root",
        dest="data_root",
        default="",
        help="Root path to store session files in",
    )
    parser.add_argument(
        "--no-auth",
        dest="no_auth",
        action="store_true",
        help="Disable authentication and API token input, exitting if needed",
    )
    parser.add_argument(
        "--proxy-host",
        dest="proxy_host",
        action="store",
        help="MTProto proxy host, without port",
    )
    parser.add_argument(
        "--proxy-port",
        dest="proxy_port",
        action="store",
        type=int,
        help="MTProto proxy port",
    )
    parser.add_argument(
        "--proxy-secret",
        dest="proxy_secret",
        action="store",
        help="MTProto proxy secret",
    )
    parser.add_argument(
        "--root",
        dest="disable_root_check",
        action="store_true",
        help="Disable `force_insecure` warning",
    )
    parser.add_argument(
        "--sandbox",
        dest="sandbox",
        action="store_true",
        help="Die instead of restart",
    )
    parser.add_argument(
        "--proxy-pass",
        dest="proxy_pass",
        action="store_true",
        help="Open proxy pass tunnel on start (not needed on setup)",
    )
    parser.add_argument(
        "--no-tty",
        dest="tty",
        action="store_false",
        default=True,
        help="Do not print colorful output using ANSI escapes",
    )
    arguments = parser.parse_args()
    logging.debug(arguments)
    return arguments


class SuperList(list):
    """
    Makes able: await self.allclients.send_message("foo", "bar")
    """

    def __getattribute__(self, attr: str) -> typing.Any:
        if hasattr(list, attr):
            return list.__getattribute__(self, attr)

        for obj in self:
            attribute = getattr(obj, attr)
            if callable(attribute):
                if asyncio.iscoroutinefunction(attribute):

                    async def foobar(*args, **kwargs):
                        return [await getattr(_, attr)(*args, **kwargs) for _ in self]

                    return foobar
                return lambda *args, **kwargs: [
                    getattr(_, attr)(*args, **kwargs) for _ in self
                ]

            return [getattr(x, attr) for x in self]


class InteractiveAuthRequired(Exception):
    """Is being rased by Telethon, if phone is required"""


def raise_auth():
    """Raises `InteractiveAuthRequired`"""
    raise InteractiveAuthRequired()


class Heroku:
    """Main userbot instance, which can handle multiple clients"""

    def __init__(self):
        global BASE_DIR, BASE_PATH, CONFIG_PATH
        self.omit_log = False
        self.arguments = parse_arguments()
        if self.arguments.data_root:
            BASE_DIR = self.arguments.data_root
            BASE_PATH = Path(BASE_DIR)
            CONFIG_PATH = BASE_PATH / "config.json"
        try:
            self.loop = asyncio.get_running_loop()
            
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.clients = SuperList()
        self.ready = asyncio.Event()
        self._read_sessions()
        self._get_api_token()
        self._get_proxy()

    def _get_proxy(self):
        """
        Get proxy tuple from --proxy-host, --proxy-port and --proxy-secret
        and connection to use (depends on proxy - provided or not)
        """
        if (
            self.arguments.proxy_host is not None
            and self.arguments.proxy_port is not None
            and self.arguments.proxy_secret is not None
        ):
            logging.warning("The use of MTProto proxies is not yet available")
            self.proxy = None
            return
            logging.debug(
                "Using proxy: %s:%s",
                self.arguments.proxy_host,
                self.arguments.proxy_port,
            )
            self.proxy = (
                (
                    self.arguments.proxy_host,
                    self.arguments.proxy_port,
                    self.arguments.proxy_secret,
                )
            )
            return

        self.proxy = None

    def _read_sessions(self):
        """Gets sessions from environment and data directory"""
        self.sessions: list[str] = []
        self.sessions += [
            session.rsplit(".session", maxsplit=1)[0]
            for session in filter(
                lambda f: f.startswith("heroku-") or f.startswith("hikka-") and f.endswith(".session"),
                os.listdir(BASE_DIR),
            )
        ]
        print(self.sessions)

    def _get_api_token(self):
        """Get API Token from disk or environment"""
        api_token_type = collections.namedtuple("api_token", ("ID", "HASH"))

        # Try to retrieve credintials from config, or from env vars
        try:
            # Legacy migration
            if not get_config_key("api_id"):
                api_id, api_hash = (
                    line.strip()
                    for line in (Path(BASE_DIR) / "api_token.txt")
                    .read_text()
                    .splitlines()
                )
                save_config_key("api_id", int(api_id))
                save_config_key("api_hash", api_hash)
                (Path(BASE_DIR) / "api_token.txt").unlink()
                logging.debug("Migrated api_token.txt to config.json")

            api_token = api_token_type(
                get_config_key("api_id"),
                get_config_key("api_hash"),
            )
        except FileNotFoundError:
            try:
                from . import api_token
            except ImportError:
                try:
                    api_token = api_token_type(
                        os.environ["api_id"],
                        os.environ["api_hash"],
                    )
                except KeyError:
                    api_token = None

        self.api_token = api_token

    def _init_web(self):
        """Initialize web"""
        if (
            not web_available
            or getattr(self.arguments, "disable_web", False)
        ):
            self.web = None
            return

        self.web = core.Web(
            data_root=BASE_DIR,
            api_token=self.api_token,
            proxy=self.proxy,
        )

    async def _get_token(self):
        """Reads or waits for user to enter API credentials"""
        while self.api_token is None:
            if self.arguments.no_auth:
                return
            if self.web:
                await self.web.start(self.arguments.port, proxy_pass=True)
                await self._web_banner()
                await self.web.wait_for_api_token_setup()
                self.api_token = self.web.api_token
            else:
                run_config()
                importlib.invalidate_caches()
                self._get_api_token()

    async def save_client_session(
        self,
        client: CustomClient,
        *,
        delay_restart: bool = False,
    ):
        if hasattr(client, "tg_id"):
            telegram_id = client.tg_id
        else:
            if not (me := await client.get_me()):
                raise RuntimeError("Attempted to save non-inited session")

            telegram_id = me.id
            client._tg_id = telegram_id
            client.tg_id = telegram_id
            client.hikka_me = me
            client.heroku_me = me

        session = f"heroku-{telegram_id}"
        init_kwargs = client._export_init_kwargs()
        session_str = await client.export_session_string()

        cli = CustomClient(
            session,
            **init_kwargs
        )

        await client.stop()

        storage = SQLiteStringStorage(cli)
        await storage.import_session_string(session_str)
        cli.storage = storage

        await cli.connect()

        if not delay_restart:
            restart()

        # Set db attribute to this client in order to save
        # custom bot nickname from web
        cli.heroku_db = database.Database(cli)
        await cli.heroku_db.init()

        try:
            db = cli.heroku_db
            existing = db.get("heroku.inline", "custom_bot", False)
        except Exception:
            existing = False

        if getattr(self, "arguments", None) and getattr(self.arguments, "tty", False) and not existing:
            while (bot := input("You can enter a custom bot username or leave it empty and Heroku will generate a random one: ")):
                bot = bot.strip()
                bot = bot.lstrip("@")
                if any(ch not in (string.ascii_letters + string.digits + "_") for ch in bot):
                    print("Invalid username: use only ASCII letters, digits and underscore (_).")
                    continue
                if not (bot.lower().endswith("bot")):
                    print("Invalid username: must end with 'bot'.")
                    continue
                try:
                    if await self._check_bot(cli, bot):
                        db.set("heroku.inline", "custom_bot", bot)
                        print("Bot username saved!")
                        break
                    else:
                        print("Bot username is occupied. Try again or leave it empty")
                        continue
                except Exception:
                    print("Something went wrong")

        if delay_restart:
            await cli.disconnect()
            await asyncio.sleep(3600)  # Will be restarted from web anyway

    async def _web_banner(self):
        """Shows web banner"""
        logging.info("🔎 Web mode ready for configuration")
        logging.info("🔗 Please visit %s", self.web.url)

    async def wait_for_web_auth(self, token: str) -> bool:
        """
        Waits for web auth confirmation in Telegram
        :param token: Token to wait for
        :return: True if auth was successful, False otherwise
        """
        timeout = 5 * 60
        polling_interval = 1
        for _ in range(timeout * polling_interval):
            await asyncio.sleep(polling_interval)

            for client in self.clients:
                if client.loader.inline.pop_web_auth_token(token):
                    return True

        return False

    async def _phone_login(self, client: CustomClient) -> bool:
        # phone = input(
        #     "\033[0;96mEnter phone: \033[0m"
        #     if self.arguments.tty
        #     else "Enter phone: "
        # )

        await client.start()

        me = await client.get_me()
        telegram_id = me.id
        client._tg_id = telegram_id
        client.tg_id = telegram_id
        client.hikka_me = me
        client.heroku_me = me

        db = database.Database(client)
        await db.init()

        while (bot := input("You can enter a custom bot username or leave it empty and Heroku will generate a random one: ")):
            try:
                if await self._check_bot(client, bot):
                    db.set("heroku.inline", "custom_bot", bot)
                    print("Bot username saved!")
                    break
                else:
                    print("Bot username is occupied. Try again or leave it empty")
                    continue
            except Exception:
                print("Something went wrong")

        await self.save_client_session(client)
        self.clients += [client]
        return True

    async def _check_bot(
        self,
        client: CustomClient,
        username: str,
    ) -> bool:
        url: str = (
            await client.open_web_app(
                chat_id="@botfather",
                bot_user_id="@botfather",
                platform="android",
                url="https://webappinternal.telegram.org/botfather?"
            )
        )
        for _ in range(5):
            await asyncio.sleep(1.5)
            try:
                result = await inutils._get_webapp_session(None, url)
            except:
                continue
            break
        else:
            print("Can't check bot. WebApp is not available now")
            return False

        session, _hash = result
        main_url = url.split("?")[0]

        if await TokenObtainment._check_bot(None, session, main_url, _hash, username):
            return True

        try:
            await client.get_chat(f"{username}", force_full=False)
        except:
            return True


    async def _initial_setup(self) -> bool:
        """Responsible for first start"""
        if self.arguments.no_auth:
            return False

        if not self.web:
            client = CustomClient(
                "",
                self.api_token.ID,
                self.api_token.HASH,
                in_memory=True,
                proxy = self.proxy,
                device_model = get_app_name(),
                system_version = generate_random_system_version(),
                app_version = ".".join(map(str, __version__)) + " x64",
                lang_code = "en",
                system_lang_code = "en-US",
            )

            print(
                (
                    "\033[0;96m{}\033[0m" if self.arguments.tty else "{}"
                ).format(
                    "You can use QR-code to login from another device (your friend's"
                    " phone, for example)."
                )
            )

            user_choice = input(
                "\033[0;96mUse QR code? [y/N]: \033[0m"
                if self.arguments.tty
                else "Use QR code? [y/N]: "
            ).lower()

            match user_choice:
                case "y":
                    await client.connect()
                case _:
                    return await self._phone_login(client)

            print("\033[0;96mLoading QR code...\033[0m")
            qr_login = QRLogin(client)

            def print_qr():
                qr = QRCode()
                qr.add_data(qr_login.url)
                print("\033[2J\033[3;1f")
                qr.print_ascii(invert=True)
                print("\033[0;96mScan the QR code above to log in.\033[0m")
                print("\033[0;96mPress Ctrl+C to cancel.\033[0m")

            async def qr_login_poll() -> bool:
                logged_in = False
                while not logged_in:
                    try:
                        logged_in = await qr_login.wait(10)
                    except asyncio.TimeoutError:
                        try:
                            await qr_login.recreate()
                            print_qr()
                        except SessionPasswordNeeded:
                            return True
                    except SessionPasswordNeeded:
                        return True
                    except KeyboardInterrupt:
                        print("\033[2J\033[3;1f")
                        return None

                return False

            match await qr_login_poll():
                case None:
                    return await self._phone_login(client)

                case True:
                    print_banner("2fa.txt")
                    password = await client.invoke(GetPassword())
                    while True:
                        _2fa = getpass(
                            f"\033[0;96mEnter 2FA password ({password.hint}): \033[0m"
                            if self.arguments.tty
                            else f"Enter 2FA password ({password.hint}): "
                        )
                        try:
                            await client.check_password(_2fa)
                        except BadRequest:
                            print("\033[0;91mInvalid 2FA password!\033[0m")
                        except FloodWait as e:
                            seconds, minutes, hours = (
                                e.value % 3600 % 60,
                                e.value % 3600 // 60,
                                e.value // 3600,
                            )
                            seconds, minutes, hours = (
                                f"{seconds} second(-s)",
                                f"{minutes} minute(-s) " if minutes else "",
                                f"{hours} hour(-s) " if hours else "",
                            )
                            print(
                                "\033[0;91mYou got FloodWait error! Please wait"
                                f" {hours}{minutes}{seconds}\033[0m"
                            )
                            return False
                        else:
                            break

                case False:
                    pass

            print_banner("success.txt")
            print("\033[0;92mLogged in successfully!\033[0m")
            cli = await self.save_client_session(client)
            self.clients += [cli]
            return True

        if not self.web.running.is_set():
            await self.web.start(
                self.arguments.port,
                proxy_pass=True,
            )
            await self._web_banner()

        await self.web.wait_for_clients_setup()

        return True

    async def _init_clients(self) -> bool:
        """
        Reads session from disk and inits them
        :returns: `True` if at least one client started successfully
        """
        for session in self.sessions.copy():
            try:
                client = CustomClient(
                    session,
                    self.api_token.ID,
                    self.api_token.HASH,
                    proxy=self.proxy,
                    device_model=get_app_name(),
                    system_version=generate_random_system_version(),
                    app_version=".".join(map(str, __version__)) + " x64",
                    lang_code="en",
                    system_lang_code="en-US",
                )
                # if session.server_address == "0.0.0.0":
                #     patcher.patch(client, session)

                await client.connect()
                client.phone_number = "None"

                self.clients += [client]
            except sqlite3.OperationalError:
                logging.error(
                    "Check that this is the only instance running. "
                    "If that doesn't help, delete the file '%s'",
                    session,
                )
                continue
            except (TypeError, AuthKeyDuplicated):
                Path(session).unlink(missing_ok=True)
                self.sessions.remove(session)
            except (ValueError, ApiIdInvalid):
                # Bad API hash/ID
                run_config()
                return False
            except PhoneNumberInvalid:
                logging.error(
                    "Phone number is incorrect. Use international format (+XX...) "
                    "and don't put spaces in it."
                )
                self.sessions.remove(session)
            except InteractiveAuthRequired:
                logging.error(
                    "Session %s was terminated and re-auth is required",
                    session,
                )
                self.sessions.remove(session)

        return bool(self.sessions)

    async def amain_wrapper(self, client: CustomClient):
        """Wrapper around amain"""
        async with client:
            first = True
            me = await client.get_me()
            client._tg_id = me.id
            client.tg_id = me.id
            client.hikka_me = me
            client.heroku_me = me

            async with aiohttp.ClientSession() as session:
                async with session.get("https://raw.githubusercontent.com/coddrago/modules-web/main/mods/ids/allowed_ids.txt") as response:
                    if response.status == 200:
                        content = await response.text()
                        allowed_ids = [int(line.strip()) for line in content.split('\n') if line.strip()]
                    else:
                        logging.error(f"Exception on loading allowed beta testers ids: {response.status}")
                        return []

            await asyncio.gather(*[version.check_branch((await client.get_me()).id, allowed_ids) for client in self.clients])

            while await self.amain(first, client):
                first = False

    async def _badge(self, client: CustomClient):
        """Call the badge in shell"""
        try:
            import git

            repo = git.Repo()

            build = utils.get_git_hash()
            diff = repo.git.log([f"HEAD..origin/{version.branch}", "--oneline"])
            upd = "Update required" if diff else "Up-to-date"
            pref = client.heroku_db.get("heroku.main", "command_prefix", None)

            logo = (
                "                          _           \n"
               r"  /\  /\ ___  _ __  ___  | | __ _   _ ""\n"
               r" / /_/ // _ \| '__|/ _ \ | |/ /| | | |""\n"
                "/ __  /|  __/| |  | (_) ||   < | |_| |\n"
               r"\/ /_/  \___||_|   \___/ |_|\_\ \__,_|""\n\n"
                f"• Build: {build[:7]}\n"
                f"• Version: {'.'.join(list(map(str, list(__version__))))}\n"
                f"• {upd}\n"
            )
            web_url = ""
            if not self.omit_log:
                print(logo)
                if self.web and hasattr(self.web, "url"):
                    web_url = (
                        f"🔗 Web url: {self.web.url}"
                    )
                    logging.debug(
                        "\n🪐 Heroku %s #%s (%s) started\n%s",
                        ".".join(list(map(str, list(__version__)))),
                        build[:7],
                        upd,
                        web_url,
                    )
                    self.omit_log = True

            await client.heroku_inline.bot.send_photo(
                logging.getLogger().handlers[0].get_logid_by_client(client.tg_id),
                "https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/heroku_started.png",
                caption=(
                    "🪐 <b>Heroku {} started!</b>\n\n⚙ <b>GitHub commit SHA: <a"
                    ' href="https://github.com/coddrago/Heroku/commit/{}">{}</a></b>\n🔎'
                    " <b>Update status: {}</b>\n<b>{}</b>\n🕶 <b>Prefix:</b> <code>{}</code>"
                ).format(
                    ".".join(list(map(str, list(__version__)))),
                    build,
                    build[:7],
                    upd,
                    web_url,
                    "." if pref is None else pref,
                ),
                message_thread_id=logging.getLogger().handlers[0].get_logs_topic_id_by_client(client.tg_id),
            )
            logging.debug(
                "· Started for %s · Prefix: «%s» ·",
                client.tg_id,
                client.heroku_db.get(__name__, "command_prefix", False) or ".",
            )
        except Exception:
            logging.exception("Badge error")

    async def _add_dispatcher(
        self,
        client: CustomClient,
        modules: loader.Modules,
        db: database.Database,
    ):
        """Inits and adds dispatcher instance to client"""
        dispatcher = CommandDispatcher(modules, client, db)
        client.dispatcher = dispatcher
        modules.check_security = dispatcher.check_security

        client.add_handler(
            handlers.MessageHandler(dispatcher.handle_incoming),
        )

        client.add_handler(
            dispatcher.handle_incoming,
            events.ChatAction,
        )

        client.add_handler(
            handlers.MessageHandler(
                dispatcher.handle_command,
                filters=~filters.forwarded
            )
        )

        client.add_handler(
            handlers.EditedMessageHandler(dispatcher.handle_command),
        )

        client.add_handler(
            handlers.RawUpdateHandler(dispatcher.handle_raw),
        )

    async def amain(self, first: bool, client: CustomClient):
        """Entrypoint for async init, run once for each user"""
        client.parse_mode = ParseMode.HTML
        await client.start()

        db = database.Database(client)
        client.heroku_db = db
        await db.init()

        logging.debug("Got DB")
        logging.debug("Loading logging config...")

        translator = Translator(client, db)

        await translator.init()
        modules = loader.Modules(client, db, self.clients, translator)
        client.loader = modules

        if self.web:
            await self.web.add_loader(client, modules, db)
            await self.web.start_if_ready(
                len(self.clients),
                self.arguments.port,
                proxy_pass=self.arguments.proxy_pass,
            )

        await self._add_dispatcher(client, modules, db)

        await modules.register_all(None)
        modules.send_config()
        await modules.send_ready()

        if first:
            await self._badge(client)

        await idle.idle()

    async def _main(self):
        """Main entrypoint"""
        self._init_web()
        inital_web = False
        save_config_key("port", self.arguments.port)
        await self._get_token()

        if (
            not self.clients and not self.sessions or not await self._init_clients()
        ) and not (inital_web := await self._initial_setup()):
            return
        if inital_web:
            async def scheduled_web_stop():
                await asyncio.sleep(delay=120)
                await self.web.stop()
                logging.debug("inital web was stopped for security reasons")
            asyncio.create_task(scheduled_web_stop())

        self.loop.set_exception_handler(
            lambda _, x: logging.error(
                "Exception on event loop! %s",
                x["message"],
                exc_info=x.get("exception", None),
            )
        )

        await asyncio.gather(*[self.amain_wrapper(client) for client in self.clients])

    async def _shutdown_handler(self):
        for client in self.clients:
            inline = getattr(client.loader, "inline", None)
            if inline:
                for t in (inline._task, inline._cleaner_task):
                    if t:
                        t.cancel()
                try:
                    await inline._dp.stop_polling()
                    await inline.bot.session.close()
                except: pass
        for c in self.clients:
            await c.disconnect()
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
        self.loop.stop()

    def main(self):
        """Main entrypoint"""
        if sys.platform != "win32":
            try:
                self.loop.add_signal_handler(
                    signal.SIGINT,
                    lambda: asyncio.create_task(self._shutdown_handler())
                )
            except NotImplemented:
                logging.warning("Signal handlers not supported on this platform.")
        else:
            logging.info("Running on Windows — skipping signal handler.")

        try:
            self.loop.run_until_complete(self._main())
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received.")
            self.loop.run_until_complete(self._shutdown_handler())
        except Exception as e:
            logging.exception("Unexpected exception in main loop: %s", e)
        finally:
            logging.info("Bye!")
            try:
                self.loop.run_until_complete(self._shutdown_handler())
            except:
                pass

# pyrogram.extensions.html.CUSTOM_EMOJIS = not get_config_key("disable_custom_emojis")

heroku = Heroku()
