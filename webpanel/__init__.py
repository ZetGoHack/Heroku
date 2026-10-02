"""Heroku Userbot web login panel.

FastAPI backend that allows logging into the userbot from a browser. It is
started only when there is no authorized session available, so at any moment
either the web panel or the userbot itself is running.

The frontend (HTML/CSS/JS) is intentionally not a part of this package yet.
"""

from .app import create_app
from .login import LoginError, LoginManager
from .presets import API_PRESETS, find_preset
from .runner import run_web_login, serve_standalone

__all__ = [
    "API_PRESETS",
    "LoginError",
    "LoginManager",
    "create_app",
    "find_preset",
    "run_web_login",
    "serve_standalone",
]
