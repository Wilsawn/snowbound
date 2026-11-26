> Superseded on Nov 23, 2026: the numbers below are from the free matcher. The height-locked rerun (notes/results-zlock.md) is what the site shows now: smaller at 111, same at 142, bigger at 18; medians unchanged.

# Whole route: room for error, storm vs no snow falling, 7.4 km (Nov 22, 2026)
Builder run, then a separate critic checked every number against the CSVs. Scripts: scripts/fetch_route.py (data), scripts/sweep_route.py (sweep). Raw CSVs: results/route_storm.csv, results/route_control.csv, results/route_pairs.csv, per-chunk files in results/chunks/route-chunks/. The 460 m study this extends: notes/results-storm-vs-control.md.

## The question
The first study covered about 430 m of one street. Does "falling snow shrinks the car's room for error" hold over the whole loop, or was that street special?

## The test
Same loop, three Boreas drives (University of Toronto, CC BY 4.0): storm (boreas-2021-01-26-11-22, Jan 26 2021, snow falling), control (boreas-2021-01-19-15-08, Jan 19 2021, snow on the ground, none falling), map (boreas-2020-11-26-13-58, Nov 26 2020, built from ground-truth poses). The three drives share 7,586 m of the 7.9 km loop driven the same way, in six segments.

Test points: one every 20 m along the shared route, taken from the control drive's downloaded scans (one scan every 15th, about 1.5 s apart). Each control point is paired with the storm scan nearest to it; pairs further than 8 m apart are dropped. Pair gap: median 2.2 m, max 8.0 m. Result: 271 paired points along about 7.4 km of the loop, measured point to point in driving order; about 0.8 km of that sits in gaps where no pair was kept (storm scan too far from the control point), so the road actually tested is about 6.6 km. The first study had 22 pairs over about 430 m.

Room for error ("basin"): the car's position guess is pushed 0.25, 0.5, ... up to 3 m off in 8 directions plus a 5 degree heading error, then matched to the map (scan to map ICP, 3.5 m first match radius). Recovered means back within 0.3 m and 2 degrees. The room for error is the largest push where 7 of 8 directions recover. 3 m is the largest push tested, so "3 m+" means it never failed, not that the room is 3 m.

Map: the map drive on disk is thinned to one scan per 1.2 s over the route (one scan per 0.1 s on the 460 m stretch of the first study, left from that download). Each chunk of 12 test points gets its own local map from every map scan within 25 m of its points.

Compute: 23 chunks, 3 to 7 worker processes on the Mac, about 4.5 hours of wall time for the last 20 chunks (the first 3 came from an earlier run and were kept). Each point-day took 3 to 12 minutes on one core.

## Headline numbers (271 pairs)
| | Storm (snow falling) | Control (none falling) |
|---|---|---|
| Median room for error | 2.5 m | 3 m+ |
| Points at 3 m+ (never failed) | 91 (34%) | 201 (74%) |
| Points under 1 m | 47 (17%) | 31 (11%) |
| Points at 0 m (failed at the smallest push) | 23 (8%) | 20 (7%) |
| Lower and upper quartile | 1.5 m, 3 m+ | 2.5 m, 3 m+ |

Paired difference, storm minus control: median -0.5 m, mean -0.48 m. The storm room was smaller at 147 pairs (54%), the same at 114 (42%, of which 88 are both at 3 m+), bigger at 10 (4%).

Read it as "at least": 201 control points are capped at 3 m, so the real control room is "at least 3 m" there and the real difference is at least as big as the numbers above.

## By segment (storm loop-seconds, from fetch_route.py)
| Segment | Pairs | Length | Storm median | Storm 3 m+ | Control median | Control 3 m+ | Diff median | Storm smaller / same / bigger |
|---|---|---|---|---|---|---|---|---|
| 40 to 130 | 18 | 406 m | 1.375 m | 2 | 3 m+ | 17 | -1.375 m | 15 / 3 / 0 |
| 218 to 295 (first study's street) | 28 | 497 m | 1.625 m | 0 | 3 m+ | 21 | -1.25 m | 28 / 0 / 0 |
| 336 to 389 | 13 | 383 m | 2.0 m | 2 | 3 m+ | 11 | -0.5 m | 9 / 4 / 0 |
| 421 to 774 | 82 | 2,455 m | 2.5 m | 36 | 3 m+ | 68 | 0.0 m | 40 / 41 / 1 |
| 885 to 1295 | 113 | 3,254 m | 2.5 m | 51 | 3 m+ | 82 | 0.0 m | 48 / 61 / 4 |
| 1317 to 1402 | 17 | 394 m | 1.0 m | 0 | 0.5 m | 2 | 0.0 m | 7 / 5 / 5 |

What this says:
- The snow effect is real over the whole loop, but it is strongest on the first three segments (the first 1.3 km, including the first study's street): storm medians 1.4 to 2.0 m against a control that almost never failed.
- On the two long segments (5.7 km of the 7.4 km) the storm room is still smaller at 40 to 50% of the pairs and never much bigger, but the median difference is 0 because both days sit at 3 m+ at many points. The cap hides part of the effect there.
- The last segment (1317 to 1402) is hard on both days: control median 0.5 m, 8 of 17 control points at 0 m. There the storm room is bigger at 5 pairs, all of them where the control failed at the smallest push. That stretch is a road or map problem, not a snow problem.
- 14 pairs failed at the smallest push on both days. These are places where the method itself breaks (thin map, open ground, or the 1.2 s map spacing), and they count in both medians.

## Check against the first study (same 22 spots)
Every one of the first study's 22 pairs has a route test point within 5 m (median about 2 m, max 4.5 m). On those 22 spots:
- Control: median 3 m+ in both runs.
- Storm: first study median 1.75 m, route run 1.375 m. The route run came out smaller at 16 spots, the same at 3, bigger at 3; median change -0.5 m.
- Difference storm minus control: median -1.25 m in both runs.

So the conclusion for that street is the same, but the storm numbers moved by about one step (0.25 to 0.5 m). Not pinned down why. What differs: the test points are different scans (chosen from the control drive, about 2 m from the old ones, which were chosen from the storm drive), the random push directions have a different seed, and the local map is built from every map scan within 25 m (one per 0.1 s there, the first study used one per 0.4 s). Treat room-for-error values as good to about half a metre, and compare only numbers from the same run.

## Limits (honest list)
- The route map is one scan per 1.2 s (about 10 m at the map drive's speed), thinner than the first study's. Smaller rooms on the long segments may partly be the thin map; the control run on the same map is the fair comparison, and it mostly still sits at 3 m+.
- 3 m is a cap. 201 of 271 control points and 91 of 271 storm points hit it.
- One pair per 20 m, 8 directions, one heading error (5 degrees). Neighbouring points share road, so counts like "147 of 271" are not independent trials.
- Storm scans are about 11 m apart, so the paired storm scan is up to 8 m from the control point (median 2.2 m).
- The control car drove faster (median 10.8 m/s vs 8.4 m/s at the test points).
- Snow on the ground on both days, falling snow only in the storm. The map day (Nov 26) had no snow.
- 7.4 km of the 7.9 km loop (6.6 km tested); the parts where the drives took different lanes or directions are left out.
