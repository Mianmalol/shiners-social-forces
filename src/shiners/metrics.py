"""Descriptive pilot measurements defined in docs/methods.md.

Inputs are one trial. Pixels use image coordinates (y down). Undefined quantities
remain NaN; functions do not impute missing samples or infer behavioral responses.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter


def _single_trial(tracks):
    for column in ("group", "sequence"):
        if column in tracks and tracks[column].nunique(dropna=False) > 1:
            raise ValueError("Metrics require one trial at a time")
    if tracks.empty:
        raise ValueError("Empty tracks")
    if tracks.duplicated(["frame", "id"]).any():
        raise ValueError("Duplicate track keys")


def _scale(length_scale):
    if not np.isfinite(length_scale) or length_scale <= 0:
        raise ValueError("Length scale must be finite and positive")


def _dense(tracks, columns):
    """A frame-by-fish view with explicit identical fish coverage."""
    _single_trial(tracks)
    frames = np.sort(tracks.frame.unique())
    fish = np.sort(tracks.id.unique())
    ordered = tracks.sort_values(["frame", "id"])
    if len(ordered) != len(frames) * len(fish):
        raise ValueError("Incomplete fish set")
    # Unique keys plus the full Cartesian cardinality ensures every fish/frame.
    arrays = {column: ordered[column].to_numpy(dtype=float).reshape(len(frames), len(fish))
              for column in columns}
    return frames, fish, ordered, arrays


def kinematics(tracks, window=11, order=3):
    """Return original rows/index plus segment- and gap-safe temporal derivatives.

    vx/vy: pixels/s; ax/ay: pixels/s²; turn_rate: radians/s (clockwise positive).
    Discard half a smoothing window plus one sample at both block ends, so the
    known noisier first/last segment samples do not enter retained estimates.
    """
    _single_trial(tracks)
    if not isinstance(window, (int, np.integer)) or window < 3 or window % 2 != 1:
        raise ValueError("Window must be an odd integer >= 3")
    if not isinstance(order, (int, np.integer)) or order < 2 or order >= window:
        raise ValueError("Polynomial order must be >= 2 and below window")
    if not np.isfinite(tracks[["time", "frame", "X", "Y", "ANGLE"]].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite kinematics input")
    result = tracks.copy()
    output = {name: np.full(len(tracks), np.nan) for name in ["xs", "ys", "vx", "vy", "ax", "ay", "turn_rate"]}
    jump = np.zeros(len(tracks), dtype=bool)
    heading_valid = np.ones(len(tracks), dtype=bool)
    half = window // 2
    trim = half + 1
    # groupby.indices uses positional indexes, preserving even nonunique row labels.
    for positions in tracks.groupby(["id", "segment"], sort=False).indices.values():
        positions = positions[np.argsort(tracks.frame.to_numpy()[positions], kind="stable")]
        frame = tracks.frame.to_numpy()[positions]
        for block in np.split(positions, np.flatnonzero(np.diff(frame) != 1) + 1):
            if len(block) < 2:
                continue
            sample = tracks.iloc[block]
            heading = sample.ANGLE.to_numpy(dtype=float)
            step = (np.diff(heading) + np.pi) % (2*np.pi) - np.pi
            flagged = np.flatnonzero(np.abs(step) > np.pi/2)
            block_jump = np.zeros(len(block), dtype=bool)
            block_jump[flagged] = True
            block_jump[flagged+1] = True
            jump[block] = block_jump
            contaminated = np.convolve(np.pad(block_jump, (half, half)), np.ones(window), mode="valid") > 0
            heading_valid[block] = ~contaminated
            delta = np.diff(sample.time.to_numpy(dtype=float))
            dt = float(np.median(delta))
            if dt <= 0 or not np.allclose(delta, dt, rtol=1e-6, atol=1e-10):
                raise ValueError("Irregular or nonpositive time increments within a continuous block")
            if len(block) <= 2*trim:
                continue
            interior = block[trim:-trim]
            for coordinate, velocity, acceleration in [("X", "vx", "ax"), ("Y", "vy", "ay")]:
                values = sample[coordinate].to_numpy(dtype=float)
                smooth = savgol_filter(values, window, order, mode="interp")
                output["xs" if coordinate == "X" else "ys"][interior] = smooth[trim:-trim]
                for derivative, name in [(1, velocity), (2, acceleration)]:
                    fitted = savgol_filter(values, window, order, deriv=derivative, delta=dt, mode="interp")
                    output[name][interior] = fitted[trim:-trim]
            turn = savgol_filter(np.unwrap(heading), window, order, deriv=1, delta=dt, mode="interp")
            output["turn_rate"][interior] = turn[trim:-trim]
    output["turn_rate"][~heading_valid] = np.nan
    for name, values in output.items():
        result[name] = values
    result["heading_jump"] = jump
    result["heading_valid"] = heading_valid
    axis_error = np.full(len(tracks), np.nan)
    if all(column in tracks for column in ["poseX0", "poseY0", "poseX20", "poseY20"]):
        dx = (tracks.poseX0-tracks.poseX20).to_numpy(dtype=float)
        dy = (tracks.poseY0-tracks.poseY20).to_numpy(dtype=float)
        valid_axis = np.isfinite(dx) & np.isfinite(dy) & (np.hypot(dx, dy) > 1e-8)
        axis_error[valid_axis] = ((tracks.ANGLE.to_numpy()[valid_axis] - np.arctan2(dy[valid_axis], dx[valid_axis]) + np.pi)
                                  % (2*np.pi) - np.pi)
    result["heading_axis_error"] = axis_error
    return result


def curvature(tracks, neighborhood=7):
    """Signed midpoint curvature in 1/pixel from a local cubic midline fit.

    Equal arc-spacing coordinates are centered on keypoint 10. Points 21 and 22
    (eyes) are never used. Positive sign is clockwise head-to-tail bending.
    """
    if (not isinstance(neighborhood, (int, np.integer)) or neighborhood < 5
            or neighborhood > 21 or neighborhood % 2 != 1):
        raise ValueError("Curvature neighborhood must be odd, between 5 and 21")
    indices = np.arange(10-neighborhood//2, 11+neighborhood//2)
    u = indices / 20.0 - 0.5
    design = np.column_stack([np.ones(neighborhood), u, u*u, u*u*u])
    inverse = np.linalg.pinv(design)
    x = tracks[[f"poseX{i}" for i in indices]].to_numpy(dtype=float)
    y = tracks[[f"poseY{i}" for i in indices]].to_numpy(dtype=float)
    dx, dy = x @ inverse[1], y @ inverse[1]
    ddx, ddy = 2 * (x @ inverse[2]), 2 * (y @ inverse[2])
    speed = np.hypot(dx, dy)
    valid = np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1) & (speed > 1e-8)
    out = np.full(len(tracks), np.nan)
    out[valid] = (dx[valid]*ddy[valid] - dy[valid]*ddx[valid]) / speed[valid]**3
    return out


def collective(tracks_with_kinematics, length_scale, low_speed=.5, min_fraction=.8):
    """Per-frame heading alignment, spread and centroid-relative circulation."""
    _scale(length_scale)
    if not np.isfinite(low_speed) or low_speed <= 0 or not 0 < min_fraction <= 1:
        raise ValueError("Low speed must be positive and min_fraction in (0,1]")
    x_col, y_col = ("xs", "ys") if {"xs", "ys"}.issubset(tracks_with_kinematics.columns) else ("X", "Y")
    frames, fish, ordered, a = _dense(tracks_with_kinematics, [x_col, y_col, "ANGLE", "vx", "vy"])
    position = np.stack([a[x_col], a[y_col]], axis=2)
    velocity = np.stack([a["vx"], a["vy"]], axis=2)
    if not np.isfinite(a["ANGLE"]).all():
        raise ValueError("Nonfinite collective heading")
    relative = position - position.mean(axis=1, keepdims=True)
    radius = np.linalg.norm(relative, axis=2)
    centroid_v = velocity.mean(axis=1)
    all_velocity = np.isfinite(velocity).all(axis=(1, 2))
    all_geometry = np.isfinite(position).all(axis=(1, 2))
    all_valid = all_velocity & all_geometry
    relative_v = velocity - centroid_v[:, None, :]
    relative_speed = np.linalg.norm(relative_v, axis=2)
    eligible = ((radius > 1e-6*length_scale) & (relative_speed >= low_speed*length_scale)
                & all_valid[:, None])
    fractions = eligible.mean(axis=1)
    # Eligibility is unknown when the centroid-relative velocities cannot be computed.
    fractions = np.where(all_valid, fractions, np.nan)
    cross = relative[:, :, 0]*relative_v[:, :, 1] - relative[:, :, 1]*relative_v[:, :, 0]
    normalized = np.zeros_like(cross)
    np.divide(cross, radius*relative_speed, out=normalized, where=eligible)
    counts = eligible.sum(axis=1)
    circulation = np.full(len(frames), np.nan)
    signed = np.full(len(frames), np.nan)
    reference = np.full(len(frames), np.nan)
    valid = all_valid & (fractions >= min_fraction) & (counts > 0)
    signed[valid] = np.clip(normalized[valid].sum(axis=1)/counts[valid], -1, 1)
    circulation[valid] = np.abs(signed[valid])
    reference[valid] = np.sqrt(1/(np.pi*counts[valid]))
    # A little rounding can make an analytic unit circulation exceed one by epsilon.
    circulation[valid] = np.clip(circulation[valid], 0, 1)
    centroid_speed = np.linalg.norm(centroid_v, axis=1)/length_scale
    centroid_speed[~all_velocity] = np.nan
    first = ordered.groupby("frame", sort=True)[["time", "segment"]].first()
    polarization = np.hypot(np.cos(a["ANGLE"]).mean(axis=1), np.sin(a["ANGLE"]).mean(axis=1))
    if "heading_valid" in ordered:
        polarization[~ordered.heading_valid.to_numpy(dtype=bool).reshape(len(frames), len(fish)).all(axis=1)] = np.nan
    return pd.DataFrame({
        "frame": frames, "time": first.time.to_numpy(), "segment": first.segment.to_numpy(),
        "polarization": polarization,
        "spread_bl": np.sqrt((radius**2).mean(axis=1))/length_scale,
        "centroid_speed_bl_s": centroid_speed, "circulation": circulation,
        "eligible_fraction": fractions, "signed_circulation": signed,
        "iid_direction_reference": reference,
    })


def spatial(tracks, length_scale, extent=10, bins=40):
    """All-neighbor occupancy in focal forward/right coordinates.

    histogram[forward_bin, right_bin] contains raw ordered-pair counts. density
    divides by all focal observations and bin area in square body lengths.
    """
    _scale(length_scale)
    if not np.isfinite(extent) or extent <= 0 or not isinstance(bins, (int, np.integer)) or bins < 1:
        raise ValueError("Positive extent and integer bin count required")
    frames, fish, _, a = _dense(tracks, ["X", "Y", "ANGLE"])
    if not all(np.isfinite(values).all() for values in a.values()):
        raise ValueError("Nonfinite spatial inputs")
    edges = np.linspace(-extent, extent, bins+1)
    counts = np.zeros((bins, bins), dtype=float)
    nearest = np.full((len(frames), len(fish)), np.nan)
    off_diagonal = ~np.eye(len(fish), dtype=bool)
    # Chunk frame dimension so larger schools do not allocate a trial-sized NxN tensor.
    for start in range(0, len(frames), 128):
        stop = min(start+128, len(frames))
        x, y, theta = (a[column][start:stop] for column in ["X", "Y", "ANGLE"])
        dx = (x[:, None, :] - x[:, :, None])/length_scale
        dy = (y[:, None, :] - y[:, :, None])/length_scale
        distance = np.hypot(dx, dy)
        distance[:, np.arange(len(fish)), np.arange(len(fish))] = np.inf
        if len(fish) > 1:
            nearest[start:stop] = distance.min(axis=2)
        cosine, sine = np.cos(theta)[:, :, None], np.sin(theta)[:, :, None]
        forward = (dx*cosine + dy*sine)[:, off_diagonal].ravel()
        right = (-dx*sine + dy*cosine)[:, off_diagonal].ravel()
        counts += np.histogram2d(forward, right, bins=(edges, edges))[0]
    focal_count = len(frames)*len(fish)
    pairs = focal_count*(len(fish)-1)
    bin_area = (edges[1]-edges[0])**2
    return {
        "nearest": pd.DataFrame({"frame": np.repeat(frames, len(fish)), "id": np.tile(fish, len(frames)),
                                 "distance_bl": nearest.ravel()}),
        "histogram": counts, "density": counts/(focal_count*bin_area),
        "bin_edges": edges, "focal_count": focal_count,
        "shown_pair_fraction": float(counts.sum()/pairs) if pairs else float("nan"),
    }


def visibility(tracks, network):
    """Observer out-degree including zeros, restricted to covered frames."""
    _single_trial(tracks)
    if network.duplicated(["frame", "id1", "id2"]).any():
        raise ValueError("Duplicate visibility edges")
    if (network.id1 == network.id2).any():
        raise ValueError("Self visibility edges")
    track_keys = pd.MultiIndex.from_frame(tracks[["frame", "id"]])
    for column in ["id1", "id2"]:
        if not pd.MultiIndex.from_frame(network[["frame", column]]).isin(track_keys).all():
            raise ValueError("Dangling visibility endpoint")
    covered = tracks[tracks.frame.isin(network.frame.unique())].sort_values(["frame", "id"])
    keys = pd.MultiIndex.from_frame(covered[["frame", "id"]])
    counts = network.groupby(["frame", "id1"]).size().reindex(keys, fill_value=0)
    degree = covered[["frame", "id"]].reset_index(drop=True).copy()
    degree["degree"] = counts.to_numpy(dtype=int)
    per_frame = degree.groupby("frame", as_index=False).agg(mean_degree=("degree", "mean"))
    pairs = pd.MultiIndex.from_frame(network[["frame", "id1", "id2"]])
    reverse = pd.MultiIndex.from_arrays([network.frame, network.id2, network.id1])
    reciprocity = float(reverse.isin(pairs).mean()) if len(network) else float("nan")
    return {"degree": degree, "per_frame": per_frame, "reciprocal_edge_fraction": reciprocity}


def heading_diagnostics(k, length_scale, low_speed=.5):
    """Describe jumps and sustained travel opposite heading, without exclusion.

    Reverse motion can be real backward movement, a tracking error, or another
    mismatch. These diagnostics do not identify proven head-tail flips. The
    velocity eligibility denominator is computed before any heading jump mask.
    """
    _single_trial(k)
    _scale(length_scale)
    if not np.isfinite(low_speed) or low_speed <= 0:
        raise ValueError("Low-speed threshold must be finite and positive")
    angle = k.ANGLE.to_numpy(dtype=float)
    vx, vy = k.vx.to_numpy(dtype=float), k.vy.to_numpy(dtype=float)
    if not np.isfinite(angle).all():
        raise ValueError("Nonfinite heading diagnostic inputs")
    speed = np.hypot(vx, vy)/length_scale
    eligible = np.isfinite(speed) & (speed >= low_speed)
    slip = (np.arctan2(vy, vx) - angle + np.pi) % (2*np.pi) - np.pi
    reverse = eligible & (np.abs(slip) > np.pi/2)
    unmasked = k.heading_valid.to_numpy(dtype=bool) if "heading_valid" in k else np.ones(len(k), dtype=bool)
    frames = k.frame.to_numpy()
    events = []
    best = {int(fish): {"id": int(fish), "start": None, "end": None, "segment": None, "n": 0}
            for fish in np.sort(k.id.unique())}
    for (fish, segment), positions in k.groupby(["id", "segment"], sort=True).indices.items():
        positions = positions[np.argsort(frames[positions], kind="stable")]
        block_frames = frames[positions]
        step = (np.diff(angle[positions]) + np.pi) % (2*np.pi) - np.pi
        jumps = np.flatnonzero((np.diff(block_frames) == 1) & (np.abs(step) > np.pi/2))
        for index in jumps:
            events.append({"id": int(fish), "segment": int(segment),
                           "prev_frame": int(block_frames[index]), "frame": int(block_frames[index+1]),
                           "signed_wrapped_step": float(step[index])})
        # Retain only reverse samples. A false/ineligible sample or frame gap
        # breaks a run even if reverse motion resumes on the next stored row.
        indices = np.flatnonzero(reverse[positions])
        if not len(indices):
            continue
        cuts = np.flatnonzero((np.diff(indices) != 1) | (np.diff(block_frames[indices]) != 1))+1
        for run in np.split(indices, cuts):
            record = {"id": int(fish), "start": int(block_frames[run[0]]),
                      "end": int(block_frames[run[-1]]), "segment": int(segment), "n": int(len(run))}
            old = best[int(fish)]
            if record["n"] > old["n"] or (record["n"] == old["n"] and record["start"] < old["start"]):
                best[int(fish)] = record
    denominator = int(eligible.sum())
    return {
        "low_speed_bl_s": float(low_speed), "heading_events": events,
        "speed_eligible_rows_before_heading_mask": denominator,
        "reverse_motion_rows": int(reverse.sum()),
        "reverse_motion_fraction": float(reverse.sum()/denominator) if denominator else None,
        "reverse_motion_rows_outside_jump_mask": int((reverse & unmasked).sum()),
        "longest_reverse_runs_per_fish": list(best.values()),
        "interpretation": "Flags reverse travel relative to tracked heading, not proven head-tail flips. "
                          "Sustained intervals are not automatically excluded without video validation.",
        "mask_policy": "Finite speed >= threshold; heading_valid is not used in the primary denominator or runs.",
    }
