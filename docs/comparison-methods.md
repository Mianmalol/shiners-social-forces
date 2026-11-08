# All-trial descriptive comparison

User authorized applying the same analysis to the other trials and larger groups, with independent Claude review. No model fitting, causal inference or publication is included. OpenAI implements and executes; Claude receives exact source/result snapshots for independent static review, not computational reproduction.

## Sample and data

Ten trials: three each at N=10,30,70, one at N=151 (source directory 150-fish). Download tracks and visual-network tables only, ~7.5 GB total; reuse pilot tables. No new video inspection is claimed. Check every trial rather than extending the 0066 quality verdict. Audit projected measurement columns explicitly; do not claim validation of unused pose or metadata columns. Stream network rows in bounded batches with an exact adjacency bitset for completeness, duplicate detection, reciprocity and zero-degree accounting.

Analyze one trial per process to bound memory. Keep raw inputs immutable in ignored data/. Use actual fish IDs, frame counts and segments, not assumptions of seven segments or N=150. Preserve gaps. The same primary methods as docs/methods.md apply: cubic SG window11, half-window+1 edge exclusion, heading jump support exclusion, body-frame coordinates, 7-point midpoint curvature, raw spacing, and centroid-relative circulation with 0.5 reference body lengths/s and >=80% eligible fish. The integer eligibility count is effectively ceil(.8*N), so record eligible fractions.

The first execution stopped at nonpositive body lengths in trial0126. Follow-up inspection found isolated zero-length, collapsed-pose rows in additional trials, despite finite recorded positions and headings. Count and retain these source anomalies explicitly. Use the median of strictly positive lengths for L; undefined collapsed-pose curvature is excluded, never set to zero. The source positions and headings remain usable recorded measurements, without claiming that finite values prove tracking correctness. Add a P/C sensitivity excluding affected temporal smoothing neighborhoods and a visual-network sensitivity excluding frames containing a nonpositive length. Preserve primary raw-network summaries and disclose that networks at these frames were constructed from suspect geometry. Save the stopped initial run separately and regenerate all final trials under one common source snapshot.

## Comparison units and replication

Use each trial's fixed median body_length as descriptive length scale. Report the scale in pixels and retain pixel-unit metadata. This controls descriptive scale but is not a physical calibration. Mark the N=151 trial as a separate-camera, single-replicate observation: source reports visible bodies about15% longer than stored length. Run L*1.15 sensitivity for its circulation and speed summaries; label a scenario, not a calibrated correction.

One point in the main group-size plots is ONE TRIAL. Do not pool millions of fish-frames as independent replicates or report frame-based confidence intervals as between-trial uncertainty. Show all three smaller-group trials, and isolate N=151 visually. Numeric group summaries, if supplied, weight trials equally and give observed ranges; no group-size causal claim or hypothesis significance test.

Before examining cross-trial results, define a strict descriptive ordering: a monotone group-size pattern across N=10,30,70 requires every trial median in each adjacent group to lie on the same side of every median in the next group, with no overlapping ranges of trial medians. Otherwise describe the ranges as overlapping or the ordering as inconsistent. This criterion is descriptive, not a significance test. The single N=151 observation can only be consistent with an ordering; it cannot establish one. A claim of robustness must also name the sensitivity checks under which the ordering persists.

## Alignment and circulation

For P retain all eligible heading frames. Report median, 5th/95th percentiles, n and fraction. P is length of mean unit-heading vector, not percent aligned. P has finite-N behavior even under random directions; save the approximate iid-uniform reference sqrt(pi/(4*n)) per frame, without subtraction, division, or significance interpretation. Whole-frame exclusion can vary with N: save reasons, raw unmasked P, and a sensitivity excluding only suspect fish with at least80% of headings retained. Report n retained and summaries on each method's own frames and the common primary frame set. The common-set comparison is algebraically identical when all headings are valid; the own-frame comparison tests expanded time coverage.

For C use identical definition across groups: absolute mean normalized cross product of centroid-relative position and centroid-relative velocity. Save signed C, eligible count/fraction, and the iid-direction reference 1/sqrt(pi*n_eligible) ONLY as an illustrative reference. Because subtracting a common velocity imposes dependence, it is not a calibrated null. Do not subtract/divide by it to manufacture a corrected C. No validated milling-state classifier exists here.

For each trial, report thresholds .25,.5,1.0 BL/s with their separate eligibility fractions, C distributions and P conditional on C eligibility. Also compare thresholds on the intersection of eligible frames, exactly the1.0-eligible high-relative-motion subset for these nested cutoffs: with identical vectors, changes can still reflect which individual fish qualify, even when frames are held fixed. Separately summarize the fixed0.5-threshold C on each threshold's frame set, restricting to frames where that baseline C is defined. For the0.25 set this overlaps the0.5 set, since the primary statistic is undefined on additional slower frames. Report smoothing windows7,11,15 and a matched eligible-frame comparison. Distinguish a change of selected observations from a change in measured behavior.

Own contribution sensitivity: v_i-vbar_all=(N-1)/N*(v_i-vbar_other). Directions are unchanged by leave-one-out averaging. Compute a secondary threshold .5*(N-1)/N in all-mean coordinates, equivalent to applying .5 against the other fish. This is a diagnostic of cutoff selection, not a necessary correction to the legitimate moving-centroid frame.

## Five descriptive chapters

Retain speed/turning/slip summaries, midpoint-curvature distributions and fitting-neighborhood sensitivity, P/C/spread time series, nearest-neighbor spacing and body-frame density, and reconstructed degree/visible fraction/reciprocity/angular-size summaries. Keep separate denominators and state missing coverage, anomalies and partial metrics. Whole absent network frames remain unknown without separate coverage evidence. No persistence or response-law inference is added.

## Additional comparison sensitivities after Claude plan review

Use the first17,999 observed frames of each trial for a matched-record-count sensitivity. This is approximately matched duration under the source-declared29.97fps time base; gaps and joins remain and this does not equate acclimation history. Preserve primary full-record estimates. Report P/C, other track summaries, and network degree/visible fraction/reciprocity on that prefix. Smaller trials have joins; N=151 is a single recording. The source declares29.97fps and time=frame/29.97; we have not independently checked the151-fish video's timing or camera orientation. Do not compare signed circulation chirality across cameras.

For N=151 apply the L*1.15 scenario to all L-normalized numerical summaries: speed, spread, nearest-neighbor distance divide by1.15; curvature-times-L multiplies by1.15; a fixed physical density per L-squared multiplies by1.15^2, with bin coordinates correspondingly rescaled. Recompute cutoff-dependent circulation and heading-versus-motion eligibility and the threshold sweep. This is an algebraic sensitivity scenario, not a geometric correction. Midline truncation versus scaling is unresolved, so midpoint curvature is not anatomically calibrated between cameras; the stored network was constructed from those outlines and cannot be repaired by a unit conversion. Exclude N=151 from group-size claims about curvature and visibility.

## Outputs and required comparison review

reports/comparison/trials/<trial>/ contains summary.json, collective.csv, compact histogram/sensitivity tables and run provenance. summary.json written last signals a complete trial. Root comparison figures and report derive solely from these saved tables, with each input hash recorded.

Claude receives the methods, all-trial source changes, test evidence, full per-trial comparison/sensitivity tables, and draft narrative. It must scrutinize finite-N effects, selection bias, camera/scale confounding, replication, denominators, sign conventions and any pattern claimed to hold across trials. Reviewer must list checks not executed. Material findings require explicit disposition; no automatic PASS based only on process success.
