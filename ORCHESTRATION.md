# Golden shiners: ChatGPT–Claude orchestration guide

**Owner:** Marco  
**Created:** November 7, 2026  
**Current phase:** Phase 1 requested descriptive measurements completed across all ten trials; publication authorized by Marco. Independent computational reproduction and broader atlas extensions remain open. See the [session account](docs/session-summary.md) and [live workflow status](docs/workflow/status.md).  
**Purpose:** give ChatGPT/Codex and Claude Code one shared scientific specification and a concrete handoff process.

Read this file at the start of every project session. Do not assume another agent's chat history is available. This guide does not itself launch agents, install software, download the dataset, authorize cloud spending, or publish changes.

**Quick start for Marco:** start with the session account and live status above; M0 and the pilot are already implemented and reviewed. The configured CLI bridge now sends explicit snapshots to Claude automatically. For each next task, use the section 10 prompts and repeat implementation → independent review → fixes → integration. Static review and independent computational reproduction remain separate gates.

## 1. Outcome and scope

Build a reproducible descriptive atlas of golden-shiner behavior that Marco can present to his postdoc. The narrative is:

> We checked what the dataset measures, established which measurements are reliable, described individual and collective behavior, and identified patterns that motivate specific interaction hypotheses.

The scientific sequence is **describe behavior → map candidate responses → test predictive information → compare interaction models**. Complete the first stage before starting the others.

| Phase | Included | Not a conclusion of this phase |
| --- | --- | --- |
| **1: descriptive atlas — current scope** | Measurement validation; individual movement; body posture; school organization; spatial relationships; reconstructed visual access | Attraction/repulsion laws, attention, causal influence, leadership, inferred physical forces |
| **2: candidate responses — later** | Lagged response maps; propagation and apparent leadership; candidate pairwise and group-dependent responses | Causation established by correlation alone |
| **3: prediction and models — later** | Held-out baseline comparisons; visibility versus proximity; pairwise versus higher-order models; possible GNN + Neural ODE | A complex model is necessary merely because it fits the training data |

Phase 1 uses geometric/statistical measurements and small synthetic validation examples. It does **not** require fitting a behavioral simulator or neural model. Synthetic examples validate calculations; they are not findings about real fish.

## 2. Read these sources and establish the starting state

Read in this order:

1. [Repository README](README.md): data hosting, restoration and provenance.
2. [Original dataset README](docs/source-README.md): schema and source conventions. Preserve this file unchanged.
3. [Initial 0066 audit](analysis/0066/README.md) and [audit results](analysis/0066/audit.json): a limited pilot, not whole-dataset validation.
4. [Earlier modeling notes](docs/modeling-start.md): future modeling context. This orchestration guide defines the current phase and deliverables; do not execute those notes' modeling steps yet.

Historical starting state before implementation (consult workflow status for subsequent progress):

- The GitHub release holds the complete approximately 9.02 GB of archives. `git clone` retrieves documentation and code, not release attachments.
- There are ten trials: three each with 10, 30 and 70 fish, and one with 151 fish. The latter is named `150-fish` in the source.
- The pilot inspected only the `10-fish/0066` tracks and visibility table. It found 245,780 track rows, 24,578 tracked frames and 1,662,869 visibility rows; no nulls or duplicate keys; and valid edge endpoints. Video alignment was not independently inspected.
- The pilot downloads and temporary environment were removed. Do not assume either is available.
- Existing local work includes `scripts/audit_trial.py`, `analysis/0066/`, `docs/modeling-start.md`, and README edits. Inspect Git status before branching or staging; do not discard or silently include unrelated work.
- Claude Code CLI version 2.1.314 and its help were inspected. A live Claude request and authentication have **not** been tested. CLI availability is not proof that cross-agent communication works.

Source documentation is evidence about the intended data conventions. Executed checks are evidence about actual files. If they disagree, record both and investigate rather than silently changing the source or the data.

## 3. Roles and decision rights

The default assignment below is a workflow choice, not a claim that one model is scientifically superior. Marco may swap the implementation and review roles.

