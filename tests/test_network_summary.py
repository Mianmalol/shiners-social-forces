import json

import numpy as np
import pandas as pd
import pytest

from shiners.metrics import visibility
from shiners.network_summary import summarize_network


def tracks_fixture():
    return pd.DataFrame([
        {'frame': frame, 'id': fish, 'X': float(index*3), 'Y': float(index*4 + frame)}
        for frame in [2, 4, 8] for index, fish in enumerate([10, 20, 40])
    ])


def edges_fixture(tracks):
    # Deliberately interleave frame order and produce repeated byte indices.
    keys = [(4, 20, 40), (2, 10, 20), (4, 40, 20), (2, 20, 10), (4, 10, 20)]
    xy = tracks.set_index(['frame', 'id'])[['X', 'Y']]
    return pd.DataFrame([
        {'frame': f, 'id1': a, 'id2': b, 'n_rays': i+1,
         'angular_size_deg': .36*(i+1),
         'distance': float(np.linalg.norm(xy.loc[(f,a)]-xy.loc[(f,b)]))}
        for i, (f, a, b) in enumerate(keys)
    ])


def save(tmp_path, df):
    path = tmp_path/'network.parquet'
    df.to_parquet(path, index=False)
    return path


@pytest.mark.parametrize('batch_size', [1, 2, 3, 100])
def test_exact_unsorted_summary_matches_small_reference(tmp_path, batch_size):
    tracks = tracks_fixture().sample(frac=1, random_state=7)
    network = edges_fixture(tracks)
    result = summarize_network(save(tmp_path, network), tracks, tmp_path/'out', batch_size)
    reference = visibility(tracks, network)
    assert result['network_rows'] == 5
    assert result['covered_frame_count'] == 2
    assert result['network_uncovered_frames'] == [8]
    assert result['observer_frame_count'] == 6
    assert result['visible_degree_mean'] == pytest.approx(reference['degree'].degree.mean())
    assert result['visible_fraction_mean'] == pytest.approx(5/12)
    assert result['reciprocal_edge_fraction'] == pytest.approx(reference['reciprocal_edge_fraction'])
    assert result['reciprocal_edge_fraction'] == .8
    assert result['degree_histogram'] == {'degree': [0,1,2], 'count': [1,5,0]}
    assert sum(result['angular_size_histogram']['count']) == len(network)
    assert result['processing']['packed_adjacency_bytes'] == 6  # 3 frames x ceil(9/8)
    assert result['quality']['max_network_distance_error_px'] == 0
    matched = result['matched_duration']
    assert matched['tracked_frame_count'] == 3
    assert matched['frame_start'] == 2
    assert matched['frame_end'] == 8
    assert matched['coverage_fraction'] == pytest.approx(2/3)
    for key in ['network_rows', 'covered_frame_count', 'network_uncovered_frames',
                'observer_frame_count', 'visible_degree_mean', 'visible_fraction_mean',
                'reciprocal_edge_fraction']:
        assert matched[key] == result[key]
    frame = pd.read_csv(tmp_path/'out/per_frame.csv')
    assert frame.frame.tolist() == [2,4,8]
    assert frame.mean_degree.iloc[:2].tolist() == pytest.approx([2/3, 1])
    assert frame.reciprocal_edge_fraction.iloc[:2].tolist() == pytest.approx([1, 2/3])
    assert np.isnan(frame.mean_degree.iloc[2])
    assert np.isnan(frame.reciprocal_edge_fraction.iloc[2])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('batch_size', [1, 100])
