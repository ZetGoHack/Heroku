import typing

class BaseTunnel:
    async def start(self):
        raise NotImplementedError("Subclasses must implement the 'start' method.")

    async def stop(self):
        raise NotImplementedError("Subclasses must implement the 'stop' method.")

    async def wait_for_url(self, timeout: float) -> typing.Optional[str]:
        raise NotImplementedError("Subclasses must implement the 'wait_for_url' method.")