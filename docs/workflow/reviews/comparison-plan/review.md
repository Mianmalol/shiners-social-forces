# Review: all-trial descriptive comparison plan

**Verdict: CHANGES_REQUESTED.** The plan is sound in structure. Trials are the replicate, frame CIs are not passed off as between-trial uncertainty, C is not corrected by its iid reference, and there is no milling classifier or causal language. The changes below fix selection effects that vary with N and an incomplete treatment of the N=151 length bias. Without them, cross-N patterns could come from the method rather than the fish. All the fixes are descriptive and need no model, classifier or test.

---

## Material findings

### M1. Excluding whole frames for one fish's heading jump biases P by N
`docs/methods.md` (B1/B3) drops a whole frame from polarization if any fish's SG support touches a heading jump. If the per-fish-frame exclusion probability is *p*, frame retention is about (1−p)^N:

| p | N=10 | N=151 |
|---|---|---|
| 0.001 | 0.99 | 0.86 |
| 0.01 | 0.90 | 0.22 |

Excluded frames are probably not random. They are likely enriched for fast turns, crowding and tracking stress. So P at N=151 (and to a lesser degree N=70) would describe a progressively more selected subset of time.

**Fix:**
- Report the frame-retention fraction for P per trial, broken down by exclusion reason.
- Add a sensitivity analysis that drops only the affected fish rather than the whole frame. Record n per frame, and compare medians on the common frame set.
- If the cross-N ordering of P differs between the two masks, report the pattern as unresolved.

### M2. P has no finite-n reference saved, unlike C
For iid uniform headings, E[P²] = 1/n exactly and E[P] ≈ √(π/(4n)). That gives roughly 0.28, 0.16, 0.11 and 0.072 for n = 10, 30, 70 and 151. A raw decline of P with N is therefore expected even with no change in behavior.

**Fix:**
- Save √(π/(4n)) per frame next to P, with the same "illustrative, not a null" label used for C.
- State in the narrative that any P-vs-N statement must be read against this reference.
- Do not subtract or divide by it, matching the C rule.

### M3. The N=151 length scenario covers too few outputs
Every output scaled by L shifts under L×1.15:

- **Simple rescales:** spacing and spread divide by 1.15; body-frame density per L² multiplies by 1.15² ≈ 1.32; centroid speed and k·L also shift.
- **Outputs that need recomputation:** anything with a speed-dependent cutoff, i.e. slip eligibility, C/P eligibility, and the threshold sweep.
- **Not fixable by rescaling:**
  - **Curvature.** The source says the midline is about 15% short yet still fits the shape. That could be uniform scaling or truncation (for example, a missing tail tip). If it is truncation, midline indices 7..13 are not the anatomical midpoint, so k is not comparable to the other trials.
  - **Visual network.** It was ray-cast from the stored, too-short outlines. That plausibly lowers occlusion, raises degree and visible fraction, and shrinks angular sizes.

**Fix:**
- Apply the L×1.15 scenario to all L-normalized outputs, recomputing those with eligibility cutoffs.
- Mark N=151 curvature and network metrics as length-biased in an unknown direction or size, with no available correction.
- Exclude N=151 from any claim that curvature or visibility varies with N.

### M4. Other N=151 confounds need a statement
The N=151 trial differs in more than length:

- **Duration:** 17,999 frames (about 10 min) vs about 24,580 (about 13.7 min). If behavior drifts within a trial (acclimation), comparing the full duration mixes in a time-window effect.
- **Time base:** `time = frame/29.97` is a converter convention. The raw video name `calibrated_lowres30.25.mp4` does not confirm the frame rate, and the frame rate cannot be checked from the tracks. Speeds, turn rates and the BL/s thresholds all depend on it.
- **Segment structure:** this is a single unjoined video, so the seven-segment join structure may not apply. The plan already says to use actual segments.
- **Chirality:** a different camera or calibration could flip the image.

**Fix:**
- Recompute the smaller trials' summaries on their first 17,999 frames as a matched-duration sensitivity.
- Record the 29.97 fps assumption for N=151 as unverified.
- Do not compare signed C (direction of rotation) across cameras.

### M5. Threshold-intersection comparison: say what it actually isolates
Frame eligibility is monotone in the threshold. Reaching ≥80% of fish at 1.0 BL/s implies reaching it at 0.5 and 0.25. So the "intersection of eligible frames" is exactly the 1.0-eligible frame set, a strongly selected high-relative-motion subset. Holding fish fixed as well makes C identical across thresholds, which is trivial.

**Fix:** report two explicit components:
1. **Frame-selection effect:** C at a single threshold, computed on each threshold's frame set.
2. **Fish-composition effect:** different thresholds compared on the common (1.0-eligible) frame set.

Label the common set as "high relative motion frames", not as representative.

### M6. Pre-specify what counts as a cross-trial pattern
The plan bans significance tests but does not define "consistent across trials". That leaves room for post hoc reading of 3+3+3+1 points.

**Fix:** before results are viewed, fix a descriptive criterion. For example: "monotone in N" means every trial at a smaller N lies on the same side of every trial at the next N, so the ranges do not overlap. Anything else is reported as overlapping or inconsistent. N=151 can be at most "consistent with" the trend and never establishes it.

---

## Reasoning checks (static, by me)

- **Leave-one-out identity.** v_bar_all = (v_i + (N−1)·v_bar_other)/N, so v_i − v_bar_all = ((N−1)/N)·(v_i − v_bar_other). This is correct, and the same identity holds for r_i about the centroid. Directions are unchanged, so with the same eligible set, C under leave-one-out equals C under the all-fish mean.
  - Only eligibility changes. The secondary threshold 0.5·(N−1)/N is 0.45, 0.483, 0.493 and 0.497 BL/s across N, so the diagnostic matters mainly at N=10. The "diagnostic, not correction" framing is correct.
- **C reference.** For iid uniform directions, E[sin²] = ½, so E|mean| = 1/√(πn). This is correct. It must be evaluated per frame with that frame's n_eligible, as the plan says. Σr_i = Σu_i = 0 makes this anti-conservative or biased in an unknown direction at small N, so the "not calibrated" wording is correct.
- **Eligibility counts.** ceil(0.8N) gives 8, 24, 56 and 121 (121/151 = 0.801). Recording eligible fractions is adequate.
- **Replication framing** (one point per trial, equal weighting, ranges, no frame-based CIs) is correct.

## Checks not executed
I had no tools, so the following rest on the implementer's reports or are open:

- No code, tests, configs or outputs were run or inspected beyond the supplied text. I did not verify that `configs/comparison.json` drives the implementation.
- Per-trial schema, segment structure, frame gaps, fish counts and body_length medians were not verified.
- Heading-jump exclusion rates were not measured, so the size of M1 is unknown.
- The N=151 frame rate, image orientation and midline truncation vs scaling were not verified.
- Network completeness, adjacency bitset correctness and duplicate handling were not verified.
- No results or draft narrative were supplied. The required implementation/results review is still pending and is separate from this plan verdict.
