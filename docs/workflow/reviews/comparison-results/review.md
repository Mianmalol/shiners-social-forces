# Review: ten-trial descriptive comparison (results, code and narrative)

## Verdict: **CHANGES_REQUESTED** (narrative only; no rerun required)

I found no numerical contradiction between the README and the supplied per-trial tables. I found no code defect that would require rerunning any analysis. Every quantitative claim I checked against `trials.csv`, `metrics.csv`, `thresholds.csv`, `threshold-pairs.csv` and the four supplied per-trial `summary.json` sets matches.

The changes requested are wording fixes. One listed robustness check is near-tautological, the "Monday summary" omits the N=151 result that bears on its main claim, and there are two small numeric or rounding slips. Once these are fixed, I would consider the comparison shareable locally with its stated caveats.

All reasoning below is my own static reading. Test counts, hash verification and validator output are implementer-reported evidence that I did not execute.

---

## Blocking findings (text edits only)

### B1. "Survives smoothing windows 7/11/15" is not an informative robustness check for P
P is computed from raw `ANGLE` (`metrics.collective`). The SG window affects P only through the width of the heading-jump support mask (`kinematics`: `contaminated` uses `np.ones(window)`). The supplied numbers confirm this. For example, the 0107 window-sweep P medians are 0.50838 / 0.50851 / 0.50864.

Listing the window sweep alongside raw-heading, affected-fish-only, geometry-exclusion and matched-duration therefore overstates how independent the robustness evidence is. The plan requires robustness claims to name the checks under which an ordering persists, and this one cannot fail by construction.

**Fix:** in §1 and in the Monday summary, either remove "smoothing windows" from the P robustness list, or say explicitly that window choice changes P only through the mask, so persistence is expected.

### B2. The Monday summary should state that N=151 does not continue the ordering
§1 correctly says that the N=151 median P (0.641) and C (0.484) lie inside the 70-fish ranges. The summary instead says only that "larger groups had lower whole-school heading alignment" and that the 151 trial "is informative but has a different camera."

P is scale-free and independent of the time base. Its only L- or fps-dependence is through the heading mask, which depends on neither. So P is the metric for which the 151 observation is *least* confounded by the camera and length issues. Leaving its non-continuation out of the summary misrepresents the evidence.

**Fix:** add one clause along these lines: "the single 151-fish recording's alignment fell within the 70-fish range, so it does not extend the pattern."

### B3. Two minor numeric slips
- **§5:** "differ by at most 2.23×10⁻¹⁶". `validation.json` reports 2.220446e-16, which is 2.22×10⁻¹⁶ (one ulp near 1).
- **§1 table:** 0126 P coverage is shown as "100.0%". The actual value is 0.99951 (12 frames excluded), and §5 correctly says "98.0–99.95%". Show "99.95%", or use enough precision that a nonzero exclusion does not read as zero.

### B4. The spread lead sentence should be tied to the predeclared criterion
§3 begins with "larger groups occupy a broader whole-school footprint" and only qualifies it afterwards. Under full duration, 30→70 overlaps (4.979 < 5.069). Only 10→30 meets the nonoverlap criterion.

A larger footprint is also geometrically expected at any fixed spacing: RMS radius scales roughly as √N × spacing. Observed growth is actually sub-√N.

**Fix:** lead with "10→30 nonoverlapping; 30→70 overlapping at full duration, separated only in the matched prefix." Add one phrase noting that some growth is geometrically expected.

---

## Verified claims (my arithmetic on the supplied tables)

**Polarization ordering**

| Condition | N=10 | N=30 | N=70 | Nonoverlap |
|---|---|---|---|---|
| Primary median P | 0.894–0.943 | 0.809–0.827 | 0.509–0.694 | ✓ |
| Raw P | 0.894–0.943 | 0.809–0.827 | 0.509–0.692 | ✓ |
| Affected-fish-only P | 0.894–0.943 | 0.809–0.827 | 0.509–0.692 | ✓ |
| Geometry-excluded P | 0.894–0.943 | 0.809–0.827 | 0.509–0.694 | ✓ |
| Matched prefix P | 0.882–0.945 | 0.794–0.866 | 0.455–0.701 | ✓ (as reported) |

- The narrowest gap is 10→30 in the matched prefix (0.882 vs 0.866).
- The largest affected-fish-only shift is 0.00144 (0103) ✓.
- The largest geometry-exclusion shift is P 1.10×10⁻⁴ (0107) and C 7.31×10⁻⁵ (0126) ✓.

**Circulation**
- Medians: 0.287–0.383, 0.268–0.397, 0.379–0.781. They overlap, and the report correctly declines a monotone claim ✓.
- 0107 threshold sweep:
  - 0.25 BL/s: 74.6% coverage, median 0.441.
  - 0.5 BL/s: 10.6% coverage, median 0.781.
  - 1.0 BL/s: empty.
  - Pairwise common set: 2,598 frames, lower-cutoff median 0.742.
