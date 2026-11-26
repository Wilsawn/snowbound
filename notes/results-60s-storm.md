# First numbers: 60 s of the storm drive (Nov 20, 2026)
Produced by scripts/score_60s.py. Raw per-scan CSVs: results/storm-60s/.

Setup: storm drive boreas-2021-01-26-11-22, first 60 s of the downloaded scans (speed about 6 to 10 m/s), every 5th scan (117 scans). Map from boreas-2020-11-26-13-58 built with ground-truth poses. Scans deskewed with ground-truth velocity and yaw rate. scipy point-to-plane ICP with Huber weights. Ran on the VM (Linux), not the Mac.

| Start guess | Recovered (< 30 cm, < 2 deg) | Lateral RMSE | Longitudinal RMSE | Height RMSE | Heading RMSE |
|---|---|---|---|---|---|
| Ground truth | 100% | 1.1 cm (mean +0.1) | 1.9 cm (mean +1.8) | 3.0 cm (mean -2.9) | 0.04 deg |
| 1 m / 5 deg off | 87% | 13.9 cm | 18.9 cm | 3.1 cm | 0.47 deg |

By 20 s piece, starting 1 m / 5 deg off: 0-20 s 100%, 20-40 s 100%, **40-60 s 62%**. Something about the road in the last 20 s makes it harder to re-find the car: the kind of weak spot the Blind budget map is meant to show. Next: look at that stretch (camera frame + map) to see why.

What these numbers are NOT:
- Not comparable to Burnett et al. (2.3 cm lateral, v3): our map uses ground-truth poses, our ICP and settings differ, and this is 60 s, not the full drive.
- The small steady biases (longitudinal +1.8 cm, height -2.9 cm) are inside the ground truth's own 2 to 4 cm error; could be calibration or map stacking. Watch them, don't explain them yet.
- No control day yet (Jan 19 lidar not downloaded), so nothing about snow vs no snow so far.
