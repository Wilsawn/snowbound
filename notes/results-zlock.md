# Whole route, height-locked rerun vs the original (Nov 23, 2026)

Plain words: the same 271 paired test points, seeds, push sizes (0.25 to 3 m), 8 directions, 5 deg heading error and 3.5 m
window as results/route_pairs.csv, but the matcher could only move the scan sideways and in yaw (scripts/sweep_route_zlock.py).
Reason: the 23 November check (notes/critic-most-affected.md) found the free matcher sinks moving storm scans about 2.5 m so the
snow in the air lands on the road, which the test counted as a failure. Every number below is computed by scripts/compare_zlock.py.

## What changed, in plain words

- The lock held: the matcher moved no scan up or down at any of the 542 point-days (largest height change 0.000000 m). On its own that
  column only shows the locked code ran; the real proof is below under "Did the lock hold".
- The headline moves. Storm smaller at 111 of 271 spots (was 147), the same at 142 (was 114), bigger at 18 (was 10). The median
  storm minus no-snow gap goes from -0.5 m to 0 m. Both typical values (medians) are unchanged: storm 2.5 m, no snow 3 m.
- The storm gets easier for the matcher once it cannot sink: 83 storm spots recover from a bigger push, 170 the same, 18 a smaller
  one. No snow moves little (13 up, 4 down, 254 the same): the lock alone changes 17 no-snow answers, so it is not only a storm effect.
- Of the 23 storm spots that read 0 m before, 7 now recover (spots 2 and 3 to 3 m+, spot 20 to 1.25 m, spot 258 to 1 m, spot 270
  to 0.75 m, spot 116 to 0.5 m, spot 115 to 0.25 m) and 16 still read 0 m. Two spots that were not 0 m before now are (spots 22 and 23,
  001_009 and 001_010, from 0.75 m and 0.25 m), so the storm has 18 spots at 0 m now. 12 spots are 0 m on both days (was 14): those
  are places where the car cannot recover even without snow, so they say nothing about snow.
- The site's three stops all grew: spot 42 from 1.25 m to 1.5 m, spot 90 from 1 m to 2.5 m, spot 117 from 0.5 m to 2 m. The no-snow
  values at those spots are unchanged (3 m+, 3 m+, 1.75 m), so at spot 117 the storm now reads bigger than no snow.
- Segments 1, 4 and 5 move to 3 m in the storm, the same as no snow. Segments 2 and 3 keep a storm deficit (1.625 m vs 3 m, 2 m vs 3 m).
  Segment 6 is the stretch where no snow is worse (storm 1.25 m vs no snow 0.5 m).
- The first study's street (22 of 22 first-study spots matched within 5 m; they are route spots 21 to 42, inside segment 2): the first
  study said 1.75 m, the route's free run 1.375 m, the locked run 1.5 m.

## Did the lock hold

Largest height change the locked matcher made at any point, either day: 0.000000 m (storm max 0.000000, no snow max 0.000000).
That column is a weak check on its own: the locked matcher cannot change the height by construction, so it reads 0 whenever it ran.
The proof that it did run is that the results differ from the original at 101 storm and 17 no-snow point-days under the same seeds (the free matcher is deterministic, so a rerun of it would have matched exactly).

## Headline numbers

| | original (free matcher) | height locked |
|---|---|---|
| Storm, typical spot (median) | 2.5 m | 2.5 m |
| No snow, typical spot (median) | 3 m | 3 m |
| Storm spots at the 3 m cap | 91 of 271 | 120 of 271 |
| No-snow spots at the 3 m cap | 201 of 271 | 202 of 271 |
| Storm smaller / same / bigger | 147 / 114 / 10 | 111 / 142 / 18 |
| Storm minus no snow, median | -0.5 m | 0 m |
| Storm spots at 0 m | 23 | 18 |
| Spots at 0 m on both days | 14 | 12 |

## How the per-spot values moved

Storm: bigger at 83 spots, same at 170, smaller at 18; median change 0 m, mean +0.18 m.
No snow: bigger at 13 spots, same at 254, smaller at 4; median change 0 m, mean +0.01 m.

## The 23 spots that read 0 m in the storm before

23 spots. With the height locked: spot 2 (000_001) 3 m+, spot 3 (000_002) 3 m+, spot 19 (001_006) 0 m, spot 20 (001_007) 1.25 m, spot 57 (004_008) 0 m, spot 58 (004_009) 0 m, spot 59 (004_010) 0 m, spot 60 (004_011) 0 m, spot 61 (005_000) 0 m, spot 62 (005_001) 0 m, spot 63 (005_002) 0 m, spot 115 (009_006) 0.25 m, spot 116 (009_007) 0.5 m, spot 162 (013_005) 0 m, spot 163 (013_006) 0 m, spot 221 (018_004) 0 m, spot 222 (018_005) 0 m, spot 223 (018_006) 0 m, spot 224 (018_007) 0 m, spot 258 (021_005) 1 m, spot 259 (021_006) 0 m, spot 269 (022_004) 0 m, spot 270 (022_005) 0.75 m.
Of these, no snow was 0 m too at 14; with the lock those read 0 m, 0 m, 0 m, 0 m, 0 m, 0.25 m, 0 m, 0 m, 0 m, 0 m, 0 m, 0 m, 0 m, 0 m.

## Per segment (the route's same-direction stretches over 400 m, by storm scan time)

| segment | points | storm median, original | storm median, locked | no snow median, original | no snow median, locked |
|---|---|---|---|---|---|
| segment 1 (463 m, in drive order) | 18 | 1.375 m | 3 m | 3 m | 3 m |
| segment 2 (505 m, in drive order) | 28 | 1.625 m | 1.625 m | 3 m | 3 m |
| segment 3 (421 m, in drive order) | 13 | 2 m | 2 m | 3 m | 3 m |
| segment 4 (2470 m, in drive order) | 82 | 2.5 m | 3 m | 3 m | 3 m |
| segment 5 (3295 m, in drive order) | 113 | 2.5 m | 3 m | 3 m | 3 m |
| segment 6 (432 m, in drive order) | 17 | 1 m | 1.25 m | 0.5 m | 0.5 m |

## The first study's street (results/basin_pairs.csv, route spots within 5 m; these spots lie in segment 2, not in the route's first 463 m)

22 of the first study's 22 spots have a route spot within 5 m. Storm median there: first study 1.75 m, route original 1.375 m, route locked 1.5 m.

## The spots the site shows

| spot | pair | storm original | storm locked | no snow original | no snow locked |
|---|---|---|---|---|---|
| 42 | 003_005 | 1.25 m | 1.5 m | 3 m+ | 3 m+ |
| 90 | 007_005 | 1 m | 2.5 m | 3 m+ | 3 m+ |
| 117 | 009_008 | 0.5 m | 2 m | 1.75 m | 1.75 m |
| 16 | 001_003 | 0.25 m | 3 m+ | 3 m+ | 3 m+ |
| 2 | 000_001 | 0 m | 3 m+ | 3 m+ | 3 m+ |
| 3 | 000_002 | 0 m | 3 m+ | 3 m+ | 3 m+ |
