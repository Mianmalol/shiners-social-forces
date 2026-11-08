# Independent implementation review: all-trial comparison code

## Verdict: **PASS** (implementation snapshot only)

This is not a results or scientific-release approval. I found no mathematical or implementation error that requires a rerun.

The items below are non-blocking. Two of them (N1, N2) should be dispositioned before the narrative review, because they affect how saved tables are read rather than what they contain.

All statements below come from my static reading of the supplied source. The test outcomes are the implementer's report (`reports/test-results-comparison.txt`), not my execution.

---

## Static verification of the requested focus areas (no blockers found)

**1. Coordinate and sign definitions**
- Body-frame right is `-dx·sinθ + dy·cosθ` (`metrics.spatial`). At θ=0 this gives right = +dy, which is down in y-down image coordinates. That matches the source convention ("right = heading rotated +90°").
- The circulation cross product is `rx·uy − ry·ux` (`metrics.collective`), consistent with `docs/methods.md`.
- Curvature (`metrics.curvature`):
  - The arc parameter is `u = i/20 − 0.5`, so the fit is evaluated at index 10 (u=0).
  - The first and second derivatives are `c1` and `2·c2`, which is correct for a monomial basis at u=0.
  - The κ formula is parametrization-invariant, so the u-scaling does not matter.
- Signed C is labelled image-coordinate and not for cross-camera chirality comparison.

**2. Finite-N references**
- C: with iid uniform directions, sin φ has variance ½, so the mean has σ² = 1/(2n). Then E|Z| = σ·√(2/π) = 1/√(πn). The code computes this per frame with `counts[valid]`. Correct.
- P: the resultant is Rayleigh with per-component σ² = 1/(2n), so E[R] = σ·√(π/2) = √(π/(4n)).
  - In `heading_selection` the primary reference uses n=N, valid because primary P requires all fish valid.
  - The affected-fish-only reference uses the frame's `n_valid`. Correct.
- Neither reference is subtracted or divided out anywhere, including in the plots.

**3. Metric eligibility and denominators**
- 80% eligibility uses `eligible.mean(axis=1) >= 0.8`. The boolean sum is an exact integer, so k/N is correctly rounded and the boundary cases (8/10, 24/30, 56/70) compare as intended.
- For N=151, 121/151 passes and 120/151 fails, as expected.
- Eligible fractions are NaN rather than 0 when any velocity is undefined.

