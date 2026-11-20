"""Serialize blocking I2C reads without blocking HA's event loop."""
import asyncio
from .protocol import read


def read_sample(bus_number):
    from smbus2 import SMBus
    with SMBus(bus_number) as bus:
        return read(bus)


class Reader:
    def __init__(self, submit, bus_number, timeout=3):
        self.submit, self.bus_number, self.timeout = submit, bus_number, timeout
        self.pending = None
        self.closed = False

    async def sample(self):
        if self.closed:
            raise OSError('Reader is closed')
        if self.pending is not None:
            if not self.pending.done():
                raise OSError('Previous I2C read is still blocked; no overlapping read started')
            # Discard late results: they are not fresh enough for safety decisions.
            try:
                self.pending.result()
            except Exception:
                pass
            self.pending = None
        self.pending = self.submit(read_sample, self.bus_number)
        try:
            async with asyncio.timeout(self.timeout):
                result = await asyncio.shield(self.pending)
        except TimeoutError:
            raise OSError('I2C read timed out') from None
        except BaseException:
            if self.pending.done():
                self.pending = None
            raise
        self.pending = None
        return result

    def close(self):
        self.closed = True
        if self.pending is not None:
            # A Python timeout cannot stop a Linux I2C syscall. Keep its future
            # tracked; do not create another reader while it is outstanding.
            self.pending.add_done_callback(self._consume)

    @staticmethod
    def _consume(future):
        if not future.cancelled():
            future.exception()
