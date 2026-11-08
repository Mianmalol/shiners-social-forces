# Publication review: ten-trial descriptive package

**Reviewer:** Claude (claude-opus-5-5), tool-free static review of the supplied text snapshot
**Verdict: PASS** for publishing this clearly caveated descriptive package.

I found no blocker. Every number I checked in the session account, status page and eligibility diagnostic agrees with the supplied tables, JSON and code. The new script reproduces the original reporting rule. It verifies exact accepted-frame masks rather than counts alone, and it writes no primary outputs. The numbered findings below are minor clarity or reproducibility edits; none needs a rerun.

This PASS covers a static review of the supplied text only. It is not independent computational reproduction, image inspection, a GitHub CI result or a whole-repository security check.

---

## Basis of evidence

- **My own work:** arithmetic on supplied tables and JSON; reading `metrics.py`, `plot_eligibility.py`, its tests, the workflow YAML and the reproduction instructions.
- **Implementer-reported, not mine:** the 137 tests and 17 subtests; the validator outcome; hash matches; pilot parity; the 50 sampled P recalculations; figure inspection; and the claim that primary sources and trial outputs are unchanged.

## Checks against the task

### 1. Session account: accurate and adequately complete ✓

| Claim | Evidence I checked | Result |
|---|---|---|
| 10,827,539 / 266,688,111 / 239,246 | `validation.json` totals | ✓ |
| 22 nonpositive lengths across 14 trial-frames | Summed `nonpositive_length_rows` (0+0+1+2+2+0+8+6+2+1) and frame counts (0+0+1+1+2+0+4+3+2+1) in `trials.csv` | ✓ |
| Largest median shifts 0.000110 (P), 0.0000731 (C) | 0107 P shift = 0.5086190 − 0.5085093 = 0.0001097, consistent. 0107 C (4.5e-5) and 0124 C (0) are below the stated maximum | Partly ✓; other trials not in packet |
| P ranges 0.894–0.943 / 0.809–0.827 / 0.509–0.694 | `trials.csv` | ✓; nonoverlap holds |
| 70-fish trials slower than every 10- and 30-fish trial | 0.713–1.160 vs ≥1.376 BL/s | ✓ |
| Nearest-neighbour spacing about 1 BL | 0.876–1.467 | ✓ |
| 151: P = 0.641, C = 0.484, both inside 70-fish ranges | 0.6406 ∈ [0.509, 0.694]; 0.4837 ∈ [0.379, 0.781] | ✓ |
| Coverage rises to 74.6% / 79.1% at 0.25; zero at 1.0 | `thresholds.csv` | ✓ |
| "Much of" the C change comes from frame selection | 0107: 0.441→0.742 on shared frames vs 0.781 (≈88%). 0124: 0.524→0.639 vs 0.681 (≈73%) | ✓ |

The account covers everything the task lists:
- **Replication unit:** one trial per estimate; row counts are measurement volume, not replicates.
- **Exclusions:** boundary trimming, heading masks, collapsed-pose handling.
- **151-fish caveats:** separate camera and body-length discrepancy.
- **Exposure:** all ten trials explored, so none is an untouched validation set.
- **Open gates:** video checks, local alignment, independent reproduction and response models.
- **Causal claims:** none are made.

### 2. Eligibility numbers ✓ (independently recomputed from histograms)

| | 0107 | 0124 |
|---|---|---|
| Sum of histogram bins at ≥56 fish | 539+540+430+327+245+217+145+67+60+17+11 = **2,598** ✓ | 286+…+1 = **1,438** ✓ |
| Total histogram frames | 24,494 = 24,578 − 84 ✓ | 24,449 = 24,533 − 84 ✓ |
| Median qualifying count | Cumulative 12,043 at ≤40 and 12,737 at ≤41, with half of 24,494 = 12,247, so **41** ✓ | 11,474 at ≤40 and 12,525 at ≤41, with half = 12,225, so **41** ✓ |
| Required count | First k with k/70 ≥ 0.8 gives **56** ✓ | **56** ✓ |

**Independent derivation of the 84 undefined frames:** the trim is half-window + 1 = 6 samples at each end of each block. That gives 6 × 2 × 7 segments = 84. This matches both trials and confirms the undefined frames are boundary trimming, not missing tracking.

The script's check that undefined velocity equals undefined eligibility rules out geometry as a separate cause. Both the JSON (`"These components are not separately audited"`) and the narrative ("not the fraction of time spent circling") keep the two required distinctions: eligibility is not milling time, and the radius and speed criteria are not audited separately.

### 3. Alignment, circulation and scope qualifiers ✓

- Ordering is described as descriptive across 10/30/70 only.
- The 151 trial is described as consistent with, but not extending, the ordering.
- C is "neither angular speed nor a validated milling classifier."
- Duration matching is "approximately matched duration" in methods; the narrative avoids over-claiming.
- Video limits are stated ("No additional video inspection was performed").
- Body scale is "not centimeters."
- Visibility is "ray-cast geometric access, not attention or influence."
- No causal or untouched-validation claim appears.

### 4. Eligibility code and tests ✓

**Rule fidelity.** `required` uses the same `k/fish >= fraction` float comparison as `metrics.collective` (`eligible.mean(axis=1)` gives sum/n). This avoids ceil errors at exact boundaries such as 56/70. The accepted mask `counts >= required` matches `valid = all_valid & fractions >= min_fraction & counts > 0`, because `required ≥ 1` whenever fraction > 0.

