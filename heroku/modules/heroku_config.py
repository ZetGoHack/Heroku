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
import contextlib
import functools
import typing
from math import ceil

from herokutl.tl.types import Message
from herokutl.extensions import html

from .. import loader, translations, utils
from ..inline.types import InlineCall
from ..types import HerokuReplyMarkup

# Everywhere in this module, we use the following naming convention:
# `obj_type` of non-core module = False
# `obj_type` of core module = True
# `obj_type` of library = "library"


ROW_SIZE = 3
NUM_ROWS = 5


class _InlineFormDraft:
    inline_message_id = None

    def __init__(self):
        self.text: str | None = None
        self.reply_markup: HerokuReplyMarkup | None = None
        self.kwargs: dict[str, typing.Any] = {}

    async def edit(
        self,
        text: str | None = None,
        reply_markup: HerokuReplyMarkup | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        if text is None:
            text = kwargs.pop("text", None)

        if reply_markup is None and args:
            reply_markup = args[0]

        self.text = text
        self.reply_markup = reply_markup
        self.kwargs = kwargs


@loader.tds
class HerokuConfigMod(loader.Module):
    """Interactive configurator for Heroku Userbot"""

    strings = {"name": "HerokuConfig"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "cfg_emoji",
                "🪐",
                "Change emoji when opening config",
                validator=loader.validators.String(),
            ),
        )

    @staticmethod
    def prep_value(value: typing.Any) -> typing.Any:
        if isinstance(value, str):
            return f"<b><code>{utils.escape_html(value.strip())}</code></b>"

        if isinstance(value, list) and value:
            return (
                "<b><code>[</code></b>\n    "
                + "\n    ".join(
                    [
                        f"<b><code>{utils.escape_html(str(item))}</code></b>"
                        for item in value
                    ]
                )
                + "\n<b><code>]</code></b>"
            )

        return f"<b><code>{utils.escape_html(value)}</code></b>"

    def hide_value(self, value: typing.Any) -> str:
        if isinstance(value, list) and value:
            return self.prep_value(["*" * len(str(i)) for i in value])

        return self.prep_value("*" * len(str(value)))

    def _get_value(self, mod: str, option: str) -> str:
        return (
            self.prep_value(self.lookup(mod).config[option])
            if (
                not self.lookup(mod).config._config[option].validator
                or self.lookup(mod).config._config[option].validator.internal_id
                != "Hidden"
            )
            else self.hide_value(self.lookup(mod).config[option])
        )

    def _guess_back_to_page(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> dict:
        kwargs = {"obj_type": obj_type}
        cat = self.lookup(mod).config.get_category(option)
        if cat is not None:
            kwargs["category"] = cat.name
        return kwargs

    async def inline__set_config(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__reset_default(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        mod_instance = self.lookup(mod)
        mod_instance.config[option] = mod_instance.config.getdef(option)

        await call.edit(
            self.strings[
                "option_reset" if isinstance(obj_type, bool) else "option_reset_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__set_bool(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        validator = self.lookup(mod).config._config[option].validator
        doc = utils.escape_html(
            next(
                (
                    validator.doc[lang]
                    for original_lang in self._db.get(
                        translations.__name__, "lang", "en"
                    ).split(" ")
                    for lang in translations.iter_language_codes(original_lang)
                    if lang in validator.doc
                ),
                validator.doc["en"],
            )
        )

        await call.edit(
            self.strings[
                (
                    "configuring_option"
                    if isinstance(obj_type, bool)
                    else "configuring_option_lib"
                )
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                utils.escape_html(self.lookup(mod).config.getdoc(option)),
                self.prep_value(self.lookup(mod).config.getdef(option)),
                (
                    self.prep_value(self.lookup(mod).config[option])
                    if not validator or validator.internal_id != "Hidden"
                    else self.hide_value(self.lookup(mod).config[option])
                ),
                (
                    self.strings["typehint"].format(
                        doc,
                        eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                    )
                    if doc
                    else ""
                ),
            ),
            reply_markup=self._generate_bool_markup(mod, option, obj_type),
        )

        await call.answer("✅")

    def _generate_bool_markup(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        return [
            [
                *(
                    [
                        {
                            "text": f"❌ {self.strings['set']} `False`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, False),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    else [
                        {
                            "text": f"✅ {self.strings['set']} `True`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, True),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__add_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            with contextlib.suppress(Exception):
                query = ast.literal_eval(query)

            if isinstance(query, (set, tuple)):
                query = list(query)

            if not isinstance(query, list):
                query = [query]

            self.lookup(mod).config[option] = self.lookup(mod).config[option] + query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__remove_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            with contextlib.suppress(Exception):
                query = ast.literal_eval(query)

            if isinstance(query, (set, tuple)):
                query = list(query)

            if not isinstance(query, list):
                query = [query]

            query = list(map(str, query))

            old_config_len = len(self.lookup(mod).config[option])

            self.lookup(mod).config[option] = [
                i for i in self.lookup(mod).config[option] if str(i) not in query
            ]

            if old_config_len == len(self.lookup(mod).config[option]):
                raise loader.validators.ValidationError(
                    f"Nothing from passed value ({self.prep_value(query)}) is not in"
                    " target list"
                )
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    def _generate_series_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["remove_item_btn"],
                            "input": self.strings["remove_item_desc"],
                            "handler": self.inline__remove_item,
                            "args": (mod, option, call.inline_message_id),
                            "kwargs": {"obj_type": obj_type},
                        },
                        {
                            "text": self.strings["add_item_btn"],
                            "input": self.strings["add_item_desc"],
                            "handler": self.inline__add_item,
                            "args": (mod, option, call.inline_message_id),
                            "kwargs": {"obj_type": obj_type},
                        },
                    ]
                    if self.lookup(mod).config[option]
                    else []
                ),
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def _choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

        await call.answer("✅")

    async def _multi_choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            if value in self.lookup(mod).config._config[option].value:
                self.lookup(mod).config._config[option].value.remove(value)
            else:
                self.lookup(mod).config._config[option].value += [value]

            self.lookup(mod).config.reload()
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await self.inline__configure_option(
            call, mod=mod, config_opt=option, force_hidden=False, obj_type=obj_type
        )
        await call.answer("✅")

    def _generate_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if self.lookup(mod).config[option] == value else '🔘'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    def _generate_multi_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        return [
            [
                {
                    "text": self.strings["enter_value_btn"],
                    "input": self.strings["enter_value_desc"],
                    "handler": self.inline__set_config,
                    "args": (mod, option, call.inline_message_id),
                    "kwargs": {"obj_type": obj_type},
                }
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if value in self.lookup(mod).config[option] else '◻️'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._multi_choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__configure_option(
        self,
        call: InlineCall,
        page: int = 0,
        mod: str = "",
        config_opt: str = "",
        force_hidden: bool = False,
        obj_type: bool | str = False,
    ):
        module = self.lookup(mod)
        args = [
            utils.escape_html(config_opt),
            utils.escape_html(mod),
            utils.escape_non_html(module.config.getdoc(config_opt)),
            self.prep_value(module.config.getdef(config_opt)),
            (
                self.prep_value(module.config[config_opt])
                if not module.config._config[config_opt].validator
                or module.config._config[config_opt].validator.internal_id != "Hidden"
                or force_hidden
                else self.hide_value(module.config[config_opt])
            ),
        ]

        if (
            module.config._config[config_opt].validator
            and module.config._config[config_opt].validator.internal_id == "Hidden"
        ):
            additonal_button_row = (
                [
                    [
                        {
                            "text": self.strings["hide_value"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": False,
                            },
                        }
                    ]
                ]
                if force_hidden
                else [
                    [
                        {
                            "text": self.strings["show_hidden"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": True,
                            },
                        }
                    ]
                ]
            )
        else:
            additonal_button_row = []

        try:
            validator = module.config._config[config_opt].validator
            doc = utils.escape_html(
                next(
                    (
                        validator.doc[lang]
                        for original_lang in self._db.get(
                            translations.__name__, "lang", "en"
                        ).split(" ")
                        for lang in translations.iter_language_codes(original_lang)
                        if lang in validator.doc
                    ),
                    validator.doc["en"],
                )
            )
        except Exception:
            doc = None
            validator = None
            args += [""]
        else:
            args += [
                self.strings["typehint"].format(
                    doc,
                    eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                )
            ]
            match validator.internal_id:
                case "Boolean":
                    await call.edit(
                        self.strings[
                            (
                                "configuring_option"
                                if isinstance(obj_type, bool)
                                else "configuring_option_lib"
                            )
                        ].format(*args),
                        reply_markup=additonal_button_row
                        + self._generate_bool_markup(mod, config_opt, obj_type),
                    )
                    return
                case "Series":
                    await call.edit(
                        self.strings[
                            (
                                "configuring_option"
                                if isinstance(obj_type, bool)
                                else "configuring_option_lib"
                            )
                        ].format(*args),
                        reply_markup=additonal_button_row
                        + self._generate_series_markup(call, mod, config_opt, obj_type),
                    )
                    return
                case "Choice":
                    await call.edit(
                        self.strings[
                            (
                                "configuring_option"
                                if isinstance(obj_type, bool)
                                else "configuring_option_lib"
                            )
                        ].format(*args),
                        reply_markup=additonal_button_row
                        + self._generate_choice_markup(call, mod, config_opt, obj_type),
                    )
                    return
                case "MultiChoice":
                    await call.edit(
                        self.strings[
                            (
                                "configuring_option"
                                if isinstance(obj_type, bool)
                                else "configuring_option_lib"
                            )
                        ].format(*args),
                        reply_markup=additonal_button_row
                        + self._generate_multi_choice_markup(
                            call, mod, config_opt, obj_type
                        ),
                    )
                    return

        text = self.strings[
            (
                "configuring_option"
                if isinstance(obj_type, bool)
                else "configuring_option_lib"
            )
        ].format(*args)

        parsed_text, parsed_entities = html.parse(text)
        pages = list(utils.smart_split(parsed_text, parsed_entities))

        if len(pages) > 1:
            page = min(max(page, 0), len(pages) - 1)
            additonal_button_row += self.inline.build_pagination(
                callback=functools.partial(
                    self.inline__configure_option,
                    mod=mod,
                    config_opt=config_opt,
                    force_hidden=force_hidden,
                    obj_type=obj_type,
                ),
                total_pages=len(pages),
                current_page=page + 1,
            )
            text = pages[page]

        await call.edit(
            text,
            reply_markup=additonal_button_row
            + [
                [
                    {
                        "text": self.strings["enter_value_btn"],
                        "input": self.strings["enter_value_desc"],
                        "handler": self.inline__set_config,
                        "args": (mod, config_opt, call.inline_message_id),
                        "kwargs": {"obj_type": obj_type},
                    }
                ],
                [
                    {
                        "text": self.strings["set_default_btn"],
                        "callback": self.inline__reset_default,
                        "args": (mod, config_opt),
                        "kwargs": {"obj_type": obj_type},
                    }
                ],
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, config_opt, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ],
            ],
        )

    async def inline__configure(
        self,
        call: InlineCall,
        mod: str,
        obj_type: bool | str = False,
        folder: str | None = None,
        category: str | None = None,
    ):

        module = self.lookup(mod)
        grouped = module.config.grouped_options()

        def fmt_value(option: str) -> str:
            value = self._get_value(mod, option)
            if len(value) >= 200:
                value = list(utils.smart_split(*html.parse(value), 200))[0] + "..."
            return value

        close_btn = {
            "text": self.strings["close_btn"],
            "action": "close",
            "style": "danger",
        }

        if category is not None:
            params = list(grouped.get(category, []))
            option_lines = [
                f"▫️ <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            options_text = "\n".join(option_lines) if option_lines else "No options"

            cat_obj = module.config._categories.get(category)
            cat_doc = cat_obj.getdoc() if cat_obj else ""

            cat_text = self.strings[
                (
                    "configuring_category"
                    if isinstance(obj_type, bool)
                    else "configuring_category_lib"
                )
            ].format(
                utils.escape_html(mod),
                utils.escape_html(category),
                utils.escape_html(cat_doc),
                options_text,
            )

            return await call.edit(
                cat_text,
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__configure,
                            "args": (mod,),
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        elif folder is not None:
            params = list(module.config)
            option_lines = [
                f"▫️ <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            text = "\n".join(option_lines) if option_lines else "No options"

            return await call.edit(
                self.strings[
                    (
                        "configuring_mod"
                        if isinstance(obj_type, bool)
                        else "configuring_lib"
                    )
                ].format(utils.escape_html(mod), text),
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__global_config,
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        sections = []
        btns = []
        for section_name, section_params in grouped.items():
            if section_name is None:
                visible = [
                    p
                    for p in section_params
                    if not getattr(module.config._config.get(p), "folder", None)
                ]
                if not visible:
                    continue
                sections.append(
                    "\n".join(
                        "▫️ <code>{}</code>: {}".format(
                            utils.escape_html(p), fmt_value(p)
                        )
                        for p in visible
                    )
                )
                btns += [
                    {
                        "text": opt,
                        "callback": self.inline__configure_option,
                        "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": opt},
                    }
                    for opt in visible
                ]
            else:
                cat_lines = [
                    "∟ ▫️ <code>{}</code>: {}".format(
                        utils.escape_html(p), fmt_value(p)
                    )
                    for p in section_params
                ]
                cat_text = [
                    self.strings["category_header"].format(
                        utils.escape_html(section_name)
                    ),
                    "<blockquote expandable>" + "\n".join(cat_lines),
                    "</blockquote>",
                ]
                sections.append("\n".join(cat_text))
                btns.append(
                    {
                        "text": f"📂 {section_name}",
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "kwargs": {"obj_type": obj_type, "category": section_name},
                    }
                )

        text = "\n".join(sections).lstrip("\n") if sections else "No options"

        await call.edit(
            self.strings[
                "configuring_mod" if isinstance(obj_type, bool) else "configuring_lib"
            ].format(utils.escape_html(mod), text),
            reply_markup=list(utils.chunks(btns, 2))
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__global_config,
                        "style": "primary",
                        "kwargs": {"obj_type": obj_type},
                    },
                    close_btn,
                ]
            ],
        )

    def _get_all_folders(self) -> dict:
        folders = {}
        for mod in self.allmodules.modules:
            if not hasattr(mod, "config") or not mod.config:
                continue
            mod_name = (
                mod.strings("name") if callable(mod.strings) else mod.__class__.__name__
            )
            module_folders = set()
            for param in mod.config:
                config_value = mod.config._config.get(param)
                if (
                    config_value
                    and hasattr(config_value, "folder")
                    and config_value.folder
                ):
                    module_folders.add(config_value.folder)

            for folder_name in module_folders:
                if folder_name not in folders:
                    folders[folder_name] = {}
                folders[folder_name][mod_name] = [p for p in mod.config]
        try:
            preset_folders = self.db.get("presets", "folders")
        except Exception:
            preset_folders = {}

        if preset_folders:
            for folder_name, mod_list in preset_folders.items():
                if folder_name not in folders:
                    folders[folder_name] = {}
                for raw_mod in mod_list:
                    for mod in self.allmodules.modules:
                        try:
                            if mod.__class__.__name__.lower() == raw_mod.lower():
                                mod_name = (
                                    mod.strings("name")
                                    if callable(mod.strings)
                                    else mod.__class__.__name__
                                )
                                if mod_name not in folders[folder_name]:
                                    folders[folder_name][mod_name] = [
                                        p for p in mod.config
                                    ]
                                break
                        except Exception:
                            continue

        return folders

    async def inline__choose_category(self, call: Message | InlineCall):
        all_folders = self._get_all_folders()

        folder_btns = [
            {
                "text": f"📁 {folder_name}",
                "callback": self.inline__global_folder,
                "kwargs": {"folder": folder_name},
            }
            for folder_name in sorted(all_folders.keys())
        ]

        await utils.answer(
            call,
            self.strings["choose_core"],
            reply_markup=[
                [
                    {
                        "text": self.strings["builtin"],
                        "callback": self.inline__global_config,
                        "kwargs": {"obj_type": True},
                    },
                    {
                        "text": self.strings["external"],
                        "callback": self.inline__global_config,
                    },
                ],
                *(
                    [
                        [
                            {
                                "text": self.strings["libraries"],
                                "callback": self.inline__global_config,
                                "kwargs": {"obj_type": "library"},
                            }
                        ]
                    ]
                    if self.allmodules.libraries
                    and any(hasattr(lib, "config") for lib in self.allmodules.libraries)
                    else []
                ),
                *list(utils.chunks(folder_btns, 2)),
                [
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    }
                ],
            ],
        )

    async def _send_initial_config_form(
        self,
        message: Message,
        handler: typing.Callable[..., typing.Awaitable[typing.Any]],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        draft = _InlineFormDraft()
        await handler(draft, *args, **kwargs)

        if draft.text is None:
            return

        form_kwargs = dict(draft.kwargs)
        form_kwargs.pop("inline_message_id", None)

        await self.inline.form(
            draft.text,
            message=message,
            reply_markup=draft.reply_markup,
            silent=True,
            **form_kwargs,
        )

    async def inline__global_folder(
        self,
        call: InlineCall,
        folder: str,
    ):
        all_folders = self._get_all_folders()
        folder_options = all_folders.get(folder, {})

        btns = [
            {
                "text": f"{mod_name}",
                "callback": self.inline__configure,
                "kwargs": {"obj_type": False, "mod": mod_name, "folder": folder},
            }
            for mod_name in sorted(folder_options.keys())
        ]

        text_parts = []
        for mod_name, params in folder_options.items():
            try:
                raw_parts = []
                for param in params:
                    try:
                        raw_value = str(self.lookup(mod_name).config[param])
                        if len(raw_value) > 100:
                            raw_value = raw_value[:100] + "..."
                        raw_parts.append(
                            f"<code>{utils.escape_html(param)}</code>: <code>{utils.escape_html(raw_value)}</code>"
                        )
                    except Exception:
                        raw_parts.append(f"<code>{utils.escape_html(param)}</code>")
                text_parts.append(f"▫️ <b>{utils.escape_html(mod_name)}</b>")
            except Exception:
                text_parts.append(f"▫️ <b>{utils.escape_html(mod_name)}</b>")

        await call.edit(
            self.strings["configuring_folder"].format(
                utils.escape_html(folder),
                "\n".join(text_parts) if text_parts else "No options",
            ),
            reply_markup=list(utils.chunks(btns, 1))
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__choose_category,
                        "style": "primary",
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__global_config(
        self,
        call: InlineCall,
        page: int = 0,
        obj_type: bool | str = False,
    ):
        if isinstance(obj_type, bool):
            to_config = [
                mod.strings("name")
                for mod in self.allmodules.modules
                if hasattr(mod, "config")
                and callable(mod.strings)
                and (mod.__origin__.startswith("<core") or not obj_type)
                and (not mod.__origin__.startswith("<core") or obj_type)
            ]
        else:
            to_config = [
                lib.name for lib in self.allmodules.libraries if hasattr(lib, "config")
            ]

        to_config.sort()

        kb = []
        for mod_row in utils.chunks(
            to_config[page * NUM_ROWS * ROW_SIZE : (page + 1) * NUM_ROWS * ROW_SIZE],
            3,
        ):
            row = [
                {
                    "text": btn,
                    "callback": self.inline__configure,
                    "args": (btn,),
                    "kwargs": {"obj_type": obj_type},
                }
                for btn in mod_row
            ]
            kb += [row]

        if len(to_config) > NUM_ROWS * ROW_SIZE:
            kb += self.inline.build_pagination(
                callback=functools.partial(
                    self.inline__global_config, obj_type=obj_type
                ),
                total_pages=ceil(len(to_config) / (NUM_ROWS * ROW_SIZE)),
                current_page=page + 1,
            )

        kb += [
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__choose_category,
                    "style": "primary",
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ]
        ]

        await call.edit(
            self.strings[
                "configure" if isinstance(obj_type, bool) else "configure_lib"
            ],
            reply_markup=kb,
        )

    @loader.command(alias="cfg")
    async def configcmd(self, message: Message):
        args = utils.get_args_raw(message)
        args_s = args.split()
        if (
            len(args_s) == 1
            and self.lookup(args_s[0])
            and hasattr(self.lookup(args_s[0]), "config")
        ):
            mod = self.lookup(args_s[0])
            if isinstance(mod, loader.Library):
                type_ = "library"
            else:
                type_ = mod.__origin__.startswith("<core")

            await self._send_initial_config_form(
                message,
                self.inline__configure,
                args_s[0],
                obj_type=type_,
            )
            return

        if (
            len(args_s) == 2
            and self.lookup(args_s[0])
            and hasattr(self.lookup(args_s[0]), "config")
        ):
            mod = self.lookup(args_s[0])
            if isinstance(mod, loader.Library):
                type_ = "library"
            else:
                type_ = mod.__origin__.startswith("<core")

            if args_s[1] in mod.config.keys():
                await self._send_initial_config_form(
                    message,
                    self.inline__configure_option,
                    mod=args_s[0],
                    config_opt=args_s[1],
                    obj_type=type_,
                )
            else:
                await self.inline__choose_category(message)
            return

        await self.inline__choose_category(message)

    @loader.command(alias="fcfg")
    async def fconfig(self, message: Message):
        raw = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()

        if not raw:
            await utils.answer(message, self.strings["args"])
            return

        parts = [p.strip() for p in raw.split("&&") if p.strip()]
        if not parts:
            await utils.answer(message, self.strings["args"])
            return

        first = parts[0].split(maxsplit=2)

        if len(first) == 3:
            mod, option, value = first
        elif len(first) == 2 and reply:
            mod, option = first
            value = reply.raw_text
            if not value:
                await utils.answer(message, self.strings["args"])
                return
        else:
            await utils.answer(message, self.strings["args"])
            return

        if not (instance := self.lookup(mod)):
            await utils.answer(message, self.strings["no_mod"])
            return

        updates = []

        def apply_update(opt: str, val: str):
            if opt not in instance.config:
                return f"NO_OPTION::{opt}"
            instance.config[opt] = val
            return f"OK::{opt}"

        res = apply_update(option, value)
        if res.startswith("NO_OPTION::"):
            await utils.answer(message, self.strings["no_option"])
            return
        updates.append((option, self._get_value(mod, option)))

        for p in parts[1:]:
            seg = p.split(maxsplit=1)
            if len(seg) < 2:
                await utils.answer(message, self.strings["args"])
                return
            opt, val = seg
            res = apply_update(opt, val)
            if res.startswith("NO_OPTION::"):
                await utils.answer(message, self.strings["no_option"])
                return
            updates.append((opt, self._get_value(mod, opt)))

        lines = []
        for opt, val in updates:
            lines.append(
                self.strings[
                    (
                        "option_saved"
                        if isinstance(instance, loader.Module)
                        else "option_saved_lib"
                    )
                ].format(utils.escape_html(opt), utils.escape_html(mod), val)
            )

        await utils.answer(message, "\n".join(lines))
