"""Slow raw backup action on the existing Jiritsu connection; no second USB open."""
import time
import shutil
import uuid
from pathlib import Path

import zve10_backup_raw as raw
import zve10_common as common
import zve10_emmc_layout as emmc
from zve10_jiritsu import BackupCancelled


def write_sums(folder, reads):
    """Write SHA256SUMS with LF endings so sha256sum -c works on every host."""
    text = ''.join('%s  %s\n' % (row['sha256'], row['file']) for row in reads)
    (Path(folder) / 'SHA256SUMS').write_text(text, newline='\n')


def dispatch(camera, request, session, write_mode):
    backend = getattr(camera, '_jiritsu_backend', None)
    if backend is None:
        raise ValueError('Use the Jiritsu backend; the original fast backup CLI remains available on 2.02')
    passes = request.get('passes', 1)
    if type(passes) is not int or passes not in (1, 2):
        raise ValueError('passes must be 1 or 2')
    chunk_kib = request.get('chunk_kib', 512)
    if type(chunk_kib) is not int or chunk_kib not in (512, 1024, 2048, 4096):
        raise ValueError('chunk_kib must be 512, 1024, 2048 or 4096')
    started = time.monotonic()
    folder = Path(session) / (time.strftime('raw-backup-%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(mode=0o700)
    common.restore_owner(folder)
    raw.OUT = folder
    raw.RESULT = {'scope': 'Linux user area plus B0/B1; Jiritsu tmpfs chunks; not RPMB/OTP',
                  'passes': passes, 'backend': 'jiritsu', 'system_version': backend.expected.decode(),
                  'temporary_camera_workspace_writes': True, 'reads': [], 'completed': False}
    marker = Path(session) / 'cancel-backup'
    # A pre-existing cancellation is honored; it is never silently discarded.
    backend.cancellable = True
    try:
        with backend.backup_buffer(chunk_kib) as buffer:
            raw.RESULT['buffer'] = buffer
            raw.RESULT['partitions'] = backend.run('cat /proc/partitions')
            raw.RESULT['mounts'] = backend.run('cat /proc/mounts')
            raw.RESULT['layout'] = backend.run('for p in /sys/class/block/nflasha*; do echo DEVICE:$p; for f in dev size start ro; do echo FIELD:$f; cat "$p/$f" 2>/dev/null; done; done')
            raw.save()
            regions = emmc.validate(raw.RESULT['partitions'], raw.RESULT['layout'])
            raw.RESULT['regions'] = regions
            raw.RESULT['capacity_source'] = 'matching Linux proc/sysfs; known logical partition layout'
            raw.save()
            if shutil.disk_usage(session).free < passes * sum(regions.values()) + 1024**3:
                raise ValueError('Need actual backup capacity plus 1 GiB free host space')
            backend.backup_regions = regions.copy()
            for name in raw.REGIONS:
                rows = [raw.receive(camera, name, i) for i in range(1, passes+1)]
                if passes == 2:
                    a, b = rows
                    raw.RESULT.setdefault('comparisons', {})[name] = {
                        'identical': a['sha256'] == b['sha256'],
                        'differing_1MiB_chunks': [i for i,(x,y) in enumerate(zip(a['chunk_sha256_1MiB'],b['chunk_sha256_1MiB'])) if x != y]}
                    if name != 'nflasha' and a['sha256'] != b['sha256']:
                        raise RuntimeError('Boot-area double read mismatch')
        write_sums(folder, raw.RESULT['reads'])
        raw.RESULT['completed'] = True
    except BackupCancelled:
        raw.RESULT['cancelled'] = True
        raw.RESULT['reason'] = 'Owner cancelled at a completed data-block boundary'
    except Exception as exc:
        raw.RESULT['error'] = repr(exc)
        raise
    finally:
        raw.RESULT['seconds'] = time.monotonic() - started
        raw.RESULT['cleanup'] = dict(backend.status)
        backend.cancellable = False
        if hasattr(backend, 'backup_regions'):
            del backend.backup_regions
        for row in raw.RESULT['reads']:
            if not row['complete']:
                row['partial_file'] = row['file'] + '.part'
        raw.save()
        common.restore_tree_owner(folder)
        if marker.is_file() and not marker.is_symlink():
            marker.unlink()
    return {'backup_dir': str(folder), 'completed': raw.RESULT['completed'],
            'cancelled': raw.RESULT.get('cancelled', False), 'passes': passes}