| Role | Default | Responsibilities |
| --- | --- | --- |
| Scientific owner | Marco | Choose scope, accept material methodological tradeoffs, approve phase transitions and publication when not already authorized |
| Coordinator | ChatGPT/Codex | Maintain task state and decisions; prepare bounded assignments; consolidate reviews; keep the narrative consistent |
| Implementer | ChatGPT/Codex | Write the assigned code, validate it, produce outputs, and supply a reproducible handoff |
| Independent reviewer | Claude Code | Check definitions, independently verify critical calculations, review the pinned code and outputs, and return findings |
| Integrator | Coordinator | Apply accepted fixes, integrate reviewed commits, and regenerate affected outputs |

Only one implementer owns a task at a time. A reviewer does not edit the implementer's files. If Claude implements a task, Codex becomes its reviewer. Record the actual model identifier used when available; do not guess a model version from a product name or alias.

**Agreement between models is not validation.** Reviews must cite a source, calculation, reproducible check, inspected output, or concrete code location.

## 4. How the two agents communicate

### 4.1 Durable shared state

Use this repository as the shared record. During the first implementation milestone, create:

| Planned path | Purpose | Writer |
| --- | --- | --- |
| `docs/workflow/status.md` | Task table: ID, scope, owner, worktree, base SHA, implementation SHA, state, next action | Coordinator |
| `docs/workflow/decisions.md` | Dated scientific decisions, alternatives, evidence, affected results | Coordinator |
| `docs/workflow/tasks/<ID>.md` | Assignment and implementation handoff using the template below | Coordinator, then assigned implementer sequentially |
| `docs/workflow/reviews/<ID>-<reviewed-sha>.md` | Review findings and disposition, tied to an exact revision | Coordinator saves reviewer output; reviewer may author it in a separate review worktree |
| `docs/methods.md` | Reviewed measurement definitions and exclusions | Assigned methods owner |

These paths are **planned**, not files already present. Do not maintain duplicate competing specifications in both agents' instruction files. If `AGENTS.md` or `CLAUDE.md` is added later, use a short pointer to this guide plus necessary tool-specific instructions.

### 4.2 Manual handoff: works in terminal or app

1. Coordinator prepares a task packet with exact repository/worktree path, revision, inputs and expected output.
2. Marco opens Claude Code in the designated directory and pastes the appropriate prompt from section 10, with the packet attached or accessible as a file.
3. Claude returns a structured review or implementation handoff.
4. Coordinator records it, resolves each finding, and updates task state.

Do not assume the Claude app automatically shares the working directory, local files or history of a terminal session. Verify its repository and revision. A remote app session needs pushed input commits and its own data access; local uncommitted files will not appear there.

### 4.3 Optional CLI handoff: validate before depending on it

Claude Code supports non-interactive `claude -p` requests, JSON output and resumable sessions. The coordinator can use those capabilities to send a task and read a reply once Marco initiates that workflow. Use a dedicated project review session, not an arbitrary latest personal session.

First test: send only a short project-plan review with file-read tools, verify a successful response, and record the session/model identity if returned. Do not start data processing or code edits as part of this connectivity test. Check the installed CLI help before constructing commands; tool permissions, account access and usage limits are environment-specific.

For review calls, allow only the tools needed for the review. Grant execution separately for specified validation commands. Do not bypass permissions to make unattended automation work. If authentication, tool access or limits block a call, record the failure and use the manual handoff; do not report Claude's review as completed.

CLI automation is an optional transport. The same task/review files and acceptance gates apply whether the exchange is automatic or copied by Marco.

### 4.4 Avoid editing and output collisions

- First inspect `git status` and preserve existing work. Establish a known baseline before creating review worktrees; a worktree created from HEAD will omit uncommitted pilot files.
- For parallel implementation, use a distinct branch **and worktree** for each writer. A branch alone does not isolate a shared checkout. Suggested names: `codex/<task-id>` and `claude/<task-id>`.
- Assign explicit owned paths. Shared dependencies, environment lockfiles, common configuration and output directories each have one owner.
- Review an immutable commit in a separate worktree. Both agents may read the same raw data, but write derived outputs to separate run directories.
- If worktrees are unavailable, work serially: the writer stops, prepares a patch plus explicit untracked files and hashes, and hands over a frozen snapshot before review starts.
- Only the integrator combines changes. Re-run affected checks after integration; pre-merge reviews do not prove the merged result works.
- Do not commit raw data, secrets or local environments. Do not push or publish merely because a review passed; follow Marco's current publication instruction.

## 5. Evidence and measurement rules

Every figure caption and finding must distinguish these evidence types:

| Type | Examples | Appropriate wording |
| --- | --- | --- |
| Tracker estimate | Position, measured body heading, midline points | “The tracked positions show…” |
| Derived measurement | Speed, curvature, polarization, spacing | “Using the stated estimator…” |
| Geometric reconstruction | Visibility, angular size | “The supplied visibility reconstruction indicates…” |
| Hypothesis | Attraction, influence, leadership, response mechanism | “This motivates testing whether…” |

Rules that both agents must check:

1. **Time continuity:** derive segment counts from each file; do not force every recording into seven segments. Compute derivatives, unwrap angles, smooth trajectories and construct windows within trial/fish/continuous-segment blocks. Detect additional gaps and exclude affected intervals. Never bridge joins.
2. **Coordinates:** pixels, x right, y down. For heading `theta`, forward is `(cos(theta), sin(theta))`, and fish-right is `(-sin(theta), cos(theta))`. State all rotation and curvature signs. If converting to y-up, transform positions, headings and signed quantities together.
3. **Units:** no supported pixel-to-centimeter calibration is provided. Retain pixel-based results and state any body-length normalization. For descriptive comparisons, use a documented fixed trial scale, such as median body length; never a noisy frame-varying divisor. Later predictive pipelines need a training/calibration-only normalization policy.
4. **Camera exception:** the 151-fish trial has a documented roughly 15% body-length mismatch and only one replicate. Present it separately; do not silently correct it or attribute differences solely to group size.
5. **Heading versus travel:** measured body heading is not velocity direction. Mask travel-direction and velocity-normalized metrics at low speed; record thresholds and excluded fractions.
6. **Posture:** curvature must be derived from the head-to-tail midline; it is not a supplied ready-made scalar. Specify spatial smoothing, derivative estimation, evaluation location, units and sign.
7. **Visibility:** `id1` sees `id2`. For later source-to-target message passing, information travels `id2 → id1`. Absent pairs imply invisibility only after frame/table coverage is established. Zero-degree fish must remain in averages.
8. **Identity:** IDs are reconstructed across joins and local to trials. Do not pool the same numeric ID across trials or infer persistent leadership from it.
9. **Arena:** image borders are not established tank walls. Obtain arena geometry from evidence before calculating wall distance or “center versus edge of tank.” Distinguish that from position within the school.
10. **Uncertainty:** frames and neighboring fish are dependent. Show per-trial estimates. The three trials per smaller group provide limited replication; one 151-fish trial cannot estimate between-trial variability. Temporal block resampling, if used, estimates within-trial variability and must state block length and rationale.
11. **Exploration versus testing:** Phase 1 may describe all trials. Such inspected trials are not an untouched confirmatory test set. Record exposure; before Phase 3, agree on an exploratory validation protocol or obtain genuinely unseen data. The earlier suggested 0066/0105/0126 split is not a frozen protocol.
12. **No silent cleaning:** record the original counts, every filter, dropped counts and reasons. Do not infer ground-truth accuracy from zero nulls or smooth trajectories.

## 6. Scientific work packages and required figures

For each metric, create a methods entry **before implementation**: question, formula, required columns, units, coordinate sign, temporal/spatial smoothing, eligibility mask, pooling weights, sensitivity checks, expected synthetic result and reviewer disposition.

| Package | Measurements and decisions | Primary figure | Acceptance evidence |
| --- | --- | --- | --- |
| **Q: dataset quality** | Inventory all trials; keys, schema, finite values, frame/ID coverage, segments, edge endpoints, lengths, source integrity; video overlay and alignment | Trial quality table plus labeled overlays | Actual checks for each available trial; missing coverage explicit; no whole-dataset claim based on 0066 |
| **B1: individual movement** | Speed, acceleration magnitude, signed body-heading turn rate, wrapped body-heading/travel-direction difference | Per-trial distributions plus a representative time trace | Segment-safe estimates; smoothing sensitivity; low-speed mask; estimator/units in caption |
| **B2: body posture** | Midpoint signed curvature, full-midline bending summary, posture variability | Representative midlines and per-trial curvature distributions | Straight/curved synthetic checks; head-to-tail and sign conventions; spatial smoothing sensitivity; video examples |
| **B3: school organization** | Heading polarization, circulation, centroid speed, group spread | Synchronized time series plus alignment–circulation map with matched snapshots | Parallel-motion and circular-motion checks; degeneracy masks; no automatic “disorder” label from low alignment |
| **B4: spatial relationships** | Nearest-neighbor distance, neighbor bearing, relative heading, local neighbor counts at specified radii | Body-frame neighbor-position map plus spacing distributions | Self-pairs excluded; focal/neighbor direction correct; density denominator and spatial bins stated; all-neighbor and nearest-neighbor results distinguished |
| **B5: visual access** | Visible-neighbor count, visible fraction, directed reciprocity, angular-size distribution, link persistence | Visibility distributions and selected directed snapshots | Endpoint/frame coverage; include zero-degree nodes; correct denominator; persistence censored at recording boundaries |