**Mask verification.** `np.array_equal(accepted_mask, isfinite(circulation))` checks frame-by-frame identity, not just totals. `test_count_match_alone_does_not_hide_wrong_accepted_frames` exercises exactly this case with a count-preserving swap.

**Frozen inputs.** The script checks:
- `summary.json`, `config.json` and `collective.csv` hashes against `provenance.json`;
- the `metrics.py` hash against the frozen run's source hash;
- the summary's `n` and coverage against the reconstructed values.

It writes only figure 05, `circulation-eligibility.json` and its manifest, so primary outputs cannot be silently changed.

**Tests.** I traced all six tests and the nine mutation subtests by hand. Each raises at its intended check given the order of checks in the script. Examples:
- The 151-fish case requires 121 fish, since 120.8 rounds up.
- The mixed fixture has median 55 over [0, 41, 55, 56, 70].
- The `.501 × 70` mutation fails integer reconstruction.

The counts 6 + 131 = 137 and 9 + 8 = 17 are consistent with the publication log.

### 5. Reproduction instructions ✓, with notes 2–3 below

- The commands use a fresh `reports/comparison-rerun` root and a fresh pilot output path.
- They state that ignored frame tables must be regenerated, that retained provenance holds historical absolute paths, and that `--resume` is not a portable cache.
- Member CRC and extracted SHA256 are consistently distinguished from a full-archive SHA256 check, in the README, the session account and the fetcher code.
- CI is offline unit and synthetic testing only. The workflow has no data fetch, `contents: read`, pinned checkout and pinned uv. The session account says CI runs "without raw-data downloads."

### 6. CI and merge claims ✓

No text claims that CI passed or that a merge occurred. The forward links to `reviews/publication/` are expected, per the task.

---

## Findings (all non-blocking)

**F1 — `status.md` publication row could be read as recording CI results.**
"AUTHORIZED; review and checks recorded with this package … and PR CI" could imply CI evidence already exists.
- *Fix:* "PR CI results and merge state: see the GitHub PR (pending at time of writing)."
- *Verify:* no present- or past-tense CI-pass wording remains before the checks actually run.

**F2 — The eligibility manifest's `reproduce` command contradicts the fresh-output guidance.**
`circulation-eligibility-manifest.json` says `python scripts/plot_eligibility.py --root reports/comparison`. In a fresh checkout `collective.csv` is gitignored, so this fails with a missing-file error. Where it does run, it rewrites committed outputs, because the script has no refuse-to-overwrite guard unlike `run_comparison.py`. The `--root` default also points at the retained report.
- *Fix:* change the manifest string, or add a note, to say it requires regenerated `collective.csv` and should target a rerun root, e.g. `uv run python scripts/plot_eligibility.py --root reports/comparison-rerun`. Optionally refuse to overwrite existing outputs.
- *Note:* collective.csv hashes listed in the manifest cannot be checked from Git alone. Saying so would be helpful.

**F3 — The validator's exact pilot parity may not hold on another platform.**
`check_pilot` requires exact JSON float equality. A fresh rerun on different hardware or BLAS could differ in the last bits even with `uv.lock`. A failure there would not indicate a scientific defect.
- *Fix:* one README sentence explaining this, or a documented tolerance path for independent reproducers.

**F4 — No recorded inspection of the new figure.**
The coordinator inspection evidence (`validation.md`, `status.md`) covers "all four final figure sets." Figure 05 is new, embedded in the report, and I cannot view it.
- *Fix:* record that the coordinator inspected `05-circulation-eligibility.png/svg`, including bar colours, the 56-fish line and readable footnote text. Otherwise the session account's "inspected the figures" is slightly broader than the evidence.

**F5 — Some current-facing documents keep pre-publication wording.**
- `reports/comparison/validation.md` says it "supports the local descriptive report."
- `docs/comparison-methods.md` says "No … publication is included."
- `docs/methods.md` says "implementation review remains pending."

The two methods files are hash-pinned in every trial's provenance and in `validation.json`. Editing them would break `validate_completed` and resume verification, so they should **not** be edited.
- *Fix:* add a one-line pointer in `validation.md`, the session account, or the README noting that the hash-pinned methods files preserve their run-time status text.

**F6 — Trivia.** `status.md` has "0107 and0124" (missing space). The comparison README's "131 tests" is correct for the comparison run but is not the latest suite count; a pointer to the publication log would help.

## Optional suggestions

- Record the Python version in the eligibility manifest alongside the package versions.
- Note in the eligibility JSON that the 84 undefined frames equal the expected trim (6 × 2 × 7), so readers can see they are structural.

---

## Not executed or not verifiable from this packet

- **Not run by me:** any code, tests, the validator, the pipeline or CI. I recomputed nothing from raw tracks or networks.
- **Not viewed:** any PNG or SVG, including figure 05.
- **Hashes:** not checked against actual files. Whether primary sources and trial outputs are unchanged is coordinator-reported.
- **Missing from packet:** `collective.csv`, `provenance.json` and the remaining eight trial summaries. The nonpositive-length shift maxima for those eight trials and the matched-prefix values rest on earlier reviews.
- **Provenance key format:** not checked. The script's lookup assumes relative keys such as `src/shiners/metrics.py`; the successful manifest implies this, but I could not see `provenance.json`.
- **Other tests:** not inspected for hidden network or data access. "Mocked" is implementer-reported.
- **Out of scope:** whole-repository security review, release-asset integrity, the `mirror-data.yml` workflow, the `claude_review.py` threat model, and the targets of the forthcoming review and adjudication links.

The independent computational reproduction and video-validation gates remain open, as the package itself states.
