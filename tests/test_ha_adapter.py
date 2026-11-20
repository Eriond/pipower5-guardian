"""HA adapter contract tests with explicit test doubles, not a real HA runtime."""
import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch
from test_guardian import sample, validate


class UpdateFailed(Exception):pass


class FakeCoordinator:
    def __init__(self,hass,*args,**kwargs):
        self.hass=hass;self.last_update_success=True;self.data=None
    async def async_refresh(self):
        try:
            self.data=await self._async_update_data();self.last_update_success=True
        except UpdateFailed:self.last_update_success=False


def adapter():
    def module(name,**attrs):
        m=types.ModuleType(name);m.__dict__.update(attrs);return m
    notification=module('homeassistant.components.persistent_notification',
                        async_create=Mock(),async_dismiss=Mock())
    mocks={
      'homeassistant':module('homeassistant'),
      'homeassistant.components':module('homeassistant.components',persistent_notification=notification),
      'homeassistant.const':module('homeassistant.const',EVENT_HOMEASSISTANT_STOP='stop'),
      'homeassistant.core':module('homeassistant.core',callback=lambda f:f),
      'homeassistant.helpers':module('homeassistant.helpers'),
      'homeassistant.helpers.event':module('homeassistant.helpers.event',async_track_time_interval=Mock(return_value=Mock())),
      'homeassistant.helpers.update_coordinator':module('homeassistant.helpers.update_coordinator',DataUpdateCoordinator=FakeCoordinator,UpdateFailed=UpdateFailed),
    }
    with patch.dict(sys.modules,mocks):
        return importlib.import_module('guardian_test.coordinator')


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def make(self):
        m=adapter()
        hass=types.SimpleNamespace(async_add_executor_job=Mock(),async_create_task=asyncio.create_task,
            services=types.SimpleNamespace(async_call=AsyncMock()),
            bus=types.SimpleNamespace(async_listen_once=Mock(return_value=Mock())))
        entry=types.SimpleNamespace(async_create_background_task=lambda hass,coro,name:asyncio.create_task(coro,name=name))
        c=m.GuardianCoordinator(hass,entry,validate({}))
        c.reader=types.SimpleNamespace(sample=AsyncMock(return_value=sample()),close=Mock())
        return c

    async def test_exact_host_service(self):
        c=self.make();await c.host_shutdown()
        c.hass.services.async_call.assert_awaited_once_with('hassio','host_shutdown',{},blocking=True)

    async def test_shared_script_contract(self):
        c=self.make();await c.notify('test')
        c.hass.services.async_call.assert_awaited_once_with('script','turn_on',
            {'entity_id':'script.ups_notify','variables':{'title':'PiPower 5 Guardian','message':'test'}},blocking=True)

    async def test_polling_without_entities_and_shutdown(self):
        c=self.make();c.reader.sample.return_value=sample(battery_percentage=10)
        c.shutdown.request=AsyncMock()
        await c.poll();await c.poll();await c.shutdown_task
        c.shutdown.request.assert_awaited_once()
        await c.close()

    async def test_invalid_data_does_not_trigger_shutdown(self):
        c=self.make();c.reader.sample.side_effect=OSError('test')
        c.shutdown.request=AsyncMock()
        await c.poll();await c.poll()
        c.shutdown.request.assert_not_called()
        self.assertFalse(c.last_update_success)
        self.assertEqual(c.queue.qsize(),1)
        await c.close()

    async def test_singleflight_ticks(self):
        c=self.make();gate=asyncio.Event()
        async def blocked():await gate.wait();return sample()
        c.reader.sample.side_effect=blocked
        c.tick();await asyncio.sleep(0)
        for _ in range(100):c.tick()
        self.assertEqual(c.reader.sample.await_count,1)
        gate.set();await c.poll_task;await c.close()

    async def test_close_cancels_all_jobs(self):
        c=self.make();c.start();await asyncio.sleep(.01)
        async with asyncio.timeout(2):
            await c.close()
        self.assertTrue(c.closed)
        self.assertTrue(c.notify_task.done())
        self.assertTrue(c.poll_task.done())
        c.reader.close.assert_called_once()
        self.assertIsNone(c.cancel_timer)

    async def test_queue_bounded(self):
        c=self.make()
        for i in range(10000):c.enqueue(str(i))
        self.assertEqual(c.queue.qsize(),8)
        self.assertEqual(c.queue.get_nowait()[1],'9992')
        await c.close()

    async def test_stop_event_does_not_remove_consumed_listener(self):
        c=self.make();c.start();await asyncio.sleep(.01)
        remove_listener=c.cancel_stop
        await c.stop_event(None)
        remove_listener.assert_not_called()
        self.assertTrue(c.closed)
        self.assertTrue(c.notify_task.done())
        self.assertIsNone(c.cancel_stop)
