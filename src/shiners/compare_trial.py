"""Run the reviewed descriptive measurements on one trial, with bounded network IO.

One invocation/process per trial. This keeps each trial separate and releases its
memory on exit. A summary.json is written only after every requested stage passes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .metrics import kinematics, curvature, collective, spatial, heading_diagnostics

BASE_COLUMNS = ['frame', 'id', 'segment', 'time', 'X', 'Y', 'ANGLE', 'body_length']
IDENTITY_COLUMNS = ['group', 'sequence']
POSE_INDICES = [0, *range(6, 15), 20]
POSE_COLUMNS = [f'pose{axis}{i}' for axis in 'XY' for i in POSE_INDICES]
CORE_COLUMNS = BASE_COLUMNS + IDENTITY_COLUMNS + ['poseX0','poseY0','poseX20','poseY20']


def quant(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    return {'n': int(len(a)), **{str(q): float(np.quantile(a,q)) if len(a) else None
                               for q in [.05,.5,.95]}}


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def atomic_json(path, value):
    # All values must be finite JSON numbers, or explicit null for undefined metrics.
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def validate_tracks(tracks):
    """Validate the projected fields actually used; do not claim unselected QC."""
    required = BASE_COLUMNS + IDENTITY_COLUMNS + POSE_COLUMNS
    missing = sorted(set(required)-set(tracks.columns))
    if missing: raise ValueError(f'Missing track columns: {missing}')
    if tracks.empty: raise ValueError('Empty tracks')
    for col in BASE_COLUMNS + POSE_COLUMNS:
        if not np.isfinite(tracks[col].to_numpy(dtype=float)).all():
            raise ValueError(f'Nonfinite track values: {col}')
    for col in ['frame','id','segment']:
        a = tracks[col].to_numpy(dtype=float)
        if (a != np.floor(a)).any(): raise ValueError(f'Noninteger track {col}')
    positive_length=tracks.body_length>0
    if not positive_length.any():raise ValueError('No positive body lengths for reference scale')
    bad_geometry=tracks.loc[~positive_length,['frame','id','segment','time','body_length']]
    bad_geometry_frames=sorted(int(f) for f in bad_geometry.frame.unique())
    for col in IDENTITY_COLUMNS:
        if tracks[col].isna().any() or tracks[col].nunique() != 1:
            raise ValueError(f'Expected one nonnull {col}')
    if tracks.duplicated(['frame','id']).any(): raise ValueError('Duplicate track keys')
    grouped = tracks.groupby('frame',sort=True)
    count = grouped.id.nunique()
    fish = int(tracks.id.nunique())
    if fish<2:raise ValueError('Social comparison requires at least two fish')
    if (count != fish).any(): raise ValueError('Incomplete fish set')
    if (grouped[['time','segment']].nunique() != 1).any().any():
        raise ValueError('Inconsistent time or segment inside a frame')
    frames = grouped[['time','segment']].first()
    if (np.diff(frames.time) <= 0).any(): raise ValueError('Nonmonotone frame times')
    if (np.diff(frames.segment) < 0).any(): raise ValueError('Nonmonotone segments')
    breaks = (frames.index.to_series().diff().fillna(1) != 1) | (frames.segment.diff().fillna(0) != 0)
    blocks = []
    for _, g in frames.groupby(breaks.cumsum()):
        delta = np.diff(g.time.to_numpy())
        if len(delta) and not np.allclose(delta,np.median(delta),rtol=1e-6,atol=1e-10):
            raise ValueError('Irregular timestamps inside continuous block')
        blocks.append({'segment':int(g.segment.iloc[0]),'first_frame':int(g.index.min()),
                       'last_frame':int(g.index.max()),'frames':int(len(g))})
    frame_steps = np.diff(frames.index.to_numpy())
    return {
        'track_rows':int(len(tracks)), 'fish':fish, 'frames':int(len(frames)),
        'frame_range':[int(frames.index.min()),int(frames.index.max())],
        'time_range_s':[float(frames.time.min()),float(frames.time.max())],
        'duration_s':float(frames.time.max()-frames.time.min()),
        'fps_from_track_timestamps':float(np.median(np.diff(frames.index)/np.diff(frames.time))) if len(frames)>1 else None,
        'segment_count':int(tracks.segment.nunique()), 'continuous_blocks':blocks,
        'missing_frames_inside_range':int(np.maximum(frame_steps-1,0).sum()),
        'nonpositive_length_rows':int(len(bad_geometry)),
        'nonpositive_length_frame_count':len(bad_geometry_frames),
        'nonpositive_length_frames':bad_geometry_frames,
        'nonpositive_length_observations':bad_geometry.to_dict('records'),
        'nonpositive_length_policy':'Reference length uses positive values only; curvature is explicitly undefined for nonpositive-length rows. Finite measured positions/headings remain in primary metrics. A separate full-frame exclusion sensitivity recomputes kinematics with gap guards.',
        'checked_columns':required,
        'qc_scope':'Projected measurement inputs only; unselected pose/eye columns are not audited.',
        'passed':['finite required numeric fields','unique track keys','complete fish set',
                  'positive reference length available; nonpositive values disclosed','single trial','consistent per-frame time/segment',
                  'monotone times/segments','regular within-block timestamps'],
    }


def collective_summary(c):
    eligible = np.isfinite(c.circulation.to_numpy())
    joint = eligible & np.isfinite(c.polarization.to_numpy())
    return {
        'tracked_frames':int(len(c)), 'circulation_valid_frames':int(eligible.sum()),
        'circulation_eligible_frame_fraction':float(eligible.mean()),
        'joint_valid_frames':int(joint.sum()), 'joint_eligible_frame_fraction':float(joint.mean()),
        'circulation':quant(c.circulation), 'circulation_median':quant(c.circulation)['0.5'],
        'signed_circulation':quant(c.signed_circulation),
        'polarization':quant(c.polarization),
        'polarization_valid_frames':int(np.isfinite(c.polarization).sum()),
        'polarization_eligible_frame_fraction':float(np.isfinite(c.polarization).mean()),
        'polarization_when_circulation_eligible':quant(c.loc[eligible,'polarization']),
        'polarization_when_circulation_ineligible_or_unknown':quant(c.loc[~eligible,'polarization']),
        'eligible_fish_fraction':quant(c.eligible_fraction),
        'iid_direction_reference':quant(c.iid_direction_reference),
    }


def heading_selection(k, c, min_fraction=.8):
    """Expose whole-frame versus affected-fish-only heading-mask selection."""
    n=int(k.id.nunique())
    units=pd.DataFrame({'frame':k.frame.to_numpy(), 'x':np.cos(k.ANGLE),
                        'y':np.sin(k.ANGLE), 'valid':k.heading_valid.astype(int)})
    units['valid_x']=units.x*units.valid;units['valid_y']=units.y*units.valid
    grouped=units.groupby('frame',sort=True)
    means=grouped[['x','y']].mean().reindex(c.frame)
    sums=grouped[['valid_x','valid_y','valid']].sum().reindex(c.frame)
    raw=np.hypot(means.x,means.y).to_numpy()
    n_valid=sums.valid.to_numpy(dtype=int)
    subset_valid=n_valid/n>=min_fraction
    subset=np.full(len(c),np.nan)
    subset[subset_valid]=np.hypot(sums.valid_x,sums.valid_y).to_numpy()[subset_valid]/n_valid[subset_valid]
    valid=np.isfinite(c.polarization.to_numpy())
    raw_median=quant(raw)['0.5'];masked_median=quant(c.polarization)['0.5']
    reference=np.full(len(c),np.nan);reference[valid]=np.sqrt(np.pi/(4*n))
    subset_reference=np.full(len(c),np.nan)
    subset_reference[subset_valid]=np.sqrt(np.pi/(4*n_valid[subset_valid]))
    frame_output=pd.DataFrame({'polarization_raw':raw,'polarization_valid_fish':subset,
        'heading_valid_fish_count':n_valid,'polarization_iid_reference':reference,
        'polarization_valid_fish_iid_reference':subset_reference})
    result={
        'raw_polarization':quant(raw), 'masked_polarization':quant(c.polarization),
        'raw_polarization_on_masked_frames':quant(raw[valid]),
        'raw_polarization_on_excluded_frames':quant(raw[~valid]),
        'raw_minus_masked_median':raw_median-masked_median if masked_median is not None else None,
        'polarization_valid_frames':int(valid.sum()),
        'polarization_eligible_frame_fraction':float(valid.mean()),
        'heading_jump_rows':int(k.heading_jump.sum()),
        'heading_jump_row_fraction':float(k.heading_jump.mean()),
        'heading_masked_rows':int((~k.heading_valid).sum()),
        'heading_masked_row_fraction':float((~k.heading_valid).mean()),
        'exclusion_reasons':{'any_fish_heading_jump_support':int((~valid).sum()),
                             'nonfinite_heading_input':0,'incomplete_fish_set':0},
        'affected_fish_only':{
            'minimum_heading_valid_fraction':float(min_fraction),
            'valid_fish_per_frame':quant(n_valid),
            'polarization':quant(subset),
            'valid_frames':int(subset_valid.sum()),'valid_frame_fraction':float(subset_valid.mean()),
            'polarization_on_primary_valid_frames':quant(subset[valid]),
            'primary_polarization_on_common_frames':quant(c.loc[valid,'polarization']),
            'common_frames':int(valid.sum()),
            'iid_reference':quant(subset_reference),
        },
        'polarization_iid_reference':quant(reference),
        'iid_reference_note':'sqrt(pi/(4*n)) approximates mean P for independent uniform headings. Illustrative only, not a calibrated null or subtraction/division correction; E[P squared]=1/n under that idealization.',
        'interpretation':'Raw uses all finite recorded headings; primary excludes an entire frame when any fish is heading-masked. Affected-fish-only sensitivity requires >=80% valid headings. Differences in medians describe selection and changing fish composition, not a correction.',
    }
    return frame_output,result


def common_cohort_summaries(tables, labels, label_name, require_polarization=True):
    """Same frame IDs eligible for every setting; fish composition may differ."""
    if not tables:raise ValueError('No settings')
    if len(tables)!=len(labels):raise ValueError('Setting labels mismatch')
    ref=tables[0].frame.to_numpy()
    if any(not np.array_equal(t.frame.to_numpy(),ref) for t in tables):
        raise ValueError('Sensitivity tables do not share frame ordering')
    masks=[np.isfinite(t.circulation) for t in tables]
    if require_polarization:masks=[m&np.isfinite(t.polarization) for m,t in zip(masks,tables)]
    mask=np.logical_and.reduce(masks)
    return {
        'common_frames':int(mask.sum()),'common_fraction':float(mask.mean()),
        'require_valid_polarization':require_polarization,
        'definition':'Same frames eligible for every setting; eligible fish may differ. For threshold sweeps this is a selected high-relative-motion subset, not representative of the trial.',
        'settings':[{label_name:float(label),'circulation':quant(t.loc[mask,'circulation']),
                     'signed_circulation':quant(t.loc[mask,'signed_circulation']),
                     'polarization':quant(t.loc[mask,'polarization'])}
                    for label,t in zip(labels,tables)],
    }


def threshold_frame_selection(baseline, tables, thresholds, baseline_threshold):
    """Keep C's calculation fixed while changing the eligible frame set."""
    result=[]
    for threshold,t in zip(thresholds,tables):
        frame_mask=np.isfinite(t.circulation.to_numpy())
        baseline_valid=np.isfinite(baseline.circulation.to_numpy())
        joint=frame_mask&baseline_valid
        result.append({'threshold_frame_set_bl_s':float(threshold),
                       'candidate_frames':int(frame_mask.sum()),
                       'baseline_valid_frames':int(joint.sum()),
                       'baseline_undefined_frames':int((frame_mask&~baseline_valid).sum()),
                       'baseline_circulation':quant(baseline.loc[joint,'circulation']),
                       'baseline_signed_circulation':quant(baseline.loc[joint,'signed_circulation'])})
    return {'baseline_threshold_bl_s':float(baseline_threshold),'settings':result,
            'interpretation':'Fixed baseline C sampled on each threshold-eligible frame set. Frames where baseline C is undefined are counted and excluded; especially relevant to the lower-threshold set.'}


