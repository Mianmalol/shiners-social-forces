"""Comparison checks use analytic examples, not expected real-trial rankings."""
import json

import numpy as np
import pandas as pd
import pytest

from shiners.compare_trial import (
    POSE_INDICES, collective_summary, common_cohort_summaries, file_hash,
    heading_selection, run, threshold_frame_selection, validate_tracks,
)
from shiners.metrics import collective, kinematics


def circular_tracks(fish=4, frames=61):
    t=np.repeat(np.arange(frames)*.1,fish)
    ids=np.tile(np.arange(fish),frames)
    phase=t+ids*2*np.pi/fish
    tr=pd.DataFrame({'frame':np.repeat(np.arange(frames),fish),'id':ids,
                     'time':t,'segment':0,'group':f'{fish}-fish','sequence':'synthetic',
                     'X':2*np.cos(phase),'Y':2*np.sin(phase),
                     'ANGLE':phase+np.pi/2,'body_length':1.})
    for i in POSE_INDICES:
        offset=(10-i)/20
        tr[f'poseX{i}']=tr.X+offset*np.cos(tr.ANGLE)
        tr[f'poseY{i}']=tr.Y+offset*np.sin(tr.ANGLE)
    return tr


def test_quality_accepts_other_fish_counts_and_explicit_gaps():
    tr=circular_tracks(fish=7)
    tr=tr[tr.frame!=30].copy()
    tr.loc[tr.frame>=45,'segment']=1
    qc=validate_tracks(tr)
    assert qc['fish']==7
    assert qc['segment_count']==2
    assert qc['missing_frames_inside_range']==1
    assert [(b['first_frame'],b['last_frame']) for b in qc['continuous_blocks']]==[(0,29),(31,44),(45,60)]


@pytest.mark.parametrize('fault,message',[
    ('duplicate','Duplicate'),('missing','Incomplete'),('nonfinite','Nonfinite'),
    ('length','No positive'),('time','Irregular'),('frame_time','Inconsistent'),
])
def test_quality_rejects_invalid_measurement_inputs(fault,message):
    tr=circular_tracks()
    if fault=='duplicate':tr=pd.concat([tr,tr.iloc[[0]]],ignore_index=True)
    if fault=='missing':tr=tr.iloc[1:]
    if fault=='nonfinite':tr.loc[0,'poseX6']=np.nan
    if fault=='length':tr['body_length']=0
    if fault=='time':tr.loc[tr.frame==25,'time']+=.01
    if fault=='frame_time':tr.loc[0,'time']+=.01
    with pytest.raises(ValueError,match=message):validate_tracks(tr)


def test_quality_discloses_isolated_nonpositive_lengths_without_mutating_data():
    tr=circular_tracks()
    tr.loc[0,'body_length']=0
    tr.loc[8,'body_length']=-1
    qc=validate_tracks(tr)
    assert qc['nonpositive_length_rows']==2
    assert qc['nonpositive_length_frames']==[0,2]
    assert [r['id'] for r in qc['nonpositive_length_observations']]==[0,0]
    assert tr.loc[0,'body_length']==0
    assert tr.loc[8,'body_length']==-1


def test_common_cohort_distinguishes_sampling_from_values():
    a=pd.DataFrame({'frame':[2,4,6],'polarization':[.3,.6,.9],
                    'circulation':[.1,.6,.8],'signed_circulation':[-.1,.6,.8],
                    'eligible_fraction':[1.,1.,1.],'iid_direction_reference':[.1]*3})
    b=a.copy();b.loc[0,'circulation']=np.nan;b.loc[2,'polarization']=np.nan
    assert collective_summary(a)['circulation_median']==.6
    assert collective_summary(b)['circulation_median']==.7
    joint=common_cohort_summaries([a,b],[.25,1.],'threshold_bl_s')
    assert joint['common_frames']==1
    assert joint['common_fraction']==1/3
    assert [s['circulation']['0.5'] for s in joint['settings']]==[.6,.6]
    c_only=common_cohort_summaries([a,b],[.25,1.],'threshold_bl_s',False)
    assert c_only['common_frames']==2
    fixed=threshold_frame_selection(b,[a,b],[.25,1.],1.)
    assert fixed['settings'][0]['candidate_frames']==3
    assert fixed['settings'][0]['baseline_undefined_frames']==1
    assert fixed['settings'][0]['baseline_circulation']['0.5']==.7
    with pytest.raises(ValueError,match='frame ordering'):
        common_cohort_summaries([a,b.iloc[::-1]],[.25,1.],'threshold_bl_s')


