"""HOST-only fault injection: no device or pyserial required."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('j5_can141', Path(__file__).with_name('j5_can141.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_table(two_apps=False):
    rows = struct.pack('<HBBII16sI', 0x50AA, 1, 2, 0x9000, 0x6000, b'nvs', 0)
    rows += struct.pack('<HBBII16sI', 0x50AA, 0, 0, 0x10000, 0x100000, b'factory', 0)
    if two_apps:
        rows += struct.pack('<HBBII16sI', 0x50AA, 0, 16, 0x110000, 0x100000, b'ota_0', 0)
    rows += b'\xeb\xeb' + b'\xff' * 14 + hashlib.md5(rows).digest()
    return rows + b'\xff' * (4096 - len(rows))


def fixture_app():
    raw = bytearray(4096)
    raw[0:2] = bytes((0xE9, 4))
    struct.pack_into('<H', raw, 12, 9)
    struct.pack_into('<I', raw, 28, 512)
    struct.pack_into('<I', raw, 32, 0xABCD5432)
    for offset, text in [(48, b'1.0'), (80, b'fixture_project'), (112, b'12:34:56'),
                         (128, b'Nov 12 2026'), (144, b'v5.5.6')]:
        raw[offset:offset + len(text)] = text
    raw[176:208] = bytes(range(32))
    return bytes(raw)


class FakeSerial:
    def __init__(self, *, fail=None, block=b'', **kwargs):
        self.kwargs = kwargs
        self.fail = fail
        self.block = block
        self.events = []
        self.close_called = False

    def open(self):
        self.events.append(('open', self.dtr, self.rts, self.port))
        if self.fail == 'open':
            raise OSError('injected open failure')

    def read(self, count):
        if self.fail == 'read':
            raise OSError('injected read failure')
        return self.block[:count]

    def write(self, data):
        raise AssertionError('Application write is forbidden')

    def close(self):
        self.close_called = True
        if self.fail == 'close':
            raise OSError('injected close failure')


class Tests(unittest.TestCase):
    def clock(self):
        value = iter(range(1000))
        return lambda: next(value) / 4

    def test_default_blocks(self):
        result = module.preparation()
        self.assertEqual(result['frames'], [])
        self.assertIsNone(result['actual_id'])
        self.assertFalse(result['hardware_approved'])
        self.assertEqual(result['existing_diagnostic'], 'BLOCKED_UNCONFIRMED_PROFILE')

    def test_exact_eight_frames(self):
        for node in (1, 2):
            frames = module.preparation(node)['frames']
            self.assertEqual([f['data'] for f in frames], [[0x31, 0x31 + node], [0x32, 0x32 + node],
                                                         [0xF1, 0xF1 + node], [0x3A, 0x3A + node]])
            self.assertTrue(all(f['dlc'] == 2 and not f['rtr'] and not f['extended'] for f in frames))
        for bad in (0, 3, 5, 127, '1', True, 1.0):
            with self.assertRaises(ValueError):
                module.preparation(bad)

    def test_capture_silent_and_control_order(self):
        client = FakeSerial()
        data, result = module.capture(lambda **kw: client, self.clock())
        self.assertEqual(data, b'')
        self.assertEqual(result['state'], 'SILENT_UNIDENTIFIED')
        self.assertEqual(client.events, [('open', False, False, 'COM7')])
        self.assertTrue(client.close_called)
        self.assertEqual(result['USB_application_TX_bytes'], 0)

    def test_capture_byte_limit(self):
        client = FakeSerial(block=b'a' * 4096)
        data, result = module.capture(lambda **kw: client, self.clock())
        self.assertEqual(len(data), 65536)
        self.assertEqual(result['state'], 'CAPTURED')

    def test_capture_fault_cleanup(self):
        for stage in ('open', 'read', 'close'):
            client = FakeSerial(fail=stage)
            _, result = module.capture(lambda **kw: client, self.clock())
            self.assertEqual(result['state'], 'ERROR')
            self.assertTrue(client.close_called)
            self.assertTrue(result['errors'])

    def test_capture_backwards_clock(self):
        ticks = iter([5, 4, 5])
        client = FakeSerial()
        _, result = module.capture(lambda **kw: client, lambda: next(ticks))
        self.assertEqual(result['state'], 'ERROR')
        self.assertTrue(client.close_called)

    def test_last_read_uses_remaining_time(self):
        class VirtualTime:
            value = 0.0

            def __call__(self):
                return self.value

        clock = VirtualTime()

        class TimedSerial(FakeSerial):
            timeouts = []

            def read(self, count):
                self.timeouts.append(self.timeout)
                clock.value += min(0.19, self.timeout)
                return b''

        client = TimedSerial()
        _, result = module.capture(lambda **kw: client, clock)
        self.assertEqual(result['state'], 'SILENT_UNIDENTIFIED')
        self.assertLess(client.timeouts[-1], 0.03)
        self.assertAlmostEqual(result['elapsed_s'], 8.0)
        self.assertTrue(client.close_called)

    def test_partition_valid_and_mutated(self):
        self.assertEqual(module.partition_table(fixture_table())['app']['offset'], 0x10000)
        bad = bytearray(fixture_table())
        bad[12] ^= 1
        for raw in (fixture_table(True), bytes(bad), fixture_table()[:4095], b'\xff' * 4096):
            with self.assertRaises(ValueError):
                module.partition_table(raw)

    def test_app_valid_and_mutated(self):
        raw = fixture_app()
        result = module.app_descriptor(raw)
        self.assertEqual((result['project'], result['version'], result['idf']), ('fixture_project', '1.0', 'v5.5.6'))
        self.assertEqual(result['complete_image_integrity'], 'NOT_VERIFIED')
        for offset in (0, 1, 12, 32, 80):
            bad = bytearray(raw)
            bad[offset] = 0xFF
            with self.assertRaises(ValueError, msg=str(offset)):
                module.app_descriptor(bytes(bad))
        short_segment = bytearray(raw)
        struct.pack_into('<I', short_segment, 28, 255)
        with self.assertRaises(ValueError):
            module.app_descriptor(bytes(short_segment))


if __name__ == '__main__':
    unittest.main(verbosity=2)
