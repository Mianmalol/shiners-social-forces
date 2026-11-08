# Golden shiners: social-force dataset

Public mirror of Jacob Davidson's Mosaic-format golden-shiner dataset, shared November 5, 2026, for social-force modeling. Ten trials contain tracks with midline pose, directed visual networks, and videos for groups of 10, 30, 70, and 151 fish.

**Analysis results:** read the [session account](docs/session-summary.md) for our
approach and conclusions, or open the [ten-trial comparison](reports/comparison/README.md)
for the plots. This is a descriptive study; independent computational reproduction
and social-force modeling remain future work.

**[Download the complete dataset](https://github.com/Mianmalol/shiners-social-forces/releases/tag/data-2026-11-05)** (9,016,186,295 archive bytes, approximately 9.02 GB). All three source archives are hosted in this repository's release. The tracks and networks ZIPs are split into ordered binary parts because GitHub limits each release asset to under 2 GiB. Reassembly restores the original ZIPs byte for byte; no data has been transformed or omitted.

## Download and restore

With [GitHub CLI](https://cli.github.com/), download the release assets into a new directory:

```sh
gh release download data-2026-11-05 --repo Mianmalol/shiners-social-forces --dir downloads
```

Clone this small repository or download [`scripts/restore_archives.py`](scripts/restore_archives.py), then run:

```sh
python3 scripts/restore_archives.py --directory downloads
cd downloads
shasum -a 256 -c SHA256SUMS
```

The Python script needs only the standard library. It verifies the downloaded parts, reconstructs the split archives, and verifies the original archive checksums. It keeps the parts until you choose to remove them. On Linux, `sha256sum -c SHA256SUMS` is equivalent to the command above.

Extract **all three archives into the same destination** so their tracks, features, and media directories form one Mosaic dataset:

```sh
unzip shiners-tracks.zip
unzip shiners-networks.zip
unzip shiners-videos.zip
```

Allow extra disk space for both the downloaded parts, reconstructed ZIPs, and extracted data. The full archive inventory and hashes are in the release's `release-manifest.json`.

## Understand the data

Read the **[original dataset README](docs/source-README.md)** for the schema, trial list, coordinate conventions, segment gaps, identity reconstruction, video alignment, and worked loading examples. The original is preserved byte for byte and is also included as release asset `README.md`.

- Tracks: one row per fish per frame, including image-coordinate position, measured heading, body length, a 21-point midline, and two eye positions.
- Visual networks: one row per directed visible pair per frame, with observer `id1`, observed fish `id2`, ray count, angular size, and pixel distance.
- Videos: joined recordings for the nine smaller-group trials and the original single recording for the 151-fish trial.
- Mosaic manifest: `dataset.yaml` is included in the source archives. [Mosaic](https://github.com/ecodylicscience/mosaic) is the upstream analysis platform; pandas and pyarrow suffice to read the Parquet tables.

For derivatives, keep recording segments separate and never difference across segment joins. Coordinates are pixels with y increasing downward; see the source README for the 151-fish body-length caveat. The source documents a **visual interaction network**, not a learned visual identity embedding. Midpoint curvature must be defined and derived from the midline if needed; it is not listed as a ready-made track column in the README.

## Provenance, license, and integrity

Davidson JD, Sosna MMG, Twomey CR, Sridhar VH, Leblanc SP, Couzin ID (2021). *Collective detection based on visual information in animal groups.* Journal of the Royal Society Interface 18:20210142. [Paper DOI](https://doi.org/10.1098/rsif.2021.0142).

The [original Dryad data](https://doi.org/10.5061/dryad.sbcc2fr2h) is public under **CC0 1.0**. Jacob's source README explicitly applies the same license to this derivative. This mirror preserves that license and attribution; it does not claim authorship of the dataset. The paper has its own publication license.

- [Source Drive folder](https://drive.google.com/drive/folders/1biRGH82dsgAKaXenlQzxtOQWJOmYXTdo)
- [`source-manifest.json`](source-manifest.json): source identifiers, exact sizes, original SHA256 checksums, and snapshot date.
- [`SHA256SUMS`](SHA256SUMS): unmodified source checksum file (its `README.md` entry refers to the release's original README, not this landing page).
- Release `ASSET_SHA256SUMS`: checksums of the hosted ZIP parts.
- Release `release-manifest.json`: ordered parts, archive checksums, and ZIP member inventory.

The [manual transfer workflow](.github/workflows/mirror-data.yml) downloads directly onto temporary GitHub-hosted runners, checks all originals against the source SHA256 sums, and checks uploaded parts against GitHub's server-computed SHA256 digests. It prepares a draft release for publication after verification. Bulk data is stored in Releases, keeping the Git repository small.

## Initial exploration

Read the [ChatGPT–Claude orchestration guide](ORCHESTRATION.md) for the scientific
scope, agent roles, task handoffs, review gates, and report completion criteria.

A first hands-on audit of trial `10-fish/0066` is in
[`analysis/0066/README.md`](analysis/0066/README.md), with a plot and column profiles.
The [modeling starting plan](docs/modeling-start.md) connects the data to pairwise
social-response baselines and a later GNN + Neural ODE comparison.
Reproduce the audit with `scripts/audit_trial.py TRACKS.parquet NETWORKS.parquet OUTPUT_DIR`
(requires numpy, pandas, pyarrow, scipy and matplotlib; use `--skip-plot` for numbers only).

## Reproduce the descriptive pilot

Start with the [five-chapter pilot report](reports/findings.md), including figures,
video overlays, measured results, and limitations.

The pilot covers one trial. The all-trial workflow below extends the same measurements
to the ten recordings, with explicit comparison sensitivities.
OpenAI coordinates and implements; Claude Code provides independent snapshot reviews.
Review evidence and unresolved gates are tracked in [`docs/workflow/status.md`](docs/workflow/status.md).

From the repository root:

```sh
uv sync --frozen
uv run python scripts/fetch_pilot.py --video
uv run pytest -q
uv run shiners-pilot --output reports/pilot-0066
```

The downloader obtains only trial 0066 (about 257 MB including video), validates
ZIP-member CRC, and records extracted-file SHA256. It does not verify the complete
source archives' SHA256. Downloads are cached in ignored `data/0066/`. Use a new
output directory for each rerun; the pipeline refuses to overwrite a nonempty run.
Measurements and exclusions are specified in [`docs/methods.md`](docs/methods.md).
`uv.lock` records the tested dependency versions.

To request an automatic Claude review of an explicit source snapshot, after signing
in to Claude Code:

```sh
uv run python scripts/claude_review.py \
  --prompt docs/workflow/tasks/implementation-review-prompt.md \
  --input docs/methods.md \
  --input src/shiners/metrics.py \
  --output docs/workflow/reviews/my-review
```

Use a new review output directory. Add each relevant source, test, or result file
with another `--input`; do not send only a partial packet for a whole-project review.
The runner uses the configured Claude model unless `--model` is explicitly supplied,
records the returned model identity, and captures failures without calling them reviews.
Claude receives no tools: its review is independent reasoning about supplied evidence,
not independent execution. Both limitations and material review findings remain visible.

## Compare all ten trials

The [all-trial report](reports/comparison/README.md) compares alignment, circulation,
movement, posture, spacing and reconstructed visibility. Read the
[comparison methods](docs/comparison-methods.md) for eligibility, trial-level
replication, source anomalies and the separate-camera 151-fish caveat.

From a fresh checkout after `uv sync --frozen`:

```sh
uv run python scripts/fetch_trials.py --all
uv run pytest -q
uv run python scripts/run_comparison.py --output-root reports/comparison-rerun/trials
MPLCONFIGDIR=.cache/matplotlib uv run python scripts/plot_comparison.py --root reports/comparison-rerun
uv run python scripts/compare_threshold_pairs.py --root reports/comparison-rerun
MPLCONFIGDIR=.cache/matplotlib uv run python scripts/plot_eligibility.py --root reports/comparison-rerun
uv run python scripts/validate_comparison.py --output-root reports/comparison-rerun/trials --report reports/comparison-rerun/validation.json
```

Tracks and networks require about 7.53 GB in ignored `data/trials/`; this workflow does
not download additional videos. Fetching verifies each ZIP member's CRC and records
its extracted SHA256, without claiming a full-archive SHA256 check. Trial analyses
run in separate processes and network tables are streamed in bounded batches.
Summaries, figures, compact tables and provenance are intended for Git; generated
frame-level comparison CSVs remain local and can be rebuilt with the commands above.
Saved provenance retains the original run's absolute paths. A fresh checkout must
regenerate the omitted frame tables in a new output directory; the retained results
are evidence, not a portable resume cache.

Use `run_comparison.py --resume` only to verify and skip completed results; changed
sources or partial outputs are rejected. The example uses a fresh output directory
so the retained report is preserved. For another rerun, choose another unused name;
pass its parent as `--root` to plotting/pairwise comparison and its `/trials` directory
as `--output-root` to the validator, with a matching `--report` path.
Plotting and the final validator require all ten trials;
exploratory partial plots must be explicitly requested and are labelled partial.

The final validator checks recorded hashes, common source/config across trials,
exact reproduction of the pilot, table accounting, and independently recalculates
50 alignment values. This coordinator-run QA is separate from Claude's static review
and does not replace independent computational reproduction.
Exact pilot equality is intentionally strict: a rerun on different hardware or
numerical libraries may differ in the last bits. Investigate and report the size
and source of such a mismatch; it is not automatically a scientific discrepancy.

The hash-pinned methods files preserve the status text from their measurement runs.
For current review and publication state, use the [workflow status](docs/workflow/status.md)
and GitHub PR, rather than those historical status sentences.