def test_leave_one_out_equivalence_and_invariant_rotation():
    tr=circular_tracks(fish=4,frames=1)
    tr['vx']=-.4*np.sin(tr.ANGLE-np.pi/2)
    tr['vy']=.4*np.cos(tr.ANGLE-np.pi/2)
    v=tr[['vx','vy']].to_numpy()
    relative=v-v.mean(axis=0)
    other_mean=(v.sum(axis=0)-v)/(len(v)-1)
    np.testing.assert_allclose(relative,(len(v)-1)/len(v)*(v-other_mean),atol=1e-15)
    assert np.isnan(collective(tr,1,.5).circulation.iloc[0])
    adjusted=collective(tr,1,.5*(len(v)-1)/len(v))
    assert adjusted.circulation.iloc[0]==pytest.approx(1)
    assert adjusted.eligible_fraction.iloc[0]==1
    # Doubling the reference length and halving the threshold preserves C.
    scaled=collective(tr,2,.25*(len(v)-1)/len(v))
    assert scaled.circulation.iloc[0]==pytest.approx(adjusted.circulation.iloc[0])


def test_heading_selection_retains_raw_measurements_and_exposes_coverage():
    tr=circular_tracks()
    tr.loc[(tr.id==0)&(tr.frame>=30),'ANGLE']+=np.pi
    k=kinematics(tr)
    c=collective(k,1)
    frames,report=heading_selection(k,c)
    raw=frames.polarization_raw.to_numpy()
    valid=np.isfinite(c.polarization)
    assert np.isfinite(raw).all()
    np.testing.assert_allclose(raw[valid],c.loc[valid,'polarization'],atol=1e-15)
    assert report['polarization_valid_frames']==49
    assert report['heading_masked_rows']==12
    assert report['heading_jump_rows']==2
    assert report['raw_polarization_on_excluded_frames']['n']==12
    # With 4 fish, 3 valid heads fall below the >=80% rule.
    assert report['affected_fish_only']['valid_frames']==49
    assert frames.loc[valid,'polarization_iid_reference'].iloc[0]==pytest.approx(np.sqrt(np.pi/16))
    json.dumps(report,allow_nan=False)


def test_affected_fish_only_p_retains_frames_when_eighty_percent_valid():
    tr=circular_tracks(fish=5)
    tr.loc[(tr.id==0)&(tr.frame>=30),'ANGLE']+=np.pi
    k=kinematics(tr);c=collective(k,1)
    frames,report=heading_selection(k,c)
    assert report['affected_fish_only']['valid_frames']==61
    assert report['affected_fish_only']['common_frames']==49
    assert frames.heading_valid_fish_count.min()==4
    assert frames.polarization_valid_fish.notna().all()
    assert frames.loc[frames.heading_valid_fish_count==4,'polarization_valid_fish_iid_reference'].iloc[0]==pytest.approx(np.sqrt(np.pi/16))
    np.testing.assert_allclose(frames.loc[c.polarization.notna(),'polarization_valid_fish'],c.polarization.dropna(),atol=1e-15)


def test_track_only_trial_completes_and_preserves_all_frames(tmp_path):
    data=tmp_path/'data';data.mkdir()
    circular_tracks().to_parquet(data/'tracks.parquet',index=False)
    (data/'provenance.json').write_text(json.dumps({'files':{'tracks.parquet':{
        'sha256':file_hash(data/'tracks.parquet')}}}))
    cfg={'smoothing_windows':[7,11,15],'primary_window':11,'polynomial_order':3,
         'low_speed_bl_s':.5,'curvature_neighborhoods':[5,7,9],
         'primary_curvature_neighborhood':7,'circulation_min_fraction':.8,
         'spatial_extent_bl':10,'spatial_bins':20,'low_speed_sensitivity_bl_s':[.25,.5,1.]}
    config=tmp_path/'config.json';config.write_text(json.dumps(cfg))
    out=tmp_path/'out'
    result=run(data,out,config,no_network=True)
    c=pd.read_csv(out/'collective.csv')
    assert len(c)==61
    assert c.circulation.notna().sum()==49
    assert result['polarization']['0.5']==pytest.approx(0,abs=1e-14)
    assert result['circulation']['0.5']==pytest.approx(1,abs=1e-10)
    assert result['network']=={'status':'not_requested'}
    assert result['scale_sensitivity_151'] is None
    assert result['threshold_common_eligible']['common_frames']==49
    assert result['window_common_eligible']['common_frames']==45
    assert result['spatial_map']['shown_pair_fraction']==1
    assert result['histograms']['speed']['finite_n']==49*4
    assert result['matched_duration_sensitivity']['frame_count']==61
    clean=result['nonpositive_length_frame_exclusion_sensitivity']
    assert clean['excluded_frame_count']==0
    assert clean['speed_bl_s']==result['speed_bl_s']
    assert clean['circulation']==result['circulation']
    assert result['curvature_times_L']['0.5']==pytest.approx(0,abs=1e-10)
    provenance=json.loads((out/'provenance.json').read_text())
    assert provenance['fetch_member_hashes_match'] is True
    assert provenance['output_hashes']['summary.json']==file_hash(out/'summary.json')
    assert 'src/shiners/metrics.py' in provenance['source_hashes']
    with pytest.raises(ValueError,match='new or empty'):run(data,out,config,no_network=True)


