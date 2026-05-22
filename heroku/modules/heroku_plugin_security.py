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

import difflib
import typing

from .. import loader, utils


def allow_session_hash(db, module_hash: str) -> typing.List[str]:
    if not module_hash:
        return []

    session_allow = db.get("HerokuPluginSecurity", "session_allow", [])
    if not isinstance(session_allow, list):
        session_allow = (
            list(session_allow) if isinstance(session_allow, (tuple, set)) else []
        )

    if module_hash not in session_allow:
        session_allow.append(module_hash)
        db.set("HerokuPluginSecurity", "session_allow", session_allow)

    loader.set_session_access_hashes(session_allow)
    return session_allow


@loader.tds
class HerokuPluginSecurity(loader.Module):
    """Manage external module security overrides"""

    strings = {"name": "HerokuPluginSecurity"}

    async def client_ready(self):
        self._internalized = self.pointer("internalized", [])
        self._session_allow = self.pointer("session_allow", [])
        self._apply_internalized()
        self._sync_session_allowlist()

    def _sync_session_allowlist(self):
        loader.set_session_access_hashes(self._session_allow)

    @staticmethod
    def _real_allmodules(mod) -> "loader.Modules":
        if isinstance(mod.allmodules, loader.SafeAllModulesProxy):
            return mod.allmodules._get_real_allmodules()

        return mod.allmodules

    def _get_module_hash(self, mod) -> typing.Optional[str]:
        return loader.get_module_hash(mod)

    def _get_module_name(self, mod) -> str:
        return mod.__class__.__name__

    def _find_module_by_hash(self, module_hash: str):
        for mod in self.allmodules.modules:
            if self._get_module_hash(mod) == module_hash:
                return mod

        return None

    def _find_module_by_name(self, name: str):
        for mod in self.allmodules.modules:
            if mod.__class__.__name__.lower() == name.lower():
                return mod
        return None

    def _internalized_has(self, name: str) -> bool:
        name_l = name.lower()
        return any(item.lower() == name_l for item in self._internalized)

    def _internalized_add(self, name: str) -> None:
        if not self._internalized_has(name):
            self._internalized.append(name)

    def _internalized_remove(self, name: str) -> None:
        for item in list(self._internalized):
            if item.lower() == name.lower():
                self._internalized.remove(item)
                return

    def _normalize_internalized(self) -> None:
        if not self._internalized:
            return

        names = {
            self._get_module_name(m).lower(): self._get_module_name(m)
            for m in self.allmodules.modules
        }
        normalized = []

        for item in list(self._internalized):
            if not isinstance(item, str):
                continue

            item_l = item.lower()

            if item_l in names:
                normalized.append(names[item_l])
                continue

            mod = self._find_module_by_hash(item)

            if mod:
                normalized.append(self._get_module_name(mod))

        if not normalized:
            return

        seen = set()
        deduped = []

        for name in normalized:
            name_l = name.lower()
            if name_l in seen:
                continue

            seen.add(name_l)
            deduped.append(name)

        if deduped != list(self._internalized):
            self._internalized.data = deduped

    def _resolve_module(self, query: str):
        mod = self._find_module_by_name(query)

        if mod:
            return mod, None

        names = [m.__class__.__name__ for m in self.allmodules.modules]
        closest = (difflib.get_close_matches(query, names, n=1, cutoff=0.3) or [None])[
            0
        ]

        return None, closest

    def _internalize(self, mod) -> bool:
        if not getattr(mod, "is_external", False):
            return False

        real_allmodules = self._real_allmodules(mod)
        mod.is_external = False
        mod.allmodules = real_allmodules
        mod.client = real_allmodules.client
        mod._client = real_allmodules.client
        mod.allclients = real_allmodules.allclients
        mod.db = real_allmodules.db
        mod._db = real_allmodules.db
        mod.lookup = mod.allmodules.lookup
        mod.get_prefix = mod.allmodules.get_prefix
        mod.get_prefixes = mod.allmodules.get_prefixes
        mod.inline = mod.allmodules.inline
        mod.tg_id = mod._client.tg_id
        mod._tg_id = mod._client.tg_id

        return True

    def _externalize(self, mod) -> bool:
        if getattr(mod, "is_external", False):
            return False

        real_allmodules = self._real_allmodules(mod)
        origin = getattr(mod, "__origin__", "")
        safe_client = loader.SafeClientProxy(real_allmodules.client, origin)
        safe_allclients = [
            loader.SafeClientProxy(c, origin) for c in real_allmodules.allclients
        ]
        safe_db = loader.SafeDatabaseProxy(real_allmodules.db, origin)
        safe_inline = loader.SafeInlineProxy(real_allmodules.inline, origin)

        mod.is_external = True
        mod.allmodules = loader.SafeAllModulesProxy(
            real_allmodules,
            safe_client,
            safe_allclients,
            safe_db,
            safe_inline,
        )
        mod.client = safe_client
        mod._client = safe_client
        mod.allclients = safe_allclients
        mod.db = safe_db
        mod._db = safe_db
        mod.lookup = mod.allmodules.lookup
        mod.get_prefix = mod.allmodules.get_prefix
        mod.get_prefixes = mod.allmodules.get_prefixes
        mod.inline = mod.allmodules.inline
        mod.tg_id = mod._client.tg_id
        mod._tg_id = mod._client.tg_id

        return True

    def _apply_internalized(self):
        self._normalize_internalized()

        internalized = {name.lower() for name in self._internalized}

        for mod in self.allmodules.modules:
            mod_name = self._get_module_name(mod)
            if mod_name.lower() in internalized:
                self._internalize(mod)

    @loader.command(ru_doc="<name> | Разрешить модулю полный доступ к юзерботу")
    async def unexternal(self, message):
        """<name> | Grant full userbot access for module"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, self.strings("no_hash"))
            return

        query = args.strip()
        mod, closest = self._resolve_module(query)

        if not mod:
            if closest:
                await utils.answer(
                    message,
                    self.strings("hash_not_found_suggest").format(
                        utils.escape_html(closest)
                    ),
                )
            else:
                await utils.answer(message, self.strings("hash_not_found"))
            return

        changed = self._internalize(mod)
        module_name = self._get_module_name(mod)
        module_hash = self._get_module_hash(mod)

        self._internalized_add(module_name)

        if module_hash and module_hash not in self._session_allow:
            self._session_allow.append(module_hash)
            self._sync_session_allowlist()

        await utils.answer(
            message,
            self.strings("external_removed" if changed else "already_internal").format(
                mod.__class__.__name__
            ),
        )

    @loader.command(ru_doc="<name> | Запретить модулю полный доступ к юзерботу")
    async def external(self, message):
        """<name> | Deny full userbot access for module"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, self.strings("no_hash"))
            return

        query = args.strip()
        mod, closest = self._resolve_module(query)

        if not mod:
            if closest:
                await utils.answer(
                    message,
                    self.strings("hash_not_found_suggest").format(
                        utils.escape_html(closest)
                    ),
                )
            else:
                await utils.answer(message, self.strings("hash_not_found"))
            return

        changed = self._externalize(mod)
        module_name = self._get_module_name(mod)
        module_hash = self._get_module_hash(mod)

        self._internalized_remove(module_name)

        if module_hash and module_hash in self._session_allow:
            self._session_allow.remove(module_hash)
            self._sync_session_allowlist()

        await utils.answer(
            message,
            self.strings("external_restored" if changed else "already_external").format(
                mod.__class__.__name__
            ),
        )
