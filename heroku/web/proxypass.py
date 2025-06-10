# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Heroku Userbot
# 🌐 https://github.com/hikariatama/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import os
import logging
import typing
from .ssh_tunnel import SSHTunnel
from .cloudflare_tunnel import CloudflareTunnel


logger = logging.getLogger(__name__)


class ProxyPasser:
    def __init__(
        self,
        port: int,
        change_url_callback: typing.Callable[[str], None] = None,
        verbose: bool = False
    ):
        self._tunnel_url = None
        self._port = port
        self._change_url_callback = change_url_callback
        self._verbose = verbose
        self._tunnels = [
            SSHTunnel(port=port, change_url_callback=self._on_url_change),
            CloudflareTunnel(port=port, verbose=verbose, change_url_callback=self._on_url_change)
        ]


    def _on_url_change(self, url: str):
        self._tunnel_url = url
        if self._change_url_callback:
            self._change_url_callback(url)
    
    def set_port(self, port: int):
        self.port = port

    async def get_url(self, timeout: float = 25) -> typing.Optional[str]:
        
        if "DOCKER" in os.environ:
            # We're in a Docker container, so we can't use ssh
            # Also, the concept of Docker is to keep
            # everything isolated, so we can't proxy-pass to
            # open web.
            return None
        
        for tunnel in self._tunnels:
            try:
                await tunnel.start()
                self._tunnel_url = await tunnel.wait_for_url(timeout)
                if self._tunnel_url:
                    return self._tunnel_url
                else:
                    logger.warning(f"{tunnel.__class__.__name__} failed to provide URL.")
            except Exception as e:
                logger.warning(f"{tunnel.__class__.__name__} failed: {e}")

        return None