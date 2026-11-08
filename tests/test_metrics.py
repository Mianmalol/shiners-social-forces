"""Synthetic checks derived from analytic geometry, not real-data expectations."""

import unittest
import json
import numpy as np
import pandas as pd

from shiners.metrics import kinematics, curvature, collective, spatial, visibility, heading_diagnostics


def trajectory(n=61, dt=.1):
    t = np.arange(n)*dt
    return pd.DataFrame({"frame": np.arange(n), "id": 0, "segment": 0,
                         "time": t, "X": 3*t, "Y": 4*t, "ANGLE": 0.})


def frame(x, y, theta=None, vx=None, vy=None):
    n = len(x)
    return pd.DataFrame({"frame": 0, "time": 0., "segment": 0, "id": np.arange(n),
                         "X": x, "Y": y, "ANGLE": np.zeros(n) if theta is None else theta,
                         "vx": np.zeros(n) if vx is None else vx, "vy": np.zeros(n) if vy is None else vy})


def midline(x, y):
    return pd.DataFrame({**{f"poseX{i}": [v] for i, v in enumerate(x)},
                         **{f"poseY{i}": [v] for i, v in enumerate(y)},
                         "poseX21": [1e9], "poseY21": [-1e9]})


class KinematicsTests(unittest.TestCase):
    def test_constant_velocity_and_preserved_index(self):
        tr = trajectory().sample(frac=1, random_state=1)
        out = kinematics(tr)
        self.assertTrue(out.index.equals(tr.index))
        valid = out.frame.between(6, 54)
        np.testing.assert_allclose(out.loc[valid, "vx"], 3, atol=1e-10)
        np.testing.assert_allclose(out.loc[valid, "vy"], 4, atol=1e-10)
        np.testing.assert_allclose(out.loc[valid, "ax"], 0, atol=1e-9)
        self.assertTrue(out.loc[~valid, ["vx", "vy", "ax", "ay", "turn_rate"]].isna().all().all())

    def test_acceleration_and_wrapped_signed_turn(self):
        tr = trajectory()
        tr["X"] = 2*tr.time**2 + 3*tr.time
        tr["ANGLE"] = (3 + .7*tr.time + np.pi) % (2*np.pi) - np.pi
        out = kinematics(tr)
        np.testing.assert_allclose(out.ax.dropna(), 4, atol=1e-9)
        np.testing.assert_allclose(out.turn_rate.dropna(), .7, atol=1e-10)

    def test_gaps_and_segment_boundaries_never_bridge(self):
        tr = trajectory(100)
        tr = tr[tr.frame != 40].copy()
        tr.loc[tr.frame > 40, "X"] += 1000
        tr.loc[tr.frame >= 70, "segment"] = 1
        out = kinematics(tr)
        for center in [40, 70]:
            # Extra sample removes noisy block-edge data from retained windows.
            affected = out.frame.between(center-6, center+5)
            self.assertTrue(out.loc[affected, "vx"].isna().all())
        np.testing.assert_allclose(out.vx.dropna(), 3, atol=1e-9)

    def test_irregular_sampling_is_rejected_even_short_block(self):
        tr = trajectory(8)
        tr.loc[4, "time"] += .01
        with self.assertRaisesRegex(ValueError, "Irregular"):
            kinematics(tr)

    def test_heading_jump_contaminates_only_heading_metrics_and_sg_support(self):
        tr = trajectory()
        tr.loc[tr.frame >= 30, "ANGLE"] = np.pi
        tr["poseX0"] = tr.X+1; tr["poseX20"] = tr.X-1
        tr["poseY0"] = tr.Y; tr["poseY20"] = tr.Y
        out = kinematics(tr)
        self.assertEqual(out.loc[out.heading_jump, "frame"].tolist(), [29, 30])
        self.assertEqual(out.loc[~out.heading_valid, "frame"].tolist(), list(range(24, 36)))
        self.assertTrue(out.loc[~out.heading_valid, "turn_rate"].isna().all())
        self.assertTrue(out.loc[~out.heading_valid, "vx"].notna().all())
        self.assertTrue(out.heading_valid.iloc[0])  # A kinematic edge is not a bad heading.
        self.assertAlmostEqual(abs(out.heading_axis_error.iloc[40]), np.pi)
        organized = collective(out, 1)
        self.assertTrue(np.isnan(organized.polarization.iloc[29]))
        self.assertEqual(organized.polarization.iloc[0], 1)