def test_duplicate_edges_rejected_across_or_inside_batches(tmp_path, batch_size):
    tracks = tracks_fixture()
    network = edges_fixture(tracks)
    network = pd.concat([network, network.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match='Duplicate visibility edges'):
        summarize_network(save(tmp_path, network), tracks, batch_size=batch_size)


@pytest.mark.parametrize('column,value,error', [
    ('frame', 100, 'Dangling'), ('id1', 999, 'Dangling'), ('id2', 30, 'Dangling'),
    ('id2', 20, 'Self'), ('frame', 2.5, 'noninteger'), ('id1', np.inf, 'nonfinite'),
    ('n_rays', 0, 'Nonpositive'), ('n_rays', 1.5, 'noninteger'),
    ('angular_size_deg', 5., 'Angular size'), ('distance', 7., 'distance'),
    ('distance', -1., 'distance'), ('distance', np.inf, 'nonfinite'),
])
def test_invalid_network_rejected(tmp_path, column, value, error):
    tracks = tracks_fixture()
    network = edges_fixture(tracks)
    network[column] = network[column].astype(float)
    network.loc[0, column] = value
    with pytest.raises(ValueError, match=error):
        summarize_network(save(tmp_path, network), tracks, batch_size=2)


def test_null_and_missing_column_rejected(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks)
    network.loc[0, 'distance'] = np.nan
    with pytest.raises(ValueError, match='null'):
        summarize_network(save(tmp_path, network), tracks)
    with pytest.raises(ValueError, match='missing columns'):
        summarize_network(save(tmp_path, network.drop(columns='distance')), tracks)


def test_empty_network_is_unknown_coverage_not_all_invisible(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks).iloc[:0]
    result = summarize_network(save(tmp_path, network), tracks)
    assert result['network_rows'] == 0
    assert result['covered_frame_count'] == 0
    assert result['network_uncovered_frames'] == [2,4,8]
    assert result['visible_degree_mean'] is None
    assert result['reciprocal_edge_fraction'] is None
    assert result['degree_histogram']['count'] == [0,0,0]
    assert result['matched_duration']['coverage_fraction'] == 0
    assert result['matched_duration']['visible_degree_mean'] is None
    assert result['matched_duration']['reciprocal_edge_fraction'] is None
    json.dumps(result, allow_nan=False)


def test_matched_duration_uses_observed_frame_order_and_pooled_edges(tmp_path):
    # Gapped IDs, shuffled input, and unknown coverage do not change the cutoff.
    frames = 10 + 3*np.arange(18001)
    tracks = pd.DataFrame({'frame': np.repeat(frames, 2),
                           'id': np.tile([10, 20], len(frames)),
                           'X': np.tile([0., 5.], len(frames)), 'Y': 0.})
    tracks = tracks.sample(frac=1, random_state=7)
    network = pd.DataFrame({
        'frame': [frames[17999], frames[0], frames[17998], frames[0], frames[17999]],
        'id1': [10, 10, 10, 20, 20], 'id2': [20, 20, 20, 10, 10],
        'n_rays': 1, 'angular_size_deg': .36, 'distance': 5.,
    })
    result = summarize_network(save(tmp_path, network), tracks, batch_size=2)
    matched = result['matched_duration']
    assert matched['tracked_frame_count'] == 17999
    assert matched['target_frame_count'] == 17999
    assert matched['frame_end'] == int(frames[17998])
    assert matched['covered_frame_count'] == 2
    assert matched['coverage_fraction'] == pytest.approx(2/17999)
    assert matched['network_uncovered_frames'] == frames[1:17998].tolist()
    assert matched['network_rows'] == 3
    assert matched['observer_frame_count'] == 4
    assert matched['visible_degree_mean'] == .75
    assert matched['visible_fraction_mean'] == .75
    assert matched['reciprocal_edge_fraction'] == pytest.approx(2/3)
    assert result['network_rows'] == 5
    assert result['reciprocal_edge_fraction'] == .8
    json.dumps(result, allow_nan=False)


def test_float32_geometry_and_angular_tolerances(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks)
    tracks['X'] = tracks.X.astype('float32')
    network['distance'] = (network.distance + .0005).astype('float32')
    network['angular_size_deg'] = network.angular_size_deg.astype('float32')
    result = summarize_network(save(tmp_path, network), tracks)
    assert result['quality']['distance_tolerance_px'] == .001
    assert result['quality']['angular_tolerance_deg'] == .0001


def test_high_angular_values_record_histogram_overflow(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks)
    # Preserve the exact documented ray formula while ensuring no dropped counts.
    network.loc[0, ['n_rays','angular_size_deg']] = [2001, .36*2001]
    result = summarize_network(save(tmp_path, network), tracks)
    hist = result['angular_size_histogram']
    assert hist['overflow'] == 1
    assert sum(hist['count']) + hist['overflow'] + hist['underflow'] == len(network)


def test_track_contract_and_arguments(tmp_path):
    tracks = tracks_fixture(); path = save(tmp_path, edges_fixture(tracks))
    with pytest.raises(ValueError, match='Duplicate track'):
        summarize_network(path, pd.concat([tracks,tracks.iloc[[0]]]))
    with pytest.raises(ValueError, match='Incomplete fish set'):
        summarize_network(path, tracks.iloc[1:])
    with pytest.raises(ValueError, match='nonfinite'):
        summarize_network(path, tracks.assign(X=np.nan))
    with pytest.raises(ValueError, match='one trial'):
        summarize_network(path, tracks.assign(sequence=['a']*8+['b']))
    with pytest.raises(ValueError, match='batch_size'):
        summarize_network(path, tracks, batch_size=0)


def test_nonpositive_length_frame_sensitivity_preserves_primary_and_zero_degrees(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks)
    path = save(tmp_path, network)
    original = summarize_network(path, tracks, batch_size=2)
    result = summarize_network(path, tracks, tmp_path/'out', batch_size=2, excluded_frames=[8, 4, 4])
    key = 'nonpositive_length_frame_exclusion_sensitivity'
    assert {k: v for k, v in result.items() if k != key} == {k: v for k, v in original.items() if k != key}
    sensitivity = result[key]
    assert sensitivity['frame_ids_provided']
    assert sensitivity['excluded_tracked_frames'] == [4, 8]
    assert sensitivity['excluded_tracked_frame_count'] == 2
    assert sensitivity['excluded_covered_frames'] == [4]
    assert sensitivity['excluded_covered_frame_count'] == 1
    assert sensitivity['excluded_network_rows'] == 3
    assert sensitivity['tracked_frame_count'] == sensitivity['covered_frame_count'] == 1
    assert sensitivity['coverage_fraction'] == 1.
    assert sensitivity['network_uncovered_frames'] == []
    assert sensitivity['observer_frame_count'] == 3
    assert sensitivity['network_rows'] == 2
    assert sensitivity['visible_degree_mean'] == pytest.approx(2/3)
    assert sensitivity['visible_fraction_mean'] == pytest.approx(1/3)
    assert sensitivity['reciprocal_edge_fraction'] == 1.
    assert sensitivity['degree_histogram'] == {'degree': [0, 1, 2], 'count': [1, 2, 0]}
    per_frame = pd.read_csv(tmp_path/'out/per_frame.csv')
    assert per_frame.excluded_nonpositive_length_sensitivity.tolist() == [False, True, True]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('excluded_frames', [None, [], [2, 4, 8]])
def test_exclusion_sensitivity_empty_and_all_frame_cases(tmp_path, excluded_frames):
    tracks = tracks_fixture(); path = save(tmp_path, edges_fixture(tracks))
    result = summarize_network(path, tracks, excluded_frames=excluded_frames)
    sensitivity = result['nonpositive_length_frame_exclusion_sensitivity']
    if excluded_frames:
        assert sensitivity['tracked_frame_count'] == 0
        assert sensitivity['network_rows'] == 0
        assert sensitivity['coverage_fraction'] is None
        assert sensitivity['visible_degree_mean'] is None
        assert sensitivity['visible_fraction_mean'] is None
        assert sensitivity['reciprocal_edge_fraction'] is None
        assert sensitivity['degree_histogram']['count'] == [0, 0, 0]
    else:
        assert sensitivity['excluded_tracked_frames'] == []
        for key in ['visible_degree_mean', 'visible_fraction_mean', 'reciprocal_edge_fraction',
                    'degree_histogram', 'network_uncovered_frames']:
            assert sensitivity[key] == result[key]
    json.dumps(result, allow_nan=False)


def test_excluded_frames_still_undergo_raw_qc_and_require_valid_track_ids(tmp_path):
    tracks = tracks_fixture(); network = edges_fixture(tracks)
    path = save(tmp_path, network)
    with pytest.raises(ValueError, match='excluded frame'):
        summarize_network(path, tracks, excluded_frames=[999])
    with pytest.raises(ValueError, match='noninteger'):
        summarize_network(path, tracks, excluded_frames=[2.5])
    network.loc[0, 'distance'] = -1.
    with pytest.raises(ValueError, match='distance'):
        summarize_network(save(tmp_path, network), tracks, excluded_frames=[4])
