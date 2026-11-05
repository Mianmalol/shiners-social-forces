# Golden shiners: tracks with posture, for social-force inference

Free-swimming golden shiners (*Notemigonus crysoleucas*) in groups of 10, 30, 70 and 151,
filmed from above. There are ten trials, about 13 minutes each at 29.97 frames per
second. For every fish in every frame the tables give a position, a measured heading,
a 21-point body midline and both eye positions. Identities are continuous through each
trial.

Source: Davidson JD, Sosna MMG, Twomey CR, Sridhar VH, Leblanc SP, Couzin ID (2021).
Collective detection based on visual information in animal groups. *J R Soc Interface*
18: 20210142. doi:10.1098/rsif.2021.0142. The raw data is on Dryad,
doi:10.5061/dryad.sbcc2fr2h, under CC0 1.0, and so is this derivative.

## Files

```
shiners-social-forces/
  README.md                       this file
  dataset.yaml                    mosaic manifest (its notes field repeats the conventions below)
  tracks/convert-schooltracker_midline_fov_h5.1.0-8c8f6ad206/
      <group>__<trial>.parquet    one table per trial: positions, heading, posture (4.3 GB)
  features/visual-network__from__tracks/0.1-65625b7549/
      <group>__<trial>.parquet    one table per trial: who sees whom, per frame (2.8 GB)
  media/joined/<hash>.joined.mp4  one video per trial, segments joined (1.4 GB)
  media_raw/150-fish/150-fish/calibrated_lowres30.25.mp4    the 150-fish video
```

| group | trials | fish | frames per trial |
| --- | --- | --- | --- |
| `10-fish` | 0066, 0105, 0126 | 10 | about 24,580 |
| `30-fish` | 0084, 0115, 0120 | 30 | about 24,580 |
| `70-fish` | 0103, 0107, 0124 | 70 | about 24,570 |
| `150-fish` | 150-fish | 151 | 17,999 |

The 150-fish trial has 151 tracks. Its directory name and its track count are both kept
as they are in the source.

## Reading a table

You need only pandas and pyarrow; mosaic is not required.

```python
import pandas as pd, glob
path = glob.glob("shiners-social-forces/tracks/*/10-fish__0066.parquet")[0]
df = pd.read_parquet(path)            # one row per fish per frame
# positions of all fish, frame by frame, as an array (frames, fish, 2):
wide = df.pivot(index="frame", columns="id", values=["X", "Y"])
```

## Columns

| column | meaning |
| --- | --- |
| `frame` | video frame number (see "Time and gaps") |
| `time` | seconds, `frame / 29.97` |
| `id` | fish identity, constant through the trial |
| `segment` | which recording segment the row comes from (0-6) |
| `X`, `Y` | body centre, in pixels: the mean of the 21 midline points |
| `ANGLE` | heading in radians, `atan2(dy, dx)` in image coordinates |
| `body_length` | visible body length in pixels |
| `poseX0..20`, `poseY0..20` | body midline in pixels, from 0 = head to 20 = tail tip |
| `poseX21`, `poseY21` | left eye, in pixels |
| `poseX22`, `poseY22` | right eye, in pixels |
| `group`, `sequence` | group size and trial |

## Conventions

- **Units are video pixels.** The image is 1920 × 1032 px (1890 × 1080 for the 150-fish
  trial), and **y points down**. A fish's right side is the heading rotated by +90°
  in these coordinates. No pixel-to-centimetre scale is recorded in the source data;
  `body_length` (about 38 px) is the natural length unit.
- **The heading is measured**, from the tracker's body-axis fit, not derived from the
  direction of travel. It differs from the direction of travel by a median of 3.5°.
- **The midline** consists of 21 points at equal arc spacing along the body. Its total
  length equals `body_length`. Checked against the video, the midline points lie a
  median of 0.5 px from the dark centreline of the fish.
- **`body_length` is half the tracker's raw value.** The tracker's value overshoots the
  visible fish about two-fold. In the nine 10-, 30- and 70-fish trials the halved value
  matches the visible fish in the video. The same factor of 0.5 is used for the
  150-fish trial, which was filmed with a different camera setup (1890 × 1080 video).
  There the visible fish measures about 15% longer than `body_length`. No per-trial
  correction is applied, so the midline and `body_length` of that trial are about 15%
  short. The midline shape still fits the fish (median lateral offset 0.5 px).

## Time and gaps

Each trial was recorded as seven consecutive segments of about 2 minutes. The tracker
skipped one video frame per segment, so **one frame is missing at every segment join**.
The trajectories confirm this: extrapolating each fish's velocity across a join gives
about 2 frames elapsed. `frame` counts video frames, so at a join it jumps by 2 and
`segment` increments.