def scaled_measurements(k, c, length, curve, low_speed):
    speed=np.hypot(k.vx,k.vy).to_numpy()/length
    slip=np.arctan2(np.sin(np.arctan2(k.vy,k.vx)-k.ANGLE),
                    np.cos(np.arctan2(k.vy,k.vx)-k.ANGLE))
    slip=np.where((speed>=low_speed)&k.heading_valid,slip,np.nan)
    return {'reference_length_px':float(length),'speed_bl_s':quant(speed),
            'acceleration_bl_s2':quant(np.hypot(k.ax,k.ay)/length),
            'turn_rate_rad_s':quant(k.turn_rate),'slip_rad':quant(slip),
            'curvature_times_L':quant(curve*length),'spread_bl':quant(c.spread_bl),
            'centroid_speed_bl_s':quant(c.centroid_speed_bl_s),
            **collective_summary(c)}


def histogram(values, edges, path):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    counts,_=np.histogram(a,bins=edges)
    pd.DataFrame({'left':edges[:-1],'right':edges[1:],'count':counts}).to_csv(path,index=False)
    return {'finite_n':int(len(a)), 'counted_n':int(counts.sum()),
            'underflow':int((a<edges[0]).sum()), 'overflow':int((a>edges[-1]).sum()),
            'range':[float(edges[0]),float(edges[-1])], 'bins':int(len(edges)-1)}