class CurvatureTests(unittest.TestCase):
    def test_straight_line_and_degenerate_curve(self):
        np.testing.assert_allclose(curvature(midline(np.linspace(0, 20, 21), np.zeros(21))), 0, atol=1e-12)
        self.assertTrue(np.isnan(curvature(midline(np.ones(21), np.ones(21)))[0]))

    def test_circular_arc_sign_and_translation(self):
        angle = np.linspace(-.3, .3, 21)
        # Increasing angle on an image-coordinate circle is clockwise.
        for radius in [10., 100.]:
            tr = midline(1000+radius*np.cos(angle), 2000+radius*np.sin(angle))
            self.assertAlmostEqual(curvature(tr)[0], 1/radius, delta=1e-3/radius)
            reflected = midline(1000+radius*np.cos(angle), 2000-radius*np.sin(angle))
            self.assertAlmostEqual(curvature(reflected)[0], -1/radius, delta=1e-3/radius)


class CollectiveTests(unittest.TestCase):
    def test_parallel_translation_is_aligned_but_circulation_undefined(self):
        tr = frame([-1, 1], [0, 0], vx=[3, 3], vy=[4, 4])
        out = collective(tr, 2).iloc[0]
        self.assertEqual(out.polarization, 1)
        self.assertAlmostEqual(out.spread_bl, .5)
        self.assertAlmostEqual(out.centroid_speed_bl_s, 2.5)
        self.assertTrue(np.isnan(out.circulation))
        self.assertEqual(out.eligible_fraction, 0)

    def test_circular_motion_and_translation_invariance(self):
        a = np.arange(8)*2*np.pi/8
        tr = frame(5*np.cos(a), 5*np.sin(a), theta=a+np.pi/2,
                   vx=-2*np.sin(a), vy=2*np.cos(a))
        out = collective(tr, 1).iloc[0]
        self.assertAlmostEqual(out.circulation, 1)
        self.assertAlmostEqual(out.signed_circulation, 1)
        self.assertAlmostEqual(out.iid_direction_reference, np.sqrt(1/(8*np.pi)))
        self.assertAlmostEqual(out.polarization, 0, delta=1e-12)
        tr["vx"] += 20; tr["vy"] -= 7
        self.assertAlmostEqual(collective(tr, 1).circulation.iloc[0], 1)
        tr["vx"] *= -1; tr["vy"] *= -1
        reversed_out = collective(tr, 1).iloc[0]
        self.assertAlmostEqual(reversed_out.signed_circulation, -1)
        self.assertAlmostEqual(reversed_out.circulation, 1)

    def test_invalid_velocity_and_insufficient_eligibility(self):
        tr = frame([-1, 1], [0, 0], vx=[0, 0], vy=[1, -1])
        tr.loc[0, "vx"] = np.nan
        out = collective(tr, 1).iloc[0]
        self.assertTrue(np.isnan(out.circulation))
        self.assertTrue(np.isnan(out.centroid_speed_bl_s))
        self.assertTrue(np.isnan(out.eligible_fraction))
        tr = frame([0, 1, -1], [0, 0, 0], vy=[0, 1, -1])
        out = collective(tr, 1).iloc[0]
        self.assertAlmostEqual(out.eligible_fraction, 2/3)
        self.assertTrue(np.isnan(out.circulation))


