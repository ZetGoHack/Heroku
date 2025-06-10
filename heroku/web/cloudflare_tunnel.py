import typing
import logging
import asyncio
import contextvars
import functools

from pycloudflared import try_cloudflare

from .base_tunnel import BaseTunnel


logger = logging.getLogger(__name__)


class CloudflareTunnel(BaseTunnel):
    def __init__(
        self,
        port: int,
        verbose: bool = False,
        change_url_callback: typing.Callable[[str], None] = None,
    ):
        self.port = port
        self.verbose = verbose
        self._change_url_callback = change_url_callback
        self._tunnel_url = None
        self._url_available = asyncio.Event()
        self._url_available.clear()
    
    # to support python 3.8...
    async def to_thread(self, func, /, *args, **kwargs):
        loop = asyncio.get_running_loop()
        ctx = contextvars.copy_context()
        func_call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)

    async def start(self):
        logger.debug(f"Attempting Cloudflare tunnel on port {self.port}...")
        
        try:
            self._tunnel_url = (await self.to_thread(try_cloudflare, port=self.port, verbose=self.verbose)).tunnel
            logger.debug(f"Cloudflare tunnel established: {self._tunnel_url}")

            if self._change_url_callback:
                self._change_url_callback(self._tunnel_url)

            self._url_available.set()
        
        except Exception as e:
            logger.error(f"Failed to establish Cloudflare tunnel: {e}")
            raise

    async def stop(self):
        logger.debug("Stopping Cloudflare tunnel...")
        try_cloudflare.terminate(self.port)
    
    async def wait_for_url(self, timeout: float) -> typing.Optional[str]:
        try:
            await asyncio.wait_for(self._url_available.wait(), timeout)
            return self._tunnel_url
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for Cloudflare URL.")
            return None