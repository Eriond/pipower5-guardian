"""Hardware-free regression tests; no service can reach a real HA instance."""
import asyncio
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'custom_components/pipower5_guardian'
# Load pure modules without executing the HA-only package initializer.
package=types.ModuleType('guardian_test'); package.__path__=[str(PKG)]
sys.modules['guardian_test']=package
from guardian_test.protocol import decode, read
from guardian_test.const import validate
from guardian_test.policy import Policy
from guardian_test.reader import Reader
from guardian_test.runtime import Shutdown


def packet():
    b=[0]*25
    for offset,value in [(0,12000),(2,900),(4,5050),(6,1600),(8,7800),(10,65036)]:
        b[offset:offset+2]=[value&255,value>>8]
    b[12],b[15],b[16],b[18],b[20]=75,1,0,0,0
    return b


def sample(**updates):
    return {**decode(packet(),[10,42],[1,2,3],1,10),**updates}


class ProtocolTests(unittest.TestCase):
    def test_signed_current_and_units(self):
        d=sample()
        self.assertEqual(d['battery_current'],-.5)
        self.assertEqual(d['battery_power'],-3.9)
        self.assertEqual(d['output_voltage'],5.05)

    def test_wrong_board_stops_reads(self):
        bus=Mock();bus.read_i2c_block_data.return_value=[0,1]
        with self.assertRaises(ValueError):read(bus)
        bus.read_i2c_block_data.assert_called_once_with(0x5c,140,2)
        bus.read_byte_data.assert_not_called()

    def test_read_only_contract(self):
        bus=Mock();bus.read_i2c_block_data.side_effect=[[10,42],packet(),[1,2,3]]
        bus.read_byte_data.side_effect=[1,10]
        self.assertEqual(read(bus)['battery_percentage'],75)
        self.assertTrue(all(c[0].startswith('read_') for c in bus.mock_calls))

    def test_malformed_rejected(self):
        for index,value in [(12,101),(15,2),(16,2),(18,2),(20,4),(0,-1)]:
            b=packet();b[index]=value
            with self.subTest(index=index),self.assertRaises(ValueError):
                decode(b,[10,42],[1,2,3],1,10)
        for b in ([0]*25,[255]*25,packet()[:-1]):
            with self.assertRaises(ValueError):decode(b,[10,42],[1,2,3],1,10)

    def test_absent_board(self):
        bus=Mock();bus.read_i2c_block_data.side_effect=OSError()
        with self.assertRaises(OSError):read(bus)

    def test_boundary_percentages(self):
        for percent in (0,100):
            b=packet();b[12]=percent
            self.assertEqual(decode(b,[10,42],[1,0,0],0,10)['battery_percentage'],percent)


