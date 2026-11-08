"""Fetch selected/all golden-shiner track/network members, never videos.

Reuses the pilot's checked byte-range transport and atomic ZIP-member extraction.
ZIP CRC and extracted-file SHA256 are recorded; full archive SHA256 is NOT verified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('_shiners_fetch_helpers', ROOT/'scripts'/'fetch_pilot.py')
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)

TRIALS = (
    '10-fish__0066', '10-fish__0105', '10-fish__0126',
    '30-fish__0084', '30-fish__0115', '30-fish__0120',
    '70-fish__0103', '70-fish__0107', '70-fish__0124',
    '150-fish__150-fish',
)
KINDS = {'tracks': 'shiners-tracks.zip', 'networks': 'shiners-networks.zip'}
PREFIXES = {
    'tracks': 'shiners-social-forces/tracks/convert-schooltracker_midline_fov_h5.1.0-8c8f6ad206/',
    'networks': 'shiners-social-forces/features/visual-network__from__tracks/0.1-65625b7549/',
}


def canonical_trial(value: str) -> str:
    value = value.strip().replace('/', '__')
    if value in ('150-fish', '151-fish', '151-fish__151-fish'):
        value = '150-fish__150-fish'
    if value in TRIALS:
        return value
    matches = [trial for trial in TRIALS if trial.split('__', 1)[1] == value]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f'Unknown trial {value!r}; choose from {", ".join(TRIALS)}')


def selected_trials(values=None, all_trials=False):
    if all_trials and values:
        raise ValueError('Choose --all or --trial, not both')
    if all_trials:
        return list(TRIALS)
    if not values:
        raise ValueError('Specify --all or at least one --trial')
    # Stable deduplication means aliases never repeat downloads.
    return list(dict.fromkeys(canonical_trial(v) for v in values))


def selected_kinds(kind):
    if kind == 'both':
        return list(KINDS)
    if kind not in KINDS:
        raise ValueError('Kind must be tracks, networks, or both; videos are excluded')
    return [kind]


def validate_manifest(manifest: dict, source: dict, trials, kinds):
    if (manifest.get('schema_version') != 1 or manifest.get('repository') != helpers.REPOSITORY
            or manifest.get('tag') != helpers.TAG):
        raise ValueError('Release manifest identity mismatch')
    archives = manifest.get('archives', [])
    names = [a['name'] for a in archives]
    expected_names = {'shiners-tracks.zip', 'shiners-networks.zip', 'shiners-videos.zip'}
    if set(names) != expected_names or len(names) != len(expected_names):
        raise ValueError('Unexpected or duplicate archives')
    originals = {f['name']: f for f in source['files']}
    result = {}
    for archive in archives:
        original = originals[archive['name']]
        if any(archive[k] != original[k] for k in ('size', 'sha256')):
            raise ValueError('Release archive differs from repository source manifest')
        if type(archive['size']) is not int or archive['size'] <= 0:
            raise ValueError('Invalid archive size')
        parts = archive['parts']
        ordered = ([archive['name']] if len(parts) == 1 else
                   [f'{archive["name"]}.part{i:03}' for i in range(1, len(parts)+1)])
        if (not parts or [p['name'] for p in parts] != ordered
                or any(type(p['size']) is not int or p['size'] <= 0 for p in parts)
                or sum(p['size'] for p in parts) != archive['size']):
            raise ValueError('Invalid archive parts, ordering, or sizes')
        result[archive['name']] = archive
    for trial in trials:
        if trial not in TRIALS:
            raise ValueError('Unknown canonical trial')
        for kind in kinds:
            archive = result[KINDS[kind]]
            path = PREFIXES[kind]+trial+'.parquet'
            matches = [m for m in archive['members'] if m['path'] == path]
            if len(matches) != 1:
                raise ValueError(f'Selected member missing or duplicated: {path}')
            m = matches[0]
            if (type(m['size']) is not int or not 0 < m['size'] <= 2*1024**3
                    or type(m['compressed_size']) is not int
                    or not 0 < m['compressed_size'] <= archive['size']
                    or not re.fullmatch('[0-9a-f]{8}', m['crc32'])):
                raise ValueError(f'Invalid selected member size/CRC: {path}')
    return result


def safe_output_directory(path: Path):
    # Check every existing ancestor so an intermediate symlink cannot redirect writes.
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise ValueError(f'Output must not traverse a symlink: {component}')
    path.mkdir(parents=True, exist_ok=True)


def fetch_trials(manifest, source, trials, kinds, output, transport, force=False,
                 manifest_sha256=None):
    archives = validate_manifest(manifest, source, trials, kinds)
    safe_output_directory(output)
    for trial in trials:
        directory = output/trial
        safe_output_directory(directory)
        provenance_path = directory/'provenance.json'
        if provenance_path.is_symlink():
            raise ValueError('Provenance may not be a symlink')
        prior = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
        if prior and (prior.get('repository') != helpers.REPOSITORY
                      or prior.get('release_tag') != helpers.TAG
                      or prior.get('trial') != trial.replace('__', '/')):
            raise ValueError(f'Existing provenance belongs to a different release/trial: {trial}')
        provenance = {
            'repository': helpers.REPOSITORY, 'release_tag': helpers.TAG,
            'trial': trial.replace('__', '/'),
            'release_manifest_sha256': manifest_sha256,
            'full_archive_sha256_verified': False,
            'files': prior.get('files', {}),
        }
        print(f'Starting {trial}: {", ".join(kinds)}', flush=True)
        for kind in kinds:
            filename = kind+'.parquet'
            entry = helpers.fetch_member(archives[KINDS[kind]], PREFIXES[kind]+trial+'.parquet',
                                         directory/filename, transport,
                                         provenance['files'].get(filename), force)
            provenance['files'][filename] = entry
            helpers.atomic_json(provenance_path, provenance)
            print(f'  {filename}: {entry["size"]:,} bytes; member CRC verified; SHA256 {entry["sha256"]}', flush=True)
        helpers.atomic_json(directory/'release-manifest.json', manifest)
        print(f'Completed {trial}', flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    choose = p.add_mutually_exclusive_group(required=True)
    choose.add_argument('--all', action='store_true', help='All ten trials, ordered by group size')
    choose.add_argument('--trial', action='append', help='Repeatable stem, group/sequence, or unique sequence alias')
    p.add_argument('--kind', choices=['tracks', 'networks', 'both'], default='both')
    p.add_argument('--output', type=Path, default=ROOT/'data'/'trials')
    p.add_argument('--manifest', type=Path, help='Use this local release manifest after source-identity checks')
    p.add_argument('--max-transfer-mib', type=int, default=8000)
    p.add_argument('--force', action='store_true', help='Explicitly replace files failing saved-provenance checks')
    args = p.parse_args(argv)
    if args.max_transfer_mib <= 0:
        p.error('Transfer budget must be positive')
    try:
        trials = selected_trials(args.trial, args.all)
        kinds = selected_kinds(args.kind)
        transport = helpers.CurlTransport(args.max_transfer_mib*1024**2)
        local = args.manifest
        if local is None and (ROOT/'data'/'0066'/'release-manifest.json').is_file():
            local = ROOT/'data'/'0066'/'release-manifest.json'
        raw = local.read_bytes() if local else transport.manifest()
        manifest = json.loads(raw)
        source = json.loads((ROOT/'source-manifest.json').read_text())
        fetch_trials(manifest, source, trials, kinds, args.output, transport, args.force,
                     hashlib.sha256(raw).hexdigest())
        print(f'Bounded request allowance used: {transport.requested_bytes:,} bytes; full archive SHA256 not verified.')
    except (ValueError, KeyError, OSError) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
