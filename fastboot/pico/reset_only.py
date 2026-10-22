"""Pulse GP27 -> 470R -> camera D+ (A6) once; no carrier, no records.

Use it to stop the 1L7S blink and return the camera to normal boot without
removing the battery. Requires the v15 firmware.
"""
import argparse
from inspect_pico import Link

VERSION = b'zve10_uart_od 15'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()

    link = Link(args.port)
    try:
        if link.exchange(1) != VERSION:
            raise RuntimeError('Unexpected firmware (need zve10_uart_od 15)')
        print('before:', link.status(), flush=True)
        link.exchange(2)
        print('RESET PULSED. Carrier is off; the camera should boot normally.',
              flush=True)
        print('after :', link.status(), flush=True)
    finally:
        try:
            link.exchange(3, b'\x00')
        except Exception:
            pass
        link.serial.close()


if __name__ == '__main__':
    main()
