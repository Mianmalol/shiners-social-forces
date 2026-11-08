# Workflow status

Updated November 7, 2026. Roles: OpenAI coordinator/implementer; Claude independent reviewer. Marco has authorized publication and merging this descriptive package into GitHub main. The [session account](../session-summary.md) summarizes the work and its scientific limits.

| Task | State | Evidence / next action |
| --- | --- | --- |
| M0 methods | Review corrections incorporated | Claude Opus 5.5 initial review, decisions.md, and M1-fixes confirmation |
| Review bridge | IMPLEMENTED; live exchanges successful | scripts/claude_review.py; saved inputs, hashes, model identity, responses and failure handling |
| Pilot data | Downloaded and member-verified | Ignored data/0066; extracted file SHA256; no full-archive SHA256 claim |
| M1 five-chapter pilot | READY_FOR_REVIEW: static PASS, independent execution pending | reports/findings.md; reports/pilot-0066-reviewed; 57 tests and 8 subtests passed by coordinator |
| Claude implementation review | PASS for tool-free static scope | reviews/M1-fixes/review.md and adjudication.md; no remaining material correction |
| Video correspondence | Selected examples inspected by coordinator | Three predefined track frames, both i−1 and i; qualitative only |
| Heading anomalies | Disclosed; targeted video review pending | 266 opposite-motion candidate rows; longest run fish 3, frames 15808–15830; not proven flips |
| Independent computational reproduction | PENDING | Reviewer must independently rerun pinned source snapshot/environment/data; tool-free review does not satisfy this gate |
| M2 all-trial measurement audit | COMPLETE for requested measurements | All ten track tables and every network row processed; 22 nonpositive-length observations across 14 frames disclosed and tested with exclusions; unused pose columns/additional video inspection remain outside scope |
| M3 all-trial descriptive comparison | COMPLETE for descriptive scope; independent reproduction pending | reports/comparison/README.md; four original PNG/SVG figure sets plus circulation-eligibility diagnostic; all ten trial summaries; threshold, duration, heading, geometry and scale sensitivities |
| Claude comparison implementation review | PASS for tool-free static scope | reviews/comparison-implementation/review.md and adjudication.md; no primary rerun requested |
| Claude comparison results review | PASS after narrative corrections | reviews/comparison-results-fixes/review.md and adjudication.md; share locally with caveats; independent execution still pending |
| Publication | AUTHORIZED; local checks pass and Claude static review is PASS | Session account, publication review/disposition and publication test log. PR CI results and merge state: see the GitHub PR (pending at this document's preparation). Scientific reproduction gate remains open. |

## Commands actually completed

- `uv sync`: environment and lockfile created.
- `python3 scripts/fetch_pilot.py --video`: tracks, network and video fetched using checked ranges and ZIP CRC verification.
- `.venv/bin/python -m pytest -q`: final run 57 passed, 8 subtests passed; log in reports/test-results-final.txt.
- `.venv/bin/python -m shiners.pilot --output reports/pilot-0066-reviewed`: final retained run.
- Source and output hashes checked against provenance after generation; local links and Git whitespace check passed.
- Claude: one methods review, one implementation review and one focused fix review. All resolved to model claude-opus-5-5; default configured selection, no fallback.
- All-trial extension: downloaded member-verified track/network tables for all ten trials (~7.53 GB); no additional video downloads.
- `scripts/run_comparison.py`: completed all ten trials under identical analysis source/config and Python/package versions. An initial run stopped on invalid lengths; it remains preserved in ignored .cache, and all retained trials were regenerated after explicit handling was added.
- Original comparison suite: 131 tests and 8 subtests pass; reports/test-results-comparison.txt. Publication suite: 137 tests and 17 subtests pass; reports/test-results-publication.txt.
- `scripts/plot_comparison.py` and `scripts/compare_threshold_pairs.py`: four complete figure sets, compact comparison tables and 30 explicitly exploratory threshold pairs.
- `scripts/validate_comparison.py`: all hashes and counts passed; exact pilot parity; 50 independent sampled P calculations agree within 2.23e-16. Evidence in reports/comparison/validation.json. All four final figures visually inspected by coordinator.
- Claude comparison plan review: corrections incorporated before interpreting results; implementation snapshot subsequently passed. Separate results review requested narrative corrections only; focused confirmation returned PASS. Both snapshots and coordinator dispositions are retained.
- Publication preparation adds a reproducible eligibility diagnostic and a Python 3.11/3.13 CI workflow. The [publication test log](../../reports/test-results-publication.txt), [Claude publication review](reviews/publication/review.md), and [disposition](reviews/publication/adjudication.md) preserve the additional evidence; the GitHub PR records remote checks and merge state.
- The coordinator visually inspected the new `05-circulation-eligibility.png`: blue/orange bars, the 56-fish threshold, counts, and footnote text are readable and consistent with the JSON table. Matching SVG output is retained; Claude did not view either rendering.

## Next bounded task

Inspect selected high-C intervals from 70-fish/0107 and 0124 and known heading events against video, compare local versus global alignment, and arrange independent computational reproduction. Response laws, leadership, calibrated null models and persistence extensions remain future scientific tasks. Observed ordering across recorded trials does not establish a causal group-size effect.
