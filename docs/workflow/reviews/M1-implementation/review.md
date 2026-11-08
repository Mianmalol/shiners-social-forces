# Independent implementation review: pilot 0066 (static snapshot)

**Reviewer:** Claude (`claude-opus-5-5`), tool-free static review
**Verdict: CHANGES_REQUESTED.** The scope of the requested changes is narrow.

I found no arithmetic or code error that invalidates a reported number. The supplied counts are internally consistent with the code, and I worked through them below. One prior M0 disposition (heading flips) is only partially met, and the evidence supplied cannot rule out a heading defect that would affect polarization, slip and the body-frame map. Two presentation items also need fixes. All three are inexpensive and stay within the pilot scope.

---

## 1. What I did and did not do

**Did (reasoning only):**
- Traced the code paths for each metric.
- Derived the analytic test expectations by hand.
- Checked the sign conventions algebraically.
- Cross-checked the summary counts against the code's masking logic.

**Did not execute or inspect:**
- I ran no tests. `54 passed` is the coordinator's log, not my result.
- I did not run the pilot or recompute any number from the parquet files.
- I viewed no figures, including the video overlays, the occupancy map's "lower-density centre", and the midline examples.
- I did not see these tables: `speed-sensitivity.csv`, `curvature-sensitivity.csv`, `collective.csv`, `provenance.json`, `status.md`.
- I did not see `scripts/fetch_pilot.py` or the ZIP CRC provenance.
- I made no check of the video frame index against the track frame index beyond reading the code.

---

## 2. M0 findings: confirm or reject each disposition

| M0 finding | Disposition | Assessment |
|---|---|---|
| Heading flips | Flag adjacent jumps >π/2, mask SG support, exclude polarization frames, axis QA | **Partially confirmed; see F1.** The masking of the transition is correct. A sustained flipped interval is not detected. |
| Low-speed noise | 0.5 BL/s primary, 0.25/0.5/1.0 sensitivity, approximate noise diagnostic | **Confirmed.** The threshold is about 9× the illustrative per-component velocity scale (≈0.055 BL/s). The diagnostic is labelled non-calibrated. |
| Positive circulation bias | Signed value saved; iid reference labelled illustrative | **Confirmed.** For iid uniform directions, cross = sin Δ with variance ½. That gives E\|mean\| = √(2/π)·√(1/2n) = 1/√(πn), so the code matches. The figure and report both say "not significance". |
| Curvature anatomy | Geometric sign kept; anatomical relation explained | **Confirmed.** For heading +x, the head-to-tail tangent is −x. Clockwise rotation in y-down maps (−1,0)→(0,−1), which is fish-left. The centre of curvature therefore lies fish-left, so "positive ⇒ concave fish-left" is correct. The arc test sign also checks out: x′y″−y′x″ = R² > 0. |
| Float precision distance | Tolerance chosen by dtype; dtypes and error recorded | **Confirmed.** All columns are float64, the maximum error is 1.1e-13 px, and the tolerance is 1e-4. |
| Join-neighbour noise | Drop half+1 at both block ends | **Confirmed.** With `trim=6` and w=11, the first retained centre's window spans indices 1–11, so endpoint samples never enter. The real data has 7 blocks × 12 × 10 fish = 840 rows. 245,780 − 840 = 244,940, which equals speed *n*. |
| Centroid position source | SG positions for circulation, raw for spacing | **Confirmed** in the code. See minor note M2 on spread. |

---

## 3. Material findings

### F1: Heading-flip QA detects transitions, not flipped states

**Code:** `kinematics` in `src/shiners/metrics.py`.

The code flags only adjacent-sample steps above π/2. Suppose the tracker swaps head and tail at event A and swaps back at event B. Then the intervening frames carry a heading off by π. Those frames would still count as `heading_valid` and would feed into polarization, slip, and the spatial map rotation.

The axis-disagreement QA cannot catch this. If the pose keypoints swap along with ANGLE, `ANGLE − atan2(pose0−pose20)` stays near zero. The reported "0 rows > π/2" is therefore consistent with both of these explanations:
- (a) real fast turns, or
- (b) consistent head/tail swaps.

