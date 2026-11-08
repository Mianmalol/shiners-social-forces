"""Exploratory pairwise threshold comparisons from frozen per-trial CSV outputs.

This follow-up was introduced after a trial had no frames eligible at 1 BL/s,
which made its three-way threshold intersection empty. It does not rerun or alter
primary measurements. Each pair is reported, including empty intersections.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            result.update(block)
    return result.hexdigest()


def quantiles(values, prefix):
    values=np.asarray(values,dtype=float)
    values=values[np.isfinite(values)]
    result={prefix+'_n':int(len(values))}
    for q,label in [(.05,'p05'),(.5,'median'),(.95,'p95')]:
        result[prefix+'_'+label]=float(np.quantile(values,q)) if len(values) else None
    return result


def pair_rows(trial, fish, tables):
    """Compare C-valid frame sets; P may be undefined and has its own count."""
    thresholds=sorted(tables)
    if len(thresholds)<2:raise ValueError('At least two thresholds are required')
    reference=tables[thresholds[0]]
    required={'frame','time','segment','circulation','polarization'}
    for threshold,table in tables.items():
        if not required.issubset(table):raise ValueError(f'{trial}: incomplete threshold table')
        if len(table)==0:raise ValueError(f'{trial}: empty frame table')
        for col in ['frame','time','segment']:
            if not np.isfinite(table[col]).all():raise ValueError(f'{trial}: nonfinite {col}')
            if not np.array_equal(table[col],reference[col]):
                raise ValueError(f'{trial}: threshold tables differ in {col}')
        if table.frame.duplicated().any() or (np.diff(table.frame)<=0).any():
            raise ValueError(f'{trial}: repeated or unordered frames')
        for col in ['circulation','polarization']:
            values=table[col].to_numpy(dtype=float)
            if np.isinf(values).any() or (values < -1e-10).any() or (values > 1+1e-10).any():
                raise ValueError(f'{trial}: invalid {col}')
        if not np.allclose(table.polarization,reference.polarization,equal_nan=True,atol=1e-12,rtol=0):
            raise ValueError(f'{trial}: polarization changed across speed thresholds')
    result=[]
    for low,high in itertools.combinations(thresholds,2):
        left,right=tables[low],tables[high]
        low_valid=np.isfinite(left.circulation.to_numpy())
        high_valid=np.isfinite(right.circulation.to_numpy())
        if (high_valid&~low_valid).any():
            raise ValueError(f'{trial}: higher-threshold eligibility is not a subset')
        common=low_valid&high_valid
        row={
            'trial':trial,'fish':int(fish),'low_threshold_bl_s':float(low),
            'high_threshold_bl_s':float(high),'source_frames':int(len(reference)),
            'low_eligible_frames':int(low_valid.sum()),'low_eligible_fraction':float(low_valid.mean()),
            'high_eligible_frames':int(high_valid.sum()),'high_eligible_fraction':float(high_valid.mean()),
            'common_frames':int(common.sum()),'common_fraction':float(common.mean()),
            **quantiles(left.loc[common,'circulation'],'common_low_c'),
            **quantiles(right.loc[common,'circulation'],'common_high_c'),
            **quantiles(left.loc[common,'polarization'],'common_low_p'),
            **quantiles(right.loc[common,'polarization'],'common_high_p'),
            **quantiles(left.loc[low_valid,'circulation'],'low_own_c'),
            **quantiles(right.loc[high_valid,'circulation'],'high_own_c'),
            **quantiles(left.loc[high_valid,'circulation'],'low_c_on_high_frames'),
            **quantiles(right.loc[common,'circulation'].to_numpy()-left.loc[common,'circulation'].to_numpy(),'common_paired_c_difference'),
        }
        row['frame_selection_median_shift']=(row['low_c_on_high_frames_median']-row['low_own_c_median']) if common.any() else None
        row['fish_composition_median_shift']=(row['common_high_c_median']-row['common_low_c_median']) if common.any() else None
        row['total_own_median_shift']=(row['high_own_c_median']-row['low_own_c_median']) if common.any() else None
        result.append(row)
    return result


def run(root, config, allow_partial=False):
    cfg=json.loads(config.read_text())
    trials=cfg['trials'];thresholds=sorted(cfg['low_speed_sensitivity_bl_s'])
    if len(trials)!=len(set(trials)) or not trials:raise ValueError('Invalid trial list')
    if len(thresholds)!=3 or len(set(thresholds))!=3 or any(not np.isfinite(x) or x<=0 for x in thresholds):
        raise ValueError('Expected three distinct positive finite thresholds')
    if any(Path(t).name!=t for t in trials):raise ValueError('Trial identifiers must be directory names')
    missing=[];complete=[]
    for trial in trials:
        folder=root/'trials'/trial
        inputs=[folder/'summary.json',folder/'provenance.json']+[
            folder/'tables'/f'collective-threshold-{threshold:g}.csv' for threshold in thresholds]
        if any(not p.is_file() for p in inputs):missing.append(trial)
        else:complete.append((trial,folder,inputs))
    if missing and not allow_partial:raise ValueError('Missing completed trials: '+', '.join(missing))
    if not complete:raise ValueError('No complete threshold outputs available')
    input_hashes={};rows=[]
    for stem,folder,inputs in complete:
        for path in inputs:input_hashes[str(path.resolve())]=digest(path)
        summary=json.loads((folder/'summary.json').read_text())
        provenance=json.loads((folder/'provenance.json').read_text())
        # Detect accidental changes to the frozen completed outputs before deriving results.
        for path in [inputs[0],*inputs[2:]]:
            expected=provenance['output_hashes'].get(str(path.relative_to(folder)))
            if expected is None or expected!=input_hashes[str(path.resolve())]:
                raise ValueError(f'{stem}: completed output hash mismatch for {path.name}')
        if summary['trial']!=stem.replace('__','/') or summary['fish']<2:
            raise ValueError(f'{stem}: summary identity mismatch')
        tables={threshold:pd.read_csv(folder/'tables'/f'collective-threshold-{threshold:g}.csv') for threshold in thresholds}
        expected={float(item['threshold_bl_s']):item['circulation'] for item in summary['threshold_sensitivity']}
        if set(expected)!=set(thresholds):raise ValueError(f'{stem}: threshold settings mismatch')
        for threshold,table in tables.items():
            if len(table)!=summary['quality']['frames']:raise ValueError(f'{stem}: source frame count mismatch')
            actual=quantiles(table.circulation,'c');known=expected[threshold]
            if actual['c_n']!=known['n']:raise ValueError(f'{stem}: finite C count mismatch')
            if known['n'] and not np.allclose([actual['c_'+k] for k in ['p05','median','p95']],
                                             [known[k] for k in ['0.05','0.5','0.95']],atol=1e-10,rtol=0):
                raise ValueError(f'{stem}: source C quantile mismatch')
        rows.extend(pair_rows(summary['trial'],summary['fish'],tables))
    output=root/'tables';output.mkdir(parents=True,exist_ok=True)
    path=output/'threshold-pairs.csv';temporary=path.with_suffix('.csv.tmp')
    pd.DataFrame(rows).to_csv(temporary,index=False);temporary.replace(path)
    manifest={
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'analysis_status':'Exploratory follow-up after an empty three-threshold intersection was observed in 70-fish/0107; not a prespecified primary analysis.',
        'cohort_complete':not missing,'included_trials':[t for t,_,_ in complete],'missing_trials':missing,
        'thresholds_bl_s':thresholds,'pair_rows':len(rows),
        'frame_set_definition':'Pairwise intersection of finite circulation frames, without requiring finite P. P quantiles omit heading-masked frames and report their own denominator. Higher-threshold eligibility must be a subset of lower-threshold eligibility.',
        'frame_selection_definition':'Compare low_own_c with low_c_on_high_frames: identical low-threshold C calculation evaluated on different frame sets.',
        'fish_composition_definition':'Compare common_low_c with common_high_c: same high-threshold-eligible frames, potentially different included fish.',
        'shift_definition':'Median shifts are differences between medians, not causal effects or statistical tests. common_paired_c_difference separately gives quantiles of paired per-frame differences. Empty sets produce null/blank quantiles, never zeros.',
        'limitations':'Frames are temporally dependent; pairwise common sets are selected higher-relative-motion frames and are not representative samples. No null calibration, smoothing changes, or raw-data recomputation.',
        'source_hashes':{str(Path(__file__).resolve()):digest(Path(__file__)),str(config.resolve()):digest(config)},
        'input_hashes':input_hashes,'output_hashes':{'threshold-pairs.csv':digest(path)},
    }
    manifest_path=output/'threshold-pairs-manifest.json'
    temporary=manifest_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n');temporary.replace(manifest_path)
    return pd.DataFrame(rows),manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'reports/comparison')
    parser.add_argument('--config',type=Path,default=ROOT/'configs/comparison.json')
    parser.add_argument('--allow-partial',action='store_true',help='Explicitly permit an incomplete exploratory table')
    args=parser.parse_args()
    rows,manifest=run(args.root,args.config,args.allow_partial)
    print(f"Saved {len(rows)} pairs from {len(manifest['included_trials'])} trials; complete={manifest['cohort_complete']}")


if __name__=='__main__':main()
