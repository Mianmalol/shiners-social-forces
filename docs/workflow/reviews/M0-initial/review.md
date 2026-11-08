# Independent review: 0066 descriptive pilot methods

**Reviewer:** Claude (claude-opus-5-5), static reasoning review of the supplied snapshot. I did not execute any code. The executed test logs belong to the OpenAI coordinator, and this review is not an independent computational reproduction.

## Verdict: **CHANGES_REQUESTED** (minor; no redesign needed)

The core definitions are correct: coordinate transforms, signed curvature, circulation, derivative windows, and graph metrics. With the corrections below, the methods are suitable for a **clearly labeled descriptive pilot**. Nothing below is blocking in the sense of a wrong formula. M1 and M2 do change computed numbers, so they should be fixed in `docs/methods.md` before the real run, not after.

---

## Material findings

**M1. Unwrapping assumes no head–tail flips in `ANGLE`; add a flip/jump QA check.**
`np.unwrap` treats any per-frame step over π as a wrap. A tracker head–tail inversion is a step of about ±π. It would appear as a spurious turn-rate spike of order π × 29.97 ≈ 94 rad/s, and it would also corrupt slip and polarization P.
*Correction:* Before deriving turn rate, flag frames where |wrap(ΔANGLE)| > π/2 per frame. Also cross-check `ANGLE` against the midline axis, e.g. atan2(pose₀ − pose₂₀). Report the count of flagged frames. Exclude flagged frames, plus their SG window support, from turn-rate and slip, or split blocks at flags. State the rule in the methods.

**M2. The 0.1 L/s thresholds for slip and circulation sit at the velocity noise floor.**
Rough estimate, using README noise σ ≈ 0.5 px and SG cubic first derivative at w=11: the derivative noise gain is about 0.2–0.25 σ per frame. That gives roughly 0.1–0.12 px/frame per component, or about 3–4 px/s, or about 0.1 L/s at L ≈ 38 px. At 0.1 L/s, then, velocity *direction* is largely noise. This makes slip near threshold meaningless. It also lets noise-driven uᵢ enter C.
*Correction:* Estimate the noise floor empirically. One option is the SD of (raw − smoothed) position propagated through the SG derivative kernel; another is the speed distribution of near-stationary fish. Then set thresholds to several times that floor (provisionally ~0.5 L/s). Report a threshold sensitivity, for example 0.25, 0.5 and 1.0 L/s, alongside the window sensitivity.

**M3. C has a positive null bias; report a reference level and the signed value.**
Suppose relative velocity directions are unrelated to centroid position, as in near-translation with noisy uᵢ. Then C = |mean of n terms with SD ≈ 1/√2|, and E[C] ≈ √(2/π)·(1/√2)/√n. That is ≈ 0.18 for n = 10 and ≈ 0.20 for n = 8. Low-to-moderate C values are therefore not evidence of circulation.
*Correction:* Report the analytic or permutation null, e.g. shuffling the uᵢ↔rᵢ pairing within a frame, next to the C distribution. Also save the **signed** mean so that rotation sense (positive = clockwise on screen) is not discarded. Label C as a centroid-relative variant, not directly comparable to literature milling indices that use raw velocity.

**M4. Curvature sign: state the anatomical meaning, which is opposite to the turn-rate sign.**
The formula and the description "positive = clockwise head-to-tail in y-down" are geometrically correct. The anatomy works out as follows. With u running head→tail, the tangent points tailward. The center of curvature lies along n = (−y′, x′)/|r′|. For a fish heading +x, that normal is (0, −1), which is the fish's **left**, since the README puts right at heading +90° = (0, +1). So **k > 0 means the body is concave to the fish's left**, which typically accompanies a counter-clockwise turn (negative turn rate). Readers will misinterpret this unless it is stated.
*Correction:* Either state "k > 0 ⇔ concave to fish's left" explicitly, or define k_body = −k so that positive means concave right and matches the turn-rate sign. Specify the parametrization direction (head→tail) in the circular-arc test, along with the expected sign for a known left- and right-bent arc.

**M5. The 1e-4 px distance tolerance may fail spuriously if stored as float32.**
At coordinates around 1000 px, float32 spacing is about 6e-5 px, so recomputed distances can differ by roughly 1e-4.
*Correction:* Record the dtypes of `X`, `Y` and `distance`. If any is float32, use a tolerance tied to dtype precision (e.g. ≤ 1e-3 px, or relative 1e-6) and report the max absolute discrepancy rather than only pass/fail.

## Minor findings

