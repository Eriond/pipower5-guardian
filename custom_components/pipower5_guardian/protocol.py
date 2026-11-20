"""PiPower 5 register decoding. Protocol references are in PROTOCOL-SOURCES.md.

No firmware writes, bus scanning, or forced access. A register-address phase
is part of an SMBus read and does not change configuration registers.
"""
ADDRESS = 0x5C
BOARD_ID = 2602


def decode(raw, identity, firmware, default_on, firmware_threshold):
    for data, size in ((raw, 25), (identity, 2), (firmware, 3)):
        if len(data) != size or any(type(b) is not int or not 0 <= b <= 255 for b in data):
            raise ValueError('Malformed I2C response')
    board = identity[0] * 256 + identity[1]
    if board != BOARD_ID:
        raise ValueError(f'Unexpected board ID {board}; expected PiPower 5 ({BOARD_ID})')
    if firmware in ([0, 0, 0], [255, 255, 255]):
        raise ValueError('Invalid firmware version')
    if raw[12] > 100 or raw[15] not in (0, 1) or raw[20] not in (0, 1, 2, 3):
        raise ValueError('Invalid battery percentage, source or shutdown request')
    if any(v not in (0, 1) for v in (raw[16], raw[18], default_on)):
        raise ValueError('Invalid status flag')
    if type(firmware_threshold) is not int or not 10 <= firmware_threshold <= 100:
        raise ValueError('Invalid firmware shutdown threshold')

    def u16(offset):
        return raw[offset] | (raw[offset + 1] << 8)

    current = u16(10)
    current = current if current < 32768 else current - 65536
    # Broad physical sanity checks: reject corrupted/all-zero packets. These
    # are not operating limits or a substitute for measured undervoltage.
    if not 3500 <= u16(4) <= 6500 or u16(0) > 20000 or not 4000 <= u16(8) <= 10000:
        raise ValueError('Implausible voltage or battery not measurable')
    d = {'board_id': board, 'firmware': '.'.join(map(str, firmware)),
         'default_on': bool(default_on), 'firmware_shutdown_percentage': firmware_threshold,
         'battery_percentage': raw[12], 'power_source': 'battery' if raw[15] else 'external',
         'input_connected': bool(raw[16]), 'charging': bool(raw[18]),
         'shutdown_request': raw[20]}
    for name, offset in (('input', 0), ('output', 4), ('battery', 8)):
        d[name + '_voltage'] = u16(offset) / 1000
        d[name + '_current'] = (current if name == 'battery' else u16(offset + 2)) / 1000
        d[name + '_power'] = round(d[name + '_voltage'] * d[name + '_current'], 3)
    return d


def read(bus):
    identity = bus.read_i2c_block_data(ADDRESS, 140, 2)
    if len(identity) != 2 or (identity[0] << 8 | identity[1]) != BOARD_ID:
        raise ValueError('PiPower 5 identity not confirmed; no further reads')
    return decode(bus.read_i2c_block_data(ADDRESS, 0, 25), identity,
                  bus.read_i2c_block_data(ADDRESS, 128, 3),
                  bus.read_byte_data(ADDRESS, 139), bus.read_byte_data(ADDRESS, 143))