**4. Threshold nesting** (`threshold_frame_selection`, `common_cohort_summaries`)
- Per-fish eligibility at 1.0 implies eligibility at 0.5, which implies eligibility at 0.25. So the frame sets are exactly nested.
- The threshold "common" set is therefore exactly the 1.0-eligible set, as the plan states.
- The two components (fixed-baseline C on each threshold's frames, and varying-cutoff C on common frames) are computed separately and are correctly labelled.

**5. Leave-one-out identity**
- `effective_cutoff = 0.5·(N−1)/N` is the correct cutoff for the identity v_i − v̄_all = ((N−1)/N)(v_i − v̄_other).
- Directions are unchanged, so only eligibility moves.

**6. Gaps, segments and truncated duration**
- `kinematics` groups by `(id, segment)` and splits blocks on `diff(frame) != 1`. It trims `w//2 + 1` samples from each end, unwraps heading within each block only, and never bridges a gap.
- The heading-jump support convolution has the correct length and covers ±half around each flagged pair.
- Matched-duration kinematics are recomputed on the truncated rows, so the prefix endpoint is trimmed. The supplied test expects 31 − 12 = 19 frames, which matches.

**7. Nonpositive-length handling**
- L is the median of positive lengths only.
- Curvature is NaN on affected rows in all neighborhoods. Position and heading are retained in primary metrics.
- The sensitivity analysis removes whole frames and recomputes kinematics, so the new gap is trimmed. The test's expected NaN span (frames 24–36 around frame 30) is consistent with this.
- For P, the sensitivity removes only the affected frame itself. That is appropriate because P is instantaneous. The recomputed jump detection no longer spans the removed frame.

**8. N=151 length scenario**
| Output | Treatment under L×1.15 |
|---|---|
| Speed, acceleration, spread, centroid speed, nearest-neighbor distance | Divided by 1.15 |
| Curvature × L | Multiplied by 1.15 |
| Spatial density | Multiplied by 1.15²; coordinates divided by 1.15 (algebra correct) |
| Turn rate | Unchanged (correct) |
| Threshold sweep, slip eligibility, reverse-motion diagnostics | Recomputed at the scaled L |

The limitation text covers the network and midline truncation.

**9. Streaming network** (`network_summary.summarize_network`)
- Bit packing uses `1 << (pair % 8)` at byte `pair // 8`, decoded with `unpackbits(bitorder='little')`. This is consistent.
- Each frame is padded to whole bytes, and the padding bits are sliced off.
- Duplicates are rejected both within and across batches.
- Reciprocity uses `A & Aᵀ`, which gives an edge-weighted count of directed edges.
- Zero-degree observers on covered frames are counted, via `bincount(minlength=n)` on the full degree matrix.
- The total edge count is checked against Parquet metadata and the packed sum.
- Primary and geometry-excluded counts are stored separately. The excluded degree histogram is the full histogram minus the excluded-frame histogram.

---

## Non-blocking findings

**N1. Threshold-panel identities should be asserted or annotated before the narrative.**
Because the sets are exactly nested (point 4), two outputs are fixed by construction:
- Baseline C on the 0.25 frame set is *identical* to baseline C on the 0.5 set. The plan says "overlaps", but the overlap is complete.
- `baseline_undefined_frames` at 1.0 must be 0.

So in `plot_thresholds` panel 4, the 0.25→0.5 segment is flat by construction. It should not be read as robustness.

Fix (no rerun needed): add these invariants to `validate_trial`, and add a caption note. Optionally add `common_frames == circulation n at 1.0`.

**N2. A common source snapshot across trials is not checked when plotting.**
- `run_comparison.validate_completed` does check that recorded source hashes match current files, but only on `--resume`.
- `plot_comparison` reads only `summary.json` and `collective.csv`.
- The plan requires all final trials to come from one common snapshot.

Fix: have `plot_comparison` (or a separate check) load each trial's `provenance.json` and require identical `source_hashes` for `compare_trial.py`, `metrics.py`, `network_summary.py` and the config. Record that in the manifest. If this check is not added, verify it by hand before results acceptance.

**N3. The circulation eligibility denominator mixes two causes.**
`circulation_eligible_frame_fraction` divides by all tracked frames. That includes frames where velocity is undefined because of edge trimming, not low relative motion. The plan asks for separate denominators.
- The effect is small: about 7 blocks × 12 trimmed frames in the smaller trials versus 1 × 12 at N=151, roughly 0.3%.
- It can be derived without a rerun: rows of `collective.csv` with finite `eligible_fraction` are the velocity-defined frames.
- Recommend reporting both fractions.

**N4. The affected-fish-only P on primary frames is identical by construction.**
`polarization_on_primary_valid_frames` equals primary P exactly, because all headings are valid on those frames. The plan already acknowledges this. The informative contrast is affected-fish-only P on the *added* frames (subset valid, primary masked), which is not summarized.

It can be derived without a rerun from `collective.csv` columns `polarization_valid_fish` and `heading_frame_valid`. Recommend adding it to the narrative tables.

**N5. The network matched-duration count is hard-coded.**
`summarize_network` uses 17999 and ignores the config `matched_frame_count`, while `compare_trial` reads `cfg.get('matched_frame_count', 17999)`.
- This is harmless in the current config, which omits the key, so both use 17999.
- It is a latent divergence that the `matched_frame_count=31` test does not catch, because that test runs without the network.
- Fix: pass the value through.

**N6. Scale scenario coverage is partial (optional).**
The window-sweep and leave-one-out circulation are not recomputed under L×1.15. The plan names only the threshold sweep, so this is an optional extension.

**N7. Minor disclosure items.**
- `body_length_px` quantiles include nonpositive values. This is fine if labelled as raw.
- `heading_axis_error` is not masked on nonpositive-length rows unless the pose is exactly collapsed (≤1e-8).
- Spatial occupancy has no nonpositive-length sensitivity; only nearest-neighbor distance does. The plan does not require one.
- A network frame with zero edges is indistinguishable from an uncovered frame. This is inherent to the edge-list format and consistent with the pilot; it is very unlikely at N≥10.

**N8. Figure 04 caption.**
The visibility and curvature panels include N=151. The caption says "different camera/length calibration" but should state explicitly that N=151 curvature and visibility are excluded from group-size claims, as the plan requires. This belongs to the narrative review.

---

## Test evidence (as reported)
- The reported run is "123 passed, 8 subtests passed". The supplied test files contain about 60 test cases including parametrizations, and none use subtests. The rest presumably come from pilot test files not supplied here, so I could not map the reported count to the code reviewed.
- I independently re-derived these expected values and they match the code logic:
  - 49 retained frames and 12 masked rows in the heading test
  - 36 circulation frames in the geometry sensitivity
  - 19 matched-prefix frames
  - the packed-byte count of 6
  - the reciprocity value of 0.8

## Checks not executed
- I ran no code, tests, data or real trials. I inspected no figures or output tables. Results were not supplied.
- I did not confirm that the source `group` and `sequence` values produce stem-matching trial labels. A mismatch would fail loudly in `run_comparison` or the plot, not silently.
- I did not verify these against real data:
  - nonpositive-length row counts or their locations near joins
  - heading-jump rates
  - network coverage
  - float32 tolerances
  - the N=151 frame count, segment structure or timing
- I did not check the memory and runtime bounds for N=151.
- I did not verify that the stopped initial run was preserved, or that all final trials share one source snapshot (see N2).
- I did not review the pilot code or tests beyond the functions quoted here, nor `fetch_trials.py`, `audit_trial.py` or `pyproject.toml`/`uv.lock`.
