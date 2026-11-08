# Validation assessment

**Share with noted caveats.** All ten trials are analyzed and the descriptive comparison has passed coordinator computational QA and Claude's independent static review after narrative corrections.

## Evidence

- [Machine-readable QA](validation.json): all recorded hashes match; source/configuration agree across all ten runs; metadata and network histograms reconcile. Python/package versions also match across runs.
- Exact pilot parity: ten primary quantile dictionaries, visual-degree quantiles, mean degree and reciprocity match the retained 0066 pilot.
- Fifty sampled alignment values independently recalculated from raw headings agree within floating-point precision; maximum absolute difference 2.220446049250313e-16.
- [Test evidence](../test-results-comparison.txt): 131 tests and 8 subtests passed. No numerical source changed after this run.
- All four final figure sets visually inspected: clear units, trial-level markers, within-trial percentile ranges rather than confidence intervals, and explicit eligibility/151-fish caveats. Local report links checked.
- [Claude implementation review](../../docs/workflow/reviews/comparison-implementation/review.md), [results review](../../docs/workflow/reviews/comparison-results/review.md), and [final PASS](../../docs/workflow/reviews/comparison-results-fixes/review.md) are retained with exact supplied snapshots and coordinator dispositions.

## Required caveats

Trials are the descriptive comparison units; fish-frames are temporally and socially dependent. Raw P and C have finite-group behavior and no calibrated experimental null. Circulation summaries are conditional on eligibility, with particularly sparse coverage in 70-fish/0107 and 0124. The 151-fish recording is a single different-camera trial and does not continue the P ordering; its curvature and visibility are excluded from group-size claims. Rare collapsed-posture observations are disclosed and sensitivity-tested. Additional videos were not inspected, and finite tracked values do not prove biological correctness.

Claude did not execute code or inspect figures. Independent computational reproduction remains pending. This assessment supports the local descriptive report, not a causal model, behavioral-state classifier or independently reproduced scientific release.