The reported counts fit "two transitions". There are 4 flagged rows, and 24 rows each are removed from turn rate and polarization. A single fish with flip-then-unflip would produce exactly this pattern.

Slip only weakly bounds the problem. The 95th percentile of |slip| is 0.27 rad, so flipped speed-eligible rows make up less than 5% of the total. That still leaves room for a non-trivial interval of reversed heading.

**Required fix (no new analysis scope):**
1. Report the fish ID, frame, and signed step for each flagged event. State whether two events on the same fish bracket an interval.
2. Report the number and fraction of speed-eligible rows with |slip| > π/2 (velocity opposite heading). This is the direct detector for a sustained flip. List the longest such run for each fish.
3. If a flipped interval exists, either exclude it from heading-derived quantities and the spatial map, or state it explicitly as a known defect. Add a synthetic test with flip-then-unflip to confirm the chosen behaviour.

### F2: Selection conditioning in the polarization–circulation panel is not disclosed

**Code:** `pilot.py`, panel `ax[1,1]` and the `collective` eligibility rule.

Circulation is defined only where at least 80% of fish have centroid-relative speed ≥ 0.5 BL/s. In a polarized translating school, relative velocities are small. That pushes frames out of eligibility, so the eligible 46.6% of frames is selected toward low-polarization or turning frames. The P–C hexbin therefore shows a joint distribution conditioned on that selection. Readers will tend to read it as a general P–C relationship.

Rigid group rotation also yields C = 1. The methods already say not to read C as milling, but the caption should repeat this.

**Required fix:**
- Caption or report text along these lines: "Only frames eligible for circulation (46.6%); eligibility depends on relative motion and is not independent of polarization."
- Optionally, report the polarization distribution for eligible frames versus ineligible frames. This is one extra quantile line.

### F3: The smoothing-robustness claim (B1-01) is not supported by evidence in the review packet

The report says the speed distributions are "similar across 7-, 11-, 15-frame filters". The supporting table, `speed-sensitivity.csv`, is not in the snapshot, and `summary.json` does not contain it.

The code is sound: it uses a common eligible mask set by the w=15 trim. I cannot confirm the claim itself.

**Fix:** Add the speed-sensitivity and curvature-sensitivity quantiles to `summary.json` or to the review packet. Otherwise, mark B1-01's robustness sentence as "not independently reviewed".

---

## 4. Minor findings (non-blocking)

- **M1. Spatial map ignores `heading_valid`.** `spatial()` rotates by raw ANGLE in all frames, including the 24 contaminated frames. The impact is negligible now, but it becomes relevant if F1 finds a flipped interval. Methods B4 says "per valid frame". Either mask these frames or document the choice.
- **M2. Spread and nearest-neighbour distance use different position sources.** Spread uses SG-smoothed positions (n = 24,494, losing 84 frames). Nearest-neighbour distance uses raw positions. This is defensible but not stated in the methods. Add one sentence.
- **M3. Polarization exclusion is wider than needed.** Removing the full 11-frame SG support for a heading that is only bad at the jump is conservative. It is fine, but the methods should say "SG-support frames" rather than "affected frames".
- **M4. Noise diagnostic is biased low for white noise.** For SG(11,3), residual variance under white noise is σ²(1 − c₀) with c₀ = 89/429 ≈ 0.207. Residual SD therefore understates σ by about 11%, while real movement inflates it. This sits inside the "illustrative" label. You could mention it, but it is not required.
- **M5. Relative heading is in the spec but not implemented.** Methods B4 defines `wrap(θj−θi)`, but the code neither computes nor reports it. The report makes no claim about it. Either remove it from the methods or defer it explicitly.
- **M6. Provenance coverage gaps.** `source_hashes` covers `src/shiners`, `tests`, config, methods and the lock file. It omits `scripts/fetch_pilot.py`, which produces the input and the ZIP CRC provenance. Add it. `fetch_provenance` silently becomes `null` if the file is absent; consider failing or warning instead.
- **M7. Video frame indexing.** Frames are counted by decode enumeration starting at 0, while track frames start at 1. Showing both i−1 and i covers the off-by-one. Enumeration still assumes no dropped or VFR frames, so this is acceptable only as qualitative evidence, as currently stated.
- **M8. Posture panel may clip strong bends.** The y-limits are ±0.25 BL, so strongly bent midlines could be clipped. Check the three examples.
- **M9. Jump detection stops at block boundaries.** A flip that coincides with a segment gap goes undetected. F1's slip-based check would also cover this case.