- Decomposition: frame selection 0.301 + fish composition 0.039 = 0.340 total ✓. This is additive by construction, because the pairwise common set equals the higher-threshold set.
- Leave-one-out: coverage gains range from 0.29 percentage points (151) to 10.45 (0066). The maximum |ΔC median| is 0.0246 (0066). Leave-one-out C ranges still overlap ✓.

**Other chapters**
- Speed, RMS radius, nearest-neighbor, visible degree, visible fraction and reciprocity ranges in the §3 table all match ✓.
- The 70 < {10, 30} speed claim holds at full and matched duration ✓.
- 0084 matched speed changes by +23.6% ✓.
- The visibility orderings hold in the matched prefix and with geometry excluded ✓.

**N=151 and data accounting**
- L×1.15 scenario ✓:
  - speed 1.618
  - RMS radius 8.927 → 7.763
  - nearest neighbor 0.985 → 0.857
  - C coverage 87.1% → 77.4%
  - C median 0.484 → 0.507
- 22 nonpositive-length rows across 14 frames ✓.
- 239,246 frames ✓.
- No uncovered network frames in any trial ✓.

**Test evidence reconciliation.** The "8 subtests" equal 6 error-case subtests in `test_claude_review.py` plus 2 compression subtests in `test_fetch_pilot.py`. This is consistent. I could not reconcile the 131 total, because `shiners.validation` (imported by `test_validation.py`) and the pilot tests were not supplied.

## Code reasoning (no rerun-level defects)

- **Unchanged definitions:** the P, C, nesting, leave-one-out and reference definitions match the plan and my prior implementation review.
- **Validator coverage:** the N1–N4 validators (`validate_trial` identities, velocity-defined denominator, added-frame P) are implemented as dispositioned.
- **Exploratory pairwise script:**
  - It enforces frame alignment, subset nesting and P invariance across thresholds.
  - It records empty intersections as null.
  - It checks that its inputs match the frozen output hashes.
- **Matched prefix:** it uses sorted observed frames in both the track path and the network path, so the two are consistent. The 151 "matched" sensitivity is identical to its primary result by construction, which is correctly not presented as evidence.

---

## Recommended (non-blocking) follow-ups

1. **Clustered heading jumps.** The jump events cluster across many fish within a few frames:
   - 0084: about 15 fish at frames 17057–17066
   - 0107: frames 19468–19478 and 9949–9958
   - 0103: frames 16807–16831
   - 0124: frames 18690–18716

   These could be frame-level tracking defects, or genuine collective fast turns or startles. Whole-frame exclusion would preferentially remove the second kind. The effect on medians is small (≤0.0016), but these frame windows are good targets for the unfinished video-inspection gate. Suggest listing them as such.

2. **Activity as a co-varying factor for P.** The 70-fish trials are also the slowest (median 0.71–1.16 BL/s), and P is computed over all frames, including low-speed ones. A P-by-centroid-speed stratification would show whether the alignment ordering co-varies with activity level. Until then, a sentence noting the co-occurrence would be prudent. This is not a causal claim either way.

3. **N-dependence of C eligibility.** At larger N, the eligible fraction concentrates around its mean, so the ≥80% rule behaves almost like an all-or-none threshold on the group's 20th-percentile relative speed. C coverage itself is therefore not comparable across N, separately from speed differences. Worth one sentence in §2.

4. **Curvature sign.** Median signed curvature×L is positive in all ten trials (0.015–0.123). Calling these "near-zero" understates a consistent sign. That sign could be a pose-model or midline asymmetry rather than behavior. No claim is made, so just avoid "near-zero."

5. **Visibility finite-N expectation.** As with P, falling visible fraction and rising degree are partly expected from occlusion geometry at higher N. A short note would parallel the P reference treatment.

---

## Checks not executed

- **No code run.** I executed no code, tests, validator or pipeline, and recomputed nothing from raw tracks or networks. The 131/8 test result, hash verification, same-source/config check, pilot parity and the 50 sampled-P recomputations are coordinator evidence.
- **No figures inspected.** I did not view rendered figures (PNG/SVG), and could not confirm that captions, markers, the isolation of N=151, or missing-marker rendering match the code.
- **Five trials summarized only via tables.** Full `summary.json` files for 0105 (supplied), 0115, 0120, 0103 and 0124 were checked. For the remaining trials, I checked the values that appear in `trials.csv`, `metrics.csv` and `thresholds.csv`, but not every nested field.
- **Unverified at source:**
  - the nonpositive-length row locations
  - heading-jump events against video
  - the 151 frame rate, orientation, and midline truncation versus scaling
- **Not reviewed:** `shiners/validation.py`, `fetch_trials.py`, `audit_trial.py`, `pyproject.toml`/`uv.lock`, the run log and the download log.
- **Gates still open:** independent computational reproduction and video inspection of the high-C and clustered-jump intervals remain explicitly unfinished. This review does not substitute for either.
