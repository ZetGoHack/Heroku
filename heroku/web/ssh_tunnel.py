import typing
import logging
import asyncio
import re

from .base_tunnel import BaseTunnel

logger = logging.getLogger(__name__)

class SSHTunnel(BaseTunnel):
    def __init__(
        self,
        port: int,
        change_url_callback: typing.Callable[[str], None] = None,
    ):
        #TODO: select ssh servers?
        self.ssh_commands = [
            (f"ssh -R 80:127.0.0.1:{port} serveo.net -T -n", r"https:\/\/(\S*serveo\.net\S*)"),
            (f"ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:{port} nokey@localhost.run", r"https:\/\/(\S*lhr\.life\S*)"),
            ]
        self._change_url_callback = change_url_callback
        self._tunnel_url = None
        self._url_available = asyncio.Event()
        self._url_available.clear()
        self.process = None
        self.current_command_index = 0
        self._ssh_task = None
        self._all_commands_failed = False

    async def start(self):
        self._ssh_task = asyncio.create_task(self._run_ssh_tunnel())

    async def stop(self):
        if self._ssh_task:
            self._ssh_task.cancel()
            try:
                await self._ssh_task
            except asyncio.CancelledError:
                logger.debug("SSH task was cancelled")

        if self.process:
            logger.debug("Stopping SSH tunnel...")
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except Exception as e:
                logger.warning(f"Failed to terminate SSH process: {e}")
            finally:
                self.process = None

    async def wait_for_url(self, timeout: float) -> typing.Optional[str]:
        if self._all_commands_failed:
            return None
        try:
            await asyncio.wait_for(self._url_available.wait(), timeout)
            return self._tunnel_url
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for tunnel URL.")
            return None

    async def _run_ssh_tunnel(self):
        if not self.ssh_commands:
            logger.debug("SSH command list is empty")
            return
        try:
            while self.current_command_index < len(self.ssh_commands):
                ssh_command, regex_pattern = self.ssh_commands[self.current_command_index]
                logger.debug(f"Attempting SSH command: {ssh_command} with pattern: {regex_pattern}")
                try:
                    command_list = ssh_command.split()
                    self.process = await asyncio.create_subprocess_exec(
                        *command_list,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    logger.debug(f"SSH tunnel started with PID: {self.process.pid}")
                    asyncio.create_task(self._read_stream_and_process(self.process.stdout, regex_pattern))
                    
                    await self.process.wait()
                    
                    if self._tunnel_url is None:
                        logger.warning("SSH tunnel disconnected without providing a URL.")
                    else:
                        logger.info("SSH tunnel disconnected, but URL was obtained. Exiting SSH Tunnel attempts.")
                        return

                except Exception as e:
                    logger.error(
                        f"Failed to start SSH tunnel with command: {ssh_command}. Error: {e}"
                    )
                    
                finally:
                    if self.process:
                        self.process = None
                    if self._tunnel_url is None:
                        logger.info("Reconnecting SSH tunnel after failure...")
                        self.current_command_index += 1
                        await asyncio.sleep(2)
                    else:
                        logger.info("Exiting SSH Tunnel attempts after disconnect.")
                        return
            self._all_commands_failed = True
        finally:
            if self._tunnel_url is None and self._all_commands_failed:
                logger.error("All SSH commands failed.")
                self._url_available.set()

    async def _read_stream_and_process(self, stream, regex_pattern: str):
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode("utf-8").strip()
                await self._process_stream(line_str, regex_pattern)
        except Exception as e:
            logger.exception(f"Error reading and processing stream: {e}")

    async def _process_stream(self, stdout_line: str, regex_pattern: str):
        logger.debug(stdout_line)
        match = re.search(regex_pattern, stdout_line)
        if match:
            self._tunnel_url = match.group(0)
            if self._change_url_callback:
                self._change_url_callback(self._tunnel_url)
            self._url_available.set()