---

## 5. Numerical consistency checks (my reasoning against the coordinator's outputs)

| Quantity | Check | Result |
|---|---|---|
| Duration | 24,584 frames / 29.97 fps ≈ 820 s ≈ 13.7 min | consistent |
| Gaps | 6 missing frames, all at segment boundaries, giving 7 blocks per fish | consistent |
| Speed *n* | 245,780 − 7·12·10 = 244,940 | exact |
| Turn *n* | 244,940 − 24 (one fish, 2 jumps × 12 support rows) = 244,916 | exact |
| Polarization *n* | 24,578 − 24 = 24,554 | exact |
| Spread *n* | 24,578 − 84 (7 blocks × 12 frames) = 24,494 | exact |
| Mean degree | 1,662,869 / 245,780 = 6.7657 | exact |
| Slip eligible @0.5 | equals `slip_fraction` 0.9039 | consistent |
| Example frames | `iloc[int(0.1·24577)] = 2457` → frame 2458, which precedes the first gap | consistent |
| ANGLE convention | median axis disagreement 0.03 rad, so ANGLE = image-coordinate head direction and pose0 = head | supports the turn and curvature sign text |

**Synthetic tests (hand-derived):**
- Constant velocity (3, 4) and ax = 4 are exact for a cubic SG.
- The wrapped turn is 0.7 rad/s.
- The jump at 29/30 masks frames 24–35 (one sample conservative on each side, which is acceptable).
- The circle test gives a normalized cross of 10/(5·2) = 1, and the reversed case gives −1.
- The translation test gives spread 0.5 and centroid speed 2.5, with C undefined.
- Body-frame displacement (2, 1) at θ = π/2 gives forward 1 and right −2, which lands in bin (5, 2).
- The three-fish eligibility case gives 2/3 < 0.8, so the output is NaN.
- Visibility degrees are [1, 2, 0], and reciprocity is 2/3.

All of these match the test assertions. No test covers a sustained flip (F1) or the speed-sensitivity table (F3).

---

## 6. Claims in `reports/findings.md`

The numeric claims match `summary.json`. The language on dependence, the lack of confidence intervals, the illustrative iid reference, threshold-selected subsets, occupancy versus force, and visibility versus influence is appropriately restrained. The report does not use the iid reference or the residual-noise diagnostic as calibrated evidence.

Exceptions:
- B1-01 robustness is unverifiable from the packet (F3).
- The B3 hexbin description needs the selection caveat (F2).
- "Polarization uses body headings, with frames contaminated by heading jumps excluded" overstates the QA until F1 is resolved.

Data leakage: there is no fitted model. Trial-median L normalization is labelled descriptive, not a predictive transform, so leakage does not apply here.

---

## 7. Remaining limitations (accepted for a pilot)

- This is a single trial. Fish-frames are dependent, and there are no confidence intervals. The report states this correctly.
- There is no independent computational reproduction. The M1 execution gate and the release gate remain open, and this review does not close them.
- Video alignment is qualitative only. There is no identity audit.
- Arena and wall geometry is not validated, so the spatial-map structure may include boundary effects.
- Curvature relies on equal arc spacing of the source keypoints, which is assumed and not verified.

**To reach PASS:** resolve F1 by reporting the events and the |slip| > π/2 count, and exclude or disclose any flipped interval. Add the F2 caption. Supply or soften the F3 evidence. Then refreeze the snapshot hashes for re-review.