class PolicyTests(unittest.TestCase):
    def test_mandatory_default_and_boundary(self):
        for percent in (0,19,20):
            p=Policy();d=sample(battery_percentage=percent)
            self.assertIsNone(p.evaluate(d,0).shutdown_reason)
            self.assertIsNotNone(p.evaluate(d,5).shutdown_reason)

    def test_above_threshold(self):
        p=Policy()
        for t in range(0,50,5):self.assertIsNone(p.evaluate(sample(battery_percentage=21),t).shutdown_reason)

    def test_no_low_charge_shutdown_on_external_power(self):
        p=Policy()
        for t in range(0,50,5):
            self.assertIsNone(p.evaluate(sample(power_source='external',battery_percentage=0),t).shutdown_reason)

    def test_power_restoration_cancels_pending(self):
        p=Policy();low=sample(battery_percentage=10)
        p.evaluate(low,0)
        self.assertIsNone(p.evaluate(sample(power_source='external'),5).shutdown_reason)
        self.assertIsNone(p.evaluate(low,10).shutdown_reason)

    def test_errors_reset_confirmation(self):
        p=Policy();low=sample(battery_percentage=10)
        p.evaluate(low,0);p.invalid()
        self.assertIsNone(p.evaluate(low,5).shutdown_reason)

    def test_large_sampling_gap_resets(self):
        p=Policy();low=sample(battery_percentage=10)
        p.evaluate(low,0)
        self.assertIsNone(p.evaluate(low,20).shutdown_reason)

    def test_firmware_threshold_takes_precedence(self):
        p=Policy();low=sample(battery_percentage=35,firmware_shutdown_percentage=40)
        p.evaluate(low,0)
        self.assertIsNotNone(p.evaluate(low,5).shutdown_reason)

    def test_firmware_battery_emergencies(self):
        for request in (1,3):
            p=Policy();d=sample(shutdown_request=request,power_source='external')
            p.evaluate(d,0)
            self.assertIsNotNone(p.evaluate(d,5).shutdown_reason)

    def test_button_alone_not_shutdown(self):
        p=Policy();d=sample(shutdown_request=2)
        p.evaluate(d,0)
        self.assertIsNone(p.evaluate(d,5).shutdown_reason)

    def test_notification_dedup_and_rearm(self):
        p=Policy();d=sample(battery_percentage=30)
        self.assertEqual(len(p.evaluate(d,0).notifications),2)
        for t in range(5,10005,5):self.assertEqual(p.evaluate(d,t).notifications,())
        self.assertEqual(len(p.evaluate(sample(power_source='external'),10005).notifications),1)
        self.assertEqual(len(p.evaluate(d,10010).notifications),2)

    def test_start_already_low(self):
        p=Policy();d=sample(battery_percentage=2)
        self.assertEqual(len(p.evaluate(d,0).notifications),2)
        self.assertIsNotNone(p.evaluate(d,5).shutdown_reason)

    def test_threshold_configuration(self):
        self.assertEqual(validate({})['shutdown_percentage'],20)
        for cfg in ({'shutdown_percentage':0},{'shutdown_percentage':True},
                    {'shutdown_percentage':95},{'warning_percentage':20},
                    {'bus':3},{'notification_script':''}):
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):validate(cfg)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_despite_notification_failure(self):
        call=AsyncMock();notify=AsyncMock(side_effect=OSError());report=Mock()
        s=Shutdown(call,notify,report)
        await s.request('test');await s.request('test')
        call.assert_awaited_once();self.assertTrue(s.accepted)

    async def test_shutdown_retry_and_cooldown(self):
        now=[0];call=AsyncMock(side_effect=[OSError(),None]);report=Mock()
        s=Shutdown(call,AsyncMock(),report,clock=lambda:now[0])
        await s.request('test');await s.request('test')
        self.assertEqual(call.await_count,1);self.assertFalse(s.accepted)
        now[0]=15;await s.request('test')
        self.assertEqual(call.await_count,2);self.assertTrue(s.accepted)
        report.assert_called_once()

    async def test_concurrent_shutdown_is_singleflight(self):
        gate=asyncio.Event()
        async def call():await gate.wait()
        mocked=AsyncMock(side_effect=call)
        s=Shutdown(mocked,AsyncMock(),Mock())
        first=asyncio.create_task(s.request('test'))
        await asyncio.sleep(.01)
        await s.request('test');gate.set();await first
        mocked.assert_awaited_once()

    async def test_slow_notification_cannot_block_shutdown(self):
        async def hang(_):await asyncio.Event().wait()
        call=AsyncMock();s=Shutdown(call,hang,Mock())
        await asyncio.wait_for(s.request('test'),2.5)
        call.assert_awaited_once()

    async def test_i2c_timeout_no_new_threads(self):
        pending=asyncio.get_running_loop().create_future()
        submit=Mock(return_value=pending);r=Reader(submit,1,timeout=.01)
        with self.assertRaises(OSError):await r.sample()
        for _ in range(100):
            with self.assertRaises(OSError):await r.sample()
        self.assertFalse(pending.cancelled());submit.assert_called_once()
        pending.set_result(sample());fresh=asyncio.get_running_loop().create_future()
        fresh.set_result(sample(battery_percentage=90));submit.return_value=fresh
        self.assertEqual((await r.sample())['battery_percentage'],90)

    async def test_cancel_preserves_pending_i2c(self):
        pending=asyncio.get_running_loop().create_future();r=Reader(Mock(return_value=pending),1)
        task=asyncio.create_task(r.sample());await asyncio.sleep(0);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertIs(r.pending,pending);self.assertFalse(pending.cancelled())
        r.close();pending.set_exception(OSError());await asyncio.sleep(0)

    async def test_i2c_exception_releases_future(self):
        pending=asyncio.get_running_loop().create_future();pending.set_exception(OSError())
        r=Reader(Mock(return_value=pending),1)
        with self.assertRaises(OSError):await r.sample()
        self.assertIsNone(r.pending)


class PackagingTests(unittest.TestCase):
    def test_no_mqtt_or_optional_shutdown(self):
        manifest=json.loads((PKG/'manifest.json').read_text())
        self.assertEqual(manifest['dependencies'],['hassio'])
        self.assertEqual(manifest['version'],'1.0.0')
        self.assertFalse((PKG/'mqtt.py').exists())
        self.assertNotIn('automatic_shutdown', (PKG/'const.py').read_text())

    def test_translations_and_manifest(self):
        for p in PKG.rglob('*.json'):json.loads(p.read_text())
        self.assertEqual(json.loads((PKG/'strings.json').read_text()),json.loads((PKG/'translations/en.json').read_text()))


if __name__=='__main__':unittest.main()
