# Golden shiners: social-force dataset

Public mirror of Jacob Davidson's Mosaic-format golden-shiner dataset, shared November 5, 2026, for social-force modeling. Ten trials contain tracks with midline pose, directed visual networks, and videos for groups of 10, 30, 70, and 151 fish.

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