def test_151_scale_and_matched_endpoint_sensitivities(tmp_path):
    data=tmp_path/'data';data.mkdir()
    circular_tracks(fish=151,frames=41).to_parquet(data/'tracks.parquet',index=False)
    (data/'provenance.json').write_text(json.dumps({'files':{'tracks.parquet':{
        'sha256':file_hash(data/'tracks.parquet')}}}))
    cfg={'smoothing_windows':[7,11,15],'primary_window':11,'polynomial_order':3,
         'low_speed_bl_s':.5,'curvature_neighborhoods':[5,7,9],
         'primary_curvature_neighborhood':7,'circulation_min_fraction':.8,
         'spatial_extent_bl':10,'spatial_bins':20,'low_speed_sensitivity_bl_s':[.25,.5,1.],
         'matched_frame_count':31}
    config=tmp_path/'config.json';config.write_text(json.dumps(cfg))
    out=tmp_path/'out';result=run(data,out,config,no_network=True)
    scaled=result['scale_sensitivity_151']
    for key in ['speed_bl_s','acceleration_bl_s2','spread_bl','centroid_speed_bl_s','nearest_neighbor_bl']:
        assert scaled[key]['0.5']==pytest.approx(result[key]['0.5']/1.15,abs=1e-12)
    assert len(scaled['threshold_sensitivity'])==3
    assert scaled['heading_diagnostics']['low_speed_bl_s']==.5
    assert scaled['spatial_map']['density_multiplier']==pytest.approx(1.15**2)
    original=pd.read_csv(out/'tables/spatial-map.csv')
    transformed=pd.read_csv(out/'tables/spatial-map-Lx1p15.csv')
    np.testing.assert_allclose(transformed.density_per_focal_per_bl2,original.density_per_focal_per_bl2*1.15**2)
    matched=result['matched_duration_sensitivity']
    assert matched['frame_count']==31
    assert matched['circulation']['n']==19
    # Recomputing at the cutoff trims its six final samples; selecting old outputs would leave 25.
    assert matched['speed_bl_s']['n']==19*151
    assert matched['nearest_neighbor_bl']['n']==31*151


def test_nonpositive_length_masks_curvature_and_breaks_sensitivity_smoothing(tmp_path):
    data=tmp_path/'data';data.mkdir()
    tr=circular_tracks()
    tr.loc[(tr.frame==30)&(tr.id==0),'body_length']=0
    # Even a noncollapsed finite pose must not yield curvature when length metadata is invalid.
    tr.to_parquet(data/'tracks.parquet',index=False)
    (data/'provenance.json').write_text(json.dumps({'files':{'tracks.parquet':{
        'sha256':file_hash(data/'tracks.parquet')}}}))
    cfg={'smoothing_windows':[7,11,15],'primary_window':11,'polynomial_order':3,
         'low_speed_bl_s':.5,'curvature_neighborhoods':[5,7,9],
         'primary_curvature_neighborhood':7,'circulation_min_fraction':.8,
         'spatial_extent_bl':10,'spatial_bins':20,'low_speed_sensitivity_bl_s':[.25,.5,1.]}
    config=tmp_path/'config.json';config.write_text(json.dumps(cfg))
    out=tmp_path/'out';result=run(data,out,config,no_network=True)
    assert result['quality']['nonpositive_length_rows']==1
    assert result['quality']['nonpositive_length_frames']==[30]
    assert result['length_scale_px']==1
    assert result['curvature_times_L']['n']==61*4-1
    assert result['polarization']['n']==61
    assert result['circulation']['n']==49
    sensitivity=result['nonpositive_length_frame_exclusion_sensitivity']
    assert sensitivity['excluded_fish_observations']==4
    assert sensitivity['retained_frame_count']==60
    assert sensitivity['polarization']['n']==60
    assert sensitivity['circulation']['n']==36
    assert sensitivity['speed_bl_s']['n']==36*4
    assert sensitivity['nearest_neighbor_bl']['n']==60*4
    assert sensitivity['circulation_valid_frame_fraction_of_source']==36/61
    exported=pd.read_csv(out/'tables/collective-nonpositive-length-exclusion.csv')
    assert len(exported)==61
    assert exported.loc[exported.frame.between(24,36),'circulation'].isna().all()
    assert not exported.loc[exported.frame==30,'geometry_frame_retained'].iloc[0]
    # Raw data are unchanged, including the source invalid observation.
    assert pd.read_parquet(data/'tracks.parquet').body_length.eq(0).sum()==1
