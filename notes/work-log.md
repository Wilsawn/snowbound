# Work log (Claude's off-computer runs)
Newest first. Each entry: date, what was done, files written, anything Delo needs to look at.

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
