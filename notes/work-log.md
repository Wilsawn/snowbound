# Work log (Claude's off-computer runs)
Newest first. Each entry: date, what was done, files written, anything Delo needs to look at.

## Nov 20, 2026 (evening)
- Done: queue 6 and 7 (both added by Claude; remove them from the queue if you disagree).
- 6: full 60 s storm (117 scans): from the true start 100% recovered, lateral 1.1 cm, longitudinal 1.9 cm, heading 0.04 deg. From 1 m / 5 deg off: 87% overall, but only 62% in seconds 40-60 (100% in 0-40 s): a weak stretch worth a look. File: notes/results-60s-storm.md, raw CSVs in results/storm-60s/.
- 7: scripts/sweep_basin.py. Critic review applied: one fixed search window for all sizes (3.5 m), capped results shown as ">= X m", directions measured from the direction of travel with a random twist, optional joint position + heading test.
  - Prototype, 2 points in the weak stretch, window 3.5 m, 5 deg heading added: basin 1.0 m (1 m: 4 of 4 directions recover, 2 m: 1 of 4, 3 and 4 m: 0). Heading alone at +/-5 deg: recovered.
  - Lesson: with the search window tied to the offset, both points looked like >= 2 m. The window choice changes the answer, so always report it.
- Small change to my own scripts/score_60s.py: --save CSV option and a first_radius setting for ICP.
- Next: download the Jan 19 control (notes/control-drive.md), then run sweep_basin.py on the Mac for both drives over the same stretch.
- Limits: 2 points is not a result; scipy ICP; map from ground-truth poses.

## Nov 20, 2026 (afternoon)
- Done: queue 3 (Blind budget design, notes/blind-budget.md) and 4 (scripts/score_60s.py). Also scripts/fetch_control.py (download any control drive without editing fetch_boreas.py). Builder, then critic, then fixes.
- Checked the control: Jan 19 2021 camera frames (S3, viewed in Chrome) show a dry road, cloudy, no falling snow.
- score_60s.py, 20 storm scans over 20 s, map from ground-truth poses:
  - true start: lateral 0.5 cm, longitudinal 1.7 cm (mean +1.6), heading 0.03 deg, recovered 100%
  - start 1 m / 5 deg off: lateral 3.8 cm, longitudinal 13.7 cm, recovered 95%
  - critic found: no deskew gave 19.4 cm longitudinal and 90% recovery from the true start; deskew (GT velocity + yaw rate, per-point time) fixed it. Huber weights must start loose (first strict version dropped 1 m recovery to 15%).
- Delo to look at: run `uv run python scripts/score_60s.py --seconds 60 --every 5` on the Mac (open3d not needed). Numbers are NOT comparable to Burnett's 2.3 cm (our map uses ground-truth poses).
- Limits: only 20 scans tested on the VM; scipy ICP, not Open3D yet; deskew uses ground truth, not odometry.

## Nov 20, 2026 (morning)
- Done: queue 1 (paper guide) and 2 (control drive). Builder agents researched, a separate critic checked every number against the paper, the Boreas site, S3 and Environment Canada.
- Files: notes/paper-burnett.md, notes/control-drive.md
- Delo to look at: (1) "2.3 cm" is from arXiv v3 (2023); the 2022 RA-L version says 4.7 cm lateral. Cite v3 by name. (2) Watch 2 YouTube previews to pick the control (Jan 19 vs Dec 18). (3) OK a small change to scripts/fetch_boreas.py (--drive option).
- Limits: "not snowing" on Jan 19 comes from the official tag; weather records show 0.6 cm light snow at Pearson that day. Road wetness not checked.
