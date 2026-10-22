"""Pico-only inspection. --bench-wave requires camera disconnected; no payloads."""
import argparse
import json
import math
import statistics
import struct
import time
from pathlib import Path

VERSION = b'zve10_uart_pp 6'

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

def run(port, bench, monitor_seconds=0):
    link = Link(port)
    result = {'port': port, 'scope': 'Pico inspection only; no camera records', 'bench_wave': bench}
    try:
        version = link.exchange(1)
        if version != VERSION:
            raise ValueError('Unexpected firmware: '+repr(version))
        result['version'] = version.decode()
        result['before'] = link.status()
        if result['before']['mode'] != 0:
            raise RuntimeError('Expected idle after boot')
        result['idle_high_samples_out_of_256'] = int.from_bytes(link.exchange(8), 'little')
        if monitor_seconds:
            result['scope'] = 'Passive GP28 sampling only; no carrier or camera records'
            result['samples'] = []
            print('PASSIVE MONITOR: GP28 stays input; no carrier or payload.', flush=True)
            started = time.monotonic()
            while time.monotonic() - started < monitor_seconds:
                status = link.status()
                if (status['mode'] != 0 or status['gpio_function'] != 5 or
                        status['pull_up'] or status['pull_down'] or status['blob_pending']):
                    raise RuntimeError('Passive monitor requires idle without pulls')
                raw = link.exchange(8)
                if len(raw) != 2 or int.from_bytes(raw, 'little') > 256:
                    raise ValueError('Bad sense reply')
                sample = {'elapsed_s': round(time.monotonic()-started, 4),
                          'high_out_of_256': int.from_bytes(raw, 'little')}
                result['samples'].append(sample)
                print(json.dumps(sample), flush=True)
                time.sleep(0.1)
        if bench:
            try:
                link.exchange(3, b'\x01')
                result['carrier_status'] = link.status()
                try:
                    link.exchange(8)
                except RuntimeError as error:
                    if str(error) != 'sense requires idle':
                        raise
                    result['sense_while_driving_rejected'] = True
                else:
                    raise AssertionError('Push-pull sense should be rejected')
                raw = link.exchange(10)
                count = int.from_bytes(raw[:2], 'little')
                if len(raw) != 2+count*5:
                    raise ValueError('Bad capture framing')
                edges = [struct.unpack_from('<IB', raw, 2+i*5) for i in range(count)]
                if count < 32:
                    raise RuntimeError('Too few observed carrier edges')
                spans = [b[0]-a[0] for a,b in zip(edges, edges[1:])]
                result['carrier_edges'] = edges
                result['median_half_period_us'] = statistics.median(spans)
                result['half_period_range_us'] = [min(spans), max(spans)]
                if not all(110 <= width <= 140 for width in spans):
                    raise RuntimeError('Observed carrier outside expected timing band')
            finally:
                link.exchange(3, b'\x00')
            # Check the inherited 1200ms inactivity release without sending a record.
            link.exchange(3, b'\x01')
            time.sleep(1.4)
            header = link.exact(3)
            answer = link.exact(int.from_bytes(header[1:], 'little'))
            if header[0] != 0x82 or answer != b'starved':
                raise RuntimeError('Expected automatic idle release event')
            result['inactivity_release'] = True
        result['after'] = link.status()
        if result['after']['mode'] != 0 or result['after']['pull_up'] or result['after']['pull_down']:
            raise RuntimeError('Expected floating high-impedance idle')
        result['passed'] = True
    finally:
        # Always request idle; never issue BLOB, RESET, or UART commands.
        try:
            link.exchange(3, b'\x00')
        finally:
            link.serial.close()
        dest = Path(__file__).parent/'logs'/('pico-inspection-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        dest.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k != 'samples'}, indent=2))
        print('LOG:', dest)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--bench-wave', action='store_true', help='Observe carrier on isolated Pico; camera MUST be disconnected')
    parser.add_argument('--monitor-seconds', type=float, default=0,
                        help='Passive input sampling at ~10 Hz; not an automatic trigger or voltage measurement')
    args = parser.parse_args()
    if not math.isfinite(args.monitor_seconds) or not 0 <= args.monitor_seconds <= 300:
        parser.error('--monitor-seconds must be finite and between 0 and 300')
    if args.bench_wave and args.monitor_seconds:
        parser.error('--bench-wave and passive monitoring cannot be combined')
    run(args.port, args.bench_wave, args.monitor_seconds)