Minimum definitions to resolve at the methods review:

- **Polarization:** `P(t) = norm(mean_i([cos(theta_i), sin(theta_i)]))`. State that this uses body headings. Any velocity-based variant must have a different name.
- **Spread:** define, for example, RMS distance from the instantaneous group centroid. Do not interchange it with convex-hull area or nearest-neighbor spacing.
- **Circulation:** specify the center, whether velocities are laboratory-frame or centroid-relative, the order of signed averaging and absolute value, and masks for stationary fish or fish at the center. Those choices measure different things; reviewers must agree before implementation.
- **Midpoint curvature:** proposed geometric definition `(x' y'' - y' x'') / (x'^2 + y'^2)^(3/2)` along head-to-tail arc length, evaluated near half arc length. Define the fit neighborhood and discrete estimator; test sign explicitly in y-down coordinates. Label raw units `1/pixel`, and state any length scaling.
- **Reciprocity:** fraction of directed edges whose reverse is present in the same frame. Distinguish a mean of frame fractions from an edge-weighted pooled fraction.
- **Visibility persistence:** contiguous visible intervals, broken at gaps and segment boundaries; boundary intervals are censored, not observed disappearances.

Use the following plotting contract for every primary figure:

- Save a publication-friendly PNG and vector output when appropriate, plus the underlying small summary table.
- Caption: question; evidence type; metric definition; units; trial/fish/time coverage; estimator/filter settings; denominator; uncertainty method or explicit “descriptive only”; exclusions; limitation.
- Show trials individually before any pooled group-size summary. Keep pooling weights explicit.
- Use consistent group colors, readable labels, and explicit y-down/body-frame conventions. Network arrows and heading arrows must be visually distinguishable.
- Predefine representative sampling: coverage across early/middle/late periods and collective-state ranges, with exact frame indices recorded. Disclose extra anomaly-selected examples; do not choose only attractive snapshots.
- Continuous measures precede behavioral labels. Label milling/schooling examples only after video checks; descriptive associations do not establish response or causality.

## 7. Milestones and review gates

Use task states: `PLANNED → IN_PROGRESS → READY_FOR_REVIEW → CHANGES_REQUESTED or VERIFIED → INTEGRATED`. Use `BLOCKED` only with a concrete blocker and next action. “Code written” is not “verified.”

| Milestone | Work | Reviewer must verify | Exit condition |
| --- | --- | --- | --- |
| **M0: agree on methods** | Set up workflow records; review source conventions and methods entries; choose environment, data/cache policy and resource budget | Scope stays descriptive; formulas/signs/degeneracies are explicit; pilot limitations preserved | Material questions resolved and Marco accepts the methods scope before analysis implementation |
| **M1: reproducible pilot** | Implement minimal loading and validation on 0066; port useful pilot code rather than blindly replacing it; generate one video overlay | Input integrity, segment handling, numerical checks, recorded environment and exact commands | Reviewer reproduces required pilot checks; output is labeled pilot-only. If access prevents reproduction, retain the static review but leave M1 unverified and the reproduction task BLOCKED |
| **M2: dataset quality** | Run metadata/quality checks across all ten trials; establish video and scale limitations | Per-trial evidence; no fabricated checks for unavailable data; bounded memory use | Quality report with known limitations and explicit eligibility for later figures |
| **M3: five chapters** | Implement B1–B5 from reviewed methods; run on eligible trials and build five primary figures | Synthetic validation, sensitivity, trial weighting, captions and claim traceability | Each chapter separately VERIFIED; unresolved material findings removed from headline claims |
| **M4: presentation release** | Integrate, rerun, organize report and reproduction instructions | Clean-checkout reproduction path; evidence links; no stale outputs; scope and coverage honest | Cohesive report ready for Marco; publish only under his publication instruction |

