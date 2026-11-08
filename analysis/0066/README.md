# First audit: 10-fish/0066

Measured from the two release Parquet members on November 5, 2026. This is one
trial, not a whole-dataset quality claim. No video overlay was inspected.

| Measure | Result |
| --- | ---: |
| Track rows / columns | 245,780 / 56 |
| Fish / tracked frames | 10 / 24,578 |
| Frame range | 1–24,584 |
| Directed visibility rows | 1,662,869 |
| Track / network null cells | 0 / 0 |
| Nonfinite numeric track cells | 0 |
| Mean visible neighbors | 6.766 of 9 |
| Directed links with reverse link present | 85.08% |
| Median body length | 38.99 px |
| Median heading polarization | 0.894 |
| Median smoothed speed | 1.453 trial-median body lengths/s |
| 5th–95th percentile smoothed speed | 0.355–3.532 body lengths/s |

All natural keys are unique, every network endpoint has a corresponding track,
there are no self links, and each fish/segment has contiguous frames and regular
timestamps. Both tables are complete at the cell level. This does not establish
tracking accuracy, identity correctness or video alignment.

Missing frame numbers inside the trial range are 3597, 7193, 10790, 14386, 17982,
and 21579. These divide seven segments; the final segment is shorter (3005 frames).
Never estimate derivatives or construct rollout windows across these boundaries.

Polarization is the magnitude of the mean unit body-heading vector: 1 means
perfect alignment. Its high median and repeated low excursions motivate comparing
collective states; low polarization alone does not distinguish milling from disorder.

Speed uses a cubic 11-frame Savitzky–Golay derivative, independently per fish and
segment, dropping five frames at either end. This is an exploratory, noncausal
smoother. Test other bandwidths before interpreting accelerations as responses.

Files: `audit.json` contains the numerical results and checks; the two CSVs profile
all columns; `overview.png` shows a snapshot, heading polarization and speed.
The snapshot lines show visible pairs without encoding direction; arrows show
fish headings, not influence. See ../../docs/modeling-start.md for the modeling plan.
