# Coordinator disposition: results review

Claude Opus5.5 returned **CHANGES_REQUESTED, narrative only**. It reported no numerical contradiction or code defect requiring a rerun. The primary results, figures and their provenance remain unchanged.

| Finding | Change |
| --- | --- |
| B1: P smoothing robustness overstated | Removed smoothing from the independent robustness list and Monday summary. Explicitly state that P uses raw headings; SG window choice changes only the heading-mask support. Mask changes could in principle alter P summaries, so the review's stronger phrase “cannot fail by construction” is not adopted. |
| B2:151 observation missing from short summary | Monday summary now explicitly states that the151 alignment lies within the70-fish range and does not extend the ordering. |
| B3: precision | Table now reports P coverage to two decimal places, showing99.95% for0126. The validation difference is given exactly as2.220446049250313e-16 with an approximate2.22e-16 reading. The earlier “at most2.23e-16” was a valid conservative bound; this is a precision clarification, not a computational correction. |
| B4: spread lead too broad | Lead now states10-to30 separation but30/70 overlap at full duration, with separation only in the matched prefix. Adds that some footprint growth is geometrically expected at comparable spacing. |

Optional suggestions incorporated without new analyses: note the co-occurrence of lower speed and lower P at70; clarify that the80% eligibility rule and fish-speed dependence prevent treating coverage as a group-size-neutral behavioral duration; disclose positive signed-curvature medians without interpreting them as bending intensity; mention occlusion geometry in visual-access interpretation; list clustered heading-event windows as future video-inspection targets. The suggested windows were checked against saved heading_events.

All ten full trial summaries were supplied in the immutable review packet. The reviewer explicitly did not check every nested field and relied on the comparison tables for some trials. It executed no tests, inspected no rendered images and did not reproduce the pipeline. Acceptance is for sharing a descriptive local report with its caveats, not independent computational certification or scientific publication.

Focused confirmation of these narrative changes is recorded separately in comparison-results-fixes.
