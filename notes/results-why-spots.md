# Why did snow hurt at some spots and not others? (Nov 25, 2026)

Script: scripts/why_spots.py. Per-spot numbers: results/why_spots.csv. Chart: results/why_spots.png. Examples: results/why_spots_examples.jpg. Every number below is printed by the script from that CSV unless it says otherwise.

## The question

The height-locked run (notes/results-zlock.md, results/route_pairs_zlock.csv) has 271 paired spots. At 111 the storm's room for error is smaller than on the no-snow day ("hurt"), at 142 it is the same ("same"), at 18 it is bigger ("bigger"). The hypothesis: snow hurts most on wide open roads with little structure nearby (walls, poles, trees, parked cars), because snow hides curbs and lane edges and traffic spray adds clutter.

## The measures

All measures are taken at the STORM spot's true pose (the same map measures are also taken at the control pose, columns ctrl_*). Frame: the sweep's frame (scripts/sweep_route.py). Each chunk (pair prefix 000 to 022, 12 pairs each, 7 in the last) gets the same local map the sweep used: every map-drive scan (boreas-2020-11-26-13-58) within 25 m of the chunk's storm and control points, points 3 to 60 m from the map car, 0.3 m voxel per scan, 0.2 m voxel overall, in metres east-north-up relative to the chunk's first storm point. Chunk 000 reproduces the sweep's map exactly (50 scans, 732,977 points, as in results/chunks/route-chunks-zlock/chunk_000.done). The car pose is pose_matrix(row, origin) from the pose row nearest the scan time in the storm (or control) drive's applanix/lidar_poses.csv.

Local ground: the median z of the map points 2 to 6 m (horizontal) from the car that lie in the lowest 20 percent of z in that ring. "Above ground" means z minus that value. The lidar sits about 2.2 m above it, which is right for a roof-mounted sensor.

Heading: from vel_east, vel_north. At 3 storm spots and 1 control spot the car was nearly stopped (under 0.5 m/s), and the heading of the nearest pose in time moving faster than 1 m/s was used instead.

(a) Structure: map points 0.5 to 3 m above local ground within 10 m and within 20 m of the car, and per square metre of the disc.

(b) Open width: the distance from the car to the nearest structure point on the left and on the right, measured across the heading, using map points within 25 m ahead and behind and at least 1 m off the car's axis; open width = left + right. A tighter version uses 10 m ahead and behind and at least 1.5 m off the axis (open_width10). The 25 m strip is spoiled on curves and at cross streets: the straight line 25 m ahead of the car leaves the lane and hits curbs and parked cars, which is why that version reads about 1 m on one side at most spots. The 10 m strip is the one the chart and the verdict use.

(c) Storm clutter: the share of the storm scan's points (the scan at scan_time_us, placed at the true pose, points more than 3 m from the lidar, as the sweep's keep_ring, and below 4 m above ground) with no map point within 0.5 m (cKDTree). The same share for the control scan at its pose is the baseline.

(d) Speed: speed_mps from results/route_storm_zlock.csv (and route_control_zlock.csv).

### A problem found on the first run, and what was done about it

On the stretches where the map drive on disk has one scan every 0.1 s instead of every 1.2 s (chunks 001 to 003, 009, 010, 012, 013, 019, 020; 168 to 792 map scans against 33 to 133 elsewhere (chunk 021 has 133 raw scans, 59 thinned)), the sweep's map holds the map drive's own traffic, stamped along the road at car height. At spot 003_005, a wide arterial on the dashcam, the raw count was 24,010 "structure" points within 10 m, most of them 0.5 to 2 m high and sitting in or next to the car's own lane. So the raw structure count mostly measures how dense the map is there (Spearman of the raw count with the number of map scans +0.35), and the dense-map chunks are exactly the hurt ones (Spearman of map scans with diff_m -0.35).

