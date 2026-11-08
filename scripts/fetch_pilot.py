"""Fetch only trial 0066 from release ZIPs using checked HTTP byte ranges.

Python standard library + curl. No full archive or part is downloaded. ZIP CRC32
checks member integrity; locally computed SHA256 records the extracted file.
Neither is a verification of the full source archive's SHA256.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'Mianmalol/shiners-social-forces'
TAG = 'data-2026-11-05'
BASE_URL = f'https://github.com/{REPOSITORY}/releases/download/{TAG}/'
CHUNK = 8 * 1024 * 1024
MEMBERS = {
    'shiners-tracks.zip': ('shiners-social-forces/tracks/convert-schooltracker_midline_fov_h5.1.0-8c8f6ad206/10-fish__0066.parquet', 'tracks.parquet'),
    'shiners-networks.zip': ('shiners-social-forces/features/visual-network__from__tracks/0.1-65625b7549/10-fish__0066.parquet', 'networks.parquet'),
    'shiners-videos.zip': ('shiners-social-forces/media/joined/e29d6495a5.67dcc35d06.joined.mp4', 'video.mp4'),
}


def digest_file(path: Path) -> tuple[int, str, str]:
    sha = hashlib.sha256(); crc = 0; size = 0
    with path.open('rb') as source:
        for block in iter(lambda: source.read(CHUNK), b''):
            sha.update(block); crc = zlib.crc32(block, crc); size += len(block)
    return size, sha.hexdigest(), f'{crc:08x}'


def check_range_response(status: int, headers: str, data: bytes,
                         start: int, end: int, total: int) -> None:
    """Only the final response headers matter after HTTPS redirects/proxies."""
    blocks = re.split(r'(?m)^HTTP/[^\r\n]+\r?\n', headers)
    final = blocks[-1]
    match = re.search(r'(?im)^content-range:\s*bytes (\d+)-(\d+)/(\d+)\s*$', final)
    if status != 206 or not match or tuple(map(int, match.groups())) != (start, end, total):
        raise ValueError('Server did not honor the exact byte range and asset size')
    if len(data) != end - start + 1:
        raise ValueError('Incomplete or excessive range response')


class CurlTransport:
    """Bound each request and total requested response bytes, including retries.

    curl's max-filesize rejects a full large-asset response when range is ignored.
    Retries are deliberately disabled so the stated transfer budget stays bounded.
    """
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.requested_bytes = 0

    def _get(self, url: str, limit: int, byte_range=None):
        if self.requested_bytes + limit > self.max_bytes:
            raise ValueError('Transfer budget exceeded; increase --max-transfer-mib explicitly')
        self.requested_bytes += limit
        with tempfile.TemporaryDirectory(prefix='shiner-http-') as tmp:
            body = Path(tmp) / 'body'; headers = Path(tmp) / 'headers'
            cmd = ['curl', '-q', '--fail', '--silent', '--show-error', '--location',
                   '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '15',
                   '--max-time', '120', '--max-filesize', str(limit),
                   '--dump-header', str(headers), '--output', str(body), '--write-out', '%{http_code}']
            if byte_range is not None:
                cmd.extend(['--range', f'{byte_range[0]}-{byte_range[1]}'])
            result = subprocess.run(cmd + [url], check=True, capture_output=True, text=True, timeout=130)
            if body.stat().st_size > limit:
                raise ValueError('Response exceeds bounded request')
            return int(result.stdout.strip()), headers.read_text(), body.read_bytes()

    def manifest(self) -> bytes:
        status, _, data = self._get(BASE_URL + 'release-manifest.json', 2 * 1024 * 1024)
        if status != 200:
            raise ValueError('Unexpected manifest HTTP status')
        return data

    def range(self, name: str, start: int, end: int, total: int) -> bytes:
        status, headers, data = self._get(BASE_URL + name, end - start + 1, (start, end))
        check_range_response(status, headers, data, start, end, total)
        return data


class RemoteArchive(io.RawIOBase):
    """Seek across ordered binary ZIP parts without assembling them on disk."""
    def __init__(self, archive: dict, transport):
        super().__init__()
        self.archive = archive; self.transport = transport; self.position = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError('Invalid whence')
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.archive['size'])
        if position < 0:
            raise ValueError('Negative seek')
        self.position = position
        return position

    def read(self, size=-1):
        remaining = max(0, self.archive['size'] - self.position)
        size = remaining if size is None or size < 0 else min(size, remaining)
        result = []; base = 0
        for part in self.archive['parts']:
            end = base + part['size']
            while size and base <= self.position < end:
                count = min(size, end - self.position, CHUNK)
                start = self.position - base
                block = self.transport.range(part['name'], start, start + count - 1, part['size'])
                if len(block) != count:
                    raise ValueError('Transport returned an incorrect range length')
                result.append(block); self.position += count; size -= count
            base = end
        return b''.join(result)


def validate_manifest(manifest: dict, source: dict) -> dict:
    if manifest.get('schema_version') != 1 or manifest.get('repository') != REPOSITORY or manifest.get('tag') != TAG:
        raise ValueError('Release manifest identity mismatch')
    archives = manifest['archives']
    if {a['name'] for a in archives} != set(MEMBERS) or len(archives) != len(MEMBERS):
        raise ValueError('Unexpected or duplicate archives')
    expected = {a['name']: a for a in source['files']}
    for archive in archives:
        original = expected[archive['name']]
        if any(archive[k] != original[k] for k in ('size', 'sha256')):
            raise ValueError('Release manifest does not match the repository source manifest')
        parts = archive['parts']
        if not parts or sum(p['size'] for p in parts) != archive['size']:
            raise ValueError('Part sizes do not reconstruct the original archive')
        names = [p['name'] for p in parts]
        ordered = [archive['name']] if len(parts) == 1 else [f'{archive["name"]}.part{i:03}' for i in range(1, len(parts)+1)]
        if names != ordered or any(type(p['size']) is not int or p['size'] <= 0 for p in parts):
            raise ValueError('Invalid part names, ordering or sizes')
        member, _ = MEMBERS[archive['name']]
        selected = [m for m in archive['members'] if m['path'] == member]
        if len(selected) != 1 or selected[0]['size'] <= 0 or selected[0]['size'] > 300 * 1024 * 1024:
            raise ValueError('Selected member is absent, duplicated or exceeds pilot size limit')
        if not re.fullmatch('[0-9a-f]{8}', selected[0]['crc32']):
            raise ValueError('Invalid selected member CRC32')
    return {a['name']: a for a in archives}


def atomic_json(path: Path, value: dict):
    if path.is_symlink():
        raise ValueError(f'Refusing symlink output: {path}')
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.metadata-', delete=False) as f:
        tmp = Path(f.name)
        try:
            json.dump(value, f, indent=2); f.write('\n'); f.close()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def fetch_member(archive: dict, member: str, destination: Path, transport,
                 prior: dict | None = None, force=False) -> dict:
    """Atomic extraction; never trust an existing file without rechecking it."""
    matches = [m for m in archive['members'] if m['path'] == member]
    if len(matches) != 1:
        raise ValueError('Member must appear exactly once in release manifest')
    expected = matches[0]
    identity = {'archive': archive['name'], 'archive_sha256_expected': archive['sha256'],
                'member': member, 'size': expected['size'], 'crc32': expected['crc32']}
    if destination.is_symlink():
        raise ValueError(f'Refusing symlink output: {destination}')
    if destination.exists() and not force:
        size, sha, crc = digest_file(destination)
        if (prior is None or any(prior.get(k) != v for k,v in identity.items())
                or size != expected['size'] or crc != expected['crc32'] or sha != prior.get('sha256')):
            raise ValueError(f'Existing file has no matching verified provenance: {destination}; use --force to replace it')
        return prior
    with zipfile.ZipFile(RemoteArchive(archive, transport)) as archive_file:
        infos = [i for i in archive_file.infolist() if i.filename == member]
        if len(infos) != 1:
            raise ValueError('Member must appear exactly once in ZIP directory')
        info = infos[0]
        if (info.file_size != expected['size'] or info.compress_size != expected['compressed_size']
                or f'{info.CRC:08x}' != expected['crc32']):
            raise ValueError('ZIP directory and release manifest disagree')
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.member-', delete=False) as output:
            temporary = Path(output.name)
            try:
                with archive_file.open(info) as content:
                    for block in iter(lambda: content.read(CHUNK), b''):
                        output.write(block)
                output.close()
                size, sha, crc = digest_file(temporary)
                if size != expected['size'] or crc != expected['crc32']:
                    raise ValueError('Extracted size/CRC mismatch')
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
    return {**identity, 'sha256': sha, 'local_file': destination.name,
            'zip_member_crc32_verified': True, 'full_archive_sha256_verified': False,
            'sha256_scope': 'locally computed extracted member, not independently source-authenticated',
            'verified_at_utc': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data'/'0066')
    parser.add_argument('--video', action='store_true', help='Also fetch the approximately 129 MB trial video')
    parser.add_argument('--force', action='store_true', help='Replace existing trial files, even if they fail verification')
    parser.add_argument('--max-transfer-mib', type=int, default=400)
    args = parser.parse_args()
    if args.max_transfer_mib <= 0: parser.error('Transfer budget must be positive')
    if args.output.is_symlink(): parser.error('Output directory may not be a symlink')
    args.output.mkdir(parents=True, exist_ok=True)
    provenance_path = args.output/'provenance.json'
    if provenance_path.is_symlink(): parser.error('Provenance may not be a symlink')
    prior = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    if prior and (prior.get('release_tag') != TAG or prior.get('repository') != REPOSITORY):
        parser.error('Existing provenance belongs to a different release')
    transport = CurlTransport(args.max_transfer_mib * 1024 * 1024)
    raw_manifest = transport.manifest()
    manifest = json.loads(raw_manifest)
    archives = validate_manifest(manifest, json.loads((ROOT/'source-manifest.json').read_text()))
    provenance = {'repository': REPOSITORY, 'release_tag': TAG, 'trial': '10-fish/0066',
                  'release_manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
                  'full_archive_sha256_verified': False, 'files': prior.get('files', {})}
    for name, (member, filename) in MEMBERS.items():
        if name == 'shiners-videos.zip' and not args.video: continue
        entry = fetch_member(archives[name], member, args.output/filename, transport,
                             provenance['files'].get(filename), args.force)
        provenance['files'][filename] = entry
        atomic_json(provenance_path, provenance)
        print(f'{filename}: {entry["size"]:,} bytes; CRC verified; SHA256 {entry["sha256"]}', flush=True)
    atomic_json(args.output/'release-manifest.json', manifest)
    print(f'Bounded request allowance used: {transport.requested_bytes:,} bytes; full archive SHA256 not verified.')


if __name__ == '__main__':
    main()
