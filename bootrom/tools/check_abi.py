"""Pin stage 2's raw function pointers to one exact published stage 1."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]

STAGE2 = ROOT / 'stage2'
PREBUILT = ROOT / 'prebuilt'
STAGE1 = PREBUILT / 'stage1.bin'
RELEASE = json.loads((PREBUILT / 'manifest.json').read_text())['artifacts']

EXPECTED_SHA = '4b63d41fc4ba537b2811cc444389c5db152aac92b699129bc0cd1c623ad034e9'
IMMUTABLE_SIZE = 0x1f58  # .text + .rodata; final .data word usb_led_trace changes at runtime.
FUNCTIONS = ('usb_bulk_recv', 'usb_bulk_send', 'usb_event_pump', 'usb_bulk_abort',
             'usb_bulk_recover', 'usb_bulk_enable_pending', 'dwc3_disconnect',
             'system_reset', 'led_heartbeat')
DATA_SYMBOLS = ('usb_bulk_error', 'ka_sent', 'ka_busy', 'ka_timer_ok',
                'ka_rx0', 'ka_rx13', 'ka_rx_ok')


def verify(build=False):
    path = ROOT / "stage1/build/fastboot.bin" if build else STAGE1
    blob = path.read_bytes()
    if len(blob) != 8028 or hashlib.sha256(blob).hexdigest() != EXPECTED_SHA:
        raise ValueError('Published stage 1 changed; regenerate and review USB ABI')
    if not build:
        return blob
    elf = path.with_suffix('.elf')
    with tempfile.TemporaryDirectory(prefix='stage2-abi-') as directory:
        output = Path(directory) / 'stage1.bin'
        subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', str(elf), str(output)], check=True)
        if output.read_bytes() != blob:
            raise ValueError('Stage 1 ELF does not match the pinned binary')
    symbols = {}
    text = subprocess.check_output(['arm-none-eabi-nm', '--defined-only', str(elf)], text=True)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    header = (STAGE2 / 'include/usb_link.h').read_text()
    for name in (*FUNCTIONS, *DATA_SYMBOLS):
        line = next(line for line in header.splitlines() if line.startswith('#define ' + name + ' '))
        match = re.search(r'0x([0-9a-fA-F]+)u', line)
        expected = symbols[name] | (1 if name in FUNCTIONS else 0)
        if not match or int(match[1], 16) != expected:
            raise ValueError(f'ABI address mismatch: {name}; expected 0x{expected:08x}')
    match = re.search(r'#define STAGE1_DL_BUF\s+0x([0-9a-fA-F]+)u', header)
    if int(match[1], 16) != symbols['download_buf']:
        raise ValueError('Stage 1 download buffer address mismatch')
    if symbols['usb_led_trace'] != 0xfe020000 + IMMUTABLE_SIZE:
        raise ValueError('Stage 1 immutable region layout changed')
    return blob


def verify_stage2(blob, elf_path=None, allow_writer=False):
    digest = hashlib.sha256(blob).hexdigest()
    for name in ('stage2-flash.bin',):
        row = RELEASE[name]
        if len(blob) == row['bytes'] and digest == row['sha256']:
            if row['writer'] and not allow_writer:
                raise ValueError('Write-enabled image requires an explicit write workflow')
            return row['identity']
    # Custom development images require ELF inspection; released images above
    # need only the exact published bytes, not binutils or intermediate files.
    elf = Path(elf_path) if elf_path else STAGE2 / 'build-flash/stage2-fastboot-flash.elf'
    if not elf.is_file():
        raise ValueError('Image is not a published payload; matching development ELF required')
    import struct
    if struct.unpack_from('<I', elf.read_bytes(), 24)[0] != 0xfe300001:
        raise ValueError('Stage 2 ELF entry is not the fixed Thumb entry')
    with tempfile.TemporaryDirectory(prefix='stage2-image-') as directory:
        output = Path(directory) / 'stage2.bin'
        subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', str(elf), str(output)], check=True)
        if output.read_bytes() != blob:
            raise ValueError('Selected stage2 does not match its ELF')
    names = subprocess.check_output(['arm-none-eabi-nm', str(elf)], text=True)
    if not allow_writer and re.search(r'\bmmc_write_blocks$', names, re.M):
        raise ValueError('Unexpected eMMC block writer in read-only image')
    match = re.search(r'^([0-9a-fA-F]+)\s+\w\s+stage2_build_id$', names, re.M)
    if not match:
        raise ValueError('Stage 2 has no exported build identity; rebuild it')
    offset = int(match[1], 16) - 0xfe300000
    if not 0 <= offset < len(blob):
        raise ValueError('Stage 2 build identity is outside the image')
    identity = blob[offset:offset + 64].split(b'\0', 1)[0].decode('ascii')
    writers = {'stage2-flash-20261026'}
    if identity not in writers:
        raise ValueError(f'Unknown stage 2 build identity: {identity!r}')
    has_writer = bool(re.search(r'\bmmc_write_blocks$', names, re.M))
    if has_writer != (identity in writers):
        raise ValueError('Stage 2 identity does not match its write capability')
    if not allow_writer and identity in writers:
        raise ValueError('Write-enabled image requires an explicit write workflow')
    return identity


if __name__ == '__main__':
    building = '--build' in sys.argv
    verify(build=building)
    print('PASS: pinned stage1' + (' and built ELF/USB ABI' if building else ' release hash'))
    if building:
        if '--image' in sys.argv:
            verify_stage2((STAGE2 / 'build-flash/stage2-fastboot-flash.bin').read_bytes(), allow_writer=True)
            print('PASS: full stage2 image')
    else:
        for name in ('stage2-flash.bin',):
            row = RELEASE[name]
            blob = (PREBUILT / name).read_bytes()
            if len(blob) != row['bytes'] or hashlib.sha256(blob).hexdigest() != row['sha256']:
                raise ValueError('Published payload changed: ' + name)
            verify_stage2(blob, allow_writer=row['writer'])
        print('PASS: published full stage2 hash and write capability')