The positions next to a join are also noisier. The first tracked frame of a segment
deviates about 1.5 px from a smooth path, against about 0.5 px elsewhere, and the last
frame before a join about 0.8 px. A velocity computed with the correct time step is
therefore still about 1.2 times too high across a join, and an acceleration shows a
spike there.

**For anything that takes time derivatives, treat each segment as its own continuous
recording.** Do not difference across a join:

```python
for (fish, seg), track in df.groupby(["id", "segment"]):
    t = track["time"].to_numpy()
    vx = np.gradient(track["X"].to_numpy(), t)  # never spans a join
```

That gives 7 continuous pieces of about 2 minutes per trial, with identities carried
through.

## Identity

Within a segment, identities come from the tracker. Each segment numbers its fish
independently, so identities across a join were **reconstructed**. Every fish in the
first frame of a segment was matched to a fish in the last frame of the previous segment
by a global position assignment, with one frame of motion between them. The matched
distance is typically a few pixels, while the next-nearest candidate is typically more
than ten times further away. In rare cases two fish cross exactly at a join, and the
assignment between them is then less certain. Over all joins, 12 of 1,980 fish had a
runner-up nearer than their own match.

`detected` is 1 for every fish in every frame of the source, so the tables have no gaps
within a segment.

## Visual networks

`features/visual-network__from__tracks/0.1-65625b7549/<group>__<trial>.parquet` lists,
for every frame, which fish each fish can see. One row is one directed link: fish `id1`
sees fish `id2` in frame `frame`. **A pair that is absent from a frame is not visible in
that frame.**

| column | meaning |
| --- | --- |
| `frame` | as in the tracks |
| `id1` | the observer |
| `id2` | the fish it sees |
| `n_rays` | rays (of 1000 per eye) whose first hit is `id2` |
| `angular_size_deg` | the angle `id2` covers in `id1`'s view, `n_rays * 360 / 1000` |
| `distance` | body-centre distance, pixels |
| `perspective` | 0 if `id1 < id2`, else 1 (mosaic's pair-table convention; ignore it) |

The method is the ray casting of Davidson et al. (2021). Each fish is a four-sided
outline: head, right eye, tail tip, left eye. From each eye, 1000 rays are cast
evenly over 360 degrees, and each ray stops at the first outline it meets. Fish `id1`
sees `id2` when at least one ray from either eye hits `id2` first. Each eye covers its
own side plus 12.5 degrees across the midline, which leaves a 25-degree blind wedge
behind the fish. Fish of the same group block each other's view; there is no partial
transparency.

To get the network of one frame as an adjacency matrix:

```python
net = pd.read_parquet("features/visual-network__from__tracks/0.1-65625b7549/10-fish__0066.parquet")
f = net[net.frame == 1000]
A = pd.crosstab(f.id1, f.id2).reindex(index=range(10), columns=range(10), fill_value=0)
```

On average a fish sees 6.8 of the other 9 fish in a 10-fish group, and 85 percent of
links are reciprocated.

## Videos

Each trial's seven segments are joined into one video. **Frame `i` of the joined
video is track frame `i`**, counted from 0. Frame 0 of each segment has no tracks
(see "Time and gaps"), but the video keeps it.

| trial | video |
| --- | --- |
| 10-fish/0066 | `media/joined/e29d6495a5.67dcc35d06.joined.mp4` |
| 10-fish/0105 | `media/joined/b98be8fc26.67dcc35d06.joined.mp4` |
| 10-fish/0126 | `media/joined/e1d5eec202.67dcc35d06.joined.mp4` |
| 30-fish/0084 | `media/joined/9d17691756.67dcc35d06.joined.mp4` |
| 30-fish/0115 | `media/joined/84afa71461.67dcc35d06.joined.mp4` |
| 30-fish/0120 | `media/joined/3469428553.67dcc35d06.joined.mp4` |
| 70-fish/0103 | `media/joined/80b84cbbf1.67dcc35d06.joined.mp4` |
| 70-fish/0107 | `media/joined/bc886afc4c.67dcc35d06.joined.mp4` |
| 70-fish/0124 | `media/joined/7fec52a075.67dcc35d06.joined.mp4` |
| 150-fish | `media_raw/150-fish/150-fish/calibrated_lowres30.25.mp4` (a single video, not joined) |

The joined videos are **AV1**, re-encoded from the original MPEG-4 at near-lossless
quality (CRF 14). VLC and current browsers play them. In Python, read frames with PyAV
(`pip install av`), because OpenCV's pip builds often cannot decode AV1. The original
segment videos are on Dryad.

Frame alignment between the tracks and the video is accurate to about one frame.
Measured against the video, the mapping is between frame `i` and frame `i - 1`. The
tracks themselves do not depend on this.