B1–B5 may run in parallel after shared measurement conventions and data interfaces are stable. Assign separate modules and output paths, and let only one agent change the shared loader or configuration. B3 and movement-dependent parts of B4 should consume reviewed kinematics rather than independently reimplementing them.

For a time-limited Monday presentation, reduce coverage explicitly rather than skip scientific gates. A verified 0066 pilot with five chapters is acceptable as a **pilot**; the full atlas requires documented coverage of all trials. Unsupported or unavailable metrics should be marked incomplete, not replaced by plausible prose.

## 8. Reproducibility and repository contract

Proposed implementation layout (not an assertion that these files already exist):

```text
ORCHESTRATION.md              This shared workflow
configs/                     Reviewed parameters and trial selections
src/shiners/                 Loading, validation and metric functions
scripts/                     Analysis and figure-generation entry points
notebooks/                   Narrative exploration using shared functions
tests/                       Synthetic numerical and data-contract checks
docs/methods.md               Measurement definitions
docs/workflow/               Task, review and decision records
reports/data-quality.md       Coverage and limitations
reports/findings.md           Five-chapter scientific narrative
reports/figures/              Reviewed primary/supplementary figures
reports/tables/               Compact figure data
reports/runs/<run-id>.json    Provenance for retained outputs
```

At M0, choose one supported Python environment and a reproducible dependency specification. Avoid independently installed, conflicting environments. Choose storage and compute limits before bulk data acquisition; start with a bounded trial. Large network tables should be processed with column selection and batches where needed, not loaded wholesale by default.

Every retained run records:

```text
run ID and timestamp
Git commit; clean/dirty state (patch hash if dirty)
Python and dependency versions / environment lock reference
input release tag, member paths, sizes and available checksums
config file and hash; trial, frame and fish selection
exact commands; seeds where applicable
filters, exclusions and counts; warnings and failures
output paths and checksums
```

Full-archive SHA256 verification, member CRC verification and a locally computed file hash are distinct checks. Report exactly which occurred. Keep the original data immutable. Raw archives/videos/Parquet, caches and environments stay outside Git; define their ignored locations before downloading. Do not delete another agent's cache or source files. Preserve compact verified results and provenance even when a task's temporary data is cleaned up.

For each headline claim in `reports/findings.md`, record: **claim ID → evidence type → figure/table → run ID → method → trial coverage → limitation → review status**. Include null/negative results. If input, formula or preprocessing changes, invalidate and regenerate dependent figures and claims.

Meaningful numerical checks include constant velocity, an analytic turn, straight and curved midlines, perfectly parallel headings, circular motion, known body-frame neighbor positions, and a tiny directed graph with a zero-degree fish. Define expected values and tolerances before running the implementation. Reviewer spot checks should derive the expected answer independently, not call the same helper function as the implementation.

## 9. Assignment, handoff and review templates

### Task packet — coordinator fills before delegation

```markdown
# <ID>: <one bounded outcome>
State: PLANNED
Phase/milestone:
Implementer / reviewer / actual models if known:
Repository and absolute worktree paths:
Base commit:
Owned paths (writes allowed):
Read-only inputs and data locations:
Dependencies and completed prerequisite tasks:
Question and evidence type:
Method definition / accepted decision references:
Expected outputs:
Acceptance checks, expected values and tolerances:
Runtime / storage / model-call budget:
Out of scope:
Stop-and-report conditions:
Next handoff recipient:
```

### Implementation handoff — implementer fills before review

```markdown
State: READY_FOR_REVIEW
Task ID / implementation commit / base commit:
Changed paths and reason:
Commands actually run and exit/results:
Input/config/environment/run references:
Outputs and concise numerical findings:
Checks passed / failed / not run (with reasons):
Known limitations and open questions:
Exact review instructions:
```

### Review — reviewer returns without editing implementation

```markdown
Task ID / reviewed commit / reviewer and model:
Verdict: PASS | CHANGES_REQUESTED | BLOCKED
Scope actually inspected:
Independent calculations/checks and observed results:
Findings:
- ID; severity (blocking/material/minor); file or claim; evidence;
  why it matters; specific correction; how to verify the fix.
Not inspected / not executed and why:
Remaining uncertainty:
```

