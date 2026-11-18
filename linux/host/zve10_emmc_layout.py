"""Read-only Linux eMMC geometry checks shared by both backup paths."""
import re

import zve10_common as common

AREA_NAMES = ('nflasha', 'nflashaB0', 'nflashaB1')
LAYOUT_COMMAND = ('for p in /sys/class/block/nflasha*; do echo DEVICE:$p; '
                  'for f in dev size start ro; do echo FIELD:$f; '
                  'busybox cat "$p/$f" 2>/dev/null; done; done')
INFO_COMMAND = ('for p in /sys/class/block/nflasha/device '
                '/sys/class/mmc_host/mmc*/* /sys/bus/mmc/devices/*; do '
                'for f in cid csd manfid oemid name date hwrev fwrev; do '
                'if [ -f "$p/$f" ]; then echo FILE:$p/$f; busybox cat "$p/$f"; fi; '
                'done; done')


def validate(partitions, layout):
    """Require two matching capacity sources and the known 16-partition layout.

    Capacity variation is allowed only for the three whole-area devices.
    This is a backup policy, not permission to write or restore these areas.
    """
    proc = {}
    for line in partitions.splitlines():
        fields = line.split()
        if len(fields) != 4 or not fields[3].startswith('nflasha'):
            continue
        if not all(f.isdecimal() for f in fields[:3]) or fields[3] in proc:
            raise ValueError('Malformed or duplicate /proc/partitions entry')
        proc[fields[3]] = (int(fields[0]), int(fields[1]), int(fields[2]) * 1024)
    devices = {}
    device = field = None
    for line in layout.splitlines():
        if line.startswith('DEVICE:'):
            path = line[7:]
            if not re.fullmatch(r'/sys/class/block/nflasha(?:\d+|B[01])?', path):
                raise ValueError('Unexpected eMMC sysfs device')
            device, field = path.rsplit('/', 1)[1], None
            if device in devices:
                raise ValueError('Duplicate eMMC sysfs device')
            devices[device] = {}
        elif line.startswith('FIELD:'):
            field = line[6:]
            if device is None or field not in ('dev', 'size', 'start', 'ro') or field in devices[device]:
                raise ValueError('Unexpected or duplicate sysfs field')
            devices[device][field] = ''
        elif line.strip():
            if device is None or field is None or devices[device][field]:
                raise ValueError('Malformed eMMC sysfs value')
            devices[device][field] = line.strip()
    expected = {}
    sample = common.ROOT / 'examples/partitions.sample.tsv'
    for line in sample.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            name, start, size = line.split()
            expected[name] = (int(start, 0), int(size, 0))
    names = set(expected) | set(AREA_NAMES)
    if set(devices) != names or set(proc) != names:
        raise ValueError('Missing or unexpected eMMC areas/partitions')
    identities = set()
    sizes = {}
    for name, fields in devices.items():
        dev = fields.get('dev', '')
        if not re.fullmatch(r'\d+:\d+', dev) or not fields.get('size', '').isdecimal():
            raise ValueError('Missing eMMC identity or capacity: ' + name)
        major, minor = map(int, dev.split(':'))
        size = int(fields['size']) * 512
        if (major, minor) in identities or proc[name] != (major, minor, size):
            raise ValueError('eMMC proc/sysfs identity or capacity mismatch: ' + name)
        identities.add((major, minor))
        if size <= 0 or size % 4096 or size >= 2**32 or fields.get('ro') not in ('0', '1'):
            raise ValueError('Unsupported eMMC capacity/alignment/state: ' + name)
        sizes[name] = size
        if name in expected:
            if not fields.get('start', '').isdecimal():
                raise ValueError('Missing partition start: ' + name)
            if (int(fields['start']) * 512, size) != expected[name]:
                raise ValueError('Partition differs from known ZV-E10 layout: ' + name)
        elif fields.get('start', '') not in ('', '0'):
            raise ValueError('Whole area has nonzero start: ' + name)
    end = max(start + size for start, size in expected.values())
    if sizes['nflasha'] < end:
        raise ValueError('Partitions extend beyond the user area')
    for name in ('nflashaB0', 'nflashaB1'):
        if sizes[name] < 131072 or sizes[name] % 131072 or sizes[name] > 32 * 1048576:
            raise ValueError('Unsupported boot-area capacity: ' + name)
    return {name: sizes[name] for name in AREA_NAMES}


def collect(camera):
    result = {}
    for key, cmd in (('partitions', 'busybox cat /proc/partitions'), ('layout', LAYOUT_COMMAND)):
        reply = common.command(camera.dev, 'emmc_' + key, cmd, 30)
        if reply['exit_code']:
            raise RuntimeError('eMMC metadata query failed: ' + key)
        result[key] = reply['output']
    return result


def dispatch(camera, request, session, write_mode):
    """Optional chip identity from sysfs; no mmc utility or config writes."""
    backend = getattr(camera, '_jiritsu_backend', None)
    expected = backend.expected if backend is not None else common.EXPECTED_VERSION
    for _ in range(2):
        common.check_version(camera, expected)
    result = collect(camera)
    try:
        result['regions'] = validate(result['partitions'], result['layout'])
    except ValueError as exc:
        result['layout_error'] = str(exc)
    reply = common.command(camera.dev, 'emmc_identity', INFO_COMMAND, 30)
    if reply['exit_code']:
        raise RuntimeError('eMMC identity query failed')
    result.update(action='emmc-info', identity=reply['output'],
                  identity_available=bool(reply['output'].strip()),
                  privacy='CID may contain a device serial; redact before sharing')
    return result
