# Publication review disposition

**Accepted for publication as a descriptive research package, subject to successful
PR checks.** Claude Code returned `claude-opus-5-5`, verdict PASS, with no material
blocker. Marco explicitly authorized pushing and merging to main. This acceptance
does not close independent computational reproduction or video-validation gates.

The initial review inspected 34 explicit text files (417,015 input bytes); their
hashes and exact contents are preserved in the adjacent manifest and snapshot.
Claude checked supplied numerical evidence, formulas, code, tests and wording. It
did not execute code, inspect rendered figures, verify file hashes, or check GitHub.
The other eight detailed trial summaries were outside this publication packet;
prior results reviews cover that wider comparison. No whole-repository security
audit or full dataset re-download is claimed.

All six non-blocking findings were addressed:

| Finding | Disposition |
| --- | --- |
| F1: CI status could be ambiguous | Current workflow status explicitly says PR CI and merge were pending at preparation; the PR is the authority for actual remote state. |
| F2: eligibility manifest regeneration command | Manifest guidance now uses a fresh rerun root, gives the two-trial prerequisite command, and states that omitted frame-table hashes cannot be checked from Git alone. The script's original-output-root field preserves run context. No primary measurement or output changed. |
| F3: exact pilot parity across platforms | README explains that last-bit numerical differences require investigation and are not automatically scientific discrepancies. The strict validator remains unchanged. |
| F4: new figure inspection | Workflow status records coordinator visual inspection of the PNG, including colors, threshold, counts and footnotes. Claude did not inspect images. |
| F5: historical methods status | README identifies the hash-pinned methods' run-time status sentences as historical and points to current workflow state. Frozen methods files remain unchanged. |
| F6: stale count / typo | Comparison report distinguishes the original 131-test suite from the publication suite of 137 tests and 17 subtests; spacing typo fixed. |

The optional Python-version metadata suggestion was also incorporated. The original
review remains immutable. Subsequent edits are limited to those documented clarity
changes and eligibility regeneration metadata, followed by a focused confirmation.
That [confirmation returned PASS](../publication-fixes/review.md); see its
[final disposition](../publication-fixes/adjudication.md).

Coordinator evidence: the full publication suite passed 137 tests and 17 subtests;
113 retained primary source-hash checks and all 13 eligibility manifest hashes
matched. The PNG was visually inspected. Synthetic/unit CI separately checks
Python 3.11 and 3.13; it does not reproduce the real-data analysis independently.

One interpretation guard applies to the review text: matching undefined-velocity
and undefined-eligibility masks explains which frames lack a computable result;
it does not separate radius failures from speed failures among defined frames.
The report and eligibility JSON retain that distinction. The 151-fish point lies
inside the 70-fish range and does not extend the monotone 10→30→70 ordering.

Current source/config and primary trial results remain unchanged from their saved
provenance. Generated SVG whitespace, intentional Markdown line breaks and original
review text are preserved rather than normalized, to avoid rewriting evidence.
