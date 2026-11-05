"""Verify a source archive and upload byte-preserving parts from a hosted runner."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

import gdown

ROOT = Path(__file__).resolve().parents[1]
PART_SIZE = 1_900_000_000  # Strictly below GitHub's 2 GiB release-asset limit.


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def upload(path, tag, repo):
    for attempt in range(3):
        try:
            gh('release', 'upload', tag, str(path), '--repo', repo, '--clobber')
            return
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def main():
    name, tag = sys.argv[1:]
    repo = os.environ['GITHUB_REPOSITORY']
    source = json.loads((ROOT / 'source-manifest.json').read_text())
    item = next(x for x in source['files'] if x['name'] == name)
    # The by-tag REST endpoint excludes unpublished drafts; list includes them.
    release = next(x for x in json.loads(gh('api', f'repos/{repo}/releases?per_page=100'))
                   if x['tag_name'] == tag)
    if not release['draft']:
        raise RuntimeError('Refusing to replace assets in a published release')
    with tempfile.TemporaryDirectory(prefix='shiners-mirror-') as tmp:
        directory = Path(tmp)
        archive = directory / name
        for attempt in range(3):
            try:
                result = gdown.download(id=item['drive_id'], output=str(archive),
                                        quiet=True, use_cookies=False, resume=True)
                if result is None:
                    raise RuntimeError('Google Drive download did not complete')
                if archive.stat().st_size != item['size'] or sha256(archive) != item['sha256']:
                    archive.unlink(missing_ok=True)
                    raise RuntimeError(f'Source size/SHA256 mismatch: {name}')
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
        print(f'Verified source: {name} ({item["size"]:,} bytes)', flush=True)
        with zipfile.ZipFile(archive) as zf:
            inventory = [{'path': x.filename, 'size': x.file_size,
                          'compressed_size': x.compress_size, 'crc32': f'{x.CRC:08x}'}
                         for x in zf.infolist()]
        parts = []
        if item['size'] < 2**31:
            paths = [archive]
        else:
            paths = []
            with archive.open('rb') as stream:
                index = 1
                while stream.tell() < item['size']:
                    path = directory / f'{name}.part{index:03}'
                    with path.open('wb') as output:
                        remaining = PART_SIZE
                        while remaining:
                            block = stream.read(min(8 * 1024 * 1024, remaining))
                            if not block:
                                break
                            output.write(block)
                            remaining -= len(block)
                    paths.append(path)
                    index += 1
        for path in paths:
            part = {'name': path.name, 'size': path.stat().st_size, 'sha256': sha256(path)}
            upload(path, tag, repo)
            assets = json.loads(gh('api', f'repos/{repo}/releases/{release["id"]}/assets?per_page=100'))
            remote = next(x for x in assets if x['name'] == path.name)
            if (remote['state'] != 'uploaded' or remote['size'] != part['size']
                    or remote.get('digest') != 'sha256:' + part['sha256']):
                raise RuntimeError(f'GitHub asset verification failed: {path.name}')
            parts.append(part)
            print(f'Verified GitHub asset: {path.name}', flush=True)
            if path != archive:
                path.unlink()
        record = {key: item[key] for key in ('name', 'size', 'sha256')}
        record.update(parts=parts, members=inventory)
        manifest = directory / f'{name}.manifest.json'
        manifest.write_text(json.dumps(record, indent=2) + '\n')
        upload(manifest, tag, repo)
        assets = json.loads(gh('api', f'repos/{repo}/releases/{release["id"]}/assets?per_page=100'))
        remote = next(x for x in assets if x['name'] == manifest.name)
        if (remote['state'] != 'uploaded' or remote['size'] != manifest.stat().st_size
                or remote.get('digest') != 'sha256:' + sha256(manifest)):
            raise RuntimeError(f'GitHub metadata verification failed: {manifest.name}')


if __name__ == '__main__':
    main()
