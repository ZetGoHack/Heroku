"""Heroku Userbot web login panel.

FastAPI backend that allows logging into the userbot from a browser. It is
started only when there is no authorized session available, so at any moment
either the web panel or the userbot itself is running.
"""

from .app import create_app
from .login import LoginError, LoginManager
from .runner import run_web_login, serve_standalone

__all__ = [
    "LoginError",
    "LoginManager",
    "create_app",
    "run_web_login",
    "serve_standalone",
]
