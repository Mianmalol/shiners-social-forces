# Decisions

## 2026-11-07: roles and first task

Marco authorized OpenAI coordination/implementation and automatic Claude reviews. The active Codex model is the implementer; its exact API model identifier is not exposed in this workflow. The first Claude response identifies `claude-opus-5-5`; this was the local configured/default model, with no fallback requested. Pilot scope is trial 0066; all-trial atlas remains future work.

## 2026-11-07: review mode and provenance

Use tool-free snapshot reviews through Claude Code. Each prompt contains exact source text and hashes; reviewers cannot mutate project files or run commands. This is independent scientific/code reasoning, NOT independent computational reproduction. Synthetic tests and actual runs are executed by the OpenAI coordinator. M1's strict independent-execution gate and final report release gate remain pending even if static review passes. No autonomous claim of final scientific verification.

Preserve current dirty workspace and preexisting pilot. No commit or push in this task. Reviews use frozen input snapshots; local HEAD alone does not identify the new work.

## 2026-11-07: initial Claude findings

Source: reviews/M0-initial/review.md. Verdict CHANGES_REQUESTED.

| Finding | Resolution planned/applied in implementation | Evidence required |
| --- | --- | --- |
| Heading flips | Flag adjacent heading jumps >pi/2; mask SG support for turn/slip and exclude suspect polarization frames; report midline-axis disagreements | Synthetic jump test and actual flag counts |
| Low-speed noise | Raise primary direction threshold to .5 BL/s; report .25,.5,1.0 sensitivity; residual/kernel noise diagnostic explicitly approximate | Threshold table, residual diagnostic |
| Positive circulation bias | Save signed circulation and illustrative 1/sqrt(pi*n) reference; explicitly not calibrated for centroid-relative dependent vectors | Circle/reversed/translated synthetic checks; caption limitation |
| Curvature anatomy | Preserve geometric head-to-tail sign; explain its relation to anatomical concavity and no direct turn inference | Signed arc tests and methods |
| Float precision distance | Use 1e-4 px float64 or 1e-3 if any input float32; record actual dtypes/error | Actual quality output |
| Join-neighbor noise | Drop half-window+1 centers at both ends of continuous blocks | Boundary test |
| Centroid position source | Use SG-smoothed positions for circulation, raw positions for spacing | Methods and code |

These are dispositions, not proof of completion; the implementation handoff and review must supply evidence.

## 2026-11-07: implementation review M1-implementation

Claude Opus 5.5 requested three bounded fixes. It found no arithmetic defect invalidating a reported value, but static review alone cannot confirm images or raw-data behavior.

- F1: distinguish transition masks from sustained heading errors. Added event IDs/frames, opposite-motion counts before masks, longest contiguous run per fish, and a synthetic flip/unflip test. The two large transitions occur on different fish; they do not form a same-fish flip/unflip pair. Reverse-motion candidates are explicitly unresolved, not automatically corrected or called proven flips.
- F2: disclose that the P–C plot is conditioned on relative-motion eligibility (46.6% of frames at the chosen threshold), and save eligible/ineligible P summaries. No whole-recording joint-distribution claim.
- F3: include speed/curvature sensitivity tables and numbers in the new review packet and summary.
- Minor follow-ups: state raw-heading occupancy limitations; distinguish smoothed spread from raw spacing; explicitly defer relative-heading distributions; hash the fetch script and require fetch provenance. The three plotted posture examples were visually checked and are not clipped.

Source/method changes invalidate the prior run's provenance for the current implementation. Regenerate to reports/pilot-0066-reviewed and send a new frozen review packet. Do not overwrite the original Claude findings.

## 2026-11-07: follow-up static review accepted

Claude M1-fixes returned PASS for the stated tool-free static scope with no remaining material corrections. Coordinator accepted that limited verdict and applied optional report wording clarifications (joint eligibility percentage, specific masked metrics, low-speed blind spot). No further numerical/source implementation changes followed the reviewed snapshot. Do not relabel this as independent computational reproduction, validated anomaly identities, or a final scientific release.
