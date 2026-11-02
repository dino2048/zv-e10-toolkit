"""Framed serial transport for the v15 Pico sender."""
import struct

class Link:
    def __init__(self, port):
        import serial
        self.serial = serial.Serial(port, 115200, timeout=2, write_timeout=2, exclusive=True)
    def exact(self, size):
        result = bytearray()
        while len(result) < size:
            part = self.serial.read(size-len(result))
            if not part:
                raise TimeoutError('No complete Pico response')
            result.extend(part)
        return bytes(result)
    def exchange(self, command, data=b''):
        packet = bytes([command])+struct.pack('<H', len(data))+data
        if self.serial.write(packet) != len(packet):
            raise IOError('Short serial write')
        header = self.exact(3)
        size = int.from_bytes(header[1:], 'little')
        if size > 4100:
            raise ValueError('Oversized reply; wrong firmware or framing')
        answer = self.exact(size)
        if header[0] == 0x82:
            raise RuntimeError(answer.decode('ascii', errors='replace'))
        if header[0] != 0x81:
            raise ValueError('Unexpected reply type')
        return answer
    def status(self):
        data = self.exchange(9)
        if len(data) != 7:
            raise ValueError('Bad status length')
        return dict(zip(('mode', 'gpio_function', 'level', 'pull_up', 'pull_down', 'push_pull_build', 'blob_pending'), data))
