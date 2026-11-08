#!/usr/bin/env python3
"""Explain circulation coverage from frozen per-frame comparison outputs.

Run after the comparison pipeline has created collective.csv for both trials.
Only this script's derived table, manifest, and figure are written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TRIALS = ("70-fish__0107", "70-fish__0124")
REPO = Path(__file__).resolve().parents[1]
COUNT_ATOL = 1e-8


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def eligibility_summary(stem, summary, config, collective):
    """Recover integer fish counts and cross-check the actual reporting mask."""
    fish = summary["fish"]
    if isinstance(fish, bool) or not isinstance(fish, int) or fish < 2:
        raise ValueError(f"{stem}: fish must be an integer >= 2")
    fraction = float(config["circulation_min_fraction"])
    speed = float(config["low_speed_bl_s"])
    if not np.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError(f"{stem}: invalid minimum fraction")
    if not np.isfinite(speed) or speed <= 0:
        raise ValueError(f"{stem}: invalid speed cutoff")
    # Use the same >= fraction comparison as the original metric. This avoids
    # a floating-point ceil error at exact integer-count boundaries.
    required = int(np.flatnonzero(np.arange(fish + 1) / fish >= fraction)[0])
    required_columns = {"frame", "eligible_fraction", "circulation"}
    if not required_columns.issubset(collective.columns):
        raise ValueError(f"{stem}: missing required columns")
    frames = collective["frame"].to_numpy(dtype=float)
    if (not len(frames) or not np.isfinite(frames).all()
            or not np.equal(frames, np.rint(frames)).all()
            or not (np.diff(frames) > 0).all()):
        raise ValueError(f"{stem}: frames must be unique increasing integers")
    if len(frames) != summary["quality"]["frames"]:
        raise ValueError(f"{stem}: tracked-frame denominator mismatch")
    fractions = collective["eligible_fraction"].to_numpy(dtype=float)
    circulation = collective["circulation"].to_numpy(dtype=float)
    if np.isinf(fractions).any() or np.isinf(circulation).any():
        raise ValueError(f"{stem}: infinities are not missing values")
    defined = np.isfinite(fractions)
    if ((fractions[defined] < 0) | (fractions[defined] > 1)).any():
        raise ValueError(f"{stem}: eligible fractions outside [0, 1]")
    scaled_counts = fractions[defined] * fish
    counts = np.rint(scaled_counts).astype(int)
    if not np.allclose(scaled_counts, counts, rtol=0, atol=COUNT_ATOL):
        raise ValueError(f"{stem}: eligible fractions do not encode integer fish counts")
    if "eligible_fish_count" in collective:
        saved = collective["eligible_fish_count"].to_numpy(dtype=float)
        if (np.isinf(saved).any() or not np.array_equal(np.isfinite(saved), defined)
                or not np.allclose(saved[defined], counts, rtol=0, atol=COUNT_ATOL)):
            raise ValueError(f"{stem}: saved eligible fish count mismatch")
    accepted_mask = np.zeros(len(frames), dtype=bool)
    accepted_mask[defined] = counts >= required
    finite_c = np.isfinite(circulation)
    if not np.array_equal(accepted_mask, finite_c):
        raise ValueError(f"{stem}: qualifying frame mask differs from finite circulation")
    if ((circulation[finite_c] < -1e-12) | (circulation[finite_c] > 1 + 1e-12)).any():
        raise ValueError(f"{stem}: circulation outside [0, 1]")
    accepted = int(accepted_mask.sum())
    coverage = accepted / len(frames)
    if accepted != summary["circulation"]["n"]:
        raise ValueError(f"{stem}: circulation summary count mismatch")
    if not np.isclose(coverage, summary["circulation_eligible_frame_fraction"], rtol=0, atol=1e-12):
        raise ValueError(f"{stem}: circulation summary coverage mismatch")
    # The saved eligibility mask cannot separate radius failures from relative
    # speed failures. It can verify that undefined frames have undefined velocity.
    velocity_undefined = None
    if "centroid_speed_bl_s" in collective:
        centroid_speed = collective["centroid_speed_bl_s"].to_numpy(dtype=float)
        if np.isinf(centroid_speed).any():
            raise ValueError(f"{stem}: infinite centroid speed")
        velocity_undefined = int((~np.isfinite(centroid_speed)).sum())
        if not np.array_equal(~np.isfinite(centroid_speed), ~defined):
            raise ValueError(f"{stem}: undefined eligibility and velocity masks differ")
    return {
        "trial": stem,
        "fish": fish,
        "low_speed_bl_s": speed,
        "circulation_min_fraction": fraction,
        "required_qualifying_fish": required,
        "tracked_frames": len(frames),
        "eligibility_defined_frames": int(defined.sum()),
        "eligibility_undefined_frames": int((~defined).sum()),
        "velocity_undefined_frames": velocity_undefined,
        "accepted_frames": accepted,
        "defined_but_below_requirement_frames": int(defined.sum()) - accepted,
        "coverage_all_tracked_frames": coverage,
        "median_qualifying_fish": float(np.median(counts)) if len(counts) else None,
        "qualifying_fish_p05_p95": np.quantile(counts, [.05, .95]).tolist() if len(counts) else None,
        "histogram_fish_count": list(range(fish + 1)),
        "histogram_frame_count": np.bincount(counts, minlength=fish + 1).tolist(),
    }


def load_trial(root, stem):
    folder = root / "trials" / stem
    paths = {name: folder / name for name in ("summary.json", "config.json", "collective.csv", "provenance.json")}
    provenance = json.loads(paths["provenance.json"].read_text())
    for name in ("summary.json", "config.json", "collective.csv"):
        if digest(paths[name]) != provenance["output_hashes"].get(name):
            raise ValueError(f"{stem}: saved provenance hash mismatch for {name}")
    metric = "src/shiners/metrics.py"
    if digest(REPO / metric) != provenance["source_hashes"].get(metric):
        raise ValueError(f"{stem}: metric source differs from the frozen run")
    result = eligibility_summary(
        stem, json.loads(paths["summary.json"].read_text()),
        json.loads(paths["config.json"].read_text()), pd.read_csv(paths["collective.csv"]),
    )
    hashes = {str(path.relative_to(root)): digest(path) for path in paths.values()}
    return result, hashes


def draw(rows, figure_dir):
    settings = {(r["fish"], r["required_qualifying_fish"], r["low_speed_bl_s"], r["circulation_min_fraction"]) for r in rows}
    if len(settings) != 1:
        raise ValueError("The shared comparison figure requires matching fish counts and cutoffs")
    fish, required, speed, fraction = settings.pop()
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["svg.hashsalt"] = "shiners-circulation-eligibility"
    fig, axes = plt.subplots(1, len(rows), figsize=(12, 5.6), sharey=True, squeeze=False)
    maximum = max(max(row["histogram_frame_count"]) for row in rows)
    for ax, row in zip(axes[0], rows):
        x = np.asarray(row["histogram_fish_count"])
        ax.bar(x, row["histogram_frame_count"], width=.96,
               color=np.where(x >= required, "#d77b16", "#7892a4"))
        ax.axvline(required - .5, color="black", linestyle="--", linewidth=1.3)
        ax.set_xlim(-.5, fish + .5)
        ax.set_ylim(0, max(1, maximum) * 1.12)
        ax.set_xticks(sorted(set(range(0, fish + 1, max(1, fish // 7))) | {required, fish}))
        ax.set_xlabel("Number of fish qualifying in that frame")
        ax.set_title(f"Trial {row['trial'].split('__')[1]}: {row['accepted_frames']:,} / {row['tracked_frames']:,} frames qualify\n"
                     f"({row['coverage_all_tracked_frames']:.1%} of all tracked frames)", fontsize=11)
        median = row["median_qualifying_fish"]
        median_label = f"{median:g} of {fish}" if median is not None else "unavailable"
        ax.text(.025, .95, f"Median qualifying count: {median_label}", transform=ax.transAxes, va="top", fontsize=10)
        ax.text(required + .6, .66 * max(1, maximum), f"Requirement: {required} fish", rotation=90, fontsize=10, va="center")
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=.15)
    axes[0, 0].set_ylabel("Number of frames")
    fig.suptitle(f"Circulation is reported only when at least {required} of {fish} fish qualify (≥{fraction:.0%})", fontsize=14, y=.98)
    unknown = "; ".join(f"{r['trial'].split('__')[1]}: {r['eligibility_undefined_frames']:,}" for r in rows)
    undefined_kind = "velocity-undefined" if all(r["velocity_undefined_frames"] is not None for r in rows) else "eligibility-undefined"
    fig.text(.07, .025,
             "Blue bars: too few fish qualify. Orange bars: the frame passes the reporting rule.\n"
             f"Qualifying fish need speed ≥{speed:g} body lengths/s relative to the moving school, plus the tiny radius guard (r > 10⁻⁶ body lengths).\n"
             f"The {undefined_kind} frames ({unknown}) are absent from the bars, but included in each coverage denominator.\n"
             "Coverage measures where circulation is defined under this rule; it is not the fraction of time the school circles.",
             fontsize=9, va="bottom")
    fig.subplots_adjust(left=.07, right=.99, bottom=.27, top=.81, wspace=.08)
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in ("png", "svg"):
        path = figure_dir / f"05-circulation-eligibility.{suffix}"
        metadata = {"Date": None} if suffix == "svg" else None
        fig.savefig(path, dpi=180, bbox_inches="tight", metadata=metadata)
        paths.append(path)
    plt.close(fig)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("reports/comparison"), help="comparison output root")
    args = parser.parse_args()
    rows, input_hashes = [], {}
    for stem in TRIALS:
        row, hashes = load_trial(args.root, stem)
        rows.append(row)
        input_hashes.update(hashes)
    outputs = draw(rows, args.root / "figures")
    table = args.root / "tables" / "circulation-eligibility.json"
    table.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scope": "Descriptive counts of tracked frames, not independent samples or a milling-time estimate.",
        "eligibility": "Saved eligible_fraction includes school-relative speed >= the configured cutoff and radius > 1e-6 body lengths. These components are not separately audited here.",
        "count_reconstruction_absolute_tolerance": COUNT_ATOL,
        "trials": rows,
    }
    table.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    outputs.append(table)
    manifest = {
        "reproduce": "MPLCONFIGDIR=.cache/matplotlib uv run python scripts/plot_eligibility.py --root reports/comparison-rerun",
        "prerequisites": [
            "Install the frozen environment and fetch the source tracks and networks for 70-fish__0107 and 70-fish__0124; see README.md.",
            "Regenerate collective.csv, summary.json, config.json, and provenance.json for both trials in a fresh output directory before plotting:",
            "uv run python scripts/run_comparison.py --trial 70-fish__0107 --trial 70-fish__0124 --output-root reports/comparison-rerun/trials",
        ],
        "git_only_verification_limit": "The frame-level collective.csv files are omitted from Git. Their recorded hashes cannot be checked from a fresh checkout alone; regenerate the trial outputs first. Rerun provenance will describe the new run.",
        "original_output_root": str(args.root),
        "input_path_base": "comparison root supplied by --root",
        "source_path_base": "repository root",
        "source_hashes": {p: digest(REPO / p) for p in ("scripts/plot_eligibility.py", "src/shiners/metrics.py")},
        "input_hashes": input_hashes,
        "output_hashes": {str(p.relative_to(args.root)): digest(p) for p in outputs},
        "python": platform.python_version(),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
        "validation": ["inputs match frozen trial provenance", "metric source matches frozen trial provenance", "integer qualifying counts", "exact finite-circulation frame-mask match", "summary counts and all-tracked-frame coverage match"],
    }
    (table.parent / "circulation-eligibility-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({r["trial"]: {k: r[k] for k in ("accepted_frames", "tracked_frames", "eligibility_undefined_frames", "required_qualifying_fish", "median_qualifying_fish")} for r in rows}, indent=2))


if __name__ == "__main__":
    main()
