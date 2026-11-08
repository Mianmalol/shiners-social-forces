"""Offline checks for numerical handoff and truthful plotting of missing frames."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('plot_comparison',Path(__file__).resolve().parents[1]/'scripts/plot_comparison.py')
plot=importlib.util.module_from_spec(spec);spec.loader.exec_module(plot)


def q(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return {'n':len(a),**{str(p):float(np.quantile(a,p)) if len(a) else None for p in [.05,.5,.95]}}


def fixture(stem=plot.TRIALS[0]):
    n=int(stem.split('-fish')[0]);n=151 if n==150 else n
    c=pd.DataFrame({'frame':[1,2,3,5,6,7],'time':[1,2,3,5,6,7],
                    'segment':[0,0,0,1,1,1],'polarization':[.8,.9,np.nan,.6,.7,.8],
                    'circulation':[np.nan,.2,.3,np.nan,.6,.9],
                    'eligible_fraction':[np.nan,.8,.9,.6,.9,1.],
                    'polarization_valid_fish':[.8,.9,.4,.6,.7,.8]})
    cq=q(c.circulation);pq=q(c.polarization)
    degree_count=[0]*n;degree_count[1]=n*3;degree_count[2]=n*3
    summary={'trial':stem.replace('__','/'),'group':stem.split('__')[0],
             'sequence':stem.split('__')[1],'fish':n,'length_scale_px':40.,
             'quality':{'frames':6,'duration_s':6.,'segment_count':2},
             **{key:q([1,2,3]) for key in plot.METRICS},
             'polarization':pq,'circulation':cq,'circulation_eligible_frame_fraction':4/6,
             'joint_eligible_frame_fraction':3/6,
             'threshold_sensitivity':[{'threshold_bl_s':t,'circulation':cq,
                'circulation_eligible_frame_fraction':4/6} for t in [.25,.5,1.]],
             'threshold_common_eligible':{'common_frames':3,'common_fraction':.5,
                'settings':[{'threshold_bl_s':t,'circulation':q([.2,.6,.9])} for t in [.25,.5,1.]]},
             'threshold_circulation_common_eligible':{'common_frames':4,'common_fraction':4/6,
                'settings':[{'threshold_bl_s':t,'circulation':cq} for t in [.25,.5,1.]]},
             'threshold_frame_selection':{'baseline_threshold_bl_s':.5,
                'settings':[{'threshold_frame_set_bl_s':t,'candidate_frames':4,'baseline_valid_frames':4,
                             'baseline_undefined_frames':0,'baseline_circulation':cq} for t in [.25,.5,1.]]},
             'leave_one_out_threshold_sensitivity':{'effective_all_mean_cutoff_bl_s':.5*(n-1)/n,
                'other_fish_cutoff_bl_s':.5,'circulation':cq,'polarization':pq,
                'circulation_eligible_frame_fraction':4/6},
             'scale_sensitivity_151':None,
             'network':{'fish':n,'tracked_frame_count':6,'covered_frame_count':6,
                'observer_frame_count':6*n,'visible_fraction_mean':1.5/(n-1),
                'reciprocal_edge_fraction':.8,
                'degree_histogram':{'degree':list(range(n)),'count':degree_count}}}
    return {'stem':stem,'summary':summary,'collective':c}


class PlotComparisonTests(unittest.TestCase):
    def test_counts_quantiles_and_coverage_must_match(self):
        r=fixture();plot.validate_trial(r['stem'],r['summary'],r['collective'])
        for key,value in [('circulation_eligible_frame_fraction',1),('joint_eligible_frame_fraction',1)]:
            s=copy.deepcopy(r['summary']);s[key]=value
            with self.assertRaisesRegex(ValueError,'coverage mismatch'):
                plot.validate_trial(r['stem'],s,r['collective'])
        s=copy.deepcopy(r['summary']);s['polarization']['0.5']=.5
        with self.assertRaises(ValueError):plot.validate_trial(r['stem'],s,r['collective'])
        s=copy.deepcopy(r['summary']);s['network']['degree_histogram']['count'][1]-=1
        with self.assertRaisesRegex(ValueError,'denominator mismatch'):
            plot.validate_trial(r['stem'],s,r['collective'])

    def test_histogram_quantiles_match_numpy_interpolation(self):
        net={'fish':10,'degree_histogram':{'degree':[0,1,2,3,4],'count':[0,2,0,3,1]}}
        result=plot.degree_quantiles(net)
        expected=np.quantile(np.repeat([0,1,2,3,4],[0,2,0,3,1])/9,[.05,.5,.95])
        np.testing.assert_allclose([result[k] for k in plot.QKEYS],expected)
        self.assertEqual(result['n'],6)

    def test_threshold_nesting_identities_are_checked(self):
        r=fixture();s=r['summary']
        # Count checks alone would not catch this plausible changed median.
        s['threshold_frame_selection']['settings'][0]['baseline_circulation']=q([.2,.4,.6,.9])
        with self.assertRaisesRegex(ValueError,'baseline 0.25/0.5 identity'):
            plot.validate_trial(r['stem'],s,r['collective'])
        r=fixture();s=r['summary'];selection=s['threshold_frame_selection']['settings'][-1]
        selection.update(baseline_undefined_frames=1,baseline_valid_frames=3,baseline_circulation=q([.2,.6,.9]))
        with self.assertRaisesRegex(ValueError,'nested baseline undefined-frame identity'):
            plot.validate_trial(r['stem'],s,r['collective'])
        r=fixture();s=r['summary'];common=s['threshold_circulation_common_eligible']
        common.update(common_frames=3,common_fraction=.5)
        for item in common['settings']:item['circulation']=q([.2,.6,.9])
        with self.assertRaisesRegex(ValueError,'common circulation set'):
            plot.validate_trial(r['stem'],s,r['collective'])

    def test_velocity_denominator_and_added_heading_frames_are_exported(self):
        r=fixture();tables=plot.make_tables([r]);row=tables['trials'].iloc[0]
        self.assertEqual(row.velocity_defined_frames,5)
        self.assertAlmostEqual(row.velocity_defined_frame_fraction,5/6)
        self.assertAlmostEqual(row.circulation_eligible_fraction_of_velocity_defined_frames,4/5)
        self.assertEqual(row.polarization_valid_fish_added_frames,1)
        self.assertEqual(row.polarization_valid_fish_on_added_frames_n,1)
        self.assertEqual(row.polarization_valid_fish_on_added_frames_median,.4)
        r['collective'].loc[2,'polarization_valid_fish']=np.nan
        row=plot.make_tables([r])['trials'].iloc[0]
        self.assertEqual(row.polarization_valid_fish_added_frames,0)
        self.assertIsNone(row.polarization_valid_fish_on_added_frames_median)

    def test_timeline_breaks_at_segments_gaps_and_metric_nans(self):
        r=fixture();x,y=plot.line_with_breaks(r['collective'],'polarization')
        self.assertTrue(np.isnan(x[3]));self.assertTrue(np.isnan(y[3]))
        self.assertTrue(np.isnan(y[2]))
        np.testing.assert_allclose(x[np.isfinite(x)]*60,r['collective'].time)
        # Even consecutive frame numbers must break at a segment boundary.
        c=r['collective'].copy();c['frame']=[1,2,3,4,5,6]
        self.assertTrue(np.isnan(plot.line_with_breaks(c,'polarization')[0][3]))

    def test_missing_trials_require_explicit_partial_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r=fixture();dest=root/'trials'/r['stem'];dest.mkdir(parents=True)
            (dest/'summary.json').write_text(json.dumps(r['summary']))
            r['collective'].to_csv(dest/'collective.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Comparison incomplete'):plot.load_trials(root)
            records,missing=plot.load_trials(root,True)
            self.assertEqual(len(records),1);self.assertEqual(len(missing),9)

    def test_tables_and_all_four_figures_with_ten_synthetic_trials(self):
        records=[fixture(stem) for stem in plot.TRIALS]
        tables=plot.make_tables(records)
        self.assertEqual(len(tables['trials']),10)
        self.assertEqual(len(tables['thresholds']),30)
        self.assertEqual(tables['trials'].iloc[-1].fish,151)
        self.assertAlmostEqual(tables['trials'].iloc[0].visible_fraction_median,1.5/9)
        self.assertTrue((tables['thresholds'].common_subset_circulation_n==4).all())
        self.assertTrue((tables['thresholds'].joint_common_subset_circulation_n==3).all())
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)
            plot.plot_alignment(tables,directory)
            plot.plot_thresholds(tables,directory)
            plot.plot_timelines(records,directory)
            plot.plot_chapters(tables,directory)
            self.assertEqual(len(list(directory.glob('*.png'))),4)
            self.assertEqual(len(list(directory.glob('*.svg'))),4)
            self.assertTrue(all(p.stat().st_size>1000 for p in directory.iterdir()))

    def test_geometry_counts_and_complete_nested_sensitivities_are_exported(self):
        r=fixture();s=r['summary']
        s['quality'].update(nonpositive_length_rows=2,nonpositive_length_frame_count=1)
        s['nonpositive_length_frame_exclusion_sensitivity']={
            'removed_frames':[3],'recomputed':{'circulation':q([.2,.6])}}
        s['network']['nonpositive_length_frame_exclusion_sensitivity']={
            'excluded_frame_count':1,'visible_fraction_mean':.2}
        s['network']['matched_duration']={'frames':4,'visible_fraction_mean':.3}
        tables=plot.make_tables([r]);row=tables['trials'].iloc[0]
        self.assertEqual(row.nonpositive_length_rows,2)
        self.assertEqual(row.nonpositive_length_frame_count,1)
        diagnostics=tables['sensitivity'].set_index(['family','parameter'])['value']
        self.assertEqual(diagnostics.loc[('nonpositive_length_frame_exclusion_sensitivity','removed_frames.0')],3)
        self.assertEqual(diagnostics.loc[('nonpositive_length_frame_exclusion_sensitivity','recomputed.circulation.n')],2)
        self.assertEqual(diagnostics.loc[('network_nonpositive_length_frame_exclusion_sensitivity','excluded_frame_count')],1)
        self.assertEqual(diagnostics.loc[('network_matched_duration','visible_fraction_mean')],.3)
        old=plot.make_tables([fixture()])['trials'].iloc[0]
        self.assertIsNone(old.nonpositive_length_rows)


if __name__=='__main__':unittest.main()
