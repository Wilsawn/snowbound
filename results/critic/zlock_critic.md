# Critic pass: notes/results-zlock.md (height-locked route rerun), Nov 23, 2026

## Verdict: PASS on the numbers, with 3 wording fixes needed before the note goes out

Every number in the note was recomputed with independent pandas code from the CSVs (not by rerunning
compare_zlock.py). All of them match. Three plain-words claims are not supported as written, and the
"did the lock hold" check is weaker than the note implies. Details below.

## 1. Numbers recomputed (all match)

- Rows: 271 in all six CSVs; pair ids identical in the same order across all six.
- route_pairs*.csv agree exactly with route_storm*/route_control* (basin and capped columns, both runs).
- Headline table: storm median 2.5 / 2.5 m; no-snow median 3 / 3 m; storm capped 91 / 120; no-snow capped
  201 / 202; smaller/same/bigger 147/114/10 and 111/142/18; diff median -0.5 / 0 m; storm at 0 m 23 / 18;
  both days 0 m 14 / 12. All correct.
- Per-spot movement: storm bigger 83, same 170, smaller 18, median 0, mean +0.179 m (note rounds to +0.18);
  no snow bigger 13, same 254, smaller 4, median 0, mean +0.012 m (note +0.01). Correct.
- The 23 former-zero storm spots: list of 1-based positions, pair ids and locked values all correct
  (7 recover: spots 2, 3, 20, 115, 116, 258, 270; 16 still 0 m). 14 of the 23 had no snow 0 m too; the 14
  locked no-snow values in the note (five 0 m, one 0.25 m at spot 115, eight 0 m) are correct in order.
- New zeros: spots 22 (001_009, was 0.75 m) and 23 (001_010, was 0.25 m). Correct.
- Per segment (storm_segments(400.0), matched by storm scan_time_us): 6 segments, lengths 463, 505, 421,
  2470, 3295, 432 m; counts 18, 28, 13, 82, 113, 17 (sum 271, every point in exactly one segment); all 24
  medians match the table.
- First study: 22 of 22 basin_pairs.csv spots have a route spot within 5 m (max 4.53 m, 22 distinct route
  spots). Storm medians: study 1.75 m, route original 1.375 m, route locked 1.5 m. Correct.
- Site spots table (42, 90, 117, 16, 2, 3): all 24 cells correct, including the "3 m+" marks.

## 2. Lock check

- dz_max_m is 0.0 at all 271 rows of route_storm_zlock.csv and all 271 of route_control_zlock.csv.
- icp_zlock (scripts/sweep_route_zlock.py lines 37 to 61): A keeps only columns [2,3,4] (yaw, x, y);
  the update is T[:3,:3] = rot_z(dx[0]) @ R and T[:3,3] = c + [dx, dy, 0]. A rotation about world z keeps
  the body z axis's tilt, so roll and pitch cannot change, and T[2,3] is never written. The early exit
  (under 50 matches) returns T untouched. The code genuinely cannot move height, roll or pitch.
- The monkeypatch (line 64) is a module-level statement, so it also runs in each spawned Pool worker when
  the main module is re-imported. DZ is reset inside the day loop of run_chunk (per point-day, not just per
  point as the comment says), and recorded per day. That is fine.
- FINDING (weak check): dz_max_m = 0 is a tautology, not evidence. icp_zlock cannot change z by
  construction, so it always records 0. Worse, if the patch had silently failed and the free matcher had
  run, DZ would never be touched and dz_max_m would still read 0. The note presents "largest height change
  0.000000 m" as the proof the lock held. The real proof is that the locked results differ from the
  original run at 101 storm and 17 no-snow point-days despite identical seeds and a deterministic matcher
  (the free matcher would have reproduced the original exactly). Say that in the note instead, or in
  addition.

## 3. Pairing check (pass)

scan_time_us, east and north are bit-identical between route_storm.csv and route_storm_zlock.csv and
between route_control.csv and route_control_zlock.csv; pair ids identical and in the same order.

## 4. Sanity of ok_per_size, basin and capped (pass)

All 1084 rows (4 CSVs) have 10 ok_per_size entries. Recomputing basin with the sweep_point rule (largest
size such that every size up to it had ok >= NEED, NEED = ceil(8*7/8) = 7) reproduces basin_radius_m at
every row, capped equals the "every size passed" flag at every row, and capped == 1 iff basin == 3 holds.

## 5. Plain-words claims not supported by the numbers

- FINDING (wrong): "Segments 2, 3 and 6 keep a storm deficit (... 1.25 m vs 0.5 m ...)". Segment 6 has
  storm 1.25 m and no snow 0.5 m: the storm is BETTER there by 0.75 m, so it is not a storm deficit. Only
  segments 2 and 3 keep a deficit. Rewrite as: segments 2 and 3 keep a storm deficit; segment 6 is the one
  stretch where no snow is worse (0.5 m vs 1.25 m storm), unchanged in kind from the original run.
- FINDING (misleading label): "The first 460 m, the stretch of the first study" and the heading "The first
  460 m against the first study". The 22 route spots nearest the first-study spots are 001_008 to 003_005
  (spots 21 to 42), and every one of them falls in route segment 2 (505 m), not segment 1 (463 m, the
  route's first 460 m). The study stretch is a 460 m street, but it is not the first 460 m of the route.
  The medians are right; rename the section "The first study's street (22 route spots within 5 m, all in
  segment 2)". It also means segment 1's jump from 1.375 m to 3 m is unrelated to the first study's 1.75 m.
- FINDING (overreach): "Segments 1, 4 and 5 (the long open stretches)". Segment 1 is 463 m, about the same
  length as segments 2, 3 and 6 (505, 421, 432 m). Only 4 and 5 are long. Drop segment 1 from "long".
- Caveat (not wrong, but worth one sentence): "No snow barely moves ... which is what we expected: it had no
  snow in the air to sink into." No snow still changed at 17 of 271 spots (13 up, 4 down), so the lock by
  itself shifts some answers without any snow. The storm gain (83 up vs 13) is still far larger, which is
  the point; just do not imply the control change is zero.
- Note for the parent: the task brief said src/fetch_route.py; there is no src/ folder, the segment code is
  scripts/fetch_route.py (compare_zlock.py imports it from scripts/). Not a note error.
- Minor: "+0 m" in the table for the median gap is the compare script's +g formatting; "0 m" reads better.

## Summary

Numbers: 100 percent reproduced. Fix the segment 6 "deficit" sentence, relabel the first-study section
(it is segment 2, not the first 460 m of the route), drop segment 1 from "long open stretches", and say
what actually proves the lock (results changed under identical seeds), since dz_max_m cannot.