So every map measure is computed three ways and all three are in the CSV:
- raw: the sweep's map as is (columns n_struct_10m, open_width_m, ...). Kept as a record; not used for the verdict.
- thin: the map thinned to one scan per 1.2 s everywhere (the sweep's nominal design; columns *_thin).
- static: from the thin map, only 0.5 m ground cells that at least 3 different map scans put a band point in. A wall, pole or tree is seen by every passing scan; a moving car lands in a cell once (columns *_static). The static count is unrelated to map density (Spearman with map scans -0.03) and matches the dashcam at the spots checked (below). This is the headline structure measure.

Static structure still counts traffic that was stopped for more than about 3.6 s in the map drive (a queue at a light), and it misses thin things the 0.3 m voxel drops. The raw-to-static Spearman is +0.70, so the ranking is only partly changed.

### Sanity checks

- Groups from results/route_pairs_zlock.csv: hurt 111, same 142, bigger 18. Control at 3 m+: 202.
- 003_005 (dashcam: wide arterial, poles far back): raw 24,010 points within 10 m, static 5,029, open width (10 m strip) 9.3 m. The static count is still high; the map drive probably sat in traffic there (not checked).
- 009_008 (dashcam: a bridge with railings on both sides; this spot is in the bigger group): static 1,149, open width 17.4 m.
- Examples sheet: 003_008 and 004_007 (hurt, 0 static points, open width 34 m and 31 m) are wide arterials in the dashcam; 022_006 and 021_008 (same, about 5,900 static points, open width 4.6 m and 13.9 m) are a building wall and a tree-lined lane.

## The numbers (all 271 pairs; hurt vs same, bigger kept out of the two-group test)

Typical = median. Mann-Whitney U, two-sided. Rank-biserial: positive means the hurt group tends to be larger. Spearman with diff_m (storm minus control): a negative value means the measure is larger where snow hurt more; "no bigger" leaves out the 18 bigger pairs (253 left).

| measure | typical, hurt (111) | typical, same (142) | typical, bigger (18) | hurt minus same | p | rank-biserial | Spearman with diff_m, all 271 | Spearman, 253 no bigger |
|---|---|---|---|---|---|---|---|---|
| static structure within 10 m (points) | 686 | 582 | 1040 | +104 | 0.096 | +0.12 | -0.05 (p 0.432) | -0.13 (p 0.040) |
| static structure within 20 m (points) | 11,382 | 12,262 | 13,272 | -880 | 0.116 | -0.12 | +0.18 (p 0.003) | +0.14 (p 0.022) |
| static density within 10 m (points per m2) | 2.18 | 1.85 | 3.31 | +0.33 | 0.096 | +0.12 | -0.05 (p 0.432) | -0.13 (p 0.040) |
| open width, 10 m strip (m) | 11.2 | 13.9 | 11.1 | -2.7 | 0.015 | -0.18 | +0.14 (p 0.021) | +0.18 (p 0.004) |
| left, 10 m strip (m) | 6.3 | 8.7 | 5.4 | -2.5 | 0.033 | -0.16 | +0.13 (p 0.037) | +0.16 (p 0.009) |
| right, 10 m strip (m) | 3.6 | 4.4 | 5.0 | -0.8 | 0.003 | -0.22 | +0.21 (p under 0.001) | +0.20 (p 0.001) |
| open width, 25 m strip (m) | 2.9 | 5.3 | 6.6 | -2.4 | 0.097 | -0.12 | +0.16 (p 0.007) | +0.14 (p 0.026) |
| storm clutter (share of scan points off the map) | 0.132 | 0.116 | 0.096 | +0.015 | 0.016 | +0.18 | -0.29 (p under 0.001) | -0.24 (p under 0.001) |
| control clutter (same, control scan) | 0.017 | 0.020 | 0.026 | -0.003 | 0.291 | -0.08 | +0.07 (p 0.251) | +0.03 (p 0.629) |
| storm speed (m/s) | 8.3 | 8.6 | 7.2 | -0.3 | 0.873 | +0.01 | -0.00 (p 0.940) | +0.02 (p 0.793) |
| control speed (m/s) | 12.8 | 10.6 | 9.5 | +2.2 | under 0.001 | +0.24 | -0.23 (p under 0.001) | -0.23 (p under 0.001) |
| map scans in the chunk's map | 168 | 72 | 110 | +96 | under 0.001 | +0.36 | -0.35 (p under 0.001) | -0.35 (p under 0.001) |
| raw structure within 10 m (sweep's map, counts ghost traffic) | 1,949 | 962 | 1,412 | +987 | under 0.001 | +0.41 | -0.35 (p under 0.001) | -0.42 (p under 0.001) |

Reading it:
- Structure: the hurt spots have slightly MORE static structure within 10 m than the same spots (686 vs 582 points, p 0.096, rank-biserial +0.12), not less. Within 20 m the two groups are alike (p 0.116). The hypothesis predicts the opposite sign.
- Open width: the hurt spots are NARROWER (11.2 m vs 13.9 m, p 0.015, rank-biserial -0.18; Spearman +0.14 to +0.18, wider road goes with a less negative diff). Again the opposite sign to the hypothesis. The 25 m strip version says the same, weaker.
- Clutter: the storm scan is more cluttered where snow hurt (0.132 vs 0.116, p 0.016, rank-biserial +0.18; Spearman -0.29, more clutter goes with more hurt). This is the only measure in the direction the hypothesis would want, and it is a measure of the snow itself, not of the road. The storm scan is more cluttered than the control scan at 262 of 271 spots (typical +0.098), and storm clutter does not track control clutter (Spearman +0.09), so it is the storm day, not the place.
- Speed: nothing (storm speed p 0.873). The control car was faster at the hurt spots (12.8 vs 10.6 m/s), which says the hurt spots are faster roads on a normal day, not that speed in the storm matters.
- Map density: the strongest road-side predictor of hurt is how many map scans the chunk's map has (p under 0.001, Spearman -0.35). That is a property of the data on disk, not of the road.

## By chunk (pair prefix; chunks run in drive order, so 000 to 001 is segment 1, 001 to 003 is segment 2, the first study's street, 003 to 004 segment 3, 004 to 011 segment 4, 011 to 021 segment 5, 021 to 022 segment 6, by the segment point counts in notes/results-zlock.md)

| chunk | pairs | hurt | share hurt | storm typical | no snow typical | static structure 10 m | static structure 20 m | open width, 10 m strip | storm clutter | speed | raw structure 10 m | map scans (thinned) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 000 | 12 | 4 | 33% | 3 m+ | 3 m+ | 3810 | 20780 | 7.1 m | 0.111 | 5.4 m/s | 3982 | 50 (50) |
| 001 | 12 | 9 | 75% | 1.5 m | 3 m+ | 786 | 12369 | 7.3 m | 0.200 | 5.7 m/s | 3061 | 168 (86) |
| 002 | 12 | 12 | 100% | 2 m | 3 m+ | 550 | 6530 | 8.3 m | 0.178 | 9.8 m/s | 11101 | 374 (45) |
| 003 | 12 | 12 | 100% | 1.75 m | 3 m+ | 1576 | 6098 | 9.2 m | 0.243 | 7.2 m/s | 11524 | 792 (113) |
| 004 | 12 | 4 | 33% | 2.25 m | 3 m+ | 38 | 6465 | 18.9 m | 0.197 | 10.5 m/s | 1050 | 94 (93) |
| 005 | 12 | 8 | 67% | 1.25 m | 2.375 m | 504 | 13523 | 13.5 m | 0.099 | 7.9 m/s | 832 | 113 (113) |
| 006 | 12 | 1 | 8% | 3 m+ | 3 m+ | 687 | 13460 | 13.3 m | 0.104 | 7.9 m/s | 997 | 65 (65) |
| 007 | 12 | 4 | 33% | 3 m+ | 3 m+ | 626 | 15542 | 12.4 m | 0.145 | 8.3 m/s | 972 | 68 (68) |
| 008 | 12 | 1 | 8% | 3 m+ | 3 m+ | 438 | 13376 | 13.3 m | 0.119 | 9.6 m/s | 732 | 71 (71) |
| 009 | 12 | 5 | 42% | 2.25 m | 2.75 m | 942 | 13288 | 15.5 m | 0.115 | 10.6 m/s | 1480 | 327 (61) |
| 010 | 12 | 4 | 33% | 3 m+ | 3 m+ | 482 | 10947 | 14.4 m | 0.101 | 9.4 m/s | 944 | 284 (62) |
| 011 | 12 | 3 | 25% | 2.75 m | 3 m+ | 1198 | 12761 | 9.0 m | 0.080 | 5.6 m/s | 1296 | 35 (34) |
| 012 | 12 | 2 | 17% | 3 m+ | 3 m+ | 566 | 13122 | 12.9 m | 0.091 | 6.5 m/s | 724 | 221 (60) |
| 013 | 12 | 3 | 25% | 2.25 m | 3 m+ | 842 | 12356 | 14.4 m | 0.122 | 9.7 m/s | 1288 | 381 (63) |
| 014 | 12 | 3 | 25% | 3 m+ | 3 m+ | 686 | 12276 | 14.6 m | 0.116 | 10.2 m/s | 783 | 70 (70) |
| 015 | 12 | 4 | 33% | 3 m+ | 3 m+ | 352 | 11674 | 14.3 m | 0.103 | 8.7 m/s | 921 | 72 (72) |
| 016 | 12 | 2 | 17% | 3 m+ | 3 m+ | 654 | 12965 | 13.2 m | 0.079 | 9.2 m/s | 1047 | 67 (67) |
| 017 | 12 | 7 | 58% | 2.5 m | 3 m+ | 676 | 12548 | 13.4 m | 0.077 | 10.6 m/s | 958 | 43 (43) |
| 018 | 12 | 3 | 25% | 0.625 m | 1 m | 219 | 10352 | 6.4 m | 0.108 | 9.0 m/s | 1119 | 108 (107) |
| 019 | 12 | 5 | 42% | 2.75 m | 3 m+ | 1604 | 4610 | 9.4 m | 0.180 | 11.7 m/s | 5494 | 766 (119) |
| 020 | 12 | 10 | 83% | 2.25 m | 3 m+ | 454 | 5788 | 11.2 m | 0.164 | 10.9 m/s | 11524 | 429 (54) |
| 021 | 12 | 5 | 42% | 1.75 m | 1.125 m | 1564 | 6474 | 11.9 m | 0.114 | 6.0 m/s | 2783 | 133 (59) |
| 022 | 7 | 0 | 0% | 1.25 m | 0 m | 2020 | 16380 | 7.1 m | 0.126 | 5.7 m/s | 2336 | 33 (33) |

("3 m+" in the typical columns is the script's 3 m, which is the cap.) Across the 23 chunks, Spearman of the share hurt with the chunk's typical value: static structure within 10 m +0.02 (p 0.912), open width (10 m strip) -0.09 (p 0.672), storm clutter +0.38 (p 0.073), speed +0.25 (p 0.245). The hurt stretches (001 to 003, 005, 017, 020) are not the open ones: chunk 004 is the most open stretch (38 static points, 18.9 m wide) and is hurt at only 4 of 12; chunks 002 and 003 (100% hurt) are 8 to 9 m wide with 550 to 1,576 static points, which is mid-table.

## Capped-only check (202 pairs where no snow was 3 m+, so the storm could have been cut: hurt 83, same 119, bigger 0)

| measure | typical, hurt | typical, same | hurt minus same | p | rank-biserial | Spearman with diff_m |
|---|---|---|---|---|---|---|
| static structure within 10 m | 714 | 489 | +225 | 0.035 | +0.17 | -0.17 (p 0.016) |
| static structure within 20 m | 11,666 | 11,673 | -7 | 0.335 | -0.08 | +0.10 (p 0.168) |
| open width, 10 m strip | 12.1 m | 14.0 m | -1.9 m | 0.062 | -0.15 | +0.15 (p 0.036) |
| open width, 25 m strip | 2.9 m | 5.4 m | -2.5 m | 0.134 | -0.12 | +0.14 (p 0.046) |
| storm clutter | 0.130 | 0.116 | +0.014 | 0.053 | +0.16 | -0.21 (p 0.003) |
| storm speed | 9.1 m/s | 9.0 m/s | +0.1 m/s | 0.750 | +0.03 | +0.00 (p 0.984) |
| map scans | 221 | 71 | +150 | under 0.001 | +0.35 | -0.33 (p under 0.001) |

The picture does not change. If anything the "more structure where it hurt" reading gets a little firmer (p 0.035, rank-biserial +0.17), and the width gap stays in the same direction (p 0.062).

## Verdict

The hypothesis does NOT hold: on this route the spots where snow hurt have a little more static structure within 10 m (686 vs 582 points, p 0.096, rank-biserial +0.12) and are narrower (11.2 m vs 13.9 m, p 0.015, rank-biserial -0.18), the opposite of "wide and empty", and these are small effects either way; the only measure that separates the groups in the expected direction is the storm scan's own clutter (0.132 vs 0.116, p 0.016, Spearman -0.29 with the storm-minus-control gap), which is the snow, not the road.

No sentence is proposed for the post, since the hypothesis is not supported. If a one-liner is wanted for the opposite finding, it should wait for a second storm.

What the data does say, for whatever it is worth: where snow hurt, the storm scan had more points that match nothing in the map (anything that was not there on the map day: snow in the air, and whatever else changed), and the stretch's map on disk was denser (0.1 s scan spacing, which stamps the map drive's traffic into the map). Whether the second one is a cause (ghost traffic in the map pulls the matcher) or a coincidence (those stretches were downloaded densely for the first study, which was chosen because snow hurt there) cannot be told from this data. The first-study street (chunks 001 to 003) was picked before the whole-route run, so that is a real possibility.

## Limits

- One storm, one control day, one route. 271 spots 20 m apart on the same roads are not independent trials; a p of 0.015 here is weaker than it looks.
- The map is from two months earlier (Nov 26, 2020). Parked cars, construction and foliage moved between the map day and the storm. The structure counts describe the map, not what the storm car saw.
- "Structure" is map points 0.5 to 3 m above local ground. It misses curbs and lane paint (under 0.5 m), which is what the hypothesis is really about: snow hides the curb line whether or not there is a wall 8 m away. It also counts fences, hedges and snowbanks the same as a wall, and the 0.3 m voxel drops thin poles and wires.
- Static structure (3 or more map scans per 0.5 m cell on the 1.2 s thinned map) still counts traffic that sat still in the map drive for more than about 3.6 s, and 003_005 (open on the dashcam, 5,029 static points) looks like such a case. The raw count on the sweep's actual map is unusable as a structure measure on the dense-map chunks, for the reason given above.
- Local ground is one number per spot (lowest 20 percent within 2 to 6 m); on crowned roads or at a kerb it can be off by a few tens of centimetres, which shifts points in and out of the 0.5 m lower edge of the band.
- Open width is measured along a straight strip; on curves even the 10 m version can hit the inside of the bend. Nothing was capped at 40 m in the storm set (2 control spots were on the 10 m strip).
- Clutter at 0.5 m is a coarse measure of "snow in the scan": it also counts anything that changed since the map day. The control baseline (typical 0.018) shows that part is small.
- The hurt / same split hides size: "hurt" includes 0.25 m drops and 3 m drops alike. The Spearman columns with diff_m are the graded version and tell the same story.
- The map measures at the control pose track the storm pose closely (Spearman +0.87 for static structure within 10 m), so the pair gap (median 2.2 m) does not matter for this.

## Where every number comes from

- Groups, basins, diff_m, capped flags: results/route_pairs_zlock.csv (written by scripts/sweep_route_zlock.py).
- Scan times and speeds: results/route_storm_zlock.csv, results/route_control_zlock.csv.
- All measures, medians, Mann-Whitney p, rank-biserial, Spearman, by-chunk table, capped-only table: scripts/why_spots.py (printed at the end of its run), from results/why_spots.csv.
- The four example frames were picked as the extremes on purpose (the two hurt spots with the least structure and most width, the two same spots with the most structure), so they show what the hypothesis predicts, not what the whole set shows; the chart carries the verdict.
- Chart: results/why_spots.png, example sheet: results/why_spots_examples.jpg, both drawn by scripts/why_spots.py; dashcam frames from docs/media/spots/<pair>_storm_cam.jpg.
- Segment to chunk mapping: segment point counts in notes/results-zlock.md (18, 28, 13, 82, 113, 17 in drive order) against chunks of 12 pairs.
- Map and frame conventions: scripts/score_60s.py (build_map, pose_matrix, keep_ring, voxel_downsample) and scripts/sweep_route.py.