def validate_config(cfg):
    windows=cfg['smoothing_windows']; primary=cfg['primary_window']
    if primary not in windows or len(windows)!=len(set(windows)):
        raise ValueError('Primary window missing or duplicate windows')
    if any(type(w) is not int or w<5 or w%2!=1 for w in windows):
        raise ValueError('Invalid smoothing windows')
    neighborhoods=cfg['curvature_neighborhoods']
    if any(n not in [5,7,9] for n in neighborhoods) or cfg['primary_curvature_neighborhood'] not in neighborhoods:
        raise ValueError('Projection supports curvature neighborhoods 5,7,9')
    thresholds=cfg['low_speed_sensitivity_bl_s']
    if cfg['low_speed_bl_s'] not in thresholds or len(thresholds)!=len(set(thresholds)) or any(not np.isfinite(t) or t<=0 for t in thresholds):
        raise ValueError('Invalid direction thresholds')
    if not 0 < cfg['circulation_min_fraction'] <= 1:
        raise ValueError('Invalid circulation eligibility fraction')
    if not 1 <= cfg['polynomial_order'] < min(windows):
        raise ValueError('Invalid smoothing polynomial order')
    if type(cfg.get('matched_frame_count',17999)) is not int or cfg.get('matched_frame_count',17999)<1:
        raise ValueError('Invalid matched frame count')


