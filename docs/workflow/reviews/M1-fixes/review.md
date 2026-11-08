# Second independent static review: pilot 0066 (F1/F2/F3 closure)

**Reviewer:** Claude (`claude-opus-5-5`), tool-free static review of the supplied snapshot
**Verdict: PASS for the stated static-review scope**, with the limitations below. I found no remaining material error. The minor notes are optional and do not block.

This verdict does not cover a final scientific release, independent computational reproduction, the M1 execution gate, visual or video validation, or all-trial and modeling scope.

---

## 1. Basis of this review

**What I did, by reasoning only:**
- Read the new `heading_diagnostics` code and the three new tests.
- Derived each test assertion by hand.
- Cross-checked the new summary numbers against the old ones for internal consistency.
- Read the revised wording in the methods and report.

**What the coordinator reported (I did not reproduce any of it):**
- All numbers in `summary.json`, the sensitivity CSVs, and `57 passed, 8 subtests passed`.

---

## 2. Finding-by-finding disposition

### F1: Sustained-flip detection — **Closed**

**Code (`metrics.py`, `heading_diagnostics`):**
- Slip is computed on raw `ANGLE` against SG velocity.
- Eligibility is finite speed ≥ 0.5 BL/s, evaluated before the `heading_valid` mask, as the revised methods require.
- Events require a one-frame step (`diff(frame)==1`), so a heading change across a gap is never called a jump. This addresses M9 for event reporting.
- Runs break at frame gaps, segment changes and ineligible rows.
- The tie-break with `start=None` can only arise when `n == 0`, and real runs always have `n ≥ 1`, so it is safe.
- The output is JSON-safe when the denominator is zero.

**Analytic check of the new tests (my derivation):**

*Flip-then-unflip test:* `trajectory(100)`, dt = 0.1, X = 3t, Y = 0, w = 11, trim = 6.
- Retained interior is frames 6–93, which is **88** rows. Speed is 3 BL/s with L = 1, so all 88 are eligible.
- `ANGLE = π` on frames 30–69. Slip there is wrap(0 − π) = −π, so |slip| > π/2 gives **40** reverse rows. One run spans 30–69 with n = 40. The fraction is 40/88.
- The steps at 29→30 and 69→70 wrap to −π, giving the events **(29,30)** and **(69,70)**.
- The SG mask covers frames 24–35 and 64–75. Reverse rows outside the mask are 36–63, which is 28 > 0.
- All assertions match.

*Gap/segment test:* reverse candidates fall in runs 0–4, 6–11, 12–16 and 18–19.
- The gap at frame 5, the segment change at 12, and the NaN velocity at 17 all break runs.
- The longest run is **6–11, n = 6**.
- Setting frames < 5 to 0 creates a heading change across the gap. The `diff==1` condition correctly excludes it from the events.
- All assertions match.

**Real-data consistency (my arithmetic on the coordinator's numbers):**
- Speed-eligible rows before the mask (222,181) minus 24 SG-support rows equals 222,157. That equals the slip *n*, and 0.90389 × 245,780 also gives 222,157. So all 24 masked rows were speed-eligible.
- 266 reverse rows minus 265 outside the mask leaves 1 reverse row inside the mask. 266/222,181 = 0.1197%. Both are consistent.
- The two events are on different fish (1 and 2, frames 20279 and 18174), so neither bracket can be a flip/unflip pair. This resolves the ambiguity I raised in my prior review.
- The event magnitudes are +1.71 and +1.89 rad. A head–tail swap would produce a step near ±π, so these values fit fast turns better, though they do not prove it.

**Bound on undetected flips:** velocity comes from positions and is independent of `ANGLE`. Any flipped state during forward, speed-eligible motion must therefore produce reverse rows. That bounds flipped speed-eligible rows at ≤ 266 (0.12%), with the longest contiguous run at 23 frames (≈ 0.77 s).

**Wording:** the report and methods call these "unresolved candidates", state that axis agreement cannot exclude a joint pose/heading reversal, preserve the intervals, and apply no correction. This is scientifically honest. The occupancy map's use of raw headings is now disclosed, which closes M1.

### F2: Selection conditioning — **Closed**
- The hexbin title states that the panel is conditioned on relative-motion eligibility.
- The report says eligibility "depends on relative motion and is not independent of polarization", says the panel is not the whole-recording joint distribution, and repeats that rigid rotation gives C = 1.
- `summary.json` adds polarization split by eligibility:
  - Eligible frames: median 0.878, 5th percentile 0.237.
  - Ineligible frames: median 0.908, 5th percentile 0.439.
- This supports the predicted direction of selection. The counts also reconcile: 11,434 + 13,120 = 24,554, the polarization *n*.

### F3: Smoothing robustness — **Closed**
- The speed and curvature sensitivity tables are now in the packet.
- Common *n* is 245,780 − 7 blocks × 10 fish × 2 × 8 (w = 15 trim) = **244,660**, which is exact.
- Speed medians are 1.462 / 1.453 / 1.449. The 95th percentiles are 3.563 / 3.531 / 3.498, a spread of about 2%.
- Curvature medians are 0.0158 / 0.0154 / 0.0146, and the tails differ by about 3%.
- "Similar across 7/11/15", limited to these settings, is supported.

### Prior minor items
| Item | Status |
|---|---|
| M1 (map uses raw headings) | Disclosed |
| M2 (spread vs. nearest-neighbour position sources) | Stated in methods |
| M5 (relative heading) | Deferred in methods |
| M6 (`fetch_pilot.py` hashing) | Added to `source_files`; the `null` fallback is now unreachable because `run` raises first |
| M3 | Mostly fixed; see N3 |
| M4, M7, M8 | Unchanged and acceptable |

---

## 3. Remaining material corrections

**None.**

## 4. Optional, non-blocking notes

- **N1. Low-speed blind spot.** The reverse-motion detector cannot see rows below 0.5 BL/s, about 9.6% of rows, and those rows still feed polarization and the spatial map. Persistent hidden contamination would need a flipped state that stays slow, or that begins and ends at block boundaries, without ever producing a long eligible reverse run. That is implausible but not excluded. One sentence in the report would make the bound explicit.
- **N2. Two different eligibility percentages.** The hexbin title computes 11,434/24,578 = **46.5%**, because it also requires valid polarization. The report quotes **46.6%**, the circulation-eligible fraction. Both are correct for their definitions, but harmonizing the wording would avoid reader confusion. Also, the "ineligible" polarization group includes 84 frames where eligibility is *unknown* (no valid velocity), which is negligible.
- **N3. Residual wording.**
  - The findings sentence "smoothing support was excluded from heading-derived results" should say turn rate, slip and polarization, because the map deliberately keeps raw headings.
  - The methods "Units and smoothing" paragraph still says "omit affected frames from polarization". It should say "SG-support frames", to match B3.
- **N4. Optional observation.** The report could note that the event steps of about 1.7–1.9 rad are not near π.

## 5. Checks I did not execute

- I ran no tests and cannot account for the "8 subtests", which are not in the supplied test file.
- I did not run the pilot or recompute anything from the parquet files.
- I did not view any figures: the hexbin title as rendered, the posture panel clipping (M8), the occupancy map, or the video overlays.
- I did not inspect any flagged reverse-motion interval or heading event against the video.
- I did not see `provenance.json`, `collective.csv`, `threshold-sensitivity.csv`, `status.md`, `decisions.md`, `validation.py`, or `scripts/fetch_pilot.py`.
- I did not verify that the snapshot hashes match the live repository.

This review is advisory. The coordinator adjudicates acceptance, and the independent computational reproduction and release gates remain open.
