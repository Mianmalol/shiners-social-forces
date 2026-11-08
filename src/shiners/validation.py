"""Data contract checks for one trial; never repair data silently."""
import numpy as np
import pandas as pd


def validate(tracks, network):
    required = ['frame', 'id', 'segment', 'time', 'X', 'Y', 'ANGLE', 'body_length']
    pose = [f'pose{axis}{i}' for axis in 'XY' for i in range(21)]
    edges = ['frame', 'id1', 'id2', 'n_rays', 'angular_size_deg', 'distance']
    for name, df, cols in [('tracks', tracks, required + pose), ('network', network, edges)]:
        missing = set(cols) - set(df.columns)
        if missing:
            raise ValueError(f'{name}: missing columns {sorted(missing)}')
        if not len(df):
            raise ValueError(f'{name}: empty table')
        if not np.isfinite(df[cols].to_numpy(dtype=float)).all():
            raise ValueError(f'{name}: nonfinite required values')
    if tracks.duplicated(['frame', 'id']).any():
        raise ValueError('Duplicate track keys')
    if network.duplicated(['frame', 'id1', 'id2']).any():
        raise ValueError('Duplicate network keys')
    if (tracks.body_length <= 0).any():
        raise ValueError('Nonpositive body length')
    for c in ['frame', 'id', 'segment']:
        if (tracks[c] != np.floor(tracks[c])).any():
            raise ValueError(f'Noninteger tracks {c}')
    for c in ['frame', 'id1', 'id2', 'n_rays']:
        if (network[c] != np.floor(network[c])).any():
            raise ValueError(f'Noninteger network {c}')
    grouped = tracks.groupby('frame')
    if (grouped[['time', 'segment']].nunique() != 1).any().any():
        raise ValueError('Inconsistent frame time or segment across fish')
    if (grouped.id.nunique() != tracks.id.nunique()).any():
        raise ValueError('Incomplete fish set')
    frames = grouped[['time', 'segment']].first().sort_index()
    if (np.diff(frames.time) <= 0).any():
        raise ValueError('Nonmonotone timestamps')
    if (np.diff(frames.segment) < 0).any():
        raise ValueError('Nonmonotone segment labels')
    keys = pd.MultiIndex.from_frame(tracks[['frame', 'id']])
    for c in ['id1', 'id2']:
        if not pd.MultiIndex.from_frame(network[['frame', c]]).isin(keys).all():
            raise ValueError('Dangling network endpoint')
    if (network.id1 == network.id2).any() or (network.n_rays <= 0).any():
        raise ValueError('Self link or nonpositive rays')
    if not np.allclose(network.angular_size_deg, network.n_rays * .36, rtol=0, atol=1e-9):
        raise ValueError('Angular size inconsistent with ray count')
    xy = tracks.set_index(['frame', 'id'])[['X', 'Y']]
    a = xy.reindex(pd.MultiIndex.from_frame(network[['frame', 'id1']])).to_numpy()
    b = xy.reindex(pd.MultiIndex.from_frame(network[['frame', 'id2']])).to_numpy()
    err = np.abs(np.linalg.norm(a-b, axis=1) - network.distance.to_numpy())
    dtypes = {c: str(tracks[c].dtype) for c in ['X','Y']}
    dtypes['distance'] = str(network.distance.dtype)
    tolerance = 1e-3 if 'float32' in dtypes.values() else 1e-4
    if err.max() > tolerance:
        raise ValueError('Network center distance inconsistent with tracks')
    covered = np.sort(network.frame.unique())
    unknown = frames.index.difference(covered).tolist()
    jumps = np.diff(frames.index.to_numpy())
    return {
        'track_rows': len(tracks), 'network_rows': len(network),
        'fish': int(tracks.id.nunique()), 'frames': len(frames),
        'frame_range': [int(frames.index.min()), int(frames.index.max())],
        'segments': tracks.groupby('segment').frame.agg(['min','max','nunique']).reset_index().to_dict('records'),
        'missing_frames_inside_range': int(np.maximum(jumps-1, 0).sum()),
        'network_uncovered_frames': unknown,
        'network_coverage_policy': 'Whole missing frames unknown; zero-degree fish included in covered frames.',
        'max_network_distance_error_px': float(err.max()),
        'distance_tolerance_px': tolerance, 'distance_source_dtypes': dtypes,
        'null_cells_tracks': int(tracks.isna().sum().sum()),
        'null_cells_network': int(network.isna().sum().sum()),
        'passed': ['required schema/finite values', 'unique keys', 'complete fish set',
                   'consistent frame times/segments', 'monotone times/segments',
                   'edge endpoints', 'no self edges', 'positive lengths/rays',
                   'angular-size relation', 'network center distances'],
    }
