"""Polling and UPS actions; polling never depends on enabled sensor entities."""
import asyncio
from datetime import timedelta
import logging
import time
from homeassistant.components import persistent_notification
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, NAME, POLL_SECONDS
from .policy import Policy
from .reader import Reader
from .runtime import Shutdown

LOGGER = logging.getLogger(__name__)


class GuardianCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, config):
        super().__init__(hass, LOGGER, name=NAME, config_entry=entry)
        self.entry, self.config = entry, config
        self.reader = Reader(hass.async_add_executor_job, config['bus'])
        self.policy = Policy(config['shutdown_percentage'], config['warning_percentage'])
        self.shutdown = Shutdown(self.host_shutdown, self.notify, self.report)
        self.poll_task = None
        self.shutdown_task = None
        self.notify_task = None
        self.queue = asyncio.Queue(maxsize=8)
        self.cancel_timer = None
        self.cancel_stop = None
        self.closed = False
        self.read_failed = False

    def report(self, message):
        LOGGER.error('%s', message)
        persistent_notification.async_create(self.hass, message, title=NAME,
                                             notification_id=DOMAIN + '_protection')

    async def notify(self, message):
        persistent_notification.async_create(self.hass, message, title=NAME,
                                             notification_id=DOMAIN + '_power')
        await self.hass.services.async_call('script', 'turn_on', {
            'entity_id': self.config['notification_script'],
            'variables': {'title': NAME, 'message': message}}, blocking=True)

    async def host_shutdown(self):
        await self.hass.services.async_call('hassio', 'host_shutdown', {}, blocking=True)

    async def _async_update_data(self):
        try:
            data = await self.reader.sample()
        except (OSError, ValueError) as exc:
            self.policy.invalid()
            if not self.read_failed:
                self.report('PiPower readings unavailable: battery protection cannot be evaluated. ' + str(exc))
                self.enqueue('PiPower monitoring failed; check the UPS connection. Automatic battery protection is impaired.')
            self.read_failed = True
            raise UpdateFailed(str(exc)) from exc
        if self.read_failed:
            self.read_failed = False
            self.enqueue('PiPower monitoring has recovered.')
            persistent_notification.async_dismiss(self.hass, DOMAIN + '_protection')
        return data

    def enqueue(self, message):
        if self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait((time.monotonic(), message))

    async def deliver(self):
        while not self.closed:
            created, message = await self.queue.get()
            if time.monotonic() - created > 60:
                continue
            try:
                async with asyncio.timeout(5):
                    await self.notify(message)
            except Exception as exc:
                LOGGER.warning('UPS notification failed: %s', type(exc).__name__)

    async def poll(self):
        await self.async_refresh()
        if self.closed or not self.last_update_success:
            return
        decision = self.policy.evaluate(self.data, time.monotonic())
        for message in decision.notifications:
            self.enqueue(message)
        if decision.shutdown_reason and (self.shutdown_task is None or self.shutdown_task.done()):
            self.shutdown_task = self.entry.async_create_background_task(
                self.hass, self.shutdown.request(decision.shutdown_reason), 'Guardian host shutdown')

    @callback
    def tick(self, _=None):
        if not self.closed and (self.poll_task is None or self.poll_task.done()):
            self.poll_task = self.entry.async_create_background_task(self.hass, self.poll(), 'Guardian poll')

    def start(self):
        self.notify_task = self.entry.async_create_background_task(self.hass, self.deliver(), 'Guardian notifications')
        self.cancel_timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=POLL_SECONDS))
        self.cancel_stop = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_event)
        self.tick()

    async def stop_event(self, _):
        # HA removes a one-shot listener before invoking its callback.
        self.cancel_stop = None
        await self.close()

    async def close(self):
        self.closed = True
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.cancel_stop:
            self.cancel_stop()
            self.cancel_stop = None
        tasks = [t for t in (self.poll_task, self.notify_task, self.shutdown_task)
                 if t and t is not asyncio.current_task() and not t.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.reader.close()
