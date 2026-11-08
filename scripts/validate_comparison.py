"""Read-only computational QA of all ten completed comparison trials.

This checks recorded files and selected calculations. It does not grant
scientific approval or establish behavioral, causal, or population claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('comparison_runner', ROOT/'scripts/run_comparison.py')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
PILOT_METRICS = ('speed_bl_s', 'acceleration_bl_s2', 'turn_rate_rad_s', 'slip_rad',
                 'curvature_times_L', 'polarization', 'circulation', 'signed_circulation',
                 'spread_bl', 'nearest_neighbor_bl')
POLARIZATION_TOLERANCE = 1e-12


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def degree_quantiles(histogram):
    """Linear sample quantiles from exact integer counts, without expanding rows."""
    degrees = np.asarray(histogram['degree'], dtype=np.int64)
    cumulative = np.cumsum(histogram['count'], dtype=np.int64)
    count = int(cumulative[-1])
    result = {'n': count}
    for q in [.05, .5, .95]:
        if not count:
            result[str(q)] = None
            continue
        rank = q*(count-1)
        lower, upper = math.floor(rank), math.ceil(rank)
        a = int(degrees[np.searchsorted(cumulative, lower, side='right')])
        b = int(degrees[np.searchsorted(cumulative, upper, side='right')])
        result[str(q)] = float(a+(b-a)*(rank-lower))
    return result


def check_pilot(summary, pilot_path):
    pilot = runner.read_json(pilot_path)
    for metric in PILOT_METRICS:
        require(summary[metric] == pilot[metric], f'0066 pilot mismatch: {metric}')
    network = summary['network']
    require(degree_quantiles(network['degree_histogram']) == pilot['visible_degree'],
            '0066 pilot mismatch: visible_degree quantiles')
    for key in ['visible_degree_mean', 'reciprocal_edge_fraction']:
        require(network[key] == pilot[key], f'0066 pilot mismatch: {key}')
    return {'primary_quantile_dictionaries': len(PILOT_METRICS),
            'network_degree_quantile_dictionaries': 1, 'network_scalars': 2,
            'comparison': 'Exact JSON numeric equality', 'max_absolute_difference': 0.0,
            'pilot_summary_sha256': runner.file_hash(pilot_path)}


def check_independent_polarization(tracks_path, collective, fish):
    finite = collective.loc[np.isfinite(collective.polarization), ['frame', 'polarization']].sort_values('frame')
    require(len(finite) >= 5, f'Fewer than five finite primary P frames: {tracks_path}')
    selected = finite.iloc[np.linspace(0, len(finite)-1, 5, dtype=int)]
    frames = [int(x) for x in selected.frame]
    # Only three raw columns and these five frame IDs are requested. No metric
    # implementation is imported; trig and summation below are independent.
    tracks = pd.read_parquet(tracks_path, columns=['frame', 'id', 'ANGLE'],
                             filters=[('frame', 'in', frames)])
    require(set(tracks.frame) == set(frames), f'Filtered frame mismatch: {tracks_path}')
    checks = []
    for frame, expected in selected.itertuples(index=False, name=None):
        group = tracks.loc[tracks.frame == frame].sort_values('id')
        require(len(group) == fish and group.id.nunique() == fish,
                f'Incomplete independent P fish set: {tracks_path}, frame {frame}')
        angles = group.ANGLE.to_numpy(dtype=float)
        require(np.isfinite(angles).all(), f'Nonfinite raw heading: {tracks_path}, frame {frame}')
        x = math.fsum(math.cos(angle) for angle in angles)/fish
        y = math.fsum(math.sin(angle) for angle in angles)/fish
        independent = math.hypot(x, y)
        difference = abs(independent-float(expected))
        require(difference <= POLARIZATION_TOLERANCE,
                f'Independent P mismatch: {tracks_path}, frame {frame}, difference {difference}')
        checks.append({'frame': int(frame), 'fish': fish, 'saved': float(expected),
                       'independent': independent, 'absolute_difference': difference})
    return {'selection': 'First, quarter, middle, three-quarter and last index of sorted finite primary P frames',
            'frames_checked': len(checks), 'checks': checks,
            'max_absolute_difference': max(item['absolute_difference'] for item in checks)}


def check_metadata_and_histogram(data, summary, collective):
    track_rows = pq.ParquetFile(data/'tracks.parquet').metadata.num_rows
    network_rows = pq.ParquetFile(data/'networks.parquet').metadata.num_rows
    network, quality = summary['network'], summary['quality']
    fish, frames = int(summary['fish']), int(quality['frames'])
    require(track_rows == quality['track_rows'] == fish*frames, f'Track row accounting mismatch: {data}')
    require(network_rows == network['network_rows'], f'Network row accounting mismatch: {data}')
    require(network['fish'] == fish and network['tracked_frame_count'] == frames,
            f'Network trial dimensions mismatch: {data}')
    require(len(collective) == frames and collective.frame.nunique() == frames,
            f'Collective frame accounting mismatch: {data}')
    histogram = network['degree_histogram']
    require(histogram['degree'] == list(range(fish)), f'Degree labels mismatch: {data}')
    counts = histogram['count']
    require(len(counts) == fish and all(type(x) is int and x >= 0 for x in counts),
            f'Invalid degree counts: {data}')
    observations = sum(counts)
    weighted_edges = sum(degree*count for degree, count in zip(histogram['degree'], counts))
    require(observations == network['observer_frame_count'] == network['covered_frame_count']*fish,
            f'Observer denominator mismatch: {data}')
    require(weighted_edges == network_rows, f'Histogram weighted edge count mismatch: {data}')
    require(network['covered_frame_count']+len(network['network_uncovered_frames']) == frames,
            f'Network coverage accounting mismatch: {data}')
    mean = weighted_edges/observations if observations else None
    fraction = weighted_edges/(observations*(fish-1)) if observations and fish > 1 else None
    require(mean == network['visible_degree_mean'], f'Histogram mean degree mismatch: {data}')
    require(fraction == network['visible_fraction_mean'], f'Histogram mean visible fraction mismatch: {data}')
    angular = network['angular_size_histogram']
    require(sum(angular['count'])+angular['underflow']+angular['overflow'] == network_rows,
            f'Angular histogram row accounting mismatch: {data}')
    return {'metadata_files_checked': 2, 'track_rows': int(track_rows), 'network_rows': int(network_rows),
            'frames': frames, 'fish': fish, 'observer_frames': observations,
            'histogram_weighted_edges': weighted_edges, 'histogram_mean_degree': mean,
            'mean_degree_max_absolute_difference': 0.0}


def validate(config, data_root, output_root, pilot, report):
    config, data_root, output_root, pilot, report = [Path(p).resolve()
        for p in (config, data_root, output_root, pilot, report)]
    cfg = runner.read_json(config)
    trials = cfg.get('trials')
    require(isinstance(trials, list) and len(trials) == len(set(trials)) == 10,
            'Validation requires exactly ten distinct configured trials')
    require('10-fish__0066' in trials, 'The 0066 pilot must be included')
    # Fail before hashing gigabytes if the run is still incomplete.
    for trial in trials:
        require(Path(trial).name == trial, f'Unsafe trial name: {trial}')
        for name in ['summary.json', 'provenance.json', 'config.json', 'collective.csv']:
            require((output_root/trial/name).is_file(), f'Incomplete trial: {trial}/{name}')
    results = []
    common_sources = None
    totals = {'trials': 0, 'input_files': 0, 'input_bytes': 0,
              'output_files_including_provenance': 0, 'output_bytes_including_provenance': 0,
              'track_rows': 0, 'network_rows': 0, 'frames': 0,
              'input_hash_checks': 0, 'source_hash_checks': 0, 'output_hash_checks': 0,
              'independent_polarization_frames': 0}
    pilot_check = None
    for trial in trials:
        print(f'{trial}: validating saved hashes, accounting and independent P samples', flush=True)
        data, output = data_root/trial, output_root/trial
        runner.validate_completed(output, data, config)
        provenance = runner.read_json(output/'provenance.json')
        summary = runner.read_json(output/'summary.json')
        require(runner.read_json(output/'config.json') == cfg, f'Config differs from current config: {trial}')
        if common_sources is None:
            common_sources = provenance['source_hashes']
        require(provenance['source_hashes'] == common_sources, f'Analysis source snapshot differs: {trial}')
        collective = pd.read_csv(output/'collective.csv', usecols=['frame', 'polarization'])
        accounting = check_metadata_and_histogram(data, summary, collective)
        polarization = check_independent_polarization(data/'tracks.parquet', collective, int(summary['fish']))
        if trial == '10-fish__0066':
            pilot_check = check_pilot(summary, pilot)
        input_paths = [runner._resolve_recorded(name, ROOT) for name in provenance['input_hashes']]
        output_paths = [output/name for name in provenance['output_hashes']]+[output/'provenance.json']
        counts = {'input_files': len(input_paths), 'input_bytes': sum(p.stat().st_size for p in input_paths),
                  'output_files_including_provenance': len(output_paths),
                  'output_bytes_including_provenance': sum(p.stat().st_size for p in output_paths),
                  'input_hash_checks': len(provenance['input_hashes']),
                  'source_hash_checks': len(provenance['source_hashes']),
                  'output_hash_checks': len(provenance['output_hashes'])}
        for key, value in counts.items():
            totals[key] += value
        for key in ['track_rows', 'network_rows', 'frames']:
            totals[key] += accounting[key]
        totals['trials'] += 1
        totals['independent_polarization_frames'] += polarization['frames_checked']
        results.append({'trial': trial, 'strict_provenance_hashes_match': True,
                        'same_source_snapshot': True, 'config_matches': True,
                        'file_totals': counts, 'accounting': accounting,
                        'independent_polarization': polarization})
    result = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'COMPUTATIONAL_CHECKS_PASSED',
        'scope': 'File integrity, common analysis source/configuration, exact pilot parity, row/histogram accounting, and 50 independent sampled P calculations. This is not scientific approval or a complete independent recomputation of all metrics.',
        'alltrials_samesource': True,
        'alltrials_sameconfig': True,
        'source_hashes': common_sources,
        'config_sha256': runner.file_hash(config),
        'validator_sha256': runner.file_hash(Path(__file__)),
        'provenance_validator_sha256': runner.file_hash(ROOT/'scripts/run_comparison.py'),
        'checks': {'strict_hash_trials': len(results), 'same_source_comparisons': len(results)-1,
                   'same_config_comparisons': len(results), 'parquet_metadata_files': 2*len(results),
                   'network_histograms': len(results), 'pilot_parity': pilot_check,
                   'independent_polarization_frames': totals['independent_polarization_frames'],
                   'independent_polarization_absolute_tolerance': POLARIZATION_TOLERANCE,
                   'independent_polarization_max_absolute_difference': max(
                       r['independent_polarization']['max_absolute_difference'] for r in results)},
        'totals': totals,
        'trials': results,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_suffix(report.suffix+'.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    temporary.replace(report)
    print(f'Computational checks passed for {len(results)} trials; report: {report}', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/comparison.json')
    parser.add_argument('--data-root', type=Path, default=ROOT/'data/trials')
    parser.add_argument('--output-root', type=Path, default=ROOT/'reports/comparison/trials')
    parser.add_argument('--pilot-summary', type=Path, default=ROOT/'reports/pilot-0066-reviewed/summary.json')
    parser.add_argument('--report', type=Path, default=ROOT/'reports/comparison/validation.json')
    args = parser.parse_args()
    validate(args.config, args.data_root, args.output_root, args.pilot_summary, args.report)


if __name__ == '__main__':
    main()
