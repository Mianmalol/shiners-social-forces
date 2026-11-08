# Coordinator disposition: comparison plan

Claude returned **CHANGES_REQUESTED** for its tool-free plan review. The coordinator accepted the six scientific concerns before viewing cross-trial results. This record describes the resulting analysis design; implementation and results require a separate review.

| Finding | Disposition |
| --- | --- |
| M1: whole-frame heading exclusion depends on N | Add P coverage and reasons, raw P, affected-fish-only P with at least80% valid headings, n retained, and common-frame summaries. Preserve the pilot definition as primary. |
| M2: finite-N reference for P | Save and plot sqrt(pi/(4n)), explicitly the approximate mean under iid uniform headings, not an expected median, calibrated null, or correction. |
| M3: N=151 length scenario | Extend algebraic L*1.15 scaling to all L-normalized track outputs and recompute cutoff-sensitive statistics. Stored outlines and their visual network cannot be repaired by this unit change. Exclude N=151 from claims of curvature or visibility changing with N. |
| M4: duration, timing, segments, chirality | Summarize the first17,999 observed frames of every trial, preserving joins/gaps. Source README explicitly declares29.97fps; independent video timing remains unchecked. Use actual segments and do not compare rotation sign across cameras. |
| M5: threshold selection versus fish composition | Separate fixed0.5-cutoff C evaluated on each threshold's overlapping valid frame set from varying-cutoff C on common high-relative-motion frames. State that this common set is selected. |
| M6: predeclare consistency | Before examining results, require nonoverlapping ranges of trial medians in the same order at adjacent N=10,30,70 for a strict monotone descriptive pattern. Treat N=151 only as a single external observation consistent/inconsistent with that ordering. No significance or causal claim. |

The reviewer did not run code, inspect images, or reproduce data. The timing concern is treated as an unverified source convention, not evidence that the source frame rate is wrong. Hypothesized effects of shortened outlines on visibility are not measured corrections and will not be claimed as established directional biases.
