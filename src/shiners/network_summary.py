"""Exact visibility summaries with bounded Parquet batches and packed adjacency.

The largest retained network object is one bit per possible directed fish pair
per tracked frame, padded to a byte at each frame. Row ordering is irrelevant.
A whole track frame absent from the network is unknown coverage, not zero edges.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


COLUMNS = ['frame', 'id1', 'id2', 'n_rays', 'angular_size_deg', 'distance']
ANGULAR_EDGES = np.linspace(0.0, 720.0, 361)  # 2-degree bins, both-eye ray convention


def _finite_numeric(values, name):
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name}: nonnumeric values') from exc
    if not np.isfinite(result).all():
        raise ValueError(f'{name}: null or nonfinite values')
    return result


def _integer_keys(values, name):
    """Validate without losing precision on integer-typed IDs."""
    values = np.asarray(values)
    if values.dtype.kind in 'iu':
        if values.dtype.kind == 'u' and values.size and values.max() > np.iinfo(np.int64).max:
            raise ValueError(f'{name}: integer outside int64 range')
        return values.astype(np.int64, copy=False)
    numeric = _finite_numeric(values, name)
    if ((numeric != np.floor(numeric)).any() or (np.abs(numeric) >= 2**53).any()):
        raise ValueError(f'{name}: noninteger or unsafe floating-point identifier')
    return numeric.astype(np.int64)


def _dense_tracks(tracks):
    missing = {'frame', 'id', 'X', 'Y'} - set(tracks)
    if missing:
        raise ValueError(f'Tracks missing columns: {sorted(missing)}')
    if tracks.empty:
        raise ValueError('Empty tracks')
    for column in ['group', 'sequence']:
        if column in tracks and tracks[column].nunique(dropna=False) > 1:
            raise ValueError('Network summary requires one trial')
    selected = tracks[['frame', 'id', 'X', 'Y']].copy()
    selected['frame'] = _integer_keys(selected.frame.to_numpy(), 'track frame')
    selected['id'] = _integer_keys(selected.id.to_numpy(), 'track id')
    selected['X'] = _finite_numeric(selected.X.to_numpy(), 'track X')
    selected['Y'] = _finite_numeric(selected.Y.to_numpy(), 'track Y')
    if selected.duplicated(['frame', 'id']).any():
        raise ValueError('Duplicate track keys')
    frames = np.sort(selected.frame.unique())
    fish = np.sort(selected.id.unique())
    if len(selected) != len(frames) * len(fish):
        raise ValueError('Incomplete fish set')
    selected = selected.sort_values(['frame', 'id'])
    positions = selected[['X', 'Y']].to_numpy().reshape(len(frames), len(fish), 2)
    return frames, fish, positions


def _lookup(values, labels, name):
    index = np.searchsorted(labels, values)
    if (index >= len(labels)).any():
        raise ValueError(f'Dangling network {name}')
    if not np.array_equal(labels[index], values):
        raise ValueError(f'Dangling network {name}')
    return index


def summarize_network(path, tracks, output_dir=None, batch_size=131072, *, excluded_frames=None):
    """Summarize one network Parquet without materializing its edge table.

    ``tracks`` needs frame/id/X/Y for the full trial. Duplicate edges are rejected
    even across batches. Covered frames include all fish, including zero-degree
    observers. Unknown whole-frame coverage is excluded from degree denominators.
    Optional CSVs include every track frame and NaN metrics for unknown coverage.
    ``excluded_frames`` supplies track-frame IDs with any nonpositive body length
    for a separate whole-frame exclusion sensitivity; primary metrics and every
    raw-row validation retain all frames.
    """
    if not isinstance(batch_size, (int, np.integer)) or batch_size < 1:
        raise ValueError('batch_size must be a positive integer')
    frames, fish, xy = _dense_tracks(tracks)
    frame_count, n = len(frames), len(fish)
    excluded = np.zeros(frame_count, dtype=bool)
    if excluded_frames is not None:
        exclude_ids = _integer_keys(list(excluded_frames), 'excluded frame')
        if exclude_ids.ndim != 1:
            raise ValueError('excluded_frames must contain one-dimensional frame IDs')
        excluded[_lookup(exclude_ids, frames, 'excluded frame')] = True
    source = pq.ParquetFile(path)
    missing = set(COLUMNS) - set(source.schema_arrow.names)
    if missing:
        raise ValueError(f'Network missing columns: {sorted(missing)}')
    float32_geometry = (any(str(tracks[column].dtype).lower() == 'float32' for column in ['X', 'Y'])
                        or source.schema_arrow.field('distance').type == pa.float32())
    distance_tolerance = 1e-3 if float32_geometry else 1e-4
    angular_tolerance = 1e-4 if source.schema_arrow.field('angular_size_deg').type == pa.float32() else 1e-9
    bits_per_frame = n * n
    bytes_per_frame = (bits_per_frame + 7) // 8
    packed = np.zeros(frame_count * bytes_per_frame, dtype=np.uint8)
    rows = 0
    angular_counts = np.zeros(len(ANGULAR_EDGES)-1, dtype=np.int64)
    underflow = overflow = 0
    max_distance_error = max_angular_error = 0.0
    angular_min = float('inf'); angular_max = -float('inf')
    distance_min = float('inf'); distance_max = -float('inf')
    ray_min = None; ray_max = None
    batches = 0
    for batch in source.iter_batches(batch_size=int(batch_size), columns=COLUMNS):
        batches += 1
        arrays = {}
        for column in COLUMNS:
            arrow = batch.column(batch.schema.get_field_index(column))
            if arrow.null_count:
                raise ValueError(f'Network {column}: null values')
            value = arrow.to_numpy(zero_copy_only=False)
            arrays[column] = (_integer_keys(value, f'network {column}')
                              if column in ['frame', 'id1', 'id2', 'n_rays']
                              else _finite_numeric(value, f'network {column}'))
        if not batch.num_rows:
            continue
        fi = _lookup(arrays['frame'], frames, 'frame')
        observer = _lookup(arrays['id1'], fish, 'observer')
        observed = _lookup(arrays['id2'], fish, 'observed fish')
        if (observer == observed).any():
            raise ValueError('Self visibility edge')
        rays = arrays['n_rays']
        if (rays <= 0).any():
            raise ValueError('Nonpositive ray count')
        angular = arrays['angular_size_deg']
        angular_error = np.abs(angular - .36*rays)
        max_angular_error = max(max_angular_error, float(angular_error.max()))
        if angular_error.max() > angular_tolerance:
            raise ValueError('Angular size inconsistent with ray count')
        distances = arrays['distance']
        actual_distance = np.linalg.norm(xy[fi, observer] - xy[fi, observed], axis=1)
        error = np.abs(actual_distance - distances)
        max_distance_error = max(max_distance_error, float(error.max()))
        if (distances < 0).any() or error.max() > distance_tolerance:
            raise ValueError('Network center distance inconsistent with tracks')
        # Validate uniqueness before OR operations; repeated byte indices are fine,
        # but the same bit means the same directed edge at the same frame.
        pair = observer * n + observed
        keys = fi * bits_per_frame + pair
        if len(np.unique(keys)) != len(keys):
            raise ValueError('Duplicate visibility edges within batch')
        byte = fi * bytes_per_frame + pair // 8
        mask = np.left_shift(np.uint8(1), (pair % 8).astype(np.uint8))
        if (np.bitwise_and(packed[byte], mask) != 0).any():
            raise ValueError('Duplicate visibility edges across batches')
        np.bitwise_or.at(packed, byte, mask)
        rows += batch.num_rows
        angular_counts += np.histogram(angular, bins=ANGULAR_EDGES)[0]
        underflow += int((angular < ANGULAR_EDGES[0]).sum())
        overflow += int((angular > ANGULAR_EDGES[-1]).sum())
        angular_min = min(angular_min, float(angular.min()))
        angular_max = max(angular_max, float(angular.max()))
        distance_min = min(distance_min, float(distances.min()))
        distance_max = max(distance_max, float(distances.max()))
        ray_min = int(rays.min()) if ray_min is None else min(ray_min, int(rays.min()))
        ray_max = int(rays.max()) if ray_max is None else max(ray_max, int(rays.max()))
    if rows != source.metadata.num_rows:
        raise ValueError('Streamed row count does not match Parquet metadata')

    degrees_histogram = np.zeros(n, dtype=np.int64)
    excluded_degrees_histogram = np.zeros(n, dtype=np.int64)
    edge_counts = np.zeros(frame_count, dtype=np.int64)
    reciprocal_counts = np.zeros(frame_count, dtype=np.int64)
    packed_by_frame = packed.reshape(frame_count, bytes_per_frame)
    # At most 128*N*N unpacked bits resident, ~2.9 MB for N=151.
    for start in range(0, frame_count, 128):
        stop = min(start+128, frame_count)
        adjacency = np.unpackbits(packed_by_frame[start:stop], axis=1, bitorder='little')[:, :bits_per_frame]
        adjacency = adjacency.reshape(stop-start, n, n)
        degree = adjacency.sum(axis=2, dtype=np.int64)
        edges = degree.sum(axis=1)
        edge_counts[start:stop] = edges
        reciprocal_counts[start:stop] = np.bitwise_and(adjacency, adjacency.swapaxes(1, 2)).sum(axis=(1, 2), dtype=np.int64)
        covered_here = edges > 0
        degrees_histogram += np.bincount(degree[covered_here].ravel(), minlength=n)
        excluded_here = covered_here & excluded[start:stop]
        excluded_degrees_histogram += np.bincount(degree[excluded_here].ravel(), minlength=n)
    covered = edge_counts > 0
    covered_count = int(covered.sum())
    if int(edge_counts.sum()) != rows:
        raise ValueError('Packed adjacency row-count consistency failed')
    eligible_observations = covered_count * n
    per_frame = pd.DataFrame({'frame': frames, 'covered': covered, 'edge_count': edge_counts,
                              'mean_degree': np.where(covered, edge_counts/n, np.nan)})
    reciprocity = np.full(frame_count, np.nan)
    np.divide(reciprocal_counts, edge_counts, out=reciprocity, where=covered)
    per_frame['reciprocal_edge_fraction'] = reciprocity
    per_frame['excluded_nonpositive_length_sensitivity'] = excluded
    # Match durations by observed frame order, not numeric frame ID or edge
    # coverage. Gaps and wholly missing network frames must not shift the window.
    matched_count = min(17999, frame_count)
    matched_covered = covered[:matched_count]
    matched_covered_count = int(matched_covered.sum())
    matched_rows = int(edge_counts[:matched_count].sum())
    matched_observations = matched_covered_count * n
    matched_duration = {
        'target_frame_count': 17999,
        'selection': 'First min(17999, tracked_frame_count) sorted observed track frames',
        'tracked_frame_count': matched_count,
        'frame_start': int(frames[0]),
        'frame_end': int(frames[matched_count-1]),
        'covered_frame_count': matched_covered_count,
        'coverage_fraction': float(matched_covered_count/matched_count),
        'network_uncovered_frames': frames[:matched_count][~matched_covered].tolist(),
        'observer_frame_count': matched_observations,
        'network_rows': matched_rows,
        'visible_degree_mean': float(matched_rows/matched_observations) if matched_observations else None,
        'visible_fraction_mean': float(matched_rows/(matched_observations*(n-1))) if matched_observations and n > 1 else None,
        'reciprocal_edge_fraction': float(reciprocal_counts[:matched_count].sum()/matched_rows) if matched_rows else None,
    }
    kept = ~excluded
    kept_count = int(kept.sum())
    kept_covered_count = int((kept & covered).sum())
    kept_rows = int(edge_counts[kept].sum())
    kept_observations = kept_covered_count*n
    exclusion_sensitivity = {
        'frame_ids_provided': excluded_frames is not None,
        'selection': 'Exclude whole caller-supplied frames with any nonpositive body length; retain all frames in primary metrics and raw-row QC',
        'excluded_tracked_frames': frames[excluded].tolist(),
        'excluded_tracked_frame_count': int(excluded.sum()),
        'excluded_covered_frames': frames[excluded & covered].tolist(),
        'excluded_covered_frame_count': int((excluded & covered).sum()),
        'excluded_network_rows': int(rows-kept_rows),
        'tracked_frame_count': kept_count,
        'covered_frame_count': kept_covered_count,
        'coverage_fraction': float(kept_covered_count/kept_count) if kept_count else None,
        'network_uncovered_frames': frames[kept & ~covered].tolist(),
        'observer_frame_count': kept_observations,
        'network_rows': kept_rows,
        'visible_degree_mean': float(kept_rows/kept_observations) if kept_observations else None,
        'visible_fraction_mean': float(kept_rows/(kept_observations*(n-1))) if kept_observations and n > 1 else None,
        'reciprocal_edge_fraction': float(reciprocal_counts[kept].sum()/kept_rows) if kept_rows else None,
        'degree_histogram': {'degree': list(range(n)), 'count': (degrees_histogram-excluded_degrees_histogram).tolist()},
    }
    summary = {
        'network_rows': int(rows), 'fish': n, 'tracked_frame_count': frame_count,
        'covered_frame_count': covered_count,
        'network_uncovered_frames': frames[~covered].tolist(),
        'observer_frame_count': eligible_observations,
        'visible_degree_mean': float(rows/eligible_observations) if eligible_observations else None,
        'visible_fraction_mean': float(rows/(eligible_observations*(n-1))) if eligible_observations and n > 1 else None,
        'reciprocal_edge_fraction': float(reciprocal_counts.sum()/rows) if rows else None,
        'degree_histogram': {'degree': list(range(n)), 'count': degrees_histogram.tolist()},
        'angular_size_histogram': {'edges_deg': ANGULAR_EDGES.tolist(), 'count': angular_counts.tolist(),
                                   'underflow': underflow, 'overflow': overflow},
        'angular_size_range_deg': [angular_min, angular_max] if rows else None,
        'distance_range_px': [distance_min, distance_max] if rows else None,
        'ray_count_range': [ray_min, ray_max] if rows else None,
        'matched_duration': matched_duration,
        'nonpositive_length_frame_exclusion_sensitivity': exclusion_sensitivity,
        'quality': {
            'passed': ['required columns and finite values', 'integer keys and ray counts',
                       'complete track fish set', 'edge endpoints', 'no self edges',
                       'unique edges within/across batches', 'positive rays',
                       'angular-size relation', 'center distance relation',
                       'stream and packed adjacency row counts'],
            'max_network_distance_error_px': max_distance_error,
            'distance_tolerance_px': distance_tolerance,
            'max_angular_relation_error_deg': max_angular_error,
            'angular_tolerance_deg': angular_tolerance,
            'required_null_cells': 0,
            'coverage_policy': 'Whole missing frames are unknown; exclude them from denominators. Include zero-degree fish in covered frames.',
        },
        'source_schema': {field.name: str(field.type) for field in source.schema_arrow},
        'processing': {'batch_size': int(batch_size), 'batches': batches,
                       'packed_adjacency_bytes': int(packed.nbytes),
                       'frame_decode_chunk': 128,
                       'row_order_assumption': 'none'},
    }
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        per_frame.to_csv(output_dir/'per_frame.csv', index=False)
        pd.DataFrame(summary['degree_histogram']).to_csv(output_dir/'degree_histogram.csv', index=False)
        pd.DataFrame({'left_deg': ANGULAR_EDGES[:-1], 'right_deg': ANGULAR_EDGES[1:],
                      'count': angular_counts}).to_csv(output_dir/'angular_size_histogram.csv', index=False)
    return summary
