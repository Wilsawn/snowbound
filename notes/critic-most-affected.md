# Critic: are the "three most affected spots" (2, 3, 16) real snow effects? (Nov 23)

Data critic pass. Scripts (rerun from ~/snowbound with `nice -n 19 uv run python <script>`), all in
scripts/critic/ (copied from the session scratch folder; outputs in results/critic/):
- check_truth.py: rebuilds the chunk 0 and chunk 1 maps exactly as scripts/sweep_route.py run_chunk does
  (build_map every=1, deskew, origin = chunk's first storm pose), runs score_60s.icp_point_to_plane from the
  recorded true pose (push 0, and yaw-only +-5 deg), window 3.5 m. Output truth_icp.csv.
- zlock_sweep.py: reruns sweep_route.sweep_point (same seed per point) with an ICP whose height, roll and
  pitch are locked (only x, y, yaw move). Output zlock.log / zlock_sweep.csv.
- poses_cov.py: storm applanix poses in the first 20 s; map-drive scans within 20 m of every spot. Output map_cov.csv.

## 1. Matcher started at the true pose (push 0)
| spot | pair | day | scan pts | map pts in 20 m | inliers at truth | xy move m | yaw deg | height move m | inliers after |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 000_000 | storm (0.38 m/s) | 21,924 | 51,720 | 0.573 | 0.029 | 0.04 | +0.042 | 0.572 |
| 2 | 000_001 | storm | 30,316 | 53,316 | 0.485 | 0.066 | 0.40 | -2.691 | 0.335 |
| 3 | 000_002 | storm | 23,717 | 44,081 | 0.460 | 0.251 | -0.02 | -2.389 | 0.340 |
| 4 | 000_003 | storm | 21,652 | 45,546 | 0.548 | 0.135 | 0.37 | -2.182 | 0.408 |
| 15 | 001_002 | storm | 25,814 | 45,726 | 0.469 | 0.116 | 0.12 | -2.494 | 0.321 |
| 16 | 001_003 | storm | 31,772 | 51,564 | 0.480 | 0.123 | 0.54 | -2.684 | 0.334 |
| 2 | 000_001 | control | 17,111 | 51,948 | 0.954 | 0.036 | 0.07 | -0.001 | 0.955 |
| 3 | 000_002 | control | 10,775 | 44,035 | 0.965 | 0.016 | 0.08 | -0.017 | 0.965 |
| 15 | 001_002 | control | 12,409 | 45,290 | 0.963 | 0.054 | 0.07 | +0.012 | 0.963 |
| 16 | 001_003 | control | 17,371 | 53,053 | 0.958 | 0.050 | 0.04 | +0.021 | 0.958 |
(inliers = share of scan points within 0.5 m of a map point. Median point-to-plane residual at truth 3.2 to 4.1 cm
for every row; after the storm slides it is 14.0 to 15.7 cm.) Yaw-only push -5 deg moved spot 2 storm 0.342 m
(fails the 0.3 m test), spot 3 0.299 m, spot 16 0.233 m.

Reading: horizontal truth and map agree (control scans stay put, 95 to 97% inliers). Every MOVING storm scan
slides 2.2 to 2.7 m DOWN from the true pose; the stopped one (spot 1) does not. About half the storm points
match nothing (snow kicked up around the moving car; storm scans carry 1.5 to 2.4x the points of the control scans).

## 2. Same sweep with height locked (zlock_sweep.py)
| spot | original room / ok_per_size | height locked |
|---|---|---|
| 1 | 1.75 m, 8|8|8|8|8|8|8|5|2|0 | 2.0 m, 8|8|8|8|8|8|8|7|6|2 |
| 2 | 0 m, 6|5|8|4|5|5|6|4|3|3 | 3 m capped, 8 of 8 at every size |
| 3 | 0 m, 5|6|5|4|4|4|2|3|1|1 | 3 m capped, 8|8|8|8|8|8|8|8|8|7 |
| 15, 16 | 1.0 m, 0.25 m | not finished when stopped (rerun zlock_sweep.py) |

## 3. Map coverage
Map-drive scans on disk within 20 m: spots 1/2/3/4/15/16 = 10/12/8/8/8/9 (storm positions); median over all 271
spots 8 (range 3 to 591). Not thin. Map points within 20 m (3D) are 44k to 53k at all six spots.

## 4. Ground truth (storm applanix, first 20 s after the first scan)
Car starts from a stop at t=0 (spot 1), 4.5 to 5.1 m/s at 6 to 12 s, gentle turns (yaw rate under 0.15 rad/s).
Step length minus speed x dt: max 0.82 cm; heading step minus yaw rate x dt: max 0.28 deg over the whole drive.
Heading plus track angle 45.3 to 46.2 deg at the six spot times, same as drive medians (45.7 storm, 45.7 Jan 19,
45.9 Nov 26). No jumps. Truth is reliable.

## 5. Scene (docs/media/spots)
All in the UTIAS yard: wide snow-covered lot, white dome on the right, low buildings and blue containers, a parked
sedan close on the right at spot 3, no truck blocking the view, no stopped car at 2/3/16. Storm lidar shows a dense
snow plume over a big part of the view at 2, 3, 15, 16. Not a GPS, map or blocking-vehicle artifact.

## Verdict
Spots 2, 3 (and by the same mechanism 16, 15, 4): ARTIFACT OF THE MATCHER, triggered by snow. The snow plume is
real, but the 0 m comes from the test letting height float: the scan sinks about 2.5 m to sit snow points on the
road. Lock height and spots 2 and 3 go to 3 m+, same as no snow. Do not call them "most affected by snow".
Bigger problem: this probably affects every moving storm scan on the route, so route_storm.csv may understate
storm room for error everywhere. Rerun the route sweep with height locked (or a ground/height prior) before
using any per-spot storm number.

Next candidates by the asked ranking (skipping 2, 3, 16 and repeats within 5 m): spot 23 (001_010) storm 0.25 m vs
3 m capped, 8.46 m/s; spot 37 (003_000) 0.25 vs 2.5 m, 6.61 m/s; spot 4 (000_003) 0.75 vs 3 m capped, 5.99 m/s.
Spot 4 already shows the same 2.18 m slide, so treat all three as UNSURE until the height-locked rerun.
