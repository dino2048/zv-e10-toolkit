"""Jiritsu-backed persistent shell and bounded block reads (no boot persistence)."""
import hashlib
from contextlib import contextmanager
from pathlib import Path
import re
import struct
import time
import uuid

import zve10_common as common
from zve10_read_file_jiritsu import read_file

FIRMWARES = {'2.02': b'30110_05.2025031501', '2.03': b'30110_06.2026060501'}
REGIONS = {'/dev/nflasha': 1954545664, '/dev/nflashaB0': 4194304,
           '/dev/nflashaB1': 4194304, '/dev/nflasha5': 62914560}
PAYLOAD_SHA = 'c22deba2d43a6643c628a0dd5e7f524fa7b50dcc766fcee0eb37d667895c4b24'

class BackupCancelled(Exception):
    pass

def jcmd(camera, code, data=b''):
    response = camera._sendAdjustControlPacket(0x1001, code, data)
    if len(response) < 4:
        raise RuntimeError('Jiritsu command %d: short status reply (%d bytes)' % (code, len(response)))
    status = struct.unpack_from('<I', response)[0]
    if status:
        raise RuntimeError('Jiritsu command %d failed: status 0x%08x' % (code, status))
    return response[4:]

def upload_verified(camera, path, data):
    """Small file upload, retaining firmware path normalization semantics."""
    if not path.startswith(('/tmp/jiritsu/', '/tmp_network/zve10-')) or '..' in path:
        raise ValueError('Unexpected temporary upload path')
    if not data or len(data) > 65536:
        raise ValueError('Only small helpers/commands may be uploaded')
    transport = '/tmp/jiritsu/../..' + path if path.startswith('/tmp_network/') else path
    jcmd(camera, 15, b'\0' + transport.encode('ascii') + b'\0')
    jcmd(camera, 16, b'\0\xff\0' + data)
    if read_file(camera, path, 65536) != data:
        raise RuntimeError('Upload readback mismatch; stop before execution')