- **Noisy join-adjacent frames still enter retained windows.** Excluding w//2 points removes them as window centers. With w=11, though, the first retained center (index 5) still has the README's 1.5 px-noisy first segment frame inside its window. Drop the first tracked frame of each segment (optionally also the last) before filtering, or exclude w//2 + 1 points. This is cheap and removes the known acceleration spike.
- **Minimum block length.** Require block length ≥ w (strictly, ≥ 2·(w//2) + 1) for each window. Report how many blocks or rows are dropped by nonunit frame jumps.
- **Acceleration noise.** The SG second derivative amplifies noise much more than the first. Report its noise floor next to the acceleration distribution so readers do not take low-magnitude acceleration as signal.
- **Position source for r in B3/B4.** State whether centroid, rᵢ and neighbor deltas use raw or SG-smoothed positions. I recommend the smoothed positions on the same rows used for v in B3, for consistency, and raw positions in B4, where no derivative is needed.
- **Heatmap orientation.** Specify the axis mapping, e.g. horizontal = right, vertical = forward-up, so the body-frame map is not accidentally mirrored. Use the same rotation in the posture figure.
- **Circulation tests.** Add one test with rotation plus a common translation, expecting C = 1 and verifying the mean-velocity subtraction. Add one with reversed rotation, expecting the signed value to flip and C to stay 1.

---

## Independent analytic checks

| Item | Check | Result |
|---|---|---|
| Turn sign | θ = atan2(dy, dx) with y down: increasing θ rotates +x toward +y (down), which is clockwise on screen. The README's right side is θ + 90°, so positive turn = turning right. | ✅ Correct |
| Slip | wrap(atan2(vy, vx) − θ) > 0 means travel is rotated clockwise from heading, i.e. toward the fish's right. Consistent with the turn sign. | ✅ Correct (threshold issue M2) |
| Body frame (B4) | Right unit vector = (−sin θ, cos θ), so right = −dx sin θ + dy cos θ. Forward = (cos θ, sin θ)·Δ. This is an orthonormal rotation and matches the README's "right = heading + 90°". | ✅ Correct |
| Signed curvature | k = (x′y″ − y′x″)/\|r′\|³ equals dθ_tangent/ds and is parametrization-invariant in magnitude. Using u ∈ [0, 1] with \|r′\| ≈ L px per u still gives k in 1/px. A cubic on indices 7..13, evaluated at u = 0.5 (index 10), is centered. A 5-point cubic has 1 residual dof, which is acceptable for sensitivity only. | ✅ Correct (sign interpretation M4) |
| Arc test | Points on a circle of radius R traversed clockwise on screen (θ increasing in y-down) give k = +1/R; counter-clockwise gives −1/R. | ✅ Expected values as stated, once direction is specified |
| Circulation | For rigid rotation about the centroid, uᵢ = ω × rᵢ, so cross(r̂ᵢ, ûᵢ) = sign(ω) for all i and C = 1. For pure translation, uᵢ = 0, all fish are ineligible, and C is undefined (not 0). The cross product rx·uy − ry·ux > 0 means clockwise on screen. | ✅ Correct (null bias M3) |
| Centroid speed | SG is linear, so smoothing and then averaging velocities equals differentiating the smoothed centroid. | ✅ Consistent |
| Polarization | P = \|mean unit heading\| ∈ [0, 1]; P = 1 for parallel headings. It is sensitive to head–tail flips (M1). | ✅ Correct |
| Window durations | 7, 11 and 15 frames at 29.97 fps are 0.234, 0.367 and 0.500 s. | ✅ Matches |
| Derivative treatment | Blocks split at segment changes or frame jumps, with no bridging, matching the README guidance. Using real dt (= 1/29.97 within blocks) as the SG `delta`, w//2 end exclusion, and common eligible rows across windows are all correct. Cubic SG derivatives: the first derivative equals the quartic one and the second equals the quadratic one. That is fine and not a concern. | ✅ Correct (join-noise minor) |
| Angular size | 360/1000 = 0.36 deg per ray. | ✅ Correct |
| Reciprocity | The pooled edge-weighted definition matches the README's "85% of links reciprocated" phrasing, so it is directly comparable as a sanity check. Expected mean out-degree is about 6.8. | ✅ Correct |
| Network coverage | Treating a missing whole frame as unknown is more conservative than the README's pair-absence rule. That is justified, since an all-zero frame cannot be distinguished from a dropped frame without completeness evidence. | ✅ Appropriate |
| Graph direction | Table id1 → id2 means "id1 sees id2"; a later GNN message goes id2 → id1. | ✅ Consistent |

## Limitations (to state in the report)

- The analysis covers a single 10-fish trial. Frames are autocorrelated and the observations are not independent samples, so all percentiles are descriptive only, with no CIs. This is already stated, which is good.
- There is no physical calibration. Normalizing by the median L assumes body_length is stable. That holds for the 10-fish trials but not for the 150-fish trial (about 15% short), which matters for later extension.
- Velocities are noncausal smoothed estimates. Heading, curvature and slip at low speed or small bends are bounded by tracker noise, about 0.5 px.
- Cross-segment identities were reconstructed. The metrics here do not depend on them, but any future per-fish pooling across segments inherits the ambiguities (12/1,980 near-ties).
- The visual network is a geometric reconstruction (four-point outlines, no transparency). It is derived, not observed, and does not establish influence.
- Arena or wall geometry is unvalidated, so occupancy maps and spacing near walls are confounded by boundaries.
- Video alignment is good only to about one frame, and overlay checks are qualitative.
- Persistence metrics and all-trial analysis are deferred, as stated. This review does not cover them.