"""Check coverage accounting, integer boundaries, and corrupt saved inputs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("plot_eligibility", Path(__file__).resolve().parents[1] / "scripts/plot_eligibility.py")
plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot)


def fixture(fish=70, counts=(np.nan, 0, 41, 55, 56, 70)):
    counts = np.asarray(counts, dtype=float)
    fractions = counts / fish
    valid = np.isfinite(counts) & (fractions >= .8)
    summary = {"fish": fish, "quality": {"frames": len(counts)},
               "circulation": {"n": int(valid.sum())},
               "circulation_eligible_frame_fraction": float(valid.mean())}
    config = {"circulation_min_fraction": .8, "low_speed_bl_s": .5}
    frame = pd.DataFrame({"frame": np.arange(1, len(counts) + 1),
                          "eligible_fraction": fractions,
                          "eligible_fish_count": counts,
                          "circulation": np.where(valid, .7, np.nan),
                          "centroid_speed_bl_s": np.where(np.isfinite(counts), .1, np.nan)})
    return summary, config, frame


class EligibilityTests(unittest.TestCase):
    def test_mixed_frames_keep_unavailable_in_coverage_but_not_histogram(self):
        result = plot.eligibility_summary("test", *fixture())
        self.assertEqual(result["required_qualifying_fish"], 56)
        self.assertEqual(result["accepted_frames"], 2)
        self.assertEqual(result["defined_but_below_requirement_frames"], 3)
        self.assertEqual(result["velocity_undefined_frames"], 1)
        self.assertEqual(result["coverage_all_tracked_frames"], 2 / 6)
        self.assertEqual(sum(result["histogram_frame_count"]), 5)
        self.assertEqual(result["histogram_frame_count"][0], 1)
        self.assertEqual(result["median_qualifying_fish"], 55)

    def test_fractional_requirement_rounds_up_and_tolerates_csv_roundoff(self):
        s, c, f = fixture(151, (np.nan, 120, 121, 151))
        f.loc[2, "eligible_fraction"] += 1e-12
        result = plot.eligibility_summary("test", s, c, f)
        self.assertEqual(result["required_qualifying_fish"], 121)
        self.assertEqual(result["accepted_frames"], 2)
        self.assertEqual(result["low_speed_bl_s"], .5)

    def test_all_unavailable_has_no_histogram_or_median(self):
        result = plot.eligibility_summary("test", *fixture(10, (np.nan, np.nan)))
        self.assertEqual(result["coverage_all_tracked_frames"], 0)
        self.assertIsNone(result["median_qualifying_fish"])
        self.assertEqual(sum(result["histogram_frame_count"]), 0)

    def test_count_match_alone_does_not_hide_wrong_accepted_frames(self):
        s, c, f = fixture()
        f.loc[3, "circulation"], f.loc[4, "circulation"] = .7, np.nan
        with self.assertRaisesRegex(ValueError, "frame mask differs"):
            plot.eligibility_summary("test", s, c, f)

    def test_loader_rejects_changed_input_against_frozen_provenance(self):
        s, c, f = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "trials" / "test"
            folder.mkdir(parents=True)
            (folder / "summary.json").write_text(json.dumps(s))
            (folder / "config.json").write_text(json.dumps(c))
            f.to_csv(folder / "collective.csv", index=False)
            provenance = {
                "output_hashes": {name: plot.digest(folder / name) for name in ("summary.json", "config.json", "collective.csv")},
                "source_hashes": {"src/shiners/metrics.py": plot.digest(plot.REPO / "src/shiners/metrics.py")},
            }
            (folder / "provenance.json").write_text(json.dumps(provenance))
            row, hashes = plot.load_trial(root, "test")
            self.assertEqual(row["accepted_frames"], 2)
            self.assertIn("trials/test/provenance.json", hashes)
            # The numerical values are unchanged, but source bytes no longer
            # match the frozen run. The loader must still reject the artifact.
            with (folder / "collective.csv").open("a") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ValueError, "provenance hash mismatch"):
                plot.load_trial(root, "test")

    def test_rejects_bad_fractions_counts_and_denominators(self):
        mutations = [
            (lambda s, c, f: f.__setitem__("eligible_fraction", [np.nan, 0, .501, 55/70, .8, 1]), "integer fish"),
            (lambda s, c, f: f.loc.__setitem__((1, "eligible_fraction"), np.inf), "infinities"),
            (lambda s, c, f: f.loc.__setitem__((1, "eligible_fraction"), -.1), "outside"),
            (lambda s, c, f: f.loc.__setitem__((4, "eligible_fish_count"), 55), "saved eligible"),
            (lambda s, c, f: f.loc.__setitem__((1, "frame"), 1), "unique increasing"),
            (lambda s, c, f: s["quality"].update(frames=7), "denominator"),
            (lambda s, c, f: s.update(circulation_eligible_frame_fraction=.4), "coverage"),
            (lambda s, c, f: c.update(circulation_min_fraction=1.1), "minimum fraction"),
            (lambda s, c, f: f.loc.__setitem__((1, "centroid_speed_bl_s"), np.nan), "velocity masks"),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                s, c, f = fixture()
                mutate(s, c, f)
                with self.assertRaisesRegex(ValueError, message):
                    plot.eligibility_summary("test", s, c, f)


if __name__ == "__main__":
    unittest.main()
