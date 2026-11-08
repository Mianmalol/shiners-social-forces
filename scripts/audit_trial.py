"""Audit one matched track/network trial; no derivatives span segment boundaries.

Usage: python scripts/audit_trial.py TRACKS.parquet NETWORKS.parquet OUTPUT_DIR
Dependencies: numpy pandas pyarrow scipy matplotlib
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tracks'); p.add_argument('networks'); p.add_argument('output')
    p.add_argument('--skip-plot', action='store_true')
    args = p.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    tr = pd.read_parquet(args.tracks).sort_values(['segment', 'id', 'frame'])
    net = pd.read_parquet(args.networks)
    assert not tr.duplicated(['frame', 'id']).any(), 'Duplicate track keys'
    assert not net.duplicated(['frame', 'id1', 'id2']).any(), 'Duplicate network keys'
    keys = pd.MultiIndex.from_frame(tr[['frame', 'id']])
    for col in ['id1', 'id2']:
        assert pd.MultiIndex.from_frame(net[['frame', col]]).isin(keys).all(), 'Dangling edge endpoint'
    assert (net.id1 != net.id2).all(), 'Self links'
    frames = np.sort(tr.frame.unique())
    fish = np.sort(tr.id.unique())
    length = float(tr.body_length.median())
    segs = tr.groupby('segment').agg(first_frame=('frame','min'), last_frame=('frame','max'), frames=('frame','nunique'))
    speeds = []; times = []
    for (_, _), g in tr.groupby(['segment', 'id']):
        # Require regular sampling inside segments; smooth 11 frames (~0.37 s).
        assert np.all(np.diff(g.frame)==1), 'Internal frame gap'
        dt = float(np.median(np.diff(g.time)))
        assert np.allclose(np.diff(g.time), dt), 'Irregular timestamps'
        v = np.column_stack([savgol_filter(g[c], 11, 3, deriv=1, delta=dt) for c in ['X','Y']])
        speeds.extend((np.linalg.norm(v[5:-5], axis=1)/length).tolist())
        times.extend(g.time.to_numpy()[5:-5].tolist())
    state = tr.assign(cx=np.cos(tr.ANGLE), sy=np.sin(tr.ANGLE)).groupby('frame').agg(time=('time','first'), cx=('cx','mean'), sy=('sy','mean'))
    state['polarization'] = np.hypot(state.cx, state.sy)
    degree = net.groupby(['frame','id1']).size().reindex(keys, fill_value=0)
    pairs = pd.MultiIndex.from_frame(net[['frame','id1','id2']])
    reverse = pd.MultiIndex.from_arrays([net.frame,net.id2,net.id1])
    quant = lambda x: {str(q):float(np.quantile(x,q)) for q in [.01,.05,.5,.95,.99]}
    report = dict(trial=str(tr.sequence.iloc[0]), track_rows=len(tr), track_columns=len(tr.columns),
        network_rows=len(net), fish=len(fish), tracked_frames=len(frames),
        frame_min=int(frames[0]), frame_max=int(frames[-1]),
        missing_frame_numbers=np.setdiff1d(np.arange(frames[0],frames[-1]+1),frames).tolist(),
        segments=segs.reset_index().to_dict('records'),
        track_nulls=tr.isna().sum().to_dict(), network_nulls=net.isna().sum().to_dict(),
        nonfinite_numeric_tracks=int((~np.isfinite(tr.select_dtypes('number'))).sum().sum()),
        body_length_px=quant(tr.body_length), mean_visible_neighbors=float(degree.mean()),
        reciprocal_edge_fraction=float(reverse.isin(pairs).mean()),
        angular_size_formula_max_error=float(np.abs(net.angular_size_deg-net.n_rays*.36).max()),
        polarization=quant(state.polarization), speed_body_lengths_per_second=quant(speeds),
        speed_method='11-frame cubic Savitzky-Golay derivative per fish/segment, five edge frames excluded; normalized by trial median body_length',
        checks_passed=['unique track and edge keys','edge endpoints exist','no self links','regular within-segment timestamps and frames'])
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    tr.describe(include='all').to_csv(out/'track-column-profile.csv')
    net.describe(include='all').to_csv(out/'network-column-profile.csv')
    print(json.dumps({k:v for k,v in report.items() if k not in ['track_nulls','network_nulls']},indent=2), flush=True)
    if args.skip_plot:
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1,3,figsize=(15,4))
    f=int(frames[len(frames)//2]); snap=tr[tr.frame==f].set_index('id')
    for row in net[net.frame==f].itertuples():
        a=snap.loc[row.id1]; b=snap.loc[row.id2]
        ax[0].plot([a.X,b.X],[a.Y,b.Y],color='#9bb5c3',alpha=.25,lw=.7)
    ax[0].quiver(snap.X,snap.Y,np.cos(snap.ANGLE),np.sin(snap.ANGLE),angles='xy',scale_units='xy',scale=.025,color='#146c94')
    ax[0].margins(.2); ax[0].invert_yaxis(); ax[0].set_aspect('equal'); ax[0].set_title(f'Frame {f}: headings and visible pairs')
    ax[0].set_xlabel('x (pixels)'); ax[0].set_ylabel('y (pixels, down)')
    ax[1].plot(state.time,state.polarization,lw=.5,color='#146c94'); ax[1].set_ylim(0,1)
    for s in segs.first_frame.iloc[1:]: ax[1].axvline(float(tr.loc[tr.frame==s,'time'].iloc[0]),color='gray',ls=':',lw=.6)
    ax[1].set_title('Heading polarization'); ax[1].set_xlabel('Time (s)')
    ax[2].hist(speeds,bins=70,color='#146c94'); ax[2].set_title('Smoothed speed'); ax[2].set_xlabel('Trial-median body lengths / second')
    fig.suptitle(f'{len(fish)}-fish trial {tr.sequence.iloc[0]}: initial audit (visibility is not inferred influence)')
    fig.tight_layout(); fig.savefig(out/'overview.png',dpi=160); plt.close(fig)

if __name__ == '__main__':
    main()
