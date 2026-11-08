"""Run configured trials sequentially in fresh processes; never overwrite results."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
INPUT_MEMBERS = ('tracks.parquet', 'networks.parquet')


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text())
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object')
        return value
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read valid JSON: {path}') from exc


def downloads_ready(data):
    """The fetcher atomically saves each member before adding its provenance."""
    provenance = data/'provenance.json'
    if not provenance.is_file():
        return False
    files = read_json(provenance).get('files', {})
    if not isinstance(files, dict):
        raise ValueError(f'Invalid fetch member manifest: {provenance}')
    for name in INPUT_MEMBERS:
        path = data/name
        entry = files.get(name, {})
        if not isinstance(entry, dict):
            raise ValueError(f'Invalid fetch member entry: {name}')
        sha = entry.get('sha256')
        if not path.is_file() or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', sha):
            return False
        if entry.get('size') != path.stat().st_size:
            return False
    return True


def _resolve_recorded(path, root):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (root/path).resolve()


def validate_completed(output, data, config, repo=ROOT):
    """Accept only complete results with all recorded digests still matching."""
    if not (output/'summary.json').is_file() or not (output/'provenance.json').is_file():
        raise ValueError(f'Partial output; leave untouched and choose a new output root: {output}')
    provenance = read_json(output/'provenance.json')
    manifests = {}
    for category, root in [('input_hashes', repo), ('source_hashes', repo), ('output_hashes', output)]:
        hashes = provenance.get(category)
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError(f'Missing {category} in {output}/provenance.json')
        manifests[category] = {}
        for name, expected in hashes.items():
            path = _resolve_recorded(name, root)
            if category == 'output_hashes' and not path.is_relative_to(output.resolve()):
                raise ValueError(f'Output hash path escapes trial directory: {name}')
            if not path.is_file() or file_hash(path) != expected:
                raise ValueError(f'Resume refused: {category} mismatch: {path}')
            manifests[category][path] = expected
    required_inputs = {(data/name).resolve() for name in (*INPUT_MEMBERS, 'provenance.json')}
    if set(manifests['input_hashes']) != required_inputs:
        raise ValueError(f'Resume refused: input manifest does not match selected trial: {data}')
    required_sources = {config.resolve(), (repo/'src/shiners/compare_trial.py').resolve(),
                        (repo/'src/shiners/metrics.py').resolve(), (repo/'src/shiners/network_summary.py').resolve()}
    if not required_sources.issubset(manifests['source_hashes']):
        raise ValueError('Resume refused: config or analysis source missing from provenance')
    recorded_outputs = set(manifests['output_hashes'])
    actual_outputs = {p.resolve() for p in output.rglob('*') if p.is_file() and p != output/'provenance.json'}
    if (output/'summary.json').resolve() not in recorded_outputs or recorded_outputs != actual_outputs:
        raise ValueError(f'Resume refused: incomplete or unrecorded output files: {output}')
    summary = read_json(output/'summary.json')
    network = summary.get('network')
    if (summary.get('trial') != data.name.replace('__', '/')
            or not isinstance(network, dict) or 'network_rows' not in network):
        raise ValueError(f'Resume refused: wrong trial or incomplete network analysis: {output}')
    if not provenance.get('fetch_member_hashes_match'):
        raise ValueError('Resume refused: fetch member validation is absent')


def run(config, data_root, output_root, trials=None, resume=False, wait_for_downloads=False,
        poll_interval=10):
    config, data_root, output_root = [Path(p).resolve() for p in (config, data_root, output_root)]
    configured = read_json(config).get('trials')
    if (not isinstance(configured, list) or not configured
            or any(not isinstance(t, str) or not re.fullmatch(r'\d+-fish__[A-Za-z0-9_-]+', t) for t in configured)
            or len(configured) != len(set(configured))):
        raise ValueError('Config trials must be a nonempty list of unique safe trial names')
    selected = list(dict.fromkeys(trials)) if trials else configured
    if any(t not in configured for t in selected):
        raise ValueError('Every --trial must occur in config trials')
    for trial in selected:
        data, output = data_root/trial, output_root/trial
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            if not resume or not output.is_dir():
                raise ValueError(f'Nonempty output; use --resume only for verified completed results: {output}')
            validate_completed(output, data, config)
            print(f'{trial}: verified complete; skipping', flush=True)
            continue
        announced = False
        while not downloads_ready(data):
            if not wait_for_downloads:
                raise ValueError(f'Input members/provenance are incomplete: {data}; use --wait-for-downloads to wait')
            if not announced:
                print(f'{trial}: waiting for tracks and networks with completed fetch provenance', flush=True)
                announced = True
            time.sleep(poll_interval)
        print(f'{trial}: starting fresh analysis process', flush=True)
        subprocess.run([sys.executable, '-m', 'shiners.compare_trial', '--data', str(data),
                        '--output', str(output), '--config', str(config)], cwd=ROOT, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/comparison.json')
    parser.add_argument('--data-root', type=Path, default=ROOT/'data/trials')
    parser.add_argument('--output-root', type=Path, default=ROOT/'reports/comparison/trials')
    parser.add_argument('--trial', action='append', help='Configured trial name; repeat to select several')
    parser.add_argument('--resume', action='store_true', help='Skip completed trials only after checking all saved hashes')
    parser.add_argument('--wait-for-downloads', action='store_true', help='Wait for both input members and fetch provenance')
    args = parser.parse_args(argv)
    try:
        run(args.config, args.data_root, args.output_root, args.trial, args.resume, args.wait_for_downloads)
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