class SpatialVisibilityTests(unittest.TestCase):
    def test_known_body_frame_direction_and_normalization(self):
        # Fish 0 points down: displacement (2,1) is forward=1, right=-2.
        tr = frame([0, 2], [0, 1], theta=[np.pi/2, 0])
        out = spatial(tr, 1, extent=4, bins=8)
        self.assertAlmostEqual(out["density"].sum(), 1)
        self.assertEqual(out["focal_count"], 2)
        self.assertEqual(out["shown_pair_fraction"], 1)
        np.testing.assert_allclose(out["nearest"].distance_bl, np.sqrt(5))
        self.assertEqual(out["histogram"][5, 2], 1)
        # The reverse pair seen by fish 1 has forward=-2, right=-1.
        self.assertEqual(out["histogram"][2, 3], 1)

    def test_out_of_view_pairs_do_not_change_focal_denominator(self):
        tr = frame([0, 1, 20], [0, 0, 0])
        out = spatial(tr, 1, extent=2, bins=4)
        self.assertAlmostEqual(out["shown_pair_fraction"], 2/6)
        self.assertAlmostEqual(out["density"].sum(), 2/3)

    def test_visibility_zero_degree_and_unknown_frame(self):
        tr = pd.concat([frame([0, 1, 2], [0, 0, 0]), frame([0, 1, 2], [0, 0, 0]).assign(frame=1)], ignore_index=True)
        net = pd.DataFrame({"frame": [0, 0, 0], "id1": [0, 1, 1], "id2": [1, 0, 2]})
        out = visibility(tr, net)
        self.assertEqual(out["degree"].degree.tolist(), [1, 2, 0])
        self.assertEqual(out["degree"].frame.unique().tolist(), [0])
        self.assertEqual(out["per_frame"].mean_degree.iloc[0], 1)
        self.assertAlmostEqual(out["reciprocal_edge_fraction"], 2/3)
        dangling = net.copy()
        dangling.loc[0, "id2"] = 99
        with self.assertRaisesRegex(ValueError, "Dangling"):
            visibility(tr, dangling)


class HeadingDiagnosticTests(unittest.TestCase):
    def test_flip_then_unflip_exposes_sustained_reverse_interval(self):
        tr = trajectory(100)
        tr["Y"] = 0.
        tr.loc[tr.frame.between(30, 69), "ANGLE"] = np.pi
        k = kinematics(tr)
        out = heading_diagnostics(k, 1)
        self.assertEqual([(x["prev_frame"], x["frame"]) for x in out["heading_events"]], [(29, 30), (69, 70)])
        self.assertEqual(out["speed_eligible_rows_before_heading_mask"], 88)
        self.assertEqual(out["reverse_motion_rows"], 40)
        self.assertGreater(out["reverse_motion_rows_outside_jump_mask"], 0)
        self.assertAlmostEqual(out["reverse_motion_fraction"], 40/88)
        self.assertEqual(out["longest_reverse_runs_per_fish"], [{"id": 0, "start": 30, "end": 69, "segment": 0, "n": 40}])
        json.dumps(out, allow_nan=False)

    def test_gaps_segments_and_ineligible_rows_break_reverse_runs(self):
        # Explicit kinematics lets the test isolate run boundaries from SG trim.
        tr = trajectory(20).assign(ANGLE=np.pi, vx=1., vy=0.)
        tr = tr[tr.frame != 5].copy()
        tr.loc[tr.frame >= 12, "segment"] = 1
        tr.loc[tr.frame == 17, "vx"] = np.nan
        out = heading_diagnostics(tr, 1)
        self.assertEqual(out["longest_reverse_runs_per_fish"], [{"id": 0, "start": 6, "end": 11, "segment": 0, "n": 6}])
        # A heading change across the gap must not be described as a one-frame jump.
        tr.loc[tr.frame < 5, "ANGLE"] = 0
        self.assertEqual(heading_diagnostics(tr, 1)["heading_events"], [])

    def test_no_speed_eligible_data_is_json_safe(self):
        tr = trajectory(5).assign(vx=np.nan, vy=np.nan)
        out = heading_diagnostics(tr, 1)
        self.assertIsNone(out["reverse_motion_fraction"])
        self.assertEqual(out["longest_reverse_runs_per_fish"][0]["n"], 0)
        json.dumps(out, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