def run(data, output, config, no_network=False):
    cfg=json.loads(config.read_text());validate_config(cfg)
    if output.exists() and any(output.iterdir()): raise ValueError('Output directory must be new or empty')
    provenance_file=data/'provenance.json'
    if not provenance_file.is_file(): raise ValueError('Missing fetch provenance')
    fetch_provenance=json.loads(provenance_file.read_text())
    output.mkdir(parents=True,exist_ok=True); tables=output/'tables';tables.mkdir()
    path=data/'tracks.parquet'; parquet=pq.ParquetFile(path)
    available=parquet.schema_arrow.names
    requested=BASE_COLUMNS+IDENTITY_COLUMNS+POSE_COLUMNS
    if set(requested)-set(available): raise ValueError(f'Missing projected fields: {set(requested)-set(available)}')
    t=pd.read_parquet(path,columns=requested).sort_values(['frame','id']).reset_index(drop=True)
    quality=validate_tracks(t)
    group=str(t.group.iloc[0]); sequence=str(t.sequence.iloc[0]);trial=f'{group}/{sequence}'
    fish=quality['fish'];length=float(t.loc[t.body_length>0,'body_length'].median())
    bad_geometry_rows=(t.body_length<=0).to_numpy()
    bad_geometry_frames=quality['nonpositive_length_frames']
    print(f'{trial}: {len(t):,} rows, {fish} fish, measuring tracks',flush=True)
    curves={n:curvature(t,n) for n in cfg['curvature_neighborhoods']}
    for curve in curves.values():curve[bad_geometry_rows]=np.nan
    curve_common=np.logical_and.reduce([np.isfinite(x) for x in curves.values()])
    curvature_sensitivity=[{'neighborhood':n,**quant(v[curve_common]*length)} for n,v in curves.items()]
    core=t[CORE_COLUMNS].copy()
    primary=kinematics(core,cfg['primary_window'],cfg['polynomial_order'])
    speed=np.hypot(primary.vx,primary.vy).to_numpy()/length
    slip=np.arctan2(np.sin(np.arctan2(primary.vy,primary.vx)-primary.ANGLE),np.cos(np.arctan2(primary.vy,primary.vx)-primary.ANGLE))
    slip=np.where((speed>=cfg['low_speed_bl_s'])&primary.heading_valid,slip,np.nan)
    threshold_tables=[]; threshold_sensitivity=[]
    for threshold in cfg['low_speed_sensitivity_bl_s']:
        c=collective(primary,length,threshold,cfg['circulation_min_fraction'])
        c['eligible_fish_count']=np.rint(c.eligible_fraction*fish)
        c.to_csv(tables/f'collective-threshold-{threshold:g}.csv',index=False)
        threshold_tables.append(c)
        threshold_sensitivity.append({'threshold_bl_s':float(threshold),**collective_summary(c)})
    main_index=cfg['low_speed_sensitivity_bl_s'].index(cfg['low_speed_bl_s'])
    c=threshold_tables[main_index]
    c['heading_frame_valid']=np.isfinite(c.polarization)
    heading_frames,heading_sensitivity=heading_selection(primary,c,cfg['circulation_min_fraction'])
    for column in heading_frames:c[column]=heading_frames[column].to_numpy()
    c.to_csv(output/'collective.csv',index=False)
    threshold_common=common_cohort_summaries(threshold_tables,cfg['low_speed_sensitivity_bl_s'],'threshold_bl_s')
    threshold_c_common=common_cohort_summaries(threshold_tables,cfg['low_speed_sensitivity_bl_s'],'threshold_bl_s',False)
    frame_selection=threshold_frame_selection(c,threshold_tables,cfg['low_speed_sensitivity_bl_s'],cfg['low_speed_bl_s'])
    # Independent settings are processed sequentially; retain only speed arrays and frame summaries.
    speeds={cfg['primary_window']:speed}; window_tables={cfg['primary_window']:c}
    for window in cfg['smoothing_windows']:
        if window==cfg['primary_window']:continue
        motion=kinematics(core,window,cfg['polynomial_order'])
        speeds[window]=np.hypot(motion.vx,motion.vy).to_numpy()/length
        window_tables[window]=collective(motion,length,cfg['low_speed_bl_s'],cfg['circulation_min_fraction'])
        del motion;gc.collect()
    speed_common=np.logical_and.reduce([np.isfinite(s) for s in speeds.values()])
    speed_sensitivity=[{'window':w,**quant(speeds[w][speed_common])} for w in cfg['smoothing_windows']]
    window_sensitivity=[{'window':w,**collective_summary(window_tables[w])} for w in cfg['smoothing_windows']]
    window_common=common_cohort_summaries([window_tables[w] for w in cfg['smoothing_windows']],cfg['smoothing_windows'],'window')
    effective_cutoff=cfg['low_speed_bl_s']*(fish-1)/fish
    loo=collective(primary,length,effective_cutoff,cfg['circulation_min_fraction'])
    loo_summary={'effective_all_mean_cutoff_bl_s':effective_cutoff,
                 'other_fish_cutoff_bl_s':cfg['low_speed_bl_s'],
                 'interpretation':'Speed-threshold equivalent to subtracting the other-fish mean; directions and primary measurements unchanged. The tiny radius eligibility tolerance is retained.',
                 **collective_summary(loo)}
    scale_sensitivity=None
    if fish==151:
        scaled_tables=[collective(primary,length*1.15,threshold,cfg['circulation_min_fraction'])
                       for threshold in cfg['low_speed_sensitivity_bl_s']]
        scaled=scaled_tables[main_index]
        scaled.to_csv(tables/'collective-Lx1p15.csv',index=False)
        scale_sensitivity={'scenario':'Illustrative reference length increased by 15%; not a correction or new physical calibration.',
                           **scaled_measurements(primary,scaled,length*1.15,
                               curves[cfg['primary_curvature_neighborhood']],cfg['low_speed_bl_s']),
                           'speed_sensitivity':[{'window':w,**quant(speeds[w][speed_common]/1.15)} for w in cfg['smoothing_windows']],
                           'curvature_sensitivity':[{'neighborhood':n,**quant(v[curve_common]*length*1.15)} for n,v in curves.items()],
                           'heading_diagnostics':heading_diagnostics(primary,length*1.15,cfg['low_speed_bl_s']),
                           'threshold_sensitivity':[{'threshold_bl_s':float(threshold),**collective_summary(table)}
                               for threshold,table in zip(cfg['low_speed_sensitivity_bl_s'],scaled_tables)],
                           'threshold_common_eligible':common_cohort_summaries(scaled_tables,cfg['low_speed_sensitivity_bl_s'],'threshold_bl_s'),
                           'threshold_circulation_common_eligible':common_cohort_summaries(scaled_tables,cfg['low_speed_sensitivity_bl_s'],'threshold_bl_s',False),
                           'threshold_frame_selection':threshold_frame_selection(scaled,scaled_tables,cfg['low_speed_sensitivity_bl_s'],cfg['low_speed_bl_s']),
                           'limitation':'Changing L cannot repair an anatomically truncated or otherwise biased midline, nor rerender the ray-cast visual network. N=151 curvature and network metrics are not comparable for a size-trend claim.'}
    target_frames=int(cfg.get('matched_frame_count',17999))
    cutoff_frames=c.frame.iloc[:target_frames].to_numpy()
    matched_rows=core.frame.isin(cutoff_frames).to_numpy()
    matched=primary if len(cutoff_frames)==len(c) else kinematics(core.loc[matched_rows],cfg['primary_window'],cfg['polynomial_order'])
    matched_c=collective(matched,length,cfg['low_speed_bl_s'],cfg['circulation_min_fraction'])
    matched_h,matched_heading=heading_selection(matched,matched_c,cfg['circulation_min_fraction'])
    for column in matched_h:matched_c[column]=matched_h[column].to_numpy()
    matched_c.to_csv(tables/'collective-matched-duration.csv',index=False)
    matched_summary={'target_frame_count':target_frames,'frame_count':int(len(cutoff_frames)),
                     'frame_start':int(cutoff_frames[0]),'frame_end':int(cutoff_frames[-1]),
                     'duration_s':float(matched_c.time.max()-matched_c.time.min()),
                     **scaled_measurements(matched,matched_c,length,
                         curves[cfg['primary_curvature_neighborhood']][matched_rows],cfg['low_speed_bl_s']),
                     'heading_selection_sensitivity':matched_heading,
                     'definition':'First min(target, available) sorted observed frames; kinematics recomputed with the truncated endpoint, retaining original segment/gap boundaries.'}
    del matched;gc.collect()
    geometry_rows=~core.frame.isin(bad_geometry_frames).to_numpy()
    if bad_geometry_frames:
        if not geometry_rows.any():raise ValueError('No complete frames remain for bad-geometry sensitivity')
        geometry_motion=kinematics(core.loc[geometry_rows],cfg['primary_window'],cfg['polynomial_order'])
        geometry_c=collective(geometry_motion,length,cfg['low_speed_bl_s'],cfg['circulation_min_fraction'])
        geometry_h,geometry_heading=heading_selection(geometry_motion,geometry_c,cfg['circulation_min_fraction'])
        for column in geometry_h:geometry_c[column]=geometry_h[column].to_numpy()
    else:
        geometry_motion=primary;geometry_c=c;geometry_heading=heading_sensitivity
    geometry_summary={
        'excluded_frames':bad_geometry_frames,'excluded_frame_count':len(bad_geometry_frames),
        'source_frame_count':int(len(c)), 'retained_frame_count':int(len(geometry_c)),
        'excluded_fish_observations':int((~geometry_rows).sum()),
        **scaled_measurements(geometry_motion,geometry_c,length,
            curves[cfg['primary_curvature_neighborhood']][geometry_rows],cfg['low_speed_bl_s']),
        'heading_selection_sensitivity':geometry_heading,
        'circulation_valid_frame_fraction_of_source':float(np.isfinite(geometry_c.circulation).sum()/len(c)),
        'polarization_valid_frame_fraction_of_source':float(np.isfinite(geometry_c.polarization).sum()/len(c)),
        'definition':'Remove the complete frame whenever any fish has nonpositive body length, then recompute kinematics so smoothing never bridges the resulting gap. This is a sensitivity, not a claim that all retained finite primary positions/headings are correct. Own-set coverage uses retained frames; source-frame coverage is also recorded.',
    }
    common=c[['frame','polarization','circulation']].merge(
        geometry_c[['frame','polarization','circulation']],on='frame',suffixes=('_primary','_sensitivity'))
    geometry_summary['common_frame_comparison']={}
    for metric in ['polarization','circulation']:
        mask=np.isfinite(common[f'{metric}_primary'])&np.isfinite(common[f'{metric}_sensitivity'])
        geometry_summary['common_frame_comparison'][metric]={
            'frames':int(mask.sum()),'primary':quant(common.loc[mask,f'{metric}_primary']),
            'sensitivity':quant(common.loc[mask,f'{metric}_sensitivity'])}
    if bad_geometry_frames:
        geometry_export=c[['frame','time','segment']].merge(geometry_c.drop(columns=['time','segment']),on='frame',how='left')
        geometry_export['geometry_frame_retained']=~geometry_export.frame.isin(bad_geometry_frames)
        geometry_export.to_csv(tables/'collective-nonpositive-length-exclusion.csv',index=False)
    del geometry_motion;gc.collect()
    diagnostics=heading_diagnostics(primary,length,cfg['low_speed_bl_s'])
    space=spatial(core,length,cfg['spatial_extent_bl'],cfg['spatial_bins'])
    histograms={}
    for name,values,edges in [
        ('speed',speed,np.linspace(0,12,121)),
        ('turn',primary.turn_rate,np.linspace(-20,20,161)),
        ('curvature',curves[cfg['primary_curvature_neighborhood']]*length,np.linspace(-5,5,161)),
        ('nearest',space['nearest'].distance_bl,np.linspace(0,20,161)),
        ('polarization',c.polarization,np.linspace(0,1,51)),
        ('circulation',c.circulation,np.linspace(0,1,51)),
    ]:
        histograms[name]=histogram(values,edges,tables/f'{name}-histogram.csv')
    edges=space['bin_edges'];centers=(edges[1:]+edges[:-1])/2
    xx,yy=np.meshgrid(centers,centers,indexing='ij')
    spatial_table=pd.DataFrame({'forward_bl':xx.ravel(),'right_bl':yy.ravel(),'count':space['histogram'].ravel(),
                  'density_per_focal_per_bl2':space['density'].ravel()})
    spatial_table.to_csv(tables/'spatial-map.csv',index=False)
    matched_summary['nearest_neighbor_bl']=quant(space['nearest'].loc[space['nearest'].frame.isin(cutoff_frames),'distance_bl'])
    geometry_summary['nearest_neighbor_bl']=quant(space['nearest'].loc[~space['nearest'].frame.isin(bad_geometry_frames),'distance_bl'])
    if scale_sensitivity is not None:
        scale_sensitivity['nearest_neighbor_bl']=quant(space['nearest'].distance_bl/1.15)
        scaled_spatial=spatial_table.copy()
        scaled_spatial[['forward_bl','right_bl']]/=1.15
        scaled_spatial['density_per_focal_per_bl2']*=1.15**2
        scaled_spatial.to_csv(tables/'spatial-map-Lx1p15.csv',index=False)
        scale_sensitivity['spatial_map']={'density_multiplier':1.15**2,
            'coordinate_divisor':1.15,'extent_bl':cfg['spatial_extent_bl']/1.15,
            'normalization':'Original physical cells/pairs transformed to the new length units; coordinates divide by 1.15 and density multiplies by 1.15 squared. Not rebinned into a new fixed +/-10 BL crop.'}
    nearest_quant=quant(space['nearest'].distance_bl)
    spatial_summary={'focal_count':int(space['focal_count']),
                     'shown_pair_fraction':float(space['shown_pair_fraction']),
                     'extent_bl':cfg['spatial_extent_bl'],'bins':cfg['spatial_bins'],
                     'normalization':'Counts divided by all focal observations and bin area; visible map need not integrate to one.'}
    del space,core;gc.collect()
    summary={
        'trial':trial,'group':group,'sequence':sequence,'fish':fish,'quality':quality,
        'scope':'All valid observations of this trial; descriptive estimates, not independent samples or causal effects.',
        'length_scale_px':length,'body_length_px':quant(t.body_length),'speed_bl_s':quant(speed),
        'acceleration_bl_s2':quant(np.hypot(primary.ax,primary.ay)/length),
        'turn_rate_rad_s':quant(primary.turn_rate),'slip_rad':quant(slip),
        'curvature_times_L':quant(curves[cfg['primary_curvature_neighborhood']]*length),
        'curvature_sensitivity':curvature_sensitivity,'speed_sensitivity':speed_sensitivity,
        'polarization':quant(c.polarization),'circulation':quant(c.circulation),
        'signed_circulation':quant(c.signed_circulation),'spread_bl':quant(c.spread_bl),
        'centroid_speed_bl_s':quant(c.centroid_speed_bl_s),'nearest_neighbor_bl':nearest_quant,
        'threshold_sensitivity':threshold_sensitivity,'threshold_common_eligible':threshold_common,
        'threshold_circulation_common_eligible':threshold_c_common,
        'threshold_frame_selection':frame_selection,
        'window_sensitivity':window_sensitivity,'window_common_eligible':window_common,
        'leave_one_out_threshold_sensitivity':loo_summary,'scale_sensitivity_151':scale_sensitivity,
        'matched_duration_sensitivity':matched_summary,
        'nonpositive_length_frame_exclusion_sensitivity':geometry_summary,
        'heading_diagnostics':diagnostics,
        'heading_selection_sensitivity':heading_sensitivity,
        'polarization_eligible_frame_fraction':heading_sensitivity['polarization_eligible_frame_fraction'],
        'heading_axis_disagreement_abs_rad':quant(np.abs(primary.heading_axis_error)),
        'kinematics_eligible_fraction':float(np.isfinite(speed).mean()),
        'circulation_eligible_frame_fraction':float(np.isfinite(c.circulation).mean()),
        'joint_eligible_frame_fraction':float((np.isfinite(c.polarization)&np.isfinite(c.circulation)).mean()),
        'histograms':histograms,'spatial_map':spatial_summary,
        'finite_N_note':'Normalized circulation uses a finite number of dependent centroid-relative vectors; iid_direction_reference is illustrative, not a calibrated null or cross-N bias correction.',
        'time_base_note':'Track timestamps are used as provided. For N=151, the converter 29.97 fps convention is unverified against the raw video; speed, rates and eligibility inherit it.' if fish==151 else 'Track timestamps are used as provided; no independent camera-clock calibration performed in this comparison.',
        'signed_circulation_note':'Image-coordinate sign; do not compare chirality across cameras without verifying image orientation.',
        'video_status':'No new video overlays in this comparison; original 0066 pilot retains its three inspected examples.',
    }
    del primary,curves,speeds;gc.collect()
    if no_network:
        summary['network']={'status':'not_requested'}
    else:
        from .network_summary import summarize_network
        print(f'{trial}: streaming network',flush=True)
        summary['network']=summarize_network(data/'networks.parquet',t[['frame','id','X','Y']],output_dir=output/'network',
                                            batch_size=cfg.get('network_batch_size',131072),excluded_frames=bad_geometry_frames)
    pd.DataFrame(speed_sensitivity).to_csv(tables/'speed-sensitivity.csv',index=False)
    pd.DataFrame(curvature_sensitivity).to_csv(tables/'curvature-sensitivity.csv',index=False)
    atomic_json(output/'config.json',cfg)
    repo=Path(__file__).resolve().parents[2]
    inputs=[path,provenance_file]
    if not no_network:inputs.append(data/'networks.parquet')
    sources=[Path(__file__),repo/'src/shiners/metrics.py',repo/'src/shiners/network_summary.py',
             repo/'scripts/fetch_trials.py',repo/'scripts/fetch_pilot.py',repo/'pyproject.toml',repo/'uv.lock',config,
             repo/'docs/methods.md',repo/'docs/comparison-methods.md']
    sources=[p for p in sources if p.is_file()]
    input_hashes={str(p):file_hash(p) for p in inputs}
    for p in inputs:
        if p.name=='provenance.json':continue
        expected=fetch_provenance.get('files',{}).get(p.name,{}).get('sha256')
        if expected is None:raise ValueError(f'Missing fetch SHA256 for {p.name}')
        if expected!=input_hashes[str(p)]:raise ValueError(f'Input differs from fetch provenance: {p.name}')
    provenance={
        'created_utc':datetime.now(timezone.utc).isoformat(),'command':sys.argv,
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True),
        'python':sys.version,'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','pyarrow']},
        'source_hashes':{str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p):file_hash(p) for p in sources},
        'input_hashes':input_hashes,
        'fetch_member_hashes_match':True,
        'fetch_provenance':fetch_provenance,'projected_track_columns':requested,
        'source_schema':{f.name:str(f.type) for f in parquet.schema_arrow},
        'output_hashes':{str(p.relative_to(output)):file_hash(p) for p in output.rglob('*') if p.is_file()},
    }
    # Summary last is the completion marker. Its digest is included in provenance.
    encoded=json.dumps(summary,indent=2,allow_nan=False)+'\n'
    provenance['output_hashes']['summary.json']=hashlib.sha256(encoded.encode()).hexdigest()
    atomic_json(output/'provenance.json',provenance)
    (output/'summary.json.tmp').write_text(encoded);(output/'summary.json.tmp').replace(output/'summary.json')
    print(f'{trial}: complete; P median={summary["polarization"]["0.5"]}, C median={summary["circulation"]["0.5"]}, C coverage={summary["circulation_eligible_frame_fraction"]:.3f}',flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/comparison.json'))
    p.add_argument('--no-network',action='store_true',help='Track-only smoke test; network results explicitly absent')
    a=p.parse_args();run(a.data,a.output,a.config,a.no_network)

if __name__=='__main__':main()
