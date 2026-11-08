"""Run the five-chapter descriptive pilot; source data remain immutable."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .validation import validate
from .metrics import kinematics, curvature, collective, spatial, visibility, heading_diagnostics


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def quant(x):
    a = np.asarray(x, dtype=float); a = a[np.isfinite(a)]
    return {'n': len(a), **{str(q): float(np.quantile(a, q)) if len(a) else None for q in [.05,.5,.95]}}


def segmented_plot(ax, frame_table, col, **kwargs):
    kwargs.setdefault('color', '#146c94')
    d = frame_table.sort_values('frame')
    breaks = (d.segment.diff().fillna(0) != 0) | (d.frame.diff().fillna(1) != 1)
    for _, g in d.groupby(breaks.cumsum()):
        ax.plot(g.time, g[col], **kwargs)


def video_overlays(tracks, video_path, out, quantiles, plt):
    if not video_path.exists():
        return {'status': 'not_run', 'reason': 'video.mp4 absent'}
    import av
    frames = np.sort(tracks.frame.unique())
    targets = [int(frames[int(q*(len(frames)-1))]) for q in quantiles]
    wanted = {x for f in targets for x in (f-1,f)}
    decoded = {}
    with av.open(str(video_path)) as c:
        c.streams.video[0].thread_type = 'AUTO'
        for i, frame in enumerate(c.decode(video=0)):
            if i in wanted:
                decoded[i] = frame.to_ndarray(format='rgb24')
            if i >= max(wanted):
                break
    if set(decoded) != wanted:
        raise ValueError('Video too short for selected overlays')
    fig, axes = plt.subplots(len(targets), 2, figsize=(12, 3.6*len(targets)))
    for row, f in enumerate(targets):
        snap = tracks[tracks.frame == f]
        for col, vf in enumerate([f-1, f]):
            ax = axes[row,col]; ax.imshow(decoded[vf])
            for r in snap.itertuples():
                ax.plot([getattr(r,f'poseX{i}') for i in range(21)],
                        [getattr(r,f'poseY{i}') for i in range(21)],lw=.7,color='cyan')
                ax.text(r.X, r.Y, str(r.id),color='yellow',fontsize=6)
            ax.set_xlim(snap.X.min()-70, snap.X.max()+70)
            ax.set_ylim(snap.Y.max()+70, snap.Y.min()-70)
            ax.set_title(f'Tracks {f}; video {vf}'); ax.axis('off')
    fig.suptitle('0066: predefined time-quantile overlays; compare i−1 and i')
    fig.tight_layout(); fig.savefig(out/'figures/video-overlays.png',dpi=160); plt.close(fig)
    return {'status':'generated_for_visual_review', 'track_frames':targets,
            'video_candidates':[[f-1,f] for f in targets],
            'note':'Overlays are qualitative; no numerical alignment accuracy inferred.'}


def run(args):
    cfg = json.loads(args.config.read_text())
    if not (args.data/'provenance.json').is_file():
        raise ValueError('Missing fetch provenance; run scripts/fetch_pilot.py first')
    out = args.output
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be new or empty; use a new run directory')
    (out/'figures').mkdir(parents=True,exist_ok=True); (out/'tables').mkdir()
    os.environ.setdefault('MPLCONFIGDIR', str(Path('.cache/matplotlib').resolve()))
    os.environ.setdefault('XDG_CACHE_HOME', str(Path('.cache').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    t = pd.read_parquet(args.data/'tracks.parquet').sort_values(['frame','id']).reset_index(drop=True)
    n = pd.read_parquet(args.data/'networks.parquet')
    quality = validate(t,n)
    if set(t.sequence.astype(str)) != {'0066'} or len(t.id.unique()) != 10:
        raise ValueError('This configured pilot expects 10-fish/0066')
    length = float(t.body_length.median())
    curves = {w: curvature(t,w) for w in cfg['curvature_neighborhoods']}
    motions = {w: kinematics(t,w,cfg['polynomial_order']) for w in cfg['smoothing_windows']}
    k = motions[cfg['primary_window']]
    speed = np.hypot(k.vx,k.vy)/length
    turn = k.turn_rate
    slip = np.arctan2(np.sin(np.arctan2(k.vy,k.vx)-t.ANGLE), np.cos(np.arctan2(k.vy,k.vx)-t.ANGLE))
    slip = np.where((speed >= cfg['low_speed_bl_s']) & k.heading_valid, slip, np.nan)
    c = collective(k,length,cfg['low_speed_bl_s'],cfg['circulation_min_fraction'])
    if 'frame' not in c.columns: c=c.reset_index()
    space = spatial(t,length,cfg['spatial_extent_bl'],cfg['spatial_bins'])
    vis = visibility(t,n)
    c.to_csv(out/'tables/collective.csv',index=False)
    vis['per_frame'].to_csv(out/'tables/visibility-time.csv',index=False)
    # Retain compact distributions and exact histogram tables, not huge per-fish intermediates.
    summary = {
        'scope':'10-fish/0066 pilot only; no interaction/causal model fitted',
        'length_scale_px': length, 'quality':quality,
        'speed_bl_s':quant(speed), 'acceleration_bl_s2':quant(np.hypot(k.ax,k.ay)/length),
        'turn_rate_rad_s':quant(turn), 'slip_rad':quant(slip),
        'curvature_times_L':quant(curves[cfg['primary_curvature_neighborhood']]*length),
        'polarization':quant(c.polarization), 'circulation':quant(c.circulation),
        'signed_circulation':quant(c.signed_circulation),
        'spread_bl':quant(c.spread_bl), 'nearest_neighbor_bl':quant(space['nearest'].distance_bl),
        'visible_degree':quant(vis['degree'].degree),
        'visible_degree_mean':float(vis['degree'].degree.mean()),
        'reciprocal_edge_fraction':float(vis['reciprocal_edge_fraction']),
        'eligibility':{'kinematics_fraction':float(np.isfinite(speed).mean()),
                       'slip_fraction':float(np.isfinite(slip).mean()),
                       'circulation_frame_fraction':float(np.isfinite(c.circulation).mean()),
                       'curvature_fraction':float(np.isfinite(curves[cfg['primary_curvature_neighborhood']]).mean()),
                       'spatial_displayed_pair_fraction':float(space['shown_pair_fraction'])},
    }
    from scipy.signal import savgol_coeffs
    dt=float(t.groupby('id').time.diff().dropna().median())
    sigma=np.array([np.nanstd(t.X-k["xs"]),np.nanstd(t.Y-k["ys"])])
    summary['noise_diagnostic']={'position_residual_sd_px':sigma.tolist(),
        'velocity_component_sd_bl_s':(sigma*np.linalg.norm(savgol_coeffs(cfg['primary_window'],3,deriv=1,delta=dt))/length).tolist(),
        'acceleration_component_sd_bl_s2':(sigma*np.linalg.norm(savgol_coeffs(cfg['primary_window'],3,deriv=2,delta=dt))/length).tolist(),
        'limitation':'Illustrative white-noise propagation only; SG residuals include real movement and are correlated. Not calibrated uncertainty.'}
    summary['heading_diagnostics']=heading_diagnostics(k,length,cfg['low_speed_bl_s'])
    summary['heading_qa']={'jump_flagged_rows':int(k.heading_jump.sum()),
        'axis_disagreement_abs_rad':quant(np.abs(k.heading_axis_error)),
        'axis_disagreement_over_pi_over_2_rows':int((np.abs(k.heading_axis_error)>np.pi/2).sum())}
    thresholds=[]
    for threshold in cfg['low_speed_sensitivity_bl_s']:
        cc=collective(k,length,threshold,cfg['circulation_min_fraction'])
        thresholds.append({'threshold_bl_s':threshold,'slip_eligible_fraction':float(((speed>=threshold)&k.heading_valid).mean()),
            'circulation_eligible_frame_fraction':float(np.isfinite(cc.circulation).mean()),
            'circulation_median':quant(cc.circulation)['0.5']})
    pd.DataFrame(thresholds).to_csv(out/'tables/threshold-sensitivity.csv',index=False)
    summary['threshold_sensitivity']=thresholds
    summary['polarization_by_circulation_eligibility']={
        'eligible':quant(c.loc[np.isfinite(c.circulation),'polarization']),
        'ineligible':quant(c.loc[~np.isfinite(c.circulation),'polarization'])}
    def hist(ax, values, name, xlabel, bins=60):
        a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
        counts,edges=np.histogram(a,bins=bins)
        ax.stairs(counts,edges,fill=True,alpha=.85,color='#146c94');ax.set_xlabel(xlabel);ax.set_ylabel('Count')
        pd.DataFrame({'left':edges[:-1],'right':edges[1:],'count':counts}).to_csv(out/f'tables/{name}.csv',index=False)
    def save(fig,name,title):
        fig.suptitle('0066 pilot — '+title);fig.tight_layout()
        for ext in ['png','svg']:fig.savefig(out/f'figures/{name}.{ext}',dpi=150,bbox_inches='tight')
        plt.close(fig)
    common=np.logical_and.reduce([np.isfinite(m.vx)&np.isfinite(m.vy) for m in motions.values()])
    sensitivity=[]
    for w,m in motions.items():
        sensitivity.append({'window':w,**quant((np.hypot(m.vx,m.vy)/length)[common])})
    summary['speed_sensitivity']=sensitivity
    pd.DataFrame(sensitivity).to_csv(out/'tables/speed-sensitivity.csv',index=False)
    fig,ax=plt.subplots(1,3,figsize=(13,3.8))
    hist(ax[0],speed,'speed','Speed (trial-median body lengths/s)')
    hist(ax[1],turn,'turn','Body turn rate (rad/s; clockwise positive)')
    for w,m in motions.items():
        vals=(np.hypot(m.vx,m.vy)/length)[common];counts,bins=np.histogram(vals,bins=np.linspace(0,10,81))
        ax[2].stairs(counts,bins,label=f'{w} frames')
    ax[2].legend();ax[2].set_xlabel('Speed; common eligible observations');ax[2].set_ylabel('Count')
    save(fig,'01-movement','Derived movement and smoothing sensitivity')
    cs=[]
    curvature_common=np.logical_and.reduce([np.isfinite(v) for v in curves.values()])
    for w,v in curves.items():cs.append({'neighborhood':w,**quant(v[curvature_common]*length)})
    summary['curvature_sensitivity']=cs
    pd.DataFrame(cs).to_csv(out/'tables/curvature-sensitivity.csv',index=False)
    fig,ax=plt.subplots(1,2,figsize=(11,4))
    hist(ax[0],curves[cfg['primary_curvature_neighborhood']]*length,'curvature','κ × trial-median body length')
    ax[0].set_title('Positive: clockwise head-to-tail; normally concave fish-left',fontsize=9)
    fish=t[t.id==t.id.min()]
    for q in cfg['video_quantiles']:
        r=fish.iloc[int(q*(len(fish)-1))];dx=np.array([r[f'poseX{i}']-r.poseX0 for i in range(21)]);dy=np.array([r[f'poseY{i}']-r.poseY0 for i in range(21)])
        ax[1].plot((dx*np.cos(r.ANGLE)+dy*np.sin(r.ANGLE))/length,(-dx*np.sin(r.ANGLE)+dy*np.cos(r.ANGLE))/length,label=f'frame {int(r.frame)}')
    ax[1].set_aspect('equal');ax[1].set_ylim(.25,-.25);ax[1].set_xlabel('Forward from head (body lengths)');ax[1].set_ylabel('Fish-right (body lengths)');ax[1].legend(loc='upper right',fontsize=8)
    save(fig,'02-posture','Derived curvature; predefined midline examples')
    fig,ax=plt.subplots(2,2,figsize=(12,7))
    for a,col,label in zip(ax.flat[:3],['polarization','circulation','spread_bl'],['Heading polarization','Centroid-relative circulation','RMS spread (body lengths)']):
        segmented_plot(a,c,col,lw=.6);a.set_xlabel('Time (s)');a.set_ylabel(label)
    segmented_plot(ax[0,1],c,'iid_direction_reference',lw=.7,color='orange',ls=':')
    ax[0,1].set_title('Orange: illustrative iid reference, not significance')
    valid=c.dropna(subset=['polarization','circulation'])
    ax[1,1].hexbin(valid.polarization,valid.circulation,gridsize=40,mincnt=1,cmap='Blues');ax[1,1].set_xlabel('Heading polarization');ax[1,1].set_ylabel('Circulation')
    ax[1,1].set_title(f'Conditioned on relative-motion eligibility ({len(valid)/len(c):.1%} of frames)',fontsize=9)
    save(fig,'03-organization','Collective measurements; low alignment does not imply disorder')
    fig,ax=plt.subplots(1,2,figsize=(11,4))
    h=space['histogram'];edges=space['bin_edges'];density=h/(space['focal_count']*np.diff(edges)[0]**2)
    im=ax[0].pcolormesh(edges,edges,density.T,cmap='Blues');cb=fig.colorbar(im,ax=ax[0]);cb.set_label('Neighbors / focal observation / square body length',fontsize=8)
    ax[0].set_xlabel('Neighbor forward (body lengths)');ax[0].set_ylabel('Neighbor fish-right (body lengths)');ax[0].invert_yaxis();ax[0].set_aspect('equal')
    hist(ax[1],space['nearest'].distance_bl,'nearest','Nearest-neighbor distance (body lengths)')
    gridx,gridy=np.meshgrid((edges[:-1]+edges[1:])/2,(edges[:-1]+edges[1:])/2,indexing='ij')
    pd.DataFrame({'forward':gridx.ravel(),'right':gridy.ravel(),'count':h.ravel(),'density':density.ravel()}).to_csv(out/'tables/spatial-map.csv',index=False)
    save(fig,'04-spacing','Observed neighbor occupancy, not an inferred force')
    fig,ax=plt.subplots(1,3,figsize=(13,4))
    hist(ax[0],vis['degree'].degree,'degree','Number of visible neighbors',bins=np.arange(-.5,10.5,1))
    vf=vis['per_frame'].merge(c[['frame','time','segment']],on='frame',validate='one_to_one')
    segmented_plot(ax[1],vf,'mean_degree',lw=.6);ax[1].set_xlabel('Time (s)');ax[1].set_ylabel('Mean visible neighbors')
    hist(ax[2],n.angular_size_deg,'angular-size','Reconstructed angular size (degrees)')
    save(fig,'05-visibility','Geometric visual access, not measured influence')
    summary['video']=video_overlays(t,args.data/'video.mp4',out,cfg['video_quantiles'],plt)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    (out/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    source_files=[Path('scripts/fetch_pilot.py'),Path('pyproject.toml'),Path('uv.lock'),args.config,Path('docs/methods.md'),*Path('src/shiners').glob('*.py'),*Path('tests').glob('*.py')]
    raw=[args.data/'tracks.parquet',args.data/'networks.parquet']
    if (args.data/'video.mp4').exists():raw.append(args.data/'video.mp4')
    provenance={'created_utc':datetime.now(timezone.utc).isoformat(),'command':sys.argv,
      'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'git_status':subprocess.check_output(['git','status','--porcelain'],text=True),
      'python':sys.version,'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','pyarrow','matplotlib','av']},
      'source_hashes':{str(p):digest(p) for p in source_files},'input_hashes':{str(p):digest(p) for p in raw},
      'fetch_provenance':json.loads((args.data/'provenance.json').read_text()) if (args.data/'provenance.json').exists() else None,
      'output_hashes':{str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()}}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path('data/0066'))
    p.add_argument('--config',type=Path,default=Path('configs/pilot.json'))
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())

if __name__=='__main__':main()
