#!/usr/bin/env python3
"""Exact-byte APK deployment delta, retaining unchanged official native payloads."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zipfile


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(65536), b''):
            result.update(block)
    return result.hexdigest()


def payload_offset(data, info):
    name_length, extra_length = struct.unpack_from('<HH', data, info.header_offset + 26)
    return info.header_offset + 30 + name_length + extra_length


def create(old, new, patch):
    original = Path(old).read_bytes()
    updated = Path(new).read_bytes()
    with zipfile.ZipFile(old) as old_zip, zipfile.ZipFile(new) as new_zip:
        previous = {entry.filename: entry for entry in old_zip.infolist()}
        segments = []
        cursor = 0
        for entry in sorted(new_zip.infolist(), key=lambda value: value.header_offset):
            start = payload_offset(updated, entry)
            end = start + entry.compress_size
            segments.append({'data': base64.b64encode(updated[cursor:start]).decode('ascii')})
            old_entry = previous.get(entry.filename)
            old_start = payload_offset(original, old_entry) if old_entry else 0
            if old_entry and old_entry.compress_size == entry.compress_size and original[old_start:old_start + entry.compress_size] == updated[start:end]:
                segments.append({'copy': [old_start, entry.compress_size]})
            else:
                segments.append({'data': base64.b64encode(updated[start:end]).decode('ascii')})
            cursor = end
        segments.append({'data': base64.b64encode(updated[cursor:]).decode('ascii')})
    document = {'base': digest(old), 'target': digest(new), 'size': len(updated), 'segments': segments}
    with gzip.open(patch, 'wt', encoding='ascii') as output:
        json.dump(document, output, separators=(',', ':'))
    print('Delta created; target SHA256:', document['target'])


def apply(old, patch, output):
    with gzip.open(patch, 'rt', encoding='ascii') as source:
        document = json.load(source)
    if digest(old) != document['base']:
        raise ValueError('base APK mismatch')
    result = hashlib.sha256()
    count = 0
    partial = output + '.part'
    old_size = os.path.getsize(old)
    with open(old, 'rb') as original, open(partial, 'wb') as destination:
        for segment in document['segments']:
            if 'copy' in segment:
                offset, remaining = segment['copy']
                if offset < 0 or remaining < 0 or offset + remaining > old_size:
                    raise ValueError('invalid delta range')
                original.seek(offset)
                while remaining:
                    block = original.read(min(65536, remaining))
                    if not block:
                        raise ValueError('truncated base APK')
                    destination.write(block)
                    result.update(block)
                    count += len(block)
                    remaining -= len(block)
            else:
                block = base64.b64decode(segment['data'], validate=True)
                destination.write(block)
                result.update(block)
                count += len(block)
        destination.flush()
        os.fsync(destination.fileno())
    if count != document['size'] or result.hexdigest() != document['target']:
        raise ValueError('reconstructed APK mismatch')
    os.replace(partial, output)
    print('Reconstructed APK verified SHA256:', result.hexdigest())


if __name__ == '__main__':
    {'create': create, 'apply': apply}[sys.argv[1]](*sys.argv[2:])
