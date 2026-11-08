"""Plot completed trial summaries without loading the raw parquet data.

Run after compare_trial: python scripts/plot_comparison.py
Every plotted interval is a within-trial 5th–95th percentile range, not a CI.
Each trial is a separate point; observations are never pooled across trials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRIALS = ('10-fish__0066', '10-fish__0105', '10-fish__0126',
          '30-fish__0084', '30-fish__0115', '30-fish__0120',
          '70-fish__0103', '70-fish__0107', '70-fish__0124',
          '150-fish__150-fish')
GROUPS = (10, 30, 70, 151)
COLORS = {10: '#0072B2', 30: '#D55E00', 70: '#009E73', 151: '#8D4CA8'}
QKEYS = {'0.05': 'p05', '0.5': 'median', '0.95': 'p95'}
METRICS = {
    'polarization': ('Heading alignment P', 'group-frame', 'index'),
    'circulation': ('Centroid-relative circulation C', 'eligible group-frame', 'index'),
    'signed_circulation': ('Signed circulation', 'eligible group-frame', 'index'),
    'speed_bl_s': ('Swimming speed', 'fish-frame', 'body lengths / s'),
    'turn_rate_rad_s': ('Signed turning rate', 'fish-frame', 'rad / s'),
    'curvature_times_L': ('Signed body bending', 'fish-frame', 'curvature × reference length'),
    'spread_bl': ('RMS group spread', 'group-frame', 'body lengths'),
    'nearest_neighbor_bl': ('Nearest-neighbor distance', 'fish-frame', 'body lengths'),
}


def quant_check(q, name, maximum=None):
    if type(q['n']) is not int or q['n'] < 0:
        raise ValueError(f'{name}: invalid observation count')
    values = [q[k] for k in QKEYS]
    if q['n'] == 0:
        if any(v is not None for v in values):
            raise ValueError(f'{name}: nonempty quantiles with zero observations')
        return
    if any(v is None or not np.isfinite(v) for v in values) or values != sorted(values):
        raise ValueError(f'{name}: invalid/unsorted quantiles')
    if maximum is not None and (values[0] < -1e-10 or values[-1] > maximum+1e-10):
        raise ValueError(f'{name}: outside [0,{maximum}]')


def validate_trial(stem, summary, collective):
    expected_n = int(stem.split('-fish')[0])
    if expected_n == 150: expected_n = 151
    if summary['trial'] != stem.replace('__', '/') or summary['fish'] != expected_n:
        raise ValueError(f'{stem}: mismatched identity or observed fish count')
    frames = summary['quality']['frames']
    required = {'frame', 'time', 'segment', 'polarization', 'circulation',
                'eligible_fraction', 'polarization_valid_fish'}
    if not required.issubset(collective.columns) or len(collective) != frames or frames == 0:
        raise ValueError(f'{stem}: collective table schema/frame count mismatch')
    for key in ['frame', 'time', 'segment']:
        if not np.isfinite(collective[key]).all():
            raise ValueError(f'{stem}: nonfinite {key}')
    if collective.frame.duplicated().any() or (np.diff(collective.frame) <= 0).any() or (np.diff(collective.time) <= 0).any():
        raise ValueError(f'{stem}: repeated/nonmonotone group frames or times')
    for key in METRICS:
        quant_check(summary[key], key, 1 if key in ('polarization', 'circulation') else None)
    for key in ('polarization', 'circulation'):
        a = collective[key].to_numpy(dtype=float)
        if np.isinf(a).any(): raise ValueError(f'{stem}: infinite {key}')
        a = a[np.isfinite(a)]
        if len(a) != summary[key]['n']:
            raise ValueError(f'{stem}: {key} table/summary count mismatch')
        if len(a) and not np.allclose(np.quantile(a, [.05,.5,.95]), [summary[key][k] for k in QKEYS], atol=1e-10):
            raise ValueError(f'{stem}: {key} table/summary quantile mismatch')
        if len(a) and (a.min() < -1e-10 or a.max() > 1+1e-10):
            raise ValueError(f'{stem}: {key} outside [0,1]')
    fraction = summary['circulation']['n']/frames
    if not np.isclose(fraction, summary['circulation_eligible_frame_fraction'], atol=1e-12, rtol=0):
        raise ValueError(f'{stem}: circulation coverage mismatch')
    joint = (np.isfinite(collective.polarization) & np.isfinite(collective.circulation)).mean()
    if not np.isclose(joint, summary['joint_eligible_frame_fraction'], atol=1e-12, rtol=0):
        raise ValueError(f'{stem}: joint coverage mismatch')
    velocity_defined = np.isfinite(collective.eligible_fraction)
    if (np.isfinite(collective.circulation) & ~velocity_defined).any():
        raise ValueError(f'{stem}: circulation exists without defined velocities')
    for key in ('eligible_fraction','polarization_valid_fish'):
        values = collective[key].to_numpy(dtype=float)
        if np.isinf(values).any() or ((values[np.isfinite(values)] < -1e-10)
                                     | (values[np.isfinite(values)] > 1+1e-10)).any():
            raise ValueError(f'{stem}: invalid {key}')
    thresholds = summary['threshold_sensitivity']
    if sorted(t['threshold_bl_s'] for t in thresholds) != [.25,.5,1.]:
        raise ValueError(f'{stem}: expected three threshold settings')
    common = summary['threshold_circulation_common_eligible']
    if not np.isclose(common['common_frames']/frames, common['common_fraction'], atol=1e-12, rtol=0):
        raise ValueError(f'{stem}: common-frame coverage mismatch')
    settings = {t['threshold_bl_s']:t for t in common['settings']}
    if set(settings) != {.25,.5,1.}: raise ValueError(f'{stem}: missing common-frame setting')
    for t in thresholds:
        quant_check(t['circulation'], 'threshold circulation', 1)
        n = t['circulation']['n']
        if not np.isclose(n/frames, t['circulation_eligible_frame_fraction'], atol=1e-12, rtol=0):
            raise ValueError(f'{stem}: threshold coverage mismatch')
        q = settings[t['threshold_bl_s']]['circulation']
        quant_check(q, 'common-frame circulation', 1)
        if q['n'] != common['common_frames'] or q['n'] > n:
            raise ValueError(f'{stem}: inconsistent common-frame count')
    selections = {t['threshold_frame_set_bl_s']:t for t in summary['threshold_frame_selection']['settings']}
    if set(selections) != {.25,.5,1.}: raise ValueError(f'{stem}: missing frame-selection setting')
    for t in thresholds:
        selected = selections[t['threshold_bl_s']]
        if (selected['candidate_frames'] != t['circulation']['n']
                or selected['baseline_valid_frames'] != selected['baseline_circulation']['n']
                or selected['baseline_valid_frames']+selected['baseline_undefined_frames'] != selected['candidate_frames']):
            raise ValueError(f'{stem}: inconsistent baseline frame-selection count')
    by_threshold = {t['threshold_bl_s']:t for t in thresholds}
    counts = [by_threshold[t]['circulation']['n'] for t in (.25,.5,1.)]
    if counts != sorted(counts,reverse=True):
        raise ValueError(f'{stem}: threshold frame counts are not nested')
    if summary['threshold_frame_selection']['baseline_threshold_bl_s'] != .5:
        raise ValueError(f'{stem}: expected the 0.5 baseline threshold')
    if (selections[.25]['baseline_circulation'] != selections[.5]['baseline_circulation']
            or selections[.5]['baseline_circulation'] != summary['circulation']):
        raise ValueError(f'{stem}: baseline 0.25/0.5 identity failed')
    if (selections[1.]['baseline_undefined_frames'] != 0
            or selections[.5]['baseline_undefined_frames'] != 0
            or selections[.25]['baseline_undefined_frames'] != counts[0]-counts[1]):
        raise ValueError(f'{stem}: nested baseline undefined-frame identity failed')
    if (common['common_frames'] != counts[2]
            or settings[1.]['circulation'] != by_threshold[1.]['circulation']):
        raise ValueError(f'{stem}: common circulation set must equal the 1.0 frame set')
    network = summary['network']
    if network.get('status') == 'not_requested':
        raise ValueError(f'{stem}: network analysis is incomplete')
    if network['fish'] != expected_n or network['tracked_frame_count'] != frames:
        raise ValueError(f'{stem}: network/track coverage mismatch')
    nobs = network['observer_frame_count']
    if nobs != network['covered_frame_count']*expected_n or not 0 <= nobs <= frames*expected_n:
        raise ValueError(f'{stem}: network observation denominator mismatch')
    hist = network['degree_histogram']
    if sum(hist['count']) != nobs:
        raise ValueError(f'{stem}: visible-degree histogram denominator mismatch')
    for k in ['visible_fraction_mean', 'reciprocal_edge_fraction']:
        if network[k] is not None and not 0 <= network[k] <= 1:
            raise ValueError(f'{stem}: network fraction out of bounds')


def load_trials(root, allow_partial=False):
    missing = [s for s in TRIALS if not (root/'trials'/s/'summary.json').is_file() or not (root/'trials'/s/'collective.csv').is_file()]
    if missing and not allow_partial:
        raise ValueError('Comparison incomplete; missing completed summaries/tables: '+', '.join(missing))
    records = []
    for stem in TRIALS:
        if stem in missing: continue
        directory = root/'trials'/stem
        summary = json.loads((directory/'summary.json').read_text())
        collective = pd.read_csv(directory/'collective.csv')
        validate_trial(stem, summary, collective)
        records.append({'stem':stem, 'summary':summary, 'collective':collective})
    if not records: raise ValueError('No completed trials available')
    return records, missing


def degree_quantiles(network):
    """Exact NumPy-linear quantiles from integer degree counts, without expansion."""
    hist = network['degree_histogram']
    values, counts = np.asarray(hist['degree']), np.asarray(hist['count'], dtype=np.int64)
    if len(values) != len(counts) or (counts < 0).any() or (np.diff(values) <= 0).any():
        raise ValueError('Invalid degree histogram')
    n = int(counts.sum())
    q = {'n': n}
    for key in QKEYS:
        if n == 0: q[key] = None; continue
        rank = float(key)*(n-1)
        lo, hi = int(np.floor(rank)), int(np.ceil(rank))
        cs = np.cumsum(counts)
        vlo, vhi = values[np.searchsorted(cs, [lo, hi], side='right')]
        q[key] = float((vlo+(vhi-vlo)*(rank-lo))/(network['fish']-1))
    return q


def quant_columns(prefix, q):
    return {prefix+'_n':q['n'], **{prefix+'_'+label:q[key] for key,label in QKEYS.items()}}


def finite_quantiles(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return {'n':int(len(a)),**{key:float(np.quantile(a,float(key))) if len(a) else None for key in QKEYS}}


def make_tables(records):
    trials, thresholds, metrics, sensitivity = [], [], [], []
    for r in records:
        s = r['summary']; net = s['network']; stem = r['stem']; c = r['collective']
        velocity_defined = int(np.isfinite(c.eligible_fraction).sum())
        added = ~np.isfinite(c.polarization) & np.isfinite(c.polarization_valid_fish)
        added_p = finite_quantiles(c.loc[added,'polarization_valid_fish'])
        ident = {'trial':stem, 'fish':s['fish']}
        row = {**ident, 'source_group':s['group'], 'sequence':s['sequence'],
               'tracked_frames':s['quality']['frames'], 'duration_s':s['quality']['duration_s'],
               'segments':s['quality']['segment_count'], 'length_scale_px':s['length_scale_px'],
               'nonpositive_length_rows':s['quality'].get('nonpositive_length_rows'),
               'nonpositive_length_frame_count':s['quality'].get('nonpositive_length_frame_count'),
               'circulation_eligible_frame_fraction':s['circulation_eligible_frame_fraction'],
               'velocity_defined_frames':velocity_defined,
               'velocity_defined_frame_fraction':velocity_defined/len(c),
               'circulation_eligible_fraction_of_velocity_defined_frames':s['circulation']['n']/velocity_defined if velocity_defined else None,
               'polarization_valid_fish_added_frames':int(added.sum()),
               'joint_eligible_frame_fraction':s['joint_eligible_frame_fraction'],
               'iid_uniform_heading_approx_mean_reference':float(np.sqrt(np.pi/(4*s['fish']))),
               'network_covered_frames':net['covered_frame_count'],
               'visible_fraction_mean':net['visible_fraction_mean'],
               'reciprocal_edge_fraction':net['reciprocal_edge_fraction']}
        row.update(quant_columns('polarization_valid_fish_on_added_frames',added_p))
        metrics.append({**ident,'metric':'polarization_valid_fish_on_added_frames',
                        'observation_unit':'group-frame with primary P undefined and subset P finite',
                        'measurement_unit':'index','n':added_p['n'],
                        **{label:added_p[key] for key,label in QKEYS.items()}})
        for name, (_,unit,scale) in METRICS.items():
            row.update(quant_columns(name,s[name]))
            metrics.append({**ident,'metric':name,'observation_unit':unit,'measurement_unit':scale,
                            'n':s[name]['n'], **{label:s[name][key] for key,label in QKEYS.items()}})
        visible = degree_quantiles(net)
        row.update(quant_columns('visible_fraction', visible))
        metrics.append({**ident,'metric':'visible_fraction','observation_unit':'fish-frame in covered frames',
                        'measurement_unit':'fraction of other fish','n':visible['n'],
                        **{label:visible[key] for key,label in QKEYS.items()}})
        heading = s.get('heading_selection_sensitivity',{})
        if 'raw_polarization' in heading: row.update(quant_columns('polarization_raw',heading['raw_polarization']))
        if 'polarization_eligible_frame_fraction' in s:
            row['polarization_eligible_frame_fraction']=s['polarization_eligible_frame_fraction']
        trials.append(row)
        common = s['threshold_circulation_common_eligible']
        settings = {t['threshold_bl_s']:t for t in common['settings']}
        joint_common = {t['threshold_bl_s']:t for t in s['threshold_common_eligible']['settings']}
        selections = {t['threshold_frame_set_bl_s']:t for t in s['threshold_frame_selection']['settings']}
        for t in s['threshold_sensitivity']:
            q = settings[t['threshold_bl_s']]['circulation']
            selected = selections[t['threshold_bl_s']]
            thresholds.append({**ident,'threshold_bl_s':t['threshold_bl_s'],
                'tracked_frames':s['quality']['frames'],
                'eligible_frame_fraction':t['circulation_eligible_frame_fraction'],
                **quant_columns('own_subset_circulation',t['circulation']),
                'common_frame_fraction':common['common_fraction'],
                **quant_columns('common_subset_circulation',q),
                **quant_columns('joint_common_subset_circulation',joint_common[t['threshold_bl_s']]['circulation']),
                'baseline_threshold_bl_s':s['threshold_frame_selection']['baseline_threshold_bl_s'],
                'baseline_candidate_frames':selected['candidate_frames'],
                'baseline_undefined_frames':selected['baseline_undefined_frames'],
                **quant_columns('baseline_circulation_on_selected_frames',selected['baseline_circulation'])})
        for family, items, param in [
            ('smoothing_window',s.get('window_sensitivity',[]),'window'),
            ('speed_smoothing',s.get('speed_sensitivity',[]),'window'),
            ('curvature_neighborhood',s.get('curvature_sensitivity',[]),'neighborhood'),
            ('leave_one_out', [s['leave_one_out_threshold_sensitivity']], 'effective_all_mean_cutoff_bl_s'),
            ('length_scale_151', [s['scale_sensitivity_151']] if s.get('scale_sensitivity_151') else [], 'reference_length_px'),
        ]:
            for item in items:
                itemrow = {**ident,'family':family,'parameter':param,'value':item[param]}
                if 'n' in item: itemrow.update(quant_columns('measurement', item))
                for key in ('circulation','signed_circulation','polarization','speed_bl_s','curvature_times_L'):
                    if key in item: itemrow.update(quant_columns(key,item[key]))
                for key in ('circulation_eligible_frame_fraction','joint_eligible_frame_fraction','other_fish_cutoff_bl_s'):
                    if key in item: itemrow[key]=item[key]
                sensitivity.append(itemrow)
        wc = s.get('window_common_eligible',{})
        for item in wc.get('settings',[]):
            sensitivity.append({**ident,'family':'smoothing_common_frames','parameter':'window','value':item['window'],
                                'common_fraction':wc['common_fraction'],**quant_columns('circulation',item['circulation'])})
        # Keep the complete, potentially nested heading-selection diagnostics reviewable.
        if s.get('heading_selection_sensitivity'):
            for path,value in flatten(s['heading_selection_sensitivity']):
                sensitivity.append({**ident,'family':'heading_selection','parameter':path,'value':value})
        for key in ('matched_duration_sensitivity','scale_sensitivity_151',
                    'nonpositive_length_frame_exclusion_sensitivity'):
            if s.get(key):
                for path,value in flatten(s[key]):
                    sensitivity.append({**ident,'family':key,'parameter':path,'value':value})
        for key in ('matched_duration','nonpositive_length_frame_exclusion_sensitivity'):
            if net.get(key):
                for path,value in flatten(net[key]):
                    sensitivity.append({**ident,'family':'network_'+key,'parameter':path,'value':value})
    return { 'trials':pd.DataFrame(trials), 'thresholds':pd.DataFrame(thresholds),
             'metrics':pd.DataFrame(metrics), 'sensitivity':pd.DataFrame(sensitivity)}


def flatten(value, prefix=''):
    if isinstance(value,dict):
        for key,child in value.items(): yield from flatten(child, f'{prefix}.{key}'.lstrip('.'))
    elif isinstance(value,list):
        for i,child in enumerate(value): yield from flatten(child, f'{prefix}.{i}')
    else: yield prefix,value


def point_style(stem, fish):
    peers = [t for t in TRIALS if t.startswith(f'{150 if fish == 151 else fish}-fish__')]
    i = peers.index(stem)
    x = GROUPS.index(fish)+(i-1)*.19 if fish != 151 else GROUPS.index(fish)
    marker = ('o','s','^')[i] if fish != 151 else 'D'
    return x,COLORS[fish],marker


def group_axis(ax, ylabel, bounded=False):
    ax.set_xticks(range(4), ['10','30','70','151*'])
    ax.set_xlabel('Observed fish in the group')
    ax.set_ylabel(ylabel)
    if bounded: ax.set_ylim(-.025,1.06)
    ax.set_xlim(-.5,3.55)
    ax.grid(axis='y',color='#dddddd',lw=.7)
    ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)


def interval_points(ax, frame, metric, labels=False):
    for r in frame.to_dict('records'):
        x,color,marker = point_style(r['trial'],r['fish'])
        y,lo,hi = (r.get(metric+'_'+q) for q in ('median','p05','p95'))
        if pd.isna(y): continue
        ax.errorbar(x,y,yerr=[[y-lo],[hi-y]],fmt=marker,color=color,
                    elinewidth=1.5,capsize=4,markersize=6,zorder=3)
        if labels:
            label = r['trial'].split('__')[1] if r['fish'] != 151 else '151 fish*'
            ax.annotate(label,(x,y),xytext=(0,8),textcoords='offset points',fontsize=7,color=color,ha='center')


def save(fig, directory, name, partial=False):
    if partial: fig.text(.5,.995,'PARTIAL COMPARISON — missing trials',ha='center',va='top',color='#aa2222',weight='bold')
    fig.savefig(directory/(name+'.png'),dpi=180,bbox_inches='tight')
    fig.savefig(directory/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)


def plot_alignment(tables, directory, partial=False):
    fig,axes = plt.subplots(1,2,figsize=(13,5.2))
    for ax,key,title in zip(axes,('polarization','circulation'),('Heading alignment P','Centroid-relative circulation C')):
        interval_points(ax,tables['trials'],key,True)
        group_axis(ax,title,bounded=True)
        ax.set_title(title+' across trials')
    for x,fish in enumerate(GROUPS):
        axes[0].hlines(np.sqrt(np.pi/(4*fish)),x-.3,x+.3,color='#666666',ls=':',lw=1.4)
    axes[0].plot([],[],ls=':',color='#666666',label='Independent isotropic headings: approximate mean P')
    axes[0].legend(loc='lower left',fontsize=8)
    fig.suptitle('Each marker is one trial; whiskers show within-trial 5th–95th percentiles',fontsize=13)
    fig.text(.5,.005,'Group-frame observations; C uses its eligible frames only. Ranges are not confidence intervals.\nDotted P reference √[π/(4N)] is illustrative, not a calibrated null, expected median or cross-N correction.\n*151 fish: one trial, different camera/length calibration; group size and trial conditions cannot be separated.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.14,1,.94))
    save(fig,directory,'01-alignment-circulation',partial)


def plot_thresholds(tables,directory,partial=False):
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    specs=[('eligible_frame_fraction','Frames with measurable C','Fraction of all tracked frames'),
           ('own_subset_circulation_median','Median C: each setting’s eligible frames','Median circulation C'),
           ('common_subset_circulation_median','Median C: same frames at all settings','Median circulation C'),
           ('baseline_circulation_on_selected_frames_median','Baseline C: frames selected by each setting','Median C, keeping the 0.5 BL/s definition')]
    handles=[]
    for stem,g in tables['thresholds'].groupby('trial',sort=False):
        g=g.sort_values('threshold_bl_s');fish=int(g.fish.iloc[0]);_,color,marker=point_style(stem,fish)
        peers=[t for t in TRIALS if t.split('__')[0]==stem.split('__')[0]]
        ls=('-', '--', ':')[peers.index(stem)]
        label=f'{fish} fish / {stem.split("__")[1]}'
        for ax,(key,title,ylabel) in zip(axes.flat,specs):
            ax.plot(g.threshold_bl_s,g[key],color=color,marker=marker,ls=ls,lw=1.4,ms=5,label=label)
            ax.set(title=title,xlabel='Minimum relative speed (body lengths / s)',ylabel=ylabel,ylim=(-.025,1.05))
            ax.set_xticks([.25,.5,1.]);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
        handles.append(Line2D([0],[0],color=color,marker=marker,ls=ls,label=label))
    fig.legend(handles=handles,loc='lower center',ncol=5,fontsize=8,bbox_to_anchor=(.5,.065))
    fig.suptitle('Circulation depends on which observations pass the speed threshold',fontsize=14)
    fig.text(.5,.005,'Common frames require finite C at all settings; eligible fish can still differ. Baseline panel isolates frame selection where baseline C exists.\nBaseline 0.25→0.5 is flat by construction, not evidence of robustness. Missing markers mean no eligible frames.\nThe 151-fish recording is a single trial with different camera/length calibration.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.17,1,.95))
    save(fig,directory,'02-circulation-thresholds',partial)


def line_with_breaks(table, column):
    """Keep actual times and insert NaNs at segment/frame gaps; retain metric NaNs."""
    times=table.time.to_numpy(dtype=float)/60
    values=table[column].to_numpy(dtype=float)
    cuts=np.flatnonzero((np.diff(table.frame.to_numpy()) != 1) | (np.diff(table.segment.to_numpy()) != 0))+1
    return np.insert(times,cuts,np.nan),np.insert(values,cuts,np.nan)


def plot_timelines(records,directory,partial=False):
    fig,axes=plt.subplots(5,2,figsize=(15,14),squeeze=False)
    for ax,r in zip(axes.flat,records):
        s=r['summary'];c=r['collective']
        for key,color,label in [('polarization','#0072B2','Alignment P'),('circulation','#D55E00','Circulation C')]:
            x,y=line_with_breaks(c,key);ax.plot(x,y,color=color,lw=.55,alpha=.85,label=label)
        ax.set(title=f'{s["fish"]} fish / {s["sequence"]} — C eligible in {s["circulation_eligible_frame_fraction"]:.1%} of frames',
               xlabel='Recorded time (minutes)',ylabel='Index',ylim=(-.03,1.03))
        ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    for ax in list(axes.flat)[len(records):]:ax.set_visible(False)
    axes.flat[0].legend(loc='lower left',fontsize=8,ncol=2)
    fig.suptitle('Within-trial school organization over recorded time',fontsize=16,y=.995)
    fig.text(.5,.005,'Every recorded group frame is shown; lines break at missing values, recording segments and frame gaps.\nC gaps include speed/eligibility exclusions and are not zero circulation. The 151-fish trial uses different camera/length calibration.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.98))
    save(fig,directory,'03-collective-timelines',partial)


def plot_chapters(tables,directory,partial=False):
    fig,axes=plt.subplots(2,3,figsize=(15,9))
    specs=[('speed_bl_s','Swimming speed','body lengths / s\n(fish-frame quantiles)'),
           ('curvature_times_L','Signed body bending','curvature × reference length\n(fish-frame quantiles)'),
           ('spread_bl','RMS group spread','body lengths\n(group-frame quantiles)'),
           ('nearest_neighbor_bl','Nearest-neighbor distance','body lengths\n(fish-frame quantiles)'),
           ('visible_fraction','Reconstructed visible fraction','fraction of other fish\n(covered fish-frame quantiles)')]
    for ax,(key,title,ylabel) in zip(axes.flat,specs):
        interval_points(ax,tables['trials'],key)
        group_axis(ax,ylabel,key=='visible_fraction');ax.set_title(title)
        if key=='curvature_times_L':ax.axhline(0,color='gray',lw=.8,ls=':')
    ax=axes.flat[-1]
    for r in tables['trials'].to_dict('records'):
        x,color,marker=point_style(r['trial'],r['fish'])
        ax.plot(x,r['reciprocal_edge_fraction'],marker=marker,color=color,ls='none',ms=6)
    group_axis(ax,'fraction of directed links with a reverse link\n(all covered frames; edge-weighted ratio)',True)
    ax.set_title('Reciprocal reconstructed visibility')
    fig.suptitle('Other measured features: one point per trial',fontsize=15)
    fig.text(.5,.005,'Whiskers are within-trial 5th–95th percentiles, not confidence intervals; reciprocity shows one aggregate ratio per trial.\nVisibility is geometrically reconstructed access, not attention or influence. *151 fish: single trial with different camera/length calibration.\nThe 151-fish curvature and visibility measurements are excluded from group-size claims.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.065,1,.95))
    save(fig,directory,'04-other-chapters',partial)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'reports/comparison')
    parser.add_argument('--allow-partial',action='store_true',help='Explicitly permit missing trials; figures will say partial')
    args=parser.parse_args(argv)
    try:
        records,missing=load_trials(args.root,args.allow_partial)
        tables=make_tables(records)
        tabledir=args.root/'tables';figdir=args.root/'figures'
        tabledir.mkdir(parents=True,exist_ok=True);figdir.mkdir(parents=True,exist_ok=True)
        for name,table in tables.items():table.to_csv(tabledir/(name+'.csv'),index=False)
        plt.rcParams.update({'font.size':10,'axes.titlesize':11,'svg.fonttype':'none'})
        partial=bool(missing)
        plot_alignment(tables,figdir,partial);plot_thresholds(tables,figdir,partial)
        plot_timelines(records,figdir,partial);plot_chapters(tables,figdir,partial)
        inputs={}
        for r in records:
            for name in ['summary.json','collective.csv']:
                path=args.root/'trials'/r['stem']/name
                inputs[str(path.relative_to(args.root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest={'trials':[r['stem'] for r in records],'missing_trials':missing,'complete':not missing,
                  'input_sha256':inputs,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'interval_definition':'Within-trial 5th–95th percentiles; not confidence intervals.',
                  'weighting':'Each trial plotted separately; no pooling across trials.',
                  'timeline':'Every group frame; breaks at metric NaNs, segment boundaries and frame gaps.'}
        (args.root/'plot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'Wrote four PNG/SVG figures and four numeric tables for {len(records)} trials to {args.root}')
    except (ValueError,KeyError,OSError) as exc:
        parser.error(str(exc))


if __name__=='__main__':main()
