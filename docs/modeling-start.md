# Starting social-force inference

## Context and scope

The earlier “Decode golden shiner dataset” chat describes the team objective as a
GNN integrated with a Neural ODE, comparing pairwise and higher-order interactions.
The current repository is a dataset mirror, not an existing training implementation.
The source paper studies visual detection; it does not provide ground-truth social forces.
Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC8261228/

The source README documents 10 trials: three each with 10, 30 and 70 fish, and one
with 151 fish. Positions, measured headings, lengths, 21 midline points and eyes
are provided at approximately 29.97 Hz. Visual-network tables encode directed
visibility. Video is useful for verifying tracks, posture and arena geometry.

## First experiment

Use 10-fish/0066 to develop and audit the loader. Before fitting, reserve 0105 for
validation and 0126 for testing; with only three trials, later rotate the held-out
trial to assess robustness. Segments from the same trial are not independent
replicates. Do not randomly split overlapping windows or fish from the same frames.
Evaluate larger group sizes separately as generalization tests, accounting for the
151-fish trial's different camera and documented body-length mismatch.

1. Validate unique (trial, frame, fish) keys, finite data, constant fish counts,
   segment boundaries, network endpoints and video alignment.
2. Estimate velocities, turning and acceleration within continuous fish/segment
   blocks. Sweep smoothing windows rather than accepting one arbitrary derivative.
   Exclude boundary frames affected by smoothing. Centered smoothing is suitable
   for exploratory derivatives but must not leak future data into forecasting
   inputs; use causal filters for input states and a split/window guard interval.
3. Establish constant-velocity and self-motion baselines. Add wall distance and
   wall-normal direction after checking the arena geometry against video. Image
   borders are not automatically tank boundaries.
4. Fit an interpretable pairwise model before a flexible GNN. Compare metric-radius,
   nearest-neighbor and visibility-based graphs under the same evaluation protocol.
5. Add posture and then explicit higher-order terms only if held-out results improve.

## State and interaction representation

Use a common length scale (estimated on training data) and seconds. Keep trial
scale differences explicit; do not normalize each frame with a noisy fish length.
Measured body heading and velocity direction are separate quantities. Represent
orientation as sin/cos, and unwrap it within segments when taking derivatives.
Define signed midpoint curvature explicitly from a smoothed local midline fit,
including the head-to-tail convention and the y-down sign; it is not supplied as
an independent measured scalar. Its noise and redundancy with turning need checking.

For focal fish i and neighbor j, rotate displacement and relative velocity into
i's body frame. In image coordinates, forward=(cos(theta),sin(theta)) and
right=(-sin(theta),cos(theta)). Candidate features are forward/right displacement,
relative heading, relative velocity, distance, visibility and angular size.

A useful initial equation is:

    acceleration_i = self_motion(state_i) + wall_response(i)
                     + sum_j weight_ij * pair_response(state_i, state_j) + residual_i

Also compare predicting speed change and heading turn rate directly. These are
effective behavioral responses, not calibrated Newtonian forces: mass, physical
length calibration, propulsion and hydrodynamic contributions are not separately
identified by these observations.

`id1` is the observer, `id2` the observed fish. For conventional source-to-target
GNN message passing, use source=id2, target=id1. Missing rows mean invisible only
within frames with valid network coverage. Visibility is a model-derived geometric
feature, not attention, identity embedding or proof of influence. Its ray casting
already includes third-fish occlusion: distinguish additive pair responses gated
by group-dependent visibility from explicitly higher-order response functions.

## Evaluation and Neural ODE considerations

Report short-horizon position/heading errors and rollout behavior: polarization,
spacing, speed, turning, collisions and boundary violations. Compare equal-capacity
baselines and trial-level uncertainty; millions of frames are not millions of
independent behavioral samples. Condition neighbor-response maps on focal speed,
wall proximity and collective state before interpreting attraction or repulsion.

For autonomous rollout, recompute geometry and graph features from predicted states.
Using observed future visibility would leak the answer. Hard visibility changes
make the vector field discontinuous; a discrete-time model is a sensible first
baseline before choosing fixed, piecewise-updated or smooth graph rules for an ODE.
Prediction gains alone do not establish causal interactions.

## Reproduce the first audit

The reusable script is `scripts/audit_trial.py`; install numpy, pandas, pyarrow,
scipy and matplotlib, then pass the two matching trial Parquet files and an output
directory. `--skip-plot` runs only the numerical audit. Outputs for 0066 are in
`analysis/0066/`. The exploratory speed estimate uses an 11-frame cubic
Savitzky–Golay derivative separately for every fish and segment, drops five frames
at each end, and divides by the trial median body length. It is a descriptive
estimate, not a tuned training preprocessing choice.

Only the two 0066 tables were sampled from the release (128,017,419 bytes total),
using byte-range reads and ZIP CRC verification; the full archives were not downloaded.
This verifies member integrity, not the original archives' full SHA256 hashes.
No new video overlay or other-trial audit has been performed in this exploration.