Coordinator appends each finding's disposition: accepted/fixed with revision and rerun, rejected with evidence, or unresolved with the claim withheld. PASS means the assigned acceptance checks passed within the stated scope; it does not certify the entire dataset.

On disagreement: isolate the disputed definition or claim, consult the original source, construct a minimal numerical counterexample, and compare evidence. Marco resolves substantive scope or interpretation choices. Never decide by majority vote among LLMs. After two unsuccessful review/fix cycles on the same issue, summarize the precise disagreement instead of running an open-ended agent loop; continue independent unblocked tasks.

## 10. Copy-and-paste prompts

Replace angle-bracket placeholders before use. Attach the same reviewed task packet to both agents.

### Start with ChatGPT/Codex as coordinator

> Work in `/Users/marcoli/github/shiners-social-forces`. Read ORCHESTRATION.md and its source links, inspect the actual Git state, and preserve existing work. Coordinate M0 only: prepare the methods and task records for the five descriptive chapters, identify unresolved scientific choices, and prepare a bounded Claude review packet. Do not implement analysis or fit models yet. List what is already measured versus merely documented. Use this guide's review and evidence rules. Return the exact files and decisions I need to review.

### Ask Claude to review the plan before coding

> You are the independent scientific reviewer for the golden-shiner descriptive atlas. Read ORCHESTRATION.md, docs/source-README.md, the pilot audit and task packet `<path>`, at revision `<sha>` in `<worktree>`. Review only; do not edit implementation, download data, or fit models. Check phase boundaries, coordinate/sign conventions, continuity, metric definitions, visibility direction, replication and data-exposure policy. Independently reason through the proposed circulation and curvature definitions. Return the structured review from section 9, distinguishing blockers from optional improvements. Do not treat agreement with the implementer as evidence.

### Assign an implementation task to either assistant

> Implement only task `<ID>` from `<task packet>` at base `<sha>` in `<worktree>`. Read ORCHESTRATION.md and the accepted methods decisions. You own only `<paths>`; other agents may be working elsewhere. Do not revert their changes or alter shared interfaces without coordination. Use the recorded data/resource budget. Run the specified independent numerical checks, preserve raw data, and record exact commands, provenance and limitations. Stop at READY_FOR_REVIEW with the section 9 handoff. Do not expand into response inference, neural models or publication.

### Ask the other assistant to verify an implementation

> Independently review task `<ID>` at commit `<sha>` in `<review worktree>`, using its task packet and handoff. Do not modify the implementation. First derive expected values for its critical synthetic cases, then inspect the code and reproduce the specified checks within the assigned budget. Verify the saved tables and figures, not just successful process exits. Check scientific claims against actual coverage, units, exclusions and source conventions. Return the section 9 review with precise evidence. Explicitly list anything you could not execute.

### Resolve findings and hand back

> Address review `<review path>` for task `<ID>`. For every finding, record its disposition and evidence. Change only assigned paths; rerun affected checks and regenerate affected outputs. Record the new revision and identify which earlier outputs are stale. Request re-review of material fixes. Do not mark the task VERIFIED yourself when independent review is still outstanding.

## 11. Definition of done for the first scientific report

- [ ] Data and source provenance are accessible and correctly attributed.
- [ ] Actual trial/video coverage and known limitations are explicit.
- [ ] The five descriptive chapters each have a reviewed method, primary figure, underlying table and evidence-backed caption.
- [ ] Synthetic examples and sensitivity checks support the calculations used in claims.
- [ ] The report separates tracker estimates, derived quantities, reconstructed visibility and hypotheses.
- [ ] A reviewer has reproduced the required checks at a pinned revision and all material findings are resolved or the affected claims withheld.
- [ ] A documented environment and exact commands reproduce the retained outputs; any unavailable data are identified.
- [ ] No future-model results, video inspections or whole-dataset checks are claimed without execution evidence.
- [ ] The final narrative explains what is present, how reliable it is, and which next hypotheses are justified.
- [ ] Marco receives the report link, implementation/review status, remaining limitations, and the explicit local-versus-published GitHub status.

**Assignment confirmed:** OpenAI coordinates and implements; Claude independently reviews. Continue from [workflow status](docs/workflow/status.md), not from an assumed completed milestone. The guide defines the process; actual review records establish what has been reviewed.