class JiritsuBackend:
    def __init__(self, camera, session, firmware, cancelled=lambda: False):
        self.camera, self.session = camera, Path(session)
        self.expected = FIRMWARES[firmware]
        self.ram = '/tmp_network/zve10-' + uuid.uuid4().hex[:12]
        self.number = 0
        self.started = False
        self.cancellable = False
        self.chunk_bytes = 524288
        self.cancelled = cancelled
        self.status = {'backend': 'jiritsu', 'requires_power_cycle': False}

    def start(self):
        versions = [read_file(self.camera, '/version.txt', 64) for _ in range(2)]
        if versions != [self.expected, self.expected]:
            raise RuntimeError('Two exact firmware-version reads required')
        self.status['system_version'] = self.expected.decode()
        # SET_FILE2 mounts the workspace but cannot create its mountpoint.
        # Use the firmware's MOUNT initialization before inspecting/uploading
        # loader files, including on cameras never prepared by earlier tools.
        self.status['workspace_initialized'] = False
        jcmd(self.camera, 2, b'\x00\x00')
        self.status['workspace_initialized'] = True
        for path in ('/tmp/jiritsu/run.sh', '/tmp/jiritsu/libJit.so', '/tmp/jiritsu/out.txt'):
            try:
                read_file(self.camera, path, 65536)
            except RuntimeError as exc:
                if '0x10000006' not in str(exc):
                    raise
            else:
                raise RuntimeError('Existing loader workspace: inspect it before starting; no overwrite')
        payload = (common.ROOT / 'helpers/jiritsu-shell/launch.so').read_bytes()
        if len(payload) != 440 or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA:
            raise RuntimeError('Unknown root loader; rebuild/check its source')
        r = self.ram
        script = f'''#!/bin/sh
grep ' /tmp_network tmpfs ' /proc/mounts >/dev/null || exit 31
mkdir '{r}' || exit 32
exec >'{r}/daemon.log' 2>&1
cat /proc/$$/status >'{r}/ready'
echo $$ >'{r}/pid'
while :; do
 if [ -f '{r}/input' ] && [ -f '{r}/go' ]; then
  mv '{r}/input' '{r}/current' || exit 33
  . '{r}/current' >'{r}/output.tmp' 2>&1
  zv_rc=$?
  printf '\\n__ZV_RC__:%s\\n' "$zv_rc" >>'{r}/output.tmp'
  mv '{r}/output.tmp' '{r}/output'
  rm '{r}/current'
 else
  sleep "${{ZV_POLL:-1}}"
 fi
done
'''.encode()
        (self.session / 'root-daemon.sh').write_bytes(script)
        common.restore_owner(self.session / 'root-daemon.sh')
        self.status['requires_power_cycle'] = True
        upload_verified(self.camera, '/tmp/jiritsu/run.sh', script)
        self.status['loader_upload_attempted'] = True
        # A failed response can still mean the constructor ran: never retry blindly.
        upload_verified(self.camera, '/tmp/jiritsu/libJit.so', payload)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                ready = read_file(self.camera, r + '/ready', 16384)
                if re.search(rb'^Uid:\s+0\s+0\s+0\s+0\s*$', ready, re.M):
                    break
                raise ValueError('Loaded process is not root')
            except RuntimeError as exc:
                if '0x10000006' not in str(exc):
                    raise
                time.sleep(.25)
        else:
            raise RuntimeError('No root-ready marker; do not re-upload')
        self.started = True
        self.status.update(root_uid=0, ram_workspace=r, requires_power_cycle=True)
        self.camera._session_read = self.read_path
        self.camera.dev._session_command = self.command
        self.camera._jiritsu_backend = self

    def command(self, label, command, timeout=60):
        if not self.started or not isinstance(command, str) or not command.isascii() or len(command) > 8192:
            raise ValueError('Invalid root command or inactive session')
        if re.search(r'\b(exit|exec|kill|trap|return)\b', command):
            raise ValueError('Do not terminate/replace the persistent shell; close service and power-cycle')
        self.number += 1
        marker = '__ZV_CMD_%d__' % self.number
        if self.number > 1:
            # Root removes the marker after output is safely read by the host.
            jcmd(self.camera, 15, b'\0' + ('/tmp/jiritsu/../..'+self.ram+'/go').encode() + b'\0')
            jcmd(self.camera, 18, b'\0\xff')
        upload_verified(self.camera, self.ram+'/input',
                        ("printf '%s\\n'\n" % marker + command + '\n').encode())
        upload_verified(self.camera, self.ram+'/go', b'go\n')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data = read_file(self.camera, self.ram+'/output', 65536)
                if data.startswith((marker+'\n').encode()):
                    end = re.search(rb'\n__ZV_RC__:(\d+)\n$', data)
                    if end:
                        return {'name': label, 'command': command, 'exit_code': int(end[1]),
                                'output': data[len(marker)+1:end.start()].decode('utf8', 'replace')}
            except RuntimeError as exc:
                if '0x10000006' not in str(exc):
                    raise
            time.sleep(.02)
        raise TimeoutError('Root command timed out; no automatic retry')

    def run(self, command):
        result = self.command('transport', command)
        if result['exit_code']:
            raise RuntimeError('Camera command failed: ' + str(result))
        return result['output']

    @contextmanager
    def backup_buffer(self, chunk_kib=512):
        """Own only this session's RAM mount; keep command files outside it."""
        if type(chunk_kib) is not int or chunk_kib not in (512, 1024, 2048, 4096):
            raise ValueError('chunk_kib must be 512, 1024, 2048 or 4096')
        if getattr(self, 'dedicated_tmpfs', False) or hasattr(self, 'chunk_dir'):
            raise ValueError('A dedicated buffer is already active')
        old_chunk = self.chunk_bytes
        if chunk_kib == 512:
            try:
                self.chunk_bytes = 524288
                yield {'chunk_bytes': 524288, 'dedicated_tmpfs_bytes': 0}
            finally:
                self.chunk_bytes = old_chunk
            return
        # The mount/unmount commands otherwise each wait for the daemon's 1 s
        # idle poll; the reader itself uses the same fast-poll handshake.
        self.run('sleep 0.01 && ZV_POLL=0.01')
        mem = self.run('busybox cat /proc/meminfo')
        values = {k: int(v) for k, v in re.findall(
            r'^(MemFree|Cached|Buffers|Shmem):\s+(\d+) kB', mem, re.M)}
        if not {'MemFree', 'Cached', 'Buffers'} <= values.keys():
            raise ValueError('Missing memory capacity information')
        available = sum(values[k] for k in ('MemFree', 'Cached', 'Buffers')) - values.get('Shmem', 0)
        if available < 32768:
            raise ValueError('Need at least 32 MiB free/reclaimable memory for the 8 MiB RAM buffer')
        bulk = self.ram + '/backup-buffer'
        created = attempted = False
        self.status['backup_buffer_removed'] = False
        try:
            self.run('busybox mkdir ' + bulk)
            created = True
            attempted = True
            self.run('busybox mount -t tmpfs -o size=8m,mode=700 zvbackup ' + bulk)
            mounts = self.run('busybox cat /proc/mounts')
            rows = [line.split() for line in mounts.splitlines() if len(line.split()) >= 4 and line.split()[1] == bulk]
            if len(rows) != 1 or rows[0][:3] != ['zvbackup', bulk, 'tmpfs']:
                raise RuntimeError('Dedicated backup tmpfs identity not confirmed')
            self.chunk_dir, self.dedicated_tmpfs = bulk, True
            self.chunk_bytes = chunk_kib * 1024
            yield {'chunk_bytes': self.chunk_bytes, 'dedicated_tmpfs_bytes': 8388608,
                   'free_reclaimable_kib': available}
        finally:
            self.chunk_bytes = old_chunk
            self.dedicated_tmpfs = False
            if hasattr(self, 'chunk_dir'):
                del self.chunk_dir
            try:
                if attempted:
                    mounts = self.run('busybox cat /proc/mounts')
                    rows = [line.split() for line in mounts.splitlines() if len(line.split()) >= 3 and line.split()[1] == bulk]
                    if rows:
                        if len(rows) != 1 or rows[0][:3] != ['zvbackup', bulk, 'tmpfs']:
                            raise RuntimeError('Unexpected mount identity; do not touch it')
                        self.run('busybox rm -f ' + bulk + '/chunk; cd /; busybox umount ' + bulk + '; ZV_POLL=1')
                        mounts = self.run('busybox cat /proc/mounts')
                        if any(line.split()[1] == bulk for line in mounts.splitlines() if len(line.split()) >= 2):
                            raise RuntimeError('Backup RAM buffer remains mounted')
                if created:
                    self.run('busybox rmdir ' + bulk + '; ZV_POLL=1')
                self.status['backup_buffer_removed'] = True
            except Exception as exc:
                self.status['backup_buffer_cleanup_error'] = repr(exc)
                raise

    def read_path(self, path, sink=None):
        if path in ('/proc', '/sys') or path.startswith(('/proc/', '/sys/')):
            raise ValueError('Read proc/sys pseudo-files through shell cat, not Jiritsu GET_FILE')
        if not path.startswith('/dev/'):
            data = read_file(self.camera, path, 32*1048576)
            if sink is not None:
                sink.write(data)
                return 0, None
            return 0, data
        if path not in REGIONS:
            raise ValueError('Block reads restricted to known user/boot/WBI regions')
        chunk_bytes = self.chunk_bytes
        if type(chunk_bytes) is not int or chunk_bytes not in (524288, 655360, 786432, 1048576, 2097152, 4194304):
            raise ValueError('Unsupported chunk size')
        name, size = path.split('/')[-1], REGIONS[path]
        if sink is None and size > 64*1048576:
            raise ValueError('Large block reads require a streaming sink')
        live = self.run('cat /sys/class/block/%s/size' % name).strip()
        if not live.isdecimal() or int(live)*512 != size:
            raise ValueError('Runtime block capacity mismatch')
        chunk_dir = getattr(self, 'chunk_dir', self.ram)
        if chunk_bytes > 524288:
            # Larger chunks require an exclusive, separately mounted tmpfs.
            # This firmware has no df applet; never guess shared free space.
            if not getattr(self, 'dedicated_tmpfs', False):
                raise ValueError('Large chunks require a verified dedicated tmpfs')
            mounts = self.run('busybox cat /proc/mounts')
            rows = [line.split() for line in mounts.splitlines()
                    if len(line.split()) >= 4 and line.split()[1:3] == [chunk_dir, 'tmpfs']]
            options = rows[0][3].split(',') if len(rows) == 1 else []
            value = next((item[5:] for item in options if item.startswith('size=')), '')
            match = re.fullmatch(r'(\d+)([kKmM]?)', value)
            capacity = int(match[1]) * {'':1,'k':1024,'m':1048576}[match[2].lower()] if match else 0
            if capacity < chunk_bytes + 131072:
                raise ValueError('Insufficient dedicated tmpfs capacity')
            entries = self.run('busybox ls -A '+chunk_dir).split()
            if any(entry != 'chunk' for entry in entries):
                raise ValueError('Dedicated tmpfs contains unexpected files')
        buffer = bytearray() if sink is None else None
        self.run('sleep 0.01 && ZV_POLL=0.01')
        stats = dict(chunk_bytes=chunk_bytes, bytes=0, command_seconds=0., transfer_seconds=0., verify_seconds=0.)
        started = time.monotonic()
        self.last_read_stats = stats
        try:
            for offset in range(0, size, chunk_bytes):
                if self.cancellable and self.cancelled():
                    raise BackupCancelled('Cancelled at completed block boundary')
                count = min(chunk_bytes, size-offset)
                tick = time.monotonic()
                text = self.run('busybox dd if=%s of=%s/chunk bs=4096 skip=%d count=%d 2>/dev/null && busybox sha256sum %s/chunk' %
                                (path, chunk_dir, offset//4096, count//4096, chunk_dir))
                stats['command_seconds'] += time.monotonic()-tick
                tick = time.monotonic()
                data = read_file(self.camera, chunk_dir+'/chunk', count)
                stats['transfer_seconds'] += time.monotonic()-tick
                tick = time.monotonic()
                if len(data) != count or not re.fullmatch(r'[0-9a-f]{64}\s+\S+\s*', text) or hashlib.sha256(data).hexdigest() != text.split()[0]:
                    raise RuntimeError('Chunk length/camera-host hash mismatch')
                if sink is not None:
                    sink.write(data)
                else:
                    buffer.extend(data)
                stats['verify_seconds'] += time.monotonic()-tick
                stats['bytes'] += len(data)
        finally:
            self.run('rm -f '+chunk_dir+'/chunk; ZV_POLL=1')
            stats['seconds'] = time.monotonic()-started
        return 0, bytes(buffer) if buffer is not None else None

    def read_regular_chunks(self, path, expected_size, chunk_kib=256):
        """Read a known regular file through bounded RAM chunks and host hashes.

        Avoid a single large GET_FILE response on hosts whose USB driver cannot
        complete it. The caller must supply the independently known file size.
        Chunks of 256/512 KiB use the shared 1 MiB /tmp_network mount; larger
        chunks require an active dedicated buffer (see ``backup_buffer``), the
        same mount rules the raw backup uses.
        """
        if (not self.started or not path.startswith('/') or path.startswith(('/dev/', '/proc/', '/sys/'))
                or type(expected_size) is not int or not 0 < expected_size <= 32*1048576
                or type(chunk_kib) is not int or chunk_kib not in (256, 512, 1024, 2048, 4096)):
            raise ValueError('Invalid bounded regular-file read')
        if not self.ram.startswith('/tmp_network/zve10-'):
            raise ValueError('Unexpected RAM workspace')
        chunk_bytes = chunk_kib * 1024
        chunk_dir = getattr(self, 'chunk_dir', self.ram)
        if chunk_bytes > 524288:
            if not getattr(self, 'dedicated_tmpfs', False):
                raise ValueError('Large chunks require a verified dedicated tmpfs')
            mounts = self.run('busybox cat /proc/mounts')
            rows = [line.split() for line in mounts.splitlines()
                    if len(line.split()) >= 4 and line.split()[1:3] == [chunk_dir, 'tmpfs']]
            options = rows[0][3].split(',') if len(rows) == 1 else []
            capacity = self._mount_capacity(options)
            if capacity < chunk_bytes + 131072:
                raise RuntimeError('Dedicated RAM mount too small for bounded read')
            entries = self.run('busybox ls -A ' + chunk_dir).split()
            if any(entry != 'regular-chunk' for entry in entries):
                raise RuntimeError('Dedicated RAM mount contains unexpected files')
        else:
            mounts = self.run('busybox cat /proc/mounts')
            rows = [line.split() for line in mounts.splitlines()
                    if len(line.split()) >= 4 and line.split()[1] == '/tmp_network']
            if len(rows) != 1 or rows[0][2] != 'tmpfs':
                raise RuntimeError('Shared RAM mount identity changed')
            capacity = self._mount_capacity(rows[0][3].split(','))
            if capacity < chunk_bytes + 262144:
                raise RuntimeError('Shared RAM mount too small for bounded read')
        quoted = common.shquote(path)
        # Same fast-poll handshake the block reader uses: without it the root
        # daemon notices a new command only on its default 1 s idle sleep, so
        # every chunk pays up to a second before it starts.
        self.run('sleep 0.01 && ZV_POLL=0.01')
        live_size = self.run('busybox wc -c < ' + quoted).strip()
        if not live_size.isdecimal() or int(live_size) != expected_size:
            raise RuntimeError('Regular file size differs from pinned size')
        common.set_terminal_timeout(self.camera, 30000)
        chunk = chunk_dir + '/regular-chunk'
        result = bytearray()
        stats = dict(chunk_kib=chunk_kib, bytes=0, command_seconds=0.,
                     transfer_seconds=0., verify_seconds=0.)
        self.last_regular_stats = stats
        self.status.update(regular_read_bytes=0, regular_read_chunks=0,
                           regular_chunk_kib=chunk_kib)
        try:
            for offset in range(0, expected_size, chunk_bytes):
                count = min(chunk_bytes, expected_size - offset)
                tick = time.monotonic()
                checksum = self.run(
                    'busybox dd if=%s of=%s bs=4096 skip=%d count=%d 2>/dev/null && busybox sha256sum %s' %
                    (quoted, chunk, offset // 4096, (count + 4095) // 4096, chunk))
                stats['command_seconds'] += time.monotonic() - tick
                tick = time.monotonic()
                data = read_file(self.camera, chunk, chunk_bytes)
                stats['transfer_seconds'] += time.monotonic() - tick
                tick = time.monotonic()
                if (len(data) != count or not re.fullmatch(r'[0-9a-f]{64}\s+\S+\s*', checksum)
                        or hashlib.sha256(data).hexdigest() != checksum.split()[0]):
                    raise RuntimeError('Regular-file chunk length/hash mismatch')
                result.extend(data)
                stats['verify_seconds'] += time.monotonic() - tick
                stats['bytes'] += len(data)
                self.status['regular_read_bytes'] += len(data)
                self.status['regular_read_chunks'] += 1
        finally:
            self.run('busybox rm -f ' + chunk + '; ZV_POLL=1')
        return bytes(result)

    @staticmethod
    def _mount_capacity(options):
        """Return a tmpfs capacity parsed from its mount options, or 0."""
        value = next((item[5:] for item in options if item.startswith('size=')), '')
        match = re.fullmatch(r'(\d+)([kKmM]?)', value)
        return int(match[1]) * {'': 1, 'k': 1024, 'm': 1048576}[match[2].lower()] if match else 0

    def close(self):
        if self.started:
            # Tested handoff: stop the service while the child still exists.
            # Exiting the child first reproducibly made GET_FILE time out.
            self.run('cd /; rm -f /tmp/jiritsu/run.sh /tmp/jiritsu/libJit.so /tmp/jiritsu/out.txt')
            for path in ('/tmp/jiritsu/run.sh', '/tmp/jiritsu/libJit.so', '/tmp/jiritsu/out.txt'):
                try:
                    read_file(self.camera, path, 65536)
                except RuntimeError as exc:
                    if '0x10000006' not in str(exc):
                        raise
                else:
                    raise RuntimeError('Temporary file cleanup not confirmed')
            self.status['loader_files_removed'] = True
            self.started = False
        for obj, key in ((self.camera, '_session_read'), (self.camera.dev, '_session_command')):
            if hasattr(obj, key):
                delattr(obj, key)
