"""Pairwise follow-up distinguishes selected time frames from fish composition."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec=importlib.util.spec_from_file_location('compare_threshold_pairs',Path(__file__).resolve().parents[1]/'scripts/compare_threshold_pairs.py')
pairs=importlib.util.module_from_spec(spec);spec.loader.exec_module(pairs)


def tables():
    low=pd.DataFrame({'frame':[1,2,4,5],'time':[.1,.2,.4,.5],'segment':[0,0,1,1],
                      'polarization':[.2,.5,np.nan,.9],'circulation':[.1,.2,.3,.4]})
    medium=low.copy();medium['circulation']=[np.nan,np.nan,.5,.9]
    high=low.copy();high['circulation']=np.nan
    return {.25:low,.5:medium,1.:high}


def test_pair_survives_empty_three_way_intersection_and_decomposes_medians():
    result=pairs.pair_rows('10-fish/example',10,tables())
    assert len(result)==3
    informative=result[0]
    assert informative['common_frames']==2
    assert informative['common_fraction']==.5
    assert informative['common_low_c_median']==pytest.approx(.35)
    assert informative['common_high_c_median']==pytest.approx(.7)
    assert informative['common_low_p_n']==1
    assert informative['common_low_p_median']==.9
    assert informative['low_own_c_median']==.25
    assert informative['low_c_on_high_frames_median']==pytest.approx(.35)
    assert informative['frame_selection_median_shift']==pytest.approx(.1)
    assert informative['fish_composition_median_shift']==pytest.approx(.35)
    assert informative['total_own_median_shift']==pytest.approx(.45)
    for empty in result[1:]:
        assert empty['common_frames']==0
        assert empty['common_high_c_median'] is None
        assert empty['frame_selection_median_shift'] is None
        assert empty['common_low_p_n']==0


@pytest.mark.parametrize('fault,error',[
    ('order','differ in frame'),('nonmonotone','higher-threshold eligibility'),
    ('heading','polarization changed'),('infinite','invalid circulation'),
])
def test_invalid_cross_threshold_handoffs_are_rejected(fault,error):
    data=tables()
    if fault=='order':data[.5]=data[.5].iloc[::-1]
    if fault=='nonmonotone':
        data[.25].loc[0,'circulation']=np.nan
        data[.5].loc[0,'circulation']=.4
    if fault=='heading':data[.5].loc[0,'polarization']=.4
    if fault=='infinite':data[.5].loc[0,'circulation']=np.inf
    with pytest.raises(ValueError,match=error):pairs.pair_rows('test',10,data)


def test_completion_guard_and_hash_manifest(tmp_path):
    stem='10-fish__synthetic';folder=tmp_path/'trials'/stem
    (folder/'tables').mkdir(parents=True)
    data=tables();threshold_summary=[];output_hashes={}
    for threshold,table in data.items():
        path=folder/'tables'/f'collective-threshold-{threshold:g}.csv';table.to_csv(path,index=False)
        output_hashes[str(path.relative_to(folder))]=pairs.digest(path)
        q=pairs.quantiles(table.circulation,'c')
        threshold_summary.append({'threshold_bl_s':threshold,'circulation':{
            'n':q['c_n'],'0.05':q['c_p05'],'0.5':q['c_median'],'0.95':q['c_p95']}})
    summary={'trial':'10-fish/synthetic','fish':10,'quality':{'frames':4},'threshold_sensitivity':threshold_summary}
    (folder/'summary.json').write_text(json.dumps(summary))
    output_hashes['summary.json']=pairs.digest(folder/'summary.json')
    (folder/'provenance.json').write_text(json.dumps({'output_hashes':output_hashes}))
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'trials':[stem,'30-fish__missing'],'low_speed_sensitivity_bl_s':[.25,.5,1.]}))
    with pytest.raises(ValueError,match='Missing completed trials'):pairs.run(tmp_path,config)
    assert not (tmp_path/'tables').exists()
    result,manifest=pairs.run(tmp_path,config,allow_partial=True)
    assert len(result)==3
    assert manifest['cohort_complete'] is False
    assert manifest['missing_trials']==['30-fish__missing']
    assert len(manifest['input_hashes'])==5
    assert len(manifest['source_hashes'])==2
    assert manifest['output_hashes']['threshold-pairs.csv']==pairs.digest(tmp_path/'tables/threshold-pairs.csv')
    assert 'Exploratory' in manifest['analysis_status']
    changed=folder/'tables/collective-threshold-0.5.csv'
    changed.write_text(changed.read_text()+'\n')
    with pytest.raises(ValueError,match='output hash mismatch'):pairs.run(tmp_path,config,allow_partial=True)
