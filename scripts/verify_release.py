"""Assemble manifests and check every GitHub asset against its expected digest."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def main():
    tag = sys.argv[1]
    repo = os.environ['GITHUB_REPOSITORY']
    source = json.loads((ROOT / 'source-manifest.json').read_text())
    release = next(x for x in json.loads(gh('api', f'repos/{repo}/releases?per_page=100'))
                   if x['tag_name'] == tag)
    if not release['draft']:
        raise RuntimeError('Expected a draft release')
    assets = {x['name']: x for x in json.loads(gh('api', f'repos/{repo}/releases/{release["id"]}/assets?per_page=100'))}
    expected_names = {'README.md', 'SHA256SUMS'}
    with tempfile.TemporaryDirectory(prefix='shiners-verify-') as tmp:
        directory = Path(tmp)
        records = []
        for item in source['files']:
            if not item['name'].endswith('.zip'):
                continue
            filename = item['name'] + '.manifest.json'
            expected_names.add(filename)
            gh('release', 'download', tag, '--repo', repo, '--pattern', filename, '--dir', tmp)
            data = (directory / filename).read_bytes()
            assert assets[filename]['size'] == len(data)
            assert assets[filename]['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
            record = json.loads(data)
            for key in ('name', 'size', 'sha256'):
                assert record[key] == item[key], (filename, key)
            assert sum(part['size'] for part in record['parts']) == item['size']
            for part in record['parts']:
                expected_names.add(part['name'])
                remote = assets[part['name']]
                assert remote['state'] == 'uploaded'
                assert remote['size'] == part['size'] < 2**31
                assert remote['digest'] == 'sha256:' + part['sha256']
            records.append(record)
        for name, local in [('README.md', ROOT / 'docs/source-README.md'), ('SHA256SUMS', ROOT / 'SHA256SUMS')]:
            data = local.read_bytes()
            assert assets[name]['size'] == len(data)
            assert assets[name]['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
        # Re-runs may already have the aggregate metadata from a previous success.
        assert set(assets) - expected_names <= {'release-manifest.json', 'ASSET_SHA256SUMS'}
        manifest = directory / 'release-manifest.json'
        manifest.write_text(json.dumps({'schema_version': 1, 'repository': repo, 'tag': tag,
                                       'archives': records}, indent=2) + '\n')
        sums = directory / 'ASSET_SHA256SUMS'
        sums.write_text(''.join(f'{p["sha256"]}  {p["name"]}\n' for r in records for p in r['parts']))
        gh('release', 'upload', tag, str(manifest), str(sums), '--repo', repo, '--clobber')
        uploaded = {x['name']: x for x in json.loads(gh('api', f'repos/{repo}/releases/{release["id"]}/assets?per_page=100'))}
        for path in (manifest, sums):
            data = path.read_bytes()
            assert uploaded[path.name]['state'] == 'uploaded'
            assert uploaded[path.name]['size'] == len(data)
            assert uploaded[path.name]['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
        print(f'Verified all 3 archives: {sum(x["size"] for x in records):,} source bytes')
        print('Draft is ready for publication; original archive and part SHA256 hashes match.')


if __name__ == '__main__':
    main()
