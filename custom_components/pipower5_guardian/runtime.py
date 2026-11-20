"""Shutdown delivery independent of remote-notification success."""
import asyncio
import time


class Shutdown:
    def __init__(self, call, notify, report, clock=time.monotonic):
        self.call, self.notify, self.report, self.clock = call, notify, report, clock
        self.accepted = False
        self.in_progress = False
        self.retry_at = 0

    async def request(self, reason):
        if self.accepted or self.in_progress or self.clock() < self.retry_at:
            return
        self.in_progress = True
        try:
            try:
                async with asyncio.timeout(2):
                    await self.notify('Shutting down Home Assistant safely: ' + reason)
            except Exception:
                pass
            # This is the HOST shutdown service, never homeassistant.stop.
            async with asyncio.timeout(10):
                await self.call()
            self.accepted = True
        except Exception as exc:
            self.retry_at = self.clock() + 15
            self.report(f'Host shutdown request failed ({type(exc).__name__}); retrying while battery remains critical.')
        finally:
            self.in_progress = False
