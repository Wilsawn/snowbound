# Blind budget: design (v2, after critic review)
Written with Claude (AI), Nov 20 2026. Builder draft, then a separate critic, then fixes.

## 1. The question
At each place on the route, how far off can the car's position guess be (after its lidar was blind for a while) and still let scan-to-map ICP re-find it, on a day with falling snow vs a day without?
Why an AV engineer cares: lidar can drop out (spray, blockage, reboot). You want to know how much drift the car can absorb before relocalizing, and where on the road that margin is small.

## 2. Metres first, seconds only as an illustration
- **Headline in metres:** the "basin radius" = the biggest starting error ICP still recovers from.
- **Seconds are an illustration, not a measurement:** seconds = radius / (speed x drift rate), with drift rate an assumption (show a band: 1%, 2%, 5% of distance driven). Label it every time.
- **Better later (v2):** measure real drift by dead reckoning from raw IMU / wheel data, if Boreas ships it (check). KISS-ICP cannot do this: it is lidar odometry, so it goes blind too.

## 3. Method
1. Data: 60 s stretches of the storm (2021-01-26-11-22, snowing) and the control (2021-01-19-15-08, snow on the ground, none falling; dry road on the camera), plus the same road from the map drive (2020-11-26). Later: 3 to 4 stretches with different geometry (straight arterial, residential, intersection).
2. Map: map-drive scans placed with ground-truth poses, deskewed. Label it "map built from ground-truth poses" (Burnett et al. used lidar only).
3. Sanity gate (must pass before any sweep): from the true start, recovery about 100% and the along-road error close to the sideways error. Status Nov 20 (20 storm scans, 20 s): with deskew, lateral 0.5 cm, longitudinal 1.7 cm (mean +1.6), recovered 100%. Without deskew, longitudinal was 19.4 cm and only 90% recovered. So deskewing is required.
4. Test points every 20 m, storm and control paired by location.
5. Offsets on separate axes: translation 0.25 m steps from 0.25 to 3 m in 8 directions (heading unchanged), and heading alone at +/-2, 5, 10 deg. Not "5 deg per metre" (that makes heading cause most failures).
6. ICP settings fixed and written down. The first match radius must be larger than the biggest offset (or every result says "for this setting"). Huber weights that start loose and tighten as ICP settles.

## 4. Definitions
- **Recovered:** final error under 0.3 m and 2 deg vs ground truth (about 10x the ground truth's own 2 to 4 cm error; a car has about 0.8 m spare each side in a lane). If final errors fall into two clear clumps, the exact threshold does not matter.
- **Basin radius at a point:** the largest offset where at least 7 of 8 directions recover and every smaller step also passes.

## 5. Outputs
- Route map, green to red: basin radius in metres (seconds band as a small label).
- Headline: paired difference in basin radius, storm minus control, with a sign test or block bootstrap (points 20 m apart overlap, so they are not independent).
- Recovery rate vs offset size, storm vs control.
- Our accuracy next to Burnett et al. (v3: 2.3 cm lateral; v1/v2: 4.7 cm), clearly marked "different map and pipeline, not directly comparable".
- Signed bias (mean) and scatter (std), not only RMSE.

## 6. If storm equals control
"On these stretches, falling snow did not shrink the margin, within the interval shown." Still worth posting: Burnett et al. never tested bad starting guesses, the interval bounds any hidden effect, and the map still shows the weak spots (open roads, few walls).

## 7. Attribution (what an AV engineer will ask)
Two drives a week apart also differ in snowbanks, parked cars, lane and speed. So:
- Add a third run: the storm with falling snow filtered out (DROR). If filtering closes the gap, it was the falling snow.
- Word claims as "this snowy day vs that day", not "snow does X".

## 8. Hours and risks
Setup 2 h, map + deskew 2 h (deskew done), sanity gate 1 h, sweep code 3 h, runs 2 h, stats 1.5 h, figures 2 h, write-up 2.5 h. About 16 h.
Risks:
1. Frame or timestamp bug: watch the sanity gate (now passing on 20 scans).
2. ICP settings set the basin, not the weather: rerun failures with a bigger match radius before believing them.
3. Map change (two months) swamps weather: control recovery at 1 m should stay high (now 95% for the storm on 20 scans with 1 m / 5 deg).

## 9. Do not claim
- Not "first ever" (Zhang et al. 2024 arXiv 2403.05666 do worst-case ICP on Boreas with learned perturbations; Pomerleau et al. 2013 sweep ICP starting offsets in general). Say: start offsets along a route, by weather.
- Not comparable to 2.3 cm (different map and pipeline).
- Seconds come from an assumed drift rate.
- One route, one drive per weather.
- Results hold for our ICP settings.
