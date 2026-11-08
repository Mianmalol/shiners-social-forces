# Session account: from dataset audit to ten-trial comparison

November 7, 2026. This publication packages the descriptive analysis, its evidence,
and a reproducible workflow. It does not fit a social-force model or establish
leadership, influence, or causation. Start with the [comparison report](../reports/comparison/README.md)
for the plots and the [workflow status](workflow/status.md) for review evidence.

## What we did

We first separated three scientific tasks: **describe behavior → map candidate
responses → test what information predicts those responses**. We completed the
requested descriptive measurements in five chapters: individual motion, body
posture, school organization, spatial relationships, and reconstructed visual
access. Broader extensions in the original plan, including local alignment and
interaction persistence, remain future work.

We audited one 10-fish recording, defined the measurements, checked them on small
synthetic examples, and produced a five-chapter pilot with selected video overlays.
We then processed all ten track tables and all supplied visual-network rows under
the same analysis code and configuration: **10,827,539 fish-frame observations,
266,688,111 directed network rows, and 239,246 observed group frames**. There are
three recordings each at 10, 30 and 70 fish, and one at 151 fish. These row counts
are measurement volume, not independent experimental replication. No additional
video inspection was performed for the ten-trial extension.

An initial comparison run stopped when it encountered nonpositive body lengths.
We found 22 such observations across 14 trial-frames, defined explicit handling,
then regenerated every retained trial. Positive lengths define the reference scale;
curvature is undefined on collapsed poses. We retained finite positions and headings
as recorded measurements and separately removed affected frames, recomputing motion
without crossing the new gaps. The largest resulting median changes were 0.000110
for alignment and 0.0000731 for circulation. This checks those anomalies, not all
possible tracking errors. The stopped run remains an ignored local cache.

## How we treated the data

- **Continuity and scale:** derivatives never cross recording joins or gaps. Motion
  uses an 11-frame cubic smoothing filter, with 7- and 15-frame sensitivities and
  boundary exclusions. Distances and speeds use each trial's median positive body
  length, not centimeters. Flagged heading jumps are masked, not automatically repaired.
- **Definitions:** alignment P measures agreement of raw body headings on a 0–1
  scale. The school center is the mean fish position. Circulation C measures
  agreement of tangential movement around that moving center, after subtracting
  the school's mean velocity. It is neither angular speed nor a validated milling
  classifier. Posture comes from the recorded midline; visual links describe
  ray-cast geometric access, not attention or influence.
- **Comparisons:** each trial supplies an estimate. Plotted 5th–95th percentiles
  describe within-trial variation, not confidence intervals. We tested heading
  exclusions, duration matching, smoothing, circulation cutoffs, affected-frame
  removal, and an explicitly illustrative length-scale scenario for the 151-fish
  recording. All ten trials have now been explored; none is an untouched confirmatory set.

## What we learned

| Result | Supported interpretation |
| --- | --- |
| Median alignment ranges: 0.894–0.943 at N=10; 0.809–0.827 at N=30; 0.509–0.694 at N=70 | Every smaller-group trial median exceeds every trial median in the next group. This ordering survives heading, duration and flagged-geometry checks. It describes these recordings, not a causal group-size effect. |
| Circulation ranges overlap between group sizes | No strict monotone circulation ordering. High values in two 70-fish trials describe a strongly selected subset of frames. |
| All three 70-fish trials swim more slowly in median than the 10- and 30-fish trials | Activity and alignment co-vary here; speed-stratified alignment remains untested. |
| Typical nearest-neighbor spacing is around one body length | A larger school footprint does not imply proportionally wider local spacing. |
| Visible-neighbor count rises across 10→30→70, but visible fraction and reciprocity fall | This is a geometric network pattern; it does not identify information use. |

The single 151-fish recording has median P=0.641 and C=0.484, both within the
70-fish ranges. It therefore does not extend a simple monotone trend. Its different
camera and documented body-length discrepancy also limit comparison; its posture
and visibility measurements are excluded from group-size claims.

## Why only 6–11% of frames qualify for circulation

The chosen reporting rule first requires finite positions and velocities for all
fish. At least 80% must then move at least 0.5 reference body lengths/s relative
to the school and lie more than 10⁻⁶ body lengths from its center, so their radial
direction is defined. For 70 fish, that means at least **56 qualifying fish in
the same frame**. Both trials have a median of only 41 qualifying fish.

| Trial | All observed frames | Velocity undefined | Circulation eligible |
| --- | ---: | ---: | ---: |
| 70-fish/0107 | 24,578 | 84 | 2,598 (10.57%) |
| 70-fish/0124 | 24,533 | 84 | 1,438 (5.86%) |

Thus, nearly all rejected frames have defined velocities but fail the eligibility
rule. Lowering only the speed cutoff to 0.25 raises coverage to 74.6% and 79.1%; at
1.0 neither trial has any qualifying frames. The [eligibility plot](../reports/comparison/figures/05-circulation-eligibility.png)
shows this directly. Low coverage is not missing tracking and is not the fraction
of time spent circling. A fish can swim rapidly with the school while barely moving
relative to it. Slow coordinated rotation can fail the cutoff; fast radial movement
can pass and still have low C. The cutoff is an analysis choice, not a validated
biological boundary. Comparing cutoffs on shared frames shows that much of the
change in median C comes from selecting different moments.

## Verification, storage, and next steps

OpenAI coordinated, implemented, ran the analysis, and inspected the figures.
Claude Code independently reviewed frozen text snapshots of methods, code and
results. Its corrections changed both measurement safeguards and narrative claims;
the corrected comparison received PASS. The [publication review](workflow/reviews/publication/review.md)
and [coordinator disposition](workflow/reviews/publication/adjudication.md) record the
additional review of this package. Claude's tool-free review does not execute code
or inspect images. Independent computational reproduction remains pending.

Coordinator QA checks input/source/output hashes, identical analysis sources across
trials, exact pilot parity, and 50 independently recalculated alignment values
(largest difference 2.22×10⁻¹⁶). The [comparison test log](../reports/test-results-comparison.txt)
records the original 131 tests and 8 subtests; the [publication test log](../reports/test-results-publication.txt)
includes the added eligibility tests. GitHub CI runs the synthetic/unit suite on
Python 3.11 and 3.13 without raw-data downloads or Claude credentials.

Git contains code, the locked environment, methods, compact results, figures, and
review records. Complete original archives remain in the existing
[dataset release](https://github.com/Mianmalol/shiners-social-forces/releases/tag/data-2026-11-05).
Local raw data and large regenerable comparison tables are ignored. Trial downloads
verify ZIP-member CRC and record extracted SHA256; they do not independently verify
whole-archive SHA256. Saved provenance retains original paths. Use the
[fresh-output reproduction commands](../README.md#compare-all-ten-trials), rather than
trying to resume retained outputs whose large intermediate tables are omitted.

Next: inspect selected high-C and heading-anomaly intervals against video, compare
local with global alignment, and arrange independent reproduction. Response maps,
leadership, pairwise-versus-group effects and predictive force models come afterward.
This descriptive publication is authorized for GitHub; publication does not close
those scientific gates.
