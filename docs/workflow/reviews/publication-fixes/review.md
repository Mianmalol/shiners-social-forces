# Focused publication confirmation: ten-trial descriptive package

**Reviewer:** Claude (claude-opus-5-5), tool-free static review of the supplied text
**Verdict: PASS.** All six findings (F1–F6) are adequately resolved in the supplied final files. The new prerequisite command is consistent with `scripts/run_comparison.py`. No material issue remains.

This PASS is a static reading of the supplied text only. I did not execute code, view figures, check hashes against files, or certify the whole repository. It does not close the independent computational reproduction or video-validation gates. CI and merge remain pending; the GitHub PR is the authority for both.

## Disposition of F1–F6

| Finding | Evidence in final files | Status |
|---|---|---|
| **F1** CI ambiguity | `status.md` Publication row: "PR CI results and merge state: see the GitHub PR (pending at this document's preparation)." No text claims CI passed or a merge occurred. The session account says only what CI *runs*. | Resolved |
| **F2** Manifest command | `reproduce` now targets `reports/comparison-rerun`. `prerequisites` gives the fetch step and a two-trial regeneration command. `git_only_verification_limit` states that `collective.csv` hashes cannot be checked from Git alone. | Resolved; see command check below |
| **F3** Strict pilot parity | README: last-bit differences across hardware or libraries require investigation and are "not automatically a scientific discrepancy." The validator is unchanged. | Resolved |
| **F4** Figure 05 inspection | `status.md` records coordinator inspection of the PNG: colours, the 56-fish threshold, counts and footnotes. It says the SVG was retained but not separately viewed, and that Claude viewed neither. | Resolved; the scope is stated accurately |
| **F5** Historical status text in hash-pinned methods | README's closing paragraph marks those sentences as historical and points to `status.md` and the PR. The frozen methods files are unedited, which is correct given the provenance pins. | Resolved |
| **F6** Typo and stale count | `status.md` now reads "0107 and 0124." The comparison README distinguishes the original 131 tests + 8 subtests from the publication suite's 137 + 17. | Resolved |

The optional Python-version suggestion was also adopted: the manifest records `"python": "3.13.9"`.

## Prerequisite command checked against `run_comparison.py`

`uv run python scripts/run_comparison.py --trial 70-fish__0107 --trial 70-fish__0124 --output-root reports/comparison-rerun/trials`

- **Trial selection:** `--trial` uses `action='append'`, so repeating it selects both trials. Both names appear in `configs/comparison.json` `trials` and match the safe-name regex. `selected ⊆ configured` passes.
- **Defaults:** `--config` defaults to `configs/comparison.json`. Its SHA256 `bd59f69f…` equals both trials' `config.json` input hashes in the manifest. `--data-root` defaults to `data/trials`, which matches the README fetch location.
- **Fresh output:** a new output root does not exist, so the nonempty-output refusal is not triggered. Each trial runs `shiners.compare_trial` in a fresh process. `downloads_ready` requires completed fetch provenance, which is covered by the fetch prerequisite.
- **Plotting compatibility:** `plot_eligibility.load_trial` reads only `trials/<stem>/…` for the two `TRIALS`. A two-trial rerun root is therefore sufficient for `--root reports/comparison-rerun`.
- **Path handling:** the relative `--output-root` resolves against the current directory. The README commands assume the repository root.

## Residual non-blocking notes (no action required for PASS)

1. **Provenance key format is still unverified.** `load_trial` looks up `source_hashes["src/shiners/metrics.py"]` and the bare `output_hashes["collective.csv"]`. The README says saved provenance "retains the original run's absolute paths." If a fresh run recorded absolute *source* keys, the plot script would fail its metric check. The original successful manifest suggests keys are relative, and `validate_completed` accepts both forms. I cannot see `compare_trial.py` or `provenance.json`, so this remains as stated in the initial review.
2. **`original_output_root` naming.** In a rerun, this field records whatever `--root` was used, such as `reports/comparison-rerun`. The adjudication's description ("preserves run context") is accurate, but the field name slightly overstates "original."
3. **No overwrite guard.** The script still defaults to `--root reports/comparison` and overwrites outputs without a guard. The manifest no longer recommends that root, and input-hash checks prevent use of mismatched inputs. This is optional hardening.
4. **Regenerated outputs.** Regenerating the manifest re-ran the script, which re-wrote figure 05 and the eligibility JSON. Whether those output hashes are byte-identical to the previously reviewed outputs is coordinator-reported ("all 13 eligibility manifest hashes matched"). I could not check it.
5. **Rounding trivia.** `status.md` says "within 2.23e-16"; the session account and comparison README say 2.22×10⁻¹⁶ (2.220446…e-16). Both are true, but the rounding differs.

## On the adjudication's interpretation guard

I accept the coordinator's correction. My initial review said the undefined-velocity/undefined-eligibility mask check "rules out geometry as a separate cause." That was too broad. The check shows only that the *undefined* frames are explained by undefined velocity. Among defined frames, it cannot separate radius-guard failures from relative-speed failures. The report and eligibility JSON ("These components are not separately audited here") already state the narrower claim correctly.

## Evidence basis and limitations

- **My own reasoning:** reading the supplied README, `status.md`, session account, comparison README, both eligibility files, `run_comparison.py` and the config. I also compared the header SHA256 values the packet supplied for consistency: the script hash `692a05ed…` matches the manifest's `source_hashes`, and the config hash matches the per-trial `config.json` hashes.
- **Implementer-reported, not verified:** 137 tests + 17 subtests; 113 primary source-hash checks and 13 eligibility hashes matching; unchanged primary measurements, configs and outputs; coordinator inspection of the PNG; CI configuration behaviour.
- **Not executed or not available:** any code, tests, validator or CI; any PNG or SVG; real file hashes; `compare_trial.py`, `fetch_trials.py`, `provenance.json`, `collective.csv`, `validation.md`; the diff against the previously reviewed files; the whole repository.
- **Gates still open:** independent computational reproduction, video validation, and PR CI and merge.
