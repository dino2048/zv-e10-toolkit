#!/usr/bin/env python3
"""Backup property actions for an existing authenticated service session.

Delegates the protocol and persistence to Sony-PMCA-RE. Does not open USB,
start a terminal, or edit Backup.bin/.bak. Snapshots may contain secrets.
"""
import json
import os
from pathlib import Path
import uuid
import zve10_common as common


def dispatch(camera, request, session: Path, write_mode: bool):
    action = request.get('action')
    if action not in ('backup-read', 'backup-write'):
        raise ValueError('Unknown Backup action')
    key = int(str(request['id']), 0)
    if not 0 <= key <= 0xFFFFFFFF:
        raise ValueError('Backup ID must be an unsigned 32-bit integer')
    if action == 'backup-write' and not write_mode:
        raise ValueError('Backup write requires --owner-authorized-write')
    if action == 'backup-write':
        expected = bytes.fromhex(request['expected'])
        value = bytes.fromhex(request['value'])
        if not 1 <= len(value) <= 512 or len(expected) != len(value):
            raise ValueError('Expected/new values must have equal lengths, 1–512 bytes')
    original = bytes(camera.readBackup(key))
    if action == 'backup-write' and original != expected:
        raise ValueError('Original Backup value mismatch; no write')
    record = {'id': hex(key), 'original': original.hex(), 'action': action}
    if action == 'backup-write':
        record['requested'] = value.hex()
    # Exclusive creation preserves every original before any write/save call.
    snapshot = session / (uuid.uuid4().hex + '-backup-property.json')
    fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    common.restore_owner(snapshot)
    if action == 'backup-read':
        return {'id': hex(key), 'value': original.hex(), 'bytes': len(original),
                'snapshot': snapshot.name}
    camera.writeBackup(key, value)
    camera.saveBackup(key >> 16)
    back = bytes(camera.readBackup(key))
    if back != value:
        raise RuntimeError('Backup readback mismatch; stop and review saved original')
    return {'id': hex(key), 'original': original.hex(), 'value': back.hex(),
            'match': True, 'snapshot': snapshot.name}
