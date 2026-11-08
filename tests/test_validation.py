"""Small independent data-contract examples; no real trial files required."""
import numpy as np
import pandas as pd
import pytest

from shiners.validation import validate


def tiny_trial():
    """Three tracked fish; only 0 sees 1, so fish 1 and 2 have zero out-degree."""
    rows = []
    for frame in (1, 2, 3):
        for fish, (x, y) in enumerate(((0., 0.), (3., 4.), (8., 0.))):
            row = dict(frame=frame, id=fish, segment=0, time=frame/29.97,
                       X=x, Y=y, ANGLE=0., body_length=2.)
            row.update({f'poseX{i}':x+1-i/10 for i in range(21)})
            row.update({f'poseY{i}':y for i in range(21)})
            rows.append(row)
    tracks = pd.DataFrame(rows)
    network = pd.DataFrame([dict(frame=f, id1=0, id2=1, n_rays=10,
                                angular_size_deg=3.6, distance=5.) for f in (1,2,3)])
    return tracks, network


def test_valid_trial_and_zero_degree_fish():
    tracks, network = tiny_trial()
    result = validate(tracks, network)
    assert result['fish'] == 3
    assert result['frames'] == 3
    assert result['track_rows'] == 9
    assert result['network_rows'] == 3
    assert result['network_uncovered_frames'] == []
    assert result['max_network_distance_error_px'] == 0.
    assert result['null_cells_tracks'] == result['null_cells_network'] == 0


def test_whole_missing_network_frame_is_unknown_not_zero_visibility():
    tracks, network = tiny_trial()
    result = validate(tracks, network.loc[network.frame != 2])
    assert result['network_uncovered_frames'] == [2]
    assert 'unknown' in result['network_coverage_policy']
    assert result['frames'] == 3


@pytest.mark.parametrize('which,key,message', [
    ('tracks','X','missing columns'), ('tracks','poseY20','missing columns'),
    ('network','distance','missing columns'),
])
def test_missing_required_columns(which,key,message):
    tracks, network = tiny_trial()
    if which == 'tracks': tracks = tracks.drop(columns=key)
    else: network = network.drop(columns=key)
    with pytest.raises(ValueError, match=message): validate(tracks,network)


@pytest.mark.parametrize('which,column,value', [
    ('tracks','X',np.nan), ('tracks','poseX10',np.inf),
    ('network','distance',np.nan), ('network','angular_size_deg',-np.inf),
])
def test_nonfinite_required_values(which,column,value):
    tracks, network = tiny_trial()
    table = tracks if which == 'tracks' else network
    table.loc[0,column] = value
    with pytest.raises(ValueError, match='nonfinite required values'): validate(tracks,network)


@pytest.mark.parametrize('which', ['tracks','network'])
def test_duplicate_keys(which):
    tracks, network = tiny_trial()
    if which == 'tracks': tracks = pd.concat([tracks,tracks.iloc[[0]]],ignore_index=True)
    else: network = pd.concat([network,network.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError, match='Duplicate'): validate(tracks,network)


@pytest.mark.parametrize('column,value', [('time',2.),('segment',1)])
def test_inconsistent_frame_metadata(column,value):
    tracks, network = tiny_trial()
    tracks.loc[0,column] = value
    with pytest.raises(ValueError, match='Inconsistent frame'): validate(tracks,network)


def test_missing_fish_record():
    tracks, network = tiny_trial()
    tracks = tracks.loc[~((tracks.frame == 2) & (tracks.id == 2))]
    with pytest.raises(ValueError, match='Incomplete fish set'): validate(tracks,network)


@pytest.mark.parametrize('endpoint', ['id1','id2'])
def test_dangling_endpoint(endpoint):
    tracks, network = tiny_trial()
    network.loc[0,endpoint] = 8
    with pytest.raises(ValueError, match='Dangling network endpoint'): validate(tracks,network)


@pytest.mark.parametrize('column,value,message', [
    ('distance',6.,'center distance'), ('angular_size_deg',4.,'Angular size'),
    ('n_rays',0,'nonpositive rays'), ('id2',0,'Self link'),
])
def test_invalid_edge_measurements(column,value,message):
    tracks, network = tiny_trial()
    network.loc[0,column] = value
    with pytest.raises(ValueError, match=message): validate(tracks,network)


def test_nonmonotone_time():
    tracks, network = tiny_trial()
    tracks.loc[tracks.frame == 2,'time'] = 0.
    with pytest.raises(ValueError, match='Nonmonotone timestamps'): validate(tracks,network)


def test_nonpositive_length():
    tracks, network = tiny_trial()
    tracks.loc[0,'body_length'] = 0.
    with pytest.raises(ValueError, match='Nonpositive body length'): validate(tracks,network)


def test_fractional_identifier():
    tracks, network = tiny_trial()
    network['id1'] = network.id1.astype(float)
    network.loc[0,'id1'] = .5
    with pytest.raises(ValueError, match='Noninteger network id1'): validate(tracks,network)


def test_missing_frame_is_reported_and_segments_not_forced_to_seven():
    tracks, network = tiny_trial()
    tracks = tracks.loc[tracks.frame != 2].copy()
    network = network.loc[network.frame != 2].copy()
    tracks.loc[tracks.frame == 3,'segment'] = 1
    result = validate(tracks,network)
    assert result['missing_frames_inside_range'] == 1
    assert len(result['segments']) == 2
