# Focused confirmation review: comparison-results narrative fixes (B1–B4)

## Verdict: **PASS**

The corrected descriptive report can be shared locally with its stated caveats. B1–B4 are each addressed. Every number I checked in the corrected README agrees with the supplied tables, `validation.json` and code. I found no remaining material wording or numerical contradiction. The optional qualifications add no unsupported biological claim. One of them names a biological possibility in hedged form, which I discuss under N2.

The three notes at the end are non-blocking.

**Basis:** everything below is my own static reading of the supplied text, tables, JSON and source code. I ran nothing and viewed no images. Test counts, hash checks, pilot parity, the 50 sampled-P recomputations and the coordinator's plot inspection are **coordinator-reported execution evidence**, not mine.

---

## B1 — P smoothing presented correctly ✓

**What the README says now**
- §1 lists only these robustness checks: raw-heading and affected-fish-only summaries, invalid-length frame exclusion, and the 17,999-frame prefix.
- It then states: "P uses raw headings: changing the smoothing window changes P only through the heading-jump exclusion mask, so the window sweep is not an independent test of smoothing the alignment signal."
- The Monday summary no longer mentions smoothing.

**Code check (my reasoning)**
- In `metrics.collective`, `polarization = hypot(mean cos ANGLE, mean sin ANGLE)` uses raw `ANGLE`. Only the `heading_valid` mask is applied afterwards.
- In `kinematics`, `heading_jump` is computed from raw `ANGLE` steps, so it does not depend on the window. `window` enters only through `np.convolve(..., np.ones(window))`, which sets the mask width.
- The README sentence therefore describes the code accurately.

**On the coordinator declining "cannot fail by construction"**
I agree with the coordinator. A wider mask excludes more frames, which could in principle shift the median. "Persistence is expected but not guaranteed" is the more precise framing, and the README's wording ("not an independent test") is sufficient.

## B2 — The N=151 result is in the short summary ✓

The Monday summary now reads: "The single 151-fish recording's alignment fell within the 70-fish range, so it does not extend the ordering; it also has a different camera."

- 151 median P = 0.6406, which lies inside the 70-fish range 0.509–0.694 ✓.
- The new lead paragraph also says circulation lies within the 70-fish range: C = 0.4837, inside 0.379–0.781 ✓.

## B3 — Precision ✓

**P coverage column.** Recomputed from `polarization_eligible_frame_fraction`:

| Trial | Fraction | README |
|---|---:|---:|
| 0066 | 0.99902 | 99.90% ✓ |
| 0105 | 0.99805 | 99.80% ✓ |
| 0126 | 0.99951 | 99.95% ✓ (nonzero exclusion now visible) |
| 0084 | 0.99130 | 99.13% ✓ |
| 0115 | 0.99797 | 99.80% ✓ |
| 0120 | 0.99642 | 99.64% ✓ |
| 0103 | 0.99032 | 99.03% ✓ |
| 0107 | 0.99292 | 99.29% ✓ |
| 0124 | 0.99197 | 99.20% ✓ |
| 151 | 0.98044 | 98.04% ✓ |

- §5's "98.0–99.95%" agrees with the table.
- The validator difference is stated as `2.220446049250313×10⁻¹⁶`. This matches `checks.independent_polarization_max_absolute_difference` exactly, and also matches the per-trial maxima for 0105, 0126 and 0120.
- I accept the coordinator's point that the earlier "≤2.23e-16" was a valid upper bound, not an error.

## B4 — Spread lead sentence ✓

§3 now leads with: "school-spread medians separate between N=10 and 30, but the N=30 and 70 ranges overlap at full duration and separate only in the matched prefix." It then adds that some growth is geometrically expected at comparable spacing.

- 10 → 30: 2.202–2.970 vs 3.707–5.069, nonoverlapping ✓.
- 30 → 70: 5.069 > 4.979, overlapping ✓.
- The phrase "A strict three-group spread ordering is therefore not robust to the time window" is consistent with this.
- **Limitation:** matched-prefix spread values are not in the supplied tables. "Separate only in the matched prefix" therefore rests on the prior review's reading of `summary.json`, not on a fresh check of mine.

## Optional additions: checked for unsupported claims

| Addition | Assessment |
|---|---|
| Lower speed and lower P co-occur at 70 | Supported: 70-fish speeds 0.713–1.160 are below every 10/30 trial (≥1.376). The text states co-variation only, says stratification has not been done, and makes no causal claim ✓ |
| 80% eligibility rule; coverage not group-size-neutral | Consistent with the `fractions >= min_fraction` logic. Appropriately cautionary ✓ |
| Positive signed-curvature medians | 0.0154–0.1231 across all ten trials ✓. "Near-zero" is gone. See N2 on wording |
| Occlusion geometry for visual access | Hedged correctly; does not assert attention or information use ✓ |
| Clustered heading-event windows | Match the prior review's list. Framed as candidates for video inspection, either tracking defects or real turns ✓ |

## Spot re-verification of other numbers (my arithmetic)

- **§3 table:** all 18 ranges match `trials.csv`, `metrics.csv` and the validator's `histogram_mean_degree` values. These cover speed, RMS radius, nearest neighbor, visible degree, visible fraction and reciprocity.
- **Counts:** 10,827,539 track rows, 266,688,111 network rows and 239,246 frames all match `validation.json` totals ✓.
- **0107 threshold example:** 74.6% / 0.441 / 10.6% / 0.781 / 2,598 frames / 0.742 ✓.
- **151:** speed 1.861 ✓; C coverage 87.1% ✓.

## Remaining non-blocking notes

- **N1. "time-window" in the Monday summary is ambiguous.** Because B1 is specifically about the smoothing *window*, "heading-filter, time-window and flagged-geometry checks" could be read as reintroducing it. Suggest "matched-duration" instead.
- **N2. The curvature-sign alternatives are incomplete.** "Biological asymmetry or pose-reconstruction bias" leaves out image-coordinate or sign-convention effects. The code defines positive curvature as clockwise in image coordinates with y pointing down. "Biological asymmetry" is hedged with "could", so it is not a claim. Adding "or a coordinate/sign-convention artifact" would make the list less suggestive.
- **N3. The review-status line will go stale.** §5 says the corrections are "now undergoing focused confirmation". The coordinator should update it once this confirmation is adjudicated.

## Checks not executed

- I ran no code, tests, validator or pipeline, and recomputed nothing from raw tracks or networks.
- I inspected no figures. Captions, missing-marker rendering and the visual isolation of N=151 are unverified by me.
- **Not verifiable from this packet:**
  - matched-prefix spread, speed and P values
  - the leave-one-out range (0.29–10.45 pp, |ΔC| ≤ 0.0246)
  - the L×1.15 scenario values
  - the geometry-exclusion shifts
  - the heading-event window locations

  These rest on the prior review's checks against `summary.json`.
- I did not re-check every nested `summary.json` field. This is a focused confirmation of B1–B4 only.
- Independent computational reproduction and video inspection remain open gates, as the report states.